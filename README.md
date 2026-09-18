# OmniUse 🤖

**An AI agent that can actually *use* things** — your browser, your Android phone, and your computer.

> Hinglish mein: *Ek AI agent jo aapke browser, phone aur computer ko khud use kar sakta hai.*
> Task bolo — "phone ki notifications padho", "YouTube pe search karke top videos batao" — agent khud click karega, type karega, screenshot dekhega, aur kaam karke jawab dega.

```
                 ┌─────────────────────────────────────────────┐
                 │                  OmniUse                     │
                 │                                             │
   task ──────▶  │   think ──▶ act (tool call) ──▶ observe ──┐  │
                 │      ▲                                  │  │
                 │      └──────────────────────────────────┘  │
                 └───────┬──────────┬──────────┬───────┬──────┘
                         │          │          │       │
                    🌐 Browser   📱 Mobile   💻 System  👁 Vision
                     Playwright    ADB         shell     screenshots
                     Chromium     Android     files     → back to the LLM
```

## What it gives your AI

| Toolset | What the agent can do | Requires |
|---|---|---|
| **browser** | Open pages, click, type, scroll, read text & links, take screenshots | `playwright` |
| **mobile** | Tap, swipe, type, press keys, screenshots, `adb shell` on an Android phone | `adb` + USB debugging |
| **system** | Run shell commands, read/write/list files on the computer | nothing extra |
| **vision** | *Look at* any screenshot it takes and reason about what it sees | a vision-capable model |

The agent works with **any OpenAI-compatible LLM** — OpenAI, Groq, OpenRouter, Together, or a local Ollama/vLLM server. Just point `OPENAI_BASE_URL` at it.

## Quickstart

```bash
git clone https://github.com/ca4219248-blip/omni-use.git
cd omni-use
pip install -r requirements.txt
playwright install chromium
cp .env.example .env        # then edit .env and add your API key
```

Run a task:

```bash
python cli.py "Open news.ycombinator.com and give me the top 3 story titles"

python cli.py "Search for 'best budget phones 2026' and compare the top 3 results"

python cli.py --tools mobile,vision "Screenshot my phone and tell me my battery % and notifications"

python cli.py --tools system "Check disk space and delete nothing, just report"
```

Use it as a library:

```python
from omniuse import Agent

agent = Agent(toolsets=["browser", "vision"], max_steps=15)
answer = agent.run("Find today's top story on Hacker News and summarise it.")
print(answer)
```

## Phone setup (mobile toolset)

1. Install [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) (gives you `adb`).
2. On the phone: **Settings → About phone → tap "Build number" 7 times**, then **Settings → Developer options → enable USB debugging**.
3. Plug in via USB, run `adb devices`, and accept the prompt on the phone.
4. That's it — `mobile_tap`, `mobile_swipe`, `mobile_screenshot` etc. now work.

## Configuration

All config is plain environment variables (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | — | Your LLM key (required) |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint |
| `OMNIUSE_MODEL` | `gpt-4o-mini` | Model name (needs vision for the vision toolset) |
| `OMNIUSE_MAX_STEPS` | `30` | Safety cap on agent steps per task |
| `OMNIUSE_HEADLESS` | `1` | `0` = watch the browser work live |
| `OMNIUSE_SCREENSHOTS_DIR` | `screenshots` | Where screenshots are saved |
| `OMNIUSE_WORKDIR` | `.` | Working directory for shell commands |

## How it works (100 lines worth of idea)

1. The task + a system prompt go to the LLM **with a menu of tools**.
2. The LLM replies with a tool call, e.g. `browser_open("example.com")`.
3. OmniUse executes it and feeds the result back.
4. Loop — with `look_at_image` available so the agent can *see* screenshots it takes.
5. When the LLM stops calling tools, its final message is the answer.

Everything is plain Python with no magic — `omniuse/agent.py` is the loop, `omniuse/tools/` holds the toolsets, and each toolset is just a dict of `(function, schema)` pairs. **Add your own toolset in ~10 lines.**

## Extending

```python
# my_tools.py — drop-in toolset
from omniuse.tools import TOOLSETS

def weather(city: str) -> str:
    return f"It's 31°C in {city}"

TOOLSETS["weather"] = {
    "weather": (weather, {
        "type": "function",
        "function": {
            "name": "weather",
            "description": "Get the weather for a city.",
            "parameters": {"type": "object",
                          "properties": {"city": {"type": "string"}},
                          "required": ["city"]},
        },
    }),
}
```

## ⚠️ Use responsibly

- The `system` toolset runs **real shell commands** — review tasks before running, and run on a machine/account you're okay with the agent touching.
- The agent has whatever permissions *you* have — it is not sandboxed.
- Use the mobile toolset **only on your own device**.
- Set a sensible `OMNIUSE_MAX_STEPS` — it's your runaway-agent brake.

## Roadmap

- [ ] iOS support (via `libimobiledevice` / Appium)
- [ ] Streaming CLI with live step display
- [ ] Memory across runs
- [ ] Docker sandbox for the `system` toolset

## License

MIT — see [LICENSE](LICENSE).
