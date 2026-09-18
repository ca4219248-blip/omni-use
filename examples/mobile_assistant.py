"""Example: let the agent use your Android phone over ADB."""

from omniuse import config

if config.warn_if_unconfigured():
    raise SystemExit("Set OPENAI_API_KEY first — see .env.example")

from omniuse.agent import Agent  # noqa: E402

agent = Agent(toolsets=["mobile", "vision"], max_steps=15)
answer = agent.run(
    "Take a screenshot of my phone, tell me which app is in the foreground, "
    "then open the notification shade by swiping down and list my notifications."
)
print("\n=== ANSWER ===\n", answer)
