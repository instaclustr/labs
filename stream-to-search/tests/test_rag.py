"""Offline unit tests for instaclustr_sdk.rag's embedder selection — no ClickHouse or Voyage needed."""
from types import SimpleNamespace

import pytest

from instaclustr_sdk import rag


class FakeClickHouse:
    def __init__(self):
        self.inserted = []
        self.query_params = []

    def insert(self, table, rows, column_names):
        self.inserted.extend(rows)

    def query(self, sql, parameters=None):
        self.query_params.append(parameters)
        return SimpleNamespace(result_rows=[])


@pytest.fixture
def client(monkeypatch):
    """Route rag.setup() to a fake client and restore rag's module state afterwards."""
    for name in ("_client", "_embed", "_embed_query", "_table"):
        monkeypatch.setattr(rag, name, getattr(rag, name))
    fake = FakeClickHouse()
    monkeypatch.setattr(rag.clickhouse_connect, "get_client", lambda **kwargs: fake)
    return fake


def test_default_voyage_embeds_queries_and_documents_differently(monkeypatch, client):
    made = []

    def fake_voyage_embedder(model="voyage-3", api_key=None, input_type="document"):
        made.append(input_type)
        return lambda text: [1.0] if input_type == "document" else [2.0]

    monkeypatch.setenv("VOYAGE_API_KEY", "test")
    monkeypatch.setattr(rag, "voyage_embedder", fake_voyage_embedder)

    rag.setup()
    rag.add_knowledge("Spikes above 90C are disconnects.")
    rag.retrieve("sensor-1 temperature spike")

    assert sorted(made) == ["document", "query"]
    assert client.inserted[0][-1] == [1.0]  # stored text gets the document embedding
    assert client.query_params[0]["qvec"] == [2.0]  # the search query gets the query embedding


def test_custom_embed_fn_is_used_for_queries_too(client):
    rag.setup(embed_fn=lambda text: [3.0])

    rag.retrieve("anything")

    assert client.query_params[0]["qvec"] == [3.0]
