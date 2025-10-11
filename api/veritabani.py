# api/veritabani.py Dosyasının TAM İÇERİĞİ (Database-per-Tenant Hazırlığı)
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine.base import Engine
import logging
from typing import Dict, Optional

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()

# --- BAĞLANTI SABİTLERİ (MASTER BAĞLANTISI İÇİN) ---
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
MASTER_DB_NAME = os.getenv("DB_NAME") # MASTER veritabanı adı
ROOT_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
DATABASE_URL = f"{ROOT_DB_URL}{MASTER_DB_NAME}"

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, MASTER_DB_NAME]):
    logger.error("Veritabanı bağlantı bilgileri .env dosyasından eksik veya hatalı. Lütfen .env dosyasını kontrol edin.")
    raise ValueError("Veritabanı bağlantı bilgileri eksik.")

# SQLAlchemy motorları ve Session maker'lar için sözlükler
# Artık tek bir Engine değil, her Tenant için dinamik Engine'ler olacak.
tenant_engines: Dict[str, Engine] = {}
tenant_session_locals: Dict[str, sessionmaker] = {}

# MASTER DB için gerekli global instance'lar (MASTER, kullanıcı listesini tutar)
master_engine: Optional[Engine] = None
MasterSessionLocal: Optional[sessionmaker] = None

def get_master_engine() -> Engine:
    """MASTER veritabanı motorunu döndürür (Kullanıcı kayıtları için)."""
    global master_engine
    if master_engine is None:
        master_engine = create_engine(DATABASE_URL)
        logger.info(f"MASTER DB motoru başlatıldı: {MASTER_DB_NAME}")
    return master_engine

def get_master_db():
    """MASTER DB oturumu almak için bağımlılık fonksiyonu."""
    global MasterSessionLocal
    if MasterSessionLocal is None:
        MasterSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_master_engine())
    
    db = MasterSessionLocal()
    try:
        yield db
    except Exception as e:
        logger.critical(f"MASTER DB bağlantısı kurulamadı! Hata: {e}")
        # Hata durumunda MASTER bağlantısı yeniden kurulmalı
        # master_engine.dispose() # Tekrar bağlanma mekanizması burada daha karmaşık ele alınmalı
        raise
    finally:
        db.close()

def get_tenant_engine(tenant_db_name: str) -> Engine:
    """Tenant veritabanı motorunu döndürür, yoksa oluşturur."""
    if tenant_db_name not in tenant_engines:
        tenant_url = f"{ROOT_DB_URL}{tenant_db_name}"
        engine = create_engine(tenant_url)
        tenant_engines[tenant_db_name] = engine
        logger.info(f"Yeni Tenant DB motoru başlatıldı: {tenant_db_name}")
    return tenant_engines[tenant_db_name]

def get_db(tenant_db_name: str):
    """
    Tenant veritabanı oturumu almak için bağımlılık fonksiyonu.
    Artık sabit bir Engine kullanmaz, tenant_db_name ile dinamik bağlanır.
    """
    if tenant_db_name not in tenant_session_locals:
        engine = get_tenant_engine(tenant_db_name)
        TenantSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        tenant_session_locals[tenant_db_name] = TenantSessionLocal
    
    db = tenant_session_locals[tenant_db_name]()
    try:
        # Yeni mimaride get_db() fonksiyonunun nasıl çağrılacağı API rotalarında değişmelidir.
        yield db
    except Exception as e:
        logger.critical(f"Tenant DB ({tenant_db_name}) bağlantısı kurulamadı! Hata: {e}")
        # Hata durumunda Tenant bağlantısı sıfırlanmalı
        if tenant_db_name in tenant_engines:
            tenant_engines[tenant_db_name].dispose()
            del tenant_engines[tenant_db_name]
        raise
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