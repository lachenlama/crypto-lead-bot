"""v1.3: hackathons and grants (parsers, helpers, eligibility, scoring, alerts)."""
from datetime import date

from bot import events, location, score
from bot.config import load_profile, load_sources_config
from bot.models import Item
from bot.sources import devfolio, devpost, ethglobal, superteam_grants
from bot.telegram import format_alert, format_digest

TODAY = date(2026, 11, 5)


# --- helpers ---

def test_parse_money_and_prize_text():
    assert events.parse_money("₹ 200,000") == (200000.0, "INR")
    assert events.parse_money("$CAD 1,400") == (1400.0, "CAD")
    assert events.parse_money("€1,000") == (1000.0, "EUR")
    assert events.parse_money("no money here") == (None, "")
    # Indian digit grouping; the entry fee next to it is smaller and loses
    assert events.prize_from_text("- ₹1,25,000 prize pool\n- Entry pass ₹300") == (125000.0, "INR")
    assert events.prize_from_text("Prizes worth $10k for DeFi") == (10000.0, "USD")
    assert events.prize_from_text("Ticket costs $20") == (None, "")  # not near a prize word


def test_end_date_formats():
    assert events.end_date("Oct 17 - Nov 10, 2026") == "2026-11-10"
    assert events.end_date("Nov 13 - 20, 2026") == "2026-11-20"
    assert events.end_date("Jul 16, 2026 - Jan 15, 2027") == "2027-01-15"
    assert events.end_date("ETHOnline 2026 Sep 4th – Sep 16th, 2026 Online") == "2026-09-16"
    assert events.end_date("November 5 7 Thu — Sat") == ""
    assert events.iso_date("2026-11-10T11:00:00.000Z") == "2026-11-10"
    assert events.days_left("2026-11-06", TODAY) == 1


# --- parsers ---

def test_devpost_parse(fx):
    items = devpost.parse(fx("devpost.json"))
    titles = [i.title for i in items]
    assert "Bharat Builds Tour" not in titles  # no cash prize: not paid work
    assert "Private Invite Hack" not in titles  # invite-only
    pp = items[0]
    assert pp.kind == "hackathon" and pp.org == "PayPal"
    assert (pp.pay_max, pp.pay_currency, pp.deadline) == (67500.0, "USD", "2026-11-12")
    assert pp.description.startswith("Location: Online")
    her = next(i for i in items if i.title == "Herhack")
    assert her.url == "https://herhack.devpost.com/" and her.pay_currency == "INR"
    assert her.deadline == "2026-11-20"


def test_devfolio_parse(fx):
    items = devfolio.parse(fx("devfolio.json"))
    assert [i.title for i in items] == ["THE BIG HACK 2.0", "hackodisha-6.0"]  # private skipped
    big, odisha = items
    assert big.url == "https://the-big-hack-2.devfolio.co/"
    assert (big.pay_max, big.pay_currency, big.deadline) == (125000.0, "INR", "2026-11-10")
    assert big.description.startswith("Location: Soladevanahalli, India")
    assert big.tags == []  # "No Restrictions" isn't a theme
    assert odisha.description.startswith("Location: Online") and odisha.pay_max == 10000.0


def test_ethglobal_upcoming_hackathons_only(fx):
    items = ethglobal.parse(fx("ethglobal.html"))
    by = {i.external_id: i for i in items}
    assert set(by) == {"mumbai", "ethonline2026", "lisbon2026"}  # no conference, no past events, no dupes
    assert by["mumbai"].description.startswith("Location: Mumbai, India")
    assert by["ethonline2026"].description.startswith("Location: Online")
    assert by["ethonline2026"].deadline == "2026-09-16"
    assert by["lisbon2026"].description.startswith("Location: Lisbon, Portugal")
    assert by["mumbai"].url == "https://ethglobal.com/events/mumbai"


def test_ethglobal_layout_change_returns_empty():
    assert ethglobal.parse("<html><h2>Something else</h2></html>") == []


