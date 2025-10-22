# api/rotalar/superadmin.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import date, timedelta
from typing import List

from .. import modeller, guvenlik
from ..veritabani import get_master_db
from ..guvenlik import get_current_user_superadmin # SADECE SUPERADMIN YETKİ KONTROLÜ İÇİN

# Loglama ayarı
import logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/superadmin",
    tags=["SUPERADMIN Yönetimi"],
    dependencies=[Depends(guvenlik.get_current_user_superadmin)], # TÜM ROTLAR SUPERADMIN KORUMALI
)

@router.get("/firmalar", response_model=List[modeller.FirmaRead], summary="Sistemdeki tüm firmaları (Tenant'ları) listele")
def list_all_firms(db: Session = Depends(get_master_db)):
    """
    Tüm firmaları lisans durumları ile birlikte listeler.
    """
    firms = db.query(modeller.Firma).all()
    
    # Lisans süresi dolanları otomatik güncelle
    bugün = date.today()
    for firma in firms:
        if firma.lisans_bitis_tarihi < bugün and firma.lisans_durum not in [modeller.LisansDurumEnum.ASKIDA, modeller.LisansDurumEnum.SURESI_BITMIS]:
            firma.lisans_durum = modeller.LisansDurumEnum.SURESI_BITMIS
            # commit işlemi toplu yapılabilir veya tek tek loglanabilir
    
    # Güncelleme sonrası commit et
    db.commit() 
    
    return [modeller.FirmaRead.model_validate(f, from_attributes=True) for f in firms]

@router.post("/lisans-uzat", response_model=modeller.FirmaRead, summary="Bir firmanın lisansını uzatır veya yeni lisans başlatır")
def extend_license(
    firma_id: int, 
    gun_ekle: int = Query(..., gt=0, description="Lisansa eklenecek gün sayısı"), 
    db: Session = Depends(get_master_db)
):
    """
    Belirtilen firma ID'sine belirtilen gün sayısını ekler.
    Lisans bitiş tarihi geçmişse, bugün + gün_ekle olarak yeni bir lisans başlatır.
    """
    firma = db.query(modeller.Firma).filter(modeller.Firma.id == firma_id).first()
    if not firma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firma bulunamadı.")
    
    bugün = date.today()
    
    # Lisans bitiş tarihi bugün veya geçmişse, başlangıcı bugünden başlat
    if firma.lisans_bitis_tarihi <= bugün:
        yeni_baslangic = bugün
        yeni_bitis = yeni_baslangic + timedelta(days=gun_ekle)
    else:
        # Lisans hala aktifse, bitiş tarihine gün ekle
        yeni_baslangic = firma.lisans_baslangic_tarihi # Başlangıç tarihi değişmez
        yeni_bitis = firma.lisans_bitis_tarihi + timedelta(days=gun_ekle)

    firma.lisans_baslangic_tarihi = yeni_baslangic
    firma.lisans_bitis_tarihi = yeni_bitis
    firma.lisans_durum = modeller.LisansDurumEnum.AKTIF # Lisans uzatıldığı için AKTIF yapılır

    try:
        db.commit()
        db.refresh(firma)
    except Exception as e:
        db.rollback()
        logger.error(f"Lisans uzatma sırasında hata: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Veritabanı hatası.")

    return modeller.FirmaRead.model_validate(firma, from_attributes=True)

@router.put("/{firma_id}/durum-degistir", response_model=modeller.FirmaRead, summary="Firmanın lisans durumunu (AKTIF/ASKIDA/SURESI_BITMIS) değiştirir.")
def change_license_status(
    firma_id: int, 
    yeni_durum: modeller.LisansDurumEnum = Query(..., description="Firma için yeni lisans durumu"), 
    db: Session = Depends(get_master_db)
):
    """
    SUPERADMIN bir firmanın durumunu (Aktif, Askıda, Süresi Bitmiş) manuel olarak değiştirir.
    """
    firma = db.query(modeller.Firma).filter(modeller.Firma.id == firma_id).first()
    if not firma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firma bulunamadı.")

    eski_durum = firma.lisans_durum
    firma.lisans_durum = yeni_durum
    
    try:
        db.commit()
        db.refresh(firma)
    except Exception as e:
        db.rollback()
        logger.error(f"Firma durumu değiştirilirken hata: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Veritabanı hatası.")

    logger.info(f"Firma (ID: {firma_id}) durumu SUPERADMIN tarafından {eski_durum} -> {yeni_durum} olarak değiştirildi.")
    return modeller.FirmaRead.model_validate(firma, from_attributes=True)

@router.get("/{firma_id}/detay", summary="Bir firmanın detaylı lisans, kullanıcı ve istatistik bilgilerini döndürür.")
def get_firma_details(firma_id: int, db: Session = Depends(get_master_db)):
    """
    SUPERADMIN'in firma detaylarını görmesini sağlar. Kullanıcı sayısı gibi temel metrikleri de içerir.
    """
    firma = db.query(modeller.Firma).filter(modeller.Firma.id == firma_id).first()
    if not firma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firma bulunamadı.")
        
    # Firmaya ait kullanıcı sayısı (Master DB'den)
    kullanici_sayisi = db.query(func.count(modeller.Kullanici.id)).filter(
        modeller.Kullanici.firma_id == firma_id
    ).scalar()
    
    bugün = date.today()
    kalan_gun = (firma.lisans_bitis_tarihi - bugün).days

    return {
        "firma_detay": modeller.FirmaRead.model_validate(firma, from_attributes=True),
        "kalan_gun": kalan_gun,
        "kullanici_sayisi": kullanici_sayisi,
        "istatistikler": "TODO: Tenant DB'den fatura/stok sayıları gibi detaylar çekilecek."
    }