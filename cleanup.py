#!/usr/bin/env python3
"""
cleanup.py — Reset the EduSecure Questionnaire Assistant to a clean state.

What gets removed:
  • questionnaire.db        — SQLite database (all users, projects, answers, chunks)
  • uploads/*               — Uploaded questionnaires, reference docs, and exported files
                              (.gitkeep is preserved so the folder stays tracked by git)

What is NOT touched:
  • sample_data/            — Sample reference docs and questionnaire (run create_sample_data.py to regenerate)
  • .env                    — Your API keys and config
  • venv/                   — Python virtual environment

Usage:
  python cleanup.py              # interactive (asks for confirmation)
  python cleanup.py --force      # skip confirmation prompt
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
DB_FILE = ROOT / "questionnaire.db"
UPLOADS_DIR = ROOT / "uploads"

# Patterns to remove from uploads/ (anything except .gitkeep)
UPLOAD_GLOB = "*"
GITKEEP = ".gitkeep"

# ── helpers ────────────────────────────────────────────────────────────────────

def _fmt_size(path: Path) -> str:
    try:
        size = path.stat().st_size
        for unit in ("B", "KB", "MB"):
            if size < 1024:
                return f"{size:.0f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"
    except Exception:
        return "?"


def _list_uploads() -> list[Path]:
    """Return all files in uploads/ except .gitkeep."""
    if not UPLOADS_DIR.exists():
        return []
    return [p for p in UPLOADS_DIR.iterdir() if p.is_file() and p.name != GITKEEP]


def _preview() -> None:
    """Print a summary of what will be deleted."""
    print("\n📋  The following will be removed:\n")

    if DB_FILE.exists():
        print(f"  🗄️   {DB_FILE.relative_to(ROOT)}  ({_fmt_size(DB_FILE)})")
    else:
        print(f"  🗄️   {DB_FILE.relative_to(ROOT)}  (not found — skipping)")

    upload_files = _list_uploads()
    if upload_files:
        print(f"\n  📁  uploads/ ({len(upload_files)} file(s)):")
        for f in sorted(upload_files):
            print(f"        • {f.name}  ({_fmt_size(f)})")
    else:
        print("\n  📁  uploads/  (empty — nothing to remove)")

    print()


def _clean_db() -> None:
    if DB_FILE.exists():
        DB_FILE.unlink()
        print(f"  ✓  Deleted {DB_FILE.relative_to(ROOT)}")
    else:
        print(f"  –  {DB_FILE.relative_to(ROOT)} not found, skipping")


def _clean_uploads() -> None:
    files = _list_uploads()
    if not files:
        print("  –  uploads/ is already empty")
        return
    for f in files:
        f.unlink()
    print(f"  ✓  Removed {len(files)} file(s) from uploads/")
    # Ensure .gitkeep exists so the folder stays in git
    (UPLOADS_DIR / GITKEEP).touch()


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Clean stale data from the questionnaire assistant.")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    print("🧹  EduSecure Questionnaire Assistant — Cleanup")
    print("=" * 50)

    _preview()

    if not args.force:
        try:
            answer = input("❓  Proceed with cleanup? [y/N] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)
        if answer not in ("y", "yes"):
            print("Aborted — nothing was deleted.")
            sys.exit(0)

    print("\n🗑️   Cleaning up...\n")
    _clean_db()
    _clean_uploads()

    print("\n✅  Done! Run the following to start fresh:\n")
    print("    python create_sample_data.py   # regenerate sample questionnaire")
    print("    python -m app.init_db          # recreate the database")
    print("    python run.py                  # start the server\n")


if __name__ == "__main__":
    main()
