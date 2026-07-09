"""
单元测试 — RAG 运行时基类
"""

import pytest
from runtime.rag import (
    Document, Chunk,
    BaseLoader, BaseChunker, BaseEmbedder,
    BaseSearchEngine, BaseRanker,
)


class TestDocument:
    """Document 数据类测试"""

    def test_minimal_document(self):
        doc = Document(id="1", content="hello")
        assert doc.id == "1"
        assert doc.content == "hello"
        assert doc.metadata == {}
        assert doc.source == ""
        assert doc.chunks == []
        assert doc.embedding is None

    def test_full_document(self):
        doc = Document(
            id="2",
            content="full document",
            metadata={"author": "test"},
            source="test_source",
            chunks=[{"index": 0, "text": "chunk1"}],
            embedding=[0.1, 0.2],
        )
        assert doc.metadata["author"] == "test"
        assert doc.source == "test_source"
        assert len(doc.chunks) == 1
        assert doc.embedding == [0.1, 0.2]


class TestChunk:
    """Chunk 数据类测试"""

    def test_minimal_chunk(self):
        chunk = Chunk(id="c1", document_id="d1", content="chunk content")
        assert chunk.id == "c1"
        assert chunk.document_id == "d1"
        assert chunk.content == "chunk content"
        assert chunk.index == 0
        assert chunk.metadata == {}
        assert chunk.embedding is None
        assert chunk.score == 0.0

    def test_full_chunk(self):
        chunk = Chunk(
            id="c2",
            document_id="d2",
            content="data",
            index=3,
            metadata={"page": 5},
            embedding=[0.5, 0.6],
            score=0.92,
        )
        assert chunk.index == 3
        assert chunk.metadata["page"] == 5
        assert chunk.embedding == [0.5, 0.6]
        assert chunk.score == 0.92


class TestBaseLoader:
    """BaseLoader 基类测试"""

    def test_load_raises_not_implemented(self):
        loader = BaseLoader({})
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(loader.load("source"))

    def test_load_batch_raises_not_implemented(self):
        loader = BaseLoader({})
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(loader.load_batch(["a", "b"]))

    def test_config_stored(self):
        loader = BaseLoader({"format": "pdf", "max_size": 10})
        assert loader.config["format"] == "pdf"
        assert loader.config["max_size"] == 10


class TestBaseChunker:
    """BaseChunker 基类测试"""

    def test_default_config(self):
        chunker = BaseChunker({})
        assert chunker.chunk_size == 512
        assert chunker.chunk_overlap == 64

    def test_custom_config(self):
        chunker = BaseChunker({"chunk_size": 256, "chunk_overlap": 32})
        assert chunker.chunk_size == 256
        assert chunker.chunk_overlap == 32

    def test_chunk_raises_not_implemented(self):
        chunker = BaseChunker({})
        doc = Document(id="1", content="test")
        with pytest.raises(NotImplementedError):
            chunker.chunk(doc)


class TestBaseEmbedder:
    """BaseEmbedder 基类测试"""

    def test_default_config(self):
        embedder = BaseEmbedder({})
        assert embedder.model == "text-embedding-ada-002"
        assert embedder.dimension == 1536

    def test_custom_config(self):
        embedder = BaseEmbedder({
            "model": "text-embedding-3-small",
            "dimension": 768,
        })
        assert embedder.model == "text-embedding-3-small"
        assert embedder.dimension == 768

    def test_embed_raises_not_implemented(self):
        embedder = BaseEmbedder({})
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(embedder.embed(["hello"]))


class TestBaseSearchEngine:
    """BaseSearchEngine 基类测试"""

    def test_default_top_k(self):
        engine = BaseSearchEngine({})
        assert engine.top_k == 5

    def test_custom_top_k(self):
        engine = BaseSearchEngine({"top_k": 10})
        assert engine.top_k == 10

    def test_search_raises_not_implemented(self):
        engine = BaseSearchEngine({})
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(engine.search("query", []))


class TestBaseRanker:
    """BaseRanker 基类测试"""

    def test_default_top_k(self):
        ranker = BaseRanker({})
        assert ranker.top_k == 3

    def test_custom_top_k(self):
        ranker = BaseRanker({"rerank_top_k": 5})
        assert ranker.top_k == 5

    def test_rerank_raises_not_implemented(self):
        ranker = BaseRanker({})
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(ranker.rerank("query", []))
