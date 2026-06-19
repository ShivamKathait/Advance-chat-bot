from typing import List, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

class Source(BaseModel):
    """Source document reference"""
    content: str = Field(..., description="Document snippet")
    score: float = Field(..., description="Similarity score")
    metadata: dict = Field(default_factory=dict, description="Document metadata")


class ChatRequest(BaseModel):
    """Chat query request"""
    message: str = Field(..., description="User message", min_length=1, max_length=500)
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    top_k: Optional[int] = Field(5, description="Number of documents to retrieve", ge=1, le=20)


class ChatResponse(BaseModel):
    """Chat response with sources"""
    response: str = Field(..., description="AI response")
    sources: List[Source] = Field(default_factory=list, description="Source documents")
    conversation_id: str = Field(..., description="Conversation ID")
    num_sources: int = Field(0, description="Number of sources used")
 
 
class ConversationMessage(BaseModel):
    """Single conversation message"""
    role: str = Field(..., description="message role: user or assistant")
    content: str = Field(..., description="Message content")
 
 
class ConversationHistory(BaseModel):
    """Conversation history"""
    conversation_id: str


class FeedbackRequest(BaseModel):
    """User feedback on a chat answer"""
    rating: int = Field(..., description="1 = thumbs down, 5 = thumbs up", ge=1, le=5)
    comment: Optional[str] = Field(None, description="Optional comment")
    query: str = Field(..., description="The query that was asked")
    response: str = Field(..., description="The response that was rated")