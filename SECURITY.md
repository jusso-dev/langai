# Security policy

V1 is an owner-operated private platform. Only the latest `main` is supported before the first stable release. Keep deployments on a reviewed, pinned commit and dependency lock files.

Report vulnerabilities through [GitHub private vulnerability reporting](https://github.com/jusso-dev/langai/security/advisories/new). Do not include dictionary contents, model artifacts, API keys or personal/community information in a public issue. Use a minimal synthetic reproduction.

All API resources require bearer authentication and workspace authorization. Viewer keys can read all languages and download artifacts in their workspace; they are not per-language or inference-only credentials. The web stores keys in HttpOnly cookies and checks mutation origins. Uploaded material stays private. Permission metadata is a recorded approval, not independent verification of the uploader's authority.

See [operations](docs/operations.md) for TLS, network isolation, backups, key rotation and ingress limits. Do not expose the supplied local development ports directly to the internet. Foundation model downloads are the only required external ML connection; dictionary text never goes to a hosted AI API.
