from bot.sources import (cryptocurrencyjobs, cryptojobslist, discourse, remoteok,
                         snapshot, superteam, telegram_channels)


def test_cryptocurrencyjobs_double_unescape(fx):
    items = cryptocurrencyjobs.parse(fx("cryptocurrencyjobs.xml"))
    assert len(items) == 2
    assert items[0].title == "Data Analyst & Researcher"
    assert items[0].kind == "job" and "Dune" in items[0].description
    assert "<p>" not in items[0].description


def test_cryptojobslist_cdata(fx):
    items = cryptojobslist.parse(fx("cryptojobslist.xml"))
    assert items[0].title == "Treasury Analyst - DeFi Fund"
    assert items[0].external_id == "cjl-123"


def test_remoteok_skips_legal_and_keeps_attribution(fx):
    items = remoteok.parse(fx("remoteok.json"))
    assert [i.external_id for i in items] == ["111", "112"]
    assert items[0].pay_min == 120000 and items[0].pay_unit == "year"
    assert "remoteok.com" in items[0].description
    assert items[1].pay_min is None and items[1].pay_unit == "unknown"


def test_superteam_open_only_and_agent_only(fx):
    items = superteam.parse(fx("superteam.json"))
    assert len(items) == 1
    it = items[0]
    assert it.url == "https://superteam.fun/earn/listing/tg-alert-bot"
    assert it.org == "Acme DAO" and it.pay_unit == "fixed" and it.kind == "gig"


def test_telegram_channel(fx):
    items = telegram_channels.parse(fx("telegram_channel.html"), "cryptojobslist")
    assert len(items) == 1
    assert items[0].external_id == "cryptojobslist/101"
    assert items[0].url == "https://t.me/cryptojobslist/101"
    assert items[0].title.startswith("Python Developer")


def test_telegram_garbage_returns_empty():
    assert telegram_channels.parse("<html>nothing</html>") == []
    assert telegram_channels.parse("") == []


def test_snapshot_keyword_filter(fx):
    items = snapshot.parse(fx("snapshot.json"))
    assert len(items) == 1 and items[0].org == "Aave" and items[0].kind == "lead"


def test_discourse(fx):
    items = discourse.parse(fx("discourse.json"), "gov.uniswap.org")
    assert len(items) == 1
    assert items[0].url == "https://gov.uniswap.org/t/rfp-analytics-dashboard/4321"
