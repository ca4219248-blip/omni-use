"""Example: research something with the browser toolset only."""

from omniuse import config

if config.warn_if_unconfigured():
    raise SystemExit("Set OPENAI_API_KEY first — see .env.example")

from omniuse.agent import Agent  # noqa: E402

agent = Agent(toolsets=["browser", "vision"], max_steps=15)
answer = agent.run(
    "Open news.ycombinator.com, find the top 3 stories, "
    "and summarise each in one line (Hinglish is fine)."
)
print("\n=== ANSWER ===\n", answer)
