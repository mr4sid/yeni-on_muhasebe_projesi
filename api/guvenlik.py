# api/guvenlik.py dosyasının tam içeriği GÜNCEL İÇERİĞİ
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from . import modeller, semalar
from .config import settings
from typing import Optional
from .database_core import SessionLocal_master
import logging
logger = logging.getLogger(__name__)

def get_master_db():
    db = SessionLocal_master()
    try:
        yield db
    finally:
        db.close()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/yonetici-giris")

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

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_master_db)):
    """
    Token'ı doğrular ve ana veritabanından (master) ilgili Kullanıcıyı döndürür.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = semalar.TokenData(username=username)
    except JWTError:
        raise credentials_exception

    # KRİTİK DÜZELTME: 'Yonetici' yerine doğru model olan 'Kullanici' modelini sorguluyoruz.
    user = db.query(modeller.Kullanici).filter(modeller.Kullanici.email == token_data.username).first()
    
    if user is None:
        raise credentials_exception
        
    return user

def get_current_user_superadmin(current_user: modeller.KullaniciRead = Depends(get_current_user)):
    if current_user.rol != modeller.RolEnum.SUPERADMIN:
        logger.warning(f"SUPERADMIN yetkisi olmayan kullanıcı erişim denemesi: {current_user.email} (Rol: {current_user.rol})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sadece SUPERADMIN yetkilidir."
        )
    return current_user

def modul_yetki_kontrol(gerekli_modul: str):
    """
    Token'daki 'izinler' listesini kontrol eden yeni decorator. (Düzeltilmiş)
    """
    # DÜZELTME: 'get_current_user' (ORM objesi) yerine 'get_token_payload' (dict) kullanıyoruz.
    def kontrol(payload: dict = Depends(get_token_payload)): 
        kullanici_rol = payload.get("rol") # Artık .get() çalışmalı

        # ADMIN (veya SUPERADMIN) her zaman yetkilidir
        if kullanici_rol == "ADMIN" or kullanici_rol == "SUPERADMIN":
            return payload

        # Token'dan izin listesini al
        kullanici_izinleri = payload.get("izinler", [])

        # Gerekli modül kullanıcının izin listesinde yoksa
        if gerekli_modul not in kullanici_izinleri:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlemi yapmak için '{gerekli_modul}' modülüne erişim yetkiniz yok."
            )

        return payload # Payload'u (sözlük) döndür

    return kontrol