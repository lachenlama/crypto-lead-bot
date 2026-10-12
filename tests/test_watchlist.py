import httpx
import pytest

from bot import main as botmain, score, telegram
from bot.config import load_profile, load_watchlist
from bot.models import Item
from bot.sources import remoteok, watchlist

WL = {
    "role_keywords": ["engineer", "data", "analyst", "ai", "full stack"],
    "exclude_keywords": ["sales", "account executive", "recruiter", "intern", "office"],
    "ai_eval_role_keywords": ["evaluator", "contract"],
}
T1 = {"name": "Nansen", "ats": "ashby", "token": "nansen", "tier": 1}
T2 = {"name": "Messari", "ats": "greenhouse", "token": "messari", "tier": 2}
EVAL = {"name": "Mercor", "ats": "ashby", "token": "mercor", "tier": 1, "category": "ai_eval"}


def test_parse_greenhouse(fx):
    items = watchlist.parse_greenhouse(fx("greenhouse.json"), T2)
    assert len(items) == 3
    it = items[0]
    assert it.org == "Messari" and it.kind == "job" and it.source == "watchlist"
    assert it.external_id == "messari:4001" and it.url.endswith("/4001")
    assert "<" not in it.description and "pipelines" in it.description and "Remote" in it.description
    assert it.tags == ["target", "tier2"]


def test_parse_lever(fx):
    items = watchlist.parse_lever(fx("lever.json"), {**T2, "ats": "lever", "token": "kaiko"})
    assert items[0].title == "Backend Engineer, Integrations"
    assert items[0].posted_at.startswith("2025-10-0")  # ms epoch -> ISO
    assert "Remote - EU" in items[0].description


def test_parse_ashby(fx):
    items = watchlist.parse_ashby(fx("ashby.json"), T1)
    assert items[0].tags == ["target", "tier1"]
    assert "$120K - $160K" in items[0].description and "remote" in items[0].description
    assert "Compensation" not in items[1].description


def test_title_prefilter(fx):
    assert watchlist.title_ok("Senior Data Engineer", T2, WL)
    assert watchlist.title_ok("Full-Stack Developer", T2, {**WL, "role_keywords": ["full stack"]})
    assert not watchlist.title_ok("Account Executive, Enterprise", T2, WL)
    assert not watchlist.title_ok("Office Manager", T2, WL)
    assert not watchlist.title_ok("Head of Marketing", T2, WL)
    assert not watchlist.title_ok("Data Intern", T2, WL)
    assert not watchlist.title_ok("Model Evaluator", T2, WL)  # evaluator only for ai_eval
    assert watchlist.title_ok("Model Evaluator", EVAL, WL)
    assert watchlist.title_ok("Freelance Contract Writer", EVAL, WL)


def test_shipped_watchlist_config():
    wl = load_watchlist()
    names = {c["name"] for c in wl["companies"]}
    assert {"Dune", "Nansen", "Messari", "Handshake AI", "Mercor"} <= names
    assert all(c["ats"] in watchlist.URLS and c["tier"] in (1, 2) for c in wl["companies"])
    assert any(c.get("category") == "ai_eval" for c in wl["companies"])
    assert watchlist.title_ok("Python Data Analyst", T1, wl)


def _patch(monkeypatch, handler, companies):
    monkeypatch.setattr(watchlist, "load_watchlist", lambda: {**WL, "companies": companies})
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(watchlist, "client", lambda: httpx.Client(transport=transport))


def test_one_company_404_does_not_fail_source(monkeypatch, fx, caplog):
    def handler(req):
        if "ashbyhq" in req.url.host:
            return httpx.Response(404)
        return httpx.Response(200, json=fx("greenhouse.json"))
    _patch(monkeypatch, handler, [T1, T2])
    with caplog.at_level("WARNING"):
        items = watchlist.fetch()
    assert [i.title for i in items] == ["Senior Data Engineer"]
    assert "watchlist company=Nansen ats=ashby status=404" in caplog.text


def test_all_companies_failing_raises(monkeypatch):
    _patch(monkeypatch, lambda req: httpx.Response(404), [T1, T2])
    with pytest.raises(RuntimeError):
        watchlist.fetch()


