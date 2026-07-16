"""Enriched player crawler.

For every input `player` item it fetches several Transfermarkt sources and merges
them into a single rich JSON record:

  - profile page          -> bio, positions, market value, league
  - transferHistory API   -> transfer history
  - performance-game API   -> per-season aggregated stats + career totals
  - injuries page          -> injury history
  - erfolge page           -> honours / palmarés ([{title, count}])
  - gallery API            -> action photos

Input (one JSON object per line):
    {"type":"player","href":"/gabriel-rojas/profil/spieler/471639"}
"""
import json
import logging
import re
from collections import OrderedDict
from urllib.parse import unquote, urlparse

from crawlee import Request
from crawlee.crawlers import ParselCrawler

from tfmkt.common import DEFAULT_BASE_URL, load_parents, check_failures, safe_strip

logger = logging.getLogger(__name__)


def _clean(s):
    if s is None:
        return None
    return s.replace('\xa0', ' ').strip() or None


def _player_id(href):
    return href.rstrip('/').split('/')[-1]


def _club_id(href):
    """Extract numeric club id from any club href (.../verein/<id>/...)."""
    if not href:
        return None
    m = re.search(r'/verein/(\d+)', href)
    return m.group(1) if m else None


def _club_logo(club_id, size='head'):
    """Build a club emblem URL. Sizes: head (large transparent), big, normal, small, tiny."""
    if not club_id:
        return None
    return f'https://tmssl.akamaized.net/images/wappen/{size}/{club_id}.png'


def _flag_id(src):
    """Extract the country id from a TM flag url (.../flagge/<size>/<id>.png)."""
    if not src:
        return None
    m = re.search(r'/flagge/[^/]+/(\d+)\.png', src)
    return m.group(1) if m else None


def _flag_url(country_id, size='head'):
    """Build a country flag URL. National-team emblems (wappen/head) come back
    empty, so we use the flag instead. Sizes: head, big, normal, small, tiny."""
    if not country_id:
        return None
    return f'https://tmssl.akamaized.net/images/flagge/{size}/{country_id}.png'


def _portrait_variants(image_url):
    """Derive portrait sizes from a profile image URL by swapping the size segment."""
    if not image_url:
        return {}
    out = {}
    for size in ('big', 'header', 'medium', 'small'):
        out[size] = re.sub(r'/portrait/[^/]+/', f'/portrait/{size}/', image_url)
    return out


