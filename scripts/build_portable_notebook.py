"""Refresh the portable notebook's embedded package from this checkout."""
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


def build(repo):
    path = repo / 'Cap_and_Pile_Design.ipynb'
    notebook = json.loads(path.read_text(encoding='utf-8'))
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
    setup['metadata'].update(cellView='form')
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            cell['outputs'] = []
            cell['execution_count'] = None
    notebook['metadata'].pop('widgets', None)
    notebook['metadata'].setdefault('colab', {})['name'] = path.name
    path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False)+'\n', encoding='utf-8')
    print(f'Updated {path.name}: {len(files)} supporting files, package {digest[:12]}')


if __name__ == '__main__':
    build(Path(__file__).resolve().parents[1])
