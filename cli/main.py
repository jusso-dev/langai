"""Every command calls the same authenticated API used by the web UI."""

import json
import os
from pathlib import Path
from typing import Annotated
import httpx
import typer

app = typer.Typer(no_args_is_help=True, help="Private dictionary training platform")
languages = typer.Typer(no_args_is_help=True)
dictionaries = typer.Typer(no_args_is_help=True)
datasets = typer.Typer(no_args_is_help=True)
app.add_typer(languages, name="language")
app.add_typer(dictionaries, name="dictionary")
app.add_typer(datasets, name="dataset")
LanguageOption = Annotated[str, typer.Option("--language", help="Language ID or slug")]


def request(method, path, **kwargs):
    token = os.environ.get("LANGAI_API_KEY")
    if not token:
        raise typer.BadParameter("Set LANGAI_API_KEY")
    try:
        response = httpx.request(
            method,
            os.environ.get("LANGAI_API_URL", "http://localhost:8100").rstrip("/") + path,
            headers={"Authorization": f"Bearer {token}"},
            timeout=300,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        typer.echo(f"API {exc.response.status_code}: {exc.response.text}", err=True)
        raise typer.Exit(1)
    except httpx.HTTPError as exc:
        typer.echo(f"Connection failed: {exc}", err=True)
        raise typer.Exit(1)


def output(value):
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2))


@languages.command("create")
def create_language(name: str, metadata: Path | None = None):
    output(
        request(
            "POST",
            "/languages",
            json={"name": name, **(json.loads(metadata.read_text()) if metadata else {})},
        )
    )


@languages.command("list")
def list_languages():
    output(request("GET", "/languages"))


@dictionaries.command("import")
def import_dictionary(
    path: Path,
    language: LanguageOption,
    governance: Annotated[Path, typer.Option(help="JSON ownership and permission record")],
    mapping: Path | None = None,
):
    with path.open("rb") as f:
        source = request(
            "POST",
            f"/languages/{language}/dictionaries",
            files={"file": (path.name, f)},
            data={"governance": governance.read_text()},
        )
    config = {"mapping": json.loads(mapping.read_text()) if mapping else source["suggested_mapping"]}
    report = request("POST", f"/dictionaries/{source['id']}/preview", json=config)
    output(
        {
            "source_id": source["id"],
            "mapping": config["mapping"],
            "quality": report["quality"],
            "preview": report["entries"][:5],
        }
    )
    if typer.confirm("Accept these mappings and import for review?", default=False):
        output(request("POST", f"/dictionaries/{source['id']}/import", json=config))


@dictionaries.command("approve")
def approve_dictionary(source_id: str):
    output(request("POST", f"/dictionaries/{source_id}/approve"))


@dictionaries.command("review")
def review_dictionary(source_id: str, issue: str = ""):
    output(request("GET", f"/dictionaries/{source_id}/entries", params={"issue": issue}))


@datasets.command("create")
def create_dataset(
    language: LanguageOption,
    source: Annotated[list[str], typer.Option("--source")],
    seed: int = 42,
    negative_corpus: str | None = None,
):
    output(
        request(
            "POST",
            f"/languages/{language}/datasets",
            json={"source_ids": source, "seed": seed, "negative_corpus_id": negative_corpus},
        )
    )


@app.command("train")
def train(
    language: LanguageOption, task: str = "embeddings", dataset: str | None = None, config: Path | None = None
):
    if not dataset:
        choices = request("GET", f"/languages/{language}/datasets")
        if not choices:
            raise typer.BadParameter("Create a dataset first")
        dataset = choices[0]["id"]
    output(
        request(
            "POST",
            f"/languages/{language}/training-runs",
            json={"dataset_id": dataset, "task": task, **(json.loads(config.read_text()) if config else {})},
        )
    )


@app.command("status")
def status(run_id: str):
    output(request("GET", f"/training-runs/{run_id}"))


@app.command("logs")
def logs(run_id: str):
    output(request("GET", f"/training-runs/{run_id}/events"))


@app.command("cancel")
def cancel(run_id: str):
    output(request("POST", f"/training-runs/{run_id}/cancel"))


@app.command("models")
def list_models(language: LanguageOption):
    output(request("GET", f"/languages/{language}/models"))


@app.command("evaluate")
def evaluate(model: str):
    output(request("GET", f"/models/{model}/evaluation"))


@app.command("approve")
def approve_model(model: str):
    output(request("POST", f"/models/{model}/approve"))


@app.command("deploy")
def deploy(model: str):
    output(request("POST", f"/models/{model}/deploy"))


@app.command("search")
def search(query: str, language: LanguageOption, limit: int = 10):
    output(request("POST", "/v1/search", json={"language": language, "query": query, "limit": limit}))


@app.command("request")
def raw_request(method: str, path: str, body: Path | None = None):
    """Access additional endpoints (e.g. negative corpora, key management) through the same API."""
    output(request(method.upper(), path, **({"json": json.loads(body.read_text())} if body else {})))
