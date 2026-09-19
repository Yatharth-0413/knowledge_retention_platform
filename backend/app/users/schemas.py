from pydantic import BaseModel, EmailStr

from app.users.models import UserRole


class UserProfileOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    designation: str | None = None
    phone_number: str | None = None
    team_id: int | None = None

    model_config = {"from_attributes": True}
