# Deployment and operations

## Services

`docker compose up --build -d` starts PostgreSQL/pgvector, Redis, RustFS S3 storage, a one-shot bucket initializer, a one-shot migration, FastAPI, the outbox dispatcher, an RQ worker and Next.js. API readiness depends on migrations and bucket initialization. Redis uses AOF persistence. S3 bucket versioning is enabled without a public policy.

The supplied Compose file is a single-node, loopback-bound deployment suitable for local use and a base for a controlled production host. For a remote service, terminate TLS at your own reverse proxy, set `LANGAI_COOKIE_SECURE=true` and `LANGAI_WEB_ORIGIN=https://your-web-host`, restrict backend/storage ports and use privately routed infrastructure. Use environment/secret injection for bootstrap, DB and object-store credentials. Set unique database credentials; the Compose DB password fallback is for development only.

The bundled object store uses the pinned [RustFS 1.0.1 release](https://github.com/rustfs/rustfs/releases/tag/1.0.1) and [official container configuration](https://docs.rustfs.com/en/installation/container/docker). The former MinIO community image is no longer available from its original registry. Storage remains generic S3; use an operator-managed S3 endpoint for your production environment. RustFS is Apache-2.0 licensed separately from this platform.

The web/API/worker images use unprivileged runtime users. Dependencies are locked with `uv.lock` and `package-lock.json`. Model downloads can be large, and the first primary encoder training has a warm-up/download phase with no invented percentage. The model and artifact caches need persistent capacity. Monitor disk space, queue age, heartbeat failures, CPU/RAM and object-store latency. API workers retain a bounded cache of three encoder variants and eight classifiers; each multilingual encoder requires substantial RAM. Scale independent API instances when inference concurrency grows.

## Credentials and roles

`scripts/setup_env.py` creates a mode-0600 `.env` and refuses to overwrite it. Read its bootstrap token locally to connect the web client. This bootstrap key is an owner key; issue scoped role keys for routine usage. Changing the configured bootstrap secret and restarting the API revokes the prior bootstrap identity while preserving its workspace. User-issued keys are separately revocable.

The BFF cookie lasts eight hours, is HttpOnly and SameSite=Strict, and is Secure when configured for HTTPS. Browser mutations must have a matching origin. Direct API clients use bearer keys. Put external rate limits, maximum request body limits and organization identity controls at the ingress boundary when exposing a deployment to multiple users. V1's role-based keys are not SSO, multi-factor login or a public SaaS signup system.

## Models and offline operation

The embedding repository is configured by `LANGAI_BASE_MODEL`; its default revision resolves once per run to a 40-character commit and is saved immutably. Set `LANGAI_MODEL_REVISION` to pin a deployment-wide revision. Review a repository's model card, licence, tokenizer coverage and memory requirements before choosing it. Remote custom model code is disabled.

Prefetch model weights in the same cache used by API revision resolution and workers:

```sh
uv run python -c "from huggingface_hub import snapshot_download; snapshot_download('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', revision='YOUR_APPROVED_COMMIT')"
```

Then set `LANGAI_LOCAL_FILES_ONLY=true` and restart API/workers. All registered-model inference uses local files regardless of this flag. Set `HF_HUB_DISABLE_TELEMETRY=1`, `DO_NOT_TRACK=1`, and enforce network policy when fully offline operation is mandatory.

`LANGAI_ENABLE_EXPERIMENTAL=true` permits the separate LoRA training task. It defaults to a small Qwen causal model unless a different repository is explicitly requested. CPU execution is supported but slower/more memory-intensive. Its artifacts are research-only and the standard semantic API never routes to it. `LANGAI_ALLOW_TEST_ENCODER=true` is only for integration verification and should stay false on real deployments.

## Reproducibility

Run records contain model revision, dataset hash/version, generation version, seed, resolved hyperparameters, environment package versions and code identity. Build with `LANGAI_GIT_COMMIT=$(git rev-parse HEAD) docker compose build` to embed the release identity. Runtime images do not require Git. Each artifact bundles the implementation source and dependency lock files. Source-tree fingerprints in run environments distinguish uncommitted code; the artifact records the actual worker environment and source hash. Keep locked dependency files with the release. Hardware differences may prevent bitwise identity; use evaluation tolerances.

The default strategy and locked Linux wheels use CPU. The explicit PyTorch CPU index follows the [uv PyTorch integration guide](https://docs.astral.sh/uv/guides/integration/pytorch/). A CUDA worker image must install a matching CUDA-enabled PyTorch wheel and driver runtime, then run with GPU access; choosing CUDA in the UI does not install them. CUDA and Apple MPS require compatible worker hardware/runtime and must be chosen explicitly. Route GPU requests to an appropriately provisioned worker pool in a larger deployment; V1 uses one `training` queue, so use homogeneous worker capabilities. The API does not assume it has the same accelerator as a worker. Unsupported device requests fail rather than silently running on a different device.

## Failure handling

QUEUED jobs survive Redis downtime through the database outbox. Workers claim atomically, and registration is transactional. Training log streams use SSE and support the `after` cursor; polling events is available for clients that cannot use SSE. Run errors expose exception type, while private operator diagnostics include stack frame locations without dictionary text. Check worker process logs and the pinned dependency/environment record.

Cancellation is cooperative. A failed/cancelled run is retained permanently; create another run for a retry. Runs with missing heartbeats for five minutes are marked FAILED by the dispatcher. RQ job timeouts bound hung jobs. Restoring a queue does not mutate historical run configuration.

Deploy verifies and loads the artifact before indexing. Headword, definition and combined vectors carry a model ID, language ID and source entry ID. A database transaction updates vectors and the active deployment pointer. Replacing a model returns the previous one to APPROVED so an owner can redeploy it as a rollback. A deployed model cannot be archived until replaced.

## Backups and retention

Back up PostgreSQL and all referenced object versions as one recoverable unit. Include model artifacts and dataset manifests, not just original uploads. Test restoration into an isolated deployment. Protect secrets separately; caches can be reconstructed from immutable private artifacts. Use provider-managed at-rest encryption/KMS and TLS as appropriate to the owner's infrastructure and policies.

Do not run destructive retention jobs against versioned originals without the custodial retention policy. The system intentionally has no one-click irreversible delete. See [governance](governance.md) for access/withdrawal limits.
