"""Byte-verified, atomic file installation with disk rollback; no FreeCAD GUI."""
from pathlib import Path
import hashlib,os,shutil
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def install(source,destination,backup,expected_old,expected_new,fail_after_replace=False):
    source=Path(source).resolve();destination=Path(destination).resolve();backup=Path(backup).resolve()
    temp=destination.with_name(destination.name+'.design-update-tmp')
    if backup.exists() or temp.exists():raise ValueError('Inspect existing backup/temp before retry')
    if digest(source)!=expected_new or digest(destination)!=expected_old:raise ValueError('Source or target changed')
    backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination,backup)
    if digest(backup)!=expected_old:raise ValueError('Backup verification failed')
    shutil.copy2(source,temp)
    if digest(temp)!=expected_new:raise ValueError('Temporary file verification failed')
    try:
        os.replace(temp,destination)
        if fail_after_replace:raise RuntimeError('Deliberate disk rollback test')
        if digest(destination)!=expected_new:raise ValueError('Installed file verification failed')
        return dict(status='INSTALLED',backup=str(backup),old_sha256=expected_old,new_sha256=expected_new)
    except Exception:
        shutil.copy2(backup,temp);os.replace(temp,destination)
        if digest(destination)!=expected_old:raise RuntimeError('DISK ROLLBACK FAILED')
        if fail_after_replace:return dict(status='TEST_ROLLBACK_VERIFIED',old_sha256=expected_old)
        raise
