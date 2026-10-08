"""Integration test for this session's P0 fix: uploading a roster-style CSV
credits each row's knowledge to the named team member, not the uploader, and the
chat assistant answers a "What does <name> know?" question from that ground-truth
evidence. Exercises the real FastAPI routes, ORM, and Postgres/pgvector - this is
the exact bug class from My_analysis_on_project.md ("What does Shivam know?"
failing while "What does Sriram know?" worked from the same uploaded file).
"""

from app.teams.models import Team
from app.users.models import User, UserRole
from app.auth.security import hash_password


def _seed_team(db_session):
    manager = User(name="Priya Manager", email="priya.manager@example.com", password_hash=hash_password("x"), role=UserRole.MANAGER)
    db_session.add(manager)
    db_session.flush()

    team = Team(name="Phase1 Verify Team", manager_id=manager.id)
    db_session.add(team)
    db_session.flush()

    alice = User(
        name="Alice Johnson", email="alice@example.com", password_hash=hash_password("x"),
        role=UserRole.MEMBER, team_id=team.id,
    )
    bob = User(
        name="Bob Smith", email="bob@example.com", password_hash=hash_password("x"),
        role=UserRole.MEMBER, team_id=team.id,
    )
    db_session.add_all([alice, bob])
    db_session.commit()
    db_session.refresh(manager)
    db_session.refresh(team)
    db_session.refresh(alice)
    db_session.refresh(bob)
    return manager, team, alice, bob


def _upload_roster_csv(client, auth_headers, manager, team):
    csv_content = (
        "Member,Notes\n"
        "Alice Johnson,Leads Agile Practices\n"
        "Bob Smith,Owns Agile Practices\n"
    ).encode()
    response = client.post(
        f"/teams/{team.id}/documents",
        files={"file": ("team_info.csv", csv_content, "text/csv")},
        headers=auth_headers(manager),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_roster_row_knowledge_is_credited_to_the_named_person_not_the_uploader(client, db_session, auth_headers):
    manager, team, alice, bob = _seed_team(db_session)
    document = _upload_roster_csv(client, auth_headers, manager, team)
    assert document["status"] == "ready"

    alice_knowledge = client.get(f"/users/{alice.id}/knowledge", headers=auth_headers(manager)).json()
    bob_knowledge = client.get(f"/users/{bob.id}/knowledge", headers=auth_headers(manager)).json()
    manager_knowledge = client.get(f"/users/{manager.id}/knowledge", headers=auth_headers(manager)).json()

    assert len(alice_knowledge) >= 1
    assert alice_knowledge[0]["document_count"] >= 1
    assert len(bob_knowledge) >= 1

    # The core P0 regression guard: the manager uploaded the file but did none of
    # the documented work - they must get no evidence credit for these rows.
    assert manager_knowledge == []


def test_chat_about_a_specific_named_member_is_grounded_in_their_own_evidence(client, db_session, auth_headers):
    manager, team, alice, bob = _seed_team(db_session)
    _upload_roster_csv(client, auth_headers, manager, team)

    response = client.post(
        f"/teams/{team.id}/chat",
        json={"question": "What does Bob Smith know?"},
        headers=auth_headers(manager),
    )
    assert response.status_code == 200
    body = response.json()

    contributor_ids = {c["user_id"] for c in body["contributors"]}
    assert bob.id in contributor_ids
    # This is the exact failure mode from the bug report - asking about the
    # *other* named person must not silently return nothing / the wrong person.
    assert body["answer"] != "I couldn't find enough documented information to answer this confidently."


def test_chat_about_the_other_named_member_also_works(client, db_session, auth_headers):
    # Regression guard for "Sriram works, Shivam doesn't" - both must work
    # symmetrically from the same uploaded document.
    manager, team, alice, bob = _seed_team(db_session)
    _upload_roster_csv(client, auth_headers, manager, team)

    response = client.post(
        f"/teams/{team.id}/chat",
        json={"question": "What does Alice Johnson know?"},
        headers=auth_headers(manager),
    )
    assert response.status_code == 200
    body = response.json()
    contributor_ids = {c["user_id"] for c in body["contributors"]}
    assert alice.id in contributor_ids
