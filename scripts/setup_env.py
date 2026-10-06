from pathlib import Path
import argparse
import secrets

parser = argparse.ArgumentParser(description="Generate private deployment credentials without printing them")
parser.add_argument("--output", type=Path, default=Path(".env"))
path = parser.parse_args().output
if path.exists():
    raise SystemExit(f"{path} already exists; leaving it unchanged")
text = (
    Path(".env.example")
    .read_text()
    .replace("replace-with-at-least-32-random-characters", secrets.token_urlsafe(36))
)
text = text.replace("replace-local-storage-secret", secrets.token_urlsafe(36))
text = text.replace("replace-local-database-secret", secrets.token_urlsafe(36))
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(text)
path.chmod(0o600)
print(f"Created private {path}. Open it locally to retrieve the workspace API key.")
