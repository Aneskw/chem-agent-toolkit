"""Single-shot DeepSeek execution for the native discovery/author/review stages.

The Codex CLI agent loop (tools, workspace helper, resume) is the default and stays
untouched. This module is the opt-in alternative used when ``model.backend`` is
``deepseek_api``: the same stage instructions, context and answer schema are sent as
one bounded chat completion, and the host applies the effects the CLI would have
applied with tools:

* the discovery and review stages return a plain JSON record;
* the author stage additionally returns ``files`` (path + UTF-8 content), which the
  host writes into the run workspace and finalises with the same ``finish`` validation.

Nothing here weakens a contract: the stage schema is still validated locally, and the
author package still goes through ``delivery.finish``/``validate_package``.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from creation_pipeline.records import redact, safe_relative, write_json

# The API provider echoes whole files in the answer, so the bound is larger than a
# planner patch but still finite; it mirrors the planner's documented output cap.
MAX_OUTPUT_TOKENS = 96000
AUTHOR_FILES = {
    'type': 'array',
    'items': {'type': 'object', 'additionalProperties': False,
              'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
              'required': ['path', 'content']},
}
# The execution requirement is a record, not a sentence: contracts.requirement()
# rejects anything else, which blocked run 16 after a correct authoring turn.
AUTHOR_REQUIREMENT = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'status': {'type': 'string', 'enum': ['required', 'not_required', 'unknown']},
                   'reason': {'type': 'string'},
                   'citations': {'type': 'array', 'items': {
                       'type': 'object', 'additionalProperties': False,
                       'properties': {'source_id': {'type': 'string'},
                                      'path': {'type': 'string'},
                                      'quote': {'type': 'string'}},
                       'required': ['source_id', 'path', 'quote']}}},
    'required': ['status', 'reason', 'citations'],
}
AUTHOR_EXTRA = ('files', 'tests', 'issues', 'notes', 'entry', 'runtime_requirement')
AUTHOR_PROPERTIES = {'files': AUTHOR_FILES, 'tests': {'type': 'array'}, 'issues': {'type': 'array'},
                     'notes': {'type': 'array'}, 'entry': {'type': 'object'},
                     'runtime_requirement': AUTHOR_REQUIREMENT}
AUTHOR_INSTRUCTIONS = (
    '\nAPI PROVIDER MODE. You have no tools and cannot read files: every needed material is '
    'inline in this prompt. Do not claim to have read anything that is not shown here. '
    'Return one JSON object that satisfies the schema exactly. Write the complete delivered '
    'files as files:[{path, content}] with UTF-8 text content; SKILL.md is the only top-level '
    'file and every other path starts with scripts/, references/, examples/, resources/ or '
    'assets/. The executable entry must be unambiguous: either ship exactly one runnable '
    'script under scripts/ (and declare entry {kind:"script", path}), or keep exactly ONE '
    'complete unindented python fence in SKILL.md; a markdown entry declaration uses a '
    '0-based block_index (the first block is 0), and extra snippets belong in a non-python '
    'fence or a references/ file. Two or more python fences without an entry declaration '
    'are refused. Also return tests, issues, notes and (when you declare one) entry as usual. '
    'A check needs a result assertion: stdout_contains (list of strings), json_equals (an '
    'OBJECT mapping a dotted field/index path into the parsed stdout JSON to its exact value, '
    'for example {"count": 0} or {"0": "*CCC"} for a top-level array) or a nonempty artifact. '
    'json_equals is never the whole JSON value, and an exit code alone is not a check. '
    'When SKILL.md documents a rejection, the delivered code must implement it; never rely '
    'on an upstream parser to reject a value (an empty or whitespace-only input is often '
    'accepted as an empty value), and a rejection case must use an input that actually '
    'triggers the documented behaviour. '
    'runtime_requirement is an OBJECT {status: required|not_required|unknown, reason, '
    'citations:[{source_id, path, quote}]}; every quote must be copied verbatim from the '
    'source text below and a required status needs at least one citation. '
    'citations[].source_id is the registered SOURCE id (for example recap or license) and '
    'citations[].path is that source\'s snapshot path (for example document.py); the eN '
    'evidence locators are only for evidence references and claims.\n')
PROVIDER_INSTRUCTIONS = {
    'discovery': ('\nAPI PROVIDER MODE. You have no tools and cannot read files: the resource '
                  'workspace, the registered evidence locators and the supplied source texts are '
                  'inline below. Base every claim on them and do not claim to have inspected '
                  'anything else. Evidence ids in the answer must be one of the registered locator '
                  'ids listed in SOURCE EVIDENCE (e1, e2, ...): never invent an id or use a '
                  'descriptive name, and put the cited claim text in claim. Return one JSON object '
                  'that satisfies the schema exactly.\n'),
    'review': ('\nAPI PROVIDER MODE. You have no tools: the delivered files, checks and source '
               'material are inline below. Judge only what is shown and return one JSON object '
               'that satisfies the schema exactly.\n'),
    'author': AUTHOR_INSTRUCTIONS,
}
SOURCE_TEXT_BUDGET = 240000


def evidence_index(sources):
    """The registered locator ids a discovery or author answer may cite."""
    result = []
    for item in getattr(sources, 'evidence', None) or []:
        if not isinstance(item, dict) or not item.get('id'):
            continue
        result.append({'id': item['id'], 'source': item.get('source'), 'path': item.get('path')})
    return result


def provider(config):
    return ((config or {}).get('model') or {}).get('backend') or 'codex_cli'


def is_api(config):
    return provider(config) == 'deepseek_api'


def author_schema(schema):
    """The author answer also carries the delivered files when no tools exist."""
    schema = json.loads(json.dumps(schema))
    properties = schema.setdefault('properties', {})
    for name in AUTHOR_EXTRA:
        properties.setdefault(name, AUTHOR_PROPERTIES[name])
    properties['files'] = AUTHOR_FILES
    properties['runtime_requirement'] = AUTHOR_REQUIREMENT
    required = schema.setdefault('required', [])
    for name in ('files',):
        if name not in required:
            required.append(name)
    return schema


def source_texts(sources, budget=SOURCE_TEXT_BUDGET):
    """Inline source text for a provider that cannot read files itself.

    Only UTF-8 text is inlined; the budget is enforced per prompt and a file that
    does not fit is reported as truncated rather than silently dropped.
    """
    result, used = [], 0
    for source in sources or []:
        root = Path(source['path'])
        for item in source.get('inventory') or []:
            path = root if root.is_file() else safe_relative(root, item['path'])
            entry = {'source_id': source['id'], 'path': item['path'], 'bytes': item.get('bytes'),
                     'sha256': item.get('sha256')}
            if used >= budget:
                result.append(dict(entry, text=None, omitted='source text budget'))
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except (OSError, UnicodeError):
                result.append(dict(entry, text=None, omitted='not UTF-8 text'))
                continue
            limit = budget - used
            if len(text) > limit:
                result.append(dict(entry, text=None, omitted='source text budget'))
                continue
            used += len(text)
            result.append(dict(entry, text=text))
    return result


def materialize(answer, output_directory, metadata_path, metadata_keys=AUTHOR_EXTRA):
    """Write the author answer's files and metadata where the CLI would have written them.

    Paths are relative, repository-style and confined to the staging directory; a
    traversal or absolute path aborts the stage instead of being repaired.
    """
    staging = Path(output_directory)
    staging.mkdir(parents=True, exist_ok=True)
    written = []
    for item in answer.get('files') or []:
        if not isinstance(item, dict) or not isinstance(item.get('path'), str):
            raise ValueError('Author files need a relative path and text content')
        target = safe_relative(staging, item['path'])
        content = item.get('content')
        if not isinstance(content, str):
            raise ValueError('Author file content must be UTF-8 text: ' + item['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8', newline='\n')
        written.append(item['path'])
    metadata = {key: answer[key] for key in metadata_keys if key in answer and key != 'files'}
    write_json(Path(metadata_path), metadata)
    return written


def call(config, prompt, schema, timeout, audit_dir, progress_timeout=None):
    """One bounded DeepSeek call, returning ``(answer, receipt)`` like the CLI path."""
    from creation_pipeline.runtime import deepseek_api
    from creation_pipeline.runtime.model_call import ModelConfigError, ModelExecutionError, ModelOutputInvalid
    model = (config.get('model') or {}).get('api_model')
    reasoning = (config.get('model') or {}).get('reasoning_effort')
    tier = (config.get('model') or {}).get('service_tier')
    started = time.monotonic()
    try:
        answer, receipt = deepseek_api.call(
            prompt, schema, model, timeout=timeout, audit_dir=audit_dir,
            options={'retries': (config.get('model') or {}).get('api_retries') or 0,
                     'max_output_tokens': MAX_OUTPUT_TOKENS, 'stream': True,
                     'connect_retries': (config.get('model') or {}).get('api_connect_retries') or 0},
            reasoning_effort=reasoning, service_tier=tier,
            progress_timeout=progress_timeout)
    except deepseek_api.ApiConfigError as exc:
        error = ModelConfigError(redact(str(exc)))
        error.code, error.kind = getattr(exc, 'code', 'model_config_invalid'), 'model_transport'
        raise error from exc
    except deepseek_api.ApiOutputInvalid as exc:
        error = ModelOutputInvalid(redact(str(exc)))
        error.code, error.kind = getattr(exc, 'code', 'model_output_invalid'), 'model_transport'
        raise error from exc
    except deepseek_api.ApiTransportError as exc:
        error = ModelExecutionError(redact(str(exc)))
        error.code, error.kind = getattr(exc, 'code', 'model_unavailable'), 'model_transport'
        raise error from exc
    receipt = dict(receipt, backend='deepseek_api', elapsed_seconds=round(time.monotonic() - started, 3))
    return answer, receipt
