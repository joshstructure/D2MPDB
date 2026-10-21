"""Deterministic source-change gate and verified publication handoff.

No AI calls, native calculations, network access or source edits. Hosting is
performed separately with authenticated Sites tools; a build is not a publish.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys

from design_atlas import build

ASSETS = ('index.html', 'atlas.css', 'atlas.js', 'layouts.js', 'downloads.js', 'dataset.js', 'atlas-data.json')
FIXED_INPUTS = (build.REGISTRY, build.TRACKER, build.SHEET, build.MAPPING, build.RECEIPT, build.ASSUMPTIONS,
                'design_atlas/manual_links.json', 'design_atlas/site.json', 'tools/project_coherence.py')


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def local(root, relative):
    if Path(relative).is_absolute() or PureWindowsPath(relative).is_absolute():
        raise ValueError('Atlas inputs must be repository-relative: ' + relative)
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Atlas input leaves repository: ' + relative)
    return path


def inventory(root):
    """Hash selected files, including absent optional files, and parser/UI code.

    Never choose sources by their dates or filenames. Changing the register
    changes this inventory. Generated output, receipts and Git HEAD are excluded
    so publication and unrelated commits cannot trigger a rebuild loop.
    """
    paths = set(FIXED_INPUTS)
    with (root / build.REGISTRY).open(encoding='utf-8-sig', newline='') as handle:
        paths.update(row['path'].replace('\\', '/') for row in csv.DictReader(handle) if row['path'])
    for pattern in ('*.py', 'web/*'):
        paths.update(p.relative_to(root).as_posix() for p in (root / 'design_atlas').glob(pattern) if p.is_file())
    files = {}
    for relative in sorted(paths):
        path = local(root, relative)
        files[relative] = build.sha(path) if path.is_file() else None
    return {'digest': digest(files), 'files': files}


def changed_paths(previous, current):
    before, after = previous.get('files', {}), current['files']
    return sorted(p for p in set(before) | set(after) if p not in before or p not in after or before[p] != after[p])


@contextmanager
def lock(root):
    """OS lock is released even after a process crash; no stale lock deletion."""
    folder = root / 'design_atlas/.refresh'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'lock').open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def pending_path(root):
    return root / 'design_atlas/.refresh/pending.json'


def status(root):
    current = inventory(root)
    published = read_json(root / 'design_atlas/publication.json', {})
    pending = read_json(pending_path(root), {})
    deployment = pending.get('deployment')
    state = 'current' if published.get('inputs', {}).get('digest') == current['digest'] else 'refresh_required'
    if deployment and deployment['status'] not in ('failed', 'succeeded'):
        state = 'deployment_pending'
    elif pending.get('staged_at') and not deployment:
        state = 'publication_in_progress'
    return {'status': state, 'input_digest': current['digest'],
            'changed_paths': changed_paths(published.get('inputs', {}), current),
            'deployment': deployment, 'staged_at': pending.get('staged_at'), 'published_at': published.get('published_at'),
            'workflow': 'design_atlas/UPDATE_WORKFLOW.md'}


def artifact_hashes(folder):
    names = set(ASSETS)
    names.update(p.relative_to(folder).as_posix() for p in (folder / 'downloads').rglob('*') if p.is_file())
    return {name: build.sha(folder / name) for name in sorted(names)}


def verify_artifact(root, pending, require_current=True):
    folder = local(root, pending['output'])
    if artifact_hashes(folder) != pending['artifacts']:
        raise RuntimeError('Prepared atlas was modified; prepare again before publishing.')
    if require_current and inventory(root) != pending['inputs']:
        raise RuntimeError('Sources changed after preparation; prepare again before publishing.')
    return folder


def check_browser_code(root, folder):
    for asset in ('atlas.js', 'layouts.js', 'downloads.js', 'dataset.js'):
        subprocess.run(['node', '--check', str(folder / asset)], check=True, capture_output=True, text=True)
    subprocess.run(['node', str(root / 'tests/test_atlas_layouts.js'), str(folder / 'atlas-data.json')],
                   cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(['node', str(root / 'tests/test_atlas_downloads.js')],
                   cwd=root, check=True, capture_output=True, text=True)


def prepare(root):
    with lock(root):
        state = status(root)
        if state['status'] in ('current', 'deployment_pending', 'publication_in_progress'):
            return state
        before = inventory(root)
        pending = read_json(pending_path(root), {})
        if pending.get('inputs') == before:
            try:
                verify_artifact(root, pending)
                return {'status': 'ready_to_publish', **pending}
            except (OSError, RuntimeError):
                pass
        data = build.build_data(root)
        for path, doc in data['documents'].items():
            if path not in before['files'] or before['files'][path] != doc['sha256']:
                raise RuntimeError('Unwatched or changed evidence: ' + path)
        data['refresh'] = {'input_digest': before['digest'], 'method': 'Deterministic registered-source extraction'}
        build.validate(data)
        output = root / 'design_atlas/.refresh' / before['digest']
        # An interrupted build is never the pending publication. Reuse complete
        # byte-identical candidates only through their verified pending receipt.
        output.mkdir(parents=True, exist_ok=True)
        build.write_atlas(data, output, root)
        check_browser_code(root, output)
        if inventory(root) != before:
            raise RuntimeError('Sources changed during preparation; last publication is unchanged. Retry after saves finish.')
        pending = {'inputs': before, 'output': output.relative_to(root).as_posix(),
                   'artifacts': artifact_hashes(output), 'prepared_at': data['generated_at'],
                   'counts': {key: len(data[key]) for key in ('nodes', 'edges', 'values')},
                   'checks': data['checks']}
        write_json(pending_path(root), pending)
        return {'status': 'ready_to_publish', **pending}


def stage(root, checkout):
    """Copy the verified app and exact source downloads to the opened Site."""
    with lock(root):
        pending = read_json(pending_path(root))
        if not pending:
            raise RuntimeError('No prepared atlas. Run prepare first.')
        if pending.get('deployment', {}).get('status') in ('pending', 'building', 'publishing'):
            raise RuntimeError('Reconcile the existing deployment first.')
        if pending.get('staged_at') and not pending.get('deployment'):
            raise RuntimeError('Publication already in progress. Reconcile the staged Site revision first.')
        source = verify_artifact(root, pending)
        from design_atlas.downloads import verify_remote_downloads
        verify_remote_downloads(read_json(source / 'atlas-data.json'), root)
        site = read_json(root / 'design_atlas/site.json')
        manifest = read_json(checkout / '.openai/hosting.json', {})
        if manifest.get('project_id') != site['project_id'] or manifest.get('static', {}).get('directory') != 'dist':
            raise ValueError('Checkout is not the configured atlas Site with static directory dist.')
        # Preserve exact artifact bytes in the hosting commit on Windows too.
        # Append our narrow rule after existing attributes; retain other rules.
        attributes = checkout / '.gitattributes'
        existing = attributes.read_text(encoding='utf-8') if attributes.is_file() else ''
        if not existing.rstrip().endswith('dist/** -text'):
            attributes.write_text(existing.rstrip() + '\ndist/** -text\n', encoding='utf-8')
        target = checkout / 'dist'
        target.mkdir(parents=True, exist_ok=True)
        from design_atlas.downloads import clean_downloads
        clean_downloads(target, set(pending['artifacts']))
        for name in pending['artifacts']:
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target / name)
        if artifact_hashes(target) != pending['artifacts']:
            raise RuntimeError('Staged assets differ from the prepared atlas.')
        # Also leave the familiar local viewer updated only after validation.
        local_dist = root / 'design_atlas/dist'
        local_dist.mkdir(parents=True, exist_ok=True)
        clean_downloads(local_dist, set(pending['artifacts']))
        for name in pending['artifacts']:
            (local_dist / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, local_dist / name)
        pending['staged_at'] = datetime.now(timezone.utc).isoformat()
        pending['staged_checkout'] = str(checkout)
        write_json(pending_path(root), pending)
        return {'status': 'staged', 'input_digest': pending['inputs']['digest'], 'project_id': site['project_id']}


def record_deployment(root, checkout, commit, result):
    with lock(root):
        pending = read_json(pending_path(root))
        if not pending:
            raise RuntimeError('No prepared atlas.')
        verify_artifact(root, pending, require_current=False)
        site = read_json(root / 'design_atlas/site.json')
        if result.get('project_id') != site['project_id'] or not result.get('id') or not result.get('version_id'):
            raise ValueError('Deployment response does not identify this Site.')
        if result.get('status') not in ('pending', 'building', 'publishing', 'succeeded', 'failed'):
            raise ValueError('Unknown deployment status.')
        actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip()
        if actual != commit or artifact_hashes(checkout / 'dist') != pending['artifacts']:
            raise RuntimeError('Pushed source does not match the prepared atlas.')
        for name, expected in pending['artifacts'].items():
            blob = subprocess.check_output(['git', 'show', commit + ':dist/' + name], cwd=checkout)
            if hashlib.sha256(blob).hexdigest() != expected:
                raise RuntimeError('Committed asset differs from prepared atlas: ' + name)
        existing = pending.get('deployment', {})
        if existing and existing['status'] != 'failed' and existing['id'] != result['id']:
            raise RuntimeError('Reconcile existing deployment before starting another.')
        pending['deployment'] = {k: result.get(k) for k in ('project_id', 'id', 'version_id', 'status', 'url')}
        pending['commit_sha'] = commit
        write_json(pending_path(root), pending)
        return {'status': 'deployment_recorded', 'deployment': pending['deployment']}


def finish(root, result):
    """Accept only the saved deployment's terminal result; never assume success."""
    with lock(root):
        pending = read_json(pending_path(root), {})
        expected = pending.get('deployment', {})
        if not expected or any(result.get(k) != expected.get(k) for k in ('project_id', 'id', 'version_id')):
            raise ValueError('Response does not match the recorded deployment.')
        if result.get('status') == 'failed':
            pending['deployment']['status'] = 'failed'
            write_json(pending_path(root), pending)
            return {'status': 'publish_failed', 'detail': result.get('failure_message')}
        if result.get('status') != 'succeeded':
            raise ValueError('Publication is not confirmed successful.')
        verify_artifact(root, pending, require_current=False)
        receipt = {key: pending[key] for key in ('inputs', 'artifacts', 'counts', 'checks', 'commit_sha')}
        receipt.update(project_id=expected['project_id'], deployment_id=expected['id'], version_id=expected['version_id'],
                       published_at=datetime.now(timezone.utc).isoformat(), url=result.get('url'))
        write_json(root / 'design_atlas/publication.json', receipt)
        pending_path(root).unlink()
        return status(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('status', 'prepare', 'stage', 'record-deployment', 'finish'))
    parser.add_argument('--root', type=Path, default=build.ROOT)
    parser.add_argument('--checkout', type=Path)
    parser.add_argument('--commit')
    parser.add_argument('--result', type=Path, help='Saved structured Sites response; never credentials')
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.action == 'status': result = status(root)
        elif args.action == 'prepare': result = prepare(root)
        elif args.action == 'stage':
            if not args.checkout: parser.error('--checkout is required')
            result = stage(root, args.checkout.resolve())
        else:
            if not args.result: parser.error('--result is required')
            response = read_json(args.result)
            if args.action == 'finish': result = finish(root, response)
            else:
                if not args.checkout or not args.commit: parser.error('--checkout and --commit are required')
                result = record_deployment(root, args.checkout.resolve(), args.commit, response)
        # Full manifests are persisted on disk; stdout is a small agent-facing decision.
        print(json.dumps({k: v for k, v in result.items() if k not in ('inputs', 'artifacts')}, indent=2))
        return 1 if result['status'] == 'publish_failed' else 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'error', 'detail': str(exc)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
