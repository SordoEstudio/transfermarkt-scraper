"""Enriched coach crawler.

For every input `coach` item it fetches the Transfermarkt trainer sources and
merges them into a single rich JSON record:

  - profile page    -> bio, role, contract, coaching licence, preferred formation
  - stations page   -> coaching history (clubs managed, as player and as coach)
  - erfolge page    -> honours / palmarés ([{title, count}])

Input (one JSON object per line):
    {"type":"coach","href":"/diego-flores/profil/trainer/12345"}
"""
import json
import logging
import re
from collections import OrderedDict
from urllib.parse import unquote, urlparse

from crawlee import Request
from crawlee.crawlers import ParselCrawler

from tfmkt.common import DEFAULT_BASE_URL, load_parents, check_failures

logger = logging.getLogger(__name__)


def _clean(s):
    if s is None:
        return None
    return s.replace('\xa0', ' ').strip() or None


def _coach_id(href):
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


def _norm_label(label):
    """Normalize a header label: collapse whitespace, drop trailing colon, lower."""
    return re.sub(r'\s+', ' ', label or '').strip().rstrip(':').strip().lower()


def _header_bio(sel):
    """Map normalized bio labels -> value from the `.data-header__items li` list.

    Trainer pages keep bio data in data-header items (label + content), NOT in
    the player-style `.info-table` with `<span>Label:</span>` blocks.
    """
    out = {}
    for li in sel.css('.data-header__items li'):
        label = _norm_label(' '.join(li.css('.data-header__label::text').getall()))
        if not label:
            continue
        value = _clean(' '.join(t.strip() for t in li.css('.data-header__content ::text, .data-header__content::text').getall() if t.strip()))
        out[label] = value
    return out


def parse_profile(sel, href):
    """Extract the full coach bio from a trainer profile page selector."""
    a = {}

    name_element = sel.xpath("//h1[contains(@class,'data-header__headline')]")
    name_parts = [t.strip() for t in name_element.xpath(".//text()").getall() if t.strip()]
    a['name'] = ' '.join(name_parts) or None
    a['last_name'] = _clean(name_element.xpath(".//strong/text()").get())

    bio = _header_bio(sel)

    dob_raw = bio.get('date of birth/age') or ''
    a['date_of_birth'] = dob_raw.split(' (')[0].strip() or None
    age_m = re.search(r'\((\d+)\)', dob_raw)
    a['age'] = age_m.group(1) if age_m else None

    # Place of birth: content text is the city; flag img title is the country.
    pob_li = sel.xpath("//li[contains(@class,'data-header__items')][.//span[contains(@class,'data-header__label')][contains(.,'Place of birth')]]")
    a['place_of_birth'] = {
        'country': pob_li.css('.data-header__content img::attr(title)').get(),
        'city': bio.get('place of birth'),
    }

    citizenships = sel.xpath(
        "//li[.//span[contains(@class,'data-header__label')][contains(.,'Citizenship')]]//img/@title").getall()
    if not citizenships and bio.get('citizenship'):
        citizenships = [bio['citizenship']]
    a['citizenship'] = citizenships[0] if citizenships else None
    a['additional_citizenships'] = citizenships[1:] if len(citizenships) > 1 else []

    # Coach-specific bio fields (labels carry odd whitespace, hence normalization)
    a['avg_term_as_coach'] = bio.get('avg. term as coach')
    a['coaching_licence'] = bio.get('coaching licence')
    a['preferred_formation'] = bio.get('preferred formation')

    # Role / club / league / dates live in the headline's club-info block.
    info = sel.css('.data-header__club-info')
    club_a = info.css('.data-header__club a')
    club_href = club_a.css('::attr(href)').get()
    club_id = _club_id(club_href)
    a['current_club'] = {
        'href': club_href,
        'name': _clean(club_a.css('::attr(title)').get() or club_a.css('::text').get()),
        'id': club_id,
        'logo_url': _club_logo(club_id),
    }
    a['current_league'] = _clean(' '.join(
        t.strip() for t in info.css('.data-header__league ::text').getall() if t.strip())) or None

    # Role = the club-info label that is plain text (no colon, e.g. "Manager").
    # Unemployed coaches ("Without Club") have no current role; the only plain
    # label there is the last club's name, so skip it.
    role = None
    club_name = a['current_club']['name']
    if club_href and club_name and club_name.lower() != 'without club':
        for lab in info.css('.data-header__label'):
            txt = _clean(' '.join(lab.css('::text').getall()))
            if txt and ':' not in txt and txt != club_name:
                role = txt
                break
    a['role'] = role

    def _date_for(keyword):
        for lab in info.css('.data-header__label'):
            head = (lab.xpath('text()').get() or '')
            if keyword.lower() in head.lower():
                return _clean(lab.css('.data-header__content::text').get())
        return None
    a['appointed'] = _date_for('Appointed')
    a['contract_expires'] = _date_for('Contract')

    a['image_url'] = sel.xpath("//img[@class='data-header__profile-image']/@src").get()
    a['image_urls'] = _portrait_variants(a['image_url'])
    a['social_media'] = sel.css('div.socialmedia-icons a::attr(href)').getall()
    return a


