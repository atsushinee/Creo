"""Unstructured Transform adapter + embeddings client (fake SDK / MockTransport)."""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.services.embedding_client import EmbeddingError, OpenAIEmbeddingClient
from app.services.unstructured_client import UnstructuredClient, UnstructuredError


class FakeParseNamespace:
    def __init__(self, client: "FakeTransformClient") -> None:
        self._client = client

    def run(self, **kwargs: object) -> object:
        self._client.calls.append(kwargs)
        if self._client.error is not None:
            raise self._client.error
        return self._client.result


class FakeTransformClient:
    """Stands in for unstructured_transform_client.TransformClient.parse."""

    def __init__(self, result: object | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict] = []
        self.closed = False
        self.parse = FakeParseNamespace(self)

    def close(self) -> None:
        self.closed = True


def fake_result(*elements: dict) -> SimpleNamespace:
    return SimpleNamespace(
        elements=[
            SimpleNamespace(
                type=item["type"],
                text=item["text"],
                metadata=SimpleNamespace(
                    page_number=item.get("page_number"),
                    text_as_html=item.get("text_as_html"),
                ),
            )
            for item in elements
        ]
    )


def write_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-1.4 test")
    return path


def test_parse_pdf_maps_elements_to_dicts(tmp_path: Path) -> None:
    fake = FakeTransformClient(
        fake_result(
            {"type": "NarrativeText", "text": "正文内容", "page_number": 2},
            {
                "type": "Table",
                "text": "tiny",
                "page_number": 3,
                "text_as_html": "<table>总资产</table>",
            },
        )
    )
    client = UnstructuredClient("key", transform_client=fake)
    elements = client.parse_pdf(write_pdf(tmp_path), "doc.pdf")

    assert elements[0] == {
        "type": "NarrativeText",
        "text": "正文内容",
        "metadata": {"page_number": 2, "text_as_html": None, "coordinates": None},
    }
    assert elements[1]["metadata"]["text_as_html"] == "<table>总资产</table>"
    call = fake.calls[0]
    assert call["output"] == "elements"  # include is only valid with output=elements
    assert call["include"] == ["coordinates", "table_html"]
    assert call["profile"] == "best"


def test_parse_pdf_custom_profile_and_close(tmp_path: Path) -> None:
    fake = FakeTransformClient(fake_result())
    client = UnstructuredClient("key", profile="balanced", transform_client=fake)
    client.parse_pdf(write_pdf(tmp_path), "doc.pdf")
    assert fake.calls[0]["profile"] == "balanced"
    client.close()
    assert fake.closed is True


def test_parse_pdf_wraps_sdk_errors(tmp_path: Path) -> None:
    fake = FakeTransformClient(error=RuntimeError("401 unauthorized"))
    client = UnstructuredClient("key", transform_client=fake)
    with pytest.raises(UnstructuredError, match="401 unauthorized"):
        client.parse_pdf(write_pdf(tmp_path), "doc.pdf")


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
