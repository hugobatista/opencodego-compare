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

BENCHMARK_FIELDS = ('intelligence', 'coding', 'agentic')


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


def build_benchmark_index(openrouter_data):
    """Normalized id/name -> benchmarks dict from OpenRouter data."""
    index = {}
    for m in openrouter_data or []:
        bm = m.get('benchmarks')
        if not bm:
            continue
        mid = m.get('id', '')
        keys = {
            norm_key(mid),
            norm_key(mid.split('/')[-1].split(':')[0]),
            norm_key(or_model_part(m.get('name'))),
        }
        for k in keys:
            if k:
                index.setdefault(k, bm)
    return index


def fill_benchmarks(rows, bm_index):
    """Propagate intelligence/coding/agentic to non-OpenRouter rows via developerId."""
    for r in rows:
        if r.get('market') == 'openrouter':
            continue
        devid = r.get('developerId')
        if not devid:
            continue
        b = norm_key(devid.split('/')[-1].split(':')[0])
        bm = bm_index.get(b)
        if not bm and len(b) >= 8:
            for k, v in bm_index.items():
                if k in b or b in k:
                    bm = v
                    break
        if bm:
            for f in BENCHMARK_FIELDS:
                if f in bm and bm[f] is not None:
                    r[f] = bm[f]


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


def build_subscription_rows(data, openrouter_name_ctx, openrouter_id_ctx):
    """Command Code Pro/Max rows already have effective prices computed by the scraper."""
    return fill_context(data, openrouter_name_ctx, openrouter_id_ctx)


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
PLANS = load_config('plans.json')
CATALOG_OVERRIDES = load_config('catalog_overrides.json')
CATALOG_OVERRIDES_NORM = {norm_key(k): v for k, v in CATALOG_OVERRIDES.items()}
OR_PROVIDER_NAMES = PLANS['gateways'].get('openrouter', {}).get('providers', {})


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


def assign_gateway(row, templates):
    """Set row['gateway'] (and provider display) from the plan's gateway.

    OpenRouter rows already set gateway/provider in the builder. For the
    other markets the provider is the gateway's own disclosed provider
    (deepinfra -> DeepInfra) or empty when undisclosed (opencode, command-code).
    """
    if row.get('gateway'):
        return row
    plan_key = row.get('market')
    plan = templates['plans'].get(plan_key) or {}
    gw = templates['gateways'].get(plan.get('gateway') or '') or {}
    row['gateway'] = plan.get('gateway')
    providers = gw.get('providers') or {}
    if len(providers) == 1:
        row['provider'] = next(iter(providers.values()))
        row['providerLink'] = gw.get('providerLink')
    return row


def assign_variants(rows):
    """model -> family (new model), old model -> variant.

    Rows may carry an explicit `variant` (e.g. DeepInfra Priority/Flex
    suffixes), which is preserved; otherwise the model name becomes the
    variant and the family overrides it.
    """
    rows_out = []
    warned = set()
    for row in rows:
        if row.get('variant') is None:
            row['variant'] = row.get('model', '')
        fam = resolve_family(row, warned)
        row['model'] = fam or row['variant']
        rows_out.append(row)
    return rows_out


def clean_model_name(name):
    """Strip parentheticals and trailing 'Free' for name matching."""
    s = re.sub(r'\s*\(.*?\)\s*', '', name or '')
    s = re.sub(r'\s+free\s*$', '', s, flags=re.I)
    return ' '.join(s.split()).strip()


def or_model_part(name):
    """'Xiaomi: MiMo-V2.5' -> 'MiMo-V2.5'. Returns name unchanged if no maker prefix."""
    if ': ' in (name or ''):
        return name.split(': ', 1)[-1].strip()
    return name


def or_model_org(model_id):
    """'~z-ai/glm-latest' -> 'z-ai'; 'xiaomi/mimo-v2.5' -> 'xiaomi'."""
    seg = (model_id or '').split('/')[0]
    return seg.lstrip('~').split(':')[0].split(',')[0]


