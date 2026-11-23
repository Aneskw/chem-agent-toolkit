"""Reuse source-bound preparation facts before an image has been built."""
import copy
from pathlib import Path
from creation_pipeline.records import read_json, write_json
from .contracts import CONTRACT_VERSION, tool_name, tool_version, validate
from .environment import fingerprint
from .environment_state import locations, locked


def anchors(sources):
    return sorted({e['sha256'] for e in sources.evidence if e.get('kind') == 'source_locator'})


class Investigations:
    def __init__(self, root):
        self.root = Path(root)
        self.path = locations(self.root)[1] / 'prepared-plans.json'

    def entries(self):
        with locked(self.root, 'prepared-plans'):
            return read_json(self.path) if self.path.exists() else []

    def remember(self, plan, sources):
        validate(plan)
        # Evidence IDs are group-local; keep the source set and original provenance explicitly.
        entry = {'key': fingerprint({'plan': plan, 'anchors': anchors(sources)}),
                 'state': 'prepared', 'plan': copy.deepcopy(plan),
                 'anchors': anchors(sources), 'evidence': [copy.deepcopy(e) for e in sources.evidence if e['id'] in plan['evidence']]}
        with locked(self.root, 'prepared-plans'):
            items = read_json(self.path) if self.path.exists() else []
            write_json(self.path, [i for i in items if i['key'] != entry['key']] + [entry])

    def invalidate(self, plan, reason):
        with locked(self.root, 'prepared-plans'):
            values = read_json(self.path) if self.path.exists() else []
            for value in values:
                if fingerprint(value['plan']) == fingerprint(plan):
                    value.update(state='needs_revision', failure=reason)
            write_json(self.path, values)

    def context(self, entity, sources):
        wanted = {tool_name(t['name']) for t in entity.get('tool_requirements', [])}
        current = set(anchors(sources))
        return [{'key': e['key'], 'state': e['state'],
                 'same_source_set': set(e['anchors']) == current,
                 'requirements': {k: e['plan'][k] for k in ('platform', 'tools', 'resources', 'conditions')},
                 'notes': e['plan']['investigation_notes'], 'record': str(self.path)}
                for e in self.entries() if e.get('state') == 'prepared' and e['plan'].get('contract_version') == CONTRACT_VERSION
                and wanted.intersection(tool_name(t['name']) for t in e['plan']['tools'])]

    def resolve(self, entity, sources):
        hints = entity.get('tool_requirements', [])
        if not hints or entity.get('environment_gaps') or entity.get('resources'):
            return None
        if any(not h['version'].strip() for h in hints):
            return None
        needed = {(h['kind'], tool_name(h['name']), tool_version(h['version'])) for h in hints}
        current = anchors(sources)
        matches = []
        for entry in self.entries():
            p = entry['plan']
            if entry.get('state') != 'prepared' or p.get('contract_version') != CONTRACT_VERSION:
                continue
            available = {(t['kind'], tool_name(t['name']), tool_version(t['version'])) for t in p['tools']}
            if needed.issubset(available) and not p['resources'] and not p['unresolved']:
                if p['conditions'] != {'accelerator': 'none', 'minimum_memory_gib': None, 'network_required': False}:
                    continue
                # Rebind only facts actually cited by this plan, not the entire group's locator map.
                original = {e['id']: e for e in entry['evidence'] if e.get('kind') == 'source_locator'}
                rebound = []
                for eid in p['evidence']:
                    fact = original.get(eid)
                    options = [e['id'] for e in sources.evidence if fact and e.get('kind') == 'source_locator'
                               and e['sha256'] == fact['sha256'] and e['path'] == fact['path']]
                    if len(options) != 1:
                        break
                    rebound.append(options[0])
                else:
                    copied = copy.deepcopy(p)
                    copied['evidence'] = rebound
                    copied['skill_tools'] = [t['name'] for t in p['tools']
                        if (t['kind'], tool_name(t['name']), tool_version(t['version'])) in needed]
                    copied['skill_resources'] = []
                    matches.append(copied)
        if not matches:
            return None
        contracts = {fingerprint({k: p[k] for k in ('platform', 'tools', 'resources', 'conditions', 'usage_notes')}) for p in matches}
        return copy.deepcopy(matches[-1]) if len(contracts) == 1 else None
