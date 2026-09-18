# OmniUse 🤖

**An AI agent that can actually *use* things** — your browser, your Android phone, your computer, remote machines, and (with guardrails) your wallet.

> Hinglish mein: *Ek AI agent jo aapke browser, phone, computer aur remote machines ko khud use kar sakta hai.*
> Task bolo — "phone ki notifications padho", "project ke tests chala ke bugs fix karo" — agent khud plan banayega, click karega, verify karega, aur kaam karke report dega.

```
                 ┌─────────────────────────────────────────────────┐
                 │                    OmniUse 2.0                   │
                 │                                                 │
   task ──────▶  │  think ──▶ act ──▶ [permissions? killswitch?]  │
                 │    ▲                    │                       │
                 │    └──── observe ◀──────┘   (self-correction)    │
                 └──┬─────────┬─────────┬─────────┬─────────┬──────┘
                    │         │         │         │         │
               🌐 Browser  📱 Mobile  💻 System  👁 Vision  🖥 Remote
               🔒 Policy   💰 Wallet  ⚠️ Escalate  🧠 Memory  🛑 Killswitch
               🖱 Universal 📺 Screen  🔌 Plugins  🚀 Missions
```

## What it gives your AI

| Toolset | What the agent can do |
|---|---|
| **browser** | Open pages, click, type, scroll, read text & links, screenshots (Playwright) |
| **mobile** | Tap, swipe, type, press keys, screenshots, `adb shell` on Android |
| **system** | Run shell commands, read/write/list files |
| **vision** | *Look at* any screenshot it takes |
| **screen** | Read a screen as **structured elements** (buttons, inputs, menus) — browser DOM or Android UI tree; `find_element('Start Race')` beats guessing coordinates |
| **universal** | One API for every device: `click('Start Race')`, `type_text(...)`, `scroll`, `open_target(...)`, `drag(...)` — OmniUse decides if that means the browser or the phone |
| **policy** | Check/record each platform's automation stance before acting; carries the non-negotiable rules |
| **wallet** | Read balances; **capped, logged** payments; limit raises need the operator's secret token; never touches private keys |
| **escalate** | Pause + notify the operator (Telegram) whenever something legally needs a human |
| **memory** | Layered persistent memory: append-only event log (every tool call auto-logged) + a fact store (`memory_save`/`memory_get`) so "mera GitHub username yaad rakhna" actually works across runs |
| **killswitch** | One switch, zero activity — checked before **every** tool call |
| **remote** | Run tools on distant machines via **OmniUse Hub** — the AI's remote body |

The agent works with **any OpenAI-compatible LLM** — OpenAI, Groq, OpenRouter, Together, or a local Ollama/vLLM server.

## Quickstart

```bash
git clone https://github.com/ca4219248-blip/omni-use.git
cd omni-use
pip install -r requirements.txt
playwright install chromium
cp .env.example .env        # then edit .env and add your API key
```

```bash
python cli.py "Open news.ycombinator.com and give me the top 3 story titles"

python cli.py --tools browser,screen,universal,vision \
  "Open youtube.com, search for lofi beats, and report the top 3 video titles"

python cli.py --mission "Run this project's tests, fix any bugs you find, and report what you did"
```

```python
from omniuse import Agent, Mission

answer = Agent(toolsets=["browser", "screen", "universal"]).run(
    "Find today's top story on Hacker News and summarise it.")

Mission("Check if the VPS bill is due and pay it if due").run()
```

## 2.0 highlights

### 🖱 Universal computer control
The agent says `click('Start Race')`; OmniUse routes it — Playwright text-locator in the browser, accessibility-tree lookup + tap on Android. `open_target('calculator')` opens a URL in the browser or launches an app on the phone. No coordinates, no device-specific branching in the AI's head.

### 👁 Structured screen understanding
`screen_elements()` returns the screen as a list of interactive elements (with selectors/coordinates); `find_element('Settings')` locates one thing fast. Mobile support uses Android's `uiautomator` dump — the same tree TalkBack sees.

### 🧠 Layered memory
- **Event log** — every tool call auto-logged to `data/memory/log.jsonl`
- **Fact store** — `memory_save("github_username", "david")` survives restarts; the agent is told to check memory *before* asking you again
- **Mission checkpoints** — long tasks save state to `data/missions/`

### 🔄 Self-correction
Failures don't stop the agent — after two failed calls the loop injects an explicit *"stop guessing, observe the screen, rethink, verify"* nudge, and every correction is logged.

### 🛡️ Permission system
Every tool call is checked against `data/permissions.json`:
- **allow** — runs
- **confirm** — interactive y/N prompt; in non-interactive runs the task pauses until you run `python -m omniuse.operator approve <tool>` (or Telegram `/approve`)
- **deny** — never runs

Defaults: payments confirm, destructive shell patterns (rm -rf, mkfs, shutdown…) confirm, mobile shell confirm, remote_run confirm, wallet_raise_limit deny. Edit the JSON anytime — no restart needed.