def build_or_identity_index(openrouter_data):
    """Normalized name/id -> {model_id, org, hf} for OpenRouter matching."""
    index = {}
    for m in openrouter_data or []:
        mid = m.get('id', '')
        rec = {'model_id': mid, 'org': or_model_org(mid), 'hf': m.get('hugging_face_id')}
        keys = {
            norm_key(or_model_part(m.get('name'))),
            norm_key(mid),
            norm_key(mid.split('/')[-1].split(':')[0]),
        }
        for k in keys:
            if k:
                index.setdefault(k, rec)
    return index


def _or_exact_or_closest(index, b):
    if not b:
        return None
    if b in index:
        return index[b]
    if len(b) < 8:
        return None
    cand = []
    for k, v in index.items():
        if k in b or b in k:
            cand.append((abs(len(k) - len(b)), v))
    return min(cand, key=lambda t: t[0])[1] if cand else None


def build_di_org_index(deepinfra_data):
    """Normalized base/model -> org slug from the DeepInfra variantLink."""
    index = {}
    for r in deepinfra_data or []:
        parts = (r.get('variantLink') or '').split('/')
        if len(parts) <= 4:
            continue
        org = parts[3]
        for name in (r.get('base'), r.get('model')):
            if name:
                index.setdefault(norm_key(name), org)
    return index


def match_modelmarkets(mm_data):
    """Normalized slug -> modelmarkets entry (used only for hfLink/modelMarketsLink)."""
    index = {}
    for entry in mm_data or []:
        index.setdefault(norm_key(entry.get('slug')), entry)
    return index


def _mm_closest(mm_index, b):
    if not b:
        return None
    if b in mm_index:
        return mm_index[b]
    if len(b) < 8:
        return None
    cand = []
    for k, v in mm_index.items():
        if k in b or b in k:
            cand.append((abs(len(k) - len(b)), v))
    return min(cand, key=lambda t: t[0])[1] if cand else None


def identity_for_row(row, or_index, di_index, mm_index):
    """Resolve maker/links for a row across the layered sources.

    Layer 4: catalog_overrides.json (anything) — manual override, highest authority.
    Layer 1: OpenRouter (maker, makerLink, hf) — primary, daily.
    Layer 2: DeepInfra org (maker, makerLink) — covers DI fine-tunes.
    Layer 3: modelmarkets (hfLink/modelMarketsLink only) — fallback for HF gaps.
    Returns a dict of resolved fields (possibly empty).
    """
    base = row.get('model') or row.get('base') or ''
    b = norm_key(clean_model_name(base))
    market = row.get('market')
    out = {}
    if market == 'openrouter':
        rec = or_index.get(norm_key(or_model_part(base))) or or_index.get(norm_key(base))
        if rec:
            out['maker'] = maker_lookup(rec['org']) or \
                (or_model_part(base).split()[0] if ' ' in base else None)
            out['makerLink'] = maker_url_lookup(rec['org'])
            out['developerId'] = rec['model_id']
            out['variantLink'] = f'https://openrouter.ai/{rec["model_id"]}'
            if rec['hf']:
                out['hfLink'] = HUGGINGFACE_BASE + rec['hf']
        o = CATALOG_OVERRIDES_NORM.get(norm_key(clean_model_name(or_model_part(base)))) or \
            CATALOG_OVERRIDES_NORM.get(norm_key(row.get('base') or ''))
        if o and 'hfLink' in o and 'hfLink' not in out:
            out['hfLink'] = o['hfLink']
        if o and 'modelMarketsLink' in o and 'modelMarketsLink' not in out:
            out['modelMarketsLink'] = o['modelMarketsLink']
        mm = _mm_closest(mm_index, norm_key(clean_model_name(or_model_part(base))))
        if mm is None and row.get('base'):
            seg = row['base'].split('/')[-1].split(':')[0]
            seg = norm_key(seg)
            if seg in mm_index:
                mm = mm_index[seg]
        if mm and mm.get('hf') and 'hfLink' not in out:
            out['hfLink'] = HUGGINGFACE_BASE + mm['hf']
        if not row.get('modelMarketsLink') and mm:
            out['modelMarketsLink'] = MODELMARKETS_BASE + mm['href']
        return out

    # L4 static override first (highest authority) — match on both the raw
    # base alias (e.g. DeepInfra 'gemma-4-E4B-it') and the cleaned name.
    o = CATALOG_OVERRIDES_NORM.get(b) or CATALOG_OVERRIDES_NORM.get(norm_key(row.get('base') or ''))
    if o:
        if 'org' in o:
            out['maker'] = o.get('maker') or maker_lookup(o['org']) or pretty_noun(o['org'])
            out['makerLink'] = o.get('makerLink') or maker_url_lookup(o['org'])
        if 'hfLink' in o:
            out['hfLink'] = o['hfLink']
        if 'modelMarketsLink' in o:
            out['modelMarketsLink'] = o['modelMarketsLink']
        return out

    # L1 OpenRouter
    rec = _or_exact_or_closest(or_index, b)
    if rec:
        out['maker'] = maker_lookup(rec['org']) or pretty_noun(rec['org'])
        out['makerLink'] = maker_url_lookup(rec['org'])
        out['developerId'] = f"{rec['org']}/{rec['model_id'].split('/')[-1].split(':')[0]}"
        out['variantLink'] = f'https://openrouter.ai/{rec["model_id"]}'
        if rec['hf']:
            out['hfLink'] = HUGGINGFACE_BASE + rec['hf']

    # L2 DeepInfra org (only fills maker/developerId if still missing)
    if 'maker' not in out:
        dorg = di_index.get(b)
        if dorg:
            out['maker'] = maker_lookup(dorg) or pretty_noun(dorg)
            out['makerLink'] = maker_url_lookup(dorg)
            out['developerId'] = f'{dorg}/{base}'

    # L3 modelmarkets — fallback ONLY for hfLink/modelMarketsLink, never maker
    mm = _mm_closest(mm_index, b)
    if mm:
        if 'hfLink' not in out and mm.get('hf'):
            out['hfLink'] = HUGGINGFACE_BASE + mm['hf']
        out['modelMarketsLink'] = MODELMARKETS_BASE + mm['href']

    return out


