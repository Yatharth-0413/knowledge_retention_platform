from app.users.models import User, UserRole


def can_view_user_profile(viewer: User, target: User) -> bool:
    """Self, a teammate, or a manager who owns the target's team."""
    if viewer.id == target.id:
        return True
    if viewer.team_id is not None and viewer.team_id == target.team_id:
        return True
    if viewer.role == UserRole.MANAGER and target.team_id is not None:
        return any(team.id == target.team_id for team in viewer.managed_teams)
    return False