def parse_profile(sel, href):
    """Extract the full player bio from a profile page selector."""
    a = {}

    name_element = sel.xpath("//h1[@class='data-header__headline-wrapper']")
    a['name'] = _clean("".join(name_element.xpath("text()").getall()))
    a['last_name'] = _clean(name_element.xpath("strong/text()").get())
    a['shirt_number'] = _clean(name_element.xpath("span/text()").get())

    a['full_name'] = _clean(sel.xpath(
        "//span[text()='Name in home country:']/following::span[1]/text()").get())

    dob_raw = sel.xpath("//span[@itemprop='birthDate']/text()").get() or ''
    a['date_of_birth'] = dob_raw.strip().split(' (')[0] or None
    age_m = re.search(r'\((\d+)\)', dob_raw)
    a['age'] = age_m.group(1) if age_m else None

    a['place_of_birth'] = {
        'country': sel.xpath(
            "//span[text()='Place of birth:']/following::span[1]/span/img/@title").get(),
        'city': _clean(sel.xpath(
            "//span[text()='Place of birth:']/following::span[1]/span/text()").get()),
    }
    a['height'] = _clean(sel.xpath(
        "//span[text()='Height:']/following::span[1]/text()").get())

    citizenships = sel.xpath(
        "//span[text()='Citizenship:']/following::span[1]/img/@title").getall()
    a['citizenship'] = citizenships[0] if citizenships else None
    a['additional_citizenships'] = citizenships[1:] if len(citizenships) > 1 else []

    a['foot'] = _clean(sel.xpath(
        "//span[text()='Foot:']/following::span[1]/text()").get())

    # Position: label + detailed main / other positions
    a['position'] = _clean(sel.xpath(
        "//span[text()='Position:']/following::span[1]/text()").get())
    detail_positions = [
        _clean(p) for p in sel.css('.detail-position__position::text').getall() if _clean(p)
    ]
    detail_positions = list(OrderedDict.fromkeys(detail_positions))
    a['main_position'] = detail_positions[0] if detail_positions else None
    a['other_positions'] = detail_positions[1:]

    # Current club + league
    club_href = sel.xpath(
        "//span[contains(text(),'Current club:')]/following::span[1]//a[contains(@href,'/verein/')]/@href").get()
    club_id = _club_id(club_href)
    a['current_club'] = {
        'href': club_href,
        'name': _clean(sel.xpath(
            "//span[contains(text(),'Current club:')]/following::span[1]//a[contains(@href,'/verein/')]/@title").get()),
        'id': club_id,
        'logo_url': _club_logo(club_id),
    }
    a['current_league'] = _clean(sel.css('.data-header__league-link::text').get())
    a['league_level'] = _clean(sel.xpath(
        "//span[@class='data-header__label' and contains(.,'League level')]/span/text()").get())

    a['joined'] = _clean(sel.xpath(
        "//span[text()='Joined:']/following::span[1]/text()").get())
    a['contract_expires'] = _clean(sel.xpath(
        "//span[text()='Contract expires:']/following::span[1]/text()").get())
    # NB: profile label is "Last contract extension:" (older crawler used the wrong text)
    a['last_contract_extension'] = _clean(sel.xpath(
        "//span[contains(text(),'ast contract extension:')]/following::span[1]/text()").get())
    a['outfitter'] = _clean(sel.xpath(
        "//span[text()='Outfitter:']/following::span[1]/text()").get())

    a['player_agent'] = {
        'href': sel.xpath(
            "//span[text()='Player agent:']/following::span[1]/a/@href").get(),
        'name': _clean(sel.xpath(
            "//span[text()='Player agent:']/following::span[1]/a/text()").get()),
    }

    # National team. The emblem (wappen/head) for national sides is empty, so we
    # expose the country flag + id and flag it as a national team for the front.
    nat_li = sel.xpath("//li[contains(text(), 'National player:')]")
    if nat_li:
        href = nat_li.xpath(".//span/a/@href").get()
        if href:
            country_id = _flag_id(nat_li.xpath(".//span/img/@src").get())
            a['national_team'] = {
                'country': _clean(nat_li.xpath(".//span/img/@title").get()),
                'href': href,
                'is_national_team': True,
                'country_id': country_id,
                'flag_url': _flag_url(country_id),
            }
    caps_li = sel.xpath("//li[contains(text(), 'Caps/Goals:')]")
    if caps_li:
        vals = caps_li.xpath("a/text()").getall()
        if len(vals) >= 2:
            a['international_caps'] = _clean(vals[0])
            a['international_goals'] = _clean(vals[1])

    # Market value (header wrapper), with last-update date
    mv_nodes = [t.strip() for t in sel.css(
        'a.data-header__market-value-wrapper *::text, '
        'div.data-header__market-value-wrapper *::text').getall() if t.strip()]
    current_mv = None
    mv_update = None
    if mv_nodes:
        money = [n for n in mv_nodes if not n.lower().startswith('last update')]
        update = [n for n in mv_nodes if n.lower().startswith('last update')]
        current_mv = ''.join(money).replace(' ', '') or None
        if update:
            mv_update = update[0].split(':', 1)[-1].strip()
    a['current_market_value'] = current_mv
    a['market_value_last_update'] = mv_update
    a['highest_market_value'] = _clean(sel.xpath(
        "//div[@class='tm-player-market-value-development__max-value']/text()").get())

    # Achievements come from the dedicated `erfolge` tab (parse_erfolge), not the
    # header badges — the badges lack per-title counts.

    a['image_url'] = sel.xpath("//img[@class='data-header__profile-image']/@src").get()
    a['image_urls'] = _portrait_variants(a['image_url'])
    a['social_media'] = sel.css(
        'div.socialmedia-icons a::attr(href)').getall()
    return a