def add_model_links(rows, mm_data, openrouter_data, deepinfra_data):
    """Set maker/links/developerId on every row via layered sources.

    OpenRouter rows keep the maker/developerId/variantLink set by their
    builder; here they only gain hfLink/modelMarketsLink. All other rows get the
    full identity resolved across the layered sources.
    """
    or_index = build_or_identity_index(openrouter_data)
    di_index = build_di_org_index(deepinfra_data)
    mm_index = match_modelmarkets(mm_data)
    unresolved = []
    for row in rows:
        if row.get('market') == 'openrouter':
            ident = identity_for_row(row, or_index, di_index, mm_index)
            if ident.get('hfLink'):
                row['hfLink'] = ident['hfLink']
            if ident.get('modelMarketsLink'):
                row['modelMarketsLink'] = ident['modelMarketsLink']
            continue
        ident = identity_for_row(row, or_index, di_index, mm_index)
        if ident:
            row.setdefault('maker', ident.get('maker'))
            row.setdefault('makerLink', ident.get('makerLink'))
            row.setdefault('developerId', ident.get('developerId'))
            row.setdefault('hfLink', ident.get('hfLink'))
            row.setdefault('modelMarketsLink', ident.get('modelMarketsLink'))
            row.setdefault('variantLink', ident.get('variantLink'))
        else:
            row.setdefault('maker', None)
            row.setdefault('makerLink', None)
            row.setdefault('developerId', None)
            row.setdefault('hfLink', None)
            row.setdefault('modelMarketsLink', None)
            row.setdefault('variantLink', None)
            unresolved.append({
                'market': row.get('market'),
                'model': row.get('model'),
                'base': row.get('base'),
            })
    if unresolved:
        print(f'Identity warning: {len(unresolved)} rows unresolved', file=sys.stderr)
        with open(os.path.join(DATA_DIR, 'unmapped.json'), 'w') as f:
            json.dump({'generated_date': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
                       'rows': unresolved}, f, indent=2)
    elif os.path.exists(os.path.join(DATA_DIR, 'unmapped.json')):
        os.remove(os.path.join(DATA_DIR, 'unmapped.json'))
    return rows


