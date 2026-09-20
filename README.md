# OmniUse 🤖

**An AI agent that can actually *use* things** — your browser, your Android phone, your computer, remote machines, a design shop, and (with guardrails) your wallet. You talk to it by typing or just speaking; it plans, acts, observes, self-corrects, and reports back.

> Hinglish mein: *Ek AI agent jo aapke browser, phone, computer aur remote machines ko khud use kar sakta hai.* Task bolo — "phone ki notifications padho", "mujhe ₹300 chahiye" — agent khud plan banayega, click karega, verify karega, aur kaam karke report dega.

```
                 ┌─────────────────────────────────────────────────┐
                 │                    OmniUse 3.2                   │
                 │                                                 │
   task ──────▶  │  think ──▶ act ──▶ [permissions? killswitch?]  │
                 │    ▲                    │                       │
                 │    └──── observe ◀──────┘   (self-correction)    │
                 └──┬─────────┬─────────┬─────────┬─────────┬──────┘
                    │         │         │         │         │
               🌐 Browser  📱 Mobile  💻 System  👁 Vision  🖥 Remote
               🔒 Policy   💰 Wallet  ⚠️ Escalate  🧠 Memory  🛑 Killswitch
               🖱 Universal 📺 Screen  🔌 Plugins  🚀 Missions  🕒 Scheduler
               🧑‍🤝‍🧑 Team     🧾 Budget   🎨 Design   💸 Payments  🛍 Shop
               💡 Ideas     🤝 Prospects   🎙 Voice
```

## What it gives your AI

| Toolset | What the agent can do |
|---|---|
| **browser** | Open pages, click, type, scroll, read text & links, screenshots, tabs, wait-for, JS eval; persistent profile so logins survive (Playwright) |
| **mobile** | Tap, swipe, type, press keys, screenshots, `adb shell` on Android |
| **system** | Run shell commands, read/write/list files |
| **vision** | *Look at* any screenshot it takes |
| **screen** | Read a screen as **structured elements** (buttons, inputs, menus) — browser DOM or Android UI tree; `find_element('Start Race')` beats guessing coordinates |
| **universal** | One API for every device: `click('Start Race')`, `type_text(...)`, `scroll`, `open_target(...)`, `drag(...)` — OmniUse decides if that means the browser or the phone |
| **remote** | Run tools on distant machines via **OmniUse Hub** — the AI's remote body (named hub registry) |
| **team** | `spawn_worker()` — delegate sub-tasks to fresh worker agents; the planner keeps the big picture |
| **memory** | Append-only event log (every tool call auto-logged) + a fact store (`memory_save`/`memory_get`) so "mera GitHub username yaad rakhna" actually works across runs; remembered facts are injected into every task |
| **missions** | Autonomous multi-step goals: work → checkpoint → repeat, with a full report per mission (`data/missions/<id>-report.md`) |
| **scheduler** | Run missions on autopilot (`python -m omniuse.scheduler daemon`) — refuses to run while the killswitch is engaged |
| **budget** | Daily step/tool-call caps (`OMNIUSE_DAILY_STEPS` / `_TOOL_CALLS`) — the agent winds down gracefully instead of burning money all night |
| **policy** | Check/record each platform's automation stance before acting; carries the non-negotiable rules |
| **wallet** | Read balances; **capped, logged** payments; limit raises need the operator's secret token; never touches private keys |
| **escalate** | Pause + raise a loud operator alert (terminal banner + alert file) whenever something legally needs a human |
| **killswitch** | One switch, zero activity — checked before **every** tool call |
| **plugins** | Drop a folder into `plugins/` (`plugin.json` + `main.py` with a TOOLS dict) — picked up automatically, manifest permissions enforced like built-ins |
| **design** | `design_poster()` PIL posters (offline) + `design_ai_image()` + `design_watermark()` previews |
| **payments** | UPI QR (amount pre-filled), order state machine, screenshot reading, **SMS payment verification + payment_wait** |
| **shop** | Catalog, proposals for inbound clients, listing drafts for your own page, prospect tracking + outreach drafts (operator-sent, one-message rule) |
| **ideas** | `idea_save`/`idea_list`/`idea_update` — a self-starter: when you have no idea, the agent brainstorms, scores and picks one itself |

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

## Talking to it: terminal + voice 🎙

No external messaging services — everything runs in your terminal, and you can just *speak*:

