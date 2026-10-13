"""Location eligibility for an owner based in India (IST, UTC+5:30) who prefers US/EU/UK remote work.

classify(item) -> (status, label). Statuses:
  open (worldwide remote) | remote_west (remote, US/EU/UK/Canada only) | india_apac |
  contract_ok | restricted (remote, other non-West region) | onsite | unknown.
Purely a filter on eligibility: it reads the job's stated location, never anything about the owner.
"""
from __future__ import annotations

import re

from .models import Item

OPEN, REMOTE_WEST, INDIA_APAC = "open", "remote_west", "india_apac"
CONTRACT_OK, RESTRICTED, ONSITE, UNKNOWN = "contract_ok", "restricted", "onsite", "unknown"
OWNER_OFFSET = 5.5

INDIA_CITIES = [
    "india", "bengaluru", "bangalore", "mumbai", "delhi", "new delhi", "ncr", "gurugram", "gurgaon",
    "noida", "hyderabad", "pune", "chennai", "kolkata", "ahmedabad",
]
WORLD_WORDS = ["worldwide", "world-wide", "anywhere", "global", "globally"]
INDIA_WORDS = ["apac", "asia", "asia-pacific", "asia pacific"] + INDIA_CITIES
WORLD_RE = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(w) for w in WORLD_WORDS) + r")(?![a-z0-9])", re.I)
INDIA_RE = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(w) for w in INDIA_WORDS) + r")(?![a-z0-9])", re.I)

# remote roles limited to a place are "remote_west" unless the place is NONWEST (then "restricted")
WEST_EXPLICIT = ["north america", "united states", "usa", "u.s.", "u.s.a.", "canada", "uk", "united kingdom",
                 "eu", "european union", "eea", "east coast us", "west coast us", "us/canada"]
NONWEST = [
    "emea", "middle east", "africa", "mena", "latam", "latin america", "south america", "amer", "americas", "cis",
    "mexico", "brazil", "argentina", "colombia", "chile", "peru", "turkey", "israel", "united arab emirates", "uae",
    "saudi arabia", "qatar", "bahrain", "egypt", "nigeria", "kenya", "south africa", "japan", "south korea",
    "korea", "china", "taiwan", "hong kong", "singapore", "malaysia", "indonesia", "thailand", "vietnam",
    "philippines", "australia", "new zealand", "pakistan", "bangladesh", "sri lanka", "nepal", "georgia",
    "armenia", "mexico city", "sao paulo", "buenos aires", "bogota", "santiago", "lima", "dubai", "abu dhabi",
    "doha", "riyadh", "istanbul", "cairo", "lagos", "nairobi", "cape town", "tokyo", "seoul", "shanghai",
    "beijing", "shenzhen", "taipei", "kuala lumpur", "jakarta", "bangkok", "ho chi minh", "hanoi", "manila",
    "sydney", "melbourne", "auckland", "karachi", "dhaka", "tel aviv",
]
ANY_RE = re.compile(r"^\s*any\b", re.I)  # "Any, Transcription"
IST_RE = re.compile(r"\bIST\b")  # case-sensitive: the word "ist" is noise
UTC_RE = re.compile(r"(?:UTC|GMT)\s*([+\-−])\s*(\d{1,2})(?::?(\d{2}))?", re.I)

REMOTE_RE = re.compile(r"(?<![a-z])remote(?![a-z])", re.I)
HYBRID_RE = re.compile(r"hybrid", re.I)
CONTRACT_RE = re.compile(
    r"(?<![a-z])(freelance|freelancer|contractor|contractors|contract|bounty|gig)(?![a-z])", re.I
)
CONTRACT_DESC_RE = re.compile(
    r"contract (?:role|position|basis|opportunity)|independent contractor|freelance|contractor|"
    r"6[- ]month contract|short[- ]term contract",
    re.I,
)

