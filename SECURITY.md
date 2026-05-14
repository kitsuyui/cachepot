# Security Policy

## Supported Versions

Security fixes are handled for the latest released version and the default
branch. Please upgrade to the latest release before reporting an issue when
possible.

| Version | Supported |
| --- | --- |
| Latest release | Yes |
| Default branch | Best effort |
| Older releases | No |

## Reporting a Vulnerability

Please do not open a public issue for suspected vulnerabilities.

Use GitHub private vulnerability reporting for this repository when it is
available. If it is not available, email the maintainer at
`kitsuyui+github@kitsuyui.com` before sharing technical details publicly.

Please include:

- The affected version or commit.
- Reproduction steps or a minimal proof of concept.
- The expected impact.
- Relevant environment details.

Reports involving serializers or cache backends should also describe whether
the cached data, cache key, storage location, or backend connection can be
influenced by an untrusted party.

The maintainer will acknowledge valid reports as soon as practical and will
coordinate a fix, release, or advisory when needed.
