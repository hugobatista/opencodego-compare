#!/usr/bin/env python3
"""Run the full data pipeline. Stage 1 fetchers run in parallel."""

import subprocess
import sys
import os

STAGE1 = [
    'fetch_openrouter.py',
    'scrape_go.py',
    'scrape_zen.py',
    'fetch_modelmarkets.py',
]
STAGE2 = [
    'fetch_endpoints.py',
    'build_json.py',
]


def run(script, script_dir):
    path = os.path.join(script_dir, script)
    print(f'\n=== Running {script} ===')
    result = subprocess.run([sys.executable, path], cwd=script_dir)
    if result.returncode != 0:
        print(f'Error: {script} failed with code {result.returncode}')
        sys.exit(1)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Stage 1: fetch_openrouter must finish before fetch_endpoints, but the
    # three fetchers themselves are independent of each other.
    print('=== Stage 1: fetching independent sources (parallel) ===')
    procs = {
        s: subprocess.Popen(
            [sys.executable, os.path.join(script_dir, s)],
            cwd=script_dir,
        )
        for s in STAGE1
    }
    for s, p in procs.items():
        p.wait()
    failed = [(s, p.returncode) for s, p in procs.items() if p.returncode != 0]
    if failed:
        for s, rc in failed:
            print(f'Error: {s} failed with code {rc}')
        sys.exit(1)
    print('=== Stage 1 complete ===')

    for script in STAGE2:
        run(script, script_dir)
    print('\n=== Pipeline complete ===')


if __name__ == '__main__':
    main()