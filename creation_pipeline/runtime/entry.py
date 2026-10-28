"""Source association and deterministic delivered-entry materialization.

No business implementation is generated here. The delivered entry is resolved in a
fixed order - an explicit caller binding, then a validated author declaration, then
conservative recognition of a single conforming candidate. A Markdown entry is one
complete unindented fenced Python block; its bytes, locator and delivery manifest
are bound.
"""
import ast
import builtins
import copy
import hashlib
import json
import math
import re
import symtable
import time
from pathlib import Path

from creation_pipeline.records import safe_relative, write_json, file_digest, redact
from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import fingerprint


class EntryError(ValueError):
    def __init__(self, code, message, lane='binding', kind='unsupported_contract'):
        self.code, self.lane, self.kind = code, lane, kind
        super().__init__(message)


def markdown_entry(package, block_index=None):
    """Extract the Markdown Python entry.

    Without ``block_index`` the conservative rule applies: exactly one complete,
    unindented ``python`` fence may exist. With an explicit index - supplied by the
    author's declaration - that specific complete block is selected, so ordinary
    documentation examples no longer make the delivery look ambiguous.
    """
    path = safe_relative(Path(package), 'SKILL.md')
    if not path.is_file():
        raise EntryError('entry_missing', 'Missing delivered SKILL.md', 'content', 'content_defect')
    raw = path.read_bytes()
    # Deliberately narrow: no nested/list-indented fences, concatenation or REPL.
    blocks = list(re.finditer(rb'^```(?:python|py)[ \t]*\r?\n(.*?)^```[ \t]*(?:\r?\n|$)', raw, re.M | re.S))
    openings = re.findall(rb'^[ \t]*[`~]{3,}(?:python|py)\b[^\r\n]*', raw, re.M)
    if block_index is None:
        if len(blocks) != 1 or len(openings) != 1:
            raise EntryError('entry_unsupported', 'Require exactly one complete, unindented ```python block in SKILL.md; multiple/interactive/ambiguous blocks are unsupported')
        index = 0
        declared_one_based = None
    else:
        if type(block_index) is not int or block_index < 0:
            raise EntryError('entry_declaration_invalid', 'A declared Markdown block index must be a nonnegative integer')
        if not blocks:
            raise EntryError('entry_unsupported', 'SKILL.md contains no complete, unindented ```python block')
        if block_index >= len(blocks) and len(blocks) == 1 and block_index == 1:
            # A one-based index over a single block is unambiguous: there is exactly
            # one candidate, so no interpretation is being guessed. Record the
            # normalisation instead of refusing a correct delivery on a convention.
            declared_one_based = block_index
            block_index = 0
        else:
            declared_one_based = None
        if block_index >= len(blocks):
            raise EntryError('entry_declaration_missing', 'Declared Markdown block %d does not exist; SKILL.md has %d complete block(s); block_index is 0-based'
                             % (block_index, len(blocks)))
        index = block_index
    # A Python-looking fence inside a larger literal fence is documentation,
    # not an executable block. Track outer backtick/tilde fences before binding.
    active = None
    top_level = []
    offset = 0
    for line in raw.splitlines(keepends=True):
        fence = re.match(rb'^ {0,3}(`{3,}|~{3,})([^\r\n]*)', line)
        if fence:
            marker, tail = fence.groups()
            if active is None:
                active = marker
                top_level.append(offset)
            elif marker[:1] == active[:1] and len(marker) >= len(active) and not tail.strip():
                active = None
        offset += len(line)
    if blocks[index].start() not in top_level:
        raise EntryError('entry_unsupported', 'Python fence is inside a literal Markdown code block')
    block = blocks[index]; code = block.group(1)
    try:
        text = code.decode('utf-8')
        tree = ast.parse(text)
        if not tree.body:
            raise SyntaxError('empty Python block')
    except (UnicodeError, SyntaxError) as exc:
        raise EntryError('entry_invalid', 'Delivered Python block is incomplete: ' + str(exc), 'content', 'content_defect') from exc
    if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {'input', 'breakpoint', 'exec', 'eval'} for n in ast.walk(tree)):
        raise EntryError('entry_unsupported', 'Interactive/dynamically constructed Python entry is unsupported')
    table = symtable.symtable(text, str(path), 'exec')
    defined = {s.get_name() for s in table.get_symbols() if s.is_assigned() or s.is_imported() or s.is_namespace()}
    allowed = defined | set(dir(builtins)) | {'__name__', '__file__', '__package__', '__doc__'}
    def unresolved(scope):
        names = {s.get_name() for s in scope.get_symbols() if s.is_referenced() and s.is_global() and s.get_name() not in allowed}
        for child in scope.get_children():
            names |= unresolved(child)
        return names
    missing = unresolved(table)
    if missing:
        raise EntryError('entry_context_missing', 'Python entry needs undeclared context: ' + ', '.join(sorted(missing)), 'content', 'content_defect')
    extraction = {'rule': 'single-unindented-python-fence-v1', 'block_index': index,
                  'start_byte': block.start(1), 'end_byte': block.end(1),
                  'start_line': raw[:block.start(1)].count(b'\n') + 1,
                  'markdown_sha256': hashlib.sha256(raw).hexdigest(),
                  'code_sha256': hashlib.sha256(code).hexdigest()}
    if declared_one_based is not None:
        # Visible normalisation: the delivery had one block and the declaration was
        # one-based. The resolved index is what later stages verify.
        extraction.update(declared_block_index=declared_one_based,
                          block_index_basis='one-based normalized over a single block')
    return {'kind': 'markdown_python', 'entry': 'SKILL.md', 'runtime_entry': 'entry/skill.py',
            'extraction': extraction}, code


