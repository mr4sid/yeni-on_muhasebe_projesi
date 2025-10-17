# api/veritabani.py Dosyasının YENİ VE TAM İÇERİĞİ
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine.base import Engine
from sqlalchemy.exc import OperationalError
import logging
from typing import Dict, Generator
from fastapi import HTTPException, status, Depends
from jose import jwt
from .database_core import create_tenant_engine_and_session
from . import modeller, semalar
from .guvenlik import oauth2_scheme
from .config import settings
# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

# --- MERKEZİ BAŞLATMA ---
try:
    master_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    MasterSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=master_engine)
    logger.info(f"MASTER DB motoru başlatıldı: {MASTER_DB_NAME}")
except Exception as e:
    logger.error(f"MASTER DB motoru başlatılırken hata oluştu: {e}")
    master_engine = None
    MasterSessionLocal = None

tenant_engines: Dict[str, Engine] = {}

# --- YARDIMCI FONKSİYONLAR (YENİ EKLENDİ) ---

def create_tenant_db_and_tables(tenant_db_name: str):
    """Yeni bir PostgreSQL veritabanı ve içinde tüm tabloları oluşturur."""
    root_engine = create_engine(ROOT_DB_URL + "postgres", isolation_level="AUTOCOMMIT")
    try:
        with root_engine.connect() as conn:
            # Veritabanının var olup olmadığını kontrol et
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{tenant_db_name}'"))
            db_exists = result.scalar() == 1
            
            if not db_exists:
                conn.execute(text(f'CREATE DATABASE "{tenant_db_name}"'))
                logger.info(f"Yeni veritabanı oluşturuldu: {tenant_db_name}")
            else:
                logger.warning(f"Veritabanı zaten mevcut: {tenant_db_name}")

        # Yeni veritabanına bağlan ve tabloları oluştur
        tenant_engine = create_engine(f"{ROOT_DB_URL}{tenant_db_name}")
        modeller.Base.metadata.create_all(bind=tenant_engine)
        logger.info(f"'{tenant_db_name}' veritabanı için tablolar başarıyla oluşturuldu/doğrulandı.")

    except OperationalError as e:
        logger.error(f"Veritabanı işlemi sırasında hata: {e}")
        raise e
    except Exception as e:
        logger.error(f"Tenant DB ve tablolar oluşturulurken beklenmedik hata: {e}")
        raise e
    finally:
        root_engine.dispose()

def add_default_user_data(db: Session, kullanici_id_master: int):
    """Yeni bir tenant veritabanına varsayılan başlangıç verilerini ve YÖNETİCİ kullanıcısını ekler."""
    try:
        # Önce Master DB'den yönetici bilgilerini çek
        master_db_session = next(get_master_db())
        master_user = master_db_session.query(modeller.Kullanici).filter(modeller.Kullanici.id == kullanici_id_master).first()
        master_db_session.close()

        if not master_user:
            raise Exception("Master veritabanında yönetici kullanıcısı bulunamadı.")

        # --- GÜNCELLEME: Tenant DB'ye yöneticiyi eklerken ID belirtmiyoruz ---
        # Veritabanı, ilk kullanıcı olduğu için ID'yi otomatik olarak 1 yapacaktır.
        tenant_user = modeller.Kullanici(
            ad=master_user.ad,
            soyad=master_user.soyad,
            email=master_user.email,
            sifre_hash=master_user.sifre_hash,
            telefon=master_user.telefon,
            rol=master_user.rol,
            aktif=True
        )
        db.add(tenant_user)
        db.flush() # ID'nin veritabanı tarafından atanmasını sağla

        # Varsayılan Kasa/Banka, Müşteri ve Tedarikçi kayıtlarını oluştur
        nakit_kasa = modeller.KasaBankaHesap(kod="NAKIT_KASA", hesap_adi="Nakit Kasa", tip="KASA", bakiye=0.0, para_birimi="TRY", kullanici_id=tenant_user.id)
        db.add(nakit_kasa)

        perakende_musteri = modeller.Musteri(ad="Perakende Müşteri", kod="PERAKENDE", kullanici_id=tenant_user.id)
        db.add(perakende_musteri)
        
        genel_tedarikci = modeller.Tedarikci(ad="Genel Tedarikçi", kod="GENEL", kullanici_id=tenant_user.id)
        db.add(genel_tedarikci)

        db.commit()
        logger.info(f"Tenant DB için yönetici ve varsayılan veriler başarıyla eklendi. Yeni Kullanıcı ID: {tenant_user.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Varsayılan veriler eklenirken hata: {e}")
        raise e

