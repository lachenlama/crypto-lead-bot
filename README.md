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
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, an LLM key (optional, see "LLM options"; without
   one only rule scoring runs and no pitches are drafted) and optionally `WEB3_CAREER_TOKEN`.
4. Enable Actions. `run.yml` runs on cron and `workflow_dispatch`; `test.yml` runs pytest.

Secrets are only read from environment variables and are never logged.

## Run locally
```
pip install -r requirements.txt
python -m bot.main --dry-run          # no Telegram, no DB writes; alerts print to stdout
python -m bot.main --source remoteok --limit 20
python -m bot.main --dry-run --top 30  # also print the 30 best-scored items with reasons (calibration)
python -m bot.main --check-watchlist   # hit every watchlist endpoint: name ats token status count
python -m pytest -q
```
Without Telegram secrets the bot prints alerts to stdout. Edit `config/profile.yaml` (skills,
rate floor, packages) and `config/sources.yaml` (enabled sources, channels, forums, keywords,
thresholds, model ids).

## LLM options
Either works; with neither key set, only rule scoring runs.
- OpenAI-compatible router (OpenRouter etc.): set secret `LLM_API_KEY`. Optional repo variables
  (Settings > Variables) `LLM_BASE_URL` (default `https://openrouter.ai/api/v1`),
  `LLM_SCORE_MODEL`, `LLM_PITCH_MODEL`. Defaults come from `models.openai_score` /
  `models.openai_pitch` in `config/sources.yaml` (`openai/gpt-4o-mini`, `openai/gpt-4o`;
  editable placeholders). A non-2xx response falls back to rule scores.
- Anthropic: set `ANTHROPIC_API_KEY`; models from `models.scoring` / `models.pitch`.
`LLM_API_KEY` wins if both are set. Keys are read from the environment only and never logged.

## Scoring
Rule score (0-100) from profile keywords, analyst/treasury bonus, avoid penalty and pay vs
floor. With an LLM key, the scoring model (default `claude-haiku-5-5`) scores items in batches of 10; the final
score is 0.7 * LLM + 0.3 * rules. Items scoring >= 70 get a pitch from the pitch model (default `claude-sonnet-5-5`)
(gigs/leads: 4-6 lines with package and fixed price; jobs: 3-4 line cover note).
The rule score starts at 20 and must be earned: skills in the title weigh much more than
mentions in the description (word-boundary matching), analyst/treasury titles get a bonus, and
items matching nothing are capped at 35. Use `--top N` to see how items scored and why.
Target-company items get +15 (tier 1) / +8 (tier 2) on the final score.
Scam-rule hits (`bot/scam.py`) add a warning line to the alert; items are never dropped.

## Target-company watchlist
`config/watchlist.yaml` lists companies whose Greenhouse / Lever / Ashby boards are polled
(source `watchlist`, enabled in `sources.yaml`):
```yaml
companies:
  - {name: Dune, ats: ashby, token: dune, tier: 1}   # tier 1 = dream, 2 = strong interest
```
The token is the slug in the careers URL (`boards.greenhouse.io/<token>`, `jobs.lever.co/<token>`,
`jobs.ashbyhq.com/<token>`). Only titles matching `role_keywords` and not `exclude_keywords` are
kept. Alerts for these start with `🎯 Target company` and add a next-step line. A company that
fails (404/bad token) is logged as `watchlist company=NAME ats=X status=404` and skipped.
Tokens are guesses: run `python -m bot.main --check-watchlist` or the manual `check-watchlist`
workflow and fix or delete the ones that 404 (or show 0 jobs).

### AI model evaluation gigs
Entries with `category: ai_eval` (Handshake AI, Mercor, Scale/Outlier, Surge, ...) also match
`ai_eval_role_keywords` (evaluator, annotator, rlhf, ...), are tagged `ai_eval`, alert as
`🧪 AI eval gig`, and score well when remote/contract, +10 more for crypto/Python/Solidity domain
evals. `config/profile.yaml` has the matching skills and the "AI eval & task building" package.

## Add a source
1. Create `bot/sources/mysource.py` with `NAME = "mysource"`, a pure `parse(...) -> list[Item]`
   and `fetch(cfg=None) -> list[Item]` (use `bot.http.client()`).
2. Register it in `bot/sources/__init__.py`.
3. Enable it under `enabled:` in `config/sources.yaml`.
4. Add a small fixture in `tests/fixtures/` and a parser test.
A failing source is caught and logged; it never breaks the run.
