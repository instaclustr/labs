"""RAG module — structured memory of past findings + domain context, in ClickHouse.

The knowledge base lives in the `knowledge` table (clickhouse/init/03_knowledge.sql):
each row is a piece of text plus its embedding vector. Retrieval is a cosine-distance
search, so the AI agent (instaclustr_sdk/agent.py) can ground its analysis in what anomalies are /
are not for a given entity, and in how similar cases were judged before.

    import instaclustr_sdk.rag as rag
    rag.setup()                                  # local embedder unless VOYAGE_API_KEY is set
    rag.add_knowledge("Spikes above 90C on sensor-1 are disconnects, not real heat.",
                      kind="domain", entity="sensor-1", metric="temperature")
    docs = rag.retrieve("sensor-1 temperature spike", k=5)

Embeddings are pluggable: pass any `embed_fn(text) -> list[float]` (and optionally a separate
`query_embed_fn` for search queries) to setup(). The default uses Voyage AI (Anthropic's
recommended embeddings partner) when VOYAGE_API_KEY is present, otherwise falls back to a
dependency-free local hashing embedder so the demo runs offline.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass
from typing import Callable, List, Optional

import clickhouse_connect

EmbedFn = Callable[[str], List[float]]
"""An embedder: takes one text and returns its embedding vector."""

_client = None
_embed: Optional[EmbedFn] = None
_embed_query: Optional[EmbedFn] = None
_table = "knowledge"

_TOKEN = re.compile(r"[a-z0-9]+")


# ------------------------------------------------------------------- embedders


def hashing_embedder(dim: int = 256) -> EmbedFn:
    """Dependency-free fallback: L2-normalized hashed bag-of-words. Low quality but offline."""

    def embed(text: str) -> List[float]:
        """Return the L2-normalized hashed bag-of-words vector for `text`."""
        vec = [0.0] * dim
        for tok in _TOKEN.findall(text.lower()):
            idx = int(hashlib.md5(tok.encode()).hexdigest(), 16) % dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    return embed


def voyage_embedder(
    model: str = "voyage-3", api_key: Optional[str] = None, input_type: str = "document"
) -> EmbedFn:
    """Voyage AI embeddings (Anthropic's recommended partner). Requires `pip install voyageai`.

    `input_type` is "document" for stored text and "query" for search queries; Voyage embeds
    the two differently to improve retrieval.
    """
    import voyageai

    vo = voyageai.Client(api_key=api_key)

    def embed(text: str) -> List[float]:
        """Return Voyage's embedding of `text` (one API call)."""
        return vo.embed([text], model=model, input_type=input_type).embeddings[0]

    return embed


def default_embedder(input_type: str = "document") -> EmbedFn:
    """The embedder `setup()` uses when given none.

    Voyage (`voyage_embedder` with this `input_type`) if VOYAGE_API_KEY is set and `voyageai`
    imports; otherwise, silently, the local `hashing_embedder()`.
    """
    if os.environ.get("VOYAGE_API_KEY"):
        try:
            return voyage_embedder(api_key=os.environ["VOYAGE_API_KEY"], input_type=input_type)
        except Exception:
            pass  # voyageai not installed / failed — fall back to local
    return hashing_embedder()


# ------------------------------------------------------------------- lifecycle


def setup(
    host: str = "localhost",
    port: int = 8123,
    username: str = "default",
    password: str = "",
    database: str = "default",
    embed_fn: Optional[EmbedFn] = None,
    table: str = "knowledge",
    query_embed_fn: Optional[EmbedFn] = None,
):
    """Connect to ClickHouse and choose embedders.

    `embed_fn` embeds stored documents. `query_embed_fn` embeds search queries; it defaults
    to `embed_fn` when one is given, otherwise to the query-side default embedder.
    """
    global _client, _embed, _embed_query, _table
    _client = clickhouse_connect.get_client(
        host=host, port=port, username=username, password=password, database=database
    )
    _embed = embed_fn or default_embedder()
    _embed_query = query_embed_fn or embed_fn or default_embedder(input_type="query")
    _table = table
    return _table


def _require():
    if _client is None or _embed is None or _embed_query is None:
        raise RuntimeError("instaclustr_sdk.rag.setup(...) must be called first")
    return _client, _embed, _embed_query


# ------------------------------------------------------------------- documents


@dataclass
class Doc:
    """One `retrieve()` result: a stored document and its cosine distance to the query.

    `kind` is 'domain' or 'finding'; `entity` and `metric` are empty when the document isn't
    tied to one. A lower `distance` is closer.
    """

    text: str
    kind: str
    entity: str
    metric: str
    distance: float


def add_knowledge(text: str, kind: str = "domain", entity: str = "", metric: str = "") -> None:
    """Embed and store one document. `kind` is 'domain' or 'finding'."""
    client, embed, _ = _require()
    client.insert(
        _table,
        [[kind, entity, metric, text, embed(text)]],
        column_names=["kind", "entity", "metric", "text", "embedding"],
    )


def add_finding(anomaly, verdict: str, explanation: str) -> None:
    """Store a past-finding memory for an analyzed anomaly (closes the learning loop)."""
    text = (
        f"Finding for {anomaly.entity}/{anomaly.metric}: value={anomaly.value}, "
        f"z-score={anomaly.zscore}. Verdict: {verdict}. {explanation}"
    )
    add_knowledge(text, kind="finding", entity=anomaly.entity, metric=anomaly.metric)


def retrieve(
    query: str,
    k: int = 5,
    kind: Optional[str] = None,
    entity: Optional[str] = None,
) -> List[Doc]:
    """Return the k most similar documents to `query` by cosine distance (lower = closer)."""
    client, _, embed_query = _require()
    params = {"qvec": embed_query(query), "k": k}
    conditions = []
    if kind is not None:
        conditions.append("kind = {kind:String}")
        params["kind"] = kind
    if entity is not None:
        # entity-specific docs plus global ('') ones
        conditions.append("(entity = {entity:String} OR entity = '')")
        params["entity"] = entity
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT text, kind, entity, metric,
               cosineDistance(embedding, {{qvec:Array(Float32)}}) AS dist
        FROM {_table}
        {where}
        ORDER BY dist ASC
        LIMIT {{k:UInt32}}
    """
    rows = client.query(sql, parameters=params).result_rows
    return [
        Doc(text=r[0], kind=str(r[1]), entity=r[2], metric=r[3], distance=float(r[4]))
        for r in rows
    ]
