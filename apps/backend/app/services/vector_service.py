
import asyncio
import collections
import datetime
import json
import time
import uuid
import redis.asyncio as aioredis

from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.exceptions import VectorStoreError
from app.core.logging import logger_adapter
from app.core.config import settings
from app.core.metrics import (
    rag_chunks_retrieved,
    rag_empty_sources,
    rag_llm_duration,
    rag_query_duration,
    rag_retrieve_duration,
)
from app.services.Ingestion_service import EmbeddingGenerator
from app.services.llm_service import LLMService
from rank_bm25 import BM25Okapi
from app.services.rerank_service import CohereRerankService

# Rolling window of pipeline timing records for the /debug/rag-stats endpoint
_pipeline_stats: collections.deque = collections.deque(maxlen=100)

class QdrantVectorStore:
    """
    Qdrant vector store for document embeddings
    """

    def __init__(self):
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        self.collection_name = settings.QDRANT_COLLECTION
        self.vector_size = settings.QDRANT_VECTOR_SIZE

    async def initialize(self):
        """
        Initialize vector collection — creates it if it doesn't exist.
        Auto-recreates if the existing collection has a different vector size.
        """
        try:
            info = await self.client.get_collection(self.collection_name)
            existing_size = info.config.params.vectors.size
            if existing_size != self.vector_size:
                logger_adapter.warning(
                    f"Collection vector size mismatch: found {existing_size}, "
                    f"expected {self.vector_size}. Recreating collection."
                )
                await self.client.delete_collection(self.collection_name)
            else:
                logger_adapter.info(f"Collection '{self.collection_name}' already exists")
                await self._ensure_document_id_index()
                return
        except UnexpectedResponse:
            pass  # Collection doesn't exist — fall through to create
        except Exception as e:
            logger_adapter.error(f"Error initializing collection: {str(e)}")
            raise VectorStoreError(f"Failed to initialize Qdrant collection: {e}")

        try:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                ),
            )
            logger_adapter.info(f"Collection '{self.collection_name}' created successfully")
            await self._ensure_document_id_index()
        except Exception as e:
            logger_adapter.error(f"Error creating collection: {str(e)}")
            raise VectorStoreError(f"Failed to create Qdrant collection: {e}")

    async def _ensure_document_id_index(self):
        """
        Create a keyword payload index on 'document_id' if it doesn't already exist.
        Required for filtered queries/deletes (e.g. delete_by_document_id, per-document search)
        — Qdrant rejects filters on un-indexed fields with a 400 Bad Request.
        """
        try:
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="document_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            logger_adapter.info("Payload index ensured on 'document_id'")
        except UnexpectedResponse as e:
            if "already exists" not in str(e):
                raise

    @staticmethod
    def _point_id(chunk_id: str) -> int:
        """Stable, collision-resistant conversion from UUID string to Qdrant int ID."""
        return int(uuid.UUID(chunk_id)) % (2 ** 63)

    async def upsert_points(self, points: List[Dict[str, Any]]) -> bool:
        """
        Insert or update points (embeddings) in Qdrant

        Args:
            points: List of points with id, vector, text, and payload keys

        Returns:
            True if successful
        """
        try:
            qdrant_points = [
                PointStruct(
                    id=self._point_id(point["id"]),
                    vector=point["vector"],
                    payload={
                        "id": point["id"],
                        "text": point["text"],
                        **point.get("payload", {})
                    }
                )
                for point in points
            ]

            await self.client.upsert(
                collection_name=self.collection_name,
                points=qdrant_points,
            )

            logger_adapter.info(f"Upserted {len(qdrant_points)} points to Qdrant")
            return True
        except Exception as e:
            logger_adapter.error(f"Error upserting points: {str(e)}")
            raise VectorStoreError(f"Failed to upsert points: {e}")

    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        score_threshold: float = None,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors

        Args:
            query_vector: Query embedding
            top_k: Number of results to return
            score_threshold: Minimum similarity score
            filters: Metadata filters

        Returns:
            List of similar documents with scores
        """
        try:
            query_filter = None
            if filters:
                query_filter = self._build_filter(filters)

            response = await self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold,  # None = no threshold; top_k controls result count
            )
            results = response.points

            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": result.payload.get("id"),
                    "text": result.payload.get("text"),
                    "score": result.score,
                    "metadata": {
                        k: v for k, v in result.payload.items()
                        if k not in ["id", "text"]
                    }
                })

            logger_adapter.info(f"Found {len(results)} results for query")
            return formatted_results

        except Exception as e:
            logger_adapter.error(f"Error searching vectors: {str(e)}")
            raise VectorStoreError(f"Failed to search vectors: {e}")

    def _build_filter(self, filters: Dict[str, Any]) -> models.Filter:
        """
        Build Qdrant filter from metadata key-value pairs.
        """
        conditions = []

        for key, value in filters.items():
            if isinstance(value, list):
                conditions.append(
                    models.FieldCondition(key=key, match=models.MatchAny(any=value))
                )
            else:
                conditions.append(
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                )

        return models.Filter(must=conditions) if conditions else None

    async def delete_by_document_id(self, document_id: str) -> bool:
        """
        Delete all points belonging to a document by filtering on the
        'document_id' payload field (not by Qdrant internal point integer IDs).

        Args:
            document_id: Document UUID string

        Returns:
            True if successful
        """
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=str(document_id)),
                            )
                        ]
                    )
                ),
            )

            logger_adapter.info(f"Deleted points for document: {document_id}")
            return True

        except Exception as e:
            logger_adapter.error(f"Error deleting points: {str(e)}")
            raise VectorStoreError(f"Failed to delete points: {e}")

    async def get_collection_info(self) -> Dict[str, Any]:
        """
        Get collection statistics
        """
        try:
            info = await self.client.get_collection(self.collection_name)

            return {
                "name": self.collection_name,
                "points_count": info.points_count,
                "status": info.status,
            }

        except Exception as e:
            logger_adapter.error(f"Error getting collection info: {str(e)}")
            return {}


class VectorStoreService:
    """
    High-level vector store service — wraps Qdrant operations with business logic.
    """

    def __init__(self, embedding_generator: EmbeddingGenerator):
        self.store = QdrantVectorStore()
        self.embedding_generator = embedding_generator
        self.llm_service = LLMService()
        self._redis = None  # lazy-initialised on first BM25 call
        self._bm25_index = None
        self._bm25_chunks = None
        self._bm25_cached_version = None

        self.reranker = None
        if settings.USE_RERANKER and settings.COHERE_API_KEY:
            try:
                self.reranker = CohereRerankService()
                logger_adapter.info("Cohere reranker initialised")
            except Exception as e:
                logger_adapter.warning(f"Reranker init failed, disabling: {e}")

    async def initialize(self):
        """Initialize vector store (create collection if needed)."""
        await self.store.initialize()

    async def add_document_chunks(self, chunks_data: List[Dict[str, Any]]) -> bool:
        """
        Add document chunks to vector store.

        Args:
            chunks_data: List of chunks with id, text, embedding, and metadata keys

        Returns:
            True if successful
        """
        try:
            points = [
                {
                    "id": chunk["id"],
                    "vector": chunk["embedding"],
                    "text": chunk["text"],
                    "payload": chunk.get("metadata", {})
                }
                for chunk in chunks_data
            ]

            return await self.store.upsert_points(points)

        except Exception as e:
            logger_adapter.error(f"Error adding chunks: {str(e)}")
            raise

    @staticmethod
    def _deduplicate_chunks(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove exact-duplicate chunks (same document + chunk index appearing twice,
        e.g. once from dense search and once from BM25).

        Does NOT drop merely-adjacent chunks: with CHUNK_SIZE=1000/CHUNK_OVERLAP=200,
        neighboring chunks share only ~20% overlap text — each still carries ~80%
        unique content, so discarding a whole neighbor on proximity alone throws away
        real information and was causing genuine retrieval misses.
        """
        results = sorted(results, key=lambda r: r["score"], reverse=True)
        kept: List[Dict[str, Any]] = []
        seen: Dict[str, set] = {}  # doc_id -> set of kept chunk indices

        for r in results:
            doc_id = r["metadata"].get("document_id", "")
            chunk_idx = r["metadata"].get("chunk_index", -1)
            doc_seen = seen.setdefault(doc_id, set())

            if chunk_idx in doc_seen:
                continue

            doc_seen.add(chunk_idx)
            kept.append(r)

        return kept

    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = None,
        document_id: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results
            score_threshold: Minimum similarity score (None = no threshold)
            document_id: Filter by specific document (optional)

        Returns:
            List of similar documents
        """
        filters = None
        if document_id:
            filters = {"document_id": str(document_id)}

        return await self.store.search(
            query_vector=query_embedding,
            top_k=top_k,
            score_threshold=score_threshold,
            filters=filters,
        )

    async def remove_document(self, document_id: str) -> bool:
        """
        Remove all chunks for a document.

        Args:
            document_id: Document UUID string

        Returns:
            True if successful
        """
        return await self.store.delete_by_document_id(document_id)

    async def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        return await self.store.get_collection_info()

    async def _get_redis(self):
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def _timed_bm25_search(self, query: str, top_k: int) -> tuple:
        """Wraps _bm25_search with its own timer, since the caller awaits this
        task after dense retrieval — timing from the caller's perspective would
        include the overlapped wait, not the actual BM25 work duration."""
        t0 = time.perf_counter()
        results = await self._bm25_search(query, top_k=top_k)
        return results, round((time.perf_counter() - t0) * 1000)

    async def _bm25_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        try:
            r = await self._get_redis()
            current_version = await r.get("bm25:version")

            if self._bm25_index is not None and current_version == self._bm25_cached_version:
                bm25, all_chunks = self._bm25_index, self._bm25_chunks
            else:
                doc_keys = await r.smembers("bm25:doc_keys")
                if not doc_keys:
                    self._bm25_index = self._bm25_chunks = None
                    self._bm25_cached_version = current_version
                    return []
                all_chunks: List[Dict[str, Any]] = []
                for key in doc_keys:
                    raw = await r.get(key)
                    if raw:
                        all_chunks.extend(json.loads(raw))
                if not all_chunks:
                    self._bm25_index = self._bm25_chunks = None
                    self._bm25_cached_version = current_version
                    return []
                corpus = [c["text"].lower().split() for c in all_chunks]
                bm25 = BM25Okapi(corpus)
                self._bm25_index, self._bm25_chunks = bm25, all_chunks
                self._bm25_cached_version = current_version

            scores = bm25.get_scores(query.lower().split())
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
            return [
                {
                    "id": all_chunks[i]["id"],
                    "text": all_chunks[i]["text"],
                    "score": float(scores[i]),
                    "metadata": all_chunks[i].get("metadata", {}),
                }
                for i in top_indices if scores[i] > 0
            ]
        except Exception as e:
            logger_adapter.warning(f"BM25 search failed, skipping: {e}")
            return []

    @staticmethod
    def _reciprocal_rank_fusion(
        dense: List[Dict[str, Any]],
        sparse: List[Dict[str, Any]],
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        scores: Dict[str, float] = {}
        chunks: Dict[str, Dict[str, Any]] = {}
        for rank, r in enumerate(dense):
            cid = str(r.get("id", ""))
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            chunks[cid] = r
        for rank, r in enumerate(sparse):
            cid = str(r.get("id", ""))
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            if cid not in chunks:
                chunks[cid] = r
        return sorted(chunks.values(), key=lambda r: scores[str(r.get("id", ""))], reverse=True)

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Return aggregate stats from the last 100 pipeline runs."""
        if not _pipeline_stats:
            return {"message": "no queries processed yet"}
        records = list(_pipeline_stats)
        total = len(records)
        empty = sum(1 for r in records if r.get("num_chunks", 0) == 0)

        def avg(key: str) -> Optional[float]:
            vals = [r[key] for r in records if key in r]
            return round(sum(vals) / len(vals), 1) if vals else None

        return {
            "total_queries": total,
            "empty_source_rate": f"{empty / total:.0%}",
            "avg_latency": {
                "rewrite_ms": avg("rewrite_ms"),
                "embed_retrieve_ms": avg("embed_retrieve_ms"),
                "bm25_ms": avg("bm25_ms"),
                "rerank_ms": avg("rerank_ms"),
                "llm_ms": avg("llm_ms"),
            },
            "avg_chunks_returned": avg("num_chunks"),
        }

    async def _embed_and_search(self, q: str, fetch_k: int) -> List[Dict[str, Any]]:
        q_embedding = await self.embedding_generator.generate_embedding(q)
        return await self.search_similar(
            query_embedding=q_embedding,
            top_k=fetch_k,
            score_threshold=settings.SIMILARITY_THRESHOLD,
        )

    async def retrieve(
        self,
        query: str,
        top_k: int = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        rewrite: bool = True,
    ) -> Dict[str, Any]:
        """
        Retrieval-only portion of the RAG pipeline — no LLM generation.

        Steps:
        1. Query rewriting (optional) — runs concurrently with BM25 search below,
           since BM25 only needs the original query, not the rewritten ones.
        2. Dense retrieval
        3. BM25 sparse retrieval + Reciprocal Rank Fusion
        4. Deduplicate overlapping chunks
        5. Cross-encoder reranking

        Returns:
            Dictionary with sources, num_sources, context, and per-stage timings
        """
        timings: Dict[str, Any] = {}
        desired_k = top_k or settings.TOP_K_RETRIEVAL
        # Fetch more candidates when reranker is active so it has room to reorder
        fetch_k = settings.MAX_RERANK_CANDIDATES if self.reranker else desired_k

        # BM25 doesn't depend on query rewriting/dense retrieval — kick it off now
        # so it overlaps with those instead of running after them.
        bm25_task = None
        if settings.BM25_ENABLED:
            bm25_task = asyncio.create_task(self._timed_bm25_search(query, fetch_k))

        # 1. Query rewriting — expand abbreviations and decompose multi-part questions
        if rewrite and settings.QUERY_REWRITE_ENABLED:
            t0 = time.perf_counter()
            rewritten_queries = await self.llm_service.rewrite_query(query, conversation_history)
            timings["rewrite_ms"] = round((time.perf_counter() - t0) * 1000)
            logger_adapter.info("Query rewritten", rewrites=rewritten_queries)
        else:
            rewritten_queries = [query]

        # 2. Dense retrieval — embed+search all rewritten queries concurrently, merge unique results
        t0 = time.perf_counter()
        seen_chunk_keys: set = set()
        dense_results: List[Dict[str, Any]] = []
        results_per_query = await asyncio.gather(
            *[self._embed_and_search(q, fetch_k) for q in rewritten_queries]
        )
        for results in results_per_query:
            for r in results:
                key = r["metadata"].get("document_id", "") + str(r["metadata"].get("chunk_index", ""))
                if key not in seen_chunk_keys:
                    seen_chunk_keys.add(key)
                    dense_results.append(r)
        timings["embed_retrieve_ms"] = round((time.perf_counter() - t0) * 1000)

        # 3. BM25 sparse retrieval + Reciprocal Rank Fusion
        raw_results = dense_results
        if bm25_task is not None:
            bm25_results, timings["bm25_ms"] = await bm25_task
            if bm25_results:
                raw_results = self._reciprocal_rank_fusion(dense_results, bm25_results)

        # 4. Remove overlapping chunks (caused by 200-char ingestion overlap)
        raw_results = self._deduplicate_chunks(raw_results)

        # 5. Cross-encoder reranking — reorder by true query-chunk relevance
        if self.reranker and raw_results:
            t0 = time.perf_counter()
            try:
                raw_results = await self.reranker.rerank(
                    query=query,
                    chunks=raw_results,
                    top_n=desired_k,
                )
                timings["rerank_ms"] = round((time.perf_counter() - t0) * 1000)
            except Exception as rerank_err:
                logger_adapter.warning(f"Reranker failed, using dense order: {rerank_err}")
                raw_results = raw_results[:desired_k]
        else:
            raw_results = raw_results[:desired_k]

        context = "\n\n".join(r["text"] for r in raw_results)
        sources = [
            {
                "content": r["text"],
                "score": r.get("rerank_score", r["score"]),
                "metadata": r["metadata"],
            }
            for r in raw_results
        ]

        return {
            "sources": sources,
            "num_sources": len(raw_results),
            "context": context,
            "timings": timings,
        }

    async def process_query(
        self,
        query: str,
        conversation_id: str,
        top_k: int = None,
        use_context: bool = True,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Process user query through full RAG pipeline

        Steps:
        1. Generate embedding for query
        2. Retrieve relevant documents
        3. Format context
        4. Generate response with LLM
        5. Save to conversation history

        Args:
            query: User query
            conversation_id: Conversation ID (new if not provided)
            top_k: Number of documents to retrieve
            use_context: Whether to use retrieved context

        Returns:
            Dictionary with response, sources, and metadata
        """
        try:
            logger_adapter.info("Processing query", query=query[:100], conversation_id=conversation_id)

            retrieval = await self.retrieve(query, top_k=top_k, conversation_history=conversation_history)
            timings = retrieval["timings"]
            sources = retrieval["sources"]
            num_docs = retrieval["num_sources"]
            context = retrieval["context"]

            # 6. LLM response generation
            t0 = time.perf_counter()
            response = await self.llm_service.generate_response(
                query=query,
                context=context if use_context else "",
                conversation_history=conversation_history,
            )
            llm_elapsed = time.perf_counter() - t0
            timings["llm_ms"] = round(llm_elapsed * 1000)

            timings["num_chunks"] = num_docs
            _pipeline_stats.append(timings)

            # Prometheus metrics
            total_elapsed = sum(v for k, v in timings.items() if k.endswith("_ms")) / 1000
            rag_query_duration.labels(
                rerank_enabled=str(bool(self.reranker)),
                bm25_enabled=str(settings.BM25_ENABLED),
            ).observe(total_elapsed)
            rag_llm_duration.observe(llm_elapsed)
            rag_retrieve_duration.observe(timings.get("embed_retrieve_ms", 0) / 1000)
            rag_chunks_retrieved.observe(num_docs)
            if num_docs == 0:
                rag_empty_sources.inc()

            logger_adapter.info(
                "RAG pipeline complete",
                **timings,
                rerank_enabled=bool(self.reranker),
                bm25_enabled=settings.BM25_ENABLED,
                query_preview=query[:60],
            )

            return {
                "conversation_id": conversation_id,
                "query": query,
                "response": response,
                "sources": sources,
                "num_sources": num_docs,
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger_adapter.error(f"Error processing query: {str(e)}")
            raise

    async def process_query_stream(
        self,
        query: str,
        conversation_id: str,
        top_k: int = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ):
        """
        Streaming RAG pipeline — same retrieval steps as process_query, but yields
        token events from the LLM as they arrive instead of waiting for the full response.

        Yields dicts:
          {"type": "token",   "content": "<text>"}
          {"type": "sources", "sources": [...], "num_sources": N}
          {"type": "done"}
        """
        # 1-5. Retrieval (rewrite, dense + BM25 search, dedup, rerank) — shared with process_query
        retrieval = await self.retrieve(query, top_k=top_k, conversation_history=conversation_history)
        context = retrieval["context"]
        sources = retrieval["sources"]
        num_docs = retrieval["num_sources"]

        # 6. Stream LLM tokens
        async for token in self.llm_service.generate_response_stream(
            query=query,
            context=context,
            conversation_history=conversation_history,
        ):
            yield {"type": "token", "content": token}

        # Prometheus counters (post-stream)
        rag_chunks_retrieved.observe(num_docs)
        if num_docs == 0:
            rag_empty_sources.inc()

        yield {"type": "sources", "sources": sources, "num_sources": num_docs}
        yield {"type": "done"}


# Export service
vector_store = VectorStoreService(embedding_generator=EmbeddingGenerator())
