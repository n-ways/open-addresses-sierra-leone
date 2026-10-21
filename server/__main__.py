"""Command line: import, serve, export.

  python3 -m server import --registry registry --db data/addresses.sqlite
  python3 -m server serve  --db data/addresses.sqlite --port 8080
  python3 -m server export --db data/addresses.sqlite --out out/registry

Configuration may also come from the environment: ADDRESSES_DB, PORT, HOST,
ISSUE_KEYS (comma-separated bearer keys; none means read-only), ISSUE_PER_DAY,
CORS_ORIGINS (comma-separated, or *), REGISTRY.
"""
import argparse
import os
import sys

from . import api, store
from .engine import REPO


def _env_list(name):
    return [x.strip() for x in os.environ.get(name, '').split(',') if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python3 -m server', description='N-Ways Addressing for Sierra Leone: registry server.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    db_default = os.environ.get('ADDRESSES_DB', 'data/addresses.sqlite')

    p = sub.add_parser('import', help='load the published registry into a new database')
    p.add_argument('--registry', default=os.environ.get('REGISTRY', os.path.join(REPO, 'registry')))
    p.add_argument('--db', default=db_default)
    p.add_argument('--register', default=os.path.join(REPO, 'engine', 'data', 'register.json'),
                   help='the frozen register (engine/data/register.json)')
    p.add_argument('--force', action='store_true', help='replace a database that holds codes not yet exported')

    p = sub.add_parser('serve', help='serve the API')
    p.add_argument('--db', default=db_default)
    p.add_argument('--host', default=os.environ.get('HOST', '0.0.0.0'))
    p.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8080')))
    p.add_argument('--issue-per-day', type=int, default=int(os.environ.get('ISSUE_PER_DAY', '5')))

    p = sub.add_parser('export', help='write the registry in the published format')
    p.add_argument('--db', default=db_default)
    p.add_argument('--out', required=True)

    a = ap.parse_args(argv)
    if a.cmd == 'import':
        try:
            store.import_registry(a.registry, a.db, a.register, force=a.force)
        except store.RegistryError as e:
            print(f'import refused: {e}', file=sys.stderr)
            return 2
    elif a.cmd == 'serve':
        if not os.path.exists(a.db):
            print(f'{a.db} does not exist: run "python3 -m server import" first', file=sys.stderr)
            return 2
        cfg = api.Config(a.db, port=a.port, host=a.host, issue_keys=_env_list('ISSUE_KEYS'), issue_per_day=a.issue_per_day,
                         cors_origins=_env_list('CORS_ORIGINS'))
        api.serve(cfg)
    elif a.cmd == 'export':
        if not os.path.exists(a.db):
            print(f'{a.db} does not exist', file=sys.stderr)
            return 2
        store.export_registry(store.connect(a.db), a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
