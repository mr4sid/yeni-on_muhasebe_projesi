# api/rotalar/stoklar.py dosyasının tam içeriği (Hata Çözümü Uygulandı)
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload # <<< KRİTİK EKLEME: joinedload eklendi
from sqlalchemy import func, and_, or_
from .. import modeller, semalar, guvenlik
from ..veritabani import get_db
from typing import List, Optional, Any
from datetime import datetime, date
from sqlalchemy import String
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
# DEĞİŞİKLİK: Doğru içe aktarma yolu kullanıldı
from hizmetler import FaturaService
import logging
from ..guvenlik import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stoklar", tags=["Stoklar"])


@router.post("/", response_model=modeller.StokRead)
def create_stok(
    stok: modeller.StokCreate,
    current_user: semalar.Kullanici = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # model_dump()'tan 'kullanici_id' hariç tutuldu. 
        stok_data = stok.model_dump(exclude={'kullanici_id', 'id'})
        
        # KRİTİK DÜZELTME: Nitelik ID'lerini -1'den None'a çevirme (ForeignKeyViolation'ı çözmek için)
        for field in ['kategori_id', 'marka_id', 'urun_grubu_id', 'birim_id', 'mense_id']:
            if stok_data.get(field) == -1:
                stok_data[field] = None
        
        db_stok = modeller.Stok(**stok_data, kullanici_id=current_user.id)
        
        db.add(db_stok)
        db.commit()
        db.refresh(db_stok)
        
        # Stok hareketi eklenir (İlk Giriş)
        # Sadece yeni ürün ekleniyorsa ilk stok miktarını ekle
        if stok.miktar and stok.miktar > 0:
             modeller.StokHareket.create_stok_hareket(
                db, 
                urun_id=db_stok.id, 
                islem_tipi=modeller.OnMuhasebe.STOK_ISLEM_TIP_GIRIS_MANUEL, 
                miktar=stok.miktar, 
                aciklama="İlk Stok Girişi", 
                kaynak="MANUEL", 
                kullanici_id=current_user.id
             )
        
        return modeller.StokRead.model_validate(db_stok, from_attributes=True)
    
    except IntegrityError as e:
        db.rollback()
        if "unique_kod" in str(e):
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ürün kodu zaten mevcut.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Stok kaydı oluşturulurken veritabanı hatası: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Stok kaydı oluşturulurken beklenmedik hata: {str(e)}")

@router.get("/", response_model=modeller.StokListResponse)
def read_stoklar(
    skip: int = 0,
    limit: int = 25,
    arama: Optional[str] = None,
    aktif_durum: Optional[bool] = True,
    kritik_stok_altinda: Optional[bool] = False,
    kategori_id: Optional[int] = None,
    marka_id: Optional[int] = None,
    urun_grubu_id: Optional[int] = None,
    stokta_var: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # DÜZELTME: JWT Kuralı ve doğru tip
):
    query = db.query(modeller.Stok).filter(modeller.Stok.kullanici_id == current_user.id) # DÜZELTME: modeller.Stok kullanıldı
    
    if arama:
        search_filter = or_(
            modeller.Stok.kod.ilike(f"%{arama}%"), # DÜZELTME: modeller.Stok kullanıldı
            modeller.Stok.ad.ilike(f"%{arama}%") # DÜZELTME: modeller.Stok kullanıldı
        )
        query = query.filter(search_filter)

    if aktif_durum is not None:
        query = query.filter(modeller.Stok.aktif == aktif_durum) # DÜZELTME: modeller.Stok kullanıldı

    if kritik_stok_altinda:
        query = query.filter(modeller.Stok.miktar <= modeller.Stok.min_stok_seviyesi) # DÜZELTME: modeller.Stok kullanıldı

    if kategori_id:
        query = query.filter(modeller.Stok.kategori_id == kategori_id) # DÜZELTME: modeller.Stok kullanıldı

    if marka_id:
        query = query.filter(modeller.Stok.marka_id == marka_id) # DÜZELTME: modeller.Stok kullanıldı

    if urun_grubu_id:
        query = query.filter(modeller.Stok.urun_grubu_id == urun_grubu_id) # DÜZELTME: modeller.Stok kullanıldı

    if stokta_var is not None:
        if stokta_var:
            query = query.filter(modeller.Stok.miktar > 0) # DÜZELTME: modeller.Stok kullanıldı
        else:
            query = query.filter(modeller.Stok.miktar <= 0) # DÜZELTME: modeller.Stok kullanıldı

    total_count = query.count()
    
    stoklar = query.offset(skip).limit(limit).all()
    
    return {"items": [
        modeller.StokRead.model_validate(s, from_attributes=True)
        for s in stoklar
    ], "total": total_count}

@router.get("/ozet", response_model=modeller.StokOzetResponse)
def get_stok_ozet(
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # DÜZELTME: JWT Kuralı ve doğru tip
):
    query = db.query(modeller.Stok).filter(modeller.Stok.kullanici_id == current_user.id) # DÜZELTME: modeller.Stok kullanıldı
    
    toplam_miktar = query.with_entities(func.sum(modeller.Stok.miktar)).scalar() or 0 # DÜZELTME: modeller.Stok kullanıldı
    toplam_alis_fiyati = query.with_entities(func.sum(modeller.Stok.alis_fiyati * modeller.Stok.miktar)).scalar() or 0 # DÜZELTME: modeller.Stok kullanıldı
    toplam_satis_fiyati = query.with_entities(func.sum(modeller.Stok.satis_fiyati * modeller.Stok.miktar)).scalar() or 0 # DÜZELTME: modeller.Stok kullanıldı
    
    toplam_urun_sayisi = query.filter(modeller.Stok.aktif == True).count() # DÜZELTME: modeller.Stok kullanıldı
    
    return {
        "toplam_urun_sayisi": toplam_urun_sayisi,
        "toplam_miktar": toplam_miktar,
        "toplam_maliyet": toplam_alis_fiyati,
        "toplam_satis_tutari": toplam_satis_fiyati
    }

@router.get("/{stok_id}", response_model=modeller.StokRead)
def read_stok(
    stok_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user)
):
    # KRİTİK DÜZELTME: İlişkileri (kategori, marka, grup, birim, mense) sorgu anında yükle (joinedload).
    # Bu, 'AttributeError: 'Stok' object has no attribute 'kategori'' hatasını çözer.
    stok = db.query(modeller.Stok).options(
        joinedload(modeller.Stok.kategori),
        joinedload(modeller.Stok.marka),
        joinedload(modeller.Stok.urun_grubu),
        joinedload(modeller.Stok.birim),
        joinedload(modeller.Stok.mense_ulke)
    ).filter(
        modeller.Stok.id == stok_id,
        modeller.Stok.kullanici_id == current_user.id
    ).first()
    
    if not stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    
    # Pydantic modeline dönüştürme
    stok_read_data = modeller.StokRead.model_validate(stok, from_attributes=True).model_dump()
    
    # İlişkili Nitelik Verilerini StokRead modeline ekle (Kontrol mekanizması korundu)
    if hasattr(stok, 'kategori') and stok.kategori:
        stok_read_data['kategori'] = modeller.UrunKategoriRead.model_validate(stok.kategori, from_attributes=True).model_dump()
    if hasattr(stok, 'marka') and stok.marka:
        stok_read_data['marka'] = modeller.UrunMarkaRead.model_validate(stok.marka, from_attributes=True).model_dump()
    if hasattr(stok, 'urun_grubu') and stok.urun_grubu:
        stok_read_data['urun_grubu'] = modeller.UrunGrubuRead.model_validate(stok.urun_grubu, from_attributes=True).model_dump()
    if hasattr(stok, 'birim') and stok.birim:
        stok_read_data['birim'] = modeller.UrunBirimiRead.model_validate(stok.birim, from_attributes=True).model_dump()
    if hasattr(stok, 'mense_ulke') and stok.mense_ulke:
        stok_read_data['mense_ulke'] = modeller.UlkeRead.model_validate(stok.mense_ulke, from_attributes=True).model_dump()
        
    return stok_read_data

