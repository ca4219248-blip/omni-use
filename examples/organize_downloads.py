#!/usr/bin/env python3
"""Local utilities, no LLM needed: clean the Downloads folder.

    python examples/organize_downloads.py [folder]

Dry run first (reports only), then set ACTUALLY_DO_IT = True.
"""

import sys

from omniuse.tools import files

FOLDER = sys.argv[1] if len(sys.argv) > 1 else "~/Downloads"
ACTUALLY_DO_IT = False

if __name__ == "__main__":
    print(files.files_sizes(FOLDER))
    print()
    print(files.files_duplicates(FOLDER))
    print()
    print(files.files_organize(FOLDER, dry_run=not ACTUALLY_DO_IT))
    if not ACTUALLY_DO_IT:
        print("\n(dry run — set ACTUALLY_DO_IT = True in this file to really move)")
