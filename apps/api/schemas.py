from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LanguageCreate(Strict):
    name: str = Field(min_length=1, max_length=150)
    alternate_names: list[str] = Field(default_factory=list, max_length=30)
    iso_code: str | None = Field(default=None, max_length=20)
    description: str = Field(default="", max_length=10000)
    default_dialect: str = Field(default="", max_length=200)
    orthography_notes: str = Field(default="", max_length=10000)
    source_community: str = Field(default="", max_length=2000)
    governance_notes: str = Field(default="", max_length=10000)

    @field_validator("name")
    @classmethod
    def nonempty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be blank")
        return v.strip()


class Governance(Strict):
    owner: str = Field(min_length=1, max_length=1000)
    custodian: str = Field(default="", max_length=1000)
    source: str = Field(min_length=1, max_length=2000)
    licence: str = Field(min_length=1, max_length=2000)
    training_allowed: bool = False
    commercial_use_allowed: bool = False
    redistribution_allowed: bool = False
    attribution: str = Field(default="", max_length=5000)


class Normalization(Strict):
    unicode_nfc: bool = True
    trim_whitespace: bool = True
    collapse_whitespace: bool = True


class ImportConfig(Strict):
    mapping: dict[str, str]
    normalization: Normalization = Field(default_factory=Normalization)


class Review(Strict):
    approved: bool
    training_eligible: bool


class DatasetCreate(Strict):
    source_ids: list[str] = Field(min_length=1, max_length=100)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    negative_corpus_id: str | None = None


class NegativeCreate(Strict):
    name: str = Field(min_length=1, max_length=200)
    texts: list[str] = Field(min_length=10, max_length=100000)
    governance: Governance
    approved: Literal[True]


class Hyperparameters(Strict):
    epochs: int | None = Field(default=None, ge=1, le=100)
    batch_size: int | None = Field(default=None, ge=2, le=512)
    learning_rate: float | None = Field(default=None, gt=0, le=0.1)
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    patience: int = Field(default=2, ge=1, le=20)
    max_length: int = Field(default=128, ge=8, le=512)
    weight_decay: float = Field(default=0.01, ge=0, le=1)
    evaluation_frequency: int = Field(default=1, ge=1, le=10)
    margin: float = Field(default=0.4, gt=0, lt=1)
    lora_rank: int = Field(default=8, ge=2, le=64)


class TrainCreate(Strict):
    dataset_id: str
    task: Literal["embeddings", "language-identification", "dictionary-adapter"] = "embeddings"
    base_model: str = "auto"
    base_model_revision: str = "auto"
    strategy: Literal["auto", "contrastive", "char-ngram", "lora"] = "auto"
    random_seed: int = Field(default=42, ge=0, le=2**31 - 1)
    hyperparameters: Hyperparameters = Field(default_factory=Hyperparameters)


class Query(Strict):
    language: str
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=10, ge=1, le=50)
    mode: Literal["semantic", "word-to-meaning", "meaning-to-word", "similar-words"] = "semantic"


class Embed(Strict):
    language: str
    texts: list[str] = Field(min_length=1, max_length=128)

    @field_validator("texts")
    @classmethod
    def bounded(cls, values):
        if any(not v.strip() or len(v) > 4000 for v in values):
            raise ValueError("Each text must contain 1–4000 characters")
        return values


class Match(Strict):
    language: str
    word: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=50)


class KeyCreate(Strict):
    name: str = Field(min_length=1, max_length=100)
    role: Literal["owner", "editor", "viewer"] = "viewer"


class DictionaryEntrySchema(BaseModel):
    id: str
    language_id: str
    source_id: str
    row_number: int
    original_row: dict
    headword: str
    normalized_headword: str
    definitions: list[str]
    alternate_spellings: list[str]
    part_of_speech: str
    dialect: str
    examples: list[str]
    notes: str
    source: str
    metadata: dict
    approved: bool
    training_eligible: bool
    issues: list[str]


class EmbedResponse(BaseModel):
    language: str
    model_id: str
    dimensions: int
    embeddings: list[list[float]]


class SearchMatch(BaseModel):
    entry_id: str
    headword: str
    normalized_headword: str
    definitions: list[str]
    source_id: str
    dialect: str
    score: float


class SearchResponse(BaseModel):
    language: str
    model_id: str
    score_type: Literal["cosine_similarity"]
    matches: list[SearchMatch]


class MatchResult(SearchMatch):
    definition: str


class MatchResponse(SearchResponse):
    matches: list[MatchResult]


class ClassificationResponse(BaseModel):
    language: str
    configured_language: str
    model_id: str
    positive_probability: float
    confidence: float
    is_language: bool
    scope: str


class DictionaryResponse(BaseModel):
    language: str
    entries: list[DictionaryEntrySchema]
