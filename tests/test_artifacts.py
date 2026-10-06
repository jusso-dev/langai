import io
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from apps.api.storage import store
from ml.encoders.tiny import TinyEncoder
from ml.inference import artifacts


def test_concurrent_model_loads_do_not_share_meta_initialization(tmp_path, monkeypatch):
    from accelerate import init_empty_weights
    from ml.encoders import load_encoder

    TinyEncoder().save(tmp_path / "encoder")
    entered, release, second_started = threading.Event(), threading.Event(), threading.Event()
    artifacts._encoder.cache_clear()
    monkeypatch.setattr(artifacts, "artifact_path", lambda *_: tmp_path)
    calls = []

    def loading(path):
        calls.append(path.name)
        if path.name == "base":
            with init_empty_weights():
                entered.set()
                assert release.wait(5)
            return object()
        return load_encoder(path)

    monkeypatch.setattr("ml.encoders.load_encoder", loading)

    def second_load():
        second_started.set()
        return artifacts.encoder("synthetic", "fixture", False)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(artifacts.encoder, "synthetic", "fixture", True)
        assert entered.wait(5)
        second = pool.submit(second_load)
        assert second_started.wait(5)
        try:
            time.sleep(0.05)
            assert not second.done(), "Model initialization must wait for the active HF context"
        finally:
            release.set()
        first.result()
        loaded = second.result()
    assert np.isfinite(loaded.encode(["synthetic"])).all()
    assert artifacts.encoder("synthetic", "fixture", False) is loaded
    assert calls == ["base", "encoder"]
    artifacts._encoder.cache_clear()


def test_artifact_rejects_traversal_and_recovers_interrupted_extraction():
    for name in ["../outside.txt", "nested/../../outside.txt"]:
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr(name, "never extract")
        sha = store().put("unsafe.zip", data.getvalue())
        with pytest.raises(ValueError, match="Unsafe"):
            artifacts.artifact_path("unsafe.zip", sha)
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("weights.txt", "complete")
    sha = store().put("valid.zip", data.getvalue())
    root = artifacts.settings().artifact_dir / sha
    root.mkdir(parents=True)
    (root / "partial").write_text("interrupted")
    restored = artifacts.artifact_path("valid.zip", sha)
    assert (restored / "weights.txt").read_text() == "complete"
    assert (restored / ".complete").exists()
    assert not (restored / "partial").exists()
