import cohere

from typing import List, Dict, Any


from app.core.config import settings
from app.core.logging import logger_adapter


class CohereRerankService:
    def __init__(self):
        self.client = cohere.AsyncClientV2(api_key=settings.COHERE_API_KEY)
        self.model = settings.COHERE_RERANK_MODEL

    async def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_n: int,
    ) -> List[Dict[str, Any]]:
        if not chunks:
            return chunks

        response = await self.client.rerank(
            model=self.model,
            query=query,
            documents=[c["text"] for c in chunks],
            top_n=min(top_n, len(chunks)),
        )

        reranked = [
            {**chunks[r.index], "rerank_score": r.relevance_score}
            for r in response.results
        ]
        logger_adapter.info(
            "Reranking complete",
            input_chunks=len(chunks),
            output_chunks=len(reranked),
        )
        return reranked
