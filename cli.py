#!/usr/bin/env python3
"""OmniUse command line.

    python cli.py "Search YouTube for lofi beats and give me the top 3 video titles"
    python cli.py --tools browser,vision "Open github.com and tell me today's trending repos"
    python cli.py --tools mobile,vision "Screenshot my phone and read my notifications"
"""

import argparse
import sys

from omniuse import __version__, config
from omniuse.agent import Agent


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="omniuse",
        description="OmniUse — an AI agent that can use your browser, phone and computer.",
    )
    parser.add_argument("task", help="What should the agent do?")
    parser.add_argument(
        "--tools", default="browser,vision,system,mobile",
        help="Comma-separated toolsets to enable (default: all four).",
    )
    parser.add_argument("--steps", type=int, default=None, help="Max agent steps.")
    parser.add_argument("--quiet", action="store_true", help="Don't print tool calls.")
    parser.add_argument("--version", action="version", version=f"omniuse {__version__}")
    args = parser.parse_args()

    warning = config.warn_if_unconfigured()
    if warning:
        print(warning, file=sys.stderr)
        return 1

    agent = Agent(
        toolsets=[t for t in args.tools.split(",") if t.strip()],
        max_steps=args.steps,
        verbose=not args.quiet,
    )
    agent.run(args.task)
    return 0


if __name__ == "__main__":
    sys.exit(main())
