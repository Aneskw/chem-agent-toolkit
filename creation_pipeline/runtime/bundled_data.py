"""Finite, opt-in file-relative JSON reads; not a general __file__ capability."""
import ast
import json
from pathlib import PurePosixPath
import re

from creation_pipeline.records import safe_relative, file_digest, has_link

ABI = 'shared_tool_image_v3'
POLICY = 'closed-python-json-data-v1'


def declaration(value):
    if not isinstance(value, list) or not value:
        raise ValueError('shared_tool.bundled_data: require nonempty explicit module/path/sha256 list')
    pairs = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {'module', 'path', 'sha256'}:
            raise ValueError('shared_tool.bundled_data: expected module, path, sha256')
        for field in ('module', 'path'):
            name = item[field]
            if not isinstance(name, str) or '\\' in name or any(p in {'', '.', '..'} for p in name.split('/')):
                raise ValueError('shared_tool.bundled_data.'+field+': unsafe path '+repr(name))
            safe_relative('/schema-only', name)
        if not item['module'].endswith('.py') or not item['path'].endswith('.json') or 'SKILL.md' in item['path']:
            raise ValueError('shared_tool.bundled_data: require .py module and .json resource')
        if not re.fullmatch('[0-9a-f]{64}', str(item['sha256'])):
            raise ValueError('shared_tool.bundled_data.sha256: expected 64 lowercase hex')
        pair = (item['module'], item['path'])
        if pair in pairs:
            raise ValueError('shared_tool.bundled_data: duplicate resource '+repr(pair))
        pairs.add(pair)


def verify(package, declarations):
    declaration(declarations)
    for item in declarations:
        for name in (item['module'], item['path']):
            path = safe_relative(package, name)
            if has_link(path) or not path.is_file():
                raise ValueError('shared_tool.bundled_data: expected file '+name+'; actual=missing_or_linked')
        resource = safe_relative(package, item['path'])
        actual = file_digest(resource)
        if actual != item['sha256']:
            raise ValueError('shared_tool.bundled_data.'+item['path']+': expected sha256='+item['sha256']+'; actual='+actual)
        try:
            json.loads(resource.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError) as exc:
            raise ValueError('shared_tool.bundled_data.'+item['path']+': expected UTF-8 JSON; actual='+str(exc)) from exc


def reads(tree, module, declarations):
    """Return the only __file__ Name nodes allowed by this profile."""
    allowed = set(); path_nodes = set(); used = set()
    declared = {i['path'] for i in declarations if i['module'] == module}
    path_imports = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                    and n.module == 'pathlib' and n.level == 0
                    and any(a.name == 'Path' and a.asname is None for a in n.names)]
    for node in ast.walk(tree):
        if ((isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name in {'Path','__file__'})
                or (isinstance(node, ast.MatchMapping) and node.rest in {'Path','__file__'})
                or (isinstance(node, ast.Attribute) and (node.attr in {'Path','__file__','modules','__import__'}
                    or (isinstance(node.ctx, (ast.Store,ast.Del)) and node.attr in {'read_text','resolve','parent'})))):
            raise ValueError('shared_tool.bundled_data: indirect path binding unsupported at '+module)
        if ((isinstance(node, ast.Name) and node.id in {'globals','locals','vars','getattr','setattr','delattr','compile'})
                or (isinstance(node, ast.Attribute) and node.attr in {'__dict__','__globals__'})):
            raise ValueError('shared_tool.bundled_data: dynamic path binding unsupported at '+module)
        if ((isinstance(node, ast.Name) and node.id in {'Path','__file__'} and not isinstance(node.ctx, ast.Load))
                or (isinstance(node, ast.arg) and node.arg in {'Path','__file__'})
                or (isinstance(node, (ast.FunctionDef,ast.ClassDef)) and node.name in {'Path','__file__'})):
            raise ValueError('shared_tool.bundled_data: path binding redefined at '+module)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if (alias.asname or alias.name.split('.')[0]) == 'Path' and node not in path_imports:
                    raise ValueError('shared_tool.bundled_data: Path must be unaliased pathlib.Path at '+module)
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != 'read_text':
            continue
        if node.args or len(node.keywords) != 1 or node.keywords[0].arg != 'encoding' or not isinstance(node.keywords[0].value, ast.Constant) or node.keywords[0].value.value != 'utf-8':
            continue
        base = node.func.value; parts = []
        while isinstance(base, ast.BinOp) and isinstance(base.op, ast.Div) and isinstance(base.right, ast.Constant) and isinstance(base.right.value, str):
            parts.insert(0, base.right.value); base = base.left
        if not parts or not path_imports or not isinstance(base, ast.Attribute) or base.attr != 'parent':
            continue
        resolve = base.value
        if not (isinstance(resolve, ast.Call) and not resolve.args and not resolve.keywords
                and isinstance(resolve.func, ast.Attribute) and resolve.func.attr == 'resolve'):
            continue
        call = resolve.func.value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'Path'
                and len(call.args) == 1 and not call.keywords and isinstance(call.args[0], ast.Name) and call.args[0].id == '__file__'):
            continue
        relative = '/'.join(parts)
        if any(p in {'', '.', '..'} for p in relative.split('/')) or '\\' in relative or PurePosixPath(relative).is_absolute():
            raise ValueError('shared_tool.bundled_data: resource escapes module at '+module+': '+relative)
        target = str(PurePosixPath(module).parent / relative)
        if target not in declared:
            raise ValueError('shared_tool.bundled_data: module='+module+'; expected declared path; actual='+target)
        allowed.add(id(call.args[0])); path_nodes.add(id(call.func)); used.add(target)
    if any(isinstance(n,ast.Name) and n.id == 'Path' and id(n) not in path_nodes for n in ast.walk(tree)):
        raise ValueError('shared_tool.bundled_data: Path is limited to declared literal JSON reads at '+module)
    if used != declared:
        raise ValueError('shared_tool.bundled_data: module='+module+'; expected literal reads='+repr(sorted(declared))+'; actual='+repr(sorted(used)))
    return allowed
