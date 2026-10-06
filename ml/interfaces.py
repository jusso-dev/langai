from pathlib import Path
from typing import Protocol, Callable
import numpy as np


class BaseModel(Protocol):
    def save(self, path: Path) -> None: ...
    @classmethod
    def load(cls, path: Path) -> "BaseModel": ...


class TextEncoder(BaseModel, Protocol):
    def encode(self, texts: list[str]) -> np.ndarray: ...
    def train(self, dataset: dict, config: dict, emit: Callable) -> dict: ...


class GenerativeModel(BaseModel, Protocol):
    def generate(self, prompt: str, max_new_tokens: int = 128) -> str: ...


class Classifier(BaseModel, Protocol):
    def predict(self, texts: list[str]) -> list[dict]: ...


class Trainer(Protocol):
    def train(self, dataset: dict, config: dict, emit: Callable) -> dict: ...


class Evaluator(Protocol):
    def evaluate(self, model: BaseModel, dataset: dict) -> dict: ...


class Representation(Protocol):
    """Future modality adapters can expose the same representation contract."""

    modality: str

    def encode(self, inputs: list) -> np.ndarray: ...
