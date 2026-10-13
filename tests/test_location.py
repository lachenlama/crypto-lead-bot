import pytest

from bot import location, score, telegram
from bot.config import load_profile
from bot.models import Item


def mk(loc=None, **kw):
    d = dict(source="watchlist", kind="job", external_id="1", title="Data Analyst", org="Acme", url="http://u")
    d.update(kw)
    if loc is not None:
        d["description"] = f"Location: {loc}\n" + d.get("description", "")
    return Item(**d)


@pytest.mark.parametrize("loc,status", [
    ("Global - Remote", "open"),
    ("Any, Transcription", "open"),
    ("Anywhere (remote)", "open"),
    ("Bengaluru, India", "india_apac"),
    ("Remote - APAC", "india_apac"),
    ("Mumbai", "india_apac"),
    ("Estonia - Remote; India - Remote; South Africa - Remote", "india_apac"),
    ("United States - Remote (remote)", "remote_west"),
    ("Remote - UK", "remote_west"),
    ("Poland (remote)", "remote_west"),
    ("European Union", "remote_west"),
    ("Brazil - Remote", "restricted"),
    ("LATAM", "restricted"),
    ("Europe, Middle East, Africa (EMEA) (remote)", "restricted"),
    ("New York City", "onsite"),
    ("London", "onsite"),
    ("San Francisco, CA; New York, NY", "onsite"),
    ("New York City, NY (Hybrid)", "onsite"),
    ("Remote (remote)", "unknown"),
    ("Mercor HQ, 181 Fremont Street", "unknown"),
])
def test_classify_location_line(loc, status):
    assert location.classify(mk(loc))[0] == status


def test_contract_ok_and_labels():
    st, label = location.classify(mk("European Union", title="Freelance Data Analyst"))
    assert st == "contract_ok" and label == "European Union"
    assert location.classify(mk("United States", kind="gig"))[0] == "contract_ok"
    assert location.classify(mk("New York City", title="Contract Analyst"))[0] == "onsite"
    assert location.classify(mk("New York City"))[1] == "New York City"


def test_text_signals_and_timezones():
    assert location.classify(mk(description="Work remotely from anywhere."))[0] == "open"
    assert location.classify(mk(description="Timezone: UTC-3 to UTC+8"))[0] == "india_apac"
    assert location.classify(mk(description="Overlap with UTC-8 to UTC-5 required"))[0] == "restricted"
    assert location.classify(mk(description="Must be authorized to work in the United States"))[0] == "remote_west"
    assert location.classify(mk(description="Fully remote, anywhere in North America"))[0] != "open"
    assert location.classify(mk())[0] == "unknown"


def test_relocation_does_not_save_onsite():
    it = mk("London", description="Visa sponsorship and relocation offered")
    assert location.classify(it)[0] == "onsite"


def _score(it):
    score.score_items([it], load_profile())
    return it.score


def test_score_bonus_and_caps():
    p = load_profile()
    base = score.rule_score(mk(title="Python Developer"), p)[0]
    assert _score(mk("Global - Remote", title="Python Developer")) == base + 10
    assert _score(mk("United States - Remote", title="Python Developer")) == base + 10
    assert _score(mk("Bengaluru, India", title="Python Developer")) == base
    assert _score(mk("Remote", title="Python Developer")) == base  # no place
    assert _score(mk("Brazil - Remote", title="Python Developer")) == 45
    assert _score(mk("New York City", title="Python Developer")) == 30
    assert _score(mk("London", title="Python Developer", description="relocation offered")) == 30
    assert _score(mk("European Union", title="Freelance Python Developer")) == score.rule_score(
        mk("European Union", title="Freelance Python Developer"), p)[0] + 5


def test_gigs_and_leads_not_capped():
    for kind in ("gig", "lead"):
        it = mk("New York City", kind=kind, title="Python Developer")
        assert _score(it) == score.rule_score(it, load_profile())[0]


def test_alert_lines_and_digest_emoji():
    cases = {
        "Global - Remote": "📍 Remote, worldwide ✅",
        "United States - Remote": "📍 Remote, United States ✅ (check if they hire from India or via contractor/EOR)",
        "Bengaluru, India": "📍 India/APAC",
        "Brazil - Remote": "📍 Brazil only ❌",
        "New York City": "📍 Onsite New York City ❌",
    }
    for loc, line in cases.items():
        assert line in telegram.format_alert(mk(loc, score=80))
    assert "📍 Location not stated ❔" in telegram.format_alert(mk(score=80))
    c = mk("European Union", title="Freelance Analyst", score=80)
    assert "📍 Contractor role in European Union: check they accept India ⚠️" in telegram.format_alert(c)
    assert "✅" in telegram.format_digest([mk("Global - Remote", score=55)])
    assert "❌" in telegram.format_digest([mk("New York City", score=55)])
