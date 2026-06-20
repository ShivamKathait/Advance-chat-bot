from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

class SignupRequest(BaseModel):
    first_name: str = Field(..., description="first name")
    last_name: str = Field(..., description="last name")
    email: str = Field(..., description="email")
    password: str = Field(..., min_length=8, max_length=16,description="password")

    @field_validator("email", mode="before")
    @classmethod
    def _strip_email(cls, v: str) -> str:
        return v.strip()
    

class SignupResponse(BaseModel):
    first_name: str 
    last_name: str 
    email: str 