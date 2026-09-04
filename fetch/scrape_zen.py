#!/usr/bin/env python3
"""Scrape OpenCode Zen pricing and deprecation tables."""

import json
import os
import re
import requests
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
ZEN_URL = 'https://opencode.ai/docs/zen'

# Override defaults for Zen models
ZEN_OVERRIDES = {
    'Claude': {'logsPrompts': True, 'retentionDays': 30},
}


def parse_money(s):
    s = s.strip().replace('$', '').replace(',', '')
    if not s or s in ('—', '-', 'N/A'):
        return None
    if s.lower() == 'free':
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def scrape():
    os.makedirs(DATA_DIR, exist_ok=True)
    resp = requests.get(ZEN_URL, timeout=60, headers={
        'User-Agent': 'modelpricing-bot/1.0'
    })
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content.decode('utf-8', 'replace'), 'html.parser')

    tables = soup.find_all('table')
    if len(tables) < 1:
        print('No tables found')
        return

    # Table 1: Pricing
    pricing_table = tables[1]

    # Table 2: Deprecation (if present)
    deprecated = set()
    if len(tables) > 2:
        dep_table = tables[2]
        for tr in dep_table.find_all('tr')[1:]:
            cells = [td.get_text(strip=True) for td in tr.find_all('td')]
            if cells:
                deprecated.add(cells[0])

    rows_out = []
    for tr in pricing_table.find_all('tr')[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all('td')]
        if len(cells) < 5:
            continue
        model = cells[0]
        if model in deprecated:
            continue

        input_p = parse_money(cells[1])
        output_p = parse_money(cells[2])
        cached_read = parse_money(cells[3])
        cached_write = parse_money(cells[4])

        # Determine overrides
        logs = None
        trains = None
        notes = ''
        for prefix, ov in ZEN_OVERRIDES.items():
            if prefix.lower() in model.lower():
                logs = ov.get('logsPrompts')
                if 'retentionDays' in ov:
                    notes = f'Retention: {ov["retentionDays"]}d'
                break

        # Free models
        is_free = (input_p == 0 and output_p == 0)
        if is_free:
            notes = 'Free tier'

        # Check for training info in model name or nearby text
        if trains is None and 'training' in model.lower():
            trains = True

        rows_out.append({
            'market': 'zen',
            'model': model,
            'base': model,
            'provider': 'OpenCode Zen',
            'providerLink': ZEN_URL,
            'input': input_p,
            'output': output_p,
            'read': cached_read,
            'write': cached_write,
            'effIn': None,
            'effOut': None,
            'effRead': None,
            'effWrite': None,
            'effAll': None,
            'peakHours': None,
            'context': None,
            'latency': None,
            'tps': None,
            'logsPrompts': logs,
            'trainsOnData': trains,
            'notes': notes,
        })

    out_path = os.path.join(DATA_DIR, 'zen.json')
    with open(out_path, 'w') as f:
        json.dump(rows_out, f, indent=2)
    print(f'Saved {len(rows_out)} Zen models to {out_path}')


if __name__ == '__main__':
    scrape()
