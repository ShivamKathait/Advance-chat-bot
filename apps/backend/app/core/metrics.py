from prometheus_client import Counter, Histogram

rag_query_duration = Histogram(
    "rag_query_duration_seconds",
    "Total RAG pipeline latency in seconds",
    ["rerank_enabled", "bm25_enabled"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

rag_llm_duration = Histogram(
    "rag_llm_duration_seconds",
    "LLM generation latency in seconds",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

rag_retrieve_duration = Histogram(
    "rag_retrieve_duration_seconds",
    "Vector retrieval latency in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

rag_empty_sources = Counter(
    "rag_empty_sources_total",
    "Number of queries that returned 0 document chunks",
)

rag_chunks_retrieved = Histogram(
    "rag_chunks_retrieved",
    "Number of chunks returned after full pipeline (dedup + rerank)",
    buckets=[0, 1, 2, 3, 4, 5, 8, 10],
)

rag_feedback_total = Counter(
    "rag_feedback_total",
    "User feedback submissions",
    ["rating"],
)
