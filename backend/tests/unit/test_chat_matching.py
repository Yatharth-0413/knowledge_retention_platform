"""Unit tests for app/chat/service.py::_match_question_to_people - the
entity-aware retrieval this session's P0 fix added so "What does Shivam know?"
is answered from ground-truth KnowledgeEvidence instead of embedding-similarity
luck. Matched generically against the real team roster - no hardcoded names.
"""

from app.chat.service import _match_question_to_people


def test_matches_full_name_mention(make_user):
    sriram = make_user("Sriram Kumar")
    shivam = make_user("Shivam Patel")
    roster = [sriram, shivam]

    matched = _match_question_to_people("What does Sriram Kumar know?", roster, current_user=sriram)

    assert matched == [sriram]


def test_matches_first_name_mention(make_user):
    sriram = make_user("Sriram Kumar")
    roster = [sriram]

    matched = _match_question_to_people("What does Sriram know about DevOps?", roster, current_user=sriram)

    assert matched == [sriram]


def test_first_name_match_is_whole_word_not_substring(make_user):
    # "Sri" must not false-positive match inside "Sriram" or vice versa - this
    # was an explicit risk called out in person_attribution.py's own docstring.
    sri = make_user("Sri Lal")
    sriram = make_user("Sriram Kumar")
    roster = [sri, sriram]

    matched = _match_question_to_people("What does Sriram know?", roster, current_user=sri)

    assert matched == [sriram]
    assert sri not in matched


def test_matches_multiple_people_named_in_one_question(make_user):
    sriram = make_user("Sriram Kumar")
    shivam = make_user("Shivam Patel")
    roster = [sriram, shivam]

    matched = _match_question_to_people(
        "Compare what Sriram and Shivam each know about DevOps", roster, current_user=sriram
    )

    assert set(matched) == {sriram, shivam}


def test_falls_back_to_asker_on_first_person_reference(make_user):
    sriram = make_user("Sriram Kumar")
    shivam = make_user("Shivam Patel")
    roster = [sriram, shivam]

    matched = _match_question_to_people("What do I know about DevOps?", roster, current_user=shivam)

    assert matched == [shivam]


def test_my_also_triggers_self_reference(make_user):
    shivam = make_user("Shivam Patel")
    matched = _match_question_to_people("Summarize my documented knowledge", [shivam], current_user=shivam)
    assert matched == [shivam]


def test_no_match_and_no_self_reference_returns_empty(make_user):
    sriram = make_user("Sriram Kumar")
    matched = _match_question_to_people("How do we deploy the Risk Engine?", [sriram], current_user=sriram)
    assert matched == []


def test_named_mention_takes_priority_over_self_reference(make_user):
    # "What does Sriram know, not what do I know" - a named mention should win
    # even if the question also happens to contain a first-person word.
    sriram = make_user("Sriram Kumar")
    shivam = make_user("Shivam Patel")

    matched = _match_question_to_people(
        "I want to know what Sriram knows", [sriram, shivam], current_user=shivam
    )

    assert matched == [sriram]