# --- places (lowercase; short codes are matched case-sensitively) ---
REGIONS = [
    "european union", "europe", "emea", "eea", "north america", "south america", "latam",
    "latin america", "amer", "americas", "middle east", "africa", "east coast us", "west coast us",
    "eu", "us/canada", "nordics", "dach", "benelux", "mena", "cis",
]
REGION_CODES = {"EU", "EEA", "EMEA", "LATAM", "AMER", "MENA", "NA"}
COUNTRIES = [
    "united states", "usa", "u.s.", "u.s.a.", "canada", "mexico", "brazil", "argentina", "colombia", "chile",
    "peru", "united kingdom", "great britain", "england", "scotland", "ireland", "germany", "france",
    "spain", "portugal", "italy", "netherlands", "belgium", "switzerland", "austria", "poland",
    "romania", "estonia", "latvia", "lithuania", "finland", "sweden", "norway", "denmark", "czechia",
    "czech republic", "hungary", "bulgaria", "serbia", "croatia", "greece", "turkey", "ukraine",
    "israel", "united arab emirates", "uae", "saudi arabia", "qatar", "bahrain", "egypt", "nigeria",
    "kenya", "south africa", "japan", "south korea", "korea", "china", "taiwan", "hong kong",
    "singapore", "malaysia", "indonesia", "thailand", "vietnam", "philippines", "australia",
    "new zealand", "pakistan", "bangladesh", "sri lanka", "nepal", "georgia", "armenia", "cyprus",
    "malta", "luxembourg", "slovenia", "slovakia", "iceland",
]
COUNTRY_CODES = {"US", "UK", "USA", "UAE", "MX", "CA"}
CITIES = [
    "new york", "nyc", "san francisco", "bay area", "los angeles", "seattle", "austin", "boston", "chicago",
    "miami", "denver", "dallas", "houston", "atlanta", "washington", "philadelphia", "portland",
    "minneapolis", "st. louis", "honolulu", "omaha", "colorado springs", "palo alto", "san jose",
    "san diego", "toronto", "vancouver", "montreal", "london", "manchester", "edinburgh", "dublin",
    "paris", "berlin", "munich", "amsterdam", "zurich", "zug", "geneva", "lisbon", "madrid",
    "barcelona", "milan", "rome", "vienna", "warsaw", "bucharest", "tallinn", "stockholm",
    "copenhagen", "oslo", "helsinki", "prague", "budapest", "belgrade", "tel aviv", "dubai",
    "abu dhabi", "doha", "riyadh", "istanbul", "cairo", "lagos", "nairobi", "cape town", "tokyo",
    "seoul", "shanghai", "beijing", "shenzhen", "taipei", "kuala lumpur", "jakarta", "bangkok",
    "ho chi minh", "hanoi", "manila", "sydney", "melbourne", "auckland", "karachi", "dhaka",
    "mexico city", "sao paulo", "buenos aires", "bogota", "santiago", "lima",
    "texas", "california", "florida", "new jersey", "virginia", "massachusetts", "colorado",
    "illinois", "georgia, usa",
]
US_STATES = (
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM "
    "NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC"
).split()
STATE_RE = re.compile(r",\s*(?:" + "|".join(US_STATES) + r")\b")


def _word_re(words: list[str]) -> re.Pattern:
    return re.compile(
        r"(?<![a-z0-9])(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")(?![a-z0-9])",
        re.I,
    )


REGION_RE, COUNTRY_RE, CITY_RE = _word_re(REGIONS), _word_re(COUNTRIES), _word_re(CITIES)
NONWEST_RE, WEST_RE = _word_re(NONWEST), _word_re(WEST_EXPLICIT)
CODE_RE = re.compile(r"(?<![A-Za-z])(" + "|".join(sorted(REGION_CODES | COUNTRY_CODES, key=len, reverse=True)) + r")(?![A-Za-z])")


def _place_level(seg: str) -> str | None:
    """'region' | 'country' | 'city' | None for a single location segment."""
    if REGION_RE.search(seg):
        return "region"
    for m in CODE_RE.finditer(seg):
        if m.group(1) in REGION_CODES:
            return "region"
    if CITY_RE.search(seg) or STATE_RE.search(seg):
        # "Paris, France" / "Poland" -> a bare country name is country level; cities win otherwise
        return "city"
    if COUNTRY_RE.search(seg) or any(m.group(1) in COUNTRY_CODES for m in CODE_RE.finditer(seg)):
        return "country"
    return None


