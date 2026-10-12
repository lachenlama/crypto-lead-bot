# crypto-lead-bot — Build Spec (v1)

A Python bot that finds crypto gigs, jobs and leads matching the owner's profile, scores them, drafts pitches, and sends Telegram alerts. Runs on a schedule via GitHub Actions. Owner profile and strategy: `../plans/money-strategy.md`.

## Owner profile (put in `config/profile.yaml`, editable)
- Priority skills: Python, data/on-chain analytics, bots (Telegram, Discord, Discord→Telegram bridges), AI/LLM agents and automation, full stack (TypeScript, Next.js), dashboards (Dune etc.).
- Secondary: Solidity, EVM, DeFi.
- Goal: gain fund management / treasury experience → boost on-chain analyst, treasury, DAO finance, research analyst roles.
- Rate floor: $60/hr contract, $600 per fixed gig. Remote.
- Avoid: pure Solidity auditor roles (low priority, not excluded), sales/BD, community moderator, unpaid "ambassador" roles.
- Packages (from strategy): community bot, trading/alert bot, on-chain analytics dashboard, AI agent/automation, full-stack dApp/internal tool.

## Sources (v1)
Each source is a module in `bot/sources/` exposing `fetch() -> list[Item]`. One failing source must never break the run (catch, log, continue). Use `httpx` with a 20s timeout and a normal browser User-Agent.

| Source | Kind | Endpoint | Notes |
|---|---|---|---|
| cryptocurrencyjobs.co | job | `https://cryptocurrencyjobs.co/index.xml` | RSS 2.0; items have title, description, pubDate, guid, link. Titles may be double-escaped (`&amp;amp;`): html-unescape twice. |
| CryptoJobsList | job | `https://api.cryptojobslist.com/jobs.rss` | RSS 2.0 with CDATA titles. |
| RemoteOK | job | `https://remoteok.com/api?tag=crypto` | JSON array; element 0 is a legal notice, skip it. Fields: id, position, company, tags, description (HTML), salary_min, salary_max, url, date. Keep the attribution link to RemoteOK as their terms require. |
| Superteam Earn | gig/bounty | `https://superteam.fun/api/listings` | JSON array. Fields: id, title, slug, type (bounty/project/…), rewardAmount, token, deadline, status, compensationType, sponsor.name, agentAccess. Only status == "OPEN". URL: `https://superteam.fun/earn/listing/{slug}`. Skip items with agentAccess "AGENT_ONLY" if present. |
| Telegram job channels | job/gig | `https://t.me/s/{channel}` | Public preview HTML. Messages in `div.tgme_widget_message` with `data-post` attr (`channel/id`), text in `div.tgme_widget_message_text`, time in `time[datetime]`. Channels list in `config/sources.yaml`, default: `cryptojobslist`. Parse defensively; if the structure changes, log and return []. |
| Snapshot (DAO treasury leads) | lead | `https://hub.snapshot.org/graphql` | POST GraphQL: proposals where state "active", first 50, ordered by created desc, fields id, title, body (truncate), space { id name }, link, created, end. Keep only proposals whose title/body mention treasury, diversification, yield, asset management, grants, RFP, tooling, analytics, dashboard. |
| DAO Discourse forums | lead | `{forum}/latest.json` | Forums in config: forum.arbitrum.foundation, gov.optimism.io, governance.aave.com, gov.uniswap.org, research.lido.fi. `topic_list.topics[]` has id, title, slug, created_at. URL `{forum}/t/{slug}/{id}`. Same keyword filter as Snapshot. |

Optional, disabled by default (config flag): web3.career API (needs `WEB3_CAREER_TOKEN`).

## Data model
`Item` dataclass: `source, kind (job|gig|lead), external_id, title, org, url, description (plain text, ≤2000 chars), pay_min, pay_max, pay_currency, pay_unit (year|hour|fixed|unknown), deadline, posted_at, tags[]`. Unique key = `sha1(source + external_id or url)`.

