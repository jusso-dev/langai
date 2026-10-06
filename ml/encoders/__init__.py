import json
from pathlib import Path


def load_encoder(path):
    engine = json.loads((Path(path) / "langai_encoder.json").read_text())["engine"]
    if engine == "test-tiny":
        from ml.encoders.tiny import TinyEncoder

        return TinyEncoder.load(path)
    if engine == "sentence-transformers":
        from ml.encoders.sentence import SentenceEncoder

        return SentenceEncoder.load(path)
    raise ValueError(f"Unknown encoder engine: {engine}")