### 🧰 Plugin SDK
Drop a folder into `plugins/`:

```
plugins/my_tool/
  ├── plugin.json   {"name": "my_tool", "permissions": {"risky_action": "confirm"}}
  └── main.py       TOOLS = {"risky_action": (fn, schema), ...}
```

It's picked up automatically on the next run — see `plugins/hello/` for a working example. Manifest permissions are enforced like built-ins.

### 🌍 Remote body (Hub)
Run on the device you want to control:

```bash
OMNIUSE_HUB_TOKEN=<secret> python -m omniuse.hub --host 0.0.0.0 --port 8787
```

Then from anywhere — another machine, a cloud agent:

```python
remote_status()                                  # is the body alive?
remote_run("browser_open", {"url": "example.com"})
```

Token-authenticated, and the hub enforces the same permission rules as local runs. One AI brain, many bodies.

### 🚀 Autonomous missions
`Mission("goal")` iterates: work → report status as JSON → checkpoint → repeat, until done/blocked/limit. Blocked missions escalate to the operator. Each mission writes a full report to `data/missions/<id>-report.md`.

## Earning-agent guardrails 🛡️

Wired into the **agent loop itself**, not just the prompt:

1. **Transparency** — the system prompt requires AI disclosure wherever the agent creates accounts or posts content.
2. **No manipulation** — no fake engagement, spam, astroturfing, or misleading financial claims; these rules override every task.
3. **Platform compliance** — `policy_check(platform)` before the first action on any platform; if automation is forbidden, the agent reports back instead of acting. *Seed entries ship unverified — confirm each platform's current terms yourself.*
4. **Spending limits** — `wallet_send` hard-refuses anything above `OMNIUSE_WALLET_MAX_TX`, only pays above `OMNIUSE_AUTOPAY_MIN`, requires a stated purpose, logs everything, and additionally sits behind a **confirm** permission. The agent never holds private keys — signing is delegated to your `OMNIUSE_SEND_CMD`.
5. **Human escalation** — anything requiring human legal identity (KYC, bank accounts, signatures) pauses the task and pings you on Telegram.
6. **Full audit trail** — `data/memory/log.jsonl` records every call, decision and payment.
7. **Killswitch** — `/stop` halts everything instantly; checked before every tool call.

### Operator console

```bash
python -m omniuse.operator            # Telegram daemon: /stop /resume /resolve /approve /revoke /status
python -m omniuse.operator stop       # one-shot CLI
python -m omniuse.operator approve wallet_send
python -m omniuse.operator status
```

## Phone setup (mobile toolset)

1. Install [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) (gives you `adb`).
2. On the phone: **Settings → About phone → tap "Build number" 7 times**, then **Settings → Developer options → enable USB debugging**.
3. Plug in via USB, run `adb devices`, accept the prompt.
4. `screen_elements(device='mobile')` and `click('Some button')` now work on the phone.

## Configuration

All config is plain environment variables (see `.env.example`). The essentials:

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | — | Your LLM key (required) |
| `OPENAI_BASE_URL` | OpenAI | Any OpenAI-compatible endpoint |
| `OMNIUSE_MODEL` | `gpt-4o-mini` | Needs vision for the vision toolset |
| `OMNIUSE_DATA_DIR` | `data` | Policies, memory, permissions, missions |
| `OMNIUSE_PLUGINS_DIR` | `plugins` | Drop-in plugin folder |
| `OMNIUSE_WALLET_MAX_TX` | `0.01` | **Hard per-transaction payment cap** |
| `OMNIUSE_SEND_CMD` | — | Command that actually signs/sends; empty = queue only |
| `OMNIUSE_TELEGRAM_BOT_TOKEN` / `_CHAT_ID` | — | Operator alerts + commands |
| `OMNIUSE_OPERATOR_TOKEN` | — | Secret needed to raise the spend limit |
| `OMNIUSE_HUB_URL` / `_TOKEN` | — | Remote body connection |

## ⚠️ Use responsibly

- The `system` toolset runs **real shell commands**; guardrails are brakes, not a sandbox — the agent has whatever permissions you have.
- Use the mobile toolset **only on your own device**.
- Exposing the hub beyond localhost (`--host 0.0.0.0`) means anyone with the token can run tools on that machine — use a strong token and a firewall.
- Crypto payments are irreversible — start with a tiny cap and test in queue-only mode (no `OMNIUSE_SEND_CMD`) first.
- "Earning" online still means following platform terms and the law. The guardrails exist so the agent stays on the right side of both; don't disable them.
- Read the memory log regularly — that's what it's for.

## Roadmap

- [ ] iOS support (via `libimobiledevice` / Appium)
- [ ] Multi-hub routing (one brain, device registry)
- [ ] Streaming CLI with live step display
- [ ] Docker sandbox for the `system` toolset

## License

MIT — see [LICENSE](LICENSE).
