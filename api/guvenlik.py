# api/guvenlik.py
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session

# DÜZELTME: Doğru içe aktarma yolları kullanıldı
from . import modeller, semalar
from .veritabani import get_db
# DÜZELTME: 'config' dosyasının 'api' dizini içinde olduğunu varsayıyoruz
from .config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

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
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    JWT token'ı kullanarak geçerli kullanıcıyı doğrular ve döndürür.
    Dönen değerin Pydantic şeması olması sağlanmıştır.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik bilgileri doğrulanamadı",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        kullanici_adi: str = payload.get("sub") 
        if kullanici_adi is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(modeller.Kullanici).filter(modeller.Kullanici.kullanici_adi == kullanici_adi).first()
    
    if user is None:
        raise credentials_exception
    return modeller.KullaniciRead.model_validate(user, from_attributes=True)