```bash
python -m omniuse.operator        # interactive console: commands AND free-text tasks
python -m omniuse.operator stop   # one-shot CLI commands
python -m omniuse.voice listen    # 10s mic recording → transcribed → routed
python -m omniuse.voice listen 30 # 30 seconds
python -m omniuse.voice file v.wav  # a saved voice note
```

```
omniuse> bhai mujhe 300 rupay chahiye      ← typed or spoken → agent task
omniuse> orders                            ← shop orders + states
omniuse> paid ord-1234-abc                 ← YOU confirming the money arrived
omniuse> stop / resume / resolve / approve <tool> / revoke / status
```

Voice needs `OMNIUSE_STT_MODEL` (default `whisper-1`) on any OpenAI-compatible provider; mic recording additionally needs `pip install sounddevice numpy scipy`. Console commands route to the operator tools; everything else runs as a full agent task.

## The design shop: watermark-first, verify-then-deliver 🎨

Sell your designs with an honest pipeline — the money rules are enforced in code, not just the prompt:

```
client messages you (inbound only)
   → design_poster() / design_ai_image()        make the design
   → design_watermark()                         watermarked preview
   → order_create + order_attach                track the order
   → payment_qr(₹price)                         your UPI QR, amount pre-filled
   → client pays
   → payment_wait(order_id)                     agent watches your SMS inbox
                                                until the bank/UPI credit SMS lands
   → order_delivered()                          clean full-resolution file, only now
```

What's enforced:
- A payment **screenshot only claims** an order — it never confirms it (screenshots can be edited). Only a credit SMS on your phone (`payment_wait`/`payment_check_sms`) or you yourself (`paid <order_id>` in the console, or `order_mark_paid` with your token) makes an order 'paid'.
- `order_mark_paid` is denied to the agent — it cannot self-approve a payment.
- The clean file is refused by `order_delivered()` until the order is verified paid.
- Every state change lands in the audit log (`data/memory/log.jsonl`).

## Self-starter: ideas, clients, one-message rule 🧠

Tell OmniUse you're out of ideas and it thinks for itself:

```
you:    "bhai mujhe ₹300 chahiye, mere paas koi idea nahi hai"
agent:  brainstorms ideas → idea_save (scored: earning vs effort)
        → idea_list (ranked) → idea_update(best, 'active')
        → proposes a plan and starts working it
```

Finding clients — researched by the agent, **sent by you**:

```
agent:  prospect_add("Sharma Sweets", source="google maps", notes="mithai shop")
        outreach_draft("Sharma Sweets", "Shop poster design")   → personalised draft
you:    send it yourself, from your own WhatsApp — once
        no reply? → prospect_status('contacted')  …and the agent REFUSES any second draft
        reply?   → prospect_status('replied')     …order flow continues (watermark → QR → paid)
```

Why the agent doesn't send first-contact messages itself: automated unsolicited messages get your account banned (spam, platform ToS) — and one honest message from you converts better than a hundred bot blasts anyway.

## Guardrails 🛡️

Wired into the **agent loop itself**, checked before every tool call — not just the prompt:

1. **Transparency** — the agent must disclose it's an AI wherever it creates accounts or posts content.
2. **No manipulation** — no fake engagement, spam, astroturfing, or misleading financial claims; these rules override every task.
3. **Platform compliance** — `policy_check(platform)` before the first action on any platform; if automation is forbidden, the agent reports back instead of acting. *Seed entries ship unverified — confirm each platform's current terms yourself.*
4. **Permissions** — every tool call is checked against `data/permissions.json`: allow / confirm (needs your approval) / deny. Defaults: wallet_send confirm, destructive shell patterns confirm, mobile_shell confirm, remote_run confirm, wallet_raise_limit + order_mark_paid deny. Edit the JSON anytime — no restart needed.
5. **Spending limits** — `wallet_send` hard-refuses anything above `OMNIUSE_WALLET_MAX_TX`, only pays above `OMNIUSE_AUTOPAY_MIN`, requires a stated purpose, and never touches private keys — signing is delegated to your `OMNIUSE_SEND_CMD`.
6. **Human escalation** — anything requiring human legal identity (KYC, bank accounts, signatures) pauses the task and raises a loud banner in your terminal (plus `data/escalation-alert.txt`).
7. **Full audit trail** — `data/memory/log.jsonl` records every call, decision and payment.
8. **Killswitch** — `stop` halts everything instantly; checked before every tool call.
9. **Daily budget** — step/tool-call caps wind the agent down instead of running all night.

