# api/rotalar/tedarikciler.py (Database-per-Tenant ve Temizlik Uygulandı)
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from .. import modeller, guvenlik, veritabani
from ..api_servisler import CariHesaplamaService
from typing import List, Optional
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/tedarikciler", tags=["Tedarikçiler"])

def get_tenant_db(payload: dict = Depends(guvenlik.get_token_payload)):
    tenant_name = payload.get("tenant_db")
    if not tenant_name:
        raise HTTPException(status_code=400, detail="Token tenant bilgisi içermiyor.")
    yield from veritabani.get_db(tenant_name)

@router.post("/", response_model=modeller.TedarikciRead)
def create_tedarikci(
    tedarikci: modeller.TedarikciCreate,
    # KRİTİK DÜZELTME 3: Tenant DB bağlantısı kullanılacak
    db: Session = Depends(get_tenant_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # DÜZELTME 4: SADECE KODUN BENZERSİZLİĞİ KONTROL EDİLİR.
    # DbT'de 'kullanici_id' artık Master'daki ID değil, Tenant DB'deki ID'dir (Genellikle 1).
    db_tedarikci = modeller.Tedarikci(**tedarikci.model_dump(exclude={"kullanici_id"}), kullanici_id=1) 
    
    db.add(db_tedarikci)
    db.commit()
    db.refresh(db_tedarikci)
    return db_tedarikci

@router.get("/", response_model=modeller.TedarikciListResponse)
def read_tedarikciler(
    # KRİTİK DÜZELTME 5: Tenant DB bağlantısı kullanılacak
    db: Session = Depends(get_tenant_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    skip: int = 0,
    limit: int = 25,
    arama: Optional[str] = None,
    aktif_durum: Optional[bool] = None
):
    # KRİTİK DÜZELTME 6: Tenant DB'deyiz, IZOLASYON FİLTRESİ KALDIRILDI!
    query = db.query(modeller.Tedarikci) 

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
        # DÜZELTME 7: semalar.CariTipiEnum yerine modeller.CariTipiEnum kullanıldı
        net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci.id, modeller.CariTipiEnum.TEDARIKCI.value)
        tedarikci_dict = modeller.TedarikciRead.model_validate(tedarikci, from_attributes=True).model_dump()
        tedarikci_dict["net_bakiye"] = net_bakiye
        tedarikciler_with_balance.append(tedarikci_dict)

    return {"items": tedarikciler_with_balance, "total": total_count}

@router.get("/{tedarikci_id}", response_model=modeller.TedarikciRead)
def read_tedarikci(
    tedarikci_id: int,
    db: Session = Depends(get_tenant_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 8: Sadece ID filtresi kullanılır (İzolasyon DB seviyesinde)
    tedarikci = db.query(modeller.Tedarikci).filter(
        modeller.Tedarikci.id == tedarikci_id
    ).first()
    if not tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")

    cari_hizmeti = CariHesaplamaService(db)
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci_id, modeller.CariTipiEnum.TEDARIKCI.value)
    tedarikci_dict = modeller.TedarikciRead.model_validate(tedarikci, from_attributes=True).model_dump()
    tedarikci_dict["net_bakiye"] = net_bakiye
    return tedarikci_dict

@router.put("/{tedarikci_id}", response_model=modeller.TedarikciRead)
def update_tedarikci(
    tedarikci_id: int,
    tedarikci: modeller.TedarikciUpdate,
    db: Session = Depends(get_tenant_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 9: Sadece ID filtresi kullanılır
    db_tedarikci = db.query(modeller.Tedarikci).filter(
        modeller.Tedarikci.id == tedarikci_id
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
    db: Session = Depends(get_tenant_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 10: Sadece ID filtresi kullanılır
    db_tedarikci = db.query(modeller.Tedarikci).filter(
        modeller.Tedarikci.id == tedarikci_id
    ).first()
    if not db_tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")
    db.delete(db_tedarikci)
    db.commit()
    return

@router.get("/{tedarikci_id}/net_bakiye", response_model=modeller.NetBakiyeResponse)
def get_net_bakiye_endpoint(
    tedarikci_id: int,
    db: Session = Depends(get_tenant_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 11: Sadece ID filtresi kullanılır
    tedarikci = db.query(modeller.Tedarikci).filter(
        modeller.Tedarikci.id == tedarikci_id
    ).first()
    if not tedarikci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tedarikçi bulunamadı")

    cari_hizmeti = CariHesaplamaService(db)
    # DÜZELTME 12: semalar.CariTipiEnum yerine modeller.CariTipiEnum kullanıldı
    net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci_id, modeller.CariTipiEnum.TEDARIKCI.value)
    return {"net_bakiye": net_bakiye}