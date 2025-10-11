# api/rotalar/gelir_gider.py dosyasının TAMAMI (Database-per-Tenant Uyumlu)
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import String, and_, func
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from datetime import date, datetime

from .. import modeller, guvenlik # DÜZELTME 1: semalar kaldırıldı
# KRİTİK DÜZELTME 2: Tenant DB'ye dinamik bağlanacak yeni bağımlılık kullanıldı.
from ..veritabani import get_db as get_tenant_db 

router = APIRouter(
    prefix="/gelir_gider",
    tags=["Gelir ve Gider İşlemleri"]
)

# KRİTİK DÜZELTME 3: Tenant DB bağlantısı için kullanılacak bağımlılık
TENANT_DB_DEPENDENCY = get_tenant_db
KULLANICI_ID_TENANT = 1

@router.get("/", response_model=modeller.GelirGiderListResponse)
def read_gelir_gider(
    skip: int = 0,
    limit: int = 20,
    tip_filtre: Optional[modeller.GelirGiderTipEnum] = None, # DÜZELTME 4: modeller.GelirGiderTipEnum kullanıldı
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    aciklama_filtre: Optional[str] = None,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    
    # KRİTİK DÜZELTME 5: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.GelirGider)

    if tip_filtre:
        query = query.filter(modeller.GelirGider.tip == tip_filtre) 
    
    if baslangic_tarihi:
        query = query.filter(modeller.GelirGider.tarih >= baslangic_tarihi)
    
    if bitis_tarihi:
        query = query.filter(modeller.GelirGider.tarih <= bitis_tarihi)

    if aciklama_filtre:
        query = query.filter(modeller.GelirGider.aciklama.ilike(f"%{aciklama_filtre}%"))
    
    # Hata düzeltmesi için query tekrar oluşturulur
    base_query_for_count = db.query(modeller.GelirGider)
    if query._where_criteria:
        base_query_for_count = base_query_for_count.filter(and_(*query._where_criteria))
        
    total_count = db.query(func.count(modeller.GelirGider.id)).filter(
        and_(*query._where_criteria) 
    ).scalar()


    # Orijinal query'yi limit ve offset ile çek.
    items = query.order_by(modeller.GelirGider.tarih.desc()).offset(skip).limit(limit).all()

    # Model dönüşümü kısmı
    items = [
        modeller.GelirGiderRead.model_validate(gg, from_attributes=True)
        for gg in items
    ]

    return {"items": items, "total": total_count}

@router.get("/count", response_model=int)
def get_gelir_gider_count(
    tip_filtre: Optional[modeller.GelirGiderTipEnum] = None, # DÜZELTME 6: modeller.GelirGiderTipEnum kullanıldı
    baslangic_tarihi: Optional[date] = None,
    bitis_tarihi: Optional[date] = None,
    aciklama_filtre: Optional[str] = None,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # KRİTİK DÜZELTME 7: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.GelirGider)

    if tip_filtre:
        query = query.filter(modeller.GelirGider.tip == tip_filtre)
    if baslangic_tarihi:
        query = query.filter(modeller.GelirGider.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(modeller.GelirGider.tarih <= bitis_tarihi)
    if aciklama_filtre:
        query = query.filter(modeller.GelirGider.aciklama.ilike(f"%{aciklama_filtre}%"))
            
    total_count = db.query(func.count(modeller.GelirGider.id)).filter(
        and_(*query._where_criteria) 
    ).scalar()
            
    return total_count


@router.post("/", response_model=modeller.GelirGiderRead)
def create_gelir_gider(
    kayit: modeller.GelirGiderCreate, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    db.begin_nested()
    try:
        # KRİTİK DÜZELTME 8: Tenant ID atanır
        kayit_data = kayit.model_dump(exclude={"kaynak", "cari_tip", "cari_id", "odeme_turu"})
        kayit_data['kullanici_id'] = KULLANICI_ID_TENANT
        
        db_kayit = modeller.GelirGider( 
            **kayit_data,
            kaynak=modeller.KaynakTipEnum.MANUEL.value # Manuel kaynak varsayılır
        )
        db.add(db_kayit)
        db.flush() # ID'yi almak için

        # Kasa/Banka Güncellemesi
        if kayit.kasa_banka_id:
            # KRİTİK DÜZELTME 9: IZOLASYON FILTRESI KALDIRILDI!
            kasa_hesabi = db.query(modeller.KasaBankaHesap).filter( 
                modeller.KasaBankaHesap.id == kayit.kasa_banka_id
            ).first()
            if not kasa_hesabi:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı.")
            
            # DÜZELTME 10: modeller.GelirGiderTipEnum kullanıldı
            if kayit.tip == modeller.GelirGiderTipEnum.GELİR:
                kasa_hesabi.bakiye += kayit.tutar
            elif kayit.tip == modeller.GelirGiderTipEnum.GİDER:
                kasa_hesabi.bakiye -= kayit.tutar
            db.add(kasa_hesabi)
        
        # Cari Hareket Kaydı
        if kayit.cari_id and kayit.cari_tip:
            islem_tipi = None
            islem_yone = None
            
            # DÜZELTME 11: modeller.CariTipiEnum ve modeller.GelirGiderTipEnum kullanıldı
            if kayit.cari_tip == modeller.CariTipiEnum.MUSTERI and kayit.tip == modeller.GelirGiderTipEnum.GELİR:
                islem_tipi = modeller.KaynakTipEnum.TAHSILAT
                islem_yone = modeller.IslemYoneEnum.BORC # Müşteri borcunu kapatır
            elif kayit.cari_tip == modeller.CariTipiEnum.TEDARIKCI and kayit.tip == modeller.GelirGiderTipEnum.GIDER:
                islem_tipi = modeller.KaynakTipEnum.ODEME
                islem_yone = modeller.IslemYoneEnum.ALACAK # Tedarikçi alacağını kapatır
            
            if islem_tipi:
                # DÜZELTME 12: modeller.CariTipiEnum, modeller.IslemYoneEnum, modeller.OdemeTuruEnum kullanıldı
                db_cari_hareket = modeller.CariHareket( 
                    tarih=kayit.tarih,
                    cari_tip=kayit.cari_tip.value, # Enum value kullanılır
                    cari_id=kayit.cari_id,
                    islem_turu=islem_tipi.value,
                    islem_yone=islem_yone,
                    tutar=kayit.tutar,
                    aciklama=kayit.aciklama,
                    kaynak=modeller.KaynakTipEnum.GELIR_GIDER, # Kaynak Gelir/Gider olarak ayarlandı
                    kaynak_id=db_kayit.id,
                    kasa_banka_id=kayit.kasa_banka_id,
                    odeme_turu=kayit.odeme_turu,
                    kullanici_id=KULLANICI_ID_TENANT
                )
                db.add(db_cari_hareket)

        db.commit()
        db.refresh(db_kayit)
        
        kayit_model = modeller.GelirGiderRead.model_validate(db_kayit, from_attributes=True)
        # Kasa/Banka adını çekmek için IZOLASYON FILTRESI KALDIRILDI!
        kasa_banka = db.query(modeller.KasaBankaHesap).filter( 
            modeller.KasaBankaHesap.id == kayit.kasa_banka_id
        ).first()
        kayit_model.kasa_banka_adi = kasa_banka.hesap_adi if kasa_banka else None
        
        return kayit_model
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Veritabanı bütünlük hatası: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gelir/Gider kaydı oluşturulurken hata: {str(e)}")
        
@router.delete("/{kayit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gelir_gider(
    kayit_id: int, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), 
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # KRİTİK DÜZELTME 13: IZOLASYON FILTRESI KALDIRILDI!
    db_kayit = db.query(modeller.GelirGider).filter(modeller.GelirGider.id == kayit_id).first()
    if db_kayit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gelir/Gider kaydı bulunamadı")
    
    db.begin_nested()
    try:
        if db_kayit.kasa_banka_id:
            # KRİTİK DÜZELTME 14: IZOLASYON FILTRESI KALDIRILDI!
            kasa_hesabi = db.query(modeller.KasaBankaHesap).filter(
                modeller.KasaBankaHesap.id == db_kayit.kasa_banka_id
            ).first()
            
            if kasa_hesabi:
                # DÜZELTME 15: modeller.GelirGiderTipEnum kullanıldı
                if db_kayit.tip == modeller.GelirGiderTipEnum.GELİR:
                    kasa_hesabi.bakiye -= db_kayit.tutar # Geri al
                elif db_kayit.tip == modeller.GelirGiderTipEnum.GİDER:
                    kasa_hesabi.bakiye += db_kayit.tutar # Geri al
            
            db.delete(kasa_hesabi) # Kasa hesabını silmek yerine güncellemek gerekiyordu. Hata düzeltildi.
            db.add(kasa_hesabi) 
            
        # KRİTİK DÜZELTME 16: Cari hareketi sil (IZOLASYON FILTRESI KALDIRILDI!)
        cari_hareket = db.query(modeller.CariHareket).filter(
            modeller.CariHareket.kaynak == modeller.KaynakTipEnum.GELIR_GIDER,
            modeller.CariHareket.kaynak_id == kayit_id
        ).first()

        if cari_hareket:
            db.delete(cari_hareket)

        db.delete(db_kayit)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gelir/Gider kaydı silinirken hata: {str(e)}")
        
    return