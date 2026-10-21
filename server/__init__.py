"""N-Ways Addressing for Sierra Leone: the registry server.

A small HTTP service that serves the published registry (``registry/``) and,
where a deployment is the designated issuer, issues new codes by the same
rules as the national issuer. Standard library only; see ``server/README.md``.
"""

COUNTRY = 'SL'
COUNTRY_NAME = 'Sierra Leone'
SPEC = '1.0'
