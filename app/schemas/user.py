from typing import Optional
from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    phone: str
    age: int
    gender: str
    medical_history: str


class RegisterResponse(BaseModel):
    id: str
    email: str
    full_name: str
    message: str = "Details saved successfully"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str
    is_active: bool
    is_admin: bool

    model_config = {"from_attributes": True}


class UserList(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str
    age: Optional[int] = None
    gender: Optional[str] = None
    medical_history: str = ""
    is_active: bool
    is_admin: bool
    created_at: str

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str