# --- OTURUM (SESSION) YÖNETİM FONKSİYONLARI ---

def get_master_engine() -> Engine:
    """MASTER veritabanı motorunu döndürür."""
    global master_engine
    if master_engine is None:
        master_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        logger.info(f"MASTER DB motoru yeniden başlatıldı: {MASTER_DB_NAME}")
    return master_engine

def get_master_db() -> Generator:
    """Master veritabanı için bir oturum sağlar."""
    if MasterSessionLocal is None:
        raise HTTPException(status_code=500, detail="Master veritabanı bağlantısı kurulamadı.")
    db = MasterSessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_tenant_engine(tenant_db_name: str) -> Engine:
    """Tenant veritabanı motorunu döndürür, yoksa oluşturur."""
    if tenant_db_name not in tenant_engines:
        tenant_url = f"{ROOT_DB_URL}{tenant_db_name}"
        engine = create_engine(tenant_url, pool_pre_ping=True)
        tenant_engines[tenant_db_name] = engine
        logger.info(f"Yeni Tenant DB motoru başlatıldı: {tenant_db_name}")
    return tenant_engines[tenant_db_name]

def get_db(token: str = Depends(oauth2_scheme)):
    """
    Token'ı çözümleyerek kullanıcıyı bulur ve kullanıcının ilişkili olduğu
    firma veritabanına (tenant) bir oturum (session) sağlar.
    """
    from . import guvenlik

    db = None
    master_db_session = next(get_master_db()) # <-- 1. ADIM: Master DB'yi al
    try:
        # <-- 2. ADIM: Aldığın Master DB'yi get_current_user'a parametre olarak ver
        current_user = guvenlik.get_current_user(token=token, db=master_db_session)

        tenant_db_name = None
        if hasattr(current_user, 'firma') and current_user.firma:
            tenant_db_name = current_user.firma.db_adi
        
        if not tenant_db_name:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            tenant_db_name = payload.get("firma_db")
            if not tenant_db_name:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Kullanıcıya atanmış bir firma veritabanı bulunamadı."
                )

        db = get_tenant_session_by_name(tenant_db_name)
        yield db

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabanı oturumu oluşturulurken bir hata oluştu: {e}")
    finally:
        if db is not None:
            db.close()
        if master_db_session is not None:
            master_db_session.close()

# get_tenant_db fonksiyonu get_db'nin bir varyasyonu olarak düzeltildi
def get_tenant_db(tenant_db_name: str) -> Generator:
    """Belirtilen ada göre tenant veritabanı oturumu sağlar."""
    if not tenant_db_name:
        raise ValueError("Tenant veritabanı adı belirtilmedi.")
    engine = get_tenant_engine(tenant_db_name)
    TenantSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TenantSessionLocal()
    try:
        yield db
    finally:
        db.close()

def reset_db_connection():
    """Tüm Tenant ve Master bağlantılarını sıfırlar."""
    global master_engine, MasterSessionLocal, tenant_engines
    
    if master_engine:
        master_engine.dispose()
        master_engine = None
    
    MasterSessionLocal = None # Yeniden oluşturulması için None yap
    
    for engine in tenant_engines.values():
        engine.dispose()
    
    tenant_engines.clear()
    logger.info("Tüm Master ve Tenant veritabanı bağlantıları sıfırlandı.")

def get_tenant_session_by_name(db_name: str):
    """
    Verilen veritabanı ismine göre yeni bir veritabanı oturumu (session) oluşturur ve döndürür.
    """
    SessionLocal_tenant = create_tenant_engine_and_session(db_name)
    return SessionLocal_tenant()    