def test_check_watchlist_cli(monkeypatch, fx, capsys):
    def handler(req):
        if "ashbyhq" in req.url.host:
            return httpx.Response(404)
        return httpx.Response(200, json=fx("greenhouse.json"))
    _patch(monkeypatch, handler, [T1, T2])
    assert botmain.main(["--check-watchlist"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["Nansen ashby nansen 404 -", "Messari greenhouse messari 200 3"]


def mk(**kw):
    d = dict(source="s", kind="job", external_id="1", title="t")
    d.update(kw)
    return Item(**d)


def test_tier_boost_and_cap():
    p = load_profile()
    base = dict(title="Python Data Analyst", org="Nansen")
    plain, t1, t2 = mk(**base), mk(**base, tags=["target", "tier1"]), mk(**base, tags=["target", "tier2"])
    score.score_items([plain, t1, t2], p)
    assert t1.score == min(100, plain.score + 15) and t2.score == min(100, plain.score + 8)
    assert "target company" in t1.score_reason
    top = mk(title="Python AI bot dashboard analyst", description="python llm dune", tags=["tier1"])
    score.score_items([top], p)
    assert top.score == 100


def test_ai_eval_scoring():
    p = load_profile()
    gen = mk(title="Model Evaluator", description="Remote contract work evaluating chatbots",
             tags=["target", "tier1", "ai_eval"])
    dom = mk(title="Model Evaluator", description="Remote contract: evaluate crypto code",
             tags=["target", "tier1", "ai_eval"])
    plain = mk(title="Model Evaluator", description="Remote contract work evaluating chatbots")
    r = [score.rule_score(i, p)[0] for i in (gen, dom, plain)]
    assert r[0] >= 60 and r[1] == r[0] + 10 and r[0] > r[2]
    score.score_items([gen], p)
    assert gen.score >= 70


def test_alert_headers():
    t = mk(title="Eng", score=80, tags=["target", "tier1"], url="http://u")
    e = mk(title="Eval", score=80, tags=["target", "tier1", "ai_eval"], url="http://u")
    n = mk(title="Plain", score=80, url="http://u")
    assert telegram.format_alert(t).startswith("🎯 Target company")
    assert "Apply within 24h; look for a referral" in telegram.format_alert(t)
    assert telegram.format_alert(e).startswith("🧪 AI eval gig")
    assert "Apply within 24h" in telegram.format_alert(e)
    assert "Target company" not in telegram.format_alert(n) and "Apply within" not in telegram.format_alert(n)


def test_remoteok_crypto_filter(fx):
    assert [i.external_id for i in remoteok.parse(fx("remoteok.json"))] == ["111", "112"]
    assert not remoteok.is_crypto({"position": "Flight Coordinator", "tags": ["ops"], "description": "maintain planes"})
    assert remoteok.is_crypto({"position": "Backend", "tags": [], "description": "build on-chain tooling"})
    assert remoteok.is_crypto({"position": "Wallet Engineer", "tags": [], "description": ""})


@pytest.mark.parametrize("title,desc", [
    ("Regional Managing Director - Little Caesars Pizza", "Lead pizza stores. Maintain operations, automation of dashboards."),
    ("Flight Coordinator - Starlink Aviation", "Maintain flight schedules and analytics reports."),
    ("Media Specialist - DSW", "Plan media. data and research."),
])
def test_junk_scores_low(title, desc):
    s, _ = score.rule_score(mk(source="remoteok", title=title, description=desc), load_profile())
    assert s < 40


def test_strong_matches_reach_70():
    p = load_profile()
    for title in ("Python Data Analyst - Nansen", "On-chain Analyst", "Treasury Analyst - DeFi Fund",
                  "Telegram Bot Developer (Python)", "AI Agent Engineer"):
        s, why = score.rule_score(mk(title=title), p)
        assert s >= 70, (title, s, why)


def test_top_flag_prints(monkeypatch, capsys, tmp_path):
    from tests.test_llm_pipeline import _Src, _items
    monkeypatch.setattr(botmain, "SOURCES", {"superteam": _Src("superteam", lambda cfg=None: _items())})
    monkeypatch.setattr(botmain, "DB_PATH", tmp_path / "leads.db")
    assert botmain.main(["--dry-run", "--top", "1"]) == 0
    out = capsys.readouterr().out
    assert " | superteam | Python Telegram bot" in out
    assert not (tmp_path / "leads.db").exists()


def test_ai_eval_tag_only_for_eval_titles(monkeypatch):
    from bot.sources import watchlist as wlmod
    co = {"name": "EvalCo", "ats": "greenhouse", "token": "evalco", "tier": 1, "category": "ai_eval"}
    wl = {"companies": [co], "role_keywords": ["engineer", "research"],
          "ai_eval_role_keywords": ["expert", "rater"], "exclude_keywords": []}
    data = {"jobs": [
        {"id": 1, "title": "Research Scientist", "absolute_url": "u1", "content": ""},
        {"id": 2, "title": "Python Expert (Contract)", "absolute_url": "u2", "content": ""},
    ]}
    monkeypatch.setattr(wlmod, "load_watchlist", lambda: wl)
    monkeypatch.setattr(wlmod, "fetch_company", lambda c, company: wlmod.parse_greenhouse(data, company))
    items = {i.title: i for i in wlmod.fetch()}
    assert "ai_eval" not in items["Research Scientist"].tags
    assert "ai_eval" in items["Python Expert (Contract)"].tags
