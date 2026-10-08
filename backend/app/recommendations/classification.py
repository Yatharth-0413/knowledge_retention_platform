from typing import Literal

Category = Literal["functional", "technical", "unclassified"]
TopicCategory = Literal["functional", "technical", "mixed", "unclassified"]

# Checked first, as whole phrases - a specific title always wins over a generic keyword.
FUNCTIONAL_PHRASES = [
    "business analyst",
    "consultant analyst",
    "scrum master",
    "agile master",
    "agile coach",
    "product owner",
    "business consultant",
    "functional consultant",
]
TECHNICAL_PHRASES = [
    "devops engineer",
    "software engineer",
    "qa engineer",
    "quality assurance engineer",
    "site reliability engineer",
    "database administrator",
    "solutions architect",
    "technical architect",
    "enterprise architect",
    "data engineer",
    "ml engineer",
    "test engineer",
]

# Fallback generic keywords, only checked if no phrase above matched.
FUNCTIONAL_KEYWORDS = ["manager", "analyst", "consultant", "coach"]
TECHNICAL_KEYWORDS = ["architect", "developer", "programmer", "devops", "engineer", "dba", "sre", "tech lead", "technical lead"]


def classify_designation(designation: str | None) -> Category:
    """Functional (business/process) vs technical knowledge, inferred from a free-text job title.

    Tier-1 phrases are checked first and short-circuit. Tier-2 is a generic single-keyword
    fallback for anything not covered by a specific phrase. A title matching both tiers' keywords
    (e.g. "Engineering Manager" contains both "manager" and "engineer") deterministically resolves
    to functional - an explicit role keyword like "manager" is a stronger signal than a bare
    "engineer" substring inside a compound word like "Engineering".
    """
    if not designation or not designation.strip():
        return "unclassified"
    text = designation.strip().lower()

    if any(phrase in text for phrase in FUNCTIONAL_PHRASES):
        return "functional"
    if any(phrase in text for phrase in TECHNICAL_PHRASES):
        return "technical"

    func_hit = any(keyword in text for keyword in FUNCTIONAL_KEYWORDS)
    tech_hit = any(keyword in text for keyword in TECHNICAL_KEYWORDS)
    if func_hit:
        return "functional"
    if tech_hit:
        return "technical"
    return "unclassified"


def classify_topic_category(contributor_categories: list[Category]) -> TopicCategory:
    """A topic's own category, by majority vote of its documented-evidence contributors.

    Unclassified contributors don't count toward either side. A real tie between functional and
    technical contributors is "mixed" rather than arbitrarily picking one.
    """
    functional_count = sum(1 for c in contributor_categories if c == "functional")
    technical_count = sum(1 for c in contributor_categories if c == "technical")

    if functional_count > technical_count:
        return "functional"
    if technical_count > functional_count:
        return "technical"
    if functional_count > 0:  # tied, both > 0
        return "mixed"
    return "unclassified"
