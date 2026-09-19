from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.users.models import UserRole


class TeamCreate(BaseModel):
    name: str


class TeamOut(BaseModel):
    id: int
    name: str
    manager_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamMemberCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    designation: str | None = None
    phone_number: str | None = None


class TeamMemberOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    designation: str | None = None
    phone_number: str | None = None
    team_id: int | None = None

    model_config = {"from_attributes": True}


class TeamDetailOut(TeamOut):
    members: list[TeamMemberOut] = []