DECLARATION_FIELDS = frozenset({'kind', 'path', 'block_index', 'code_sha256'})
DECLARATION_KINDS = frozenset({'script', 'markdown_python'})


def declared_entry(package, declared):
    """Resolve an author's structured entry declaration against the actual package.

    The declaration only selects; it earns no trust by existing. The path must be a
    safe relative path of a delivered file, a script entry must be a nonempty
    delivered ``.py``/``.sh``, and a Markdown entry must extract uniquely and
    completely (with the declared code identifier, when one is given, matching the
    exact extracted bytes). Source association and independent review still run
    afterwards and are never replaced by the declaration.
    """
    package = Path(package)
    if not isinstance(declared, dict):
        raise EntryError('entry_declaration_invalid', 'The delivered entry declaration must be an object')
    unknown = set(declared) - DECLARATION_FIELDS
    if unknown:
        raise EntryError('entry_declaration_invalid',
                         'Unsupported entry declaration fields: ' + ', '.join(sorted(unknown)))
    kind, path = declared.get('kind'), declared.get('path')
    if kind not in DECLARATION_KINDS:
        raise EntryError('entry_declaration_invalid', 'entry.kind must be script or markdown_python')
    if not isinstance(path, str) or not path.strip():
        raise EntryError('entry_declaration_invalid', 'entry.path must be nonempty text')
    try:
        safe_relative(package, path)
    except ValueError as exc:
        raise EntryError('entry_declaration_invalid', 'Unsafe entry path: ' + str(exc)) from exc
    files = {f['path']: f for f in manifest(package)}
    if path not in files:
        raise EntryError('entry_declaration_missing',
                         'Declared entry is not part of the delivered package: ' + path)
    if kind == 'script':
        if declared.get('block_index') is not None or declared.get('code_sha256') is not None:
            raise EntryError('entry_declaration_invalid',
                             'block_index and code_sha256 apply to markdown_python entries only')
        if not path.endswith(('.py', '.sh')):
            raise EntryError('entry_declaration_invalid',
                             'A script entry must be a delivered .py or .sh file: ' + path)
        if not files[path]['bytes']:
            raise EntryError('entry_declaration_invalid', 'Declared script entry is empty: ' + path)
        return {'kind': 'script', 'entry': path, 'runtime_entry': 'package/' + path,
                'declaration': copy.deepcopy(declared)}
    if path != 'SKILL.md':
        raise EntryError('entry_unsupported',
                         'A markdown_python entry is extracted from SKILL.md, not ' + path)
    binding, code = markdown_entry(package, declared.get('block_index'))
    expected = declared.get('code_sha256')
    if expected is not None:
        if not isinstance(expected, str) or expected != binding['extraction']['code_sha256']:
            raise EntryError('entry_declaration_mismatch',
                             'Declared code identifier does not match the extracted Markdown block')
    binding['declaration'] = copy.deepcopy(declared)
    return binding


