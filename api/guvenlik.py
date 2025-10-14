# api/guvenlik.py dosyasının tam içeriği
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload
from . import modeller
from .database_core import MasterSessionLocal
from .config import settings

def get_master_db():
    db = MasterSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Şifre karma oluşturma (hashing) bağlamı
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT şeması
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="dogrulama/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Düz metin parolayı hashlenmiş parolayla karşılaştırır.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Verilen parolayı hashler ve string olarak döndürür.
    """
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Verilen verilerle bir JWT erişim jetonu oluşturur.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Ayarı merkezi 'settings' nesnesinden al
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    # Ayarları merkezi 'settings' nesnesinden al
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def get_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    """JWT token'ı doğrular ve payload'ı (içeriği) döndürür."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik bilgileri doğrulanamadı",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        tenant_db_name: str = payload.get("tenant_db")
        if email is None or tenant_db_name is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_master_db)
):
    """
    Token'ı doğrular ve master veritabanından kullanıcıyı getirir.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Ayarı merkezi 'settings' nesnesinden al
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception

        user = db.query(modeller.Kullanici).filter(modeller.Kullanici.email == email).first()
        if user is None:
            raise credentials_exception

        firma = user.firma
        user_read = modeller.KullaniciRead.from_orm(user)
        # İlişkili alanları manuel olarak ata
        user_read.firma_adi = firma.firma_adi if firma else None
        user_read.tenant_db_name = firma.tenant_db_name if firma else None

        return user_read
    except JWTError:
        raise credentials_exception