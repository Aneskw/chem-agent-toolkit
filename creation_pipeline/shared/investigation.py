"""Reuse source-bound preparation facts before an image has been built."""
import copy
from pathlib import Path
from creation_pipeline.records import lease, read_json, write_json
from .contracts import CONTRACT_VERSION, tool_name, tool_version, validate
from .environment import fingerprint


def anchors(sources):
    return sorted({e['sha256'] for e in sources.evidence if e.get('kind') == 'source_locator'})


class Investigations:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / 'prepared-plans.json'

    def entries(self):
        with lease(self.root, 'prepared-plans'):
            return read_json(self.path) if self.path.exists() else []

    def remember(self, plan, sources):
        validate(plan)
        # Evidence IDs are group-local; keep the source set and original provenance explicitly.
        entry = {'key': fingerprint({'plan': plan, 'anchors': anchors(sources)}),
                 'state': 'prepared_not_built', 'plan': copy.deepcopy(plan),
                 'anchors': anchors(sources), 'evidence': copy.deepcopy(sources.evidence)}
        with lease(self.root, 'prepared-plans'):
            items = read_json(self.path) if self.path.exists() else []
            write_json(self.path, [i for i in items if i['key'] != entry['key']] + [entry])

    def context(self, entity, sources):
        wanted = {tool_name(t['name']) for t in entity.get('tool_requirements', [])}
        current = set(anchors(sources))
        return [{'key': e['key'], 'state': e['state'],
                 'same_source_set': set(e['anchors']) == current,
                 'requirements': {k: e['plan'][k] for k in ('platform', 'tools', 'resources', 'conditions')},
                 'notes': e['plan']['investigation_notes'], 'record': str(self.path)}
                for e in self.entries() if e['plan'].get('contract_version') == CONTRACT_VERSION
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
            if p.get('contract_version') != CONTRACT_VERSION or entry['anchors'] != current:
                continue
            available = {(t['kind'], tool_name(t['name']), tool_version(t['version'])) for t in p['tools']}
            if needed.issubset(available) and not p['resources'] and not p['unresolved']:
                # Exact immutable sources AND exact local locator map avoid foreign eN references.
                old = {(e['id'], e['sha256'], e['path']) for e in entry['evidence'] if e.get('kind') == 'source_locator'}
                new = {(e['id'], e['sha256'], e['path']) for e in sources.evidence if e.get('kind') == 'source_locator'}
                if old == new:
                    matches.append(p)
        if not matches:
            return None
        contracts = {fingerprint({k: p[k] for k in ('platform', 'tools', 'resources', 'conditions', 'usage_notes')}) for p in matches}
        return copy.deepcopy(matches[-1]) if len(contracts) == 1 else None
