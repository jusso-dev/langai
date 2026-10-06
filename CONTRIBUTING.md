# Contributing

Use synthetic fixture identifiers, never community dictionaries or invented Indigenous vocabulary. Do not attach private uploads, database dumps, model artifacts, credentials or screenshots of private content to issues or pull requests.

Start with the [developer setup](README.md#developer-setup). Keep the web, HTTP API and ML interfaces independent. Update immutable dataset generation versions when sample-generation behavior changes. Use a new database migration for schema changes. Every generated example must preserve its source entry IDs, and all contributing dictionary entries must stay in the same split.

Before submitting:

```sh
uv sync --frozen --extra ml --extra dev
uv run --no-sync ruff check apps ml cli tests scripts
uv run --no-sync ruff format --check apps ml cli tests scripts
uv run --no-sync pytest -q
cd apps/web
npm ci
npm run typecheck
npm run build
```

Container and browser integration checks run in CI. To reproduce locally, follow [verification](docs/verification.md). Tests must assert real behavior, not fabricated training metrics. Report any model-performance claim with its dataset permissions, provenance, split strategy, baseline and held-out sample counts.

Code contributions are under the repository's MIT licence. Dictionary content, community knowledge and downloaded foundation models retain their own ownership, permissions and licences; the repository licence does not relicense them.
