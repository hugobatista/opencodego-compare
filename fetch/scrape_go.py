#!/usr/bin/env python3
"""Scrape OpenCode Go pricing and retention tables."""

import json
import os
import re
import requests
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
GO_URL = 'https://opencode.ai/docs/go'

OFFPEAK_HOURS = '01-04, 06-10 UTC Mon-Fri'


def parse_money(s):
    """Parse a money string like '$2.50' or '$0' to float."""
    s = s.strip().replace('$', '').replace(',', '')
    if not s or s == '—' or s == '-':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_int(s):
    s = s.strip().replace(',', '')
    if not s or s == '—' or s == '-':
        return None
    try:
        return int(s)
    except ValueError:
        return None


def retain_keeps_logs(s):
    """Data retention column -> whether prompts are kept.

    '0 days' means Zero Data Retention (nothing kept).
    '30 days' / 'Not ZDR' mean logs are retained.
    """
    s = s.strip().lower()
    if not s or s in ('no', 'false', 'none', 'no retention', 'zero', 'zero data retention'):
        return False
    m = re.match(r'([\d.]+)\s*days?', s)
    if m:
        return float(m.group(1)) > 0
    return True


def scrape():
    os.makedirs(DATA_DIR, exist_ok=True)
    resp = requests.get(GO_URL, timeout=60, headers={
        'User-Agent': 'modelpricing-bot/1.0'
    })
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content.decode('utf-8', 'replace'), 'html.parser')

    tables = soup.find_all('table')
    if len(tables) < 2:
        print(f'Expected at least 2 tables, found {len(tables)}')
        return

    # Load overrides
    overrides_path = os.path.join(os.path.dirname(__file__), 'overrides.json')
    with open(overrides_path) as f:
        overrides = json.load(f)
    go_exclude = overrides.get('go', {}).get('exclude', [])

    # Table 1: Pricing
    pricing_table = tables[1]
    rows_out = []

    headers = [th.get_text(strip=True) for th in pricing_table.find_all('th')]
    for tr in pricing_table.find_all('tr')[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all('td')]
        if len(cells) < 6:
            continue
        model = cells[0]
        if model in go_exclude:
            continue

        input_p = parse_money(cells[1])
        output_p = parse_money(cells[2])
        cached_read = parse_money(cells[3])
        cached_write = parse_money(cells[4])
        usage = parse_money(cells[5])

        # Detect peak/off-peak (keep the label in the model name)
        peak_hours = None
        if '(peak)' in model.lower() or '(off-peak)' in model.lower():
            peak_hours = OFFPEAK_HOURS

        # Allowance is $10/month subscription
        # effective = listed * 10 / usage (usage is $/month at full price)
        eff_in = None
        eff_out = None
        eff_read = None
        eff_write = None
        eff_all = usage  # the allowance value

        if usage and usage > 0:
            factor = 10.0 / usage
            eff_in = (input_p or 0) * factor if input_p is not None else None
            eff_out = (output_p or 0) * factor if output_p is not None else None
            eff_read = (cached_read or 0) * factor if cached_read is not None else None
            eff_write = (cached_write or 0) * factor if cached_write is not None else None

        rows_out.append({
            'market': 'go',
            'model': model,
            'base': model.split('(')[0].strip(),
            'provider': 'OpenCode Go',
            'providerLink': GO_URL,
            'input': input_p,
            'output': output_p,
            'read': cached_read,
            'write': cached_write,
            'effIn': eff_in,
            'effOut': eff_out,
            'effRead': eff_read,
            'effWrite': eff_write,
            'effAll': eff_all,
            'peakHours': peak_hours,
            'context': None,
            'latency': None,
            'tps': None,
            'logsPrompts': None,
            'trainsOnData': None,
            'notes': '',
        })

    # Table 3 (index 3): Retention
    retention_table = tables[3] if len(tables) > 3 else None
    retention_map = {}
    if retention_table:
        for tr in retention_table.find_all('tr')[1:]:
            cells = [td.get_text(strip=True) for td in tr.find_all('td')]
            if len(cells) < 3:
                continue
            model_name = cells[0]
            # Strip suffix like "(≤ 200K tokens)"
            base_name = re.sub(r'\s*\(.*?\)\s*$', '', model_name).strip()
            training = cells[1].strip().lower() in ('yes', 'true', '✓', '✅')
            data_retention = retain_keeps_logs(cells[2])
            retention_map[base_name] = {
                'trainsOnData': training,
                'logsPrompts': data_retention,
            }

    # Merge retention into rows
    for row in rows_out:
        base = row['base']
        if base in retention_map:
            row['trainsOnData'] = retention_map[base]['trainsOnData']
            row['logsPrompts'] = retention_map[base]['logsPrompts']
        # Fallback: try matching by partial name
        if row['trainsOnData'] is None:
            for key, val in retention_map.items():
                if key.lower() in base.lower() or base.lower() in key.lower():
                    row['trainsOnData'] = val['trainsOnData']
                    row['logsPrompts'] = val['logsPrompts']
                    break

    out_path = os.path.join(DATA_DIR, 'go.json')
    with open(out_path, 'w') as f:
        json.dump(rows_out, f, indent=2)
    print(f'Saved {len(rows_out)} Go models to {out_path}')


if __name__ == '__main__':
    scrape()
