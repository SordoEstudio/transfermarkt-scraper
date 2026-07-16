"""Transform mv_players_rich.json (TM-verbatim) -> players.json per player_data_spec.md.

Output: a JSON array of spec-shaped records (camelCase, ISO dates, position enums,
derived metrics). Manual-enrichment fields (bio, scoutSummary, strengths, ...) are
left out — to be filled by the editor.
"""
import json
import re
from datetime import date

SRC = "mv_players_rich.json"
OUT = "players.json"

# TM English position label -> spec enum. Compound labels ("Defender - Centre-Back",
# "Midfield - Central Midfield") are normalised to the segment after " - " first.
POS_MAP = {
    "Goalkeeper": "goalkeeper",
    "Right-Back": "right-back",
    "Left-Back": "left-back",
    "Centre-Back": "center-back",
    "Sweeper": "center-back",
    "Defensive Midfield": "defensive-mid",
    "Central Midfield": "central-mid",
    "Attacking Midfield": "attacking-mid",
    "Right Midfield": "right-winger",
    "Left Midfield": "left-winger",
    "Right Winger": "right-winger",
    "Left Winger": "left-winger",
    "Centre-Forward": "striker",
    "Second Striker": "second-striker",
    # bare group fallbacks
    "Attack": "striker",
    "Midfield": "central-mid",
    "Defender": "center-back",
}


def map_pos(label):
    if not label:
        return None
    seg = label.split(" - ")[-1].strip()
    return POS_MAP.get(seg) or POS_MAP.get(label.strip())


def iso(d):
    """'31/12/2028' -> '2028-12-31'. Pass through anything that doesn't match."""
    if not d:
        return None
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", d.strip())
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else d


def height_cm(raw):
    if not raw:
        return None
    try:
        return round(float(raw.replace(",", ".").replace("m", "").strip()) * 100)
    except ValueError:
        return None


def to_int(s):
    if s is None:
        return None
    try:
        return int(str(s).replace(".", "").strip())
    except ValueError:
        return None


def season_label(season_id):
    """2025 -> '25/26'."""
    try:
        y = int(season_id)
    except (TypeError, ValueError):
        return str(season_id)
    return f"{y % 100:02d}/{(y + 1) % 100:02d}"


def first_name(name, last_name):
    if not name:
        return None
    if last_name and name.endswith(last_name):
        return name[: -len(last_name)].strip() or name
    return name


def tm_id(href):
    return href.rstrip("/").split("/")[-1] if href else None


def per90(num, minutes):
    if not minutes:
        return None
    return round(num / minutes * 90, 2)


def build_career(clubs_history, fallback_country):
    out = []
    ch = clubs_history or []
    for i, c in enumerate(ch):
        to = iso(ch[i + 1]["joined"]) if i + 1 < len(ch) else None
        out.append({
            "club": c.get("name"),
            "clubLogo": c.get("logo_url"),
            "country": fallback_country or "",   # per-club country not scraped
            "from": iso(c.get("joined")) or c.get("season"),
            **({"to": to} if to else {}),
        })
    return out


