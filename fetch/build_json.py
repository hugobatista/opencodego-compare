#!/usr/bin/env python3
"""Build the final prices.json from all data sources."""

import json
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

OPENROUTER_SALES_TAX_DEFAULT = 0.2425
OPENROUTER_SERVICE_FEE = 0.055
OPENROUTER_SERVICE_FEE_MIN = 0.80


def load_json(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        print(f'Warning: {path} not found, skipping')
        return None
    with open(path) as f:
        return json.load(f)


def build_go_rows(go_data):
    """Go rows already have effective prices computed by scrape_go.py."""
    return go_data


def build_zen_rows(zen_data):
    """Zen rows: real = listed (no multiplier)."""
    for row in zen_data:
        row['effIn'] = row['input']
        row['effOut'] = row['output']
        row['effRead'] = row['read']
        row['effWrite'] = row['write']
    return zen_data


def build_or_rows(openrouter_data, endpoints_data):
    """Build OpenRouter rows with real prices including fee + tax."""
    rows = []

    for model in openrouter_data:
        model_id = model['id']
        name = model.get('name', model_id)
        pricing = model.get('pricing', {})

        # OpenRouter prices are per-token; convert to per-1M tokens
        M = lambda v: None if v in (None, '') else float(v) * 1_000_000

        prompt_listed = M(pricing.get('prompt')) or 0.0
        completion_listed = M(pricing.get('completion')) or 0.0

        if prompt_listed == 0 and completion_listed == 0:
            continue

        # Get endpoint details
        ep_data = endpoints_data.get(model_id, {}) if endpoints_data else {}
        endpoints = ep_data.get('endpoints', [])

        # Keep every provider endpoint with a price (all providers per model)
        records = []

        for ep in endpoints:
            p = ep.get('pricing', {})
            ep_prompt = p.get('prompt', 0)
            ep_completion = p.get('completion', 0)
            policy = ep.get('data_policy', {})
            retains = policy.get('retainsPrompts', False)

            if ep_prompt == 0 and ep_completion == 0:
                continue

            records.append({
                'provider': ep.get('provider', 'unknown'),
                'prompt': M(ep_prompt) or 0.0,
                'completion': M(ep_completion) or 0.0,
                'read': M(p.get('input_cache_read') or p.get('prompt_read')),
                'write': M(p.get('input_cache_write') or p.get('prompt_write')),
                'discount': ep.get('discount'),
                'discount_note': ep.get('discount_note'),
                'latency': ep.get('stats', {}).get('p50_latency'),
                'tps': ep.get('stats', {}).get('p50_throughput'),
                'logsPrompts': retains,
                'trainsOnData': policy.get('training'),
            })

        # If no endpoint details, create a synthetic row
        if not records:
            records = [{
                'provider': 'openrouter',
                'prompt': prompt_listed,
                'completion': completion_listed,
                'read': None,
                'write': None,
                'discount': None,
                'latency': None,
                'tps': None,
                'logsPrompts': None,
                'trainsOnData': None,
            }]

        for ep in records:
            row = {
                'market': 'or',
                'model': name,
                'base': model_id,
                'provider': ep['provider'],
                'providerLink': f'https://openrouter.ai/{model_id}',
                'input': ep['prompt'],
                'output': ep['completion'],
                'read': ep['read'],
                'write': ep['write'],
                'effIn': None,
                'effOut': None,
                'effRead': None,
                'effWrite': None,
                'effAll': None,
                'peakHours': None,
                'context': model.get('context_length'),
                'latency': ep['latency'],
                'tps': ep['tps'],
                'logsPrompts': ep['logsPrompts'],
                'trainsOnData': ep['trainsOnData'],
                'notes': '',
            }
            if ep['discount']:
                note = ep.get('discount_note') or f'{ep["discount"]*100:.0f}% off'
                row['notes'] = note
            rows.append(row)

    return rows


def main():
    go_data = load_json('go.json')
    zen_data = load_json('zen.json')
    openrouter_data = load_json('openrouter.json')
    endpoints_data = load_json('or_endpoints.json')

    all_rows = []

    if go_data:
        all_rows.extend(build_go_rows(go_data))
    if zen_data:
        all_rows.extend(build_zen_rows(zen_data))
    if openrouter_data:
        all_rows.extend(build_or_rows(openrouter_data, endpoints_data))

    output = {
        'generated_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'meta': {
            'salesTaxDefault': OPENROUTER_SALES_TAX_DEFAULT,
            'openrouterServiceFee': OPENROUTER_SERVICE_FEE,
            'openrouterServiceFeeMin': OPENROUTER_SERVICE_FEE_MIN,
            'links': {
                'go': 'https://opencode.ai/docs/go',
                'zen': 'https://opencode.ai/docs/zen',
                'or': 'https://openrouter.ai',
            },
            'note': 'Prices in $/1M tokens unless noted. Go effective prices assume $10/mo subscription.',
        },
        'rows': all_rows,
    }

    out_path = os.path.join(DATA_DIR, 'prices.json')
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f'Saved {len(all_rows)} rows to {out_path}')


if __name__ == '__main__':
    main()
