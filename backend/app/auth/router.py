from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser, LoginRequest, RegisterManagerRequest, TokenResponse
from app.auth.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.users.models import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_manager(payload: RegisterManagerRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Self-registration is for managers only. Team members are added by a
    manager via POST /teams/{id}/members and log in with the credentials
    the manager sets for them."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        designation=payload.designation,
        phone_number=payload.phone_number,
        role=UserRole.MANAGER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id), extra_claims={"role": user.role.value})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(subject=str(user.id), extra_claims={"role": user.role.value})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=CurrentUser)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
