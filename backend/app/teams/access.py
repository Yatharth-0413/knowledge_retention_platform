from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.teams.models import Team
from app.users.models import User, UserRole


def require_team_access(team_id: int, user: User, db: Session) -> Team:
    """Manager who owns the team, or a member of it. Raises 404/403 otherwise."""
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    is_manager_owner = user.role == UserRole.MANAGER and team.manager_id == user.id
    is_member = user.team_id == team.id
    if not (is_manager_owner or is_member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this team")
    return team


def team_user_ids(team: Team) -> list[int]:
    """Everyone whose contributions count toward this team: members plus the owning manager.

    The manager's own uploads (e.g. via POST /teams/{id}/documents) would
    otherwise be invisible in team-scoped knowledge views, since a manager's
    User.team_id is None — they own the team rather than belonging to it.
    """
    return [member.id for member in team.members] + [team.manager_id]
