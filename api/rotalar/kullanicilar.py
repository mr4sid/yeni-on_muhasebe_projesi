# api/rotalar/kullanicilar.py dosyasının TAMAMI (DbT Master İzolasyonu Uygulandı)
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from .. import modeller
from ..veritabani import get_master_db, get_db
from ..guvenlik import get_current_user, get_password_hash # get_password_hash eklendi

router = APIRouter(prefix="/kullanicilar", tags=["Personel Yönetimi"]) # Tag ismi değiştirildi

@router.get("/", response_model=modeller.KullaniciListResponse)
def read_personeller(
    skip: int = 0, 
    limit: int = 1000, 
    current_user: modeller.KullaniciRead = Depends(get_current_user),
    db: Session = Depends(get_db) # KRİTİK DÜZELTME: Tenant DB kullanılıyor
):
    # Tenant DB kullanıldığı için firma_id filtresi gerekmez, zaten izole edilmiş durumda.
    query = db.query(modeller.Kullanici)
    
    total_count = query.count()
    kullanicilar = query.offset(skip).limit(limit).all()
    
    items = []
    for k in kullanicilar:
        k_read = modeller.KullaniciRead.model_validate(k, from_attributes=True)
        # Firma bilgisini Pydantic modele JWT'den gelen güncel veri ile doldur
        k_read.firma_adi = current_user.firma_adi
        k_read.firma_no = current_user.firma_no
        k_read.tenant_db_name = current_user.tenant_db_name
        items.append(k_read)
        
    return {"items": items, "total": total_count}

@router.get("/me", response_model=modeller.KullaniciRead)
def read_kullanici_me(current_user: modeller.KullaniciRead = Depends(get_current_user)):
    # Kullanıcının kendi bilgilerini döndürür (Zaten JWT'den Firma bilgisi ile birlikte gelir)
    return current_user

@router.get("/{personel_id}", response_model=modeller.KullaniciRead)
def read_personel(
    personel_id: int, 
    current_user: modeller.KullaniciRead = Depends(get_current_user),
    db: Session = Depends(get_db) # Tenant DB
):
    # Tenant DB'de sadece ID'yi arıyoruz.
    kullanici = db.query(modeller.Kullanici).filter(modeller.Kullanici.id == personel_id).first()
    
    if not kullanici:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personel bulunamadı")
        
    k_read = modeller.KullaniciRead.model_validate(kullanici, from_attributes=True)
    
    # KRİTİK DÜZELTME: Pydantic modeldeki alanlara sadece current_user'daki Pydantic alanlarını güvenli atıyoruz.
    # Eğer current_user.firma_adi yoksa, None atanır, program çökmez.
    k_read.firma_adi = getattr(current_user, 'firma_adi', None)
    k_read.firma_no = getattr(current_user, 'firma_no', None)
    k_read.tenant_db_name = getattr(current_user, 'tenant_db_name', None)
        
    return k_read

@router.put("/{personel_id}", response_model=modeller.KullaniciRead)
def update_personel(
    personel_id: int, 
    personel: modeller.KullaniciUpdate, 
    current_user: modeller.KullaniciRead = Depends(get_current_user),
    db: Session = Depends(get_db) # Tenant DB
):
    # Tenant DB'de sadece ID'ye göre filtrele.
    db_kullanici = db.query(modeller.Kullanici).filter(
        modeller.Kullanici.id == personel_id
    ).first()
    
    if not db_kullanici:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personel bulunamadı")

    update_data = personel.model_dump(exclude_unset=True)
    
    # Şifre varsa hashle
    if 'sifre' in update_data and update_data['sifre']:
        update_data['sifre_hash'] = get_password_hash(update_data['sifre'])
        del update_data['sifre']
        
    for key, value in update_data.items():
        setattr(db_kullanici, key, value)
        
    db.commit()
    db.refresh(db_kullanici)
    
    # Response modelini oluştur ve firma adını/nosunu ekle
    k_read = modeller.KullaniciRead.model_validate(db_kullanici, from_attributes=True)
    # KRİTİK DÜZELTME: Pydantic modeldeki alanlara sadece current_user'daki Pydantic alanlarını güvenli atıyoruz.
    k_read.firma_adi = getattr(current_user, 'firma_adi', None)
    k_read.firma_no = getattr(current_user, 'firma_no', None)
        
    return k_read

@router.delete("/{personel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_personel(
    personel_id: int, 
    current_user: modeller.KullaniciRead = Depends(get_current_user),
    db: Session = Depends(get_db) # KRİTİK DÜZELTME: Tenant DB kullanılıyor
):
    # Tenant DB'de sadece ID'ye göre filtrele.
    db_kullanici = db.query(modeller.Kullanici).filter(
        modeller.Kullanici.id == personel_id
    ).first()
    
    if not db_kullanici:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personel bulunamadı")
        
    db.delete(db_kullanici)
    db.commit()
    return {"message": "Personel başarıyla silindi"}