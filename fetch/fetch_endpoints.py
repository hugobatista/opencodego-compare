#!/usr/bin/env python3
"""Fetch per-provider endpoint details from OpenRouter model pages."""

import json
import os
import re
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
OR_BASE = 'https://openrouter.ai'


PROMO_RE = re.compile(
    r'Limited-time\s+(\d+)%\s+discount\s+via\s+(.+?)\s+through\s+(.+?)\s*\.'
)


def extract_promos(u):
    """Extract distinct discount promo messages from a model page."""
    promos = {}
    for pct, name, date in PROMO_RE.findall(u):
        key = (int(pct), name.strip().lower())
        promos.setdefault(key, (int(pct), name.strip(), date.strip()))
    return promos


def promo_note(promos, pct, name):
    """Map a provider endpoint to a promo message by discount % and name."""
    p = round(pct * 100)
    n = (name or '').strip().lower()
    for (mp, _), (_, mname, mdate) in promos.items():
        mn = mname.lower()
        if mp == p and n and (n in mn or mn in n):
            return f'{mp}% off through {mdate}'
    return None


def fetch_model_endpoints(model_id):
    """Fetch endpoints for a single model from its page."""
    url = f'{OR_BASE}/{model_id}'
    try:
        resp = requests.get(url, timeout=60, headers={
            'User-Agent': 'modelpricing-bot/1.0'
        })
        resp.raise_for_status()
    except Exception as e:
        print(f'  Error fetching {model_id}: {e}')
        return []

    html = resp.text
    # Unescape the double-escaped JSON in HTML
    u = html.replace('\\\\"', '"').replace('\\"', '"')
    promos = extract_promos(u)

    # Find all dataPolicy regions — each corresponds to one provider endpoint
    dp_regions = [m.start() for m in re.finditer(r'"dataPolicy"', u)]
    endpoints = []
    seen_providers = set()

    for start in dp_regions:
        # Search backwards for the nearest slug
        before = u[max(0, start - 500):start]
        slug_match = re.findall(r'"slug"\s*:\s*"([^"]+)"', before)
        slug = slug_match[-1] if slug_match else None
        if not slug or slug in seen_providers:
            continue
        if slug == 'openrouter':
            continue
        seen_providers.add(slug)

        # dataPolicy
        dp_match = re.search(r'"dataPolicy"\s*:\s*\{([^}]+)\}', u[start:start + 300])
        retains = False
        training = False
        if dp_match:
            dp_text = dp_match.group(1)
            retains_m = re.search(r'"retainsPrompts"\s*:\s*(true|false)', dp_text)
            training_m = re.search(r'"training"\s*:\s*(true|false)', dp_text)
            if retains_m:
                retains = retains_m.group(1) == 'true'
            if training_m:
                training = training_m.group(1) == 'true'

        # Pricing (search forward from dataPolicy)
        after = u[start:start + 3000]
        price_match = re.search(r'"pricing"\s*:\s*\{([^}]+)\}', after)
        pricing = {}
        if price_match:
            pt = price_match.group(1)
            for field in ['prompt', 'completion']:
                m = re.search(rf'"{field}"\s*:\s*"?([\d.]+)"?', pt)
                if m:
                    pricing[field] = float(m.group(1))
            for field in ['input_cache_read', 'input_cache_write']:
                m = re.search(rf'"{field}"\s*:\s*"?([\d.]+)"?', pt)
                if m:
                    pricing[field] = float(m.group(1))

        # Stats
        stats_match = re.search(r'"stats"\s*:\s*\{([^}]+)\}', after)
        stats = {}
        if stats_match:
            st = stats_match.group(1)
            for field in ['p50_latency', 'p50_throughput']:
                m = re.search(rf'"{field}"\s*:\s*([\d.]+)', st)
                if m:
                    stats[field] = float(m.group(1))

        # Discount
        discount_match = re.search(r'"discount"\s*:\s*([\d.]+)', after)
        discount = float(discount_match.group(1)) if discount_match else None

        # Provider display name (for matching promo messages)
        disp_match = re.search(r'"provider_display_name"\s*:\s*"([^"]+)"', after)
        disp_name = disp_match.group(1) if disp_match else slug

        if not pricing.get('prompt') and not pricing.get('completion'):
            continue

        endpoints.append({
            'provider': slug,
            'pricing': pricing,
            'data_policy': {
                'retainsPrompts': retains,
                'training': training,
            },
            'discount': discount,
            'discount_note': promo_note(promos, discount, disp_name) if discount else None,
            'stats': stats,
        })

    return endpoints


def main():
    or_path = os.path.join(DATA_DIR, 'openrouter.json')
    if not os.path.exists(or_path):
        print(f'Error: {or_path} not found. Run fetch_openrouter.py first.')
        return

    with open(or_path) as f:
        models = json.load(f)

    result = {}
    total = len(models)
    for i, m in enumerate(models):
        model_id = m['id']
        print(f'[{i+1}/{total}] {model_id}')
        endpoints = fetch_model_endpoints(model_id)
        result[model_id] = {
            'endpoints': endpoints,
            'name': m.get('name', ''),
        }

    out_path = os.path.join(DATA_DIR, 'or_endpoints.json')
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f'Saved endpoint data for {len(result)} models to {out_path}')


if __name__ == '__main__':
    main()
