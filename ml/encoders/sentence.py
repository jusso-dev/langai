import json
from pathlib import Path
import numpy as np


class SentenceEncoder:
    modality = "text"

    def __init__(self, model_id, revision=None, device="cpu", local_files_only=False):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            model_id,
            revision=revision,
            device=device,
            trust_remote_code=False,
            local_files_only=local_files_only,
        )

    def encode(self, texts):
        return np.asarray(
            self.model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                batch_size=32,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )

    def train(self, dataset, config, emit):
        from ml.trainers.contrastive import fit

        return fit(self, dataset, config, emit)

    def differentiable(self, texts):
        import torch
        from sentence_transformers.util import batch_to_device

        preprocess = getattr(self.model, "preprocess", self.model.tokenize)
        features = batch_to_device(preprocess(texts), self.model.device)
        return torch.nn.functional.normalize(self.model(features)["sentence_embedding"], dim=-1)

    def save(self, path):
        path = Path(path)
        self.model.save_pretrained(str(path), safe_serialization=True)
        (path / "langai_encoder.json").write_text(json.dumps({"engine": "sentence-transformers"}))

    @classmethod
    def load(cls, path):
        return cls(str(path), local_files_only=True)
