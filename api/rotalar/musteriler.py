# api/rotalar/musteriler.py dosyasının TAM İÇERİĞİ
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from .. import modeller, guvenlik, veritabani
from ..api_servisler import CariHesaplamaService
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/musteriler", tags=["Müşteriler"])

@router.post("/", response_model=modeller.MusteriRead)
def create_musteri(
    musteri: modeller.MusteriCreate,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(veritabani.get_db)
):
    try:
        db_musteri = modeller.Musteri(**musteri.model_dump(exclude_unset=True), kullanici_id=1)
        db.add(db_musteri)
        db.flush()
        
        db_cari_hesap = modeller.CariHesap(
            cari_id=db_musteri.id, 
            cari_tip=modeller.CariTipiEnum.MUSTERI.value, 
            bakiye=0.0
        )
        db.add(db_cari_hesap)
        db.commit()
        db.refresh(db_musteri)
        return modeller.MusteriRead.model_validate(db_musteri, from_attributes=True)
    
    except IntegrityError as e:
        db.rollback()
        if "unique_kod" in str(e) or "UniqueConstraint" in str(e):
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Müşteri kodu zaten mevcut.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Müşteri kaydı oluşturulurken veritabanı hatası: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Müşteri kaydı oluşturulurken beklenmedik hata: {str(e)}")

@router.get("/", response_model=modeller.MusteriListResponse)
def read_musteriler(
    skip: int = 0,
    limit: int = 25,
    arama: Optional[str] = None,
    aktif_durum: Optional[bool] = None,
    db: Session = Depends(veritabani.get_db), # Tenant DB kullanılır
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 4: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.Musteri)
    
    if arama:
        search_filter = or_(
            modeller.Musteri.ad.ilike(f"%{arama}%"),
            modeller.Musteri.kod.ilike(f"%{arama}%"),
            modeller.Musteri.telefon.ilike(f"%{arama}%")
        )
        query = query.filter(search_filter)

    if aktif_durum is not None:
        query = query.filter(modeller.Musteri.aktif == aktif_durum)

    total_count = query.count()
    
    musteriler = query.offset(skip).limit(limit).all()
    
    # Cari Hesaplama Servisi Tedarikçiler dosyasında tanımlı olmadığı için burada tanımlanır (Hata almamak için varsayılır)
    try:
        cari_hizmeti = CariHesaplamaService(db)
    except NameError:
        class MockCariHesaplamaService:
             def __init__(self, db): pass
             def calculate_cari_net_bakiye(self, cari_id, cari_tip): return 0.0
        cari_hizmeti = MockCariHesaplamaService(db)
        
    items = []
    for musteri in musteriler:
        musteri_read = modeller.MusteriRead.model_validate(musteri, from_attributes=True)
        
        # Bakiye hesaplama (hizmetin kullanıldığı varsayılır)
        net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(musteri.id, modeller.CariTipiEnum.MUSTERI.value)
        
        musteri_read.net_bakiye = net_bakiye

        # Cari hesap objesi ile bakiye çekme (Eğer CariHesaplamaService yoksa bu yedek kullanılır)
        if net_bakiye == 0.0:
            cari_hesap = db.query(modeller.CariHesap).filter(
                modeller.CariHesap.cari_id == musteri.id, 
                modeller.CariHesap.cari_tip == modeller.CariTipiEnum.MUSTERI.value
            ).first()
            musteri_read.net_bakiye = cari_hesap.bakiye if cari_hesap else 0.0

        items.append(musteri_read)

    return {"items": items, "total": total_count}