def or_provider_name(slug):
    """Display name for an OpenRouter endpoint provider slug.

    'azure/us' -> 'Azure (us)'; unknown bases fall back to 'pretty_noun'.
    """
    base, sep, suffix = (slug or '').partition('/')
    name = OR_PROVIDER_NAMES.get(base) or pretty_noun(base)
    return f'{name} ({suffix})' if sep else name


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

        bm = model.get('benchmarks') or {}

        for ep in records:
            row = {
                'market': 'openrouter',
                'gateway': 'openrouter',
                'model': name,
                'base': model_id,
                'developerId': model_id,
                'maker': maker,
                'makerLink': maker_link,
                'variantLink': f'https://openrouter.ai/{model_id}',
                'plan': 'OpenRouter',
                'provider': or_provider_name(ep['provider']),
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
                'privacyNote': '',
                'notes': '',
                'intelligence': bm.get('intelligence'),
                'coding': bm.get('coding'),
                'agentic': bm.get('agentic'),
            }
            if ep['discount']:
                note = ep.get('discount_note') or f'{ep["discount"]*100:.0f}% off'
                row['notes'] = note
            rows.append(row)

    return rows


def build_note(plans):
    """Describe each plan's pricing formula from plans.json config."""
    bits = ['Prices in $/1M tokens unless noted.']
    for key, p in plans['plans'].items():
        if p.get('subPrice'):
            bits.append(
                f"{p['name']} effective = listed × ({p['subPrice']} ÷ monthly "
                'credit allowance), realized only if the full monthly allowance is used.'
            )
        elif p.get('feeTax'):
            bits.append(f"{p['name']} real = listed × (1 + service fee) × (1 + tax).")
        else:
            bits.append(f"{p['name']} real = listed.")
    return ' '.join(bits)


def main():
    go_data = load_json('opencode-go.json')
    zen_data = load_json('opencode-zen.json')
    goat_data = load_json('command-code-goat.json')
    pro_data = load_json('command-code-pro.json')
    max_data = load_json('command-code-max.json')
    deepinfra_data = load_json('deepinfra.json')
    openrouter_data = load_json('openrouter.json')
    endpoints_data = load_json('openrouter-endpoints.json')
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
    if pro_data:
        all_rows.extend(build_subscription_rows(pro_data, openrouter_name_ctx, openrouter_id_ctx))
    if max_data:
        all_rows.extend(build_subscription_rows(max_data, openrouter_name_ctx, openrouter_id_ctx))
    if zen_data:
        all_rows.extend(build_opencode_zen_rows(zen_data, openrouter_name_ctx, openrouter_id_ctx))
    if openrouter_data:
        all_rows.extend(build_openrouter_rows(openrouter_data, endpoints_data))
    if deepinfra_data:
        all_rows.extend(build_deepinfra_rows(deepinfra_data, openrouter_name_ctx, openrouter_id_ctx))

    for row in all_rows:
        assign_gateway(row, PLANS)

    add_model_links(all_rows, modelmarkets_data, openrouter_data, deepinfra_data)
    assign_variants(all_rows)

    bm_index = build_benchmark_index(openrouter_data)
    for r in all_rows:
        for f in BENCHMARK_FIELDS:
            r.setdefault(f, None)
    fill_benchmarks(all_rows, bm_index)

    for row in all_rows:
        row.pop('base', None)

    output = {
        'generated_date': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
        'meta': {
            'salesTaxDefault': OPENROUTER_SALES_TAX_DEFAULT,
            'openrouterServiceFee': OPENROUTER_SERVICE_FEE,
            'openrouterServiceFeeMin': OPENROUTER_SERVICE_FEE_MIN,
            'gateways': PLANS['gateways'],
            'plans': PLANS['plans'],
            'note': build_note(PLANS),
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
