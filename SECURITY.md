# Security Policy

## Supported versions

Security fixes go into the latest release on the `main` branch.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Report it privately through GitHub's [private vulnerability reporting](https://github.com/ZJUCQR/CodeCinema/security/advisories/new) for this repository, with:

- what an attacker could do, and which version or commit you tested
- the smallest steps or screenplay that reproduce it

You can expect an acknowledgement within a week. Once a fix is ready, it is released and the advisory is published with credit to you, unless you prefer to stay anonymous.

## What to keep in mind

- **The local Studio** serves only on `127.0.0.1` and runs the production steps of the films in your workspace. Do not expose its port to a network.
- **Films can run code.** Production packs and renderer plugins are Python; screenplay and story files are plain data. Only run packs and plugins you trust.
- **Downloads are verified.** The sound bank and fonts that CodeCinema fetches on first use are pinned to exact files and checked against their SHA-256 hashes before use.
