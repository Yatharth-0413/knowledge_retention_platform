"""Integration regression test for the two pre-existing cross-team KnowledgeEvidence
leaks found and fixed during this session (not reported by the user - found via our
own testing). KnowledgeEvidence has no team_id of its own; a manager who manages
more than one team must never see one team's documented knowledge leak into another
team's dashboard/topic views just because the same manager uploaded both.
"""

from app.auth.security import hash_password
from app.teams.models import Team
from app.users.models import User, UserRole


def _seed_manager_with_two_teams(db_session):
    manager = User(
        name="Multi Team Manager", email="multi.manager@example.com",
        password_hash=hash_password("x"), role=UserRole.MANAGER,
    )
    db_session.add(manager)
    db_session.flush()

    team_a = Team(name="Team Alpha", manager_id=manager.id)
    team_b = Team(name="Team Beta", manager_id=manager.id)
    db_session.add_all([team_a, team_b])
    db_session.commit()
    db_session.refresh(manager)
    db_session.refresh(team_a)
    db_session.refresh(team_b)
    return manager, team_a, team_b


def _upload_generic_document(client, auth_headers, manager, team):
    # No cell here matches any team member's name, so match_rows_to_members finds
    # nothing and the document falls through to the ordinary whole-document
    # uploader-credit path - crediting the manager directly for Team A only.
    csv_content = b"Topic,Detail\nRisk Engine Review,High Priority Quarterly Review\n"
    response = client.post(
        f"/teams/{team.id}/documents",
        files={"file": ("risk_review.csv", csv_content, "text/csv")},
        headers=auth_headers(manager),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_team_b_dashboard_does_not_leak_team_a_evidence(client, db_session, auth_headers):
    manager, team_a, team_b = _seed_manager_with_two_teams(db_session)
    _upload_generic_document(client, auth_headers, manager, team_a)

    dashboard_a = client.get(f"/teams/{team_a.id}/dashboard", headers=auth_headers(manager)).json()
    dashboard_b = client.get(f"/teams/{team_b.id}/dashboard", headers=auth_headers(manager)).json()

    # Positive control: Team A's own dashboard does show the manager's evidence.
    assert dashboard_a["topic_count"] >= 1
    assert any(m["user_id"] == manager.id for m in dashboard_a["knowledge_by_member"])

    # The regression guard: the exact same manager's Team B dashboard must be
    # untouched by what they uploaded to Team A.
    assert dashboard_b["topic_count"] == 0
    assert dashboard_b["knowledge_by_member"] == []
    assert dashboard_b["active_contributor_count"] == 0


def test_team_b_topic_explorer_does_not_leak_team_a_topics(client, db_session, auth_headers):
    manager, team_a, team_b = _seed_manager_with_two_teams(db_session)
    _upload_generic_document(client, auth_headers, manager, team_a)

    topics_a = client.get(f"/teams/{team_a.id}/topics", headers=auth_headers(manager)).json()
    topics_b = client.get(f"/teams/{team_b.id}/topics", headers=auth_headers(manager)).json()

    assert len(topics_a) >= 1
    assert topics_b == []


def test_team_b_contributions_view_does_not_leak_team_a_activity(client, db_session, auth_headers):
    manager, team_a, team_b = _seed_manager_with_two_teams(db_session)
    _upload_generic_document(client, auth_headers, manager, team_a)

    contributions_b = client.get(f"/teams/{team_b.id}/contributions", headers=auth_headers(manager)).json()

    assert len(contributions_b) == 1
    assert contributions_b[0]["user_id"] == manager.id
    # The manager has a document on Team A, none on Team B - Team B's own
    # contribution view must show 0 for both, not Team A's counts.
    assert contributions_b[0]["document_count"] == 0
    assert contributions_b[0]["topic_count"] == 0
