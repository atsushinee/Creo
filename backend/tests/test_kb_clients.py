"""HTTP clients against httpx.MockTransport: Unstructured + embeddings."""

import json
from pathlib import Path

import httpx
import pytest

from app.services.embedding_client import EmbeddingError, OpenAIEmbeddingClient
from app.services.unstructured_client import UnstructuredClient, UnstructuredError


def write_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-1.4 test")
    return path


def test_unstructured_sends_multipart_params(tmp_path) -> None:
    recorder: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        recorder["request"] = request
        return httpx.Response(
            200,
            json=[{"type": "NarrativeText", "text": "hello", "metadata": {"page_number": 2}}],
        )

    client = UnstructuredClient(
        "http://unstructured.test",
        api_key="secret",
        strategy="hi_res",
        languages=["chi_sim", "eng"],
        max_characters=1500,
        transport=httpx.MockTransport(handler),
    )
    elements = client.partition_pdf(write_pdf(tmp_path), "doc.pdf")

    assert elements[0]["type"] == "NarrativeText"
    request = recorder["request"]
    assert request.url.path == "/general/v0/general"
    assert request.headers["unstructured-api-key"] == "secret"
    body = request.content
    assert body.count(b'name="languages"') == 2  # repeated multipart fields
    for expected in (b"hi_res", b"by_title", b"1500", b"1200", b"300", b"include_orig_elements"):
        assert expected in body


def test_unstructured_maps_errors(tmp_path) -> None:
    client = UnstructuredClient(
        "http://unstructured.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(500, text="boom")),
    )
    with pytest.raises(UnstructuredError, match="500"):
        client.partition_pdf(write_pdf(tmp_path), "doc.pdf")


def test_embedding_batches_preserve_order() -> None:
    calls: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload["input"])
        base = 100 * len(calls)
        # Deliberately out of order: the client must sort by index.
        data = [
            {"index": i, "embedding": [float(base + i)]}
            for i in reversed(range(len(payload["input"])))
        ]
        return httpx.Response(200, json={"data": data})

    client = OpenAIEmbeddingClient(
        "http://embeddings.test/v1",
        model="BAAI/bge-m3",
        batch_size=2,
        transport=httpx.MockTransport(handler),
    )
    vectors = client.embed_texts(["a", "b", "c"])

    assert calls == [["a", "b"], ["c"]]
    assert vectors == [[100.0], [101.0], [200.0]]


def test_embedding_retries_on_server_error() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 2:
            return httpx.Response(503, text="overloaded")
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})

    client = OpenAIEmbeddingClient(
        "http://embeddings.test/v1",
        max_retries=3,
        retry_backoff=0.0,
        transport=httpx.MockTransport(handler),
    )
    assert client.embed_texts(["hello"]) == [[1.0]]
    assert len(attempts) == 2


def test_embedding_does_not_retry_client_error() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(401, text="unauthorized")

    client = OpenAIEmbeddingClient(
        "http://embeddings.test/v1",
        max_retries=3,
        retry_backoff=0.0,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(EmbeddingError, match="401"):
        client.embed_texts(["hello"])
    assert len(attempts) == 1
