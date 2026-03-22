# Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository and create a branch from `main`.
2. Make your changes, keeping one class per file under `src/`.
3. Add or update tests in `tests/` — unit, integration, and benchmark as appropriate.
4. Run the full suite locally before opening a PR:
   ```bash
   make test
   ```
5. Ensure docs build cleanly:
   ```bash
   make docs
   ```
6. Open a pull request against `main` with a clear description of the change.

All PRs must pass the GitHub Actions CI checks before merging.
