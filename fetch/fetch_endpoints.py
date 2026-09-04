#!/usr/bin/env python3
"""Fetch per-provider endpoint details for OpenRouter models.

The structured API (1.4 KB/model) is the primary source. A per-model sha1
digest of the API payload decides whether the heavy model page (417 KB) must
be re-fetched to refresh data_policy and promo notes. Unchanged models reuse
the previously written data, so daily runs only touch changed models.
"""

import hashlib
import json
import os
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
OR_BASE = 'https://openrouter.ai'
OR_API = 'https://openrouter.ai/api/v1/models'

PROMO_RE = re.compile(
    r'Limited-time\s+(\d+)%\s+discount\s+via\s+(.+?)\s+through\s+(.+?)\s*\.'
)

# Runtime stats change every run; they must not invalidate the cache.
VOLATILE_FIELDS = (
    'latency_last_30m',
    'throughput_last_30m',
    'uptime_last_30m',
    'uptime_last_5m',
    'uptime_last_1d',
)

API_WORKERS = 16
HTML_WORKERS = 8


def new_session():
    """A request session with retries for transient failures."""
    s = requests.Session()
    s.headers['User-Agent'] = 'modelpricing-bot/1.0'
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=('GET',),
    )
    s.mount('https://', HTTPAdapter(max_retries=retry))
    return s


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


def fetch_model_endpoints(model_id, session=None):
    """Fetch endpoints for a single model from its page."""
    url = f'{OR_BASE}/{model_id}'
    try:
        resp = (session or new_session()).get(url, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f'  Error fetching {model_id}: {e}')
        return []

    html = resp.text
    # Unescape the double-escaped JSON in HTML
    u = html.replace('\\\\"', '"').replace('\\"', '"')
    promos = extract_promos(u)

    # Find all dataPolicy regions. A provider may appear SEVERAL times on the
    # page (overview + providers list); only some occurrences carry the
    # runtime stats (latency/throughput). Bound each region by the next
    # dataPolicy occurrence and keep, per provider, the record with stats.
    dp_regions = [m.start() for m in re.finditer(r'"dataPolicy"', u)]
    by_slug = {}

    for i, start in enumerate(dp_regions):
        # Search backwards for the nearest slug
        before = u[max(0, start - 500):start]
        slug_match = re.findall(r'"slug"\s*:\s*"([^"]+)"', before)
        slug = slug_match[-1] if slug_match else None
        if not slug or slug == 'openrouter':
            continue

        end = dp_regions[i + 1] if i + 1 < len(dp_regions) else min(start + 40000, len(u))

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

        # Pricing and stats (search forward within this endpoint object)
        after = u[start:end]
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

        rec = {
            'provider': slug,
            'pricing': pricing,
            'data_policy': {
                'retainsPrompts': retains,
                'training': training,
            },
            'discount': discount,
            'discount_note': promo_note(promos, discount, disp_name) if discount else None,
            'stats': stats,
        }

        # Prefer the occurrence with runtime stats; otherwise keep the first.
        prev = by_slug.get(slug)
        if prev is None:
            by_slug[slug] = rec
        elif rec['stats'] and not prev['stats']:
            by_slug[slug] = rec

    return list(by_slug.values())


def fetch_api_endpoints(session, model_id):
    """Fetch the structured endpoint list for one model from the API."""
    url = f'{OR_API}/{urllib.parse.quote(model_id, safe="/")}/endpoints'
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json().get('data', {})
    return data.get('endpoints', [])


def api_digest(endpoints):
    """sha1 over the API payload, ignoring volatile runtime stats."""
    quiet = [{k: v for k, v in e.items() if k not in VOLATILE_FIELDS}
             for e in endpoints]
    raw = json.dumps(quiet, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha1(raw).hexdigest()


def fetch_all_api(models, workers=API_WORKERS):
    """Fetch the API payload for all models in parallel."""
    session = new_session()
    out = {}

    def task(m):
        model_id = m['id']
        try:
            eps = fetch_api_endpoints(session, model_id)
        except Exception as e:
            print(f'  API error {model_id}: {e}')
            return model_id, None
        return model_id, {'endpoints': eps, 'digest': api_digest(eps)}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(task, m): m['id'] for m in models}
        for i, fut in enumerate(as_completed(futs), 1):
            model_id, res = fut.result()
            out[model_id] = res
            print(f'  API [{i}/{len(models)}] {model_id}')
    return out


def fetch_all_html(model_ids, workers=HTML_WORKERS):
    """Fetch model pages for the given models in parallel."""
    session = new_session()
    out = {}

    def task(model_id):
        return model_id, fetch_model_endpoints(model_id, session)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(task, mid): mid for mid in model_ids}
        for i, fut in enumerate(as_completed(futs), 1):
            model_id, eps = fut.result()
            out[model_id] = eps
            print(f'  HTML [{i}/{len(model_ids)}] refresh {model_id}')
    return out


def main():
    or_path = os.path.join(DATA_DIR, 'openrouter.json')
    if not os.path.exists(or_path):
        print(f'Error: {or_path} not found. Run fetch_openrouter.py first.')
        return

    with open(or_path) as f:
        models = json.load(f)

    # The previous output doubles as the cache.
    out_path = os.path.join(DATA_DIR, 'or_endpoints.json')
    cache = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            cache = json.load(f)

    print(f'Fetching API endpoints for {len(models)} models...')
    api = fetch_all_api(models)

    # Only models whose API data changed need the heavy HTML page re-fetched.
    to_refresh = []
    for m in models:
        model_id = m['id']
        a = api.get(model_id)
        cached = cache.get(model_id, {})
        if a is not None and (
            not cached.get('endpoints') or cached.get('digest') != a['digest']
        ):
            to_refresh.append(model_id)

    html = {}
    if to_refresh:
        print(f'Fetching HTML pages for {len(to_refresh)} changed models...')
        html = fetch_all_html(to_refresh)

    result = {}
    reused = 0
    for m in models:
        model_id = m['id']
        a = api.get(model_id)
        cached = cache.get(model_id, {})
        if a is None:
            # API failed: keep whatever we have rather than losing data.
            result[model_id] = {
                'endpoints': cached.get('endpoints', []),
                'digest': cached.get('digest'),
            }
        elif model_id in to_refresh:
            eps = html.get(model_id)
            if not eps and cached.get('endpoints'):
                print(f'  Warning: HTML refresh failed for {model_id}, keeping cached')
                eps = cached['endpoints']
            result[model_id] = {'endpoints': eps or [], 'digest': a['digest']}
        else:
            result[model_id] = {
                'endpoints': cached.get('endpoints', []),
                'digest': cached.get('digest'),
            }
            reused += 1

    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f'Saved endpoint data for {len(result)} models to {out_path}')
    print(f'  Reused unchanged: {reused}')
    print(f'  HTML re-fetched: {len(to_refresh)}')


if __name__ == '__main__':
    main()