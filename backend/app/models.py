"""Import every ORM model so SQLAlchemy's mapper registry sees all of them.

This module has no other purpose. Import it once (in app.main) before the
app starts serving so that string-based relationship() references across
domain packages resolve correctly.
"""

from app.documents.models import Document, DocumentChunk  # noqa: F401
from app.knowledge.models import DocumentTopic, KnowledgeEvidence, Topic  # noqa: F401
from app.teams.models import Team  # noqa: F401
from app.users.models import User  # noqa: F401
