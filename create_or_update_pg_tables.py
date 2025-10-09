# 'create_or_update_pg_tables.py' dosyasının GÜNCEL HALİ
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
import logging

# DÜZELTİLDİ: Tüm içe aktarmalar buraya taşındı.
from api.modeller import (
    Base, Musteri, Tedarikci, KasaBankaHesap, UrunNitelik, Kullanici,
    CariHareket, Fatura, FaturaKalemi, GelirGider, Siparis, SiparisKalemi,
    Stok, StokHareket, Sirket, SirketAyarlari, SirketBilgileri
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
        
        logger.info("Yeni veritabanı tabloları oluşturuluyor...")
        Base.metadata.create_all(bind=engine)
        logger.info("Tablo oluşturma işlemi tamamlandı.")
        
        logger.info("Varsayılan veriler ekleniyor...")
        
        if not db.query(Kullanici).filter_by(kullanici_adi="admin").first():
            hashed_password = get_password_hash("755397")
            default_user = Kullanici(
                kullanici_adi="admin",
                sifre_hash=hashed_password,
                ad="Yönetici",
                soyad="Hesabı",
                email="admin@onmuhasebe.com"
            )
            db.add(default_user)
            db.commit()
            logger.info("Varsayılan 'admin' kullanıcısı başarıyla eklendi.")

        # Nitelikler
        urun_birimleri = ["Adet", "Metre", "Kilogram", "Litre", "Kutu"]
        nitelik_listesi = [
            ("Kategori 1", "kategori"), ("Kategori 2", "kategori"),
            ("Marka 1", "marka"), ("Marka 2", "marka"),
            ("Grup 1", "urun_grubu"), ("Grup 2", "urun_grubu"),
            ("Türkiye", "ulke"), ("ABD", "ulke")
        ]
        
        for ad in urun_birimleri:
            if not db.query(UrunNitelik).filter_by(ad=ad, nitelik_tipi="birim").first():
                db.add(UrunNitelik(ad=ad, nitelik_tipi="birim", kullanici_id=1))
        
        for ad, tip in nitelik_listesi:
            if not db.query(UrunNitelik).filter_by(ad=ad, nitelik_tipi=tip).first():
                db.add(UrunNitelik(ad=ad, nitelik_tipi=tip, kullanici_id=1))

        if not db.query(Musteri).filter_by(kod="PERAKENDE_MUSTERI").first():
            perakende_musteri = Musteri(ad="Perakende Müşterisi", kod="PERAKENDE_MUSTERI", aktif=True, kullanici_id=1)
            db.add(perakende_musteri)
        
        if not db.query(Tedarikci).filter_by(kod="GENEL_TEDARIKCI").first():
            genel_tedarikci = Tedarikci(ad="Genel Tedarikçi", kod="GENEL_TEDARIKCI", aktif=True, kullanici_id=1)
            db.add(genel_tedarikci)

        if not db.query(KasaBankaHesap).filter_by(hesap_adi="NAKİT KASA").first():
            nakit_kasa = KasaBankaHesap(
                hesap_adi="NAKİT KASA",
                tip="KASA",
                bakiye=0.0,
                para_birimi="TL",
                aktif=True,
                kullanici_id=1
            )
            db.add(nakit_kasa)

        db.commit()
        logger.info("Varsayılan veriler başarıyla eklendi.")

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