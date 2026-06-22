# Contributing to cachepot

Thank you for your interest in contributing to cachepot, a Python cache library with type hints.

## Development Setup

```bash
git clone https://github.com/kitsuyui/cachepot.git
cd cachepot
uv sync
lefthook install   # install pre-commit and pre-push hooks
```

The project uses [lefthook](https://lefthook.dev/) to run the same checks as CI locally.

## Running Tests and Checks

```bash
uv run poe check   # lint, type check, format check
uv run poe test    # run tests
```

Or let the hooks run automatically when you commit/push.

## Submitting a Pull Request

1. Fork the repository and create a topic branch from `main`.
2. Make your changes. Keep each PR focused on one change.
3. Ensure `uv run poe check` and `uv run poe test` pass.
4. Open a pull request against `main` using the provided template.

Commits should follow the `fix:`, `feat:`, `docs:`, `chore:` prefix convention.

## Reporting Bugs

Use the bug report issue template. Include your Python version, OS, and steps to reproduce.

## Security Vulnerabilities

See [SECURITY.md](SECURITY.md) for the disclosure process. Do not open a public issue with exploit details.

## Code Style

This project uses `ruff` for linting and formatting. Run `uv run poe check` to verify before submitting.

## License

By contributing, you agree that your contributions will be licensed under the BSD-3-Clause license.
