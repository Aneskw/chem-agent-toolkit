"""Structured decisions; source text and task code remain outside image identity."""
import copy
from creation_pipeline.schemas import obj, array, STRING as S, STRINGS as SS, CANDIDATES as OLD_CANDIDATES
from creation_pipeline.schemas import REVIEW as OLD_REVIEW

B = {'type': 'boolean'}
TOOL = {'name': S, 'version': S, 'kind': {'type': 'string', 'enum': ['runtime', 'python', 'executable', 'system']}, 'probe': SS}
RESOURCE = {'name': S, 'url': S, 'version': S, 'included_in_image': B, 'usage': S}
TOOLS = array(TOOL)
RESOURCES = array(RESOURCE)
DECISION = {'status': {'type': 'string', 'enum': ['ready', 'blocked']}, 'reason': S, 'resume_when': S}
ENVIRONMENT = obj({**DECISION, 'selection': {'type': 'string', 'enum': ['reuse', 'extend', 'new']},
    'environment_id': S, 'environment_version': S, 'platform': S, 'base_image': S, 'tools': TOOLS, 'resources': RESOURCES,
    'conditions': obj({'accelerator': {'type': 'string', 'enum': ['none', 'nvidia', 'amd']},
        'minimum_memory_gib': {'type': ['number', 'null']}, 'network_required': B}),
    'usage_notes': SS, 'investigation_notes': SS, 'unresolved': SS, 'evidence': SS,
    'files': array({'path': S, 'content': S}), 'rationale': S})
CANDIDATES = copy.deepcopy(OLD_CANDIDATES)
CANDIDATES['properties']['candidates']['items']['properties'].update(tools=SS, resources=SS)
CANDIDATES['properties']['candidates']['items']['properties'].update(
    tool_requirements=array({'name': S, 'version': S, 'kind': TOOL['kind']}), environment_gaps=SS)
CANDIDATES['properties']['candidates']['items']['required'] += ['tools', 'resources', 'tool_requirements', 'environment_gaps']
ITEM = {'id': S, 'file': S, 'start_line': {'type': 'integer'}, 'end_line': {'type': 'integer'},
        'necessary': B, 'reason': S, 'expected_check': S}
REVIEW = copy.deepcopy(OLD_REVIEW)
REVIEW['properties']['findings']['items']['properties']['category']['enum'] += ['concision']
REVIEW['properties']['execution_items'] = array(ITEM)
REVIEW['required'].append('execution_items')
REVIEW['properties']['findings']['items']['properties']['owner'] = {'type': 'string', 'enum': ['content', 'environment']}
REVIEW['properties']['findings']['items']['required'].append('owner')
EXECUTION = obj({'status': {'type': 'string', 'enum': ['ready', 'blocked']}, 'reason': S,
    'resume_when': S, 'blocked_owner': {'type': 'string', 'enum': ['none', 'content', 'external']}, 'cases': array({'item_id': S, 'files': array({'path': S, 'content': S}),
        'command': SS, 'expected_exit': {'type': 'integer'}, 'stdout_contains': SS,
        'output_files': SS, 'check_command': SS, 'basis': S}),
    'audit_risks': {'type': 'array', 'items': {'type': 'string', 'enum': ['context_injection', 'monkeypatch', 'uncertain_oracle', 'complex_wrapper']}},
    'deferred': array({'item_id': S, 'reason': S, 'resume_when': S}), 'context_notes': SS})
REPAIR = obj({'action': {'type': 'string', 'enum': ['retry', 'environment', 'content', 'test', 'pipeline', 'blocked']},
              'reason': S, 'new_evidence_or_change': S, 'resume_when': S,
              'defect_location': S, 'defect_evidence': S})
