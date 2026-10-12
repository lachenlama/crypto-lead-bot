"""Source registry. Each module exposes NAME and fetch(cfg) -> list[Item]."""
from . import (
    cryptocurrencyjobs,
    cryptojobslist,
    discourse,
    remoteok,
    snapshot,
    superteam,
    telegram_channels,
    watchlist,
    web3career,
)

SOURCES = {
    m.NAME: m
    for m in (
        cryptocurrencyjobs,
        cryptojobslist,
        remoteok,
        superteam,
        telegram_channels,
        snapshot,
        discourse,
        watchlist,
        web3career,
    )
}
