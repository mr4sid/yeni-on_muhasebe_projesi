from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional

from .. import modeller, semalar
from ..veritabani import get_db
from ..api_servisler import CariHesaplamaService
from .. import guvenlik

router = APIRouter(prefix="/tedarikciler", tags=["Tedarikçiler"])

@router.post("/", response_model=modeller.TedarikciRead)
def create_tedarikci(
    tedarikci: modeller.TedarikciCreate,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) # DÜZELTME: JWT KURALI
):
    # MODEL TUTARLILIĞI: ORM modeli modeller.Tedarikci kullanıldı.
    db_tedarikci = modeller.Tedarikci(**tedarikci.model_dump(exclude={"kullanici_id"}), kullanici_id=current_user.id)
    db.add(db_tedarikci)
    db.commit()
    db.refresh(db_tedarikci)
    return db_tedarikci

@router.get("/", response_model=modeller.TedarikciListResponse)
def read_tedarikciler(
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # DÜZELTME: JWT KURALI
    skip: int = 0,
    limit: int = 25,
    arama: Optional[str] = None,
    aktif_durum: Optional[bool] = None
):
    # MODEL TUTARLILIĞI: Sorgularda modeller.Tedarikci kullanıldı.
    query = db.query(modeller.Tedarikci).filter(modeller.Tedarikci.kullanici_id == current_user.id)

    if arama:
        search_term = f"%{arama}%"
        query = query.filter(
            or_(
                modeller.Tedarikci.ad.ilike(search_term),
                modeller.Tedarikci.kod.ilike(search_term),
                modeller.Tedarikci.telefon.ilike(search_term),
                modeller.Tedarikci.vergi_no.ilike(search_term)
            )
        )
    
    if aktif_durum is not None:
        query = query.filter(modeller.Tedarikci.aktif == aktif_durum)

    total_count = query.count()
    tedarikciler = query.offset(skip).limit(limit).all()

    cari_hizmeti = CariHesaplamaService(db)
    tedarikciler_with_balance = []
    for tedarikci in tedarikciler:
        # Cari Tipi Enum değeri kullanıldı
        net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci.id, semalar.CariTipiEnum.TEDARIKCI.value)
        # from_attributes=True eklendi
        tedarikci_dict = modeller.TedarikciRead.model_validate(tedarikci, from_attributes=True).model_dump()
        tedarikci_dict["net_bakiye"] = net_bakiye
        tedarikciler_with_balance.append(tedarikci_dict)

    return {"items": tedarikciler_with_balance, "total": total_count}

@router.get("/{tedarikci_id}", response_model=modeller.TedarikciRead)
def read_tedarikci(
    tedarikci_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) # DÜZELTME: JWT KURALI
):
    # MODEL TUTARLILIĞI: Sorgularda modeller.Tedarikci kullanıldı.
    tedarikci = db.query(modeller.Tedarikci).filter(
        modeller.Tedarikci.id == tedarikci_id,
        modeller.Tedarikci.kullanici_id == current_user.id
    ).first()
    if not tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")

    cari_hizmeti = CariHesaplamaService(db)
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci_id, semalar.CariTipiEnum.TEDARIKCI.value)
    tedarikci_dict = modeller.TedarikciRead.model_validate(tedarikci, from_attributes=True).model_dump()
    tedarikci_dict["net_bakiye"] = net_bakiye
    return tedarikci_dict

@router.put("/{tedarikci_id}", response_model=modeller.TedarikciRead)
def update_tedarikci(
    tedarikci_id: int,
    tedarikci: modeller.TedarikciUpdate,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) # DÜZELTME: JWT KURALI
):
    # MODEL TUTARLILIĞI: Sorgularda modeller.Tedarikci kullanıldı.
    db_tedarikci = db.query(modeller.Tedarikci).filter(
        modeller.Tedarikci.id == tedarikci_id,
        modeller.Tedarikci.kullanici_id == current_user.id
    ).first()
    if not db_tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")
    for key, value in tedarikci.model_dump(exclude_unset=True).items():
        setattr(db_tedarikci, key, value)
    db.commit()
    db.refresh(db_tedarikci)
    return db_tedarikci

@router.delete("/{tedarikci_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tedarikci(
    tedarikci_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) # DÜZELTME: JWT KURALI
):
    # MODEL TUTARLILIĞI: Sorgularda modeller.Tedarikci kullanıldı.
    db_tedarikci = db.query(modeller.Tedarikci).filter(
        modeller.Tedarikci.id == tedarikci_id,
        modeller.Tedarikci.kullanici_id == current_user.id
    ).first()
    if not db_tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")
    db.delete(db_tedarikci)
    db.commit()
    return

@router.get("/{tedarikci_id}/net_bakiye", response_model=modeller.NetBakiyeResponse)
def get_net_bakiye_endpoint(
    tedarikci_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) # DÜZELTME: JWT KURALI
):
    # MODEL TUTARLILIĞI: Sorgularda modeller.Tedarikci kullanıldı.
    tedarikci = db.query(modeller.Tedarikci).filter(
        modeller.Tedarikci.id == tedarikci_id,
        modeller.Tedarikci.kullanici_id == current_user.id
    ).first()
    if not tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")

    cari_hizmeti = CariHesaplamaService(db)
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci_id, semalar.CariTipiEnum.TEDARIKCI.value)
    return {"net_bakiye": net_bakiye}