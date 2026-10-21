# Security and data problems

Report a security problem, or personal data found anywhere in this repository or in a deployment of its server, by email to **hello@nways.ng**, with "Security" in the subject. Do not open a public issue for it.

Say what you found, where (file, endpoint or URL), and how to reproduce it. We acknowledge a report within three working days, keep you informed until it is resolved, and credit you if you wish.

In scope:

- the registry server (`server/`): authentication of issuing keys, input handling, anything that lets a client issue, change or retire codes without a valid key, or read anything beyond the published registry;
- the published data (`registry/`, `model/`, `engine/data/`): anything that identifies a person, an occupant or a household, which the registry must never hold;
- the reference engine and tools, where a defect could give two compounds one code or one compound two.

Operators of a deployment are responsible for its host, its TLS certificate and its keys (`server/README.md`). Keep `ISSUE_KEYS` secret, give each client its own key, and replace a key at once if it may have leaked.
