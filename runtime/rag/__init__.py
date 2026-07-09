"""
RAG 运行时 — Loader / Chunk / Embedding / Search / Ranking
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Document:
    """文档"""
    id: str
    content: str
    metadata: Dict = field(default_factory=dict)
    source: str = ""
    chunks: List[Dict] = field(default_factory=list)
    embedding: Optional[List[float]] = None


@dataclass
class Chunk:
    """文档块"""
    id: str
    document_id: str
    content: str
    index: int = 0
    metadata: Dict = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    score: float = 0.0


class BaseLoader:
    """文档加载器基类"""
    
    def __init__(self, config: Dict):
        self.config = config
    
    async def load(self, source: str) -> Document:
        raise NotImplementedError
    
    async def load_batch(self, sources: List[str]) -> List[Document]:
        raise NotImplementedError


class BaseChunker:
    """文档分块器基类"""
    
    def __init__(self, config: Dict):
        self.chunk_size = config.get("chunk_size", 512)
        self.chunk_overlap = config.get("chunk_overlap", 64)
    
    def chunk(self, document: Document) -> List[Chunk]:
        raise NotImplementedError


class BaseEmbedder:
    """嵌入器基类"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.model = config.get("model", "text-embedding-ada-002")
        self.dimension = config.get("dimension", 1536)
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class BaseSearchEngine:
    """搜索引擎基类"""
    
    def __init__(self, config: Dict):
        self.top_k = config.get("top_k", 5)
    
    async def search(self, query: str, chunks: List[Chunk]) -> List[Chunk]:
        raise NotImplementedError


class BaseRanker:
    """重排序器基类"""
    
    def __init__(self, config: Dict):
        self.top_k = config.get("rerank_top_k", 3)
    
    async def rerank(self, query: str, chunks: List[Chunk]) -> List[Chunk]:
        raise NotImplementedError