def test_superteam_grants_parse(fx):
    items = superteam_grants.parse(fx("superteam_grants.json"))
    assert len(items) == 5  # missing slug skipped
    india = items[0]
    assert india.kind == "grant" and india.url == "https://superteam.fun/earn/grants/solana-foundation-india-grants"
    assert (india.pay_min, india.pay_max, india.pay_currency) == (None, 10000.0, "USDG")
    assert india.description.startswith("Location: India")
    assert superteam_grants.region_of("La Familia Spain Grants") == "Spain"
    assert superteam_grants.region_of("The Touching Grass Fund (UK)") == "UK"
    assert superteam_grants.region_of("Agentic Engineering Grants") == ""


# --- eligibility ---

def _ev(kind, loc, title="Some Hack", **kw):
    desc = f"Location: {loc}\n" if loc is not None else ""
    return Item(source="t", kind=kind, external_id=title + str(loc), title=title, description=desc, **kw)


def test_event_location_classes():
    assert location.classify(_ev("hackathon", "Online")) == (location.OPEN, "online")
    assert location.classify(_ev("hackathon", "Mumbai, India"))[0] == location.INDIA_APAC
    assert location.classify(_ev("hackathon", "Lisbon, Portugal")) == (location.ONSITE, "Lisbon, Portugal")
    assert location.classify(_ev("hackathon", "Kolkata, India | Online (hybrid)"))[0] == location.OPEN
    assert location.classify(_ev("grant", "USA")) == (location.RESTRICTED, "USA")
    assert location.classify(_ev("grant", "India"))[0] == location.INDIA_APAC
    assert location.classify(_ev("grant", None))[0] == location.UNKNOWN


def test_event_alert_lines():
    assert location.alert_line(_ev("hackathon", "Online")) == "📍 Online ✅"
    assert location.alert_line(_ev("hackathon", "Mumbai, India")).startswith("📍 In person, Mumbai, India ✅")
    assert location.alert_line(_ev("hackathon", "Lisbon, Portugal")) == "📍 In person, Lisbon, Portugal ❌"
    assert location.alert_line(_ev("grant", "USA")) == "📍 USA residents only ❌"
    assert "check the rules" in location.alert_line(_ev("grant", None))


# --- scoring ---

def _scored(items, today=TODAY):
    score.score_items(items, load_profile(), load_sources_config(), today=today)
    return {i.title: i for i in items}


def test_online_ai_hackathon_with_big_prize_alerts():
    it = _ev("hackathon", "Online", "PayPal AI Hackathon", pay_min=67500, pay_max=67500,
             pay_currency="USD", pay_unit="fixed", deadline="2026-11-12")
    it.description += "Themes: Machine Learning/AI, Fintech"
    s = _scored([it])["PayPal AI Hackathon"]
    assert s.score >= 70, s.score_reason
    assert "prize pool" in s.score_reason


def test_in_person_abroad_and_foreign_grants_sink():
    abroad = _ev("hackathon", "Lisbon, Portugal", "ETHGlobal Lisbon AI Hackathon", org="ETHGlobal",
                 pay_max=500000, pay_currency="USD")
    usa = _ev("grant", "USA", "Solana Foundation USA Grants", pay_max=10000, pay_currency="USDG")
    s = _scored([abroad, usa])
    assert s["ETHGlobal Lisbon AI Hackathon"].score <= 20
    assert s["Solana Foundation USA Grants"].score <= 20


def test_india_grant_beats_tiny_grant_and_fund_isnt_a_fund_role():
    big = _ev("grant", "India", "Solana Foundation India Grants", pay_max=10000, pay_currency="USDG")
    tiny = _ev("grant", "India", "The Touching Grass Fund (India)", pay_max=500, pay_currency="USDG")
    s = _scored([big, tiny])
    assert s["Solana Foundation India Grants"].score >= 60
    assert s["The Touching Grass Fund (India)"].score < 40
    assert "analyst/treasury" not in s["The Touching Grass Fund (India)"].score_reason


