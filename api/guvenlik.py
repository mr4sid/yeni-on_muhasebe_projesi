# api/guvenlik.py (Database-per-Tenant ve Email Girişine Uyarlandı)
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
# DÜZELTME: OAuth2PasswordRequestForm eklendi
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm 
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload 

# DÜZELTME: Doğru içe aktarma yolları kullanıldı
from . import modeller 
from .veritabani import get_master_db # <<< Sadece Master DB bağlantısı kullanılır
from .config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

# Şifre karma oluşturma (hashing) bağlamı
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT şeması (Giriş e-posta ile yapılacaktır)
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
    'data' içinde 'sub' (email) ve 'tenant_db' bulunmalıdır.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), master_db: Session = Depends(get_master_db)):
    """
    JWT token'ı kullanarak geçerli kullanıcıyı doğrular ve döndürür.
    Token payload'ı: {'sub': email, 'tenant_db': tenant_db_name}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik bilgileri doğrulanamadı",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub") # <<< E-posta beklenir
        tenant_db_name: str = payload.get("tenant_db") 
        if email is None or tenant_db_name is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Master DB'den kullanıcıyı ve firmayı tek sorguyla çek
    user = master_db.query(modeller.Kullanici).options(
        joinedload(modeller.Kullanici.firma)
    ).filter(
        modeller.Kullanici.email == email
    ).first()
    
    if user is None:
        raise credentials_exception
        
    # Kullanıcı objesini Pydantic'e çevir ve tenant bilgisini ekle
    user_read_data = modeller.KullaniciRead.model_validate(user, from_attributes=True)
    
    # KRİTİK: Tenant bilgisini ve Firma adını Pydantic modele elle ekle
    user_read_data.tenant_db_name = tenant_db_name
    if user.firma:
        user_read_data.firma_adi = user.firma.firma_adi
    
    return user_read_data