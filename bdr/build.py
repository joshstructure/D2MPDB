"""Build the Bridge Development Report: gather the record, render, write the manifest."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from bdr import report, sources

VERSION = "bdr 1.0.0"
OUT = sources.PKG / "output"
HTML_NAME = "B4_Bridge_Development_Report.html"
DATA_NAME = "bdr_data.json"
MANIFEST_NAME = "manifest.json"
PDF_NAME = "B4_Bridge_Development_Report.pdf"
EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render() -> tuple[str, dict]:
    bundle = sources.collect()
    html, data = report.render(bundle, VERSION)
    return html, data


def build(out_dir: Path | None = None, pdf: bool = False) -> dict:
    out_dir = Path(out_dir) if out_dir else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    html, data = render()
    html_bytes = html.encode("utf-8")
    data_bytes = (json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    (out_dir / HTML_NAME).write_bytes(html_bytes)
    (out_dir / DATA_NAME).write_bytes(data_bytes)
    manifest = {
        "generator": VERSION,
        "as_of": data["as_of"],
        "sources": sources.source_hashes(),
        "outputs": {HTML_NAME: _sha(html_bytes), DATA_NAME: _sha(data_bytes)},
        "open_items": len(data["open_items"]),
    }
    if pdf:
        manifest["pdf"] = str(print_pdf(out_dir / HTML_NAME, out_dir / PDF_NAME))
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return manifest


def print_pdf(html_path: Path, pdf_path: Path) -> Path:
    """Print the HTML with Microsoft Edge (headless). The PDF carries a creation time, so it is
    not part of the byte-identical outputs of the manifest."""
    edge = next((p for p in EDGE if p.exists()), None)
    if edge is None:
        raise RuntimeError("Microsoft Edge not found; the PDF needs msedge.exe")
    if pdf_path.exists():
        pdf_path.unlink()
    with tempfile.TemporaryDirectory() as profile:
        cmd = [str(edge), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               f"--user-data-dir={profile}", "--no-pdf-header-footer", "--virtual-time-budget=20000",
               f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()]
        subprocess.run(cmd, check=False, timeout=300, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not pdf_path.exists():
        raise RuntimeError("Edge did not write the PDF")
    return pdf_path


def check(out_dir: Path | None = None) -> tuple[bool, list[str]]:
    """Rebuild to a temporary folder and compare with the committed output and manifest."""
    out_dir = Path(out_dir) if out_dir else OUT
    lines, ok = [], True
    manifest = json.loads((out_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    for sid, rec in manifest["sources"].items():
        path = sources.ROOT / rec["path"]
        now = sources.sha256(path) if path.exists() else "missing"
        if now != rec["sha256"]:
            ok = False
            lines.append(f"source {sid} changed ({rec['path']})")
    with tempfile.TemporaryDirectory() as tmp:
        fresh = build(Path(tmp))
        for name, digest in fresh["outputs"].items():
            if manifest["outputs"].get(name) != digest:
                ok = False
                lines.append(f"output {name} differs from the committed build")
            if _sha((out_dir / name).read_bytes()) != manifest["outputs"].get(name):
                ok = False
                lines.append(f"output {name} edited after the build")
    lines.append("current" if ok else "stale: rebuild with .venv\\Scripts\\python.exe scripts\\build_bdr.py")
    return ok, lines
