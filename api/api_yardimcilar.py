import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from . import modeller 
from . import veritabani
from . import config  # <-- YENİ SATIR: config modülünü içe aktarıyoruz

# JWT token oluşturma ve doğrulama için gerekli anahtar ve algoritmalar
SECRET_KEY = config.SECRET_KEY # <-- DÜZELTİLDİ: config.SECRET_KEY olarak kullanıyoruz
ALGORITHM = config.ALGORITHM # <-- DÜZELTİLDİ: config.ALGORITHM olarak kullanıyoruz
ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES # <-- DÜZELTİLDİ

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_initial_data(db: Session):
    # Eğer veri tabanında hiç kullanıcı yoksa, varsayılan bir kullanıcı oluştur
    existing_user = db.query(modeller.User).first()
    if not existing_user:
        hashed_password = "hashed_password_placeholder"  # Şifreyi güvenli bir şekilde hash'lemeyi unutmayın
        db_user = modeller.User(
            ad="Admin",
            soyad="Kullanıcı",
            email="admin@onmuhasebe.com",
            sifre_hash=hashed_password,
            rol="yonetici"
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return {"message": "Initial user created."}
    return None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = veritabani.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = modeller.TokenData(email=email)
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = db.query(modeller.User).filter(modeller.User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user