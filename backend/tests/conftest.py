"""Shared fixtures for unit tests.

These build real ORM model instances (app.users.models.User, app.teams.models.Team)
but never touch a database - relationship attributes (e.g. Team.members,
User.managed_teams) are set directly in memory, which SQLAlchemy supports fine on
transient (never-added-to-a-session) objects. This lets unit tests exercise the real
model classes - catching attribute-name drift - without any DB/Docker dependency.
"""

import pytest

from app.teams.models import Team
from app.users.models import User, UserRole


@pytest.fixture
def make_user():
    counter = {"n": 0}

    def _make(name: str, *, role: UserRole = UserRole.MEMBER, team_id: int | None = None, email: str | None = None) -> User:
        counter["n"] += 1
        return User(
            id=counter["n"],
            name=name,
            email=email or f"{name.lower().replace(' ', '.')}@example.com",
            password_hash="x",
            role=role,
            team_id=team_id,
        )

    return _make


@pytest.fixture
def make_team():
    counter = {"n": 0}

    def _make(name: str, *, manager: User, members: list[User] | None = None) -> Team:
        counter["n"] += 1
        team = Team(id=counter["n"], name=name, manager_id=manager.id)
        team.manager = manager
        team.members = members or []
        for member in team.members:
            member.team_id = team.id
        manager.managed_teams = [*(getattr(manager, "managed_teams", []) or []), team]
        return team

    return _make
