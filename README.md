# crypto-lead-bot

Finds crypto jobs, gigs and DAO treasury leads that match the owner's profile, scores them
(rules + optional Claude refinement), drafts pitches, and sends Telegram alerts. Runs every
4 hours via GitHub Actions; state lives in `data/leads.db` (committed back by the workflow).

Sources: cryptocurrencyjobs.co, CryptoJobsList, RemoteOK (attribution kept), Superteam Earn,
public Telegram channel previews, Snapshot active proposals, DAO Discourse forums.
Optional (off by default): web3.career (`WEB3_CAREER_TOKEN`).

## Setup
1. Telegram: talk to [@BotFather](https://t.me/BotFather), `/newbot`, copy the token.
2. Chat id: message your bot once, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id`.
3. In the GitHub repo: Settings > Secrets and variables > Actions, add
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ANTHROPIC_API_KEY` (optional; without it only
   rule scoring runs and no pitches are drafted) and optionally `WEB3_CAREER_TOKEN`.
4. Enable Actions. `run.yml` runs on cron and `workflow_dispatch`; `test.yml` runs pytest.

Secrets are only read from environment variables and are never logged.

## Run locally
```
pip install -r requirements.txt
python -m bot.main --dry-run          # no Telegram, no DB writes; alerts print to stdout
python -m bot.main --source remoteok --limit 20
python -m pytest -q
```
Without Telegram secrets the bot prints alerts to stdout. Edit `config/profile.yaml` (skills,
rate floor, packages) and `config/sources.yaml` (enabled sources, channels, forums, keywords,
thresholds, model ids).

## Scoring
Rule score (0-100) from profile keywords, analyst/treasury bonus, avoid penalty and pay vs
floor. With `ANTHROPIC_API_KEY`, `claude-haiku-5-5` scores items in batches of 10; the final
score is 0.7 * LLM + 0.3 * rules. Items scoring >= 70 get a pitch from `claude-sonnet-5-5`
(gigs/leads: 4-6 lines with package and fixed price; jobs: 3-4 line cover note).
Scam-rule hits (`bot/scam.py`) add a warning line to the alert; items are never dropped.

## Add a source
1. Create `bot/sources/mysource.py` with `NAME = "mysource"`, a pure `parse(...) -> list[Item]`
   and `fetch(cfg=None) -> list[Item]` (use `bot.http.client()`).
2. Register it in `bot/sources/__init__.py`.
3. Enable it under `enabled:` in `config/sources.yaml`.
4. Add a small fixture in `tests/fixtures/` and a parser test.
A failing source is caught and logged; it never breaks the run.