def _utc_range(text: str) -> tuple[float, float] | None:
    offs = []
    for sign, h, m in UTC_RE.findall(text):
        v = int(h) + (int(m) / 60 if m else 0)
        offs.append(-v if sign in "-−" else v)
    if len(offs) >= 2:
        return min(offs), max(offs)
    return None


def _clean_label(seg: str) -> str:
    s = re.sub(r"\((?:remote|hybrid)\)", "", seg, flags=re.I)
    s = re.sub(r"(?<![a-z])(remote|hybrid)(?![a-z])", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" -–,;:()|")
    return s


def is_west(label: str) -> bool:
    """True when a place label is US / EU / EEA / UK / Canada / Europe (or a city there)."""
    codes = {m.group(1) for m in CODE_RE.finditer(label)}
    if WEST_RE.search(label) or codes & {"US", "UK", "USA", "EU", "EEA", "NA", "CA"}:
        return True
    return not (NONWEST_RE.search(label) or codes & {"UAE", "EMEA", "LATAM", "AMER", "MENA", "MX"})


def _segment(seg: str) -> tuple[str, str]:
    """Classify one location segment -> (kind, label). kind: open | india | remote_place |
    remote_bare | region_only | place_only | unknown."""
    seg = seg.strip()
    if not seg:
        return "unknown", ""
    if WORLD_RE.search(seg) or ANY_RE.search(seg):
        return "open", "worldwide"
    rng = _utc_range(seg)
    if rng:
        if rng[0] <= OWNER_OFFSET <= rng[1]:
            return "india", _clean_label(seg)
        return "remote_place", _clean_label(seg)
    if INDIA_RE.search(seg) or IST_RE.search(seg):
        return "india", _clean_label(seg) or "India/APAC"
    for sign, h, m in UTC_RE.findall(seg):
        if sign == "+" and int(h) == 5 and m == "30":
            return "india", "UTC+5:30"
    remote = bool(REMOTE_RE.search(seg)) and not HYBRID_RE.search(seg)
    level = _place_level(seg)
    label = _clean_label(seg)
    if level is None:
        return ("remote_bare", "") if remote else ("unknown", label)
    if remote:
        return "remote_place", label
    if level == "region":
        return "region_only", label
    return "place_only", label


# text-mode signals for sources with no Location line (job-board RSS, Superteam, DAO leads)
TEXT_OPEN_RE = re.compile(
    r"work(?:ing)? (?:remotely )?from anywhere|anywhere in the world|"
    r"remote[^.\n]{0,15}(?:worldwide|anywhere|global)(?! in (?:north america|the (?:us|u\.s|united|eu|uk)|europe))|"
    r"(?:worldwide|global|anywhere)[^.\n]{0,15}remote|"
    r"location\W{1,3}(?:anywhere|worldwide|global)",
    re.I,
)
TEXT_INDIA_RE = re.compile(r"remote[^.\n]{0,15}(?:apac|asia|india)|(?:apac|asia|india)[^.\n]{0,15}remote", re.I)
PLACE = r"(united states|usa|u\.s\.a?\.?|us|uk|united kingdom|eu|european union|europe|eea|emea|canada|north america|latam)"
TEXT_RESTRICT_RES = [
    re.compile(r"remote\s*[-(,/]\s*" + PLACE + r"\b", re.I),
    re.compile(PLACE + r"[- ]?(?:only|based only|residents only)", re.I),
    re.compile(r"(?i:must) (?:be )?(?:authori[sz]ed|eligible|legally able) to work in (?:the )?([A-Z][\w .]{1,30})"),
    re.compile(r"(?i:must) (?:reside|live|be located|be based|be resident) in (?:the )?([A-Z][\w .]{1,30})"),
]