def aggregate_performance(data):
    """Aggregate the performance-game API into per-season totals + career totals."""
    by_season = {}
    for perf in data.get('data', {}).get('performance', []):
        gi = perf['gameInformation']
        st = perf['statistics']
        gen = st.get('generalStatistics', {})
        if gen.get('participationState') != 'played':
            continue
        sid = gi.get('seasonId')
        s = by_season.setdefault(sid, {
            'season_id': sid, 'appearances': 0, 'goals': 0, 'assists': 0,
            'own_goals': 0, 'minutes': 0, 'yellow_cards': 0,
        })
        goals = st.get('goalStatistics', {})
        cards = st.get('cardStatistics', {})
        play = st.get('playingTimeStatistics', {})
        s['appearances'] += 1
        s['goals'] += goals.get('goalsScoredTotal') or 0
        s['assists'] += goals.get('assists') or 0
        s['own_goals'] += goals.get('ownGoalsScored') or 0
        s['minutes'] += play.get('playedMinutes') or 0
        s['yellow_cards'] += cards.get('yellowCardNet') or 0

    seasons = [by_season[k] for k in sorted(by_season, reverse=True)]
    career = {'appearances': 0, 'goals': 0, 'assists': 0, 'minutes': 0}
    for s in seasons:
        for k in career:
            career[k] += s[k]
    return seasons, career


_YOUTH_RE = re.compile(
    r'\b(U-?\d{2}|Jugend|Youth|Akademie|Academy|Reserve|Reserves)\b|/verein/.*\bii\b',
    re.IGNORECASE)


def classify_category(record):
    """Derive 'youth' | 'professional' for a player.

    Transfermarkt has no explicit youth/professional flag, so infer it from:
      - current club being a youth/reserve side (name or href: U19/U17/Jugend/II/...)
      - league level naming a youth competition
      - young age with zero senior appearances
    Falls back to 'professional' when the player clearly has senior football,
    else None when there is not enough signal.
    """
    club = record.get('current_club') or {}
    club_blob = ' '.join(str(v) for v in (club.get('name'), club.get('href')) if v)
    league_level = record.get('league_level') or ''
    if _YOUTH_RE.search(club_blob) or 'youth' in league_level.lower():
        return 'youth'

    career = record.get('career_totals') or {}
    appearances = career.get('appearances')
    try:
        age = int(record.get('age')) if record.get('age') is not None else None
    except (TypeError, ValueError):
        age = None

    if appearances:
        return 'professional'
    if age is not None and age < 19 and appearances == 0:
        return 'youth'
    if age is not None and age >= 19:
        return 'professional'
    return None


def parse_erfolge(sel):
    """Player honours from the `erfolge` tab.

    Each title is a `.content-box-headline` like "1x Campeón de la Copa Sudamericana".
    Only "Nx <title>" headlines are kept, dropping non-honour boxes
    ("Vídeos de Transfermarkt", "Todos los títulos").
    Returns [{'title': ..., 'count': N}, ...].
    """
    out = []
    for h in sel.css('.content-box-headline'):
        txt = re.sub(r'\s+', ' ', ' '.join(
            x.strip() for x in h.css('::text').getall() if x.strip())).strip()
        m = re.match(r'^(\d+)\s*x\s*(.+)$', txt)
        if m:
            out.append({'title': m.group(2).strip(), 'count': int(m.group(1))})
    return out


def parse_injuries(sel):
    injuries = []
    tables = sel.css('table.items')
    if not tables:
        return injuries
    for row in tables[0].css('tbody tr'):
        cells = [_clean(c) for c in row.css('td::text').getall() if _clean(c)]
        if len(cells) >= 5:
            injuries.append({
                'season': cells[0], 'injury': cells[1],
                'from': cells[2], 'until': cells[3], 'days': cells[4],
            })
    return injuries


