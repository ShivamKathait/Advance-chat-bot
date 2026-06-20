
from fastapi import APIRouter,Depends

from app.dependencies.services import get_auth_service
from app.schemas.auth import SignupRequest
from app.services.auth_service import AuthService


router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

router.post("/signup")
async def signup(request: SignupRequest, service: AuthService = Depends(get_auth_service)):
    return await service.user_signup(request)
