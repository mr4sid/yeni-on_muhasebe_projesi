# api/rotalar/cari_hareketler.py dosyasının tamamı (güncellenmiş ve düzeltilmiş hali)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from .. import modeller, semalar, guvenlik
from ..veritabani import get_db
from datetime import date

router = APIRouter(
    prefix="/cari_hareketler",
    tags=["Cari Hareketler"]
)

# --- VERİ OKUMA (READ) ---
@router.get("/", response_model=modeller.CariHareketListResponse)
def read_cari_hareketler(
    skip: int = 0,
    limit: int = 100,
    cari_id: Optional[int] = None,
    cari_tip: Optional[semalar.CariTipiEnum] = None,
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # JWT ile kullanıcı bilgisi
    db: Session = Depends(get_db)
):
    # KURAL UYGULANDI: Sorgular 'modeller' kullanır.
    query = db.query(modeller.CariHareket).filter(modeller.CariHareket.kullanici_id == current_user.id)

    if cari_id is not None:
        query = query.filter(modeller.CariHareket.cari_id == cari_id)
    if cari_tip:
        # HATA DÜZELTİLDİ: 'cari_turu' -> 'cari_tip'
        query = query.filter(modeller.CariHareket.cari_tip == cari_tip.value)
    if baslangic_tarihi:
        query = query.filter(modeller.CariHareket.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(modeller.CariHareket.tarih <= bitis_tarihi)

    total_count = query.count()
    # HATA DÜZELTİLDİ: Eksik olan 'olusturma_tarihi_saat' kolonuna göre sıralama eklendi.
    hareketler = query.order_by(modeller.CariHareket.tarih.desc(), modeller.CariHareket.olusturma_tarihi_saat.desc()).offset(skip).limit(limit).all()

    # Yanıt modeline uygun hale getirme
    items = [modeller.CariHareketRead.model_validate(h, from_attributes=True) for h in hareketler]

    return {"items": items, "total": total_count}

# --- VERİ OLUŞTURMA (CREATE) ---
@router.post("/manuel", response_model=modeller.CariHareketRead)
def create_manuel_cari_hareket(
    hareket: modeller.CariHareketCreate,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    # KURAL UYGULANDI: Sorgular 'modeller' kullanır ve JWT'den gelen ID kullanılır.
    db_hareket = modeller.CariHareket(
        **hareket.model_dump(),
        kullanici_id=current_user.id,
        olusturan_kullanici_id=current_user.id # Manuel hareketi oluşturan da aynı kullanıcıdır.
    )
    db.add(db_hareket)
    db.commit()
    db.refresh(db_hareket)

    return db_hareket

# --- VERİ SİLME (DELETE) ---
@router.delete("/{hareket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cari_hareket(
    hareket_id: int, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    # KURAL UYGULANDI: Sorgular 'modeller' kullanır ve JWT'den gelen ID ile filtreleme yapılır.
    db_hareket = db.query(modeller.CariHareket).filter(
        modeller.CariHareket.id == hareket_id,
        modeller.CariHareket.kullanici_id == current_user.id
    ).first()
    
    if db_hareket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cari hareket bulunamadı")
    
    # Sadece manuel olarak oluşturulan belirli hareket türlerinin silinmesine izin ver
    izinli_kaynaklar = [
        semalar.KaynakTipEnum.MANUEL,
        semalar.KaynakTipEnum.TAHSILAT,
        semalar.KaynakTipEnum.ODEME
    ]
    if db_hareket.kaynak not in [k.value for k in izinli_kaynaklar]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu türde bir cari hareket API üzerinden doğrudan silinemez.")
    
    # İlişkili kasa hareketini de geri al (eğer varsa)
    db.begin_nested()
    try:
        if db_hareket.kasa_banka_id:
            kasa_hesabi = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.id == db_hareket.kasa_banka_id).first()
            if kasa_hesabi:
                if db_hareket.islem_yone == semalar.IslemYoneEnum.ALACAK: # Tahsilat (Kasaya giriş)
                    kasa_hesabi.bakiye -= db_hareket.tutar
                elif db_hareket.islem_yone == semalar.IslemYoneEnum.BORC: # Ödeme (Kasadan çıkış)
                    kasa_hesabi.bakiye += db_hareket.tutar
        
        db.delete(db_hareket)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Cari hareket silinirken hata: {str(e)}")
        
    return