@router.put("/{stok_id}", response_model=modeller.StokRead)
def update_stok(
    stok_id: int,
    stok: modeller.StokUpdate,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # DÜZELTME: JWT Kuralı ve doğru tip
):
    db_stok = db.query(modeller.Stok).filter( # DÜZELTME: modeller.Stok kullanıldı
        modeller.Stok.id == stok_id, # DÜZELTME: modeller.Stok kullanıldı
        modeller.Stok.kullanici_id == current_user.id # DÜZELTME: modeller.Stok kullanıldı
    ).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    for key, value in stok.model_dump(exclude_unset=True).items():
        setattr(db_stok, key, value)
    db.commit()
    db.refresh(db_stok)
    return db_stok

@router.delete("/{stok_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stok(
    stok_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # DÜZELTME: JWT Kuralı ve doğru tip
):
    db_stok = db.query(modeller.Stok).filter( # DÜZELTME: modeller.Stok kullanıldı
        modeller.Stok.id == stok_id, # DÜZELTME: modeller.Stok kullanıldı
        modeller.Stok.kullanici_id == current_user.id # DÜZELTME: modeller.Stok kullanıldı
    ).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    db.delete(db_stok)
    db.commit()
    return

@router.get("/{stok_id}/anlik_miktar", response_model=modeller.AnlikStokMiktariResponse)
def get_anlik_stok_miktari_endpoint(
    stok_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # DÜZELTME: JWT Kuralı ve doğru tip
):
    stok = db.query(modeller.Stok).filter( # DÜZELTME: modeller.Stok kullanıldı
        modeller.Stok.id == stok_id, # DÜZELTME: modeller.Stok kullanıldı
        modeller.Stok.kullanici_id == current_user.id # DÜZELTME: modeller.Stok kullanıldı
    ).first()
    if not stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı")
    
    return {"anlik_miktar": stok.miktar}

