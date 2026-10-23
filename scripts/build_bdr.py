"""Build the Bridge Development Report (bdr/output/) from the current project record.

    .venv\\Scripts\\python.exe scripts\\build_bdr.py            # HTML, data JSON and manifest
    .venv\\Scripts\\python.exe scripts\\build_bdr.py --pdf      # also print the PDF with Microsoft Edge (headless)
    .venv\\Scripts\\python.exe scripts\\build_bdr.py --check    # rebuild to a temporary folder and compare with the committed output
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bdr import build  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="output folder (default bdr/output)")
    ap.add_argument("--pdf", action="store_true", help="also write the PDF with Microsoft Edge headless printing")
    ap.add_argument("--check", action="store_true", help="rebuild to a temporary folder and compare with the committed output")
    args = ap.parse_args()
    if args.check:
        ok, lines = build.check()
        print("\n".join(lines))
        sys.exit(0 if ok else 1)
    manifest = build.build(Path(args.out) if args.out else None, pdf=args.pdf)
    for name, digest in manifest["outputs"].items():
        print(f"{name}  {digest[:12]}")
    if manifest.get("pdf"):
        print("pdf:", manifest["pdf"])


if __name__ == "__main__":
    main()
