# Verification record

Release verification on 6 October 2026 with Python 3.12, Node 22, Next.js 16.3.8 and the repository dependency lock files. All uploaded fixtures use clearly labelled synthetic identifiers. No community dictionary or real Indigenous vocabulary was used or published.

## Automated checks

- **35 Python tests passed.** Coverage includes CSV/TSV/XLSX/JSON/TXT parsing; Unicode preservation; quality detection; deterministic entry/variant/definition group splits; augmentation and negative-pair leakage prevention; external-negative provenance; workspace/language isolation and roles; explicit row exclusion; frozen datasets/run configurations; cancellation, failure and watchdog recovery; real PyTorch training; embedding normalization and save/load; deployment gates and vector search; classifier calibration; SDK serialization/errors; local PEFT LoRA training; safe artifact extraction and simultaneous model initialization.
- Ruff checks and formatting passed. TypeScript checking and the optimized Next.js production build passed. Platform and Python SDK wheels built successfully.
- Gitleaks found no secrets in the publication tree. A separate comparison checked staged files against actual local deployment secrets. Credentials, uploads, databases, caches and model artifacts are excluded from Git.

## Container and backing-service checks

Built and ran the Linux CPU images in a dedicated Docker Compose project with separate volumes/network, temporary credentials, and no host ports. Applied both PostgreSQL migrations, initialized a private versioned RustFS S3 bucket, started Redis/RQ dispatch and subprocess workers, and ran the real HTTP workflow from upload through evaluation, approval, deployment and inference. Existing services on the host were not changed.

Verified original-file roundtrip, frozen dataset exports, all six dataset views and split manifests, streamed job events, registered evaluations, 32- and 384-dimensional embedding APIs, every search mode, exact dictionary lookup, lexical matching, classifier deployment/confidence, viewer restrictions and key revocation. A direct SQL attempt to mutate a dataset failed. Anonymous object retrieval returned 403; bucket versioning was enabled.

The container check caught and resolved missing runtime Git handling and an unavailable upstream MinIO image. Compose now pins RustFS 1.0.1; the application continues to use generic S3. Concurrent deployment testing found an upstream model-initialization interaction: model cache misses are now serialized, and a regression test reproduces the conflicting meta-weight initialization context. Cross-process extraction uses a file lock and discards incomplete cached artifacts.

## Browser workflow

Both committed headless Chromium tests passed against the rebuilt Docker services. The complete UI test covered session login, language creation, in-memory file selection and real multipart upload, mapping preview, extraction, exclusion of a clean row, source approval, source selection, dataset creation, real queued training and streamed evaluation, model approval/deployment, authenticated API search and baseline-versus-trained playground results. The 375-pixel layout had no horizontal overflow and no browser runtime errors were observed. The second test verified malformed JSON, oversized login payloads, cross-origin rejection and anonymous API denial.

## Full multilingual encoder

Trained `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` at commit `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` on CPU, registered it, approved it and deployed it through the pgvector API. The container fixture had 30 entries: 24 training, 3 validation and 3 test. The one-epoch run used batch size 2 and maximum token length 32.

Measured test MRR changed from approximately 0.1307 to 0.1978; Recall@5 from 0 to 0.3333; Recall@10 from 0.6667 to 0.3333. These mixed, highly uncertain results demonstrate honest reporting, **not Indigenous-language usefulness**. Synthetic identifiers and three held-out queries cannot establish linguistic performance. A prior independent local fixture also showed declining metrics, displayed without alteration.

A local original-versus-restored encoder roundtrip produced identical embeddings (maximum absolute difference 0). An upstream generic tokenizer regex warning is emitted during some local loads; the checked roundtrip preserved output.

## Full experimental adapter

Trained the actual `Qwen/Qwen2.5-0.5B-Instruct` at commit `7ae557604adf67be50417f59c2c2f167def9a775` for one CPU epoch with rank-2 LoRA, batch size 2 and maximum token length 32. Both instruction directions retained their source entry/split provenance. The complete artifact was uploaded, hash-verified, restored, and used for local generation. Its normal semantic deployment request was rejected as intended: it remains a separate research artifact.

Measured held-out loss was 11.1858 before and 2.6879 after training on this synthetic fixture. This is an engineering check of the adapter path, not evidence of grammar, translation or fluency. Sampling-only generation defaults in the upstream model produce a harmless warning when deterministic generation is selected.

## Reproduce container verification

Docker Compose 2.24.4+ supports the verification override tags. Run this against the Docker context you intend to test. It publishes no host ports and uses a separate project; cleanup below removes only that verification project's synthetic data.

```sh
python3 scripts/setup_env.py --output data/verification.env
export COMPOSE_PROJECT_NAME=langai-verify
export COMPOSE_FILE=compose.yaml:infra/compose.verify.yaml
export COMPOSE_ENV_FILES=data/verification.env
export LANGAI_GIT_COMMIT=$(git rev-parse HEAD)
docker compose build
docker compose up -d --wait --wait-timeout 180
docker compose --profile verify run --rm smoke
docker compose exec -T api python scripts/check_backing_services.py
docker compose --profile verify run --build --rm browser-tests
# Optional, downloads the actual encoder and Qwen model into the private cache:
docker compose --profile verify run --rm smoke python scripts/primary_smoke.py --adapter
# When finished with this disposable test deployment:
docker compose down --volumes --remove-orphans
```

The same download-free smoke and browser checks run in [GitHub Actions](https://github.com/jusso-dev/langai/actions/workflows/ci.yml). Browser tests use a disposable headless Chromium container and synthetic data, with no saved screenshots, videos or credential-bearing traces.

## Remaining validation boundaries

GPU execution, production SSO/ingress, large-dataset load/performance, multi-host storage recovery, and linguistic usefulness on community-approved language material have not been validated here. Role-based API keys and single-node Compose are the V1 deployment model; these checks do not certify an internet-facing production installation.
