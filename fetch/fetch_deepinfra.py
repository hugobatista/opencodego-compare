#!/usr/bin/env python3
"""Fetch DeepInfra API models list and build pricing rows.

DeepInfra is pay-per-usage (like Zen): real = listed. Prices from the API
are $/1M tokens. Only chat/LLM models (those with input_tokens/output_tokens
pricing) are kept — image/TTS/STT/embedding/video models use non-token units.
"""

import json
import os
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
API_URL = 'https://api.deepinfra.com/v1/openai/models'


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    resp = requests.get(API_URL, timeout=60, headers={
        'User-Agent': 'modelpricing-bot/1.0'
    })
    resp.raise_for_status()
    data = resp.json()

    rows = []
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
        # base = last path segment, like OpenRouter, for modelmarkets matching
        base = mid.split('/')[-1]
        rows.append({
            'market': 'deepinfra',
            'model': base,
            'base': base,
            'plan': 'DeepInfra',
            'provider': '',
            'providerLink': None,
            'input': inp,
            'output': out,
            'read': pricing.get('cache_read_tokens'),
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
        })

    out_path = os.path.join(DATA_DIR, 'deepinfra.json')
    with open(out_path, 'w') as f:
        json.dump(rows, f, indent=2)
    print(f'Saved {len(rows)} DeepInfra models to {out_path}')


if __name__ == '__main__':
    main()
