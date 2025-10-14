# api/rotalar/kasalar_bankalar.py (Database-per-Tenant ve Temizlik Uygulandı)
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import modeller # DÜZELTME: semalar kaldırıldı
# KRİTİK DÜZELTME 1: Tenant DB'ye dinamik bağlanacak yeni bağımlılık kullanıldı.
from ..veritabani import get_db as get_tenant_db 
from datetime import date
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .. import guvenlik

router = APIRouter(
    prefix="/kasalar_bankalar",
    tags=["Kasa ve Banka Hesapları"]
)

# Yardımcı fonksiyon: Boş stringleri None'a çevirir
def _convert_empty_to_none(data: dict) -> dict:
    return {k: v if v != "" else None for k, v in data.items()}

# KRİTİK DÜZELTME 2: Tenant DB bağlantısı için kullanılacak bağımlılık
TENANT_DB_DEPENDENCY = get_tenant_db

@router.get("/", response_model=modeller.KasaBankaListResponse)
def read_kasalar_bankalar(
    skip: int = 0,
    limit: int = 100,
    arama: Optional[str] = None,
    tip: Optional[modeller.KasaBankaTipiEnum] = None, # DÜZELTME: modeller.KasaBankaTipiEnum kullanıldı
    aktif_durum: Optional[bool] = None,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), 
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # KRİTİK DÜZELTME 3: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.KasaBankaHesap)

    if arama:
        query = query.filter(
            (modeller.KasaBankaHesap.hesap_adi.ilike(f"%{arama}%")) |
            (modeller.KasaBankaHesap.kod.ilike(f"%{arama}%")) |
            (modeller.KasaBankaHesap.banka_adi.ilike(f"%{arama}%"))
        )
    if tip:
        query = query.filter(modeller.KasaBankaHesap.tip == tip)
    if aktif_durum is not None:
        query = query.filter(modeller.KasaBankaHesap.aktif == aktif_durum)

    total_count = query.count()
    hesaplar = query.offset(skip).limit(limit).all()

    return {"items": hesaplar, "total": total_count}

@router.post("/", response_model=modeller.KasaBankaRead, status_code=status.HTTP_201_CREATED)
def create_kasa_banka(
    hesap: modeller.KasaBankaCreate,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY)
):
    try:
        # acilis_bakiyesi'ni modelden alıp geri kalan veriyi ayırıyoruz
        hesap_dict = hesap.model_dump()
        acilis_bakiyesi = hesap_dict.pop('acilis_bakiyesi', 0.0)
        
        hesap_data = _convert_empty_to_none(hesap_dict)

        db_hesap = modeller.KasaBankaHesap(
            **hesap_data,
            kullanici_id=1,
            bakiye=acilis_bakiyesi  # Bakiye doğrudan açılış bakiyesinden ayarlanıyor
        )
        db.add(db_hesap)
        db.flush()

        # Açılış bakiyesi varsa, doğru şekilde KasaBankaHareket oluşturuluyor
        if acilis_bakiyesi and acilis_bakiyesi != 0:
            islem_yone = modeller.IslemYoneEnum.GIRIS if acilis_bakiyesi > 0 else modeller.IslemYoneEnum.CIKIS
            
            db_kasa_hareket = modeller.KasaBankaHareket(
                tarih=date.today(),
                kasa_banka_id=db_hesap.id,
                islem_turu="AÇILIŞ BAKİYESİ",
                islem_yone=islem_yone,
                tutar=abs(acilis_bakiyesi),
                aciklama="Hesap Açılış Bakiyesi",
                kaynak=modeller.KaynakTipEnum.MANUEL,
                kullanici_id=1
            )
            db.add(db_kasa_hareket)

        db.commit()
        db.refresh(db_hesap)
        return db_hesap
    except IntegrityError as e:
        db.rollback()
        if "hesap_adi" in str(e) or "unique_hesap_adi" in str(e):
             raise HTTPException(status_code=400, detail="Bu hesap adı zaten kullanılıyor.")
        # Diğer IntegrityError'lar için genel bir mesaj
        raise HTTPException(status_code=400, detail="Bu bilgilere sahip bir kayıt zaten mevcut. Lütfen kod, hesap no gibi alanları kontrol edin.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Kasa/Banka hesabı oluşturulurken beklenmedik bir hata oluştu: {str(e)}")
            
@router.put("/{hesap_id}", response_model=modeller.KasaBankaRead)
def update_kasa_banka(
    hesap_id: int, 
    hesap: modeller.KasaBankaUpdate, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # KRİTİK DÜZELTME 6: IZOLASYON FILTRESI KALDIRILDI!
    db_hesap = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.id == hesap_id).first()
    if db_hesap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı")
    
    # KRİTİK DÜZELTME 7: Boş stringleri None'a çevir
    hesap_data = _convert_empty_to_none(hesap.model_dump(exclude_unset=True))
    for key, value in hesap_data.items():
        setattr(db_hesap, key, value)
    
    db.commit()
    db.refresh(db_hesap)
    return db_hesap

@router.delete("/{hesap_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kasa_banka(
    hesap_id: int, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # KRİTİK DÜZELTME 8: IZOLASYON FILTRESI KALDIRILDI!
    db_hesap = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.id == hesap_id).first()
    if db_hesap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı")
    
    # Kasa/Bankaya bağlı hareket olup olmadığını kontrol et (Tenant'ın kendi verisi içinde)
    hareketler = db.query(modeller.CariHareket).filter(modeller.CariHareket.kasa_banka_id == hesap_id).first()
    if hareketler:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu kasa/banka hesabına bağlı hareketler olduğu için silinemez.")

    db.delete(db_hesap)
    db.commit()
    return