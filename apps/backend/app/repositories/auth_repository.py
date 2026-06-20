
from sqlalchemy.orm import Session

from app.models.user import User

class AuthRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_email(self, email: str) -> User:
        return self.db.query(User).filter(User.email == email.lower()).first()
    
    def create_user(self, email: str, password: str, first_name: str, last_name: str) -> User:
        user = User(
            email=email,
            first_name = first_name,
            last_name = last_name,
            password = password,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user