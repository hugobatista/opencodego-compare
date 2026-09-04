#!/usr/bin/env python3
"""Run the full data pipeline in sequence."""

import subprocess
import sys
import os

SCRIPTS = [
    'fetch_openrouter.py',
    'fetch_endpoints.py',
    'scrape_go.py',
    'scrape_zen.py',
    'build_json.py',
]


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for script in SCRIPTS:
        path = os.path.join(script_dir, script)
        print(f'\n=== Running {script} ===')
        result = subprocess.run([sys.executable, path], cwd=script_dir)
        if result.returncode != 0:
            print(f'Error: {script} failed with code {result.returncode}')
            sys.exit(1)
    print('\n=== Pipeline complete ===')


if __name__ == '__main__':
    main()
