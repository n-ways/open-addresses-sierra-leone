#!/bin/sh
# First start: the database volume is empty, so load the bundled registry.
# Later starts serve the database as it is (codes issued here included).
set -e
if [ ! -s "$ADDRESSES_DB" ]; then
  echo "No database at $ADDRESSES_DB: importing the bundled registry."
  python3 -m server import --registry "$REGISTRY" --db "$ADDRESSES_DB"
fi
exec python3 -m server serve --db "$ADDRESSES_DB" --port "$PORT" "$@"
