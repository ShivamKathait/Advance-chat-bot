

from app.core.exceptions import UserAlreadyExistsError
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import SignupRequest, SignupResponse
from app.core.logging import logger_adapter
from app.core.security import SecurityUtils
from app.services.email_service import send_verification_email

class AuthService:

    def __init__(self, auth_repository: AuthRepository):
        self.auth_repository = auth_repository

    async def user_signup(self,request: SignupRequest) -> SignupResponse:
        existing_user = self.auth_repository.get_user_by_email(request.email)
        if existing_user and existing_user.isVerified:
            logger_adapter.warning(
                "Signup failed: email already registered",
                email=request.email,
                operation="user_signup"
            )
            raise UserAlreadyExistsError("An account with this email already exists.")
        
        hash_password = SecurityUtils.hash_password(request.password)
        otp = SecurityUtils.generate_numeric_otp()
        signup_token = SecurityUtils.create_signup_token(request.email)
        
        if existing_user.isVerified == False:
            send_verification_email(request.first_name,request.last_name,request.email)
            return save_user

       
        save_user = self.auth_repository.create_user(request.email,hash_password,request.first_name,request.last_name)
        send_verification_email(request.first_name,request.last_name,request.email)
        return save_user
