# api/rotalar/superadmin.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload, sessionmaker
from sqlalchemy import func, text, create_engine
from datetime import date, timedelta
from typing import List
from .. import modeller, guvenlik
from ..modeller import Fatura, Musteri, Stok
from ..config import settings
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
    Tüm firmaları lisans durumları ve kurucu iletişim bilgileri ile birlikte listeler.
    """
    logger.info("Firma listesi sorgulanıyor (kurucu bilgileriyle birlikte)...")
    try:
        # GÜNCELLEME: Firma sorgusuna kurucu kullanıcıyı (Kullanici) join et
        firms = db.query(modeller.Firma).options(
            joinedload(modeller.Firma.kurucu_personel) # 'kurucu_personel' ilişkisini yükle
        ).all()
        logger.info(f"{len(firms)} adet firma bulundu.")
    except Exception as e:
        logger.error(f"Firma sorgulama hatası: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Veritabanı sorgu hatası: {e}")

    # Lisans süresi dolanları otomatik güncelle
    bugün = date.today()
    lisans_guncellendi = False
    for firma in firms:
        if firma.lisans_bitis_tarihi < bugün and firma.lisans_durum not in [modeller.LisansDurumEnum.ASKIDA, modeller.LisansDurumEnum.SURESI_BITMIS]:
            firma.lisans_durum = modeller.LisansDurumEnum.SURESI_BITMIS
            lisans_guncellendi = True

    if lisans_guncellendi:
        try:
            db.commit()
            logger.info("Lisans durumları güncellendi.")
        except Exception as e:
            db.rollback()
            logger.error(f"Lisans durumu güncellenirken hata: {e}")

    # GÜNCELLEME: Pydantic modeli artık ilişkili veriyi (kurucu_personel) otomatik olarak işleyecek
    return [modeller.FirmaRead.model_validate(f, from_attributes=True) for f in firms]

@router.post("/{firma_id}/lisans-uzat", response_model=modeller.FirmaRead, summary="Bir firmanın lisansını uzatır veya yeni lisans başlatır")
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

@router.get("/{firma_id}/istatistikler", summary="Firma İstatistikleri")
def firma_istatistikleri(
    firma_id: int,
    db: Session = Depends(get_master_db), # Ana DB session'ı
    current_user: dict = Depends(get_current_user_superadmin) # Yetki kontrolü
):
    """
    Belirtilen firmanın istatistiklerini döndürür.
    Tenant DB'ye bağlanarak fatura, müşteri, stok sayılarını ve toplam ciroyu hesaplar.
    """
    # Firmayı ana DB'den bul
    firma = db.query(modeller.Firma).filter(modeller.Firma.id == firma_id).first()
    if not firma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firma bulunamadı")

    # Tenant DB'ye bağlanmak için .env'den yüklenen ayarları kullan
    try:
        # --- GÜNCELLENMİŞ KOD BAŞLANGICI ---
        # Ayarları settings nesnesinden çek
        DB_USER = settings.DB_USER
        DB_PASSWORD = settings.DB_PASSWORD
        DB_HOST = settings.DB_HOST
        DB_PORT = settings.DB_PORT
        TENANT_DB_NAME = firma.db_adi # Firma nesnesinden tenant DB adını al

        # Bağlantı string'ini dinamik olarak oluştur
        tenant_db_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{TENANT_DB_NAME}"
        # --- GÜNCELLENMİŞ KOD SONU ---

        tenant_engine = create_engine(tenant_db_url)
        TenantSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
        tenant_db = TenantSessionLocal() # Yeni tenant session'ı başlat

        try:
            # İstatistikleri hesapla (Tenant DB üzerinde)
            fatura_sayisi = tenant_db.query(Fatura).count()
            musteri_sayisi = tenant_db.query(Musteri).count()
            stok_sayisi = tenant_db.query(Stok).count()

            # Toplam ciro (Fatura modelindeki 'genel_toplam' alanını kullandık)
            toplam_ciro = tenant_db.query(func.sum(Fatura.genel_toplam)).scalar() or 0.0

            return {
                "firma_id": firma_id,
                "firma_adi": firma.unvan,
                "fatura_sayisi": fatura_sayisi,
                "musteri_sayisi": musteri_sayisi,
                "stok_sayisi": stok_sayisi,
                "toplam_ciro": float(toplam_ciro)
            }
        except Exception as tenant_query_error:
            logger.error(f"Tenant DB ({firma.db_adi}) sorgulama hatası: {tenant_query_error}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"İstatistikler hesaplanırken hata oluştu: {tenant_query_error}")
        finally:
            tenant_db.close() # Tenant session'ını kapat

    except Exception as connection_error:
        logger.error(f"Tenant DB ({firma.db_adi}) bağlantı hatası: {connection_error}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Firma veritabanına bağlanılamadı.")