#!/usr/bin/env python3
"""Fetch OpenRouter API models and save to data/openrouter.json."""

import json
import os
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
API_URL = 'https://openrouter.ai/api/v1/models'


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    resp = requests.get(API_URL, timeout=60, headers={
        'User-Agent': 'modelpricing-bot/1.0'
    })
    resp.raise_for_status()
    data = resp.json()

    models = data.get('data', [])
    filtered = [
        m for m in models
        if m.get('id') and 'auto' not in m['id'].lower()
    ]

    result = []
    for m in filtered:
        pricing = m.get('pricing', {})
        prompt = float(pricing.get('prompt', '0') or '0')
        completion = float(pricing.get('completion', '0') or '0')
        if prompt > 0 or completion > 0:
            result.append(m)

    out_path = os.path.join(DATA_DIR, 'openrouter.json')
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f'Saved {len(result)} models to {out_path}')


if __name__ == '__main__':
    main()
