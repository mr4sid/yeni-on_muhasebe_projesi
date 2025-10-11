# api/rotalar/kullanicilar.py dosyasının TAMAMI (DbT Master İzolasyonu Uygulandı)
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from .. import modeller
from ..veritabani import get_master_db # MASTER DB bağlantısı kullanılır
from ..guvenlik import get_current_user, get_password_hash # get_password_hash eklendi

router = APIRouter(prefix="/kullanicilar", tags=["Personel Yönetimi"]) # Tag ismi değiştirildi

@router.get("/", response_model=modeller.KullaniciListResponse)
def read_personeller(
    skip: int = 0, 
    limit: int = 1000, 
    current_user: modeller.KullaniciRead = Depends(get_current_user), # JWT ile yetkilendirme
    db: Session = Depends(get_master_db) # Master DB kullanılır
):
    # KRİTİK İZOLASYON: Sadece kullanıcının ait olduğu firmadaki personelleri göster
    if not current_user.firma_id:
        # Kurucu Master admin hesabı için (eğer firma_id null ise)
        query = db.query(modeller.Kullanici)
    else:
        query = db.query(modeller.Kullanici).filter(modeller.Kullanici.firma_id == current_user.firma_id)
        
    # Firma adını okumak için Firma ilişkisini yüklüyoruz.
    query = query.options(joinedload(modeller.Kullanici.firma))
    
    total_count = query.count()
    kullanicilar = query.offset(skip).limit(limit).all()
    
    # Pydantic'e dönüştürürken firma_adi eklenir
    items = []
    for k in kullanicilar:
        k_read = modeller.KullaniciRead.model_validate(k, from_attributes=True)
        if k.firma:
            k_read.firma_adi = k.firma.firma_adi
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
    db: Session = Depends(get_master_db)
):
    # KRİTİK İZOLASYON: Personel, sadece kendi firmasına ait personeli çekebilir
    query_filter = [modeller.Kullanici.id == personel_id]
    if current_user.firma_id:
        query_filter.append(modeller.Kullanici.firma_id == current_user.firma_id)
    
    kullanici = db.query(modeller.Kullanici).options(
        joinedload(modeller.Kullanici.firma)
    ).filter(*query_filter).first()
    
    if not kullanici:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personel bulunamadı")
        
    k_read = modeller.KullaniciRead.model_validate(kullanici, from_attributes=True)
    if kullanici.firma:
        k_read.firma_adi = kullanici.firma.firma_adi
        
    return k_read

@router.put("/{personel_id}", response_model=modeller.KullaniciRead)
def update_personel(
    personel_id: int, 
    personel: modeller.KullaniciUpdate, 
    current_user: modeller.KullaniciRead = Depends(get_current_user),
    db: Session = Depends(get_master_db)
):
    # KRİTİK İZOLASYON: Güncelleme de sadece kendi firması içinde yapılabilir
    db_kullanici = db.query(modeller.Kullanici).filter(
        modeller.Kullanici.id == personel_id,
        modeller.Kullanici.firma_id == current_user.firma_id
    ).first()
    
    if not db_kullanici:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personel bulunamadı veya bu firmanın personeli değil")

    update_data = personel.model_dump(exclude_unset=True)
    
    # Şifre varsa hashle
    if 'sifre' in update_data and update_data['sifre']:
        update_data['sifre_hash'] = get_password_hash(update_data['sifre'])
        del update_data['sifre']
        
    for key, value in update_data.items():
        setattr(db_kullanici, key, value)
        
    db.commit()
    db.refresh(db_kullanici)
    
    # Response modelini oluştur ve firma adını ekle
    k_read = modeller.KullaniciRead.model_validate(db_kullanici, from_attributes=True)
    if db_kullanici.firma:
        k_read.firma_adi = db_kullanici.firma.firma_adi
        
    return k_read

@router.delete("/{personel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_personel(
    personel_id: int, 
    current_user: modeller.KullaniciRead = Depends(get_current_user),
    db: Session = Depends(get_master_db)
):
    # KRİTİK KONTROL: Kurucu personel (firma_id'si kurucu_personel_id'ye eşit olan) silinemez.
    if current_user.firma_id and current_user.firma_id == personel_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Kurucu personel silinemez.")

    db_kullanici = db.query(modeller.Kullanici).filter(
        modeller.Kullanici.id == personel_id,
        modeller.Kullanici.firma_id == current_user.firma_id
    ).first()
    
    if not db_kullanici:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personel bulunamadı")
        
    db.delete(db_kullanici)
    db.commit()
    return {"message": "Personel başarıyla silindi"}