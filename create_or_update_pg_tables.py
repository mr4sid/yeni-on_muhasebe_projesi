# 'create_or_update_pg_tables.py' dosyasının tam içeriği
import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import date, timedelta
# Gerekli tüm master modelleri ve şifreleme fonksiyonu import edilir
from api.modeller import Base, Kullanici, Firma, Ayarlar, LisansDurumEnum, RolEnum
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
    engine_postgres = create_engine(POSTGRES_DB_URL, isolation_level='AUTOCOMMIT')
    try:
        with engine_postgres.connect() as connection:
            # Önceki denemelerden kalmış olabilecek TÜM tenant veritabanlarını bul ve sil
            tenant_dbs_query = "SELECT datname FROM pg_database WHERE datname LIKE 'tenant_%%';"
            existing_tenants = connection.execute(text(tenant_dbs_query)).fetchall()
            
            all_dbs_to_drop = [MASTER_DB_NAME] + [row[0] for row in existing_tenants]
            
            for db_name in all_dbs_to_drop:
                logger.info(f"'{db_name}' veritabanına olan bağlantılar sonlandırılıyor...")
                connection.execute(text(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}';"))
                logger.info(f"'{db_name}' veritabanı siliniyor...")
                connection.execute(text(f"DROP DATABASE IF EXISTS \"{db_name}\";"))

            logger.info(f"'{MASTER_DB_NAME}' veritabanı yeniden oluşturuluyor...")
            connection.execute(text(f"CREATE DATABASE \"{MASTER_DB_NAME}\" ENCODING 'UTF8';"))
            logger.info("Veritabanı sıfırlama işlemi tamamlandı.")
    except Exception as e:
        logger.error(f"Veritabanı sıfırlama sırasında bir hata oluştu: {e}")
        return
    finally:
        engine_postgres.dispose()

    # 2. Master Tablolarını ve İlk Kullanıcıyı Oluştur (Bu kısım zaten doğru)
    engine_master = create_engine(MASTER_DB_URL)
    SessionMaster = sessionmaker(bind=engine_master)
    db = SessionMaster()
    try:
        logger.info(f"'{MASTER_DB_NAME}' içine master tabloları (Kullanici, Firma, Ayarlar) oluşturuluyor...")
        Base.metadata.create_all(bind=engine_master, tables=[Kullanici.__table__, Firma.__table__, Ayarlar.__table__])
        logger.info("Master tabloları başarıyla oluşturuldu.")

        logger.info("Varsayılan Kurucu Personel ve Firma doğrudan veritabanına ekleniyor...")
        default_email = "admin@master.com"
        
        lisans_baslangic = date.today()
        lisans_bitis = lisans_baslangic + timedelta(days=365)

        if not db.query(Kullanici).filter_by(email=default_email).first():
            hashed_password = get_password_hash("755397")
            
            default_user = Kullanici(
                ad="Master",
                soyad="Yönetici",
                email=default_email,
                telefon="0000000000",
                sifre_hash=hashed_password,
                rol="SUPERADMIN"
            )
            db.add(default_user)
            db.flush() 

            default_firma = Firma(
                unvan="Master Yonetim Firmasi",
                db_adi="tenant_master_yonetim_firmasi",
                firma_no="mv1000",
                kurucu_personel_id=default_user.id,
                lisans_baslangic_tarihi=lisans_baslangic,
                lisans_bitis_tarihi=lisans_bitis,
                lisans_durum=LisansDurumEnum.AKTIF
            )
            db.add(default_firma)
            db.flush()

            default_user.firma_id = default_firma.id
            
            db.commit()
            logger.info(f"Varsayılan Master Kurucu Personel ({default_email}) ve Firması başarıyla eklendi.")
        else:
            default_user = db.query(Kullanici).filter_by(email=default_email).first()
            default_firma = db.query(Firma).filter_by(kurucu_personel_id=default_user.id).first()
            if default_firma:
                default_firma.lisans_baslangic_tarihi = lisans_baslangic
                default_firma.lisans_bitis_tarihi = lisans_bitis
                default_firma.lisans_durum = LisansDurumEnum.AKTIF
                db.commit()
                logger.warning(f"Kullanıcı '{default_email}' mevcut. Lisans bilgileri yeniden 1 yıl AKTIF olarak ayarlandı.")
            else:
                logger.warning(f"Kullanıcı '{default_email}' mevcut ancak firma kaydı bulunamadı. Lütfen kontrol edin.")
    
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