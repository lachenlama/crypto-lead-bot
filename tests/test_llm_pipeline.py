import json
import sys
from types import SimpleNamespace

from bot import llm, main as botmain, score
from bot.config import load_profile
from bot.models import Item


class FakeClient:
    def __init__(self):
        self.calls = []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.calls.append(kw)
        if kw["model"] == "claude-haiku-5-5":
            n = kw["messages"][0]["content"].count("\n[") + 1
            body = json.dumps([{"i": i, "score": 90, "reason": "great", "package": "community bot"}
                               for i in range(n)])
        else:
            body = "Pitch text."
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=body)])


def test_llm_scoring_and_fallback(monkeypatch):
    fake = FakeClient()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(llm, "_client", fake)
    items = [Item(source="s", kind="job", external_id=str(i), title="Python bot") for i in range(12)]
    score.score_items(items, load_profile(), {"thresholds": {"llm_batch_size": 10}})
    assert len(fake.calls) == 2  # batched 10 + 2
    assert all(i.package == "community bot" and i.score > 60 for i in items)

    def boom(**kw):
        raise RuntimeError("down")
    fake.messages.create = boom
    it = Item(source="s", kind="job", external_id="z", title="Python bot")
    score.score_items([it], load_profile(), {})
    assert it.score is not None and it.package is None


def test_pitch_model_ids(monkeypatch):
    fake = FakeClient()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(llm, "_client", fake)
    it = Item(source="s", kind="gig", external_id="1", title="Bot", package="community bot")
    assert llm.draft_pitch(it, load_profile()) == "Pitch text."
    assert fake.calls[0]["model"] == "claude-sonnet-5-5"


def _items():
    return [
        Item(source="superteam", kind="gig", external_id="1", org="Acme",
             title="Python Telegram bot with on-chain analytics dashboard",
             description="Python, Dune, AI agent", url="https://x/1",
             pay_min=1500, pay_max=1500, pay_currency="USDC", pay_unit="fixed"),
        Item(source="superteam", kind="gig", external_id="2", org="",
             title="Python on-chain analytics dashboard", description="Python Dune telegram bot. download and run this", url="https://x/2"),
    ]


class _Src:
    def __init__(self, name, fn):
        self.NAME, self.fetch = name, fn


def test_pipeline_dry_run(monkeypatch, capsys, tmp_path):
    def bad(cfg=None):
        raise RuntimeError("network down")
    monkeypatch.setattr(botmain, "SOURCES", {"superteam": _Src("superteam", lambda cfg=None: _items()),
                                              "remoteok": _Src("remoteok", bad)})
    monkeypatch.setattr(botmain, "DB_PATH", tmp_path / "leads.db")
    rc = botmain.main(["--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Python Telegram bot" in out
    assert "⚠️" in out or "Warning" in out
    assert not (tmp_path / "leads.db").exists()  # no DB writes in dry run


def test_pipeline_real_run_dedupes(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(botmain, "SOURCES", {"superteam": _Src("superteam", lambda cfg=None: _items())})
    monkeypatch.setattr(botmain, "DB_PATH", tmp_path / "leads.db")
    sent = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    monkeypatch.setattr("bot.telegram.Notifier._post", lambda self, text: sent.append(text) or True)
    monkeypatch.setattr("bot.telegram.time.sleep", lambda s: None, raising=False)
    assert botmain.main([]) == 0
    first = len(sent)
    assert first
    assert botmain.main([]) == 0
    assert len(sent) == first  # nothing new second time


def test_pipeline_without_telegram_does_not_mark_seen(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(botmain, "SOURCES", {"superteam": _Src("superteam", lambda cfg=None: _items())})
    monkeypatch.setattr(botmain, "DB_PATH", tmp_path / "leads.db")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert botmain.main([]) == 0
    assert capsys.readouterr().out
    assert botmain.main([]) == 0
    assert capsys.readouterr().out  # still printed: items weren't marked seen


def test_all_sources_failing_exits_zero(monkeypatch, tmp_path):
    def bad(cfg=None):
        raise RuntimeError("x")
    monkeypatch.setattr(botmain, "SOURCES", {"superteam": _Src("superteam", bad)})
    monkeypatch.setattr(botmain, "DB_PATH", tmp_path / "leads.db")
    assert botmain.main(["--dry-run"]) == 0


def _router(monkeypatch, handler):
    import httpx
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    transport = httpx.MockTransport(handler)
    real = httpx.post
    monkeypatch.setattr(llm.httpx, "post", lambda url, **kw: httpx.Client(transport=transport).post(url, **kw))
    return real


def test_openai_compatible_success(monkeypatch):
    import httpx
    seen = []

    def handler(req):
        body = json.loads(req.content)
        seen.append((str(req.url), req.headers["authorization"], body))
        if body["model"] == "openai/gpt-4o-mini":
            n = body["messages"][1]["content"].count("\n[") + 1
            text = json.dumps([{"i": i, "score": 90, "reason": "r", "package": None} for i in range(n)])
        else:
            text = "Router pitch."
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})
    _router(monkeypatch, handler)
    assert llm.available() and llm.provider() == "openai"
    it = Item(source="s", kind="gig", external_id="1", title="Python bot")
    score.score_items([it], load_profile(), {})
    assert it.score > 60
    url, auth, body = seen[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions" and auth == "Bearer k"
    assert body["messages"][0]["role"] == "system" and body["max_tokens"]
    assert llm.draft_pitch(it, load_profile(), llm.model_for("pitch")) == "Router pitch."
    assert seen[-1][2]["model"] == "openai/gpt-4o"


def test_openai_compatible_500_falls_back_to_rules(monkeypatch):
    import httpx
    _router(monkeypatch, lambda req: httpx.Response(500))
    it = Item(source="s", kind="job", external_id="1", title="Python bot")
    rule, _ = score.rule_score(it, load_profile())
    score.score_items([it], load_profile(), {})
    assert it.score == rule and it.package is None


def test_model_selection(monkeypatch):
    cfg = {"models": {"scoring": "a", "pitch": "b", "openai_score": "c", "openai_pitch": "d"}}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert (llm.model_for("score", cfg), llm.model_for("pitch", cfg)) == ("a", "b")
    monkeypatch.setenv("LLM_API_KEY", "y")  # router wins when both are set
    monkeypatch.setenv("LLM_BASE_URL", "https://r.example/v1")
    assert (llm.model_for("score", cfg), llm.model_for("pitch", cfg)) == ("c", "d")
    monkeypatch.setenv("LLM_SCORE_MODEL", "env-m")
    assert llm.model_for("score", cfg) == "env-m"
    assert llm.model_for("pitch", {}) == "openai/gpt-4o"
