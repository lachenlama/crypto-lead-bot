"""One-off helper: find working ATS board tokens for watchlist companies that 404.
Usage: python scripts/probe_ats.py   (prints NAME -> ats/token count for every hit)"""
import re

import httpx
import yaml

URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{t}/jobs",
    "lever": "https://api.lever.co/v0/postings/{t}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{t}",
}
EXTRA = {
    "Chainalysis": ["chainalysis", "chainalysisinc"], "Gauntlet": ["gauntlet", "gauntletnetworks"],
    "Galaxy": ["galaxy", "galaxydigitalservices", "galaxydigital"], "Wintermute": ["wintermute", "wintermutetrading"],
    "Circle": ["circle", "circleinternet", "circle-internet-financial"], "Uniswap Labs": ["uniswap", "uniswaplabs"],
    "Alchemy": ["alchemy", "alchemyinsights"], "Chainlink Labs": ["chainlink", "chainlinklabs", "smartcontract"],
    "Offchain Labs": ["offchainlabs", "offchain", "arbitrum"], "OP Labs": ["oplabs", "optimism", "op-labs"],
    "Eigen Labs": ["eigenlabs", "eigenlayer", "eigen"], "Polygon Labs": ["polygon", "polygonlabs", "polygontechnology"],
    "Lido": ["lido", "lidofinance", "lido-finance"], "Coin Metrics": ["coinmetrics", "coin-metrics"],
    "Flipside": ["flipside", "flipsidecrypto", "flipside-crypto"], "Surge AI": ["surgeai", "surge", "surgehq"],
    "DataAnnotation": ["dataannotation", "data-annotation"], "Micro1": ["micro1", "micro-1"],
    "Prolific": ["prolific", "prolificac"], "Appen": ["appen"], "Ledger": ["ledger", "ledgerhq"],
    "Token Terminal": ["tokenterminal", "token-terminal"], "Chaos Labs": ["chaoslabs", "chaos-labs", "chaos"],
    "karpatkey": ["karpatkey"], "LlamaRisk": ["llamarisk", "llama-risk"], "Ethena": ["ethena", "ethenalabs", "ethena-labs"],
    "Aave Labs": ["aave", "aavelabs", "aave-labs", "avara"], "Zerion": ["zerion"], "Kaiko": ["kaiko"],
    "Sepal AI": ["sepal", "sepalai", "sepal-ai"], "Datacurve": ["datacurve", "data-curve"],
}


def variants(name):
    base = re.sub(r"\(.*?\)", "", name).split("/")[0].strip().lower()
    out = {base.replace(" ", ""), base.replace(" ", "-"), base.replace(" ", "") + "labs", base.replace(" ", "") + "hq"}
    return list(dict.fromkeys(EXTRA.get(name, []) + sorted(out)))


def main():
    wl = yaml.safe_load(open("config/watchlist.yaml"))
    with httpx.Client(timeout=15, headers={"User-Agent": "Mozilla/5.0"}) as c:
        for co in wl["companies"]:
            try:
                r = c.get(URLS[co["ats"]].format(t=co["token"]))
                if r.status_code == 200:
                    continue
            except Exception:
                pass
            hits = []
            for t in variants(co["name"]):
                for ats, url in URLS.items():
                    try:
                        r = c.get(url.format(t=t))
                    except Exception:
                        continue
                    if r.status_code == 200:
                        d = r.json()
                        n = len(d) if isinstance(d, list) else len(d.get("jobs", []))
                        hits.append(f"{ats}/{t}:{n}")
            print(f"PROBE {co['name']} -> {', '.join(hits) or 'none'}")


if __name__ == "__main__":
    main()
