"""Unit tests for app/teams/access.py - the permission gate every team-scoped
endpoint goes through (require_team_access) and the roster helper
(team_user_ids) that this session's cross-team leak fixes and
person_attribution.py both depend on for "who counts as this team".
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.teams.access import require_team_access, team_user_ids
from app.users.models import UserRole


def _db_returning(team):
    db = MagicMock()
    db.get.return_value = team
    return db


def test_require_team_access_allows_owning_manager(make_user, make_team):
    manager = make_user("Manager One", role=UserRole.MANAGER)
    team = make_team("Team A", manager=manager)

    result = require_team_access(team.id, manager, _db_returning(team))

    assert result is team


def test_require_team_access_allows_member(make_user, make_team):
    manager = make_user("Manager One", role=UserRole.MANAGER)
    member = make_user("Member One")
    team = make_team("Team A", manager=manager, members=[member])

    result = require_team_access(team.id, member, _db_returning(team))

    assert result is team


def test_require_team_access_rejects_unrelated_user(make_user, make_team):
    manager = make_user("Manager One", role=UserRole.MANAGER)
    team = make_team("Team A", manager=manager)
    stranger = make_user("Stranger")

    with pytest.raises(HTTPException) as exc_info:
        require_team_access(team.id, stranger, _db_returning(team))
    assert exc_info.value.status_code == 403


def test_require_team_access_rejects_member_of_a_different_team(make_user, make_team):
    manager_a = make_user("Manager A", role=UserRole.MANAGER)
    manager_b = make_user("Manager B", role=UserRole.MANAGER)
    team_a = make_team("Team A", manager=manager_a)
    member_b = make_user("Member B", team_id=999)
    make_team("Team B", manager=manager_b, members=[member_b])

    with pytest.raises(HTTPException) as exc_info:
        require_team_access(team_a.id, member_b, _db_returning(team_a))
    assert exc_info.value.status_code == 403


def test_require_team_access_404s_on_missing_team(make_user):
    stranger = make_user("Stranger")
    db = MagicMock()
    db.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        require_team_access(999, stranger, db)
    assert exc_info.value.status_code == 404


def test_team_user_ids_includes_members_and_owning_manager(make_user, make_team):
    manager = make_user("Manager One", role=UserRole.MANAGER)
    member_a = make_user("Member A")
    member_b = make_user("Member B")
    team = make_team("Team A", manager=manager, members=[member_a, member_b])

    ids = team_user_ids(team)

    assert set(ids) == {manager.id, member_a.id, member_b.id}


def test_team_user_ids_on_team_with_no_members_still_includes_manager(make_user, make_team):
    manager = make_user("Solo Manager", role=UserRole.MANAGER)
    team = make_team("Empty Team", manager=manager)

    assert team_user_ids(team) == [manager.id]
