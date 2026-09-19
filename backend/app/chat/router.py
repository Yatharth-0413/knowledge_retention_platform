from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.chat.schemas import ChatRequest, ChatResponseOut
from app.chat.service import answer_question
from app.database import get_db
from app.teams.access import require_team_access
from app.users.models import User

router = APIRouter(tags=["chat"])


@router.post("/teams/{team_id}/chat", response_model=ChatResponseOut)
def chat(
    team_id: int,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponseOut:
    require_team_access(team_id, current_user, db)
    return answer_question(db, team_id, payload.question)
