"""Download-free PyTorch test encoder. Never selected by Auto or called multilingual."""

import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from safetensors.torch import load_file, save_file


class TinyEncoder:
    def __init__(self, seed=42):
        torch.manual_seed(seed)
        self.model = torch.nn.Sequential(torch.nn.Linear(256, 48), torch.nn.Tanh(), torch.nn.Linear(48, 32))

    def differentiable(self, texts):
        features = torch.zeros(len(texts), 256)
        for i, text in enumerate(texts):
            for n in range(1, 4):
                for j in range(max(0, len(text) - n + 1)):
                    bucket = (
                        int.from_bytes(hashlib.sha256(text[j : j + n].encode()).digest()[:4], "big") % 256
                    )
                    features[i, bucket] += 1
        return torch.nn.functional.normalize(
            self.model(torch.nn.functional.normalize(features, dim=-1)), dim=-1
        )

    def encode(self, texts):
        self.model.eval()
        with torch.no_grad():
            return np.asarray(self.differentiable(texts).numpy(), dtype=np.float32)

    def train(self, dataset, config, emit):
        from ml.trainers.contrastive import fit

        return fit(self, dataset, config, emit)

    def save(self, path):
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        save_file(self.model.state_dict(), str(path / "weights.safetensors"))
        (path / "langai_encoder.json").write_text(json.dumps({"engine": "test-tiny"}))

    @classmethod
    def load(cls, path):
        obj = cls()
        obj.model.load_state_dict(load_file(str(Path(path) / "weights.safetensors")))
        return obj
