# api/veritabani.py Dosyasının TAM İÇERİĞİ 
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine.base import Engine
import logging
from typing import Dict, Optional
from fastapi import HTTPException, status, Depends
from . import guvenlik, modeller

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()

# --- BAĞLANTI SABİTLERİ ---
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
MASTER_DB_NAME = os.getenv("DB_NAME")
ROOT_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
DATABASE_URL = f"{ROOT_DB_URL}{MASTER_DB_NAME}"

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, MASTER_DB_NAME]):
    logger.error("Veritabanı bağlantı bilgileri .env dosyasından eksik veya hatalı.")
    raise ValueError("Veritabanı bağlantı bilgileri eksik.")

# --- MERKEZİ BAŞLATMA (INITIALIZATION) ---
# KRİTİK DÜZELTME: motor (engine) ve oturum yöneticisi (SessionLocal)
# burada, modül yüklendiğinde bir kez oluşturulur.
try:
    master_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    MasterSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=master_engine)
    logger.info(f"MASTER DB motoru başlatıldı: {MASTER_DB_NAME}")
except Exception as e:
    logger.error(f"MASTER DB motoru başlatılırken hata oluştu: {e}")
    master_engine = None
    MasterSessionLocal = None # Hata durumunda None olarak kalsın

tenant_engines: Dict[str, Engine] = {}

def get_master_engine() -> Engine:
    """MASTER veritabanı motorunu döndürür (Kullanıcı kayıtları için)."""
    global master_engine
    if master_engine is None:
        # --- GÜNCELLEME BURADA: pool_pre_ping=True eklendi ---
        master_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        logger.info(f"MASTER DB motoru başlatıldı: {MASTER_DB_NAME}")
    return master_engine

def get_master_db():
    """Master veritabanı için bir oturum (session) sağlar."""
    db = MasterSessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_tenant_engine(tenant_db_name: str) -> Engine:
    """Tenant veritabanı motorunu döndürür, yoksa oluşturur."""
    if tenant_db_name not in tenant_engines:
        tenant_url = f"{ROOT_DB_URL}{tenant_db_name}"
        # --- GÜNCELLEME BURADA: pool_pre_ping=True eklendi ---
        engine = create_engine(tenant_url, pool_pre_ping=True)
        tenant_engines[tenant_db_name] = engine
        logger.info(f"Yeni Tenant DB motoru başlatıldı: {tenant_db_name}")
    return tenant_engines[tenant_db_name]

def get_db(current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)):
    """Kullanıcı token'ından alınan bilgiye göre tenant veritabanı oturumu sağlar."""
    tenant_db_name = current_user.tenant_db_name
    if not tenant_db_name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcıya atanmış bir firma veritabanı bulunamadı."
        )

    engine = get_tenant_engine(tenant_db_name)
    TenantSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TenantSessionLocal()
    try:
        yield db
    finally:
        db.close()

def reset_db_connection():
    """Tüm Tenant ve Master bağlantılarını sıfırlar."""
    global master_engine, MasterSessionLocal, tenant_engines, tenant_session_locals
    
    if master_engine:
        master_engine.dispose()
        master_engine = None
        MasterSessionLocal = None
    
    for engine in tenant_engines.values():
        engine.dispose()
    
    tenant_engines.clear()
    tenant_session_locals.clear()
    logger.info("Tüm Master ve Tenant veritabanı bağlantıları sıfırlandı.")

# Deklaratif taban sınıfı
Base = declarative_base()