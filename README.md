# OmniUse 🤖

**An AI agent that can actually *use* things** — your browser, your Android phone, your computer, remote machines, a paid-work shop (any skill — not just design), and (with guardrails) your wallet. You talk to it by typing or just speaking; it plans, acts, observes, self-corrects, and reports back.

> Hinglish mein: *Ek AI agent jo aapke browser, phone, computer aur remote machines ko khud use kar sakta hai.* Task bolo — "phone ki notifications padho", "mujhe ₹300 chahiye" — agent khud plan banayega, click karega, verify karega, aur kaam karke report dega.

```
                 ┌─────────────────────────────────────────────────┐
                 │                    OmniUse 5.0                   │
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
               📝 Text      📁 Files      🖼 Media
               📊 CSV       🗒 Notes      🔳 QR
               🗣 Speech    📄 Reports
```

## What it gives your AI

| Toolset | What the agent can do |
|---|---|
| **browser** | Open pages, click, type, scroll, read text & links, screenshots, tabs, wait-for, JS eval; persistent profile so logins survive (Playwright) |
| **mobile** | Tap, swipe, type, press keys, screenshots, `adb shell` on Android; **mobile_connect** pairs over WiFi (wireless ADB) — no USB cable, works from Termux too |
| **system** | Run shell commands, read/write/list files; optionally locked down with `OMNIUSE_SYSTEM_ALLOWLIST` (a poor man's Docker — only allowlisted commands run) |
| **vision** | *Look at* any screenshot it takes |
| **screen** | Read a screen as **structured elements** (buttons, inputs, menus) — browser DOM or Android UI tree; and **Set-of-Marks** (`screen_marks`): a screenshot with numbered boxes on every clickable element, so the model clicks "element #7" instead of guessing pixels |
| **universal** | One API for every device: `click('Start Race')`, `type_text(...)`, `scroll`, `open_target(...)`, `drag(...)` — OmniUse decides if that means the browser or the phone |
| **remote** | Run tools on distant machines via **OmniUse Hub** — the AI's remote body (named hub registry) |
| **team** | `spawn_worker()` — delegate sub-tasks to fresh worker agents; the planner keeps the big picture |
| **memory** | Append-only event log (every tool call auto-logged) + a fact store (`memory_save`/`memory_get`) + **lessons learned** (`lesson_save`) — facts, recent runs AND lessons are injected into every task |
| **reports** | `task_report()` — full PDF reports of finished tasks (pure-stdlib PDF writer, no extra dependency); missions auto-generate one |
| **missions** | Autonomous multi-step goals: work → checkpoint → repeat, with a full report per mission (`data/missions/<id>-report.md`) |
| **scheduler** | Run missions on autopilot (`python -m omniuse.scheduler daemon`) — refuses to run while the killswitch is engaged |
| **budget** | Daily step/tool-call caps (`OMNIUSE_DAILY_STEPS` / `_TOOL_CALLS`) — the agent winds down gracefully instead of burning money all night |
| **policy** | Check/record each platform's automation stance before acting; carries the non-negotiable rules |
| **wallet** | Read balances; **capped, logged** payments; limit raises need the operator's secret token; never touches private keys |
| **escalate** | Pause + raise a loud operator alert (terminal banner + alert file) whenever something legally needs a human |
| **killswitch** | One switch, zero activity — checked before **every** tool call |
| **plugins** | Drop a folder into `plugins/` (`plugin.json` + `main.py` with a TOOLS dict) — picked up automatically, manifest permissions enforced like built-ins |
| **design** | `design_poster()` PIL posters (offline) + `design_ai_image()` + `design_watermark()` previews — one example capability |
| **payments** | UPI QR (amount pre-filled), order state machine, screenshot reading, **SMS payment verification + payment_wait** |
| **shop** | Catalog for ANY service, proposals for inbound clients, listing drafts for your own page, **work_preview** for text deliverables, prospect tracking + outreach drafts (operator-sent, one-message rule) |
| **ideas** | `idea_save`/`idea_list`/`idea_update` — a self-starter: when you have no idea, the agent brainstorms, scores and picks one itself |
| **text** | Wordcounts, case, replace, regex extract, slugify, diff, head — plus LLM-powered `text_summarize` and `text_translate` |
| **files** | Read/write/append, tree listing, glob find, folder-size breakdown, Downloads-style `files_organize` (dry-run first), sha256 duplicate finder, zip backups |
| **media** | Resize (exact/% /ratio), crop, convert (png/jpg/webp/…), compress, contact-sheet thumbnail grids — pure Pillow, no API |
| **csvdata** | CSV summaries (types, uniques, min/max/mean), aligned head, row filters (equals/contains/gt/…), column select, merge with dedupe, CSV→JSON — stdlib only |
| **notes** | A searchable personal notebook: add/list/search/delete notes with tags (JSONL storage) |
| **qr** | QR codes for any text, URL, WiFi credentials and vCard contacts (the UPI payment QR lives in payments) |
| **speech** | `voice_speak()` — the agent talks back out loud (text-to-speech, any OpenAI-compatible endpoint; saves an mp3 even with no player installed) |

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
omniuse> improve            ← agent reviews its own history → improvement plan
omniuse> improve apply      ← you approve → behaviour rules go live
```

Voice needs `OMNIUSE_STT_MODEL` (default `whisper-1`) on any OpenAI-compatible provider; mic recording additionally needs `pip install sounddevice numpy scipy`. Console commands route to the operator tools; everything else runs as a full agent task. And the agent can **talk back**: `voice_speak()` (text-to-speech) says short confirmations out loud and always saves the mp3.

## Reliability & speed 🎯

- **Structure beats pixels**: `screen_elements()` reads the DOM / UI tree, `screen_marks()` draws numbered boxes on a screenshot (Set-of-Marks) — the model acts on "element #7", not guessed coordinates.
- **Stuck detection**: the same tool call 3 times in a row triggers a replan warning; a 4th stops the task. No infinite loops, no burning the budget on a wall.
- **Self-correction**: after repeated failures the loop injects an explicit "stop guessing, observe, rethink" nudge.
- **Cheap/fast routing**: set `OMNIUSE_FAST_MODEL` (e.g. a Groq-hosted llama) for routine turns and keep `OMNIUSE_MODEL` for planning and vision.
- **Auto-router**: `--tools auto` (or `Agent(toolsets="auto")`) — one cheap fast-model call reads the task and picks only the toolsets it needs, so the LLM sees a short menu instead of all 100+ tools. Falls back to keyword matching if the LLM is unreachable — it never blocks a task.
- **Memory carries over**: remembered facts + the last few completed runs are injected into every new task — the agent doesn't redo finished work.

## Learning & self-improvement 🧪

The agent gets better with every task, three ways:

- **Lessons** — after any real failure the agent calls `lesson_save(mistake, lesson)`; the last 10 lessons are injected into every future task, so the same mistake is never repeated.
- **PDF reports** — `task_report()` writes a full PDF report (what was done, how, what failed, what was learned) to `data/reports/`; missions auto-generate one next to their markdown report.
- **`improve`** — the operator command reviews the agent's recent runs, errors and lessons, writes `data/improvement-plan.md`; `improve apply` appends its behaviour rules to `data/agent-profile.md`, which is injected into every future task. Tony-Stark-style: it reviews its own work, you approve the fix, it flies better.

## Paid work: any skill, preview-first 🎨

The design shop was just the example — the pipeline works for ANY service you can honestly do: writing, research, data work, translations, tutorials, poster designs, anything. The money rules are enforced in code, not just the prompt:

```
client messages you (inbound only)
   → order_create(client, item, price)           any service, any price
   → do the work (design tools, writing, browser research, ...)
   → order_attach(order, preview, full)          PREVIEW the client can judge:
                                                  design_watermark() for images,
                                                  work_preview() for text work
   → payment_qr(₹price)                          your UPI QR, amount pre-filled
   → client pays
   → payment_wait(order_id)                      agent watches your SMS inbox
                                                  until the bank/UPI credit SMS lands
   → order_delivered()                           the full work, only now
```

What's enforced:
- A payment **screenshot only claims** an order — it never confirms it (screenshots can be edited). Only a credit SMS on your phone (`payment_wait`/`payment_check_sms`) or you yourself (`paid <order_id>` in the console, or `order_mark_paid` with your token) makes an order 'paid'.
- `order_mark_paid` is denied to the agent — it cannot self-approve a payment.
- The full work is refused by `order_delivered()` until the order is verified paid.
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
10. **Shell allowlist (optional)** — set `OMNIUSE_SYSTEM_ALLOWLIST` and `system_run` refuses anything not matching — a sandbox without Docker.

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

**No cable? Wireless (Termux-friendly):**

- **Same WiFi, phone option**: Developer options → **Wireless debugging** → enable, note the ip:port, then `mobile_connect("192.168.x.x:port")` (run `adb pair` once if it asks).
- **From the phone itself (Termux)**: `pkg install adb`, then run the hub or adb inside Termux — control your phone with your phone. No USB, no PC needed.

## Configuration

All config is plain environment variables (see `.env.example`). The essentials:

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | — | Your LLM key (required) |
| `OPENAI_BASE_URL` | OpenAI | Any OpenAI-compatible endpoint |
| `OMNIUSE_MODEL` | `gpt-4o-mini` | Needs vision for the vision toolset |
| `OMNIUSE_FAST_MODEL` | = `OMNIUSE_MODEL` | Cheap/fast model for routine turns |
| `OMNIUSE_DATA_DIR` | `data` | Policies, memory, permissions, missions, orders |
| `OMNIUSE_PLUGINS_DIR` | `plugins` | Drop-in plugin folder |
| `OMNIUSE_PROFILE_DIR` | — | Persistent browser profile (logins survive) |
| `OMNIUSE_DAILY_STEPS` / `_TOOL_CALLS` | `500` | Daily budget caps ("0" = unlimited) |
| `OMNIUSE_SYSTEM_ALLOWLIST` | — (unrestricted) | fnmatch patterns for `system_run` (poor man's Docker) |
| `OMNIUSE_UPI_VPA` | — | Your UPI ID (shop payments) |
| `OMNIUSE_PAYEE_NAME` | — | Name on payment requests & watermarks |
| `OMNIUSE_STT_MODEL` | `whisper-1` | Speech-to-text model for voice control |
| `OMNIUSE_TTS_MODEL` / `_VOICE` | `tts-1` / `alloy` | Text-to-speech for `voice_speak` |
| `OMNIUSE_OPERATOR_TOKEN` | — | Secret needed to raise the spend limit |
| `OMNIUSE_WALLET_MAX_TX` | `0.01` | **Hard per-transaction payment cap** |
| `OMNIUSE_SEND_CMD` | — | Command that actually signs/sends; empty = queue only |
| `OMNIUSE_HUB_URL` / `_TOKEN` | — | Remote body connection |

## ⚠️ Use responsibly

- The `system` toolset runs **real shell commands**; guardrails are brakes, not a sandbox — set `OMNIUSE_SYSTEM_ALLOWLIST` if you want a hard command filter (the agent has whatever permissions you have).
- Use the mobile toolset **only on your own device**.
- Exposing the hub beyond localhost (`--host 0.0.0.0`) means anyone with the token can run tools on that machine — use a strong token and a firewall.
- The scheduler runs missions **without a human watching** — keep daily budgets sane, read the mission reports, and keep the killswitch handy.
- Crypto payments are irreversible — start with a tiny cap and test in queue-only mode (no `OMNIUSE_SEND_CMD`) first.
- **Paid work & outreach**: a payment screenshot can be faked — the agent will not deliver the full work until a credit SMS lands on your phone (or you `paid <order_id>` it yourself in the console). The agent researches prospects and drafts first-contact messages, but **you** send them from your own account — automated unsolicited messages are spam, and platforms ban for it. One message per prospect; never again to non-responders or decliners.
- "Earning" online still means following platform terms and the law. The guardrails exist so the agent stays on the right side of both; don't disable them.
- Read the memory log regularly — that's what it's for.

## Testing

A pytest suite (78 tests, stubbed LLM — no API key needed) covers the registry, the local toolsets, and the rules that must never break: paid-work pipeline, one-message rule, killswitch, escalation, stuck detection, allowlist, Set-of-Marks, PDF reports, lessons, auto-router:

```bash
python -m pytest tests/ -q
```

## Roadmap

- [ ] iOS support (via `libimobiledevice` / Appium)
- [ ] Canva Connect API plugin for the design toolset
- [ ] Streaming CLI with live step display
- [ ] Docker sandbox for the `system` toolset
- [ ] Vector search over the memory log

## License

MIT — see [LICENSE](LICENSE).
