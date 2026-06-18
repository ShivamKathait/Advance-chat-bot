
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from app.core.config import settings
from jose import jwt, JWTError
from fastapi import status, Security,HTTPException
import secrets
import hashlib
import time

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Security
security = HTTPBearer()
 

class SecurityUtils:
    """Security utilities for authentication and authorization"""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hash
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            True if password matches, False otherwise
        """

        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token
        
        Args:
            data: Data to encode in token
            expires_delta: Token expiration time
            
        Returns:
            Encoded JWT token
        """

        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MIN)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })

        encode_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encode_jwt


    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """
        Create a JWT refresh token
        
        Args:
            data: Data to encode in token
            
        Returns:
            Encoded JWT refresh token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        Decode and validate a JWT token
        
        Args:
            token: JWT token
            
        Returns:
            Decoded token payload
            
        Raises:
            HTTPException: If token is invalid
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError as e:
            # logger.error(f"JWT decode error: {str(e)}")
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = "Could not validate credentials",
                headers = {"WWW-Authenticate": "Bearer"},
            )
            
    @staticmethod
    def generate_api_key() -> str:
        """
        Generate a secure API key
        
        Returns:
            Random API key
        """
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """
        Hash an API key for storage
        
        Args:
            api_key: API key to hash
            
        Returns:
            Hashed API key
        """
        return hashlib.sha256(api_key.encode()).hexdigest()
    

# Dependency for protected routes
async def get_current_user(credentials:HTTPAuthorizationCredentials = Security(security)) -> Dict[str,Any]:
    """
    Dependency to get current authenticated user
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        Current user data from token
        
    Raises:
        HTTPException: If authentication fails
    """

    token = credentials.credentials
    payload = SecurityUtils.decode_token(token)

    # Validate token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    # Extract user info
    user_id = payload.get("user_id")
    session_id = payload.get("session_id")

    if user_id is None or session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    return {
        "user_id": user_id,
        "session_id": session_id,
        "email": payload.get("email"),
        "role": payload.get("role", "user")
    }


# Optional authentication (allows anonymous access)
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[Dict[str, Any]]:
    """
    Dependency for optional authentication
    
    Args:
        credentials: Optional HTTP Bearer credentials
        
    Returns:
        Current user data if authenticated, None otherwise
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
    


class RateLimiter:
    """
    Simple in-memory rate limiter
    
    For production, use Redis-based rate limiting
    """

    def __init__(self):
        self.requests: Dict[str, list] = {}

    def is_allowed(self, key: str, max_request: int = 100, window_seconds: int = 60) -> bool:
        """
        Check if request is allowed under rate limit
        
        Args:
            key: Identifier (user_id, IP, etc.)
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            True if request is allowed, False otherwise
        """
         
        now = time.time()
        window_start = now - window_seconds

        # Get request timestamps for this key
        if key not in self.requests:
            self.requests[key] = []

        # Remove old requests outside the window
        self.requests[key] = [
            ts for ts in self.requests[key]
            if ts > window_start
        ]

        # Check if under limit
        if len(self.requests[key]) >= max_request:
            return False
        
        # Add current request
        self.requests[key].append(now)
        return True
    
    def get_remaining(self, key: str, max_request: int = 100) -> int:
        """
        Get remaining requests for key
        
        Args:
            key: Identifier
            max_requests: Maximum requests allowed
            
        Returns:
            Number of remaining requests
        """
        if key not in self.requests:
            return max_request
        
        return max(0, max_request - len(self.requests[key]))
    

# Global rate limiter instance
rate_limiter = RateLimiter()



def sanitize_input(text: str, max_length: int = 10000) -> str:
    """
    Sanitize user input to prevent injection attacks
    
    Args:
        text: Input text
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
        
    Raises:
        HTTPException: If input is invalid
    """
    # Check length
    if len(text) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input too long. Maximum {max_length} characters allowed."
        )
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # Check for empty input
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input cannot be empty"
        )
    
    return text
 
 
def validate_api_key(api_key: str) -> bool:
    """
    Validate an API key
    
    Args:
        api_key: API key to validate
        
    Returns:
        True if valid, False otherwise
    """
    # TODO: Implement actual API key validation
    # This should check against stored hashed keys in database
    return len(api_key) == 43  # Length of token_urlsafe(32)
 
 
class PII:
    """
    PII (Personally Identifiable Information) detection and masking
    """
    
    @staticmethod
    def mask_email(email: str) -> str:
        """
        Mask email address for logging
        
        Args:
            email: Email address
            
        Returns:
            Masked email (e.g., j***@example.com)
        """
        if '@' not in email:
            return email
        
        local, domain = email.split('@', 1)
        if len(local) <= 2:
            masked_local = local[0] + '*'
        else:
            masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        """
        Mask phone number for logging
        
        Args:
            phone: Phone number
            
        Returns:
            Masked phone (e.g., ***-***-1234)
        """
        # Remove non-digits
        digits = ''.join(c for c in phone if c.isdigit())
        
        if len(digits) < 4:
            return '*' * len(phone)
        
        return '*' * (len(digits) - 4) + digits[-4:]
    
    @staticmethod
    def contains_sensitive_data(text: str) -> bool:
        """
        Check if text contains potentially sensitive data
        
        Args:
            text: Text to check
            
        Returns:
            True if sensitive data detected
        """
        # Simple heuristics - expand as needed
        import re
        
        # Email pattern
        if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
            return True
        
        # Credit card pattern (basic)
        if re.search(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', text):
            return True
        
        # SSN pattern
        if re.search(r'\b\d{3}-\d{2}-\d{4}\b', text):
            return True
        
        return False
 
 
# Export utilities
__all__ = [
    'SecurityUtils',
    'get_current_user',
    'get_current_user_optional',
    'rate_limiter',
    'RateLimiter',
    'sanitize_input',
    'validate_api_key',
    'PII',
]



