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

## v1.1 — Target-company watchlist (personal-assistant mode)

Goal: catch roles at companies the owner actually wants, straight from their career pages, within hours of posting (less competition than job boards).

- New source `bot/sources/watchlist.py` (kind `job`, source name `watchlist`), driven by `config/watchlist.yaml`:
  ```yaml
  companies:
    - {name: Dune, ats: ashby, token: dune, tier: 1}
    - {name: Messari, ats: greenhouse, token: messari, tier: 2}
  ```
  `tier` 1 = dream company, 2 = strong interest.
- ATS public endpoints (no auth):
  - greenhouse: `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` → `jobs[]`: id, title, absolute_url, location.name, updated_at, content (HTML, html-unescape then strip tags).
  - lever: `https://api.lever.co/v0/postings/{token}?mode=json` → array: id, text (title), hostedUrl, categories.location, categories.team, createdAt (ms epoch), descriptionPlain.
  - ashby: `https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true` → `jobs[]`: id, title, jobUrl, location, publishedAt, descriptionPlain, isRemote, compensation.compensationTierSummary (string, may be absent).
- One company failing (404, bad token) must not fail the source: log `watchlist company=NAME ats=X status=404` and continue; raise only if all fail.
- Pre-filter so we don't score hundreds of irrelevant roles: keep a title only if it matches a role keyword list in watchlist.yaml (`role_keywords`: engineer, developer, python, data, analyst, analytics, research, quant, treasury, finance, strategy, ai, ml, automation, full stack, backend, bot, integrations, solutions) and doesn't match `exclude_keywords` (sales, account executive, recruiter, legal, counsel, marketing, designer, hr, people, office, executive assistant, intern unless the owner adds it).
- Item.tags gets `target`, `tier1`/`tier2`. Org = company name.
- Scoring: target-company items get +15 (tier 1) / +8 (tier 2) on the final score, capped at 100. Alert format starts with `🎯 Target company` for these.
- Alerts for target items also include a short "next step" line: "Apply within 24h; look for a referral from someone on the team" (static text, no LLM).
- Seed `config/watchlist.yaml` with ~40 crypto companies that fit the owner (data/analytics, AI, bots/infra, DeFi risk/treasury, funds). Guess ATS+token from the company's careers URL patterns; it's fine if some are wrong, the run log will show which 404 so they can be fixed. Include at least: Dune, Nansen, Messari, Chainalysis, Kaiko, Token Terminal, Artemis, Allium, Flipside, Coin Metrics, Gauntlet, Chaos Labs, Galaxy, Wintermute, Paradigm, Coinbase, Kraken, Uniswap Labs, Aave Labs, Alchemy, Phantom, Fireblocks, Chainlink Labs, Offchain Labs, OP Labs, Consensys, Ondo, Ethena, Eigen Labs, Steakhouse Financial, karpatkey, LlamaRisk, Anchorage Digital, Circle, Ledger, MetaMask/Consensys, Lido, Polygon Labs, 0x, Zerion.
- Add a CLI flag `--check-watchlist` that just hits every company endpoint and prints `name ats token status count` then exits (no scoring/alerts/db). Add a workflow `check-watchlist.yml` (workflow_dispatch only) that runs it.
- Enable `watchlist` in sources.yaml. README: section on editing the watchlist.
- Tests with fixtures for each ATS, the keyword pre-filter, the tier boost, and one-company-404 handling.

### v1.1 addition — AI model evaluation gigs
Owner has AI model evaluation / task-building experience (Handshake AI: Project Dynamo, Project Lever). This is a separate income line, not crypto-only.
- Add to `config/profile.yaml` priority skills: "AI model evaluation", "RLHF / eval task design", "LLM red-teaming", "coding eval tasks (Python/TS/Solidity)". Add a 6th package: "AI eval & task building" (contract, est. $40–100/hr depending on domain expertise).
- Add a second group in `config/watchlist.yaml` with `category: ai_eval` (tier 1): Handshake AI, Mercor, Scale AI / Outlier, Surge AI, DataAnnotation, Labelbox / Alignerr, Micro1, Turing, Invisible Technologies, Snorkel AI, Prolific, Toloka, Appen, Sepal AI, Anthropic/OpenAI-adjacent eval vendors if they have public boards. Guess ATS tokens; the check run will show which work.
- For `ai_eval` companies, `role_keywords` also include: evaluator, annotator, rater, trainer, rlhf, red team, tutor, expert, specialist, contributor, freelance, contract. Remote/contract roles score well even without crypto keywords; crypto/DeFi/Solidity/Python-domain eval roles get an extra +10 (domain-expert evals pay more).
- Tag these items `ai_eval`; alert header `🧪 AI eval gig`.

### v1.1 fixes from the first live run (2026-10-12, GitHub Actions dry run)
All 7 sources worked: cryptocurrencyjobs 55, cryptojobslist 100, remoteok 48, superteam 18, telegram 20, snapshot 8, discourse 14 = 263 items. But the rule score is miscalibrated: 0 items reached 70, and irrelevant jobs ("Regional Managing Director – Little Caesars Pizza", "Flight Coordinator – Starlink Aviation", "Media Specialist – DSW") scored 50.
- RemoteOK `tag=crypto` returns non-crypto jobs: keep a RemoteOK item only if title/tags/description mention a crypto term (crypto, web3, blockchain, defi, onchain/on-chain, ethereum, solana, token, dao, stablecoin, wallet, nft, bitcoin).
- Rule score must start low (e.g. 20) and be earned: items with zero priority/secondary skill matches and no analyst/treasury/ai_eval match must end below 40. Strong matches (e.g. "Python", "data analyst", "bot", "AI", "on-chain analyst", "treasury") should be able to reach 70+ without the LLM. Use word-boundary matching (so "ai" doesn't match "maintain").
- Add `--top N` flag: after scoring, print the top N items with score, reason/matched keywords, source, title, org (works with --dry-run), so scoring can be calibrated from live runs. Make the workflow's dry_run mode pass `--top 30`.
- Tests asserting the junk titles above score < 40 and e.g. "Python Data Analyst – Nansen" scores ≥ 70.
