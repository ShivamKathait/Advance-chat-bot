


import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.services import get_chat_service
from app.models.feedback import Feedback
from app.schemas.chat import ChatRequest, FeedbackRequest
from app.services.chat_service import ChatService

import app.models.feedback  # noqa: F401 — registers Feedback with Base.metadata

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


@router.post("/query")
async def chat(request: ChatRequest, service: ChatService = Depends(get_chat_service)):
    return await service.chat_query(request)


@router.post("/stream")
async def chat_stream(request: ChatRequest, service: ChatService = Depends(get_chat_service)):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).

    Event types:
      data: {"type": "token",   "content": "<text>"}
      data: {"type": "sources", "sources": [...], "num_sources": N}
      data: {"type": "done",    "conversation_id": "<uuid>"}
      data: [DONE]
    """
    async def event_generator():
        async for event in service.stream_query(request):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{conversation_id}/feedback")
async def submit_feedback(
    conversation_id: str,
    body: FeedbackRequest,
    db: Session = Depends(get_db),
):
    """Record user feedback (thumbs up / thumbs down) on a chat answer."""
    from app.core.metrics import rag_feedback_total
    from app.core.logging import logger_adapter

    feedback = Feedback(
        id=uuid.uuid4(),
        conversation_id=uuid.UUID(conversation_id),
        rating=body.rating,
        comment=body.comment,
        query=body.query,
        response=body.response,
    )
    db.add(feedback)
    db.commit()

    rag_feedback_total.labels(rating=str(body.rating)).inc()

    if body.rating == 1:
        logger_adapter.warning(
            "Negative feedback received",
            conversation_id=conversation_id,
            query_preview=body.query[:80],
        )

    return {"status": "recorded", "conversation_id": conversation_id, "rating": body.rating}
