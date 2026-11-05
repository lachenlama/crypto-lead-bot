"""Source registry. Each module exposes NAME and fetch(cfg) -> list[Item]."""
from . import (
    cryptocurrencyjobs,
    cryptojobslist,
    devfolio,
    devpost,
    discourse,
    ethglobal,
    remoteok,
    snapshot,
    superteam,
    superteam_grants,
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
        # hackathons and grants (v1.3)
        devpost,
        devfolio,
        ethglobal,
        superteam_grants,
    )
}
