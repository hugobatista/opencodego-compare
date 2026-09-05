#!/usr/bin/env python3
"""Build the final prices.json from all data sources."""

import json
import os
import re
import sys
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
FETCH_DIR = os.path.dirname(os.path.abspath(__file__))

OPENROUTER_SALES_TAX_DEFAULT = 0.2425
OPENROUTER_SERVICE_FEE = 0.055
OPENROUTER_SERVICE_FEE_MIN = 0.80

CONTEXT_RE = re.compile(r'\(\s*[<>≤=]+\s*(\d+)\s*K\s*tokens?\s*\)', re.I)


def load_json(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        print(f'Warning: {path} not found, skipping')
        return None
    with open(path) as f:
        return json.load(f)


def load_config(name):
    with open(os.path.join(FETCH_DIR, name)) as f:
        return json.load(f)


def norm_key(s):
    return ''.join(c for c in (s or '').lower() if c.isalnum())


def context_from_name(model):
    m = CONTEXT_RE.search(model or '')
    return int(m.group(1)) * 1000 if m else None


def lookup_openrouter_context(base, name_map, id_map):
    """Find an openrouter context_length for a go/zen base name.

    Mirrors the frontend rule: exact match, or prefix/containment match
    when the normalized base has 8+ alnum chars (avoids short-name clashes).
    """
    b = norm_key(base)
    if not b or len(b) < 8:
        return None
    exact = name_map.get(b) or id_map.get(b)
    if exact:
        return exact
    cand = []
    for m in (name_map, id_map):
        for k, v in m.items():
            if k in b or b in k:
                cand.append((abs(len(k) - len(b)), v))
    return min(cand)[1] if cand else None


def fill_context(rows, name_map, id_map):
    for r in rows:
        if r.get('context'):
            continue
        r['context'] = (
            context_from_name(r['model'])
            or lookup_openrouter_context(r.get('base'), name_map, id_map)
        )
    return rows


def build_opencode_go_rows(go_data, openrouter_name_ctx, openrouter_id_ctx):
    """OpenCode Go rows already have effective prices computed by the scraper."""
    return fill_context(go_data, openrouter_name_ctx, openrouter_id_ctx)


def build_opencode_zen_rows(zen_data, openrouter_name_ctx, openrouter_id_ctx):
    """OpenCode Zen rows: real = listed (no multiplier)."""
    for row in zen_data:
        row['effIn'] = row['input']
        row['effOut'] = row['output']
        row['effRead'] = row['read']
        row['effWrite'] = row['write']
    return fill_context(zen_data, openrouter_name_ctx, openrouter_id_ctx)


def build_command_code_goat_rows(goat_data, openrouter_name_ctx, openrouter_id_ctx):
    """Command Code GOAT rows already have effective prices computed by the scraper."""
    return fill_context(goat_data, openrouter_name_ctx, openrouter_id_ctx)


def build_deepinfra_rows(deepinfra_data, openrouter_name_ctx, openrouter_id_ctx):
    """DeepInfra rows: real = listed (no multiplier), like Zen."""
    for row in deepinfra_data:
        row['effIn'] = row['input']
        row['effOut'] = row['output']
        row['effRead'] = row['read']
        row['effWrite'] = row['write']
    return fill_context(deepinfra_data, openrouter_name_ctx, openrouter_id_ctx)


MODELMARKETS_BASE = 'https://modelmarkets.ai'
HUGGINGFACE_BASE = 'https://huggingface.co/'

MAKERS = load_config('makers.json')
MAKERS_NORM = {norm_key(k): v for k, v in MAKERS.items()}
MAKER_URLS = load_config('maker_urls.json')
MAKER_URLS_NORM = {norm_key(k): v for k, v in MAKER_URLS.items()}
FAMILIES = load_config('model_families.json')
FAMILIES_NORM = {norm_key(k): v for k, v in FAMILIES.items()}


def maker_lookup(key):
    return MAKERS_NORM.get(norm_key(key))


def maker_url_lookup(key):
    return MAKER_URLS_NORM.get(norm_key(key))


def pretty_noun(key):
    """'deepseek-ai' -> 'DeepSeek AI', 'meta-llama' -> 'Meta Llama'."""
    return ' '.join(w[:1].upper() + w[1:] if w else w for w in (key or '').replace('-', ' ').split()).strip()


FAMILY_VARIANT_TOKENS = ['latest', 'exp', 'preview', 'beta', 'snapshot']


def short_seg(devid):
    """'deepseek/deepseek-v4-pro-0813' -> 'deepseek-v4-pro-0813'."""
    s = (devid or '').split('/')[-1]
    return s.lstrip('~').split(',')[0].split(':')[0]


def family_stem_key(devid):
    """Norm key of a devId stripped of dates and variant tokens.

    'deepseek/deepseek-v4-pro-0813' and 'deepseek-ai/deepseek-v4-pro'
    both map to 'deepseekv4pro', so dated OR variants share the family
    mapping entry with their Go/GOAT counterparts.
    """
    seg = short_seg(devid)
    if not seg:
        return ''
    seg = re.sub(r'-\d{2,6}\b', ' ', seg)
    parts = seg.split('-')
    parts = [p for p in parts if p.lower() not in FAMILY_VARIANT_TOKENS]
    return norm_key(' '.join(parts))


def clean_model_tail(name):
    """Strip parentheticals, 'Free' and variant tokens from a display name."""
    s = re.sub(r'\s*\(.*?\)\s*', ' ', name or '')
    s = re.sub(r'\s+free\s*$', '', s, flags=re.I)
    return ' '.join(s.split()).strip()


def heuristic_family(devid, name):
    """Best-effort family name when no mapping exists.

    Keeps the source casing (OR/Go/GOAT names are already readable) and only
    strips maker prefixes, dates and variant tokens.
    """
    s = clean_model_tail(name)
    if ':' in s:
        pre, _, rest = s.partition(':')
        rest = rest.strip()
        if MAKERS_NORM.get(norm_key(pre)):
            s = rest
    s = re.sub(r'\s+\d{4}\b', ' ', s)
    for tok in FAMILY_VARIANT_TOKENS:
        s = re.sub(rf'\s+{re.escape(tok)}\s*$', '', s, flags=re.I)
    s = re.sub(r'\s{2,}', ' ', s).strip()
    return s or name.split(':')[-1].strip()


def resolve_family(row, warned):
    """Resolve model (family) for a row. Returns family or None."""
    devid = row.get('developerId')
    if devid:
        exact = FAMILIES_NORM.get(norm_key(short_seg(devid)))
        if exact:
            return exact
        fam = FAMILIES_NORM.get(family_stem_key(devid))
        if fam:
            return fam
    else:
        for cand in (row.get('base'), row.get('model')):
            if not cand:
                continue
            exact = FAMILIES_NORM.get(norm_key(cand))
            if exact:
                return exact
            stem = family_stem_key(clean_model_tail(cand))
            if stem and stem in FAMILIES_NORM:
                return FAMILIES_NORM[stem]
    name = row.get('model')
    fam = heuristic_family(devid, name)
    if devid not in warned and devid:
        print(f'Family warning: no mapping for {devid!r} -> {fam!r}',
              file=sys.stderr)
        warned.add(devid)
    elif not devid:
        marker = row.get('base') or name
        if marker not in warned:
            print(f'Family warning: no developerId for {marker!r} -> {fam!r}',
                  file=sys.stderr)
            warned.add(marker)
    return fam


def assign_variants(rows):
    """model -> family (new model), old model -> variant."""
    rows_out = []
    warned = set()
    for row in rows:
        row['variant'] = row.get('model', '')
        fam = resolve_family(row, warned)
        row['model'] = fam or row['variant']
        rows_out.append(row)
    return rows_out


def match_modelmarkets(mm_data):
    """Normalized slug -> modelmarkets entry."""
    index = {}
    for entry in mm_data or []:
        index.setdefault(norm_key(entry.get('slug')), entry)
    return index


def link_candidates(row):
    """Names to try when matching a row to a modelmarkets entry."""
    base = row.get('base') or row.get('model') or ''
    if row.get('market') == 'openrouter':
        yield re.split(r'[:,@]', base)[-1]
    else:
        name = re.sub(r'\s*\(.*?\)\s*', '', base)
        name = re.sub(r'\s+free\s*$', '', name, flags=re.I)
        yield name.strip()
    yield row.get('model') or base


def match_mm_entry(row, index):
    matched = None
    for name in link_candidates(row):
        entry = index.get(norm_key(name))
        if entry:
            matched = entry
            break
    if matched is None:
        candidates = []
        for name in link_candidates(row):
            b = norm_key(name)
            if len(b) < 8:
                continue
            for key, entry in index.items():
                if key in b or b in key:
                    candidates.append((abs(len(key) - len(b)), entry))
        if candidates:
            matched = min(candidates)[1]
    return matched


def add_model_links(rows, mm_data):
    """Set modelLink/hfLink/developerId/maker on every row via modelmarkets."""
    index = match_modelmarkets(mm_data)
    for row in rows:
        matched = match_mm_entry(row, index)
        if matched:
            row['modelLink'] = MODELMARKETS_BASE + matched['href']
            hf = matched.get('hf')
            row['hfLink'] = HUGGINGFACE_BASE + hf if hf else None
            org = matched.get('org')
            slug = matched.get('slug')
            if org and slug and row.get('market') != 'openrouter':
                row['developerId'] = f'{org}/{slug}'
            if org:
                row['maker'] = maker_lookup(org) or pretty_noun(org)
                row['makerLink'] = maker_url_lookup(org)
        else:
            row['modelLink'] = None
            row['hfLink'] = None
        row.setdefault('developerId', None)
        row.setdefault('maker', None)
        row.setdefault('makerLink', None)
        row.setdefault('variantLink', None)
    return rows


def build_openrouter_rows(openrouter_data, endpoints_data):
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

        maker = maker_lookup(model_id.split('/')[0].lstrip('~')) or maker_lookup('openrouter') or 'OpenRouter'
        maker_link = maker_url_lookup(model_id.split('/')[0].lstrip('~')) or maker_url_lookup('openrouter')

        for ep in records:
            row = {
                'market': 'openrouter',
                'model': name,
                'base': model_id,
                'developerId': model_id,
                'maker': maker,
                'makerLink': maker_link,
                'variantLink': f'https://openrouter.ai/{model_id}',
                'plan': 'OpenRouter',
                'provider': ep['provider'],
                'providerLink': f'https://openrouter.ai/provider/{ep["provider"]}',
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
    go_data = load_json('opencode-go.json')
    zen_data = load_json('opencode-zen.json')
    goat_data = load_json('command-code-goat.json')
    deepinfra_data = load_json('deepinfra.json')
    openrouter_data = load_json('openrouter.json')
    endpoints_data = load_json('or_endpoints.json')
    modelmarkets_data = load_json('modelmarkets.json')

    openrouter_name_ctx = {}
    openrouter_id_ctx = {}
    if openrouter_data:
        for m in openrouter_data:
            ctx = m.get('context_length')
            if not ctx:
                continue
            openrouter_name_ctx.setdefault(norm_key(m.get('name')), ctx)
            openrouter_id_ctx.setdefault(norm_key(m.get('id')), ctx)

    all_rows = []

    if go_data:
        all_rows.extend(build_opencode_go_rows(go_data, openrouter_name_ctx, openrouter_id_ctx))
    if goat_data:
        all_rows.extend(build_command_code_goat_rows(goat_data, openrouter_name_ctx, openrouter_id_ctx))
    if zen_data:
        all_rows.extend(build_opencode_zen_rows(zen_data, openrouter_name_ctx, openrouter_id_ctx))
    if openrouter_data:
        all_rows.extend(build_openrouter_rows(openrouter_data, endpoints_data))
    if deepinfra_data:
        all_rows.extend(build_deepinfra_rows(deepinfra_data, openrouter_name_ctx, openrouter_id_ctx))

    add_model_links(all_rows, modelmarkets_data)
    assign_variants(all_rows)

    for row in all_rows:
        row.pop('base', None)

    output = {
        'generated_date': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
        'meta': {
            'salesTaxDefault': OPENROUTER_SALES_TAX_DEFAULT,
            'openrouterServiceFee': OPENROUTER_SERVICE_FEE,
            'openrouterServiceFeeMin': OPENROUTER_SERVICE_FEE_MIN,
            'links': {
                'opencode-go': 'https://opencode.ai/docs/go',
                'command-code-goat': 'https://commandcode.ai/docs/plans/goat',
                'opencode-zen': 'https://opencode.ai/docs/zen',
                'openrouter': 'https://openrouter.ai',
                'deepinfra': 'https://deepinfra.com/pricing',
            },
            'note': 'Prices in $/1M tokens unless noted. Go effective prices assume $10/mo subscription and are realized only if the full monthly allowance is used. GOAT effective prices assume $10/mo subscription and the per-model monthly credit allowance.',
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
