import importlib.util
from pathlib import Path
import httpx
import pytest

module_path = Path(__file__).parents[1] / "packages/sdk-python/language_ai/client.py"
spec = importlib.util.spec_from_file_location("sdk", module_path)
sdk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdk)


def test_sdk_serializes_language_and_auth():
    def handle(request):
        assert request.headers["authorization"] == "Bearer a-key"
        assert request.url.path == "/v1/search"
        assert b'"language":"example"' in request.content
        return httpx.Response(200, json={"matches": []})

    with sdk.Client(api_key="a-key", transport=httpx.MockTransport(handle)) as client:
        assert client.search(language="example", query="water") == {"matches": []}


def test_sdk_surfaces_api_errors():
    transport = httpx.MockTransport(lambda request: httpx.Response(403, json={"detail": "Access denied"}))
    with sdk.Client(api_key="a-key", transport=transport) as client:
        with pytest.raises(sdk.APIError, match="403: Access denied"):
            client.embed(language="example", texts=["a"])