@router.post("/{stok_id}/hareket", response_model=modeller.StokHareketRead)
def create_stok_hareket(
    stok_id: int,
    hareket: modeller.StokHareketCreate,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # DÜZELTME: JWT Kuralı ve doğru tip
):
    db_stok = db.query(modeller.Stok).filter( # DÜZELTME: modeller.Stok kullanıldı
        modeller.Stok.id == stok_id, # DÜZELTME: modeller.Stok kullanıldı
        modeller.Stok.kullanici_id == current_user.id # DÜZELTME: modeller.Stok kullanıldı
    ).first()
    if not db_stok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stok bulunamadı.")
    
    if hareket.miktar <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Miktar pozitif bir değer olmalıdır.")

    db.begin_nested()

    try:
        stok_degisim_net = 0.0
        # semalar.StokIslemTipiEnum yerine modeller.StokIslemTipiEnum kullanılmalı, ancak Enum importu semalar'dan yapıldığı için semalar.StokIslemTipiEnum olarak tutuldu.
        # Not: Buradaki Enum adları, modeller.py dosyasındaki Enumlara karşılık gelmelidir.
        if hareket.islem_tipi in [
            semalar.StokIslemTipiEnum.GIRIS,
            semalar.StokIslemTipiEnum.SAYIM_FAZLASI,
            semalar.StokIslemTipiEnum.SATIŞ_İADE,
            semalar.StokIslemTipiEnum.ALIŞ
        ]:
            stok_degisim_net = hareket.miktar
        elif hareket.islem_tipi in [
            semalar.StokIslemTipiEnum.CIKIS, # CIKIS'a düzeltildi
            semalar.StokIslemTipiEnum.SAYIM_EKSİĞİ,
            # semalar.StokIslemTipiEnum.ZAYIAT, # Enum'da yoksa çıkarıldı
            semalar.StokIslemTipiEnum.SATIŞ,
            semalar.StokIslemTipiEnum.ALIŞ_İADE
        ]:
            stok_degisim_net = -hareket.miktar
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz işlem tipi.")
        
        onceki_stok_miktari = db_stok.miktar

        db_stok.miktar += stok_degisim_net
        db.add(db_stok)

        db_hareket = modeller.StokHareket( # DÜZELTME: modeller.StokHareket kullanıldı
            urun_id=stok_id, # DÜZELTME: kolon adı urun_id olarak değiştirildi
            tarih=hareket.tarih,
            islem_tipi=hareket.islem_tipi,
            miktar=hareket.miktar,
            birim_fiyat=hareket.birim_fiyat,
            aciklama=hareket.aciklama,
            kaynak=semalar.KaynakTipEnum.MANUEL,
            kaynak_id=None,
            onceki_stok=onceki_stok_miktari,
            sonraki_stok=db_stok.miktar,
            kullanici_id=current_user.id
        )
        db.add(db_hareket)

        db.commit()
        db.refresh(db_hareket)
        return modeller.StokHareketRead.model_validate(db_hareket, from_attributes=True)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Stok hareketi oluşturulurken hata: {str(e)}")

