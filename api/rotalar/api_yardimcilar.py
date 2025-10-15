# api.zip/rotalar/api_yardimcilar.py
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging
from sqlalchemy.exc import SQLAlchemyError
from ..semalar import CariHareket, Musteri, Tedarikci, GelirGider
logger = logging.getLogger(__name__)

def _cari_bakiyesini_guncelle(db: Session, cari_id: int, cari_tipi: str, kullanici_id: int):
    """
    Belirli bir carinin (Müşteri/Tedarikçi) bakiyesini, ilişkili tüm cari hareketlerini toplayarak yeniden hesaplar ve günceller.
    Bu fonksiyon, bir işlem (fatura, ödeme vb.) eklendiğinde veya silindiğinde çağrılmalıdır.
    """
    try:
        hareketler = db.query(CariHareket).filter(
            CariHareket.cari_id == cari_id,
            CariHareket.kullanici_id == kullanici_id
        ).all()

        toplam_borc = sum(h.tutar for h in hareketler if h.islem_yone == "BORC")
        toplam_alacak = sum(h.tutar for h in hareketler if h.islem_yone == "ALACAK")

        guncel_bakiye = toplam_alacak - toplam_borc

        if cari_tipi == "MUSTERI":
            cari = db.query(Musteri).filter(Musteri.id == cari_id, Musteri.kullanici_id == kullanici_id).first()
        elif cari_tipi == "TEDARIKCI":
            cari = db.query(Tedarikci).filter(Tedarikci.id == cari_id, Tedarikci.kullanici_id == kullanici_id).first()
        else:
            logger.warning(f"Bilinmeyen cari tipi: {cari_tipi} için bakiye güncellenemedi.")
            return

        if cari:
            cari.bakiye = guncel_bakiye
            db.commit()
            db.refresh(cari)
            logger.info(f"Cari ID {cari_id} için bakiye başarıyla güncellendi. Yeni bakiye: {guncel_bakiye}")
        else:
            logger.warning(f"Cari ID {cari_id} bulunamadığı için bakiye güncellenemedi.")

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Cari bakiye güncellenirken veritabanı hatası: {e}", exc_info=True)
        raise e
    except Exception as e:
        logger.error(f"Cari bakiye güncellenirken beklenmeyen bir hata oluştu: {e}", exc_info=True)
        raise e