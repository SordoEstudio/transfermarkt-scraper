"""Build demo.html: merge players + coaches into the template.

Reads mv_players_rich.json and mv_coaches_rich.json (JSONL), tags records
with _kind and category, and injects the merged list into the
demo_template.html `/*__DATA__*/` placeholder.
"""
import json
import re

# Youth players as informed by the agency (TM slug from href, e.g. /slug/profil/spieler/<id>)
YOUTH_SLUGS = {
    "bautista-andrade",
    "axel-borja",
    "lautaro-fernandez",
    "elias-sapaya",
    "tomas-moreno",
    "santiago-ledesma",
}


def _slug(player):
    href = player.get("href") or ""
    parts = href.strip("/").split("/")
    return parts[0] if parts else ""

PLAYERS = "mv_players_rich.json"
COACHES = "mv_coaches_rich.json"
TEMPLATE = "demo_template.html"
OUT = "demo.html"


def load_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main():
    players = load_jsonl(PLAYERS)
    for p in players:
        p["_kind"] = "player"
        p["category"] = "youth" if _slug(p) in YOUTH_SLUGS else "professional"

    coaches = load_jsonl(COACHES)
    for c in coaches:
        c["_kind"] = "coach"

    data = players + coaches
    payload = json.dumps(data, ensure_ascii=False)

    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()

    html = re.sub(
        r"/\*__DATA__\*/.*?/\*__END__\*/",
        lambda _: "/*__DATA__*/" + payload + "/*__END__*/",
        html,
        count=1,
        flags=re.DOTALL,
    )

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)

    cats = {}
    for p in players:
        cats[p["category"]] = cats.get(p["category"], 0) + 1
    print(f"players={len(players)} coaches={len(coaches)} categories={cats}")


if __name__ == "__main__":
    main()
