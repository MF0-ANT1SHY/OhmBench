#!/usr/bin/env python3
"""Batch-collector hook: install the signed browser HAP and replace its test history."""
import argparse
import hashlib
import json
import os
import subprocess
import time
import uuid
import zipfile
from pathlib import Path

BUNDLE = 'com.example.nanvision'
DB = f'/data/app/el2/100/database/{BUNDLE}/entry/rdb/Histories.db'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('case')
    ap.add_argument('variant', choices=['fixed', 'unfixed'])
    ap.add_argument('round', type=int)
    ap.add_argument('serial')
    args = ap.parse_args()
    assets = Path(os.environ['OHM_BROWSER_ASSETS']) / args.case
    database = assets / 'Histories.db'
    hap = assets / args.variant / 'app.hap'
    with zipfile.ZipFile(hap) as archive:
        if json.loads(archive.read('module.json'))['app']['bundleName'] != BUNDLE:
            ap.error('HAP is not the browser benchmark app')
    digest = hashlib.sha256(database.read_bytes()).hexdigest()

    def hdc(*command):
        return subprocess.check_output(['hdc', '-t', args.serial, *command], text=True,
                                       encoding='utf-8', errors='replace', timeout=120)

    install = hdc('install', '-r', str(hap))
    if 'install bundle successfully' not in install:
        raise RuntimeError(install.strip())
    if hdc('shell', f'test -f {DB} && echo READY').strip() != 'READY':
        hdc('shell', f'aa start -b {BUNDLE} -a EntryAbility')
        for _ in range(30):
            if hdc('shell', f'test -f {DB} && echo READY').strip() == 'READY':
                break
            time.sleep(1)
        else:
            raise RuntimeError('first launch did not initialize the browser database')

    staged = '/data/local/tmp/ohm-history-' + uuid.uuid4().hex
    try:
        hdc('file', 'send', str(database), staged)
        if hdc('shell', f'sha256sum {staged}').split()[:1] != [digest]:
            raise RuntimeError('device fixture does not match host fixture')
        hdc('shell', f'aa force-stop {BUNDLE}')
        for _ in range(20):
            if not hdc('shell', f'pidof {BUNDLE}').strip():
                break
            time.sleep(.25)
        else:
            raise RuntimeError('browser is still running')
        # Keep the owner, permissions and security label of the initialized file.
        result = hdc('shell', f'rm -f {DB}-wal {DB}-shm {DB}-dwr {DB}-compare {DB}-journal'
                     f' && cat {staged} > {DB} && sha256sum {DB}')
        if result.split()[:1] != [digest]:
            raise RuntimeError('browser database was not restored')
        print(f'{args.case}/{args.variant}, round {args.round}: fixture {digest}')
    finally:
        hdc('shell', f'rm -f {staged}')


if __name__ == '__main__':
    main()
