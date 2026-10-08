# LangAI

[![Verify MVP](https://github.com/jusso-dev/langai/actions/workflows/ci.yml/badge.svg)](https://github.com/jusso-dev/langai/actions/workflows/ci.yml)

A private dictionary training platform for language stewards and ML practitioners. Upload a dictionary, inspect its canonical entries, approve a dataset, train and evaluate a model, then explicitly approve and deploy it behind an authenticated API.

**A dictionary provides lexical knowledge, not conversational fluency.** V1 focuses on dictionary retrieval, semantic representations, spelling relationships and optional language identification. It does not include a learning game or chatbot.

## Start the container stack

Requirements: Docker Compose, at least 8 GB available RAM, and space for model downloads. GPU is optional. The default multilingual encoder runs on CPU; first use downloads its pinned weights.

```sh
git clone https://github.com/jusso-dev/langai.git
cd langai
python3 scripts/setup_env.py
LANGAI_GIT_COMMIT=$(git rev-parse HEAD) docker compose up --build -d
```

Open **http://localhost:3100**. Connect using `LANGAI_BOOTSTRAP_TOKEN` from the generated `.env` file. OpenAPI is at **http://localhost:8100/docs**. Use **Settings → Workspace API keys** to create revocable viewer/editor keys. Bootstrap secrets are never embedded in the web bundle.

Run Compose against your intended Docker context. Published development ports bind to loopback. PostgreSQL uses port 55439, Redis 56379, and S3 object storage 59000 (console 59001). Existing services are not modified. See [operations](docs/operations.md) for production configuration, offline model preparation, backups and worker recovery.

## The workflow

1. **Create a language.** Capture alternate names, optional ISO code, orthography, dialect, community and governance context.
2. **Upload a dictionary.** CSV, TSV, XLSX, JSON and delimited TXT are supported. Record owner, custodian, source, licence and training permission. Private is the only visibility exposed in V1.
3. **Map and preview.** Confirm the suggested word/meaning columns. Inspect proposed NFC/whitespace changes; source text, case, apostrophes and diacritics remain preserved. Multiple definitions/variants use JSON arrays; punctuation is never guessed to be a separator.
4. **Review and approve.** Inspect duplicates, missing values, suspicious Unicode, malformed or long rows. Flagged entries stay out unless explicitly included. Approval freezes the source.
5. **Create a dataset.** Select approved sources. Immutable snapshots include canonical entries, governance, every generated view and the deterministic group split manifest.
6. **Train.** Auto selects multilingual contrastive embeddings and conservative CPU parameters. Inspect advanced overrides, live logs and actual metrics. Language identification needs a separately approved negative corpus. Experimental LoRA must be enabled by the owner.
7. **Evaluate and test.** Inspect held-out baseline versus fine-tuned results. The playground works before deployment.
8. **Approve, then deploy.** Only an owner can do this. Deployment builds headword, definition and combined-entry vectors, then atomically switches the active model.
9. **Query.** All inference endpoints require a key and an explicit language. A request cannot silently choose or mix languages.

## Offline dictionary on iPhone

For word and phrase mapping, open **Offline phone**, export approved sources,
then install the linked dictionary web app on the iPhone Home Screen and import
the pack from Files. Exact lookup, variants, reverse lookup and labelled spelling/
phrase suggestions run entirely on the phone after setup. No LLM or training job
is needed. The workspace still requires connectivity; the separate offline app
requires HTTPS for installation. See [setup, matching rules and privacy](docs/offline-dictionary.md).

## Repository

```text
apps/web/                 Next.js 16, React, TypeScript, Tailwind; real API-backed screens
apps/api/                 FastAPI, typed inputs, auth, imports, datasets, registry and inference
apps/worker/              durable PostgreSQL outbox, Redis/RQ dispatcher and isolated worker processes
ml/datasets/              lossless importers, normalization, grouping and dataset views
ml/encoders/              pluggable Sentence Transformer and test-only PyTorch encoder
ml/classifiers/           character n-gram logistic regression and linear SVM
ml/generative/            opt-in local LoRA dictionary experiment
ml/trainers/              contrastive training, validation selection and early stopping
ml/evaluation/            held-out retrieval metrics and similarity distributions
ml/inference/             hash-verified private artifact cache
packages/sdk-python/      small synchronous Python SDK
packages/schemas/         exported OpenAPI and canonical JSON schemas
cli/                      langai CLI, using the same backend HTTP API
infra/                    Dockerfiles and versioned Alembic migrations
scripts/                  setup, schema export, local integration exercises
tests/                   parsing, leakage, jobs, loading, inference and authorization tests
```

## Developer setup

```sh
uv sync --python 3.12 --extra ml --extra dev
cd apps/web && npm ci && cd ../..
# Start only the backing services in the intended Docker context:
docker compose up -d postgres redis object-store
uv run python scripts/init_storage.py
uv run alembic upgrade head
# In separate terminals:
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8100
uv run python -m apps.worker.main --dispatch
uv run python -m apps.worker.main
cd apps/web && npm run dev
```

For SQLite/local-file development, override `LANGAI_DATABASE_URL=sqlite:///./data/langai.db`, `LANGAI_STORAGE_BACKEND=local`, then run `uv run python scripts/init_local.py`. PostgreSQL/pgvector is the production path. The NumPy search fallback exists only for local testing.

```sh
uv run --extra ml --extra dev pytest -q
uv run --extra dev ruff check apps ml cli tests scripts
cd apps/web && npm run typecheck && npm run build
```

Tests isolate their database and object store automatically. They use clearly synthetic identifiers and a download-free PyTorch encoder, never invented Indigenous vocabulary. To exercise real PostgreSQL, S3, Redis/RQ and pgvector with running services, run `scripts/integration_smoke.py` after enabling `LANGAI_ALLOW_TEST_ENCODER=true` **only for that local verification API**. `scripts/primary_smoke.py` runs the complete workflow on the actual multilingual encoder. Add `--adapter` to also verify the explicitly enabled full LoRA experiment. Both scripts create fresh synthetic fixtures; neither consumes a real dictionary. [Verification notes](docs/verification.md) distinguish measured checks from untested configurations.

## Python SDK

```sh
uv pip install -e packages/sdk-python
export LANGAI_API_KEY='your-viewer-key'
```

```python
from language_ai import Client

with Client(base_url="http://localhost:8100") as client:
    results = client.search(language="muruwari", query="water")
    vectors = client.embed(language="muruwari", texts=["water"])
```

The SDK also supports import, approval, dataset creation, training, evaluation and deployment. SDK import stops at review; it never approves a source automatically.

## CLI

```sh
export LANGAI_API_URL=http://localhost:8100
export LANGAI_API_KEY='your-editor-key'
langai language create muruwari
langai dictionary import dictionary.csv --language muruwari --governance permission.json
langai dictionary review SOURCE_ID
langai dictionary approve SOURCE_ID
langai dataset create --language muruwari --source SOURCE_ID
langai train --language muruwari --task embeddings
langai status RUN_ID
langai logs RUN_ID
langai models --language muruwari
langai evaluate MODEL_ID
# Use an owner key for the next two operations:
langai approve MODEL_ID
langai deploy MODEL_ID
langai search --language muruwari water
```

`permission.json`:

```json
{
  "owner": "The dictionary owner",
  "custodian": "The authorised custodian",
  "source": "Your source reference",
  "licence": "Your documented permission terms",
  "training_allowed": true,
  "commercial_use_allowed": false,
  "redistribution_allowed": false,
  "attribution": "Required attribution"
}
```

Grant permission only where it actually exists. `langai request METHOD /path --body request.json` exposes all additional API operations, including approved negative corpora, per-row review and key management.

## Inference API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/v1/embed` | Locally encode a batch of texts |
| POST | `/v1/search` | Private pgvector nearest concepts |
| POST | `/v1/match` | Word-to-definition matches |
| POST | `/v1/classify-language` | Configured language versus approved negatives |
| GET | `/v1/dictionary/{word}?language=…` | Exact NFC/casefold headword or variant lookup |

Search supports `semantic`, `word-to-meaning`, `meaning-to-word` and `similar-words` modes. Cosine similarities are labelled as similarities, never probabilities. Classification confidence is calibrated on validation data and only meaningful relative to the configured negative corpus.

```sh
curl http://localhost:8100/v1/search \
  -H "Authorization: Bearer $LANGAI_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"language":"muruwari","query":"water","limit":5}'
```

## Scope and extension points

See [architecture](docs/architecture.md), [data governance](docs/governance.md) and [ML methodology](docs/ml-methodology.md). Source governance and model visibility are inherited into private immutable lineage. Source rows never go to external AI APIs. Model downloads contact the configured foundation-model repository; inference uses the saved local artifact.

FastText is an optional future baseline adapter, not a required dependency. PDF/DOCX/OCR, mixed-language classifiers, additional corpora, speech/image representations, public sharing and production identity-provider integration are intentionally outside V1. Experimental adapter artifacts can be downloaded for research; no fluent-language chat endpoint is exposed.

## Licence

The platform code is [MIT licensed](LICENSE). This does not grant rights to uploaded dictionaries, community knowledge, model artifacts or third-party foundation models. Their own permissions and licences continue to apply.
