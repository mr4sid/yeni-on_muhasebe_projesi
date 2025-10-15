# api/rotalar/cari_hareketler.py (Database-per-Tenant Uyumlu ve Temizlik Uygulandı)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from .. import modeller, guvenlik
from ..veritabani import get_db as get_tenant_db # KRİTİK DÜZELTME 2: Tenant DB'ye yönlendirildi
from datetime import date
from sqlalchemy.exc import IntegrityError

router = APIRouter(
    prefix="/cari_hareketler",
    tags=["Cari Hareketler"]
)

TENANT_DB_DEPENDENCY = get_tenant_db

# --- VERİ OKUMA (READ) ---
@router.get("/", response_model=modeller.CariHareketListResponse)
def read_cari_hareketler(
    skip: int = 0,
    limit: int = 100,
    cari_id: Optional[int] = None,
    cari_tip: Optional[modeller.CariTipiEnum] = None, # DÜZELTME 3: modeller.CariTipiEnum kullanıldı
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # KRİTİK DÜZELTME 4: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.CariHareket)

    if cari_id is not None:
        query = query.filter(modeller.CariHareket.cari_id == cari_id)
    if cari_tip:
        query = query.filter(modeller.CariHareket.cari_tip == cari_tip) # DÜZELTME 5: Enum objesi doğrudan kullanılır
    if baslangic_tarihi:
        query = query.filter(modeller.CariHareket.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(modeller.CariHareket.tarih <= bitis_tarihi)

    total_count = query.count()
    hareketler = query.order_by(modeller.CariHareket.tarih.desc(), modeller.CariHareket.olusturma_tarihi_saat.desc()).offset(skip).limit(limit).all()

    items = [modeller.CariHareketRead.model_validate(h, from_attributes=True) for h in hareketler]

    return {"items": items, "total": total_count}

# --- VERİ OLUŞTURMA (CREATE) ---
@router.post("/manuel", response_model=modeller.CariHareketRead)
def create_manuel_cari_hareket(
    hareket: modeller.CariHareketCreate,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # KRİTİK DÜZELTME 6: Tenant DB'de Kurucu Personelin ID'si her zaman 1'dir.
    KULLANICI_ID = 1
    
    db_hareket = modeller.CariHareket(
        **hareket.model_dump(),
        kullanici_id=KULLANICI_ID, # Tenant ID atanır
        olusturan_kullanici_id=KULLANICI_ID 
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
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # KRİTİK DÜZELTME 7: IZOLASYON FILTRESI KALDIRILDI!
    db_hareket = db.query(modeller.CariHareket).filter(
        modeller.CariHareket.id == hareket_id
    ).first()
    
    if db_hareket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cari hareket bulunamadı")
    
    # Sadece manuel olarak oluşturulan belirli hareket türlerinin silinmesine izin ver
    izinli_kaynaklar = [
        modeller.KaynakTipEnum.MANUEL, # DÜZELTME 8: modeller.X kullanıldı
        modeller.KaynakTipEnum.TAHSILAT,
        modeller.KaynakTipEnum.ODEME
    ]
    if db_hareket.kaynak not in [k.value for k in izinli_kaynaklar]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu türde bir cari hareket API üzerinden doğrudan silinemez.")
    
    db.begin_nested()
    try:
        if db_hareket.kasa_banka_id:
             # KRİTİK DÜZELTME 9: IZOLASYON FILTRESI KALDIRILDI!
            kasa_hesabi = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.id == db_hareket.kasa_banka_id).first()
            if kasa_hesabi:
                # DÜZELTME 10: modeller.IslemYoneEnum kullanıldı
                if db_hareket.islem_yone == modeller.IslemYoneEnum.ALACAK: # Tahsilat (Kasaya giriş)
                    kasa_hesabi.bakiye -= db_hareket.tutar # Geri al
                elif db_hareket.islem_yone == modeller.IslemYoneEnum.BORC: # Ödeme (Kasadan çıkış)
                    kasa_hesabi.bakiye += db_hareket.tutar # Geri al
        
        db.delete(db_hareket)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Cari hareket silinirken hata: {str(e)}")
        
    return