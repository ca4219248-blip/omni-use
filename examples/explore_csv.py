#!/usr/bin/env python3
"""Data helper: explore a CSV without opening Excel.

    python examples/explore_csv.py data.csv
"""

import sys

from omniuse.tools import csvdata

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python examples/explore_csv.py <file.csv>")
    path = sys.argv[1]
    print(csvdata.csv_summary(path))
    print()
    print(csvdata.csv_head(path, n=10))
    print()
    print("Tip: ask the agent to csv_filter / csv_select / csv_to_json next,")
    print("     or run: python cli.py --tools csvdata 'summarize this CSV for me'")