def transform(r):
    ct = r.get("career_totals") or {}
    minutes = ct.get("minutes") or 0
    goals = ct.get("goals") or 0
    assists = ct.get("assists") or 0
    pob = r.get("place_of_birth") or {}
    citizenship = r.get("citizenship")

    rec = {
        "id": r.get("code"),
        "slug": r.get("code"),
        "firstName": first_name(r.get("name"), r.get("last_name")),
        "lastName": r.get("last_name"),
        "dateOfBirth": iso(r.get("date_of_birth")),
        "placeOfBirth": {
            "city": pob.get("city"),
            "country": pob.get("country") or citizenship or "",
        },
        "citizenship": citizenship,
        "position": map_pos(r.get("position")),
        "currentClub": (r.get("current_club") or {}).get("name"),
        "currentClubLogo": (r.get("current_club") or {}).get("logo_url"),
        "careerTotals": {
            "appearances": ct.get("appearances", 0),
            "goals": goals,
            "assists": assists,
            "minutes": minutes,
        },
        "category": "professional",
        "featured": False,
        "active": True,
        "transfermarktId": tm_id(r.get("href")),
        "transfermarktUrl": f"https://www.transfermarkt.com.ar{(r.get('href') or '')}",
    }

    # Optional identity
    if r.get("full_name"):
        rec["fullName"] = r["full_name"]
    if to_int(r.get("shirt_number")) is not None:
        rec["shirtNumber"] = to_int(r["shirt_number"])
    if height_cm(r.get("height")) is not None:
        rec["height"] = height_cm(r["height"])
    if r.get("foot") in ("left", "right", "both"):
        rec["foot"] = r["foot"]
    if r.get("additional_citizenships"):
        rec["additionalCitizenships"] = r["additional_citizenships"]
    if map_pos(r.get("main_position")):
        rec["mainPosition"] = map_pos(r["main_position"])
    others = [map_pos(o) for o in (r.get("other_positions") or [])]
    others = [o for o in others if o]
    if others:
        rec["otherPositions"] = others

    # Contract / club
    if r.get("joined"):
        rec["joined"] = iso(r["joined"])
    if r.get("contract_expires"):
        rec["contractExpires"] = iso(r["contract_expires"])

    # Market value
    if r.get("current_market_value"):
        rec["currentMarketValue"] = r["current_market_value"]
    if r.get("market_value_last_update"):
        rec["marketValueLastUpdate"] = r["market_value_last_update"]

    # National team
    if r.get("national_team"):
        rec["nationalTeam"] = r["national_team"].get("country")
    if to_int(r.get("international_caps")) is not None:
        rec["internationalCaps"] = to_int(r["international_caps"])
    if to_int(r.get("international_goals")) is not None:
        rec["internationalGoals"] = to_int(r["international_goals"])

    if r.get("transfer_fee_sum"):
        rec["transferFeeSum"] = r["transfer_fee_sum"]

    # Honours / palmarés: [{title, count}]
    if r.get("achievements"):
        rec["achievements"] = [
            {"title": a.get("title"), "count": a.get("count", 1)}
            for a in r["achievements"] if a.get("title")
        ]

    # Career (clubs history)
    rec["career"] = build_career(r.get("clubs_history"), rec["placeOfBirth"]["country"])

    # Transfers
    transfers = []
    for t in (r.get("transfers") or []):
        transfers.append({
            "date": iso(t.get("date")),
            "season": t.get("season"),
            "fromClub": (t.get("from") or {}).get("name"),
            "toClub": (t.get("to") or {}).get("name"),
            **({"fee": t["fee"]} if t.get("fee") else {}),
            **({"marketValueAtTime": t["market_value"]} if t.get("market_value") else {}),
        })
    if transfers:
        rec["transfers"] = transfers

    # Stats by season (club per season not scraped -> omitted)
    sbs = []
    for s in (r.get("stats_by_season") or []):
        sbs.append({
            "seasonId": season_label(s.get("season_id")),
            "appearances": s.get("appearances", 0),
            "goals": s.get("goals", 0),
            "assists": s.get("assists", 0),
            "minutes": s.get("minutes", 0),
            "yellowCards": s.get("yellow_cards", 0),
        })
    if sbs:
        rec["statsBySeason"] = sbs

    # Derived metrics (spec section 4)
    rec["metrics"] = {
        "goalsPer90": per90(goals, minutes),
        "assistsPer90": per90(assists, minutes),
        "goalContributions": goals + assists,
        "goalContributionsPer90": per90(goals + assists, minutes),
        "seasonsActive": len(r.get("stats_by_season") or []),
        "clubsCount": len(r.get("clubs_history") or []),
        "minPerAppearance": round(minutes / ct["appearances"]) if ct.get("appearances") else None,
    }

    # Image (TM portrait; replace with official photo later)
    imgs = r.get("image_urls") or {}
    rec["image"] = imgs.get("big") or r.get("image_url")

    # Gallery: all action photos, keep `premium` flag so the front can filter.
    gallery = [
        {
            "title": g.get("title"),
            "url": g.get("url"),
            "source": g.get("source"),
            "premium": bool(g.get("premium")),
        }
        for g in (r.get("gallery") or [])
        if g.get("url")
    ]
    if gallery:
        rec["gallery"] = gallery

    return rec


def main():
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8") if l.strip()]
    out = [transform(r) for r in rows]
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    unmapped = sorted({
        r.get("position") for raw, r in zip(rows, out)
        if r["position"] is None and raw.get("position")
    } | {
        raw["position"] for raw in rows if raw.get("position") and not map_pos(raw["position"])
    })
    print(f"wrote {len(out)} players -> {OUT}")
    if unmapped:
        print("UNMAPPED positions:", unmapped)
    else:
        print("all positions mapped")


if __name__ == "__main__":
    main()