def preflight(package, declared=None):
    """Resolve the delivered entry.

    Ordering is deliberate. A validated author declaration wins over automatic
    recognition, so a delivery may ship documentation examples plus scripts without
    being called ambiguous. Without a declaration the conservative rule stands:
    exactly one conforming candidate may be adopted, and two candidates remain
    ambiguity rather than a preference.
    """
    if declared is not None:
        return declared_entry(package, declared)
    scripts = [f['path'] for f in manifest(package) if f['path'].endswith(('.py', '.sh'))]
    markdown, markdown_error = None, None
    try:
        markdown = markdown_entry(package)[0]
    except EntryError as exc:
        markdown_error = exc
    if scripts:
        if len(scripts) > 1:
            raise EntryError('entry_ambiguous',
                             'Multiple delivered scripts need an explicit entry selection; got ' + ', '.join(sorted(scripts)),
                             kind='unresolved_input')
        if markdown is not None:
            raise EntryError('entry_ambiguous',
                             'Both a markdown python block and a delivered script could be the entry (' +
                             ', '.join(sorted(scripts)) + '); select one explicitly', kind='unresolved_input')
        binding = {'kind': 'script', 'entry': scripts[0], 'runtime_entry': 'package/' + scripts[0]}
        if markdown_error is not None:
            binding['markdown_candidate_rejected'] = {'code': markdown_error.code,
                                                      'detail': str(markdown_error)[:300]}
        return binding
    if markdown is not None:
        return markdown
    if markdown_error is not None:
        # Preserve the original lane/kind: a missing or unsupported markdown
        # entry is a delivery-contract problem, not an unresolved input choice.
        raise markdown_error
    raise EntryError('entry_missing', 'No delivered script and no markdown python block to bind',
                     'content', 'content_defect')


def runtime_path(binding):
    return binding.get('runtime_entry', 'package/' + binding['entry'])


def source_view(sources):
    """Presentation-only provenance, including honest handling of legacy records."""
    return [{'id': s['id'], 'inventory': s['inventory'], 'snapshot_fingerprint': fingerprint(s['inventory']),
             'upstream': s.get('upstream'), 'carrier_repository': s.get('carrier_repository'),
             'legacy_reference': {'value': s.get('resolved_ref'), 'meaning': 'Not verified as an upstream version unless accompanied by upstream/repo provenance'},
             'repo': s.get('repo'), 'url': s.get('url')} for s in sources]


def materialize(package, binding, target):
    if binding.get('kind') != 'markdown_python':
        return
    actual, code = markdown_entry(package, _bound_block(binding))
    if any(binding.get(k) != actual[k] for k in ('entry', 'runtime_entry', 'extraction')):
        raise ValueError('Markdown entry locator or bytes differ from bound delivery')
    output = safe_relative(Path(target), runtime_path(binding))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(code)


def _bound_block(binding):
    """Reuse the bound block index so extraction is repeated, not re-selected."""
    extraction = binding.get('extraction') or {}
    index = extraction.get('block_index')
    return index if type(index) is int and index >= 0 else None


