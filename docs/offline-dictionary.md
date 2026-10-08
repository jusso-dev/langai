# Offline dictionary on iPhone

For dictionary and phrase mapping, start with the lexical matcher. It returns
approved dictionary entries without inventing translations. There is no neural
model, MLX dependency, training job or inference server in this path.

## Export and install

1. Review and approve a dictionary in the workspace. Only entries marked both
   approved and eligible are exported. Even a one-entry dictionary works; no
   dataset or train/validation/test split is necessary.
2. Open **Offline phone**, select approved sources, and **Export phone dictionary**.
   Save the `.langai.json` file in Files on the iPhone.
3. Open **Open offline dictionary** in Safari over HTTPS. Use Share → Add to
   Home Screen, then open the installed app while connected. Import the pack
   there: Safari and the installed app may have separate storage.
4. Wait for **Ready for offline use**, enable airplane mode, close/reopen the
   installed app and search a known phrase. Both the app shell and dictionary
   must be saved before offline use is possible.

The workspace needs connectivity for approval/export. Only `/offline/index.html`
is the offline app. It is a static PWA, served by the existing web deployment.
The standalone launcher and Docker image include `public/`. A phone needs an
HTTPS deployment reachable from Safari; desktop `localhost` is sufficient for
local development but a phone connecting to an HTTP LAN address is not.

## Matching behavior

- Search either direction or both. Full headwords, alternate spellings and each
  individual definition are exact-searchable. A headword can be a whole phrase.
- Exact identity uses NFC, trimmed/collapsed whitespace and Unicode lowercase.
  Original display text, diacritics and apostrophes are preserved. Accent or
  punctuation changes never become an exact match. This is not locale-specific
  collation and deliberately does not use transliteration or stemming.
- Duplicate headwords and shared definitions return multiple entries. The UI
  indicates ambiguity even if only the first 20 results are shown.
- If no exact match exists, token overlap or character trigrams produce
  suggestions. These are lexical similarity heuristics, not probabilities or
  validated translations. Suggestions never silently decide the intended entry.
- No match is a supported outcome. Meaning-equivalent paraphrases with no shared
  wording require approved aliases/entries or a separately evaluated embedding
  model. Example sentences are not interpreted as new translation pairs.
- Queries are limited to 256 Unicode characters. All full strings remain in the
  exact index; approximate search uses the first 256 characters per field. Packs
  are limited to 32 MiB, 100,000 entries, and 2 million indexed characters. Split
  large dictionaries into smaller source selections. One pack is active at a time.

## Artifact and privacy

`POST /languages/{language_id}/offline-export` accepts
`{"source_ids":["approved-source-id"]}` with a workspace key. Like existing
read/export APIs, viewers can export data they can access. Sources must belong
to the requested language and workspace. Export is audited with its content hash.

The versioned envelope is `langai-offline-v1`, with a `payload` JSON string and
its SHA-256. The payload specifies `langai-lexical-v1`, language identity, approved
entries and source checksums/permissions. Hashing exact UTF-8 bytes makes
verification portable without ambiguous JSON canonicalization. SHA-256 detects
corruption, not malicious replacement; only import packs from a trusted source.
The endpoint copies allowlisted fields, omitting original rows, arbitrary metadata,
negative corpora, credentials and training samples. Original source SHA-256 values
and the pack hash preserve provenance for this export; changing approved data
requires re-exporting and importing the replacement.

Import validates the envelope and entry schema in a Web Worker, verifies the
hash, builds the index, then commits the pack to IndexedDB before announcing
readiness. Failed imports restore the previous saved pack. All matching happens
in that worker. Results use DOM text nodes, never dictionary-provided HTML.

The service worker has scope `/offline/` and an explicit static-asset allowlist.
It never caches authenticated workspace/API responses or downloads dictionary
packs automatically. New shell versions activate after old app windows close;
bump the cache version in `sw.js` when modifying shell assets.

A saved pack is a private device copy, subject to the source permissions displayed
inside the app. Workspace sign-out, key revocation and later server changes cannot
remotely erase an offline copy. **Remove from phone** deletes the saved pack and
terminates its worker. Keep the exported file as a backup: storage persistence
is requested but browser/OS eviction and manual clearing can remove local data.
See [WebKit's storage policy](https://webkit.org/blog/14403/updates-to-storage-policy/).

## Why Gemma is optional

Research checked 2026-10-08: Google's [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
identifies E2B and E4B as mobile/edge variants. An
[MLX 4-bit E2B checkpoint](https://huggingface.co/mlx-community/gemma-4-e2b-it-4bit)
exists, and [MLX Swift LM implements Gemma 4](https://github.com/ml-explore/mlx-swift-lm/blob/main/Libraries/MLXLLM/Models/Gemma4.swift).
Gemma would add generative capability, substantial weights and memory needs,
and a native Swift runtime for MLX execution on iOS. It is not needed for this
lookup task, so this change does not download it or claim MLX inference in Safari.
Consider a compact embedding model next only if evaluation on real queries shows
lexical matching misses important paraphrases. A generative model should have a
separate, demonstrated need and physical-device memory/performance validation.

## Verification

Backend tests cover authorization, source scope/approval, excluded entries,
single-entry export, integrity, determinism and provenance. Browser tests exercise
real service-worker installation, device-local persistence, offline reload and
search, ambiguity, reverse lookup, suggestions, Unicode, literal HTML, corrupt
imports and deletion. These are automated Chromium and WebKit (iPhone viewport) checks, not a claim of
physical iPhone verification. Tests stop their own static server before offline
reload. Chromium also uses network emulation; WebKit uses the stopped origin to
avoid [Playwright's offline-emulation bug](https://github.com/microsoft/playwright/issues/42775). Validate the installation/relaunch flow in Safari
on the intended iPhone before release.

```sh
uv run --extra dev pytest -q tests/test_offline.py
cd apps/web
npm run build
PORT=3105 npm start
# Separate terminal; does not require an API key or backend:
npx playwright install chromium webkit
LANGAI_E2E_URL=http://127.0.0.1:3105 npx playwright test --config playwright.offline.config.ts
# Set LANGAI_E2E_TOKEN against a disposable backend to include the real web export test.
```
