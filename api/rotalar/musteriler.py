from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional

from .. import modeller, semalar
from ..veritabani import get_db
from ..api_servisler import CariHesaplamaService
from .. import guvenlik

router = APIRouter(prefix="/musteriler", tags=["Müşteriler"])

@router.post("/", response_model=modeller.MusteriRead)
def create_musteri(
    musteri: modeller.MusteriCreate, # MODEL TUTARLILIĞI: Pydantic input şeması
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # JWT KURALI
    db: Session = Depends(get_db)
):
    # MODEL KULLANIMI: ORM modeline dönüştürme ve kullanici_id ekleme
    db_musteri = modeller.Musteri(**musteri.model_dump(exclude={"kullanici_id"}), kullanici_id=current_user.id)
    db.add(db_musteri)
    db.commit()
    db.refresh(db_musteri)
    return db_musteri

@router.get("/", response_model=modeller.MusteriListResponse)
def read_musteriler(
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # JWT KURALI
    skip: int = 0,
    limit: int = 25,
    arama: Optional[str] = None,
    aktif_durum: Optional[bool] = None
):
    # MODEL TUTARLILIĞI: Sorgularda modeller.Musteri kullanıldı.
    query = db.query(modeller.Musteri).filter(modeller.Musteri.kullanici_id == current_user.id)

    if arama:
        search_term = f"%{arama}%"
        query = query.filter(
            or_(
                modeller.Musteri.ad.ilike(search_term),
                modeller.Musteri.kod.ilike(search_term),
                modeller.Musteri.telefon.ilike(search_term),
                modeller.Musteri.vergi_no.ilike(search_term)
            )
        )
        
    if aktif_durum is not None:
        query = query.filter(modeller.Musteri.aktif == aktif_durum)

    total_count = query.count()
    musteriler = query.offset(skip).limit(limit).all()

    cari_hizmeti = CariHesaplamaService(db)
    musteriler_with_balance = []
    for musteri in musteriler:
        # Cari bakiye hesaplama mantığı korundu
        net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(musteri.id, semalar.CariTipiEnum.MUSTERI.value)
        # Pydantic'e dönüştürme
        musteri_dict = modeller.MusteriRead.model_validate(musteri, from_attributes=True).model_dump()
        musteri_dict["net_bakiye"] = net_bakiye
        musteriler_with_balance.append(musteri_dict)

    return {"items": musteriler_with_balance, "total": total_count}

@router.get("/{musteri_id}", response_model=modeller.MusteriRead)
def read_musteri(
    musteri_id: int, 
    db: Session = Depends(get_db), 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) # JWT KURALI
):
    # MODEL TUTARLILIĞI: Sorgularda modeller.Musteri kullanıldı.
    musteri = db.query(modeller.Musteri).filter(modeller.Musteri.id == musteri_id, modeller.Musteri.kullanici_id == current_user.id).first()
    if not musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")

    cari_hizmeti = CariHesaplamaService(db)
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(musteri_id, semalar.CariTipiEnum.MUSTERI.value)
    musteri_dict = modeller.MusteriRead.model_validate(musteri, from_attributes=True).model_dump()
    musteri_dict["net_bakiye"] = net_bakiye
    return musteri_dict

@router.put("/{musteri_id}", response_model=modeller.MusteriRead)
def update_musteri(
    musteri_id: int, 
    musteri: modeller.MusteriUpdate, 
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) # JWT KURALI
):
    # MODEL TUTARLILIĞI: Sorgularda modeller.Musteri kullanıldı.
    db_musteri = db.query(modeller.Musteri).filter(modeller.Musteri.id == musteri_id, modeller.Musteri.kullanici_id == current_user.id).first()
    if not db_musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")
        
    for key, value in musteri.model_dump(exclude_unset=True).items():
        setattr(db_musteri, key, value)
        
    db.commit()
    db.refresh(db_musteri)
    return db_musteri

@router.delete("/{musteri_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_musteri(
    musteri_id: int, 
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) # JWT KURALI
):
    # MODEL TUTARLILIĞI: Sorgularda modeller.Musteri kullanıldı.
    db_musteri = db.query(modeller.Musteri).filter(modeller.Musteri.id == musteri_id, modeller.Musteri.kullanici_id == current_user.id).first()
    if not db_musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")
    db.delete(db_musteri)
    db.commit()
    return

@router.get("/{musteri_id}/net_bakiye", response_model=modeller.NetBakiyeResponse)
def get_net_bakiye_endpoint(
    musteri_id: int, 
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) # JWT KURALI
):
    # MODEL TUTARLILIĞI: Sorgularda modeller.Musteri kullanıldı.
    musteri = db.query(modeller.Musteri).filter(modeller.Musteri.id == musteri_id, modeller.Musteri.kullanici_id == current_user.id).first()
    if not musteri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müşteri bulunamadı")

    cari_hizmeti = CariHesaplamaService(db)
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(musteri_id, semalar.CariTipiEnum.MUSTERI.value)
    return {"net_bakiye": net_bakiye}