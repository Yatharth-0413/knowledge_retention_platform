from pydantic import BaseModel, EmailStr

from app.users.models import UserRole


class RegisterManagerRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    designation: str | None = None
    phone_number: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    designation: str | None = None
    phone_number: str | None = None
    team_id: int | None = None

    model_config = {"from_attributes": True}
