# 'create_or_update_pg_tables.py' dosyasının KESİN VE YENİ MİMARİYE UYUMLU HALİ
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
import logging

# KRİTİK DÜZELTME: SADECE MASTER DB MODELLERİ İÇE AKTARILIR.
from api.modeller import (
    Base, Kullanici, Firma, Ayarlar 
    # Tenant modelleri (Musteri, Stok, KasaBankaHesap vb.) buradan import EDİLMEZ.
)
from api.guvenlik import get_password_hash

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()

# PostgreSQL bağlantı bilgileri ortam değişkenlerinden alınır
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    logger.error("Veritabanı bağlantı bilgileri .env dosyasından eksik.")
    raise ValueError("Veritabanı bağlantı bilgileri eksik. İşlem durduruldu.")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def create_or_update_tables():
    """Veritabanında eksik olan tabloları oluşturan ve varsayılan verileri ekleyen fonksiyon."""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        logger.info("Mevcut veritabanı tabloları siliniyor (CASCADE ile)...")
        with engine.connect() as connection:
            with connection.begin():
                inspector = inspect(engine)
                for table_name in inspector.get_table_names():
                    connection.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE;'))
        
        logger.info("Yeni Master DB tabloları oluşturuluyor (Firma, Kullanici, Ayarlar)...")
        # Base'in Master DB'de sadece Firma, Kullanici ve Ayarlar'ı oluşturması beklenir.
        Base.metadata.create_all(bind=engine) 
        logger.info("Master Tablo oluşturma işlemi tamamlandı.")
        
        logger.info("Varsayılan Kurucu Personel ve Firma ekleniyor...")
        
        default_email = "admin@master.com"
        # KRİTİK: Email ile sorgulanır
        if not db.query(Kullanici).filter_by(email=default_email).first(): 
            hashed_password = get_password_hash("755397")
            
            # 1. Kurucu Personeli Oluştur
            default_user = Kullanici(
                ad="Master",
                soyad="Yönetici",
                email=default_email, 
                telefon="5551234567",
                sifre_hash=hashed_password,
                rol="master" 
            )
            db.add(default_user)
            db.flush() # ID'yi alabilmek için
            
            # 2. Varsayılan Firmayı Oluştur (Tenant DB adı ile)
            default_firma = Firma(
                firma_adi="Master Yönetim Firması",
                tenant_db_name=f"tenant_{default_user.id}_master",
                kurucu_personel_id=default_user.id
            )
            db.add(default_firma)
            
            # 3. Kullanıcıyı Firmanın ID'sine Bağla (KRİTİK)
            default_user.firma_id = default_firma.id
            
            db.commit()
            logger.info(f"Varsayılan Master Kurucu Personeli ({default_email}) ve Firması başarıyla eklendi.")
        
    except Exception as e:
        logger.error(f"Veritabanı işlemleri sırasında hata oluştu: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("create_or_update_pg_tables.py çalıştırılıyor...")
    create_or_update_tables()
    logger.info("create_or_update_pg_tables.py tamamlandı.")