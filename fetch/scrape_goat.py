#!/usr/bin/env python3
"""Scrape Command Code GOAT plan pricing and monthly credits tables."""

import html
import json
import os
import re
import requests
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
GOAT_URL = 'https://commandcode.ai/docs/plans/goat'

OFFPEAK_HOURS = '01-04, 06-10 UTC Mon-Fri'
DEFAULT_CREDITS = 20.0  # "new models start at 2x credits" on the $10/mo plan

CONTEXT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*([MK])\b', re.I)


def parse_money(s):
    """Parse a money string like '$2.50' or 'Free' to float."""
    if s is None:
        return None
    s = s.strip().replace('$', '').replace(',', '')
    if not s or s in ('—', '-', 'N/A'):
        return None
    if s.lower() == 'free':
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def parse_tps(s):
    s = (s or '').strip().replace(',', '')
    if not s or s in ('—', '-'):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_context(s):
    """'1M' -> 1000000, '256K' -> 256000, '262K' -> 262000."""
    s = (s or '').strip()
    m = CONTEXT_RE.search(s)
    if not m:
        return None
    v = float(m.group(1))
    return int(v * 1_000_000) if m.group(2).upper() == 'M' else int(v * 1000)


def catalog_money(s):
    """Parse a catalog price cell: strips '+N' caps badges and struck text.

    Struck-through deal prices render like '$0.60$0.30+1'; the billed
    (last) value wins. 'Free' -> 0.0.
    """
    s = unescape(s or '').strip()
    s = re.sub(r'\+\d+\s*$', '', s)
    nums = re.findall(r'\d+(?:\.\d+)?', s)
    if not nums:
        return parse_money(s)
    try:
        return float(nums[-1])
    except ValueError:
        return None


def unescape(s):
    return html.unescape((s or '')).strip()


def clean_model(s):
    """Strip markup noise that Command Code appends to model names.

    Removes: 'Free' suffix, '-98%' deal tags, and 'Off-peak shown (17h/day)
    · peak $X / $Y 01-04 & 06-10 UTC' annotations.
    """
    s = unescape(s)
    s = re.sub(r'\s*Free\s*$', '', s, flags=re.I)
    s = re.sub(r'\s*-?\d+%+\s*$', '', s)
    s = re.sub(r'\s*Off-peak.*$', '', s, flags=re.I)
    return s.strip()


def scrape():
    os.makedirs(DATA_DIR, exist_ok=True)
    resp = requests.get(GOAT_URL, timeout=60, headers={
        'User-Agent': 'modelpricing-bot/1.0'
    })
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content.decode('utf-8', 'replace'), 'html.parser')

    tables = soup.find_all('table')
    if len(tables) < 4:
        print(f'Expected at least 4 tables, found {len(tables)}')
        return

    # Table 1 (index 0): full catalog - model, context, tps, listed prices
    catalog = tables[0]
    cat_keys = set()
    for tr in catalog.find_all('tr')[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all('td')]
        if len(cells) < 8:
            continue
        cat_keys.add(clean_model(cells[0]))
    print(f'Catalog: {len(cat_keys)} model slots')

    # Tables 3/4 (index 2/3): per-model monthly credits at billed prices
    credits = {}
    for ti in (2, 3):
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

        # Catalog price cells carry '+1' caps badges and struck-through deal
        # text; prefer the clean billed prices from the credits tables.
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
            factor = 10.0 / credits_val

        eff = lambda v: None if v is None else v * factor if factor is not None else 0.0

        # Models with off-peak pricing only show the off-peak rate in their
        # row; the peak rate sits in the annotation ('peak $X / $Y'). Emit
        # two rows like the Go scraper does, scaling read/write by the ratio.
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
                'market': 'goat',
                'model': disp_name,
                'base': disp_name.split('(')[0].strip(),
                'provider': 'Command Code GOAT',
                'providerLink': GOAT_URL,
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

    out_path = os.path.join(DATA_DIR, 'goat.json')
    with open(out_path, 'w') as f:
        json.dump(rows_out, f, indent=2)
    print(f'Saved {len(rows_out)} GOAT models to {out_path}')

    missing = cat_keys - processed
    if missing:
        print(f'Warning: catalog models not emitted: {sorted(missing)}')


if __name__ == '__main__':
    scrape()