# api/veritabani.py Dosyasının GÜNCELLENMİŞ TAM İÇERİĞİ
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import logging

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    logger.error("Veritabanı bağlantı bilgileri .env dosyasından eksik veya hatalı. Lütfen .env dosyasını kontrol edin.")
    raise ValueError("Veritabanı bağlantı bilgileri eksik.")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy motoru için global değişken
engine_instance = None
SessionLocal = None

def get_engine():
    """
    Motorun mevcut bir örneğini döndürür, yoksa yeni bir tane oluşturur.
    """
    global engine_instance
    if engine_instance is None:
        engine_instance = create_engine(DATABASE_URL)
        logger.info("Yeni bir veritabanı motoru ve bağlantı havuzu oluşturuldu.")
    return engine_instance

def reset_db_connection():
    """
    Mevcut veritabanı bağlantısını ve havuzunu sıfırlayan fonksiyon.
    """
    global engine_instance, SessionLocal
    if engine_instance:
        engine_instance.dispose()
        logger.info("Mevcut veritabanı bağlantı havuzu kapatıldı (disposed).")
    engine_instance = None
    SessionLocal = None
    
# Deklaratif taban sınıfı
Base = declarative_base()

# Veritabanı oturumu almak için bağımlılık fonksiyonu
def get_db():
    """
    Veritabanı oturumu almak için bağımlılık fonksiyonu.
    """
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
        logger.info("Yeni bir veritabanı oturumu sınıfı (SessionLocal) oluşturuldu.")
    
    db = SessionLocal()
    try:
        # Bağlantı testi kaldırıldı. İlk sorgu bağlantıyı otomatik olarak test edecektir.
        yield db
    except Exception as e:
        logger.critical(f"Veritabanı bağlantısı kurulamadı! Hata: {e}")
        reset_db_connection()
        raise
    finally:
        db.close()