def verify_material(package, binding, material):
    if binding.get('kind') != 'markdown_python':
        return
    actual, code = markdown_entry(package, _bound_block(binding))
    if any(binding.get(k) != actual[k] for k in ('entry', 'runtime_entry', 'extraction')):
        raise ValueError('Markdown entry changed after binding')
    if safe_relative(Path(material), runtime_path(binding)).read_bytes() != code:
        raise ValueError('Extracted entry differs from exact delivered code bytes')


def _upstream_path(view, source):
    """The upstream file path a single-file snapshot came from, if recorded."""
    entry = next((item for item in view if item['id'] == source['source_id']), None)
    if entry is None:
        return None
    inventory = entry.get('inventory') or []
    if len(inventory) != 1 or inventory[0].get('path') != source['path']:
        return None
    upstream = entry.get('upstream')
    return upstream.get('path') if isinstance(upstream, dict) else None


def _candidate_source(source_text, view, proposal):
    """The supplied snapshot the citation names, or None when it is not unique.

    A model may name the logical upstream path instead of the snapshot path it was
    given. That alias is accepted only when exactly one supplied file maps to it, and
    the quote is still verified against that file's bytes.
    """
    exact = [s for s in source_text
             if s['source_id'] == proposal['source_id'] and s['path'] == proposal['source_path']]
    if exact:
        return exact, None
    aliases = [s for s in source_text
               if s['source_id'] == proposal['source_id']
               and _upstream_path(view, s) == proposal['source_path']]
    if len(aliases) == 1:
        return aliases, proposal['source_path']
    return [], None


