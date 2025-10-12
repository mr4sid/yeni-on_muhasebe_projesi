# 'create_or_update_pg_tables.py' dosyasının API'den bağımsız nihai hali
import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Gerekli tüm master modelleri ve şifreleme fonksiyonu import edilir
from api.modeller import Base, Kullanici, Firma, Ayarlar
from api.guvenlik import get_password_hash

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()

# PostgreSQL bağlantı bilgileri
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
MASTER_DB_NAME = os.getenv("DB_NAME")
TENANT_DB_NAME_TO_DROP = "tenant_master_yonetim_firmasi" # Olası artıkları temizlemek için

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, MASTER_DB_NAME]):
    logger.error("Veritabanı bağlantı bilgileri .env dosyasından eksik.")
    raise ValueError("Veritabanı bağlantı bilgileri eksik. İşlem durduruldu.")

POSTGRES_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
MASTER_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{MASTER_DB_NAME}"

def setup_initial_database_and_user():
    """
    Veritabanlarını sıfırlar, master tablolarını oluşturur ve ilk master kullanıcı ile firmasını
    doğrudan veritabanına ekler. API'ye bağımlı DEĞİLDİR.
    """
    # 1. Veritabanlarını Sil ve Yeniden Oluştur
    engine_postgres = create_engine(POSTGRES_DB_URL, isolation_level='AUTOCOMMIT')
    try:
        with engine_postgres.connect() as connection:
            databases_to_drop = [MASTER_DB_NAME, TENANT_DB_NAME_TO_DROP]
            for db_name in databases_to_drop:
                logger.info(f"'{db_name}' veritabanına olan bağlantılar sonlandırılıyor...")
                connection.execute(text(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}';"))
                logger.info(f"'{db_name}' veritabanı siliniyor...")
                connection.execute(text(f"DROP DATABASE IF EXISTS {db_name};"))

            logger.info(f"'{MASTER_DB_NAME}' veritabanı yeniden oluşturuluyor...")
            connection.execute(text(f"CREATE DATABASE {MASTER_DB_NAME} ENCODING 'UTF8';"))
            logger.info("Veritabanı sıfırlama işlemi tamamlandı.")
    except Exception as e:
        logger.error(f"Veritabanı sıfırlama sırasında bir hata oluştu: {e}")
        return
    finally:
        engine_postgres.dispose()

    # 2. Master Tablolarını ve İlk Kullanıcıyı Oluştur
    engine_master = create_engine(MASTER_DB_URL)
    SessionMaster = sessionmaker(bind=engine_master)
    db = SessionMaster()
    try:
        logger.info(f"'{MASTER_DB_NAME}' içine master tabloları (Kullanici, Firma, Ayarlar) oluşturuluyor...")
        Base.metadata.create_all(bind=engine_master, tables=[Kullanici.__table__, Firma.__table__, Ayarlar.__table__])
        logger.info("Master tabloları başarıyla oluşturuldu.")

        logger.info("Varsayılan Kurucu Personel ve Firma doğrudan veritabanına ekleniyor...")
        default_email = "admin@master.com"
        
        # Kullanıcı zaten var mı diye kontrol et
        if not db.query(Kullanici).filter_by(email=default_email).first():
            hashed_password = get_password_hash("755397")
            
            # 1. Kurucu Personeli Oluştur
            default_user = Kullanici(
                ad="Master",
                soyad="Yönetici",
                email=default_email,
                telefon="0000000000",
                sifre_hash=hashed_password,
                rol="master"
            )
            db.add(default_user)
            db.flush()  # ID'yi alabilmek için

            # 2. Varsayılan Firmayı Oluştur
            # Not: Bu aşamada tenant veritabanı fiziksel olarak oluşturulmaz,
            # o işi register endpoint'i yapar. Burada sadece kaydını tutuyoruz.
            default_firma = Firma(
                firma_adi="Master Yonetim Firmasi",
                tenant_db_name="tenant_master_yonetim_firmasi", # İsimlendirme tutarlı olsun
                kurucu_personel_id=default_user.id
            )
            db.add(default_firma)
            db.flush() # ID'yi alabilmek için

            # 3. Kullanıcıyı oluşturulan firmanın ID'sine bağla
            default_user.firma_id = default_firma.id
            
            db.commit()
            logger.info(f"Varsayılan Master Kurucu Personel ({default_email}) ve Firması başarıyla eklendi.")
        else:
            logger.warning(f"Kullanıcı '{default_email}' zaten mevcut. Ekleme adımı atlandı.")
            
    except Exception as e:
        logger.error(f"Tablo veya kullanıcı oluşturma sırasında hata oluştu: {e}")
        db.rollback()
    finally:
        db.close()
        engine_master.dispose()

if __name__ == "__main__":
    logger.info("Veritabanı sıfırlama ve başlangıç kullanıcısı oluşturma scripti başlatılıyor...")
    setup_initial_database_and_user()
    logger.info("Script tamamlandı. Artık API sunucusunu başlatabilirsiniz.")