## Autonomy: missions, scheduler, team 🚀

- **Missions** — `Mission("goal")` iterates: work → report status → checkpoint → repeat until done/blocked/limit. Blocked missions escalate to you. Full report per mission in `data/missions/`.
- **Scheduler** — `python -m omniuse.scheduler add "Check server health" --every 60` then `daemon` to run missions on autopilot (never while the killswitch is engaged, always under the daily budget).
- **Team** — `spawn_worker("research X", toolsets="browser,screen")` delegates a focused sub-task to a fresh worker agent. Workers inherit every guardrail.
- **Remote bodies** — run `OMNIUSE_HUB_TOKEN=<secret> python -m omniuse.hub` on any machine, register it (`python -m omniuse.remote add pc1 <url> <token>`), then `remote_run(..., hub="pc1")` executes tools there. One brain, many bodies — token-authenticated, same permission rules.

## Phone setup (mobile toolset)

1. Install [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) (gives you `adb`).
2. On the phone: **Settings → About phone → tap "Build number" 7 times**, then **Settings → Developer options → enable USB debugging**.
3. Plug in via USB, run `adb devices`, accept the prompt.
4. `screen_elements(device='mobile')` and `click('Some button')` now work on the phone. SMS read permission additionally enables `payment_check_sms`/`payment_wait`.

## Configuration

All config is plain environment variables (see `.env.example`). The essentials:

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | — | Your LLM key (required) |
| `OPENAI_BASE_URL` | OpenAI | Any OpenAI-compatible endpoint |
| `OMNIUSE_MODEL` | `gpt-4o-mini` | Needs vision for the vision toolset |
| `OMNIUSE_DATA_DIR` | `data` | Policies, memory, permissions, missions, orders |
| `OMNIUSE_PLUGINS_DIR` | `plugins` | Drop-in plugin folder |
| `OMNIUSE_PROFILE_DIR` | — | Persistent browser profile (logins survive) |
| `OMNIUSE_DAILY_STEPS` / `_TOOL_CALLS` | `500` | Daily budget caps ("0" = unlimited) |
| `OMNIUSE_UPI_VPA` | — | Your UPI ID (shop payments) |
| `OMNIUSE_PAYEE_NAME` | — | Name on payment requests & watermarks |
| `OMNIUSE_STT_MODEL` | `whisper-1` | Speech-to-text model for voice control |
| `OMNIUSE_OPERATOR_TOKEN` | — | Secret needed to raise the spend limit |
| `OMNIUSE_WALLET_MAX_TX` | `0.01` | **Hard per-transaction payment cap** |
| `OMNIUSE_SEND_CMD` | — | Command that actually signs/sends; empty = queue only |
| `OMNIUSE_HUB_URL` / `_TOKEN` | — | Remote body connection |

## ⚠️ Use responsibly

- The `system` toolset runs **real shell commands**; guardrails are brakes, not a sandbox — the agent has whatever permissions you have.
- Use the mobile toolset **only on your own device**.
- Exposing the hub beyond localhost (`--host 0.0.0.0`) means anyone with the token can run tools on that machine — use a strong token and a firewall.
- The scheduler runs missions **without a human watching** — keep daily budgets sane, read the mission reports, and keep the killswitch handy.
- Crypto payments are irreversible — start with a tiny cap and test in queue-only mode (no `OMNIUSE_SEND_CMD`) first.
- **Shop & outreach**: a payment screenshot can be faked — the agent will not deliver the clean file until a credit SMS lands on your phone (or you `paid <order_id>` it yourself in the console). The agent researches prospects and drafts first-contact messages, but **you** send them from your own account — automated unsolicited messages are spam, and platforms ban for it. One message per prospect; never again to non-responders or decliners.
- "Earning" online still means following platform terms and the law. The guardrails exist so the agent stays on the right side of both; don't disable them.
- Read the memory log regularly — that's what it's for.

## Roadmap

- [ ] iOS support (via `libimobiledevice` / Appium)
- [ ] Canva Connect API plugin for the design toolset
- [ ] Streaming CLI with live step display
- [ ] Docker sandbox for the `system` toolset

## License

MIT — see [LICENSE](LICENSE).