def associate(record, package, sources, audit, opts, guard=None, deadline=None, entry=None):
    """One bounded proposal and independent semantic review, never self-approval.

    ``entry`` is a resolved binding (from a validated author declaration) or None
    for conservative recognition. A declaration never waives the association
    proposal, the exact-quotation check or the independent review.
    """
    from . import model_call
    from .planner import api_options as planner_options, backend_model
    from .review import review_snapshot
    def limits():
        if deadline is None or not math.isfinite(deadline):
            return opts['model_timeout'], opts['total_seconds']
        remaining = deadline - time.monotonic()
        if remaining < 1:
            raise EntryError('explicit_budget', 'Explicit runtime time limit reached before association/review', 'environment', 'caller_limit')
        return min(opts['model_timeout'], int(remaining)), int(remaining)
    entry = entry if entry is not None else preflight(package)  # deterministic failures never call a model
    audit = Path(audit); audit.mkdir(parents=True, exist_ok=True)
    source_text = []
    for s in sources:
        for f in s['inventory']:
            p = Path(s['path']) if Path(s['path']).is_file() else safe_relative(Path(s['path']), f['path'])
            if file_digest(p) != f['sha256']:
                raise ValueError('Binding source changed')
            try:
                text = p.read_text(encoding='utf-8')
            except UnicodeError:
                continue
            source_text.append({'source_id': s['id'], 'path': f['path'], 'sha256': f['sha256'], 'text': text})
    fields = {'source_id': {'type': 'string'}, 'source_path': {'type': 'string'},
              'quote': {'type': 'string'}, 'reason': {'type': 'string'},
              'invocation': {'type': 'string'}, 'supported': {'type': 'boolean'}}
    schema = {'type': 'object', 'properties': fields, 'required': list(fields), 'additionalProperties': False}
    view = source_view(sources)
    citation_paths = [{'source_id': s['source_id'], 'path': s['path'],
                       'upstream_path': _upstream_path(view, s)} for s in source_text]
    prompt = ('Associate the actual delivered entry with an inspected upstream API/tool. Return supported=false if uncertain. '
              'Supply one contiguous verbatim substring from the chosen source file as quote proving the API relationship. '
              'Never concatenate separate excerpts, insert ellipses, or change whitespace in quote; put additional API explanations in reason. '
              'source_path must be the snapshot path of the supplied file exactly as listed in citation_paths '
              '(for example document.py); an upstream repository path such as rdkit/Chem/Recap.py belongs in reason, '
              'not in source_path. '
              'Explain both source and delivery scope, '
              'and describe interpreter, arguments/function inputs, working directory, outputs and necessary supports. '
              'Do not edit code or propose tests/expected outputs. A local carrier commit is NOT an upstream version.\n' +
              json.dumps({'entry': entry, 'citation_paths': citation_paths,
                          'delivery': [{'path': f['path'], 'text': safe_relative(Path(package), f['path']).read_text(encoding='utf-8', errors='replace')} for f in manifest(package)],
                          'source_identities': view, 'sources': source_text}, ensure_ascii=False))
    if redact(prompt) != prompt:
        raise EntryError('unsafe_binding_source', 'Credential-like source material cannot enter association prompts', kind='unresolved_input')
    (audit / 'proposal-prompt.txt').write_text(prompt, encoding='utf-8')
    timeout, _ = limits()
    if guard:
        guard()
    proposal, receipt = model_call.call(prompt, schema, backend_model(opts), timeout=timeout, audit_dir=audit / 'model',
                                        transport=opts.get('transport', 'default'),
                                        progress_watch=opts.get('progress_watch', 'terminate'),
                                        reasoning=opts.get('reasoning_effort'),
                                        tier=opts.get('service_tier'),
                                        backend=opts.get('backend', 'codex_cli'),
                                        api_options=planner_options(opts))
    import jsonschema
    try:
        jsonschema.validate(proposal, schema)
    except jsonschema.ValidationError as exc:
        raise EntryError('binding_proposal_invalid', 'Association proposal schema: ' + exc.message, kind='unresolved_input') from exc
    if redact(json.dumps(proposal)) != json.dumps(proposal):
        raise EntryError('binding_proposal_invalid', 'Association proposal contains credential-like values', kind='unresolved_input')
    write_json(audit / 'proposal.json', proposal); write_json(audit / 'receipt.json', receipt)
    if not proposal['supported']:
        raise EntryError('binding_unresolved', proposal['reason'], kind='unresolved_input')
    candidates, source_path_alias = _candidate_source(source_text, view, proposal)
    if len(candidates) != 1 or not proposal['quote'].strip() or proposal['quote'] not in candidates[0]['text'] or not proposal['reason'] or not proposal['invocation']:
        raise EntryError('binding_unresolved', 'Association lacks a verified exact source citation and invocation', kind='unresolved_input')
    binding = dict(entry, association='reviewed', source_id=proposal['source_id'], source_path=candidates[0]['path'],
                   source_sha256=candidates[0]['sha256'], quote=proposal['quote'], reason=proposal['reason'], invocation=proposal['invocation'],
                   entry_sha256=file_digest(safe_relative(Path(package), entry['entry'])), files=manifest(package))
    if source_path_alias:
        # Record that the proposal named the logical upstream path; the binding still
        # points at the supplied snapshot whose bytes were checked.
        binding['source_path_alias'] = source_path_alias
    timeout, remaining = limits()
    native = opts.get('native_model') or {}
    reviewed = review_snapshot(record, package, sources, audit / 'review', proposed_binding=binding,
        model=native.get('name') or opts['model'], timeout=timeout, total_seconds=remaining, call_guard=guard,
        transport=opts.get('transport', 'default'), reasoning_effort=opts.get('reasoning_effort'),
        service_tier=opts.get('service_tier'),
        backend=native.get('backend', 'codex_cli'), api_model=native.get('api_model'))
    write_json(audit / 'independent-review.json', reviewed)
    result = reviewed['review']
    if result['status'] != 'pass' or result.get('binding_verified') is not True or result.get('requirement_assessment') != 'confirmed':
        if result.get('resolution') == 'revise_files' and any(
                isinstance(f, dict) and f.get('blocking') and f.get('category') == 'file' for f in result.get('findings', [])):
            raise EntryError('entry_content_review_failed', json.dumps(result['findings'], ensure_ascii=False), 'content', 'content_defect')
        raise EntryError('binding_review_required', 'Independent review did not approve the source association and actual invocation', kind='unresolved_input')
    binding['review_sha256'] = fingerprint(reviewed)
    return binding