def _foto_title(url):
    """Derive a readable title from a foto filename slug (no title attr on TM)."""
    fn = url.split('/')[-1]
    fn = re.sub(r'-?\d{6,}.*', '', fn)  # strip trailing timestamp/id + extension
    return fn.replace('-', ' ').strip().title() or None


def parse_erfolge(sel):
    """Honours from the `erfolge` tab (same layout for trainers and players).

    Each title is a `.content-box-headline` like "3x Campeón de Chile".
    Only headlines matching the "Nx <title>" pattern are kept, which cleanly
    drops the non-honour boxes ("Vídeos de Transfermarkt", "Todos los títulos").
    Returns [{'title': 'Campeón de Chile', 'count': 3}, ...].
    """
    out = []
    for h in sel.css('.content-box-headline'):
        txt = re.sub(r'\s+', ' ', ' '.join(
            x.strip() for x in h.css('::text').getall() if x.strip())).strip()
        m = re.match(r'^(\d+)\s*x\s*(.+)$', txt)
        if m:
            out.append({'title': m.group(2).strip(), 'count': int(m.group(1))})
    return out


def parse_stations(sel):
    """Parse the trainer "Stationen" page: clubs managed / played for over time."""
    stations = []
    tables = sel.css('table.items')
    if not tables:
        return stations
    for row in tables[0].css('tbody tr'):
        club_href = row.css("td.hauptlink a[href*='/verein/']::attr(href)").get()
        club_name = _clean(row.css("td.hauptlink a::text").get())
        if not club_name:
            continue
        cells = [_clean(c) for c in row.css('td::text').getall() if _clean(c)]
        club_id = _club_id(club_href)

        # National sides render a flag (/flagge/...) instead of a club emblem, and
        # their wappen/head image is empty. Detect and expose the flag instead.
        flag_src = next((s for s in row.css('img::attr(src)').getall()
                         if '/flagge/' in s), None)
        country_id = _flag_id(flag_src)
        is_nt = country_id is not None

        club = {
            'name': club_name,
            'href': club_href,
            'id': club_id,
            'logo_url': _flag_url(country_id) if is_nt else _club_logo(club_id),
            'is_national_team': is_nt,
        }
        if is_nt:
            club['country_id'] = country_id
            club['flag_url'] = _flag_url(country_id)
        stations.append({'club': club, 'details': cells})
    return stations


async def run(parents_arg=None, season=2024, base_url=None):
    base_url = base_url or DEFAULT_BASE_URL
    parents = load_parents(parents_arg)
    coaches = [p for p in parents if '/profil/trainer/' in p.get('href', '')]

    # Accumulator keyed by coach id, output order preserved
    acc = OrderedDict()
    for p in coaches:
        cid = _coach_id(p['href'])
        acc[cid] = {
            'type': 'coach',
            'href': p['href'],
            'code': unquote(urlparse(p['href']).path.split('/')[1]),
        }

    requests = []
    for p in coaches:
        cid = _coach_id(p['href'])
        href = p['href']
        requests += [
            Request.from_url(base_url + href,
                             label='profile', user_data={'cid': cid, 'href': href}),
            Request.from_url(base_url + href.replace('/profil/trainer/', '/stationen/trainer/'),
                             label='stations', user_data={'cid': cid}),
            Request.from_url(base_url + href.replace('/profil/trainer/', '/erfolge/trainer/'),
                             label='erfolge', user_data={'cid': cid}),
        ]

    failures = []
    crawler = ParselCrawler()

    @crawler.failed_request_handler
    async def on_failed(context, error):
        failures.append((context.request.url, error))

    @crawler.router.handler('profile')
    async def profile(context):
        ud = context.request.user_data
        acc[ud['cid']].update(parse_profile(context.selector, ud['href']))

    @crawler.router.handler('stations')
    async def stations(context):
        acc[context.request.user_data['cid']]['stations'] = parse_stations(context.selector)

    @crawler.router.handler('erfolge')
    async def erfolge(context):
        acc[context.request.user_data['cid']]['achievements'] = parse_erfolge(context.selector)

    await crawler.run(requests)

    for record in acc.values():
        print(json.dumps(record), flush=True)

    check_failures(failures)
