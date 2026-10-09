"""Refresh the portable notebook's embedded package from this checkout."""
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


def build(repo, *, preserve_outputs=False):
    path = repo / 'Cap_and_Pile_Design.ipynb'
    original_text = path.read_text(encoding='utf-8')
    notebook = json.loads(original_text)
    buffer = io.BytesIO()
    files = sorted([*repo.glob('pier_cap/*.py'), *repo.glob('pier_cap/data/*.json'),
                    repo/'requirements-pier-cap-colab.txt'])
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as package:
        for file in files:
            entry = zipfile.ZipInfo(file.relative_to(repo).as_posix(), date_time=(2026,10,1,0,0,0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(entry, file.read_bytes())
    raw = buffer.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    setup = next(c for c in notebook['cells'] if c.get('id') == 'a1e54f80')
    source, revisions = re.subn(r'^revision = "[a-f0-9]+"$', f'revision = "{digest}"',
                               ''.join(setup['source']), flags=re.M)
    source, packages = re.subn(r'^PACKAGE = "[A-Za-z0-9+/=]+"$',
                              'PACKAGE = "'+base64.b64encode(raw).decode()+'"', source, flags=re.M)
    if revisions != 1 or packages != 1:
        raise ValueError('Expected exactly one package and revision in the portable setup cell.')
    setup['source'] = source.splitlines(keepends=True)
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            metadata = cell.setdefault('metadata', {})
            metadata['cellView'] = 'form'
            metadata.setdefault('jupyter', {})['source_hidden'] = True
    if not preserve_outputs:
        notebook['cells'] = [cell for cell in notebook['cells'] if not cell.get('metadata', {}).get('saved_run_annotation')]
        for cell in notebook['cells']:
            if cell['cell_type'] == 'code':
                cell['outputs'] = []
                cell['execution_count'] = None
        notebook['metadata'].pop('widgets', None)
    notebook['metadata'].setdefault('colab', {})['name'] = path.name
    indent_match = re.search(r'^([ \t]+)"cells":', original_text, flags=re.M)
    indent = len(indent_match.group(1)) if preserve_outputs and indent_match else 1
    path.write_text(json.dumps(notebook, indent=indent, ensure_ascii=False)+'\n', encoding='utf-8')
    print(f'Updated {path.name}: {len(files)} supporting files, package {digest[:12]}')


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preserve-outputs',action='store_true',help='Keep the saved run and widget state; saved output is not a fresh execution of the new package.')
    args=parser.parse_args()
    build(Path(__file__).resolve().parents[1],preserve_outputs=args.preserve_outputs)
