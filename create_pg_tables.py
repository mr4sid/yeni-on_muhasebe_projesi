import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database
import logging

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- GÜNCELLEME: Doğru modeller 'api.modeller'den import ediliyor ---
# 'api.semalar' Pydantic şemalarını içerir, 'api.modeller' ise SQLAlchemy tablolarını (Base) içerir.
from api.modeller import Base, Firma

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()

# PostgreSQL bağlantı bilgileri ortam değişkenlerinden alınır
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME") # Bu 'on_muhasebe_master' olmalı

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    logger.error("Veritabanı bağlantı bilgileri .env dosyasından eksik veya hatalı.")
    raise ValueError("Veritabanı bağlantı bilgileri eksik.")

MASTER_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def update_master_schema(engine):
    """
    Ana veritabanı (master) şemasını GÜNCELLEr (veri kaybı olmadan).
    Eksik tabloları (örn: Firma, Kullanici) ekler.
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info(f"Ana veritabanı '{DB_NAME}' şeması başarıyla oluşturuldu/güncellendi.")
    except Exception as e:
        logger.error(f"Ana veritabanı şeması güncellenirken hata: {e}", exc_info=True)

def update_all_tenant_schemas(master_engine):
    """
    Tüm tenant veritabanlarını döngüye alır ve şemalarını GÜNCELLEr (veri kaybı olmadan).
    Eksik tabloları (örn: kullanici_izinleri) ekler.
    """
    MasterSession = sessionmaker(bind=master_engine)
    master_db = MasterSession()

    try:
        logger.info("Tüm firmaların (tenant) listesi alınıyor...")
        firmalar = master_db.query(Firma).all()
        if not firmalar:
            logger.warning("Güncellenecek tenant bulunamadı.")
            return
                
        logger.info(f"Toplam {len(firmalar)} tenant veritabanı güncellenecek...")
                
        for firma in firmalar:
            tenant_db_name = firma.db_adi
            if not tenant_db_name:
                logger.warning(f"Firma ID {firma.id} ({firma.unvan}) için 'db_adi' eksik, atlanıyor.")
                continue

            tenant_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{tenant_db_name}"

            try:
                tenant_engine = create_engine(tenant_url)
                logger.info(f"'{tenant_db_name}' veritabanına bağlanılıyor...")
                # YIKICI OLMAYAN GÜNCELLEME: Eksik tabloları ekler
                Base.metadata.create_all(bind=tenant_engine)
                logger.info(f"'{tenant_db_name}' şeması başarıyla oluşturuldu/güncellendi.")
                tenant_engine.dispose()
            except Exception as e:
                # Veritabanı yoksa veya bağlantı hatası varsa logla ve devam et
                logger.error(f"'{tenant_db_name}' güncellenirken HATA oluştu (Belki DB yoktur?): {e}")
        
    finally:
        master_db.close()

def main():
    """Ana veritabanını ve tüm tenant veritabanlarını güvenli bir şekilde günceller."""

    # 1. Ana Veritabanı (master) Engine'ini oluştur
    try:
        # Ana (master) veritabanının var olduğundan emin ol
        if not database_exists(MASTER_DATABASE_URL):
            logger.info(f"Ana veritabanı '{DB_NAME}' bulunamadı, oluşturuluyor...")
            create_database(MASTER_DATABASE_URL)
            logger.info(f"Ana veritabanı '{DB_NAME}' oluşturuldu.")
                
        master_engine = create_engine(MASTER_DATABASE_URL)
        logger.info(f"Ana veritabanına '{DB_NAME}' bağlanıldı.")
    except Exception as e:
        logger.critical(f"Ana veritabanına ({DB_NAME}) bağlanılamadı: {e}")
        return

    # 2. Ana Veritabanı Şemasını Güncelle (Veri kaybı olmadan)
    update_master_schema(master_engine)

    # 3. Tüm Tenant Veritabanı Şemalarını Güncelle (Veri kaybı olmadan)
    update_all_tenant_schemas(master_engine)

    master_engine.dispose()
    logger.info("Tüm veritabanı şemaları güncellendi.")

if __name__ == "__main__":
    logger.info("Veritabanı şema güncelleme script'i (GÜVENLİ) çalıştırılıyor...")
    main()
    logger.info("Script tamamlandı.")