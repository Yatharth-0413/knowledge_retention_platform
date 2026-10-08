"""Unit tests for app/knowledge/person_attribution.py - the generic (no hardcoded
names) roster-matching logic behind this session's P0 fix: crediting a structured
document's rows to the team member they're actually about, not the uploader."""

from app.knowledge.person_attribution import _match_cell_to_user, match_rows_to_members


def test_match_cell_to_user_exact_full_name(make_user):
    roster = [make_user("Sriram Kumar"), make_user("Shivam Patel")]
    assert _match_cell_to_user("Sriram Kumar", roster) is roster[0]


def test_match_cell_to_user_is_case_insensitive(make_user):
    roster = [make_user("Sriram Kumar")]
    assert _match_cell_to_user("  sriram kumar  ", roster) is roster[0]


def test_match_cell_to_user_exact_email(make_user):
    roster = [make_user("Sriram Kumar", email="sriram@example.com")]
    assert _match_cell_to_user("sriram@example.com", roster) is roster[0]


def test_match_cell_to_user_first_name_fallback(make_user):
    roster = [make_user("Sriram Kumar"), make_user("Shivam Patel")]
    assert _match_cell_to_user("sriram", roster) is roster[0]


def test_match_cell_to_user_first_name_does_not_substring_match(make_user):
    # "Sri" must not match "Sriram" - _match_cell_to_user compares whole tokens,
    # not substrings (see the chat entity-matching test for the same requirement).
    roster = [make_user("Sriram Kumar")]
    assert _match_cell_to_user("sri", roster) is None


def test_match_cell_to_user_no_match_returns_none(make_user):
    roster = [make_user("Sriram Kumar")]
    assert _match_cell_to_user("Someone Else", roster) is None


def test_match_cell_to_user_blank_cell_returns_none(make_user):
    roster = [make_user("Sriram Kumar")]
    assert _match_cell_to_user("   ", roster) is None


def test_match_rows_to_members_credits_matched_row_to_the_right_person(make_user):
    sriram = make_user("Sriram Kumar")
    shivam = make_user("Shivam Patel")
    roster = [sriram, shivam]
    rows = [
        ["Sriram Kumar", "working on agile", "low"],
        ["Shivam Patel", "leading devops", "medium"],
    ]

    matches = match_rows_to_members(rows, roster)

    assert len(matches) == 2
    assert matches[0] == (sriram, "working on agile low")
    assert matches[1] == (shivam, "leading devops medium")


def test_match_rows_to_members_excludes_the_matched_name_cell_itself(make_user):
    # The matched name/email cell must not leak into the remaining text that gets
    # fed to topic extraction (it isn't a topic, it's the subject's own name).
    sriram = make_user("Sriram Kumar")
    rows = [["Sriram Kumar", "working on agile"]]

    matches = match_rows_to_members(rows, [sriram])

    assert "Sriram Kumar" not in matches[0][1]


def test_match_rows_to_members_skips_rows_with_no_matching_member(make_user):
    sriram = make_user("Sriram Kumar")
    rows = [["header", "notes"], ["Someone Unlisted", "did some work"]]

    assert match_rows_to_members(rows, [sriram]) == []


def test_match_rows_to_members_skips_matched_row_with_no_remaining_text(make_user):
    # A row that's just the person's name and nothing else carries no evidence -
    # must not create an empty-text DocumentTopic.
    sriram = make_user("Sriram Kumar")
    rows = [["Sriram Kumar"]]

    assert match_rows_to_members(rows, [sriram]) == []


def test_match_rows_to_members_only_matches_first_cell_in_a_row(make_user):
    # Only one person per row is ever matched - a second roster name appearing
    # later in the same row is treated as content, not a second subject.
    sriram = make_user("Sriram Kumar")
    shivam = make_user("Shivam Patel")
    rows = [["Sriram Kumar", "mentioned Shivam Patel in review"]]

    matches = match_rows_to_members(rows, [sriram, shivam])

    assert len(matches) == 1
    assert matches[0][0] is sriram
    assert "Shivam Patel" in matches[0][1]


def test_match_rows_to_members_works_for_an_arbitrary_team_no_hardcoded_names(make_user):
    # Explicit requirement from this session's bug report: the matching logic must
    # be generic, not tuned to any specific team's member names.
    alice = make_user("Alice Nakamura")
    bob = make_user("Bob Okonkwo")
    rows = [["Alice Nakamura", "owns the billing pipeline"], ["Bob Okonkwo", "owns onboarding"]]

    matches = match_rows_to_members(rows, [alice, bob])

    assert {user.name for user, _ in matches} == {"Alice Nakamura", "Bob Okonkwo"}