def test_deadline_penalties_and_off_theme_cap():
    soon = _ev("hackathon", "Online", "AI Agents Hack", pay_max=20000, pay_currency="USD", deadline="2026-11-06")
    later = _ev("hackathon", "Online", "AI Agents Hack 2", pay_max=20000, pay_currency="USD", deadline="2026-11-30")
    past = _ev("hackathon", "Online", "AI Agents Hack 3", pay_max=20000, pay_currency="USD", deadline="2026-11-01")
    off = _ev("hackathon", "Online", "Pottery Design Jam", pay_max=1000000, pay_currency="USD")
    s = _scored([soon, later, past, off])
    assert s["AI Agents Hack"].score == s["AI Agents Hack 2"].score - 15
    assert "deadline passed" in s["AI Agents Hack 3"].score_reason
    assert s["Pottery Design Jam"].score < 50  # big prize can't rescue an off-theme event


def test_prize_pools_are_not_rates():
    # $500 prize pool must not trigger the "pay below floor" job/gig rule
    it = _ev("hackathon", "Online", "AI Agent Hack", pay_max=500, pay_currency="USD", pay_unit="fixed")
    s = _scored([it])["AI Agent Hack"]
    assert "floor" not in s.score_reason and "small prize pool" in s.score_reason


def test_trusted_organiser_bonus():
    a = _ev("hackathon", "Online", "ETHOnline 2026", org="ETHGlobal")
    b = _ev("hackathon", "Online", "Random Online 2026", org="Somebody")
    a.description += "Themes: Ethereum"
    b.description += "Themes: Ethereum"
    s = _scored([a, b])
    assert s["ETHOnline 2026"].score == s["Random Online 2026"].score + 15


# --- alerts ---

def test_hackathon_and_grant_alert_format():
    h = _ev("hackathon", "Online", "PayPal AI Hackathon", org="PayPal", pay_min=67500, pay_max=67500,
            pay_currency="USD", pay_unit="fixed", deadline="2026-11-12", url="https://x.devpost.com/")
    h.score, h.score_reason = 78, "skills: ai"
    msg = format_alert(h)
    assert msg.startswith("🏆 Hackathon")
    assert "Prize pool: 67,500 USD | Deadline: 2026-11-12" in msg
    assert "/fixed" not in msg and "📍 Online ✅" in msg
    g = _ev("grant", "India", "Solana Foundation India Grants", pay_max=10000, pay_currency="USDG",
            url="https://superteam.fun/earn/grants/x")
    g.score, g.score_reason = 70, "themes: solana"
    gm = format_alert(g)
    assert gm.startswith("💰 Grant") and "Grant size: up to 10,000 USDG" in gm
    nopay = _ev("hackathon", "Online", "ETHOnline 2026")
    nopay.score = 60
    assert "Prize pool: not stated" in format_alert(nopay)
    assert "✅🏆 60" in format_digest([nopay])


# --- online-only hackathons ---

def test_only_online_hackathons_are_kept():
    from bot.main import keep
    cfg = {}  # default: online only
    assert keep(_ev("hackathon", "Online"), cfg)
    assert keep(_ev("hackathon", "Kolkata, India | Online (hybrid)"), cfg)
    assert not keep(_ev("hackathon", "Mumbai, India"), cfg)
    assert not keep(_ev("hackathon", "Lisbon, Portugal"), cfg)
    assert not keep(_ev("hackathon", "not stated"), cfg)
    assert keep(_ev("grant", "India"), cfg)  # grants and other kinds untouched
    assert keep(_ev("hackathon", "Mumbai, India"), {"hackathons_online_only": False})


def test_pipeline_drops_in_person_hackathons(monkeypatch, capsys, tmp_path):
    import bot.main as botmain

    class Src:
        NAME = "devpost"

        @staticmethod
        def fetch(cfg=None):
            return [_ev("hackathon", "Online", "Online AI Agents Hack", pay_max=60000, pay_currency="USD"),
                    _ev("hackathon", "Mumbai, India", "Mumbai AI Agents Hack", pay_max=60000, pay_currency="USD")]

    monkeypatch.setattr(botmain, "SOURCES", {"devpost": Src})
    monkeypatch.setattr(botmain, "DB_PATH", tmp_path / "leads.db")
    assert botmain.main(["--dry-run", "--top", "5"]) == 0
    out = capsys.readouterr().out
    assert "Online AI Agents Hack" in out and "Mumbai AI Agents Hack" not in out
