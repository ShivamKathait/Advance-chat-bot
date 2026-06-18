import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_conversation(self, conversation_id: Optional[str]) -> Conversation:
        """Return existing conversation or create a new one."""
        if conversation_id:
            conv = self.db.query(Conversation).filter(
                Conversation.id == uuid.UUID(conversation_id)
            ).first()
            if conv:
                return conv

        conv = Conversation(id=uuid.uuid4())
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def add_message(self, conversation_id: uuid.UUID, role: str, content: str) -> Message:
        """Append a message to a conversation."""
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_messages(self, conversation_id: uuid.UUID, limit: int = 10) -> List[Message]:
        """Return the most recent `limit` messages for a conversation, oldest first."""
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()[::-1]
        )
