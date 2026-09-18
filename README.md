# OmniUse 🤖

**An AI agent that can actually *use* things** — your browser, your Android phone, your computer, and (with guardrails) your wallet.

> Hinglish mein: *Ek AI agent jo aapke browser, phone aur computer ko khud use kar sakta hai.*
> Task bolo — "phone ki notifications padho", "YouTube pe search karke top videos batao" — agent khud click karega, type karega, screenshot dekhega, aur kaam karke jawab dega.

```
                 ┌───────────────────────────────────────────────┐
                 │                   OmniUse                      │
                 │                                               │
   task ──────▶  │   think ──▶ act (tool call) ──▶ observe ──┐   │
                 │      ▲          │  ▲                     │   │
                 │      └──────────┘  └── killswitch check │   │
                 └───────┬────────┬────────┬───────┬──────┴────┘
                         │        │        │       │
                    🌐 Browser  📱 Mobile  💻 System  👁 Vision
                    🔒 Policy   💰 Wallet   ⚠️ Escalate
                    🧠 Memory   🛑 Killswitch
```

## What it gives your AI

| Toolset | What the agent can do | Requires |
|---|---|---|
| **browser** | Open pages, click, type, scroll, read text & links, take screenshots | `playwright` |
| **mobile** | Tap, swipe, type, press keys, screenshots, `adb shell` on an Android phone | `adb` + USB debugging |
| **system** | Run shell commands, read/write/list files on the computer | nothing extra |
| **vision** | *Look at* any screenshot it takes and reason about what it sees | a vision-capable model |
| **policy** | Check/record each platform's stance on automation before acting on it; carries the non-negotiable rules (AI disclosure, no fake engagement, no spam, no misleading financial claims) | nothing extra |
| **wallet** | Read on-chain balances; send **capped, logged** payments (auto-refuses anything over the per-tx limit; raising the limit needs the operator's secret token; never touches private keys) | optional: `OMNIUSE_SEND_CMD` |
| **escalate** | Pause the task and notify the operator (Telegram) whenever something legally needs a human — KYC, bank accounts, signatures | optional: Telegram bot |
| **memory** | Append-only log of every tool call, decision and reasoning, searchable at any time | nothing extra |
| **killswitch** | One switch, zero activity — checked before **every** tool call | nothing extra |

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

python cli.py --tools mobile,vision "Screenshot my phone and tell me my battery % and notifications"

# earnings/autonomous mode — guardrail toolsets only, no browser/phone
python cli.py --tools policy,wallet,escalate,memory,killswitch "Check if the VPS bill is due and pay it if due"
```

Use it as a library:

```python
from omniuse import Agent

agent = Agent(toolsets=["browser", "vision"], max_steps=15)
answer = agent.run("Find today's top story on Hacker News and summarise it.")
print(answer)
```

## Earning-agent guardrails 🛡️

If you let the agent operate on its own (earning mode), these are wired into the **agent loop itself**, not just the prompt:

1. **Transparency** — the system prompt requires the agent to disclose it is an AI wherever it creates an account or posts content.
2. **No manipulation** — no fake engagement, spam, astroturfing, or misleading financial claims; the policy toolset carries these rules and the prompt makes them override every task.
3. **Platform compliance** — the agent must run `policy_check(platform)` before its first action on any new platform; if automation is forbidden there, it reports back instead of acting. Stances persist in `data/platform_policies.json`. *Seed entries ship unverified — confirm each platform's current terms yourself before relying on them.*
4. **Spending limits** — `wallet_send` hard-refuses anything above `OMNIUSE_WALLET_MAX_TX` (default 0.01 ETH), only pays when the balance meets `OMNIUSE_AUTOPAY_MIN`, requires a stated purpose, and logs every payment (executed, queued, or failed) to memory. Raising the limit requires the operator's secret token (`wallet_raise_limit` with `OMNIUSE_OPERATOR_TOKEN`). The agent never holds private keys — signing is delegated to your own `OMNIUSE_SEND_CMD` (e.g. a hardware-wallet CLI); without it, payments are only queued for you.
5. **Human escalation** — anything requiring human legal identity (KYC, bank accounts, signatures, contracts, tax forms) triggers `escalate_to_operator()`, which notifies you on Telegram and **pauses the task** until you resolve it.
6. **Full audit trail** — every tool call, decision and payment lands in `data/memory/log.jsonl`; use `memory_search` / `memory_recent` or just read the file.
7. **Killswitch** — `python -m omniuse.operator stop` (or Telegram `/stop`) halts all activity instantly; the loop checks it before every tool call. Resume with `/resume`.

### Operator console

```bash
python -m omniuse.operator          # Telegram daemon: /stop /resume /resolve /status
python -m omniuse.operator stop     # one-shot CLI, no Telegram needed
python -m omniuse.operator status
```

Set `OMNIUSE_TELEGRAM_BOT_TOKEN` and `OMNIUSE_TELEGRAM_CHAT_ID` (see `.env.example`) to get escalation alerts on your phone.

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
| `OMNIUSE_DATA_DIR` | `data` | Policies, memory log, killswitch, payment queue |
| `OMNIUSE_TELEGRAM_BOT_TOKEN` / `_CHAT_ID` | — | Operator alerts + /stop /resume /resolve |
| `OMNIUSE_OPERATOR_TOKEN` | — | Secret needed to raise the spend limit |
| `OMNIUSE_RPC_URL` | `https://cloudflare-eth.com` | Ethereum JSON-RPC endpoint |
| `OMNIUSE_WALLET_ADDRESS` | — | Your 0x… address (balance checks) |
| `OMNIUSE_WALLET_MAX_TX` | `0.01` | **Hard per-transaction payment cap** |
| `OMNIUSE_AUTOPAY_MIN` | — | Balance threshold before payments may go out |
| `OMNIUSE_SEND_CMD` | — | Command that actually signs/sends; empty = queue only |

## How it works

1. The task + a system prompt (with the non-negotiable rules) go to the LLM **with a menu of tools**.
2. The LLM replies with a tool call, e.g. `browser_open("example.com")`.
3. Before executing: **killswitch check** (halt if engaged) and **escalation check** (pause if unresolved).
4. OmniUse executes it, auto-logs it to memory, and feeds the result back.
5. Loop. When the LLM stops calling tools, its final message is the answer.

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
- The agent has whatever permissions *you* have — it is not sandboxed. The guardrails (killswitch, spend caps, escalation) are brakes, not a sandbox.
- Use the mobile toolset **only on your own device**.
- Read the memory log (`data/memory/log.jsonl`) regularly — that's what it's for.
- "Earning" online still means following platform terms and the law. The guardrails exist so the agent stays on the right side of both; don't disable them.
- Crypto payments are irreversible — start with a tiny `OMNIUSE_WALLET_MAX_TX` and test with the queue-only mode (no `OMNIUSE_SEND_CMD`) first.

## Roadmap

- [ ] iOS support (via `libimobiledevice` / Appium)
- [ ] Streaming CLI with live step display
- [ ] Docker sandbox for the `system` toolset
- [ ] Scheduled/cron runs with per-run reports

## License

MIT — see [LICENSE](LICENSE).
