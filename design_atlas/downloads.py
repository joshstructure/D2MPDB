"""Package exact current source bytes; never select another document by date."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path, PureWindowsPath
from urllib.parse import quote
from urllib.request import Request, urlopen

PART_BYTES = 8 * 1024 * 1024


def committed_document(root, relative):
    """Use public GitHub only when its committed bytes match the current file."""
    config = root / 'design_atlas/site.json'
    repository = json.loads(config.read_text(encoding='utf-8')).get('document_repository') if config.exists() else None
    if not repository:
        return None
    if not re.fullmatch(r'https://github\.com/[\w.-]+/[\w.-]+', repository):
        raise ValueError('Unsupported document repository')
    commit = subprocess.check_output(['git', 'log', '-1', '--format=%H', '--', relative], cwd=root, text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        return None
    blob = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=root)
    return {'repository': repository, 'commit': commit, 'bytes': len(blob),
            'sha256': hashlib.sha256(blob).hexdigest(),
            'href': 'https://raw.githubusercontent.com/' + repository.removeprefix('https://github.com/') + '/' + commit + '/' + quote(relative, safe='/')}


def source_path(root, relative):
    if Path(relative).is_absolute() or PureWindowsPath(relative).is_absolute():
        raise ValueError('Download source must be repository-relative')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Download source leaves repository')
    return path


def describe(root, relative, expected_hash):
    path = source_path(root, relative)
    committed = committed_document(root, relative)
    if committed and committed['sha256'] == expected_hash:
        return {'filename': path.name, 'bytes': committed['bytes'], 'sha256': expected_hash,
                'repository': committed['repository'], 'commit': committed['commit'],
                'parts': [{key: committed[key] for key in ('href', 'bytes', 'sha256')}]}
    parts, whole = [], hashlib.sha256()
    with path.open('rb') as handle:
        while chunk := handle.read(PART_BYTES):
            whole.update(chunk)
            parts.append({'href': f'downloads/{expected_hash}/{len(parts):04d}.bin',
                          'bytes': len(chunk), 'sha256': hashlib.sha256(chunk).hexdigest()})
    if whole.hexdigest() != expected_hash:
        raise RuntimeError('Download source changed: ' + relative)
    # Empty documents are still real downloadable files.
    if not parts:
        parts = [{'href': f'downloads/{expected_hash}/0000.bin', 'bytes': 0, 'sha256': expected_hash}]
    return {'filename': path.name, 'bytes': sum(p['bytes'] for p in parts),
            'sha256': expected_hash, 'parts': parts}


def attach_downloads(data, root):
    for relative, document in data['documents'].items():
        if document.get('exists'):
            document['download'] = describe(root, relative, document['sha256'])
    for node in data['nodes']:
        relative = node.get('path')
        document = data['documents'].get(relative, {})
        node['download'] = ({'status': 'available', 'path': relative,
                            'scope': 'journal' if node.get('module') else 'document'}
                           if document.get('download') else
                           {'status': 'missing', 'reason': 'The registered file is missing.' if relative
                            else 'No document is linked to this node yet.'})


def write_downloads(data, output, root):
    """Stream source bytes into bounded static assets and verify every part."""
    expected = set()
    for relative, document in data['documents'].items():
        download = document.get('download')
        if not download:
            continue
        if download.get('repository'):
            if hashlib.sha256(source_path(root, relative).read_bytes()).hexdigest() != download['sha256']:
                raise RuntimeError('Download source changed: ' + relative)
            continue
        whole = hashlib.sha256()
        with source_path(root, relative).open('rb') as handle:
            for part in download['parts']:
                chunk = handle.read(part['bytes'])
                whole.update(chunk)
                if hashlib.sha256(chunk).hexdigest() != part['sha256']:
                    raise RuntimeError('Download source changed: ' + relative)
                target = output / part['href']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(chunk)
                expected.add(part['href'])
            if handle.read(1) or whole.hexdigest() != download['sha256']:
                raise RuntimeError('Download source changed: ' + relative)
    # This folder contains generated downloads only. Remove obsolete assets so
    # removed/reselected source documents are no longer served by the site.
    clean_downloads(output, expected)


def verify_remote_downloads(data, root):
    """Publication gate: every external revision must already be on public main."""
    repositories = {}
    for document in data.get('documents', {}).values():
        download = document.get('download', {})
        if download.get('repository'):
            repositories.setdefault(download['repository'], set()).add(download['commit'])
    for repository, commits in repositories.items():
        name = repository.removeprefix('https://github.com/')
        request = Request('https://api.github.com/repos/' + name, headers={'User-Agent': 'D2-Design-Atlas'})
        with urlopen(request, timeout=30) as response:
            public = json.load(response)
        if public.get('private') is not False:
            raise RuntimeError('Document repository is not public: ' + repository)
        ref = 'refs/heads/' + public['default_branch']
        result = subprocess.check_output(['git', 'ls-remote', repository + '.git', ref], cwd=root, text=True).split()
        if len(result) != 2 or not re.fullmatch(r'[0-9a-f]{40}', result[0]):
            raise RuntimeError('Cannot verify published document revision')
        for commit in commits:
            check = subprocess.run(['git', 'merge-base', '--is-ancestor', commit, result[0]], cwd=root, capture_output=True)
            if check.returncode:
                raise RuntimeError('Document revision is not on the public repository: ' + commit)


def clean_downloads(output, expected):
    folder = output / 'downloads'
    if not folder.exists():
        return
    if not folder.resolve().is_relative_to(output.resolve()):
        raise ValueError('Download output leaves atlas directory')
    for path in folder.rglob('*'):
        if path.is_file():
            if not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError('Download artifact leaves download directory')
            if path.relative_to(output).as_posix() not in expected:
                path.unlink()
