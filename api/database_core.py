# Lütfen api/database_core.py dosyasının tam içeriği

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
# KRİTİK DEĞİŞİKLİK: Ayarlar artık merkezi 'settings' nesnesinden geliyor
from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- MASTER VERİTABANI MOTORU ---
DATABASE_URL_MASTER = f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
engine_master = create_engine(DATABASE_URL_MASTER)
SessionLocal_master = sessionmaker(autocommit=False, autoflush=False, bind=engine_master)

# --- TENANT VERİTABANI MOTOR YÖNETİMİ ---
tenant_engines = {}

Base = declarative_base()

def get_tenant_engine(tenant_db_name: str):
    if tenant_db_name not in tenant_engines:
        tenant_db_url = settings.DATABASE_URL.replace(settings.DB_NAME, tenant_db_name)
        tenant_engines[tenant_db_name] = create_engine(tenant_db_url, pool_pre_ping=True)
        logger.info(f"Yeni Tenant DB motoru başlatıldı: {tenant_db_name}")
    return tenant_engines[tenant_db_name]

def create_tenant_engine_and_session(db_name: str):
    """
    Belirtilen veritabanı (tenant) adı için bir SQLAlchemy engine ve sessionmaker oluşturur.
    Bu, her bir firmaya özel dinamik veritabanı bağlantıları kurmamızı sağlar.
    """
    # Veritabanı bağlantı bilgilerini config dosyasından alarak tam bağlantı URL'sini oluşturur.
    DATABASE_URL_TENANT = f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{db_name}"    
    # Yeni veritabanı için motor (engine) oluşturulur.
    engine_tenant = create_engine(DATABASE_URL_TENANT)
    
    # Bu motora bağlı yeni bir oturum (session) sınıfı oluşturulur ve döndürülür.
    SessionLocal_tenant = sessionmaker(autocommit=False, autoflush=False, bind=engine_tenant)
    
    return SessionLocal_tenant