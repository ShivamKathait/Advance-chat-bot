from fastapi import HTTPException, status

from app.core.guardrails import check_harmful_content, check_prompt_injection, validate_llm_output
from app.core.security import sanitize_input
from app.core.logging import logger_adapter
from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import ChatRequest, ChatResponse, Source
from app.services.vector_service import VectorStoreService


class ChatService:
    def __init__(self, vector_service: VectorStoreService, chat_repository: ChatRepository):
        self.vector_service = vector_service
        self.chat_repository = chat_repository

    async def chat_query(self, request: ChatRequest) -> ChatResponse:
        try:
            message = sanitize_input(request.message, max_length=500)

            # Guardrail — input checks (raise 400 on violation)
            check_prompt_injection(message)
            check_harmful_content(message)

            # 1. Get or create conversation in DB
            conversation = self.chat_repository.get_or_create_conversation(
                request.conversation_id
            )
            conversation_id = str(conversation.id)

            logger_adapter.info(
                "Chat query received",
                message_length=len(message),
                conversation_id=conversation_id,
            )

            # 2. Load recent history from DB and format for LLM
            db_messages = self.chat_repository.get_messages(conversation.id, limit=10)
            conversation_history = [
                {"role": msg.role, "content": msg.content} for msg in db_messages
            ]
    
            # 3. Run RAG pipeline
            result = await self.vector_service.process_query(
                query=message,
                conversation_id=conversation_id,
                top_k=request.top_k,
                conversation_history=conversation_history or None,
            )

            # Guardrail — output validation (no hallucination / jailbreak output)
            safe_response = validate_llm_output(result["response"], result["sources"])

            # 4. Persist this turn to DB
            self.chat_repository.add_message(conversation.id, role="user", content=message)
            self.chat_repository.add_message(conversation.id, role="assistant", content=safe_response)

            sources = [
                Source(
                    content=source["content"],
                    score=source["score"],
                    metadata=source["metadata"],
                )
                for source in result["sources"]
            ]

            return ChatResponse(
                response=safe_response,
                sources=sources,
                conversation_id=conversation_id,
                num_sources=result["num_sources"],
            )

        except ValueError as e:
            logger_adapter.error(f"Validation error: {str(e)}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger_adapter.error(f"Error processing chat query: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable",
            )

    async def stream_query(self, request: ChatRequest):
        """
        Streaming RAG query — async generator yielding SSE event dicts.
        Runs the same guardrails as chat_query, then streams tokens from the LLM.
        Persists messages to DB after the stream completes.
        """
        message = sanitize_input(request.message, max_length=500)
        check_prompt_injection(message)
        check_harmful_content(message)

        conversation = self.chat_repository.get_or_create_conversation(request.conversation_id)
        conversation_id = str(conversation.id)

        db_messages = self.chat_repository.get_messages(conversation.id, limit=10)
        conversation_history = [
            {"role": msg.role, "content": msg.content} for msg in db_messages
        ]

        full_response = ""
        sources = []

        async for event in self.vector_service.process_query_stream(
            query=message,
            conversation_id=conversation_id,
            top_k=request.top_k,
            conversation_history=conversation_history or None,
        ):
            if event["type"] == "token":
                full_response += event["content"]
                yield event
            elif event["type"] == "sources":
                sources = event.get("sources", [])
                yield event
            elif event["type"] == "done":
                safe_response = validate_llm_output(full_response, sources)
                self.chat_repository.add_message(conversation.id, role="user", content=message)
                self.chat_repository.add_message(conversation.id, role="assistant", content=safe_response)
                yield {"type": "done", "conversation_id": conversation_id}