@router.get("/{stok_id}/hareketler", response_model=modeller.StokHareketListResponse)
def get_stok_hareketleri_endpoint(
    stok_id: int,
    skip: int = 0,
    limit: int = 100,
    islem_tipi: str = Query(None),
    baslangic_tarihi: str = Query(None),
    bitis_tarihi: str = Query(None),
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # DÜZELTME: JWT Kuralı ve doğru tip
):
    kullanici_id = current_user.id
    # MODEL TUTARLILIĞI DÜZELTME: semalar.StokHareket -> modeller.StokHareket
    query = db.query(modeller.StokHareket).filter(modeller.StokHareket.kullanici_id == kullanici_id)

    if stok_id:
        # KRİTİK DÜZELTME: Yanlış kolon 'stok_id' yerine doğru kolon 'urun_id' kullanıldı.
        query = query.filter(modeller.StokHareket.urun_id == stok_id)
    if islem_tipi:
        query = query.filter(modeller.StokHareket.islem_tipi == islem_tipi)
    if baslangic_tarihi:
        query = query.filter(modeller.StokHareket.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(modeller.StokHareket.tarih <= bitis_tarihi)

    total = query.count()
    hareketler = query.order_by(modeller.StokHareket.tarih.desc()).offset(skip).limit(limit).all()

    return {"items": [
        modeller.StokHareketRead.model_validate(hareket, from_attributes=True)
        for hareket in hareketler
    ], "total": total}

@router.delete("/hareketler/{hareket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stok_hareket(
    hareket_id: int,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # DÜZELTME: JWT Kuralı ve doğru tip
):
    db_hareket = db.query(modeller.StokHareket).filter( # DÜZELTME: modeller.StokHareket kullanıldı
        and_(
            modeller.StokHareket.id == hareket_id, # DÜZELTME: modeller.StokHareket kullanıldı
            modeller.StokHareket.kaynak == semalar.KaynakTipEnum.MANUEL, # DÜZELTME: modeller.StokHareket kullanıldı
            modeller.StokHareket.kullanici_id == current_user.id # DÜZELTME: modeller.StokHareket kullanıldı
        )
    ).first()

    if not db_hareket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Stok hareketi bulunamadı veya manuel olarak silinemez (otomatik oluşturulmuştur)."
        )
    
    stok = db.query(modeller.Stok).filter( # DÜZELTME: modeller.Stok kullanıldı
        modeller.Stok.id == db_hareket.urun_id, # DÜZELTME: urun_id kullanıldı
        modeller.Stok.kullanici_id == current_user.id # DÜZELTME: modeller.Stok kullanıldı
    ).first()
    if stok:
        # Geri alma mantığı düzeltildi
        if db_hareket.islem_tipi in [semalar.StokIslemTipiEnum.GIRIS, semalar.StokIslemTipiEnum.SAYIM_FAZLASI, semalar.StokIslemTipiEnum.ALIŞ, semalar.StokIslemTipiEnum.SATIŞ_İADE]:
            stok.miktar -= db_hareket.miktar
        elif db_hareket.islem_tipi in [semalar.StokIslemTipiEnum.CIKIS, semalar.StokIslemTipiEnum.SAYIM_EKSİĞİ, semalar.StokIslemTipiEnum.SATIŞ, semalar.StokIslemTipiEnum.ALIŞ_İADE]:
            stok.miktar += db_hareket.miktar
        db.add(stok)
    
    db.delete(db_hareket)
    db.commit()
    return {"detail": "Stok hareketi başarıyla silindi."}

