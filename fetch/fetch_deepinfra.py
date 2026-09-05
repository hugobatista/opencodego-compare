#!/usr/bin/env python3
"""Fetch DeepInfra API models list and build pricing rows.

DeepInfra is pay-per-usage (like Zen): real = listed. Prices from the API
are $/1M tokens. Only chat/LLM models (those with input_tokens/output_tokens
pricing) are kept — image/TTS/STT/embedding/video models use non-token units.

Service tiers: DeepInfra exposes a per-request `service_tier` (Priority,
Standard, Flex) at per-model multipliers. `/v1/openai/models` does not carry
those, so we read the tier multipliers from the public `/models/list`
(`rate_per_service_tier_priority` / `rate_per_service_tier_flex`, or null when
unsupported). Standard base prices stay from `/v1/openai/models` (already
$/1M). Priority/Flex become extra rows per model whose price = base × the
model's tier multiplier.
"""

import json
import os
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
MODELS_URL = 'https://api.deepinfra.com/v1/openai/models'
TIERS_URL = 'https://api.deepinfra.com/models/list'

HEADERS = {'User-Agent': 'modelpricing-bot/1.0'}


def fetch_tier_mults():
    """model_name -> ({'priority': float|None, 'flex': float|None}).

    /models/list pricing (type=tokens) carries tier multipliers or null.
    Only read the multipliers — base prices come from /v1/openai/models to
    keep units ($/1M) and the chat catalog identical to before.
    """
    resp = requests.get(TIERS_URL, timeout=60, headers=HEADERS)
    resp.raise_for_status()
    out = {}
    for m in resp.json():
        pricing = m.get('pricing', {}) or {}
        if pricing.get('type') != 'tokens':
            continue
        out[m.get('model_name')] = {
            'priority': pricing.get('rate_per_service_tier_priority'),
            'flex': pricing.get('rate_per_service_tier_flex'),
        }
    return out


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    resp = requests.get(MODELS_URL, timeout=60, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    tier_mults = fetch_tier_mults()

    rows = []
    n_priority = 0
    n_flex = 0
    for m in data.get('data', []):
        mid = m.get('id')
        if not mid:
            continue
        meta = m.get('metadata', {})
        pricing = meta.get('pricing', {})
        inp = pricing.get('input_tokens')
        out = pricing.get('output_tokens')
        if inp is None and out is None:
            # Not a token-priced model (image/TTS/STT/etc.)
            continue
        tags = meta.get('tags', [])
        if 'chat' not in tags:
            # Token-priced but not a chat/LLM model (e.g. embeddings)
            continue
        read = pricing.get('cache_read_tokens')
        # base = last path segment, like OpenRouter, for modelmarkets matching
        base = mid.split('/')[-1]
        contextual = {
            'market': 'deepinfra',
            'model': base,
            'base': base,
            'plan': 'DeepInfra',
            'provider': '',
            'providerLink': None,
            'write': None,
            'effIn': None,
            'effOut': None,
            'effRead': None,
            'effWrite': None,
            'effAll': None,
            'peakHours': None,
            'context': meta.get('context_length'),
            'latency': None,
            'tps': None,
            'logsPrompts': None,
            'trainsOnData': None,
            'notes': '',
            'variantLink': f'https://deepinfra.com/{mid}',
        }

        def add_row(variant, mult, notes):
            row = dict(contextual)
            row['variant'] = variant
            row['input'] = inp * mult
            row['output'] = out * mult
            row['read'] = read * mult if read is not None else None
            row['notes'] = notes
            rows.append(row)

        # Standard tier (base price)
        mults = tier_mults.get(mid, {})
        pmult = mults.get('priority')
        fmult = mults.get('flex')
        notes = []
        if pmult is not None:
            notes.append(f'Priority ×{pmult}')
        if fmult is not None:
            notes.append(f'Flex ×{fmult}')
        add_row(base, 1.0, ' / '.join(notes))

        if pmult is not None:
            add_row(f'{base} (Priority)', pmult, f'Priority = base ×{pmult}')
            n_priority += 1
        if fmult is not None:
            add_row(f'{base} (Flex)', fmult, f'Flex = base ×{fmult}')
            n_flex += 1

    out_path = os.path.join(DATA_DIR, 'deepinfra.json')
    with open(out_path, 'w') as f:
        json.dump(rows, f, indent=2)
    print(
        f'Saved {len(rows)} DeepInfra rows to {out_path} '
        f'({len(data.get("data", []))} models; +{n_priority} Priority, '
        f'+{n_flex} Flex)'
    )


if __name__ == '__main__':
    main()
