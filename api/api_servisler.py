from sqlalchemy.orm import Session
from sqlalchemy import func, case
import logging
from datetime import datetime
from . import semalar
from sqlalchemy.orm import Session
from .semalar import KasaBanka, Tedarikci, Musteri
from datetime import date
from .modeller import KasaBankaHesap, Tedarikci, Musteri 
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CariHesaplamaService:
    def __init__(self, db: Session):
        self.db = db

    def calculate_cari_net_bakiye(self, cari_id: int, cari_turu: str) -> float:
        """
        Belirli bir cari (Müşteri veya Tedarikçi) için net bakiyeyi tek bir sorguda hesaplar.
        KRİTİK DÜZELTME: Sorgularda semalar.CariHareket yerine modeller.CariHareket kullanıldı.
        """
        from .modeller import CariHareket # Scope'u daraltmak için burada import edildi

        # Sorgu sonucunda None gelmesi durumunda 0 değerini kullanmak için func.coalesce eklendi.
        result = self.db.query(
            func.coalesce(func.sum(case((CariHareket.islem_yone == "ALACAK", CariHareket.tutar), else_=0)), 0).label('alacak_toplami'),
            func.coalesce(func.sum(case((CariHareket.islem_yone == "BORC", CariHareket.tutar), else_=0)), 0).label('borc_toplami')
        ).filter(
            CariHareket.cari_id == cari_id,
            CariHareket.cari_tip == cari_turu
        ).one()

        net_bakiye = result.alacak_toplami - result.borc_toplami
        return net_bakiye
    
# Varsayılan verileri ekleyen fonksiyon
def create_initial_data(db: Session, kullanici_id: int):
    try:
        logger.info("Varsayılan veriler kontrol ediliyor ve ekleniyor...")

        # Varsayılan perakende müşteriyi kontrol et ve ekle
        perakende_musteri = db.query(Musteri).filter(Musteri.kod == "PERAKENDE_MUSTERI", Musteri.kullanici_id == kullanici_id).first()
        if not perakende_musteri:
            yeni_musteri = Musteri(
                ad="Perakende Müşteri",
                kod="PERAKENDE_MUSTERI",
                aktif=True,
                olusturma_tarihi=datetime.now(),
                kullanici_id=kullanici_id
            )
            db.add(yeni_musteri)
            db.commit()
            db.refresh(yeni_musteri)
            logger.info("Varsayılan 'Perakende Müşteri' başarıyla eklendi.")
        else:
            logger.info("Varsayılan 'Perakende Müşteri' zaten mevcut.")

        # Varsayılan Genel Tedarikçi (YENİ EKLENEN KISIM)
        genel_tedarikci = db.query(Tedarikci).filter(Tedarikci.kod == "GENEL_TEDARIKCI", Tedarikci.kullanici_id == kullanici_id).first()
        if not genel_tedarikci:
            yeni_tedarikci = Tedarikci(
                ad="Genel Tedarikçi",
                kod="GENEL_TEDARIKCI",
                aktif=True,
                olusturma_tarihi=datetime.now(),
                kullanici_id=kullanici_id
            )
            db.add(yeni_tedarikci)
            db.commit()
            db.refresh(yeni_tedarikci)
            logger.info("Varsayılan 'Genel Tedarikçi' başarıyla eklendi.")
        else:
            logger.info("Varsayılan 'Genel Tedarikçi' zaten mevcut.")

        # Varsayılan NAKİT hesabını kontrol et ve ekle
        nakit_kasa = db.query(KasaBankaHesap).filter(KasaBankaHesap.kod == "NAKİT_KASA", KasaBankaHesap.kullanici_id == kullanici_id).first()
        if not nakit_kasa:
            yeni_kasa = KasaBankaHesap(
                hesap_adi="Nakit Kasa",
                kod="NAKİT_KASA",
                tip="KASA",
                bakiye=0.0,
                para_birimi="TL",
                aktif=True,
                varsayilan_odeme_turu="NAKİT",
                olusturma_tarihi=datetime.now(),
                kullanici_id=kullanici_id
            )
            db.add(yeni_kasa)
            db.commit()
            db.refresh(yeni_kasa)
            logger.info("Varsayılan 'NAKİT KASA' hesabı başarıyla eklendi.")
        else:
            logger.info("Varsayılan 'NAKİT KASA' hesabı zaten mevcut.")

    except Exception as e:
        logger.error(f"Varsayılan veriler eklenirken bir hata oluştu: {e}")
        db.rollback()    