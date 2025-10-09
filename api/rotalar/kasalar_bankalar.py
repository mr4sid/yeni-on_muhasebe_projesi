# api/rotalar/kasalar_bankalar.py (TAMAMI)
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import semalar, modeller
from ..veritabani import get_db
from datetime import date
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .. import guvenlik

router = APIRouter(
    prefix="/kasalar_bankalar",
    tags=["Kasa ve Banka Hesapları"]
)

@router.get("/", response_model=modeller.KasaBankaListResponse)
def read_kasalar_bankalar(
    skip: int = 0,
    limit: int = 100,
    arama: Optional[str] = None,
    tip: Optional[semalar.KasaBankaTipiEnum] = None,
    aktif_durum: Optional[bool] = None,
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user), # Güvenli kullanıcı kimliği eklendi
    db: Session = Depends(get_db)
):
    query = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.kullanici_id == current_user.id)

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
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user), # Güvenli kullanıcı kimliği eklendi
    db: Session = Depends(get_db)
):
    try:
        db_hesap = modeller.KasaBankaHesap(
            **hesap.model_dump(exclude_unset=True, exclude={'acilis_bakiyesi'}),
            kullanici_id=current_user.id # Kullanıcı ID'si doğrudan token'dan alındı
        )
        if hasattr(hesap, 'acilis_bakiyesi') and hesap.acilis_bakiyesi is not None:
             db_hesap.bakiye = hesap.acilis_bakiyesi

        db.add(db_hesap)
        db.flush() 

        # Cari hareket oluşturma işlemi
        if hasattr(hesap, 'acilis_bakiyesi') and hesap.acilis_bakiyesi > 0:
            # KRİTİK DÜZELTME: semalar yerine modeller kullanıldı
            db_cari_hareket = modeller.CariHareket(
                tarih=date.today(),
                cari_turu="KASA_BANKA",
                cari_id=db_hesap.id,
                islem_turu="TAHSILAT",
                islem_yone=modeller.IslemYoneEnum.ALACAK,
                tutar=hesap.acilis_bakiyesi,
                aciklama="Açılış Bakiyesi",
                kaynak=modeller.KaynakTipEnum.MANUEL, # Açılış bakiyesi manuel bir harekettir.
                kasa_banka_id=db_hesap.id,
                kullanici_id=current_user.id # Kullanıcı ID'si doğrudan token'dan alındı
            )
            db.add(db_cari_hareket)
            
        db.commit()
        db.refresh(db_hesap)
        return db_hesap
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Veritabanı bütünlük hatası: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Veritabanı işlemi sırasında hata oluştu: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Kasa/Banka hesabı oluşturulurken beklenmedik bir hata oluştu: {str(e)}")
            
@router.put("/{hesap_id}", response_model=modeller.KasaBankaRead)
def update_kasa_banka(
    hesap_id: int, 
    hesap: modeller.KasaBankaUpdate, 
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user), # Güvenli kullanıcı kimliği eklendi
    db: Session = Depends(get_db)
):
    db_hesap = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.id == hesap_id, modeller.KasaBankaHesap.kullanici_id == current_user.id).first() # Sorgu güncellendi
    if db_hesap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı")
    
    hesap_data = hesap.model_dump(exclude_unset=True)
    for key, value in hesap_data.items():
        setattr(db_hesap, key, value)
    
    db.commit()
    db.refresh(db_hesap)
    return db_hesap

@router.delete("/{hesap_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kasa_banka(
    hesap_id: int, 
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user), # Güvenli kullanıcı kimliği eklendi
    db: Session = Depends(get_db)
):
    db_hesap = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.id == hesap_id, modeller.KasaBankaHesap.kullanici_id == current_user.id).first() # Sorgu güncellendi
    if db_hesap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kasa/Banka hesabı bulunamadı")
    
    hareketler = db.query(modeller.CariHareket).filter(modeller.CariHareket.kasa_banka_id == hesap_id, modeller.CariHareket.kullanici_id == current_user.id).first() # Sorgu güncellendi
    if hareketler:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu kasa/banka hesabına bağlı hareketler olduğu için silinemez.")

    db.delete(db_hesap)
    db.commit()
    return