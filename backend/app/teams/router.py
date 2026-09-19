from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_manager
from app.auth.security import hash_password
from app.database import get_db
from app.teams.models import Team
from app.teams.schemas import TeamCreate, TeamDetailOut, TeamMemberCreate, TeamMemberOut, TeamOut
from app.users.models import User, UserRole

router = APIRouter(prefix="/teams", tags=["teams"])


def _get_owned_team(team_id: int, manager: User, db: Session) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    if team.manager_id != manager.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the manager of this team")
    return team


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate, manager: User = Depends(require_manager), db: Session = Depends(get_db)
) -> Team:
    team = Team(name=payload.name, manager_id=manager.id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("", response_model=list[TeamOut])
def list_teams(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Team]:
    if current_user.role == UserRole.MANAGER:
        return db.query(Team).filter(Team.manager_id == current_user.id).order_by(Team.created_at.desc()).all()
    if current_user.team_id is None:
        return []
    team = db.get(Team, current_user.team_id)
    return [team] if team else []


@router.get("/{team_id}", response_model=TeamDetailOut)
def get_team(team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    is_manager_owner = current_user.role == UserRole.MANAGER and team.manager_id == current_user.id
    is_member = current_user.team_id == team.id
    if not (is_manager_owner or is_member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this team")
    return team


@router.post("/{team_id}/members", response_model=TeamMemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    team_id: int,
    payload: TeamMemberCreate,
    manager: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> User:
    team = _get_owned_team(team_id, manager, db)

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    member = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        designation=payload.designation,
        phone_number=payload.phone_number,
        role=UserRole.MEMBER,
        team_id=team.id,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/{team_id}/members", response_model=list[TeamMemberOut])
def list_members(
    team_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[User]:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    is_manager_owner = current_user.role == UserRole.MANAGER and team.manager_id == current_user.id
    is_member = current_user.team_id == team.id
    if not (is_manager_owner or is_member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this team")
    return db.query(User).filter(User.team_id == team.id).order_by(User.name).all()
