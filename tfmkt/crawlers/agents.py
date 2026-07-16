import json
import re

from crawlee import Request

from tfmkt.common import (
    DEFAULT_BASE_URL,
    load_parents,
    build_initial_requests,
    create_crawler,
    check_failures,
)


async def run(parents_arg=None, season=2024, base_url=None):
    """Crawl a Transfermarkt agent ("beraterfirma") page and emit its clients
    as `player` items, ready to be piped into the `players`/`appearances`
    crawlers.

    Input parent shape (one JSON object per line):
        {"type": "agent", "href": "/mv-sports-agency/beraterfirma/berater/16055"}
    """
    base_url = base_url or DEFAULT_BASE_URL
    parents = load_parents(parents_arg)
    requests = build_initial_requests(parents, season, base_url, label='parse', spider_name='agents')

    crawler, failures = create_crawler()

    @crawler.router.handler('parse')
    async def parse(context) -> None:
        parent = context.request.user_data['parent']
        sel = context.selector

        # An agent page contains several `table.items` (Player / Coach / ...).
        # Keep only the one whose first header is "Player".
        player_tables = [
            table for table in sel.css('table.items')
            if (table.css('th::text').get() or '').strip().lower() == 'player'
        ]

        for table in player_tables:
            hrefs = table.css("a[href*='/profil/spieler/']::attr(href)").getall()
            # dedupe while preserving order (name + image cell can repeat a link)
            for href in dict.fromkeys(hrefs):
                href = re.sub(r'/saison_id/[0-9]{4}$', '', href)
                item = {
                    'type': 'player',
                    'href': href,
                    'parent': parent,
                }
                print(json.dumps(item), flush=True)

        # Follow pagination (`.../berater/<id>/page/N`). Crawlee dedupes by URL,
        # so re-enqueuing the same page links from every page is safe.
        new_requests = []
        for href in sel.css('a.tm-pagination__link::attr(href)').getall():
            if '/page/' not in href:
                continue
            new_requests.append(
                Request.from_url(
                    url=base_url + href,
                    label='parse',
                    user_data={'parent': parent},
                )
            )
        if new_requests:
            await context.add_requests(new_requests)

    await crawler.run(requests)
    check_failures(failures)
