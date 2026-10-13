"""One-off: find ATS board tokens for watchlist companies that 404."""
import re, httpx, yaml
URLS = {"greenhouse": "https://boards-api.greenhouse.io/v1/boards/{t}/jobs",
        "lever": "https://api.lever.co/v0/postings/{t}?mode=json",
        "ashby": "https://api.ashbyhq.com/posting-api/job-board/{t}"}
EXTRA = {"CoinDCX": ["coindcx", "coin-dcx"], "CoinSwitch": ["coinswitch", "coinswitchkuber", "coinswitch-kuber"],
 "Delta Exchange": ["delta", "deltaexchange", "delta-exchange"], "Mudrex": ["mudrex"],
 "Biconomy": ["biconomy"], "Push Protocol": ["push", "pushprotocol", "push-protocol", "epns"],
 "Router Protocol": ["routerprotocol", "router-protocol", "router"], "OKX": ["okx", "okxglobal", "okex"],
 "Bybit": ["bybit", "bybitglobal"], "KuCoin": ["kucoin"], "Animoca Brands": ["animocabrands", "animoca", "animoca-brands"],
 "Matrixport": ["matrixport"], "HashKey": ["hashkey", "hashkeygroup", "hashkey-group"], "Crypto.com": ["crypto", "cryptocom", "crypto-com"],
 "Bitget": ["bitget"], "Ava Labs": ["avalabs", "ava-labs", "avalanche"], "Sei": ["sei", "seilabs", "sei-labs", "seifoundation"],
 "Mysten Labs (Sui)": ["mystenlabs", "mysten-labs", "mysten", "sui"], "Celestia": ["celestia", "celestialabs", "celestia-labs"],
 "Wormhole": ["wormhole", "wormholefoundation", "wormhole-foundation", "wormholelabs"], "LayerZero": ["layerzero", "layerzerolabs", "layerzero-labs"],
 "Near Foundation": ["near", "nearfoundation", "near-foundation", "nearone"]}
def main():
    with httpx.Client(timeout=15, headers={"User-Agent": "Mozilla/5.0"}) as c:
        for name, toks in EXTRA.items():
            hits = []
            for t in toks:
                for ats, url in URLS.items():
                    try: r = c.get(url.format(t=t))
                    except Exception: continue
                    if r.status_code == 200:
                        d = r.json(); n = len(d) if isinstance(d, list) else len(d.get("jobs", []))
                        hits.append(f"{ats}/{t}:{n}")
            print(f"PROBE {name} -> {', '.join(hits) or 'none'}")
main()