async def run(parents_arg=None, season=2024, base_url=None):
    base_url = base_url or DEFAULT_BASE_URL
    parents = load_parents(parents_arg)
    players = [p for p in parents if '/profil/spieler/' in p.get('href', '')]

    # Accumulator keyed by player id, output order preserved
    acc = OrderedDict()
    for p in players:
        pid = _player_id(p['href'])
        acc[pid] = {
            'type': 'player',
            'href': p['href'],
            'code': unquote(urlparse(p['href']).path.split('/')[1]),
        }

    requests = []
    for p in players:
        pid = _player_id(p['href'])
        href = p['href']
        requests += [
            Request.from_url(base_url + href,
                             label='profile', user_data={'pid': pid, 'href': href}),
            Request.from_url(f"{base_url}/ceapi/transferHistory/list/{pid}",
                             label='transfers', user_data={'pid': pid}),
            Request.from_url(f"{base_url}/ceapi/performance-game/{pid}",
                             label='performance', user_data={'pid': pid}),
            Request.from_url(base_url + href.replace('/profil/', '/verletzungen/'),
                             label='injuries', user_data={'pid': pid}),
            Request.from_url(base_url + href.replace('/profil/', '/erfolge/'),
                             label='erfolge', user_data={'pid': pid}),
            Request.from_url(f"https://tmapi.transfermarkt.technology/player/{pid}/gallery",
                             label='gallery', user_data={'pid': pid}),
        ]

    failures = []
    crawler = ParselCrawler()

    @crawler.failed_request_handler
    async def on_failed(context, error):
        failures.append((context.request.url, error))

    @crawler.router.handler('profile')
    async def profile(context):
        ud = context.request.user_data
        acc[ud['pid']].update(parse_profile(context.selector, ud['href']))

    @crawler.router.handler('transfers')
    async def transfers(context):
        body = await context.http_response.read()
        data = json.loads(body)

        def club(side):
            side = side or {}
            cid = _club_id(side.get('href'))
            return {
                'name': side.get('clubName'),
                'href': side.get('href'),
                'id': cid,
                'logo_url': side.get('clubEmblem-2x') or _club_logo(cid),
            }

        out = []
        for t in data.get('transfers', []):
            out.append({
                'date': t.get('date'), 'season': t.get('season'),
                'from': club(t.get('from')), 'to': club(t.get('to')),
                'market_value': t.get('marketValue'), 'fee': t.get('fee'),
                'upcoming': t.get('upcoming'),
            })

        # Club history: distinct destination clubs over time, oldest first.
        history = []
        seen = set()
        for t in reversed(out):
            c = t['to']
            key = c['id'] or c['name']
            if key and key not in seen:
                seen.add(key)
                history.append({**c, 'joined': t['date'], 'season': t['season']})

        pid = context.request.user_data['pid']
        acc[pid]['transfers'] = out
        acc[pid]['transfer_fee_sum'] = data.get('formattedFeeSum')
        acc[pid]['clubs_history'] = history

    @crawler.router.handler('performance')
    async def performance(context):
        body = await context.http_response.read()
        data = json.loads(body)
        seasons, career = aggregate_performance(data)
        pid = context.request.user_data['pid']
        acc[pid]['stats_by_season'] = seasons
        acc[pid]['career_totals'] = career

    @crawler.router.handler('injuries')
    async def injuries(context):
        acc[context.request.user_data['pid']]['injuries'] = parse_injuries(context.selector)

    @crawler.router.handler('erfolge')
    async def erfolge(context):
        acc[context.request.user_data['pid']]['achievements'] = parse_erfolge(context.selector)

    @crawler.router.handler('gallery')
    async def gallery(context):
        body = await context.http_response.read()
        data = json.loads(body)
        images = (data.get('data') or {}).get('images', []) if data.get('success') else []
        acc[context.request.user_data['pid']]['gallery'] = [
            {'title': img.get('title'), 'url': img.get('url'),
             'source': img.get('source'), 'premium': img.get('isPremium')}
            for img in images
        ]

    await crawler.run(requests)

    for record in acc.values():
        print(json.dumps(record), flush=True)

    check_failures(failures)
