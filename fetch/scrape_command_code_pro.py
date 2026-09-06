#!/usr/bin/env python3
"""Scrape Command Code Pro plan pricing and monthly credits tables."""

import json
import os
import re
import requests
from bs4 import BeautifulSoup

from scrape_command_code_goat import (
    OFFPEAK_HOURS,
    catalog_money,
    clean_model,
    parse_context,
    parse_money,
    parse_tps,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PRO_URL = 'https://commandcode.ai/docs/plans/pro'

SUB_PRICE = 20.0
DEFAULT_CREDITS = 30.0  # "standard $30 credits for the $20 Pro plan"


def scrape():
    os.makedirs(DATA_DIR, exist_ok=True)
    resp = requests.get(PRO_URL, timeout=60, headers={
        'User-Agent': 'modelpricing-bot/1.0'
    })
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content.decode('utf-8', 'replace'), 'html.parser')

    tables = soup.find_all('table')
    if len(tables) < 5:
        print(f'Expected at least 5 tables, found {len(tables)}')
        return

    # Table 0 (index 0): full catalog - model, context, intelligence, tps, prices.
    # Note the shifted columns vs GOAT: index 2 = intelligence, 3 = tok/s.
    catalog = tables[0]
    cat_keys = set()
    for tr in catalog.find_all('tr')[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all('td')]
        if len(cells) < 8:
            continue
        cat_keys.add(clean_model(cells[0]))
    print(f'Catalog: {len(cat_keys)} model slots')

    # Tables 2/3/4 (index 2/3/4): per-model monthly credits at billed prices.
    # Table 1 (index 1) holds request-estimate rows, not pricing - skip it.
    credits = {}
    for ti in (2, 3, 4):
        if ti >= len(tables):
            continue
        for tr in tables[ti].find_all('tr')[1:]:
            cells = [td.get_text(strip=True) for td in tr.find_all('td')]
            if len(cells) < 6:
                continue
            key = clean_model(cells[0])
            credits[key] = {
                'input': parse_money(cells[1]),
                'output': parse_money(cells[2]),
                'read': parse_money(cells[3]),
                'write': parse_money(cells[4]),
                'credits': parse_money(cells[5]),
            }
    print(f'Credits: {len(credits)} models with explicit allowance')

    rows_out = []
    processed = set()

    for tr in catalog.find_all('tr')[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all('td')]
        if len(cells) < 8:
            continue

        raw_name = cells[0]
        name = clean_model(raw_name)
        if not name:
            continue
        processed.add(name)

        entry = credits.get(name) or {}
        input_p = entry.get('input')
        output_p = entry.get('output')
        cached_read = entry.get('read')
        cached_write = entry.get('write')

        if input_p is None and output_p is None:
            # Not in the credits tables: free models fall back to the catalog.
            input_p = catalog_money(cells[4])
            output_p = catalog_money(cells[5])
            cached_read = catalog_money(cells[6])
            if cached_read == 0:
                cached_write = None
            else:
                cached_write = None if cells[7] in ('', '—', '-') else catalog_money(cells[7])

        is_free = (input_p == 0 and output_p == 0)

        notes = ''
        deal = re.search(r'\s*-(\d+)%\s*$', raw_name)
        if deal:
            notes = f'{deal.group(1)}% off'

        peak_hours = None
        if 'off-peak' in raw_name.lower():
            peak_hours = OFFPEAK_HOURS

        if is_free:
            credits_val = None
            factor = None
        else:
            credits_val = entry.get('credits')
            if credits_val is None:
                credits_val = DEFAULT_CREDITS
            factor = SUB_PRICE / credits_val

        eff = lambda v: None if v is None else v * factor if factor is not None else 0.0

        # Off-peak models only show the off-peak rate; the peak rate sits in an
        # annotation ('peak $X / $Y'). Emit two rows, scaling read/write by the
        # input peak/off-peak ratio, exactly like the GOAT scraper.
        variants = [(name, input_p, output_p, cached_read, cached_write)]
        if peak_hours:
            m = re.search(r'peak\s+\$([\d.]+)\s*/\s*\$([\d.]+)', raw_name, re.I)
            if m and input_p:
                ratio = float(m.group(1)) / input_p
                scal = lambda v: None if v is None else v * ratio
                variants = [
                    (f'{name} (Off-Peak)', input_p, output_p, cached_read, cached_write),
                    (f'{name} (Peak)', float(m.group(1)), float(m.group(2)),
                     scal(cached_read), scal(cached_write)),
                ]

        for disp_name, in_p, out_p, rd_p, wr_p in variants:
            rows_out.append({
                'market': 'command-code-pro',
                'model': disp_name,
                'base': disp_name.split('(')[0].strip(),
                'plan': 'Command Code Pro',
                'provider': '',
                'providerLink': None,
                'input': in_p,
                'output': out_p,
                'read': rd_p,
                'write': wr_p,
                'effIn': eff(in_p),
                'effOut': eff(out_p),
                'effRead': eff(rd_p),
                'effWrite': eff(wr_p),
                'effAll': credits_val,
                'peakHours': peak_hours,
                'context': parse_context(cells[1]),
                'latency': None,
                'tps': parse_tps(cells[3]),
                'logsPrompts': False,
                'trainsOnData': False,
                'notes': notes,
            })

    out_path = os.path.join(DATA_DIR, 'command-code-pro.json')
    with open(out_path, 'w') as f:
        json.dump(rows_out, f, indent=2)
    print(f'Saved {len(rows_out)} Pro models to {out_path}')

    missing = cat_keys - processed
    if missing:
        print(f'Warning: catalog models not emitted: {sorted(missing)}')


if __name__ == '__main__':
    scrape()