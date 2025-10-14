# Lütfen api/database_core.py dosyasının TÜM içeriğini bununla değiştirin.

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# KRİTİK DEĞİŞİKLİK: Ayarlar artık merkezi 'settings' nesnesinden geliyor
from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- MASTER VERİTABANI MOTORU ---
master_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
MasterSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=master_engine)

# --- TENANT VERİTABANI MOTOR YÖNETİMİ ---
tenant_engines = {}

def get_tenant_engine(tenant_db_name: str):
    if tenant_db_name not in tenant_engines:
        tenant_db_url = settings.DATABASE_URL.replace(settings.DB_NAME, tenant_db_name)
        tenant_engines[tenant_db_name] = create_engine(tenant_db_url, pool_pre_ping=True)
        logger.info(f"Yeni Tenant DB motoru başlatıldı: {tenant_db_name}")
    return tenant_engines[tenant_db_name]