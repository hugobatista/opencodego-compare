#!/usr/bin/env python3
"""Fetch modelmarkets.ai model catalog and resolve Hugging Face repos.

The models sitemap (allowed by robots.txt) lists every model URL plus its
lastmod. A cache in data/modelmarkets.json stores {org, slug, href, lastmod,
hf}; a page is only re-fetched when its lastmod changed or it is missing, so
daily runs only touch changed models. The HF repo is parsed from the page
HTML, which only links to HF for open-weight models.
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SITEMAP_URL = 'https://modelmarkets.ai/models/sitemap.xml'
MODEL_BASE = 'https://modelmarkets.ai'

HF_RE = re.compile(r'huggingface\.co/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)')
HF_SKIP_PREFIX = ('v1', 'datasets', 'spaces', 'collections', 'api', 'models')
MM_WORKERS = 8

CACHE_PATH = os.path.join(DATA_DIR, 'modelmarkets.json')


def new_session():
    s = requests.Session()
    s.headers['User-Agent'] = 'modelpricing-bot/1.0'
    return s


def norm_key(s):
    return ''.join(c for c in (s or '').lower() if c.isalnum())


def fetch_sitemap(session):
    resp = session.get(SITEMAP_URL, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'xml')
    entries = []
    for url in soup.find_all('url'):
        loc = url.find('loc')
        lastmod = url.find('lastmod')
        if loc is None:
            continue
        href = loc.get_text()
        prefix = MODEL_BASE + '/models/'
        if not href.startswith(prefix):
            continue
        rel = href[len(prefix):]
        if '/' not in rel:
            continue
        org, slug = rel.split('/', 1)
        if not org or not slug or '/' in slug:
            continue
        entries.append({
            'org': org,
            'slug': slug,
            'href': f'/models/{org}/{slug}',
            'lastmod': lastmod.get_text() if lastmod is not None else '',
        })
    return entries


def extract_hf_repo(html, slug):
    """Find the real HF repo on a model page, or None.

    Only open-weight models link to HF. We exclude CDN and non-model paths
    and prefer the repo whose name matches the page slug.
    """
    norm = norm_key(slug)
    best = None
    for repo in set(HF_RE.findall(html)):
        org, name = repo.split('/', 1)
        if org in HF_SKIP_PREFIX:
            continue
        if not name:
            continue
        if norm and norm in norm_key(repo):
            return repo
        if best is None:
            best = repo
    return best


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    session = new_session()

    cached = {}
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH) as f:
                for e in json.load(f):
                    if 'hf' in e and e.get('slug'):
                        cached[norm_key(e['slug'])] = e
        except (json.JSONDecodeError, KeyError, TypeError):
            cached = {}

    entries = fetch_sitemap(session)
    to_fetch = []
    for e in entries:
        key = norm_key(e['slug'])
        prev = cached.get(key)
        if prev is None or prev.get('lastmod') != e['lastmod']:
            to_fetch.append(e)

    fetches = 0
    failures = 0
    if to_fetch:
        def resolve(entry):
            url = MODEL_BASE + entry['href']
            try:
                resp = session.get(url, timeout=60)
                resp.raise_for_status()
                hf = extract_hf_repo(resp.text, entry['slug'])
                return {**entry, 'hf': hf}, None
            except requests.RequestException as exc:
                return {**entry, 'hf': None}, str(exc)

        with ThreadPoolExecutor(max_workers=MM_WORKERS) as pool:
            futures = [pool.submit(resolve, e) for e in to_fetch]
            for fut in as_completed(futures):
                entry, err = fut.result()
                if err:
                    failures += 1
                    print(f'Warning: failed to fetch {entry["href"]}: {err}')
                    continue
                cached[norm_key(entry['slug'])] = entry
                fetches += 1

    # Keep sitemap order; drop stale slugs no longer listed. Slugs whose
    # fetch failed this run keep their previous good data, or are omitted
    # entirely so the next run retries them.
    output = []
    for e in entries:
        key = norm_key(e['slug'])
        prev = cached.get(key)
        if prev is not None:
            output.append(prev)

    with open(CACHE_PATH, 'w') as f:
        json.dump(output, f, indent=2)
    print(f'Saved {len(output)} modelmarkets models to {CACHE_PATH} '
          f'({fetches} fetched, {failures} failed)')


if __name__ == '__main__':
    main()