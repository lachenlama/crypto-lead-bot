import json

from bot import scam, score, telegram
from bot import db
from bot.config import load_profile
from bot.models import Item


def mk(**kw):
    d = dict(source="s", kind="job", external_id="1", title="t")
    d.update(kw)
    return Item(**d)


def test_key_uses_external_id_or_url():
    assert mk().key == mk(url="http://x").key
    assert mk(external_id="", url="a").key != mk(external_id="", url="b").key
    assert mk(source="a").key != mk(source="b").key


def test_description_truncated():
    assert len(mk(description="x" * 5000).description) == 2000


def test_scam_rules():
    assert scam.check(mk(description="Please download and run this file"))
    assert scam.check(mk(description="Clone the repo and run the script"))
    assert scam.check(mk(description="You must pay a fee to start"))
    assert scam.check(mk(description="Purchase our starter kit"))
    assert scam.check(mk(description="DM on telegram to apply"))
    assert not scam.check(mk(org="Acme", description="DM on telegram to apply"))
    assert not scam.check(mk(org="Acme", description="Build dashboards in Python"))
    assert scam.check(mk(kind="gig", org="", pay_max=50000, pay_currency="USDC"))
    assert not scam.check(mk(kind="gig", org="Acme", pay_max=50000, pay_currency="USDC"))


def test_score_rules():
    p = load_profile()
    good, _ = score.rule_score(mk(title="Python on-chain analytics dashboard dev",
                                  description="Telegram bot, Dune"), p)
    bad, _ = score.rule_score(mk(title="Sales Manager", description="business development"), p)
    assert good > 50 > bad
    ana, _ = score.rule_score(mk(title="Treasury Analyst"), p)
    plain, _ = score.rule_score(mk(title="Office Person"), p)
    assert ana > plain
    aud, _ = score.rule_score(mk(title="Solidity Auditor", description="solidity"), p)
    sol, _ = score.rule_score(mk(title="Solidity Developer", description="solidity"), p)
    assert aud < sol
    lo, _ = score.rule_score(mk(title="Python dev", pay_min=10, pay_max=20, pay_unit="hour", pay_currency="USD"), p)
    hi, _ = score.rule_score(mk(title="Python dev", pay_min=100, pay_max=150, pay_unit="hour", pay_currency="USD"), p)
    assert hi > lo
    assert 0 <= lo <= 100 and 0 <= hi <= 100


def test_dedupe_db(tmp_path):
    conn = db.connect(tmp_path / "x.db")
    it = mk(pay_min=1, pay_max=2, pay_unit="fixed")
    db.save_item(conn, it)
    conn.commit()
    assert it.key in db.existing_keys(conn)
    assert conn.execute("select count(*) from pay_observations").fetchone()[0] == 1
    assert db.existing_keys(None) == set()


def test_split_message():
    assert telegram.split_message("short") == ["short"]
    text = "\n".join("line %d " % i + "x" * 100 for i in range(200))
    parts = telegram.split_message(text)
    assert len(parts) > 1 and all(len(p) <= 4096 for p in parts)
    assert "\n".join(parts) == text
    assert all(len(p) <= 4096 for p in telegram.split_message("y" * 10000))


def test_format_alert_escapes_and_warns():
    it = mk(title="A <b> & B", org="O", url="http://u", score=80, score_reason="why",
            scam_flags=["pay a fee"], pitch="Hello <script>" * 600)
    out = telegram.format_alert(it)
    assert "&lt;b&gt;" in out and "⚠️" in out and "<blockquote>" in out
    assert len(out) <= 4096
