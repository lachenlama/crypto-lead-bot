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
    assert botmain.main([]) == 0
    first = capsys.readouterr().out
    assert first
    assert botmain.main([]) == 0
    assert capsys.readouterr().out == ""  # nothing new second time


def test_all_sources_failing_exits_zero(monkeypatch, tmp_path):
    def bad(cfg=None):
        raise RuntimeError("x")
    monkeypatch.setattr(botmain, "SOURCES", {"superteam": _Src("superteam", bad)})
    monkeypatch.setattr(botmain, "DB_PATH", tmp_path / "leads.db")
    assert botmain.main(["--dry-run"]) == 0