def _text_mode(item: Item, text: str) -> tuple[str, str]:
    if rng := _utc_range(text):
        label = f"UTC{rng[0]:+g} to UTC{rng[1]:+g}"
        return (INDIA_APAC if rng[0] <= OWNER_OFFSET <= rng[1] else RESTRICTED), label
    if TEXT_OPEN_RE.search(text):
        return OPEN, "worldwide"
    if IST_RE.search(text) or TEXT_INDIA_RE.search(text):
        return INDIA_APAC, "India/APAC"
    t = INDIA_RE.search(item.title)
    if t:
        return INDIA_APAC, t.group(1)
    for rx in TEXT_RESTRICT_RES:
        m = rx.search(text)
        if m:
            label = m.group(1).strip(" .")
            return (REMOTE_WEST if is_west(label) else RESTRICTED), label
    return UNKNOWN, ""


def _location_text(item: Item) -> tuple[str, str]:
    """(explicit Location: line or '', title + remaining description)."""
    desc = item.description or ""
    loc = ""
    if desc.startswith("Location:"):
        first, _, rest = desc.partition("\n")
        loc = first[len("Location:"):].strip()
        desc = rest
    return loc, f"{item.title}\n{desc}"


def _is_contract(item: Item, loc: str, text: str) -> bool:
    if item.kind == "gig":
        return True
    if CONTRACT_RE.search(item.title) or CONTRACT_RE.search(loc):
        return True
    if any(t.lower() in ("contract", "freelance", "contractor", "bounty") for t in item.tags):
        return True
    return bool(CONTRACT_DESC_RE.search(text))


def classify(item: Item) -> tuple[str, str]:
    loc, text = _location_text(item)
    contract = _is_contract(item, loc, text)
    segs = [_segment(s) for s in re.split(r"[;|]", loc) if s.strip()] if loc else []
    kinds = {k for k, _ in segs}
    lab = lambda *ks: next((l for k, l in segs if k in ks and l), "")  # noqa: E731

    if "open" in kinds:
        return OPEN, "worldwide"
    if "india" in kinds:
        return INDIA_APAC, lab("india")
    placed = [(k, l) for k, l in segs if k in ("remote_place", "region_only", "place_only")]
    if not placed:
        return _text_fallback(item, text, loc, contract)
    remote_placed = [l for k, l in placed if k == "remote_place"]
    west_remote = [l for l in remote_placed if is_west(l)]
    west_region = [l for k, l in placed if k == "region_only" and is_west(l)]
    cities = [l for k, l in placed if k == "place_only"]
    only_cities = [l for l in cities if _place_level(l) == "city"]
    if contract and (remote_placed or not only_cities):
        return CONTRACT_OK, "; ".join(l for _, l in placed[:2])
    if west_remote or west_region:
        return REMOTE_WEST, "; ".join((west_remote + west_region)[:2])
    if remote_placed:
        return RESTRICTED, "; ".join(remote_placed[:2])
    if "remote_bare" in kinds:
        return _text_fallback(item, text, loc, contract)
    if any(k == "region_only" for k, _ in placed):
        return RESTRICTED, lab("region_only")
    return ONSITE, "; ".join(cities[:2])


def _text_fallback(item: Item, text: str, loc: str, contract: bool) -> tuple[str, str]:
    status, label = _text_mode(item, text)
    if status in (RESTRICTED, REMOTE_WEST) and contract:
        return CONTRACT_OK, label
    return status, label


def alert_line(item: Item) -> str:
    status, label = classify(item)
    if status == OPEN:
        return "📍 Remote, worldwide ✅"
    if status == REMOTE_WEST:
        return f"📍 Remote, {label} ✅ (check if they hire from India or via contractor/EOR)"
    if status == INDIA_APAC:
        return "📍 India/APAC"
    if status == CONTRACT_OK:
        return f"📍 Contractor role in {label}: check they accept India ⚠️"
    if status == RESTRICTED:
        return f"📍 {label} only ❌"
    if status == ONSITE:
        return f"📍 Onsite {label} ❌"
    return "📍 Location not stated ❔"


STATUS_EMOJI = {OPEN: "✅", REMOTE_WEST: "✅", INDIA_APAC: "🇮🇳", CONTRACT_OK: "⚠️",
                RESTRICTED: "❌", ONSITE: "❌", UNKNOWN: "❔"}


def emoji(item: Item) -> str:
    return STATUS_EMOJI[classify(item)[0]]