## Storage
SQLite at `data/leads.db` (committed back to the repo by the workflow so state persists between runs). Tables:
- `items` (key PK, all Item fields, first_seen, score, score_reason, package, pitch, alerted_at, scam_flags)
- `pay_observations` (key, source, title, pay_min, pay_max, unit, currency, seen_at) — every item with pay info, for later rate calibration.

## Pipeline (`bot/main.py`, run as `python -m bot.main`)
1. Fetch all enabled sources.
2. Normalize, dedupe against `items`; only new items continue.
3. Scam check (`bot/scam.py`, rule-based): flag phrases like "download and run", "clone the repo and run", "take-home … run locally", "pay a fee", "deposit", "purchase … starter kit", "paid in our token only", "DM on telegram to apply" with no company; and gigs with no org and huge pay. Flagged items are still stored and alerted with a ⚠️ warning line, never dropped silently.
4. Score 0–100 (`bot/score.py`):
   - Rule score from keyword matches against profile (priority skills weigh more than secondary; analyst/treasury/fund roles get a bonus; avoided roles get a penalty; pay below floor gets a penalty; known pay above floor a bonus).
   - If `ANTHROPIC_API_KEY` is set, refine with Claude: send profile + item, get JSON `{score, reason, package}` where package is one of the 5 packages or null. Use model `claude-haiku-5-5` for scoring. Batch items (e.g. 10 per call) to keep cost low. If the key is missing or the call fails, keep the rule score.
5. Pitch drafts: for items scoring ≥ 70 (configurable) and kind in (gig, lead), generate a 4–6 line pitch with model `claude-sonnet-5-5` referencing the matching package, concrete deliverable, and a fixed price from the package range. For jobs, a 3–4 line cover-note opener. Skip if no API key.
6. Alerts (`bot/telegram.py`): Telegram Bot API `sendMessage` with HTML parse mode to `TELEGRAM_CHAT_ID`.
   - Instant alert per item with score ≥ alert threshold (default 70): title, org, kind, pay, deadline, score + one-line reason, scam warning if any, link, and the pitch in a `<blockquote>`.
   - One digest per run listing the next 10 items scoring 50–69 compactly.
   - Respect Telegram's 4096-char limit (split), and sleep ~1s between messages.
   - If Telegram secrets are missing, print alerts to stdout instead (dry run).
7. Mark alerted, save, exit 0 even if some sources failed (log a summary line per source: fetched/new/errors).

CLI flags: `--dry-run` (no Telegram, no DB writes), `--source NAME` (run one source), `--limit N`.

## Config
- `config/profile.yaml` — profile above.
- `config/sources.yaml` — enable/disable sources, Telegram channels, forum list, keyword lists, thresholds.
- Secrets only via env vars: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ANTHROPIC_API_KEY`, optional `WEB3_CAREER_TOKEN`. Never log them.

## Scheduling
`.github/workflows/run.yml`: cron every 4 hours plus `workflow_dispatch`. Python 3.12, `pip install -r requirements.txt`, run `python -m bot.main`, then commit `data/leads.db` back if changed (`contents: write` permission, commit as github-actions bot, message "chore: update leads db [skip ci]").
Also `.github/workflows/test.yml`: run pytest on push/PR.

## Tests (`tests/`)
pytest, no network. Parser tests per source using small fixture files shaped like the real responses described above; scam rules; scoring rules; dedupe; Telegram message splitting; full pipeline in dry-run with sources monkeypatched. Mock the Anthropic client.

## Repo layout
```
bot/__init__.py, main.py, models.py, db.py, score.py, scam.py, pitch.py, telegram.py, llm.py, config.py
bot/sources/__init__.py (registry), cryptocurrencyjobs.py, cryptojobslist.py, remoteok.py, superteam.py, telegram_channels.py, snapshot.py, discourse.py
config/profile.yaml, config/sources.yaml
tests/…, tests/fixtures/…
.github/workflows/run.yml, test.yml
requirements.txt (httpx, feedparser, beautifulsoup4, pyyaml, anthropic, pytest)
README.md — what it does, setup (BotFather token, getting chat id, adding repo secrets), how to run locally, how to add a source.
.gitignore
```

Keep code simple and readable; no frameworks beyond the listed libs.
