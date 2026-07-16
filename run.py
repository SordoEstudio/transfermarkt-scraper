"""
MV Sports scraper — pipeline runner.

Usage
-----
  python run.py [command] [slug]

Commands
--------
  all              Scrape + enrich players and coaches, rebuild outputs  (default)
  players          Scrape + enrich all players, rebuild outputs
  coaches          Scrape + enrich all coaches, rebuild demo
  player <slug>    Re-enrich one player   (e.g. gabriel-rojas)
  coach  <slug>    Re-enrich one coach    (e.g. jorge-sampaoli)

For `player` / `coach`: the list files (mv_players.json / mv_coaches.json) must
exist. Run `players` or `coaches` first if they don't.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

PY = sys.executable
BASE = os.path.dirname(os.path.abspath(__file__))

AGENT_INPUT  = os.path.join(BASE, "mv_agent.json")
PLAYERS_LIST = os.path.join(BASE, "mv_players.json")
COACHES_LIST = os.path.join(BASE, "mv_coaches.json")
PLAYERS_RICH = os.path.join(BASE, "mv_players_rich.json")
COACHES_RICH = os.path.join(BASE, "mv_coaches_rich.json")

_env = {**os.environ, "PYTHONUTF8": "1"}


# ── helpers ──────────────────────────────────────────────────────────────────

def _run(*args, stdout=None):
    result = subprocess.run(list(args), env=_env, stdout=stdout, cwd=BASE)
    if result.returncode != 0:
        sys.exit(result.returncode)


def _crawl(crawler, input_path, output_path):
    print(f"  tfmkt {crawler} < {os.path.basename(input_path)} > {os.path.basename(output_path)}")
    with open(output_path, "w", encoding="utf-8") as out:
        _run(PY, "-m", "tfmkt", crawler, "-p", input_path, stdout=out)


def _crawl_item(crawler, item, output_path):
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(item, tmp, ensure_ascii=False)
        tmp_path = tmp.name
    try:
        _crawl(crawler, tmp_path, output_path)
    finally:
        os.unlink(tmp_path)


def _find_item(jsonl_path, slug, type_key):
    if not os.path.exists(jsonl_path):
        return None
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            href = item.get("href", "")
            item_slug = href.strip("/").split("/")[0]
            if item_slug == slug:
                return item
    return None


def _upsert_rich(rich_path, tmp_path):
    new_records = {}
    with open(tmp_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                new_records[r["code"]] = line.rstrip()

    lines = []
    if os.path.exists(rich_path):
        with open(rich_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                code = r.get("code")
                if code in new_records:
                    lines.append(new_records.pop(code))
                else:
                    lines.append(line.rstrip())

    for leftover in new_records.values():
        lines.append(leftover)

    with open(rich_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ── pipeline steps ────────────────────────────────────────────────────────────

def scrape_players():
    print(">> players list")
    _crawl("agents", AGENT_INPUT, PLAYERS_LIST)
    print(">> players enrich")
    _crawl("players_full", PLAYERS_LIST, PLAYERS_RICH)


def scrape_coaches():
    print(">> coaches list")
    _crawl("coaches", AGENT_INPUT, COACHES_LIST)
    print(">> coaches enrich")
    _crawl("coaches_full", COACHES_LIST, COACHES_RICH)


def build():
    print(">> demo.html")
    _run(PY, "build_demo.py")
    print(">> players.json (spec)")
    _run(PY, "generate_players_json.py")


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_all():
    scrape_players()
    scrape_coaches()
    build()


def cmd_players():
    scrape_players()
    build()


def cmd_coaches():
    scrape_coaches()
    print(">> demo.html")
    _run(PY, "build_demo.py")


def cmd_player(slug):
    item = _find_item(PLAYERS_LIST, slug, "player")
    if not item:
        print(f"slug '{slug}' not found in {PLAYERS_LIST}. Run `python run.py players` first.")
        sys.exit(1)
    print(f">> re-enriching player: {slug}")
    tmp = PLAYERS_RICH + ".tmp"
    _crawl_item("players_full", item, tmp)
    _upsert_rich(PLAYERS_RICH, tmp)
    os.unlink(tmp)


def cmd_coach(slug):
    item = _find_item(COACHES_LIST, slug, "coach")
    if not item:
        print(f"slug '{slug}' not found in {COACHES_LIST}. Run `python run.py coaches` first.")
        sys.exit(1)
    print(f">> re-enriching coach: {slug}")
    tmp = COACHES_RICH + ".tmp"
    _crawl_item("coaches_full", item, tmp)
    _upsert_rich(COACHES_RICH, tmp)
    os.unlink(tmp)


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="run.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=["all", "players", "coaches", "player", "coach"],
        help="Pipeline target (default: all)",
    )
    parser.add_argument(
        "slug",
        nargs="?",
        help="TM slug for `player` or `coach` commands",
    )
    args = parser.parse_args()

    if args.command in ("player", "coach") and not args.slug:
        parser.error(f"`{args.command}` requires a slug argument")

    dispatch = {
        "all":     cmd_all,
        "players": cmd_players,
        "coaches": cmd_coaches,
        "player":  lambda: cmd_player(args.slug),
        "coach":   lambda: cmd_coach(args.slug),
    }
    dispatch[args.command]()


if __name__ == "__main__":
    main()
