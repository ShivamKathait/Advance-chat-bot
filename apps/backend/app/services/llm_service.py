import json
import re
from typing import List, Optional

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.exceptions import LLMServiceError
from app.core.logging import logger_adapter


class LLMService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL
        self._system_instruction = (
            "You are a helpful assistant that answers questions strictly from the provided document context.\n\n"
            "Rules:\n"
            "- Answer ONLY from the provided context. If the context does not contain enough information, "
            "say so clearly — do not guess or use outside knowledge.\n"
            "- Format every response in clean Markdown so the frontend can render it directly:\n"
            "  - Use **bold** for key terms, dates, numbers, and important values.\n"
            "  - Use bullet points or numbered lists for any list of items.\n"
            "  - Use `##` headers to separate distinct sections when the answer covers multiple topics.\n"
            "  - Use a Markdown table when presenting structured data (e.g. a list of holidays with dates).\n"
            "- Start directly with the answer — no preamble like 'Based on the context...' or 'According to the document...'.\n"
            "- Keep paragraphs short and scannable.\n"
            "- Be concise and to the point. Never restate or repeat a fact you have already mentioned.\n"
            "- Do NOT present the same information at both a summary/table level and again in detail sections — pick one level of detail appropriate to the question."
        )

    async def generate_response(
        self,
        query: str,
        context: str,
        conversation_history: Optional[List[dict]] = None,
    ) -> str:
        contents = []

        # Replay prior turns — Gemini uses role "model" for assistant
        if conversation_history:
            for msg in conversation_history:
                role = "model" if msg["role"] == "assistant" else msg["role"]
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        if context:
            user_text = f"Context:\n{context}\n\nQuestion: {query}"
        else:
            user_text = (
                "No relevant document chunks were retrieved for this question.\n\n"
                f"Question: {query}"
            )
        contents.append({"role": "user", "parts": [{"text": user_text}]})

        logger_adapter.info("Calling Gemini API", model=self.model, turns=len(contents))

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=self._system_instruction,
                    max_output_tokens=settings.OPENAI_MAX_TOKENS,
                ),
            )
        except Exception as e:
            logger_adapter.error(f"Gemini generate_content failed: {e}")
            raise LLMServiceError(f"Failed to generate response: {e}")

        return response.text

    async def generate_response_stream(
        self,
        query: str,
        context: str,
        conversation_history: Optional[List[dict]] = None,
    ):
        """Async generator — yields text tokens from Gemini as they arrive."""
        contents = []
        if conversation_history:
            for msg in conversation_history:
                role = "model" if msg["role"] == "assistant" else msg["role"]
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        if context:
            user_text = f"Context:\n{context}\n\nQuestion: {query}"
        else:
            user_text = (
                "No relevant document chunks were retrieved for this question.\n\n"
                f"Question: {query}"
            )
        contents.append({"role": "user", "parts": [{"text": user_text}]})

        logger_adapter.info("Streaming Gemini response", model=self.model, turns=len(contents))

        try:
            stream = await self.client.aio.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=self._system_instruction,
                    max_output_tokens=settings.OPENAI_MAX_TOKENS,
                ),
            )
            async for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger_adapter.error(f"Gemini streaming failed: {e}")
            raise LLMServiceError(f"Failed to stream response: {e}")

    async def rewrite_query(
        self,
        query: str,
        conversation_history: Optional[List[dict]] = None,
    ) -> List[str]:
        """
        Expand abbreviations and decompose multi-part questions into 1–3 search queries.
        Returns the original query as a fallback on any error.
        """
        history_ctx = ""
        if conversation_history:
            for msg in conversation_history[-2:]:
                history_ctx += f"{msg['role']}: {msg['content']}\n"

        prompt = (
            "You are a query preprocessor for a document search system.\n"
            "Given the user question, return 1–3 search queries that will best retrieve "
            "relevant document chunks.\n\n"
            "Rules:\n"
            "- If the question uses an abbreviation or acronym, expand it only if its meaning "
            "is clear from the conversation history or the question's own context; otherwise "
            "leave it as-is rather than guessing.\n"
            "- If the question has multiple distinct sub-questions, split into separate queries.\n"
            "- Otherwise return exactly 1 query.\n"
            "- Output ONLY a JSON array of strings. No explanation, no markdown.\n\n"
            + (f"Prior context:\n{history_ctx}\n" if history_ctx else "")
            + f"Question: {query}\n\nOutput:"
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config=types.GenerateContentConfig(max_output_tokens=200),
            )
            match = re.search(r'\[.*?\]', response.text, re.DOTALL)
            if match:
                queries = json.loads(match.group())
                cleaned = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
                if cleaned:
                    return cleaned
        except Exception as e:
            logger_adapter.warning(f"Query rewrite failed, falling back to original query: {e}")

        return [query]
