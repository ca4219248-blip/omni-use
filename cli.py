#!/usr/bin/env python3
"""OmniUse command line.

    python cli.py "Search YouTube for lofi beats and give me the top 3 video titles"
    python cli.py --tools browser,vision,screen,universal "Open github.com and tell me today's trending repos"
    python cli.py --mission "Run my project's tests and fix any bugs you find"
"""

import argparse
import sys

from omniuse import __version__, config
from omniuse.agent import Agent


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="omniuse",
        description="OmniUse 2.0 — an AI agent that can use your browser, phone, "
                    "computer and remote machines, under operator supervision.",
    )
    parser.add_argument("task", help="What should the agent do?")
    parser.add_argument(
        "--tools", default="",
        help="Comma-separated toolsets to enable (default: all). Options: "
             "browser, mobile, system, vision, screen, universal, policy, wallet, "
             "escalate, memory, killswitch, remote, + any plugin.",
    )
    parser.add_argument("--steps", type=int, default=None, help="Max agent steps.")
    parser.add_argument("--mission", action="store_true",
                        help="Run as an autonomous mission: iterate, verify, checkpoint, report.")
    parser.add_argument("--iterations", type=int, default=5,
                        help="Max mission iterations (default 5, with --mission).")
    parser.add_argument("--quiet", action="store_true", help="Don't print tool calls.")
    parser.add_argument("--version", action="version", version=f"omniuse {__version__}")
    args = parser.parse_args()

    warning = config.warn_if_unconfigured()
    if warning:
        print(warning, file=sys.stderr)
        return 1

    toolsets = [t for t in args.tools.split(",") if t.strip()] or None

    if args.mission:
        from omniuse.missions import Mission
        mission = Mission(goal=args.task, toolsets=toolsets,
                          max_iterations=args.iterations, verbose=not args.quiet)
        print(mission.run())
        return 0

    agent = Agent(toolsets=toolsets, max_steps=args.steps, verbose=not args.quiet)
    agent.run(args.task)
    return 0


if __name__ == "__main__":
    sys.exit(main())
