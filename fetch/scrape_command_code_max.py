#!/usr/bin/env python3
"""Scrape Command Code Max 10x / Max 20x plan pricing and credits table.

The page holds a single per-model table with two credit columns: Max 10x
credits and Max 20x credits. Each model is emitted as two rows (one per
tier) with effective prices: listed × sub ÷ per-tier monthly credits.
"""

import json
import os
import requests
from bs4 import BeautifulSoup

from scrape_command_code_goat import catalog_money, clean_model, parse_context

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
MAX_URL = 'https://commandcode.ai/docs/plans/max'

TIERS = {
    'command-code-max-10x': {'plan': 'Command Code Max 10x', 'sub': 100.0},
    'command-code-max-20x': {'plan': 'Command Code Max 20x', 'sub': 200.0},
}
DEFAULT_CREDITS = {
    'command-code-max-10x': 150.0,
    'command-code-max-20x': 300.0,
}


def find_pricing_table(tables):
    """Locate the per-model pricing/credits table by its header.

    Table indexes on the page shift with layout, so match on the header
    cells ('Max 10× credits') rather than position.
    """
    for table in tables:
        first = table.find('tr')
        if not first:
            continue
        header = ' '.join(td.get_text(strip=True).lower() for td in first.find_all(['th', 'td']))
        if 'credits' in header and ('max 10' in header or '10×' in header):
            return table
    return None


def scrape():
    os.makedirs(DATA_DIR, exist_ok=True)
    resp = requests.get(MAX_URL, timeout=60, headers={
        'User-Agent': 'modelpricing-bot/1.0'
    })
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content.decode('utf-8', 'replace'), 'html.parser')

    tables = soup.find_all('table')
    pricing = find_pricing_table(tables)
    if pricing is None:
        print(f'Expected a per-model pricing table, found {len(tables)} tables')
        return

    rows_out = []
    processed = set()
    for tr in pricing.find_all('tr')[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all('td')]
        if len(cells) < 7:
            continue

        raw_name = cells[0]
        name = clean_model(raw_name)
        if not name:
            continue
        processed.add(name)

        input_p = catalog_money(cells[1])
        output_p = catalog_money(cells[2])
        cached_read = catalog_money(cells[3])
        cached_write = None if cells[4] in ('', '—', '-') else catalog_money(cells[4])
        credits10 = catalog_money(cells[5])
        credits20 = catalog_money(cells[6])

        is_free = (input_p == 0 and output_p == 0)

        for tier_key, tier in TIERS.items():
            if is_free:
                credits_val = None
                factor = None
            else:
                credits_val = credits10 if tier_key.endswith('10x') else credits20
                if not credits_val:
                    credits_val = DEFAULT_CREDITS[tier_key]
                factor = tier['sub'] / credits_val

            eff = lambda v: None if v is None else v * factor if factor is not None else 0.0

            rows_out.append({
                'market': tier_key,
                'model': name,
                'base': name.split('(')[0].strip(),
                'plan': tier['plan'],
                'provider': '',
                'providerLink': None,
                'input': input_p,
                'output': output_p,
                'read': cached_read,
                'write': cached_write,
                'effIn': eff(input_p),
                'effOut': eff(output_p),
                'effRead': eff(cached_read),
                'effWrite': eff(cached_write),
                'effAll': credits_val,
                'peakHours': None,
                'context': None,
                'latency': None,
                'tps': None,
                'logsPrompts': None,
                'trainsOnData': None,
                'privacyNote': '99% of models route via ZDR-capable upstreams, most ZDR by default',
                'notes': '',
            })

    out_path = os.path.join(DATA_DIR, 'command-code-max.json')
    with open(out_path, 'w') as f:
        json.dump(rows_out, f, indent=2)
    print(f'Saved {len(rows_out)} Max models to {out_path}')


if __name__ == '__main__':
    scrape()