@router.post("/bulk_upsert", response_model=modeller.TopluIslemSonucResponse)
def bulk_stok_upsert_endpoint(
    stok_listesi: List[modeller.StokCreate],
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(get_current_user) # DÜZELTME: JWT Kuralı ve doğru tip
):
    db.begin_nested()
    try:
        yeni_eklenen = 0
        guncellenen = 0
        hata_veren = 0
        hatalar = []

        pozitif_kalemler = []
        negatif_kalemler = []
        
        for stok_data in stok_listesi:
            try:
                db_stok = db.query(modeller.Stok).filter( # DÜZELTME: modeller.Stok kullanıldı
                    modeller.Stok.kod == stok_data.kod, # DÜZELTME: modeller.Stok kullanıldı
                    modeller.Stok.kullanici_id == current_user.id # DÜZELTME: modeller.Stok kullanıldı
                ).first()
                
                if db_stok:
                    for key, value in stok_data.model_dump(exclude_unset=True).items():
                        setattr(db_stok, key, value)
                    db.add(db_stok)
                    guncellenen += 1
                else:
                    yeni_stok = modeller.Stok(**stok_data.model_dump(), kullanici_id=current_user.id) # DÜZELTME: modeller.Stok kullanıldı
                    db.add(yeni_stok)
                    db.flush()
                    yeni_eklenen += 1
                    
                    if yeni_stok.miktar != 0:
                        # Alış fiyatının KDV hariç hali, modeldeki alış fiyatı varsayılır.
                        alis_fiyati_kdv_haric = yeni_stok.alis_fiyati
                        
                        kalem_bilgisi = {
                            "urun_id": yeni_stok.id,
                            "miktar": yeni_stok.miktar,
                            "birim_fiyat": alis_fiyati_kdv_haric,
                            "kdv_orani": yeni_stok.kdv_orani,
                            "alis_fiyati_fatura_aninda": alis_fiyati_kdv_haric
                        }
                        
                        if kalem_bilgisi["miktar"] > 0:
                            pozitif_kalemler.append(kalem_bilgisi)
                        else:
                            negatif_kalemler.append(kalem_bilgisi)

            except Exception as e:
                hata_veren += 1
                hatalar.append(f"Stok kodu '{stok_data.kod}' işlenirken hata: {e}")

        if pozitif_kalemler:
            fatura_no=f"TOPLU-ALIS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            tarih=datetime.now().date() # DÜZELTME: date objesi kullanıldı
            
            toplam_kdv_haric = sum(k['birim_fiyat'] * k['miktar'] for k in pozitif_kalemler)
            toplam_kdv_dahil = sum(k['birim_fiyat'] * (1 + k['kdv_orani'] / 100) * k['miktar'] for k in pozitif_kalemler)
            
            db_fatura = modeller.Fatura( # DÜZELTME: modeller.Fatura kullanıldı
                fatura_no=fatura_no,
                fatura_turu=semalar.FaturaTuruEnum.ALIS,
                tarih=tarih,
                cari_id=1,
                cari_tip=semalar.CariTipiEnum.TEDARIKCI.value,
                odeme_turu=semalar.OdemeTuruEnum.ETKISIZ_FATURA,
                fatura_notlari="Toplu stok ekleme işlemiyle otomatik oluşturulan alış faturası.",
                toplam_kdv_haric=toplam_kdv_haric,
                toplam_kdv_dahil=toplam_kdv_dahil,
                genel_toplam=toplam_kdv_dahil,
                kullanici_id=current_user.id
            )
            db.add(db_fatura)
            db.flush()

            for kalem_bilgisi in pozitif_kalemler:
                db_kalem = modeller.FaturaKalemi( # DÜZELTME: modeller.FaturaKalemi kullanıldı
                    fatura_id=db_fatura.id,
                    urun_id=kalem_bilgisi['urun_id'],
                    miktar=kalem_bilgisi['miktar'],
                    birim_fiyat=kalem_bilgisi['birim_fiyat'],
                    kdv_orani=kalem_bilgisi['kdv_orani'],
                    alis_fiyati_fatura_aninda=kalem_bilgisi['alis_fiyati_fatura_aninda']
                )
                db.add(db_kalem)
                
                db_stok = db.query(modeller.Stok).filter(modeller.Stok.id == kalem_bilgisi['urun_id']).first() # DÜZELTME: modeller.Stok kullanıldı
                if db_stok:
                    db_stok_hareket = modeller.StokHareket( # DÜZELTME: modeller.StokHareket kullanıldı
                        urun_id=kalem_bilgisi['urun_id'],
                        tarih=db_fatura.tarih,
                        islem_tipi=semalar.StokIslemTipiEnum.ALIŞ,
                        miktar=kalem_bilgisi['miktar'],
                        birim_fiyat=kalem_bilgisi['birim_fiyat'],
                        aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})",
                        kaynak=semalar.KaynakTipEnum.FATURA,
                        kaynak_id=db_fatura.id,
                        onceki_stok=db_stok.miktar - kalem_bilgisi['miktar'],
                        sonraki_stok=db_stok.miktar,
                        kullanici_id=current_user.id
                    )
                    db.add(db_stok_hareket)

        if negatif_kalemler:
            fatura_no=f"TOPLU-ALIS-IADE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            tarih=datetime.now().date()
            
            toplam_kdv_haric_iade = sum(k['birim_fiyat'] * abs(k['miktar']) for k in negatif_kalemler)
            toplam_kdv_dahil_iade = sum(k['birim_fiyat'] * (1 + k['kdv_orani'] / 100) * abs(k['miktar']) for k in negatif_kalemler)
            
            db_fatura_iade = modeller.Fatura( # DÜZELTME: modeller.Fatura kullanıldı
                fatura_no=fatura_no,
                fatura_turu=semalar.FaturaTuruEnum.ALIS_IADE,
                tarih=tarih,
                cari_id=1,
                cari_tip=semalar.CariTipiEnum.TEDARIKCI.value,
                odeme_turu=semalar.OdemeTuruEnum.ETKISIZ_FATURA,
                fatura_notlari="Toplu stok ekleme işlemiyle otomatik oluşturulan alış iade faturası.",
                toplam_kdv_haric=toplam_kdv_haric_iade,
                toplam_kdv_dahil=toplam_kdv_dahil_iade,
                genel_toplam=toplam_kdv_dahil_iade,
                kullanici_id=current_user.id
            )
            db.add(db_fatura_iade)
            db.flush()

            for kalem_bilgisi in negatif_kalemler:
                db_kalem = modeller.FaturaKalemi( # DÜZELTME: modeller.FaturaKalemi kullanıldı
                    fatura_id=db_fatura_iade.id,
                    urun_id=kalem_bilgisi['urun_id'],
                    miktar=abs(kalem_bilgisi['miktar']),
                    birim_fiyat=kalem_bilgisi['birim_fiyat'],
                    kdv_orani=kalem_bilgisi['kdv_orani'],
                    alis_fiyati_fatura_aninda=kalem_bilgisi['alis_fiyati_fatura_aninda']
                )
                db.add(db_kalem)
                
                db_stok = db.query(modeller.Stok).filter(modeller.Stok.id == kalem_bilgisi['urun_id']).first() # DÜZELTME: modeller.Stok kullanıldı
                if db_stok:
                    db_stok_hareket = modeller.StokHareket( # DÜZELTME: modeller.StokHareket kullanıldı
                        urun_id=kalem_bilgisi['urun_id'],
                        tarih=db_fatura_iade.tarih,
                        islem_tipi=semalar.StokIslemTipiEnum.ALIŞ_İADE,
                        miktar=abs(kalem_bilgisi['miktar']),
                        birim_fiyat=kalem_bilgisi['birim_fiyat'],
                        aciklama=f"{db_fatura_iade.fatura_no} nolu fatura ({db_fatura_iade.fatura_turu.value})",
                        kaynak=semalar.KaynakTipEnum.FATURA,
                        kaynak_id=db_fatura_iade.id,
                        onceki_stok=db_stok.miktar + abs(kalem_bilgisi['miktar']),
                        sonraki_stok=db_stok.miktar,
                        kullanici_id=current_user.id
                    )
                    db.add(db_stok_hareket)

        db.commit()
        
        toplam_islenen = yeni_eklenen + guncellenen + hata_veren
        
        return {
            "yeni_eklenen_sayisi": yeni_eklenen,
            "guncellenen_sayisi": guncellenen,
            "hata_sayisi": hata_veren,
            "hatalar": hatalar,
            "toplam_islenen": toplam_islenen
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Toplu stok ekleme/güncelleme sırasında kritik hata: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Toplu stok ekleme sırasında hata: {e}")
    
@router.get("/hareketler/", response_model=modeller.StokHareketListResponse)
def list_stok_hareketleri_endpoint(
    stok_id: Optional[int] = Query(None),
    islem_tipi: Optional[semalar.StokIslemTipiEnum] = Query(None),
    baslangic_tarihi: Optional[date] = Query(None),
    bitis_tarihi: Optional[date] = Query(None),
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    # MODEL TUTARLILIĞI DÜZELTME: semalar.StokHareket -> modeller.StokHareket
    query = db.query(modeller.StokHareket).filter(modeller.StokHareket.kullanici_id == kullanici_id)

    if stok_id:
        # KRİTİK DÜZELTME: Yanlış kolon 'stok_id' yerine doğru kolon 'urun_id' kullanıldı.
        query = query.filter(modeller.StokHareket.urun_id == stok_id)
    if islem_tipi:
        query = query.filter(modeller.StokHareket.islem_tipi == islem_tipi)
    if baslangic_tarihi:
        query = query.filter(modeller.StokHareket.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        query = query.filter(modeller.StokHareket.tarih <= bitis_tarihi)

    total = query.count()
    hareketler = query.order_by(modeller.StokHareket.tarih.desc()).offset(skip).limit(limit).all()

    return {"items": hareketler, "total": total}