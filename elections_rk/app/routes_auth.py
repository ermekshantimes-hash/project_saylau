# API роуты для аутентификации (Task #1: RBAC)
# Login, logout, refresh token, MFA, регистрация наблюдателей

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.auth_utils import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    generate_mfa_secret, generate_totp_uri, verify_totp
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ==================== SCHEMAS ====================

class LoginRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str
    mfa_code: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    mfa_required: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterObserverRequest(BaseModel):
    phone: str
    email: EmailStr
    password: str
    legal_type: str  # ORG | DELEGATE | INDEPENDENT
    org_id: Optional[int] = None


class EnableMFAResponse(BaseModel):
    mfa_secret: str
    qr_uri: str


class VerifyMFARequest(BaseModel):
    mfa_code: str


# ==================== HELPERS ====================

def get_current_user(authorization: str = Header(...), db: Session = Depends(get_db)):
    """
    Dependency для получения текущего пользователя из JWT
    """
    from app.models_extended import User
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        payload = decode_token(token)
        user_id = payload.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user or user.status != "ACTIVE":
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
        return user
    
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


def require_role(allowed_roles: list):
    """
    Декоратор для проверки роли пользователя
    """
    def role_checker(user = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {allowed_roles}"
            )
        return user
    return role_checker


# ==================== ENDPOINTS ====================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Вход в систему (телефон или email + пароль)
    """
    from app.models_extended import User
    
    # Найти пользователя
    query = db.query(User)
    
    if request.phone:
        user = query.filter(User.phone == request.phone).first()
    elif request.email:
        user = query.filter(User.email == request.email).first()
    else:
        raise HTTPException(status_code=400, detail="Phone or email required")
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Проверить пароль
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Проверить статус
    if user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Account is not active")
    
    # Проверить MFA если включен
    if user.mfa_enabled:
        if not request.mfa_code:
            return LoginResponse(
                access_token="",
                refresh_token="",
                user_id=user.id,
                role=user.role,
                mfa_required=True
            )
        
        if not verify_totp(user.mfa_secret, request.mfa_code):
            raise HTTPException(status_code=401, detail="Invalid MFA code")
    
    # Создать токены
    token_data = {"user_id": user.id, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # Обновить last_login_at
    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        role=user.role
    )


@router.post("/refresh")
async def refresh_token(request: RefreshRequest):
    """
    Обновление access token через refresh token
    """
    try:
        payload = decode_token(request.refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        token_data = {"user_id": payload["user_id"], "role": payload["role"]}
        new_access_token = create_access_token(token_data)
        
        return {"access_token": new_access_token, "token_type": "bearer"}
    
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/register/observer")
async def register_observer(request: RegisterObserverRequest, db: Session = Depends(get_db)):
    """
    Регистрация наблюдателя (PUBLIC → OBSERVER)
    """
    from app.models_extended import User, ObserverProfile
    
    # Проверить уникальность
    if db.query(User).filter(User.phone == request.phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")
    
    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Создать пользователя
    user = User(
        phone=request.phone,
        email=request.email,
        password_hash=hash_password(request.password),
        role="OBSERVER",
        status="ACTIVE"
    )
    db.add(user)
    db.flush()
    
    # Создать профиль наблюдателя
    profile = ObserverProfile(
        user_id=user.id,
        legal_type=request.legal_type,
        org_id=request.org_id,
        status="DRAFT"
    )
    db.add(profile)
    db.commit()
    
    return {"message": "Observer registered successfully", "user_id": user.id}


@router.get("/me")
async def get_current_user_info(user = Depends(get_current_user)):
    """
    Получить информацию о текущем пользователе
    """
    return {
        "user_id": user.id,
        "phone": user.phone,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "mfa_enabled": user.mfa_enabled
    }


@router.post("/mfa/enable", response_model=EnableMFAResponse)
async def enable_mfa(user = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Включить MFA для пользователя (генерирует QR-код)
    """
    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA already enabled")
    
    mfa_secret = generate_mfa_secret()
    qr_uri = generate_totp_uri(mfa_secret, user.email or user.phone)
    
    # Сохранить секрет (но не активировать до верификации)
    user.mfa_secret = mfa_secret
    db.commit()
    
    return EnableMFAResponse(mfa_secret=mfa_secret, qr_uri=qr_uri)


@router.post("/mfa/verify")
async def verify_mfa_setup(
    request: VerifyMFARequest,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Верифицировать и активировать MFA
    """
    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA not initialized")
    
    if not verify_totp(user.mfa_secret, request.mfa_code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    
    user.mfa_enabled = True
    db.commit()
    
    return {"message": "MFA enabled successfully"}


@router.post("/mfa/disable")
async def disable_mfa(
    request: VerifyMFARequest,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Отключить MFA (требует верификацию текущим кодом)
    """
    if not user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA not enabled")
    
    if not verify_totp(user.mfa_secret, request.mfa_code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    
    user.mfa_enabled = False
    user.mfa_secret = None
    db.commit()
    
    return {"message": "MFA disabled successfully"}


# ==================== ADMIN ENDPOINTS ====================

@router.post("/admin/create-user")
async def admin_create_user(
    phone: str,
    email: str,
    password: str,
    role: str,
    admin_user = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db)
):
    """
    Создать пользователя (только для админов)
    """
    from app.models_extended import User
    
    if db.query(User).filter(User.phone == phone).first():
        raise HTTPException(status_code=400, detail="Phone already exists")
    
    user = User(
        phone=phone,
        email=email,
        password_hash=hash_password(password),
        role=role,
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    
    return {"message": "User created", "user_id": user.id}
