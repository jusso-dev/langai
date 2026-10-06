from pathlib import Path
import json
import httpx


class APIError(RuntimeError):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        super().__init__(f"{status_code}: {detail}")


class Client:
    """Synchronous, provider-neutral HTTP client. Keep API keys out of source control."""
    def __init__(self, base_url="http://localhost:8100", api_key=None, timeout=120, transport=None):
        import os
        key = api_key or os.environ.get("LANGAI_API_KEY")
        if not key:
            raise ValueError("Provide api_key or set LANGAI_API_KEY")
        self.http = httpx.Client(base_url=base_url.rstrip("/"), headers={"Authorization": f"Bearer {key}"}, timeout=timeout, transport=transport)

    def request(self, method, path, **kwargs):
        response = self.http.request(method, path, **kwargs)
        if response.is_error:
            try:
                detail = response.json().get("detail", response.reason_phrase)
            except ValueError:
                detail = response.reason_phrase
            raise APIError(response.status_code, detail)
        return response.json()

    def create_language(self, name, **metadata):
        return self.request("POST", "/languages", json={"name": name, **metadata})

    def import_dictionary(self, language, path, governance, mapping=None, normalization=None):
        """Upload and extract to REVIEW. Approval is always a separate explicit operation."""
        path = Path(path)
        with path.open("rb") as source:
            uploaded = self.request("POST", f"/languages/{language}/dictionaries",
                                    files={"file": (path.name, source)}, data={"governance": json.dumps(governance)})
        config = {"mapping": mapping or uploaded["suggested_mapping"], "normalization": normalization or {}}
        return self.request("POST", f"/dictionaries/{uploaded['id']}/import", json=config)

    def approve_dictionary(self, source_id):
        return self.request("POST", f"/dictionaries/{source_id}/approve")

    def create_dataset(self, language, source_ids, seed=42, negative_corpus_id=None):
        return self.request("POST", f"/languages/{language}/datasets", json={"source_ids": source_ids, "seed": seed, "negative_corpus_id": negative_corpus_id})

    def train(self, language, dataset_id, task="embeddings", **config):
        return self.request("POST", f"/languages/{language}/training-runs", json={"dataset_id": dataset_id, "task": task, **config})

    def evaluate(self, model_id):
        return self.request("GET", f"/models/{model_id}/evaluation")

    def approve_model(self, model_id):
        return self.request("POST", f"/models/{model_id}/approve")

    def deploy(self, model_id):
        return self.request("POST", f"/models/{model_id}/deploy")

    def search(self, *, language, query, limit=10, mode="semantic"):
        return self.request("POST", "/v1/search", json={"language": language, "query": query, "limit": limit, "mode": mode})

    def embed(self, *, language, texts):
        return self.request("POST", "/v1/embed", json={"language": language, "texts": texts})

    def match(self, *, language, word, limit=5):
        return self.request("POST", "/v1/match", json={"language": language, "word": word, "limit": limit})

    def classify_language(self, *, language, text):
        return self.request("POST", "/v1/classify-language", json={"language": language, "query": text})

    def dictionary(self, *, language, word):
        from urllib.parse import quote
        return self.request("GET", f"/v1/dictionary/{quote(word, safe='')}", params={"language": language})

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
