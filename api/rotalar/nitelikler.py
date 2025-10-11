# api/rotalar/nitelikler.py (Database-per-Tenant ve Tam Temizlik Uygulandı)
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from .. import modeller, guvenlik # DÜZELTME 1: semalar kaldırıldı
# KRİTİK DÜZELTME 2: Tenant DB'ye dinamik bağlanacak yeni bağımlılık kullanıldı.
from ..veritabani import get_db as get_tenant_db 
from typing import List, Optional, Union

router = APIRouter(prefix="/nitelikler", tags=["Nitelikler"])

# KRİTİK DÜZELTME 3: Tenant DB bağlantısı için kullanılacak bağımlılık
TENANT_DB_DEPENDENCY = get_tenant_db

# Kategori endpointleri
@router.post("/kategoriler/", response_model=modeller.UrunKategoriRead)
def create_kategori(
    kategori: modeller.UrunKategoriCreate, 
    db: Session = Depends(TENANT_DB_DEPENDENCY), # Tenant DB kullanılır
    current_user=Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 4: modeller.UrunKategori kullanıldı ve kullanici_id=1 atandı.
    db_kategori = modeller.UrunKategori(**kategori.model_dump(), kullanici_id=1) 
    db.add(db_kategori)
    db.commit()
    db.refresh(db_kategori)
    return db_kategori

@router.get("/kategoriler", response_model=modeller.NitelikListResponse)
def read_kategoriler(
    skip: int = 0,
    limit: int = 1000,
    arama: str = Query(None),
    db: Session = Depends(TENANT_DB_DEPENDENCY), # Tenant DB kullanılır
    current_user=Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 5: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.UrunKategori)
    if arama:
        query = query.filter(modeller.UrunKategori.ad.ilike(f"%{arama}%"))
    kategoriler = query.offset(skip).limit(limit).all()
    total_count = query.count()
    return {"items": [modeller.UrunKategoriRead.model_validate(k, from_attributes=True) for k in kategoriler], "total": total_count}

@router.get("/kategoriler/{kategori_id}", response_model=modeller.UrunKategoriRead)
def read_kategori(kategori_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 6: IZOLASYON FILTRESI KALDIRILDI!
    kategori = db.query(modeller.UrunKategori).filter(modeller.UrunKategori.id == kategori_id).first()
    if not kategori:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori bulunamadı")
    return kategori

@router.put("/kategoriler/{kategori_id}", response_model=modeller.UrunKategoriRead)
def update_kategori(kategori_id: int, kategori: modeller.UrunKategoriUpdate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 7: IZOLASYON FILTRESI KALDIRILDI!
    db_kategori = db.query(modeller.UrunKategori).filter(modeller.UrunKategori.id == kategori_id).first()
    if not db_kategori:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori bulunamadı")
    for key, value in kategori.model_dump(exclude_unset=True).items():
        setattr(db_kategori, key, value)
    db.commit()
    db.refresh(db_kategori)
    return db_kategori

@router.delete("/kategoriler/{kategori_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kategori(kategori_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 8: IZOLASYON FILTRESI KALDIRILDI!
    db_kategori = db.query(modeller.UrunKategori).filter(modeller.UrunKategori.id == kategori_id).first()
    if not db_kategori:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori bulunamadı")
    # KRİTİK DÜZELTME 9: Stock modelinde de IZOLASYON FILTRESI KALDIRILDI!
    if db.query(modeller.Stok).filter(modeller.Stok.kategori_id == kategori_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu kategoriye bağlı ürünler olduğu için silinemez.")
    db.delete(db_kategori)
    db.commit()
    return

# Marka endpointleri
@router.post("/markalar/", response_model=modeller.UrunMarkaRead)
def create_marka(marka: modeller.UrunMarkaCreate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 10: modeller.UrunMarka kullanıldı ve kullanici_id=1 atandı.
    db_marka = modeller.UrunMarka(**marka.model_dump(), kullanici_id=1)
    db.add(db_marka)
    db.commit()
    db.refresh(db_marka)
    return db_marka

@router.get("/markalar", response_model=modeller.NitelikListResponse)
def read_markalar(
    skip: int = 0,
    limit: int = 1000,
    arama: str = Query(None),
    db: Session = Depends(TENANT_DB_DEPENDENCY),
    current_user=Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 11: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.UrunMarka)
    if arama:
        query = query.filter(modeller.UrunMarka.ad.ilike(f"%{arama}%"))
    markalar = query.offset(skip).limit(limit).all()
    total_count = query.count()
    return {"items": [modeller.UrunMarkaRead.model_validate(m, from_attributes=True) for m in markalar], "total": total_count}

@router.get("/markalar/{marka_id}", response_model=modeller.UrunMarkaRead)
def read_marka(marka_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 12: IZOLASYON FILTRESI KALDIRILDI!
    marka = db.query(modeller.UrunMarka).filter(modeller.UrunMarka.id == marka_id).first()
    if not marka:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marka bulunamadı")
    return marka

@router.put("/markalar/{marka_id}", response_model=modeller.UrunMarkaRead)
def update_marka(marka_id: int, marka: modeller.UrunMarkaUpdate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 13: IZOLASYON FILTRESI KALDIRILDI!
    db_marka = db.query(modeller.UrunMarka).filter(modeller.UrunMarka.id == marka_id).first()
    if not db_marka:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marka bulunamadı")
    for key, value in marka.model_dump(exclude_unset=True).items():
        setattr(db_marka, key, value)
    db.commit()
    db.refresh(db_marka)
    return db_marka

@router.delete("/markalar/{marka_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_marka(marka_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 14: IZOLASYON FILTRESI KALDIRILDI!
    db_marka = db.query(modeller.UrunMarka).filter(modeller.UrunMarka.id == marka_id).first()
    if not db_marka:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marka bulunamadı")
    # KRİTİK DÜZELTME 15: Stock modelinde de IZOLASYON FILTRESI KALDIRILDI!
    if db.query(modeller.Stok).filter(modeller.Stok.marka_id == marka_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu markaya bağlı ürünler olduğu için silinemez.")
    db.delete(db_marka)
    db.commit()
    return

# Ürün Grubu endpointleri
@router.post("/urun_gruplari/", response_model=modeller.UrunGrubuRead)
def create_urun_grubu(urun_grubu: modeller.UrunGrubuCreate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 16: modeller.UrunGrubu kullanıldı ve kullanici_id=1 atandı.
    db_urun_grubu = modeller.UrunGrubu(**urun_grubu.model_dump(), kullanici_id=1)
    db.add(db_urun_grubu)
    db.commit()
    db.refresh(db_urun_grubu)
    return db_urun_grubu

@router.get("/urun_gruplari", response_model=modeller.NitelikListResponse)
def read_urun_gruplari(
    skip: int = 0,
    limit: int = 1000,
    arama: str = Query(None),
    db: Session = Depends(TENANT_DB_DEPENDENCY),
    current_user=Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 17: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.UrunGrubu)
    if arama:
        query = query.filter(modeller.UrunGrubu.ad.ilike(f"%{arama}%"))
    urun_gruplari = query.offset(skip).limit(limit).all()
    total_count = query.count()
    return {"items": [modeller.UrunGrubuRead.model_validate(ug, from_attributes=True) for ug in urun_gruplari], "total": total_count}

@router.get("/urun_gruplari/{urun_grubu_id}", response_model=modeller.UrunGrubuRead)
def read_urun_grubu(urun_grubu_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 18: IZOLASYON FILTRESI KALDIRILDI!
    urun_grubu = db.query(modeller.UrunGrubu).filter(modeller.UrunGrubu.id == urun_grubu_id).first()
    if not urun_grubu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün grubu bulunamadı")
    return urun_grubu

@router.put("/urun_gruplari/{urun_grubu_id}", response_model=modeller.UrunGrubuRead)
def update_urun_grubu(urun_grubu_id: int, urun_grubu: modeller.UrunGrubuUpdate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 19: IZOLASYON FILTRESI KALDIRILDI!
    db_urun_grubu = db.query(modeller.UrunGrubu).filter(modeller.UrunGrubu.id == urun_grubu_id).first()
    if not db_urun_grubu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün grubu bulunamadı")
    for key, value in urun_grubu.model_dump(exclude_unset=True).items():
        setattr(db_urun_grubu, key, value)
    db.commit()
    db.refresh(db_urun_grubu)
    return db_urun_grubu

@router.delete("/urun_gruplari/{urun_grubu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_urun_grubu(urun_grubu_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 20: IZOLASYON FILTRESI KALDIRILDI!
    db_urun_grubu = db.query(modeller.UrunGrubu).filter(modeller.UrunGrubu.id == urun_grubu_id).first()
    if not db_urun_grubu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün grubu bulunamadı")
    # KRİTİK DÜZELTME 21: Stock modelinde de IZOLASYON FILTRESI KALDIRILDI!
    if db.query(modeller.Stok).filter(modeller.Stok.urun_grubu_id == urun_grubu_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu ürün grubuna bağlı ürünler olduğu için silinemez.")
    db.delete(db_urun_grubu)
    db.commit()
    return

# Birim endpointleri
@router.post("/urun_birimleri/", response_model=modeller.UrunBirimiRead)
def create_urun_birimi(urun_birimi: modeller.UrunBirimiCreate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 22: modeller.UrunBirimi kullanıldı ve kullanici_id=1 atandı.
    db_urun_birimi = modeller.UrunBirimi(**urun_birimi.model_dump(), kullanici_id=1)
    db.add(db_urun_birimi)
    db.commit()
    db.refresh(db_urun_birimi)
    return db_urun_birimi

@router.get("/urun_birimleri", response_model=modeller.NitelikListResponse)
def read_urun_birimleri(
    skip: int = 0,
    limit: int = 1000,
    arama: str = Query(None),
    db: Session = Depends(TENANT_DB_DEPENDENCY),
    current_user=Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 23: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.UrunBirimi)
    if arama:
        query = query.filter(modeller.UrunBirimi.ad.ilike(f"%{arama}%"))
    urun_birimleri = query.offset(skip).limit(limit).all()
    total_count = query.count()
    return {"items": [modeller.UrunBirimiRead.model_validate(ub, from_attributes=True) for ub in urun_birimleri], "total": total_count}

@router.get("/urun_birimleri/{urun_birimi_id}", response_model=modeller.UrunBirimiRead)
def read_urun_birimi(urun_birimi_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 24: IZOLASYON FILTRESI KALDIRILDI!
    urun_birimi = db.query(modeller.UrunBirimi).filter(modeller.UrunBirimi.id == urun_birimi_id).first()
    if not urun_birimi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün birimi bulunamadı")
    return urun_birimi

@router.put("/urun_birimleri/{urun_birimi_id}", response_model=modeller.UrunBirimiRead)
def update_urun_birimi(urun_birimi_id: int, urun_birimi: modeller.UrunBirimiUpdate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 25: IZOLASYON FILTRESI KALDIRILDI!
    db_urun_birimi = db.query(modeller.UrunBirimi).filter(modeller.UrunBirimi.id == urun_birimi_id).first()
    if not db_urun_birimi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün birimi bulunamadı")
    for key, value in urun_birimi.model_dump(exclude_unset=True).items():
        setattr(db_urun_birimi, key, value)
    db.commit()
    db.refresh(db_urun_birimi)
    return db_urun_birimi

@router.delete("/urun_birimleri/{urun_birimi_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_urun_birimi(urun_birimi_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 26: IZOLASYON FILTRESI KALDIRILDI!
    db_urun_birimi = db.query(modeller.UrunBirimi).filter(modeller.UrunBirimi.id == urun_birimi_id).first()
    if not db_urun_birimi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ürün birimi bulunamadı")
    # KRİTİK DÜZELTME 27: Stock modelinde de IZOLASYON FILTRESI KALDIRILDI!
    if db.query(modeller.Stok).filter(modeller.Stok.birim_id == urun_birimi_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu birime bağlı ürünler olduğu için silinemez.")
    db.delete(db_urun_birimi)
    db.commit()
    return

# Ülke endpointleri
@router.post("/ulkeler/", response_model=modeller.UlkeRead)
def create_ulke(ulke: modeller.UlkeCreate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 28: modeller.Ulke kullanıldı ve kullanici_id=1 atandı.
    db_ulke = modeller.Ulke(**ulke.model_dump(), kullanici_id=1)
    db.add(db_ulke)
    db.commit()
    db.refresh(db_ulke)
    return db_ulke

@router.get("/ulkeler", response_model=modeller.NitelikListResponse)
def read_ulkeler(
    skip: int = 0,
    limit: int = 1000,
    arama: str = Query(None),
    db: Session = Depends(TENANT_DB_DEPENDENCY),
    current_user=Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 29: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.Ulke)
    if arama:
        query = query.filter(modeller.Ulke.ad.ilike(f"%{arama}%"))
    ulkeler = query.offset(skip).limit(limit).all()
    total_count = query.count()
    return {"items": [modeller.UlkeRead.model_validate(u, from_attributes=True) for u in ulkeler], "total": total_count}

@router.get("/ulkeler/{ulke_id}", response_model=modeller.UlkeRead)
def read_ulke(ulke_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 30: IZOLASYON FILTRESI KALDIRILDI!
    ulke = db.query(modeller.Ulke).filter(modeller.Ulke.id == ulke_id).first()
    if not ulke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ülke bulunamadı")
    return ulke

@router.put("/ulkeler/{ulke_id}", response_model=modeller.UlkeRead)
def update_ulke(ulke_id: int, ulke: modeller.UlkeUpdate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 31: IZOLASYON FILTRESI KALDIRILDI!
    db_ulke = db.query(modeller.Ulke).filter(modeller.Ulke.id == ulke_id).first()
    if not db_ulke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ülke bulunamadı")
    for key, value in ulke.model_dump(exclude_unset=True).items():
        setattr(db_ulke, key, value)
    db.commit()
    db.refresh(db_ulke)
    return db_ulke

@router.delete("/ulkeler/{ulke_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ulke(ulke_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 32: IZOLASYON FILTRESI KALDIRILDI!
    db_ulke = db.query(modeller.Ulke).filter(modeller.Ulke.id == ulke_id).first()
    if not db_ulke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ülke bulunamadı")
    # KRİTİK DÜZELTME 33: Stock modelinde de IZOLASYON FILTRESI KALDIRILDI!
    if db.query(modeller.Stok).filter(modeller.Stok.mense_id == ulke_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu ülkeye bağlı ürünler olduğu için silinemez.")
    db.delete(db_ulke)
    db.commit()
    return

# Gelir Sınıflandırma endpointleri
@router.post("/gelir_siniflandirmalari/", response_model=modeller.GelirSiniflandirmaRead)
def create_gelir_siniflandirma(siniflandirma: modeller.GelirSiniflandirmaCreate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 34: modeller.GelirSiniflandirma kullanıldı ve kullanici_id=1 atandı.
    db_siniflandirma = modeller.GelirSiniflandirma(**siniflandirma.model_dump(), kullanici_id=1)
    db.add(db_siniflandirma)
    db.commit()
    db.refresh(db_siniflandirma)
    return db_siniflandirma

@router.get("/gelir_siniflandirmalari", response_model=modeller.NitelikListResponse)
def read_gelir_siniflandirmalari(
    skip: int = 0,
    limit: int = 100,
    id: Optional[int] = None,
    db: Session = Depends(TENANT_DB_DEPENDENCY),
    current_user=Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 35: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.GelirSiniflandirma)
    if id:
        query = query.filter(modeller.GelirSiniflandirma.id == id)
    siniflandirmalar = query.offset(skip).limit(limit).all()
    total_count = query.count()
    return {"items": [modeller.GelirSiniflandirmaRead.model_validate(s, from_attributes=True) for s in siniflandirmalar], "total": total_count}

@router.get("/gelir_siniflandirmalari/{siniflandirma_id}", response_model=modeller.GelirSiniflandirmaRead)
def read_gelir_siniflandirma(siniflandirma_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 36: IZOLASYON FILTRESI KALDIRILDI!
    siniflandirma = db.query(modeller.GelirSiniflandirma).filter(modeller.GelirSiniflandirma.id == siniflandirma_id).first()
    if not siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gelir sınıflandırması bulunamadı")
    return siniflandirma

@router.put("/gelir_siniflandirmalari/{siniflandirma_id}", response_model=modeller.GelirSiniflandirmaRead)
def update_gelir_siniflandirma(siniflandirma_id: int, siniflandirma: modeller.GelirSiniflandirmaUpdate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 37: IZOLASYON FILTRESI KALDIRILDI!
    db_siniflandirma = db.query(modeller.GelirSiniflandirma).filter(modeller.GelirSiniflandirma.id == siniflandirma_id).first()
    if not db_siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gelir sınıflandırması bulunamadı")
    for key, value in siniflandirma.model_dump(exclude_unset=True).items():
        setattr(db_siniflandirma, key, value)
    db.commit()
    db.refresh(db_siniflandirma)
    return db_siniflandirma

@router.delete("/gelir_siniflandirmalari/{siniflandirma_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gelir_siniflandirma(siniflandirma_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 38: IZOLASYON FILTRESI KALDIRILDI!
    db_siniflandirma = db.query(modeller.GelirSiniflandirma).filter(modeller.GelirSiniflandirma.id == siniflandirma_id).first()
    if not db_siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gelir sınıflandırması bulunamadı")
    # KRİTİK DÜZELTME 39: GelirGider modelinde de IZOLASYON FILTRESI KALDIRILDI!
    if db.query(modeller.GelirGider).filter(modeller.GelirGider.gelir_siniflandirma_id == siniflandirma_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu gelir sınıflandırmasına bağlı hareketler olduğu için silinemez.")
    db.delete(db_siniflandirma)
    db.commit()
    return

# Gider Sınıflandırma endpointleri
@router.post("/gider_siniflandirmalari/", response_model=modeller.GiderSiniflandirmaRead)
def create_gider_siniflandirma(siniflandirma: modeller.GiderSiniflandirmaCreate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 40: modeller.GiderSiniflandirma kullanıldı ve kullanici_id=1 atandı.
    db_siniflandirma = modeller.GiderSiniflandirma(**siniflandirma.model_dump(), kullanici_id=1)
    db.add(db_siniflandirma)
    db.commit()
    db.refresh(db_siniflandirma)
    return db_siniflandirma

@router.get("/gider_siniflandirmalari", response_model=modeller.NitelikListResponse)
def read_gider_siniflandirmalari(
    skip: int = 0,
    limit: int = 100,
    id: Optional[int] = None,
    db: Session = Depends(TENANT_DB_DEPENDENCY),
    current_user=Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 41: IZOLASYON FILTRESI KALDIRILDI!
    query = db.query(modeller.GiderSiniflandirma)
    if id:
        query = query.filter(modeller.GiderSiniflandirma.id == id)
    siniflandirmalar = query.offset(skip).limit(limit).all()
    total_count = query.count()
    return {"items": [modeller.GiderSiniflandirmaRead.model_validate(s, from_attributes=True) for s in siniflandirmalar], "total": total_count}

@router.get("/gider_siniflandirmalari/{siniflandirma_id}", response_model=modeller.GiderSiniflandirmaRead)
def read_gider_siniflandirma(siniflandirma_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 42: IZOLASYON FILTRESI KALDIRILDI!
    siniflandirma = db.query(modeller.GiderSiniflandirma).filter(modeller.GiderSiniflandirma.id == siniflandirma_id).first()
    if not siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gider sınıflandırması bulunamadı")
    return siniflandirma

@router.put("/gider_siniflandirmalari/{siniflandirma_id}", response_model=modeller.GiderSiniflandirmaRead)
def update_gider_siniflandirma(siniflandirma_id: int, siniflandirma: modeller.GiderSiniflandirmaUpdate, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 43: IZOLASYON FILTRESI KALDIRILDI!
    db_siniflandirma = db.query(modeller.GiderSiniflandirma).filter(modeller.GiderSiniflandirma.id == siniflandirma_id).first()
    if not db_siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gider sınıflandırması bulunamadı")
    for key, value in siniflandirma.model_dump(exclude_unset=True).items():
        setattr(db_siniflandirma, key, value)
    db.commit()
    db.refresh(db_siniflandirma)
    return db_siniflandirma

@router.delete("/gider_siniflandirmalari/{siniflandirma_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gider_siniflandirma(siniflandirma_id: int, db: Session = Depends(TENANT_DB_DEPENDENCY), current_user=Depends(guvenlik.get_current_user)):
    # KRİTİK DÜZELTME 44: IZOLASYON FILTRESI KALDIRILDI!
    db_siniflandirma = db.query(modeller.GiderSiniflandirma).filter(modeller.GiderSiniflandirma.id == siniflandirma_id).first()
    if not db_siniflandirma:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gider sınıflandırması bulunamadı")
    # KRİTİK DÜZELTME 45: GelirGider modelinde de IZOLASYON FILTRESI KALDIRILDI!
    if db.query(modeller.GelirGider).filter(modeller.GelirGider.gider_siniflandirma_id == siniflandirma_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu gider sınıflandırmasına bağlı hareketler olduğu için silinemez.")
    db.delete(db_siniflandirma)
    db.commit()
    return