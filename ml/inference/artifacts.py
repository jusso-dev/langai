import io
import threading
import shutil
import zipfile
from filelock import FileLock
from functools import lru_cache
from apps.api.config import settings
from apps.api.storage import store

_lock = threading.RLock()


def artifact_path(key, sha):
    # Cache by content hash. Always verify the archive before extracting, reject traversal/symlinks.
    root = settings().artifact_dir.resolve() / sha
    root.parent.mkdir(parents=True, exist_ok=True)
    # API processes can share this volume; an in-process lock is insufficient.
    with FileLock(str(root.parent / f"{sha}.lock"), timeout=300):
        if (root / ".complete").exists():
            return root
        if root.exists():
            shutil.rmtree(root)  # A prior interrupted extraction is never a valid cache hit.
        data = store().get(key, sha)
        root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                target = (root / info.filename).resolve()
                if not target.is_relative_to(root) or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Unsafe model artifact")
            archive.extractall(root)
        (root / ".complete").touch()
    return root


def encoder(key, sha, baseline=False):
    # HF/Accelerate initialization temporarily changes global torch module hooks.
    # Serialize cache misses across model types, including concurrent requests for
    # the same model. lru_cache alone allows simultaneous construction.
    with _lock:
        return _encoder(key, sha, baseline)


@lru_cache(maxsize=3)
def _encoder(key, sha, baseline=False):
    from ml.encoders import load_encoder

    return load_encoder(artifact_path(key, sha) / ("base" if baseline else "encoder"))


@lru_cache(maxsize=8)
def classifier(key, sha):
    from ml.classifiers.ngram import NgramClassifier

    return NgramClassifier.load(artifact_path(key, sha) / "classifier")
