from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User
from app.schemas.user import (
    RefreshRequest,
    RegisterResponse,
    TokenResponse,
    UserList,
    UserLogin,
    UserOut,
    UserRegister,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(u: User) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "full_name": u.full_name,
        "phone": u.phone,
        "is_active": u.is_active,
        "is_admin": u.is_admin,
    }


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister):
    existing = await User.find_one(User.email == body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This email is already registered")
    user = User(
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        age=body.age,
        gender=body.gender,
        medical_history=body.medical_history,
    )
    await user.insert()
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "message": "Details saved successfully",
    }


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin):
    user = await User.find_one(User.email == body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")
    uid = str(user.id)
    return {
        "access_token": create_access_token(uid),
        "refresh_token": create_refresh_token(uid),
        "token_type": "bearer",
        "user": _user_out(user),
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest):
    user_id = decode_token(body.refresh_token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = await User.get(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    uid = str(user.id)
    return {
        "access_token": create_access_token(uid),
        "refresh_token": create_refresh_token(uid),
        "token_type": "bearer",
        "user": _user_out(user),
    }


@router.get("/me", response_model=UserOut)
async def me(current_user: Annotated[User, Depends(get_current_user)]):
    return _user_out(current_user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
):
    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await current_user.set(update_data)
    return _user_out(current_user)


@router.get("/users", response_model=List[UserList])
async def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 50,
):
    """Admin-only: list all registered users."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    users = await User.find_all().skip(skip).limit(limit).to_list()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "phone": u.phone,
            "age": u.age,
            "gender": u.gender,
            "medical_history": u.medical_history,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]