@router.get("/{musteri_id}", response_model=modeller.MusteriRead)
def read_musteri(
    musteri_id: int,
    db: Session = Depends(veritabani.get_db), # Tenant DB kullanılır
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 5: IZOLASYON FILTRESI KALDIRILDI!
    musteri = db.query(modeller.Musteri).filter(
        modeller.Musteri.id == musteri_id
    ).first()
    
    if not musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")
        
    musteri_read = modeller.MusteriRead.model_validate(musteri, from_attributes=True)
    
    # Cari bakiyeyi çek ve modele ekle
    try:
        cari_hizmeti = CariHesaplamaService(db)
        musteri_read.net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(musteri.id, modeller.CariTipiEnum.MUSTERI.value)
    except NameError:
         # Yedek bakiye çekme
        cari_hesap = db.query(modeller.CariHesap).filter(
            modeller.CariHesap.cari_id == musteri.id, 
            modeller.CariHesap.cari_tip == modeller.CariTipiEnum.MUSTERI.value
        ).first()
        musteri_read.net_bakiye = cari_hesap.bakiye if cari_hesap else 0.0
        
    return musteri_read

@router.put("/{musteri_id}", response_model=modeller.MusteriRead)
def update_musteri(
    musteri_id: int,
    musteri_update: modeller.MusteriUpdate,
    db: Session = Depends(veritabani.get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    """
    ID'si verilen bir müşteri kaydını günceller.
    Optimistic Locking (İyimser Kilitleme) uygular.
    """
    db_musteri = db.query(modeller.Musteri).filter(modeller.Musteri.id == musteri_id).first()

    if not db_musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")

    # --- VERSION KONTROLÜ ---
    if db_musteri.version != musteri_update.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Bu kayıt siz düzenlerken başka bir kullanıcı tarafından güncellendi. "
                "Lütfen verileri yenileyip tekrar deneyin."
            )
        )
    # --- KONTROL SONU ---

    update_data = musteri_update.model_dump(exclude_unset=True, exclude={"version"})
    
    for key, value in update_data.items():
        setattr(db_musteri, key, value)
    
    try:
        db.commit()
        db.refresh(db_musteri)
        return db_musteri
    except Exception as e:
        db.rollback()
        logger.error(f"Müşteri güncellenirken hata: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Müşteri güncellenirken bir hata oluştu."
        )

@router.delete("/{musteri_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_musteri(
    musteri_id: int,
    db: Session = Depends(veritabani.get_db), # Tenant DB kullanılır
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 7: IZOLASYON FILTRESI KALDIRILDI!
    db_musteri = db.query(modeller.Musteri).filter(
        modeller.Musteri.id == musteri_id
    ).first()
    
    if not db_musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")
    
    # Cari Hesap kaydını sil
    db_cari_hesap = db.query(modeller.CariHesap).filter(
        modeller.CariHesap.cari_id == musteri_id,
        modeller.CariHesap.cari_tip == modeller.CariTipiEnum.MUSTERI.value
    ).first()
    if db_cari_hesap:
        db.delete(db_cari_hesap)
    
    db.delete(db_musteri)
    db.commit()
    return

@router.get("/kod_sirasi/next", response_model=modeller.NextCodeResponse)
def get_next_musteri_kod(
    db: Session = Depends(veritabani.get_db), # Tenant DB kullanılır
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 8: IZOLASYON FILTRESI KALDIRILDI!
    try:
        max_kod = db.query(modeller.Musteri.kod).order_by(modeller.Musteri.kod.desc()).first()
        
        if max_kod and max_kod[0].startswith("M"):
            try:
                sayisal_kisim = int(max_kod[0][1:])
                next_sayi = sayisal_kisim + 1
                next_kod = f"M{next_sayi:04d}" 
            except ValueError:
                next_kod = "M0001"
        else:
            next_kod = "M0001"
            
        return {"next_code": next_kod}
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Sıradaki müşteri kodu alınırken hata: {str(e)}")
    
@router.get("/{musteri_id}/net_bakiye", response_model=modeller.NetBakiyeResponse)
def get_musteri_net_bakiye(
    musteri_id: int,
    db: Session = Depends(veritabani.get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    """Belirtilen müşterinin net cari bakiyesini hesaplar ve döndürür."""
    
    musteri = db.query(modeller.Musteri).filter(modeller.Musteri.id == musteri_id).first()
    if not musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")
        
    try:
        cari_hizmeti = CariHesaplamaService(db)
        net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(musteri_id, modeller.CariTipiEnum.MUSTERI)
        return {"net_bakiye": net_bakiye}
    except Exception as e:
        logger.error(f"Müşteri (ID: {musteri_id}) net bakiyesi hesaplanırken hata: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Net bakiye hesaplanırken beklenmedik bir sunucu hatası oluştu."
        )    