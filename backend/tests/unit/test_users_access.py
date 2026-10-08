"""Unit tests for app/users/access.py::can_view_user_profile - the visibility rule
reused by /users/{id}/knowledge and /users/{id}/documents (see PROGRESS.md's note
on the manager-team_id-is-NULL bug this gate had to account for)."""

from app.users.access import can_view_user_profile
from app.users.models import UserRole


def test_self_can_always_view_own_profile(make_user):
    user = make_user("Solo User")
    assert can_view_user_profile(user, user) is True


def test_teammate_can_view_teammate(make_user, make_team):
    manager = make_user("Manager", role=UserRole.MANAGER)
    member_a = make_user("Member A")
    member_b = make_user("Member B")
    make_team("Team A", manager=manager, members=[member_a, member_b])

    assert can_view_user_profile(member_a, member_b) is True


def test_member_cannot_view_a_member_on_a_different_team(make_user, make_team):
    manager_a = make_user("Manager A", role=UserRole.MANAGER)
    manager_b = make_user("Manager B", role=UserRole.MANAGER)
    member_a = make_user("Member A")
    member_b = make_user("Member B")
    make_team("Team A", manager=manager_a, members=[member_a])
    make_team("Team B", manager=manager_b, members=[member_b])

    assert can_view_user_profile(member_a, member_b) is False


def test_manager_can_view_their_own_team_member(make_user, make_team):
    manager = make_user("Manager", role=UserRole.MANAGER)
    member = make_user("Member")
    make_team("Team A", manager=manager, members=[member])

    assert can_view_user_profile(manager, member) is True


def test_manager_cannot_view_a_member_of_a_team_they_do_not_manage(make_user, make_team):
    manager_a = make_user("Manager A", role=UserRole.MANAGER)
    manager_b = make_user("Manager B", role=UserRole.MANAGER)
    member_b = make_user("Member B")
    make_team("Team A", manager=manager_a)
    make_team("Team B", manager=manager_b, members=[member_b])

    assert can_view_user_profile(manager_a, member_b) is False


def test_manager_viewing_another_manager_with_no_team_id_is_false(make_user, make_team):
    # Regression guard for the bug this session found: a manager's own User.team_id
    # is None (they relate to a team via Team.manager_id, not team_id). Two managers
    # who don't share a team and aren't the same person must not see each other.
    manager_a = make_user("Manager A", role=UserRole.MANAGER)
    manager_b = make_user("Manager B", role=UserRole.MANAGER)
    make_team("Team A", manager=manager_a)
    make_team("Team B", manager=manager_b)

    assert can_view_user_profile(manager_a, manager_b) is False


def test_manager_managing_multiple_teams_can_view_either_teams_members(make_user, make_team):
    manager = make_user("Multi-team Manager", role=UserRole.MANAGER)
    member_a = make_user("Member A")
    member_b = make_user("Member B")
    make_team("Team A", manager=manager, members=[member_a])
    make_team("Team B", manager=manager, members=[member_b])

    assert can_view_user_profile(manager, member_a) is True
    assert can_view_user_profile(manager, member_b) is True
