from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_
from typing import List, Optional, Union
from datetime import datetime, date

from .. import modeller, semalar, guvenlik
from ..veritabani import get_db
from hizmetler import FaturaService
import logging

logger = logging.getLogger(__name__)

siparisler_router = APIRouter(prefix="/siparisler", tags=["Siparişler"])
faturalar_router = APIRouter(prefix="/faturalar", tags=["Faturalar"])
router = APIRouter()
router.include_router(siparisler_router)
router.include_router(faturalar_router)
# --- SİPARİŞLER ENDPOINT'leri ---

@siparisler_router.post("/", response_model=modeller.SiparisRead, status_code=status.HTTP_201_CREATED)
def create_siparis(siparis: modeller.SiparisCreate, db: Session = Depends(get_db), current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)):
    # YENİ: JWT'den gelen kullanıcı ID'sini kullan
    kullanici_id = current_user.id
    
    db_siparis = modeller.Siparis(
        siparis_no=siparis.siparis_no,
        siparis_turu=siparis.siparis_turu,
        durum=siparis.durum,
        tarih=siparis.tarih,
        teslimat_tarihi=siparis.teslimat_tarihi,
        cari_id=siparis.cari_id,
        cari_tip=siparis.cari_tip,
        siparis_notlari=siparis.siparis_notlari,
        genel_iskonto_tipi=siparis.genel_iskonto_tipi,
        genel_iskonto_degeri=siparis.genel_iskonto_degeri,
        fatura_id=siparis.fatura_id,
        kullanici_id=kullanici_id # JWT'den gelen ID
    )

    db.add(db_siparis)
    db.flush() 

    for kalem_data in siparis.kalemler:
        # YENİ: Kalemlere de kullanıcı ID'si eklenmeli (veritabanı şemasında varsa)
        db_kalem = modeller.SiparisKalemi(**kalem_data.model_dump(), siparis_id=db_siparis.id)
        db.add(db_kalem)
    
    db.commit() 
    db.refresh(db_siparis)
    return db_siparis

@siparisler_router.get("/", response_model=modeller.SiparisListResponse)
def read_siparisler(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=0),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # JWT Devri
    arama: str = Query(None),
    cari_id: Optional[int] = None,
    durum: Optional[semalar.SiparisDurumEnum] = None,
    siparis_turu: Optional[semalar.SiparisTuruEnum] = None,
    baslangic_tarih: Optional[date] = None, # str yerine date
    bitis_tarih: Optional[date] = None,   # str yerine date
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id
    query = db.query(modeller.Siparis).filter(modeller.Siparis.kullanici_id == kullanici_id) \
        .options(joinedload(modeller.Siparis.musteri)) \
        .options(joinedload(modeller.Siparis.tedarikci))

    if arama:
        query = query.filter(
            (modeller.Siparis.siparis_no.ilike(f"%{arama}%")) |
            (modeller.Siparis.siparis_notlari.ilike(f"%{arama}%")) |
            (modeller.Musteri.ad.ilike(f"%{arama}%")) | # İlişki üzerinden arama düzeltildi
            (modeller.Tedarikci.ad.ilike(f"%{arama}%")) # İlişki üzerinden arama düzeltildi
        )
    
    if cari_id is not None:
        query = query.filter(modeller.Siparis.cari_id == cari_id)

    if durum is not None:
        query = query.filter(modeller.Siparis.durum == durum)

    if siparis_turu is not None:
        query = query.filter(modeller.Siparis.siparis_turu == siparis_turu)

    if baslangic_tarih:
        query = query.filter(modeller.Siparis.tarih >= baslangic_tarih)

    if bitis_tarih:
        query = query.filter(modeller.Siparis.tarih <= bitis_tarih)

    total_count = query.count()
    siparisler = query.order_by(modeller.Siparis.tarih.desc()).offset(skip).limit(limit).all()

    # Düzeltme: Yanıt modeli için doğru dönüşüm
    items = [modeller.SiparisRead.from_orm(s) for s in siparisler]
    return {"items": items, "total": total_count}

@siparisler_router.delete("/{siparis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_siparis(siparis_id: int, current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), db: Session = Depends(get_db)):
    kullanici_id = current_user.id
    db_siparis = db.query(modeller.Siparis).filter(modeller.Siparis.id == siparis_id, modeller.Siparis.kullanici_id == kullanici_id).first()
    if not db_siparis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş bulunamadı")
    
    # İlişkili kalemler cascade silme ile otomatik silinecektir (modelde tanımlıysa)
    db.delete(db_siparis)
    db.commit()
    return

@siparisler_router.put("/{siparis_id}", response_model=modeller.SiparisRead)
def update_siparis(siparis_id: int, siparis_update: modeller.SiparisUpdate, current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), db: Session = Depends(get_db)):
    kullanici_id = current_user.id
    db_siparis = db.query(modeller.Siparis).filter(modeller.Siparis.id == siparis_id, modeller.Siparis.kullanici_id == kullanici_id).first()
    if not db_siparis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş bulunamadı")
    
    update_data = siparis_update.model_dump(exclude_unset=True, exclude={"kalemler"})
    for key, value in update_data.items():
        setattr(db_siparis, key, value)
    
    if siparis_update.kalemler is not None:
        # Önceki kalemleri sil
        db.query(modeller.SiparisKalemi).filter(modeller.SiparisKalemi.siparis_id == siparis_id).delete()
        # Yeni kalemleri ekle
        for kalem_data in siparis_update.kalemler:
            db_kalem = modeller.SiparisKalemi(**kalem_data.model_dump(), siparis_id=siparis_id)
            db.add(db_kalem)

    db.commit()
    db.refresh(db_siparis)
    return db_siparis

@siparisler_router.get("/{siparis_id}", response_model=modeller.SiparisRead)
def read_siparis(siparis_id: int, current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), db: Session = Depends(get_db)):
    kullanici_id = current_user.id
    siparis = db.query(modeller.Siparis) \
        .options(joinedload(modeller.Siparis.kalemler).joinedload(modeller.SiparisKalemi.urun)) \
        .filter(modeller.Siparis.id == siparis_id, modeller.Siparis.kullanici_id == kullanici_id).first()
    if not siparis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş bulunamadı")
    return siparis

@siparisler_router.post("/{siparis_id}/faturaya_donustur", response_model=modeller.FaturaRead)
def convert_siparis_to_fatura(
    siparis_id: int, 
    fatura_donusum: modeller.SiparisFaturaDonusum,
    db: Session = Depends(get_db)
):
    # MODEL TUTARLILIĞI DÜZELTME: semalar.Siparis -> modeller.Siparis (ORM)
    db_siparis = db.query(modeller.Siparis).filter(modeller.Siparis.id == siparis_id, modeller.Siparis.kullanici_id == fatura_donusum.kullanici_id).first()
    if not db_siparis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş bulunamadı.")
    
    if db_siparis.durum == semalar.SiparisDurumEnum.FATURALASTIRILDI:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sipariş zaten faturalaştırılmış.")
    
    if not db_siparis.kalemler:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Siparişin kalemi bulunmuyor, faturaya dönüştürülemez.")

    fatura_turu_olustur = semalar.FaturaTuruEnum.SATIS if db_siparis.siparis_turu == semalar.SiparisTuruEnum.SATIŞ_SIPARIS else semalar.FaturaTuruEnum.ALIS

    # MODEL TUTARLILIĞI DÜZELTME: semalar.Fatura -> modeller.Fatura (ORM)
    last_fatura = db.query(modeller.Fatura).filter(modeller.Fatura.fatura_turu == fatura_turu_olustur, modeller.Fatura.kullanici_id == fatura_donusum.kullanici_id) \
                                       .order_by(modeller.Fatura.fatura_no.desc()).first()
    
    prefix = "SF" if fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS else "AF"
    next_sequence = 1
    if last_fatura and last_fatura.fatura_no.startswith(prefix):
        try:
            current_sequence_str = last_fatura.fatura_no[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            pass
    
    new_fatura_no = f"{prefix}{next_sequence:09d}"

    # MODEL TUTARLILIĞI DÜZELTME: semalar.Fatura -> modeller.Fatura (ORM)
    db_fatura = modeller.Fatura(
        fatura_no=new_fatura_no,
        fatura_turu=fatura_turu_olustur,
        tarih=datetime.now().date(),
        vade_tarihi=fatura_donusum.vade_tarihi,
        cari_id=db_siparis.cari_id,
        cari_tip=db_siparis.cari_tip, # Siparis modelindeki cari_tip kullanıldı.
        odeme_turu=fatura_donusum.odeme_turu,
        kasa_banka_id=fatura_donusum.kasa_banka_id,
        fatura_notlari=f"Sipariş No: {db_siparis.siparis_no} üzerinden oluşturuldu.",
        genel_iskonto_tipi=db_siparis.genel_iskonto_tipi,
        genel_iskonto_degeri=db_siparis.genel_iskonto_degeri,
        olusturan_kullanici_id=fatura_donusum.olusturan_kullanici_id,
        kullanici_id=fatura_donusum.kullanici_id
    )
    db.add(db_fatura)
    db.flush()

    toplam_kdv_haric_temp = 0.0
    toplam_kdv_dahil_temp = 0.0

    for siparis_kalem in db_siparis.kalemler:
        # MODEL TUTARLILIĞI DÜZELTME: semalar.Stok -> modeller.Stok (ORM)
        urun_info = db.query(modeller.Stok).filter(modeller.Stok.id == siparis_kalem.urun_id, modeller.Stok.kullanici_id == fatura_donusum.kullanici_id).first()
        if not urun_info:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ürün ID {siparis_kalem.urun_id} bulunamadı.")
        
        alis_fiyati_fatura_aninda = urun_info.alis_fiyati

        birim_fiyat_kdv_haric_calc = siparis_kalem.birim_fiyat
        birim_fiyat_kdv_dahil_calc = siparis_kalem.birim_fiyat * (1 + siparis_kalem.kdv_orani / 100)

        fiyat_iskonto_1_sonrasi_dahil = birim_fiyat_kdv_dahil_calc * (1 - siparis_kalem.iskonto_yuzde_1 / 100)
        iskontolu_birim_fiyat_kdv_dahil = fiyat_iskonto_1_sonrasi_dahil * (1 - siparis_kalem.iskonto_yuzde_2 / 100)
        
        if iskontolu_birim_fiyat_kdv_dahil < 0: iskontolu_birim_fiyat_kdv_dahil = 0.0

        iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil / (1 + siparis_kalem.kdv_orani / 100) if siparis_kalem.kdv_orani != 0 else iskontolu_birim_fiyat_kdv_dahil

        kalem_toplam_kdv_haric = iskontolu_birim_fiyat_kdv_haric * siparis_kalem.miktar
        kalem_toplam_kdv_dahil = iskontolu_birim_fiyat_kdv_dahil * siparis_kalem.miktar
        kdv_tutari = kalem_toplam_kdv_dahil - kalem_toplam_kdv_haric

        # MODEL TUTARLILIĞI DÜZELTME: semalar.FaturaKalemi -> modeller.FaturaKalemi (ORM)
        db_fatura_kalem = modeller.FaturaKalemi(
            fatura_id=db_fatura.id,
            urun_id=siparis_kalem.urun_id,
            miktar=siparis_kalem.miktar,
            birim_fiyat=birim_fiyat_kdv_haric_calc,
            kdv_orani=siparis_kalem.kdv_orani,
            alis_fiyati_fatura_aninda=alis_fiyati_fatura_aninda,
            iskonto_yuzde_1=siparis_kalem.iskonto_yuzde_1,
            iskonto_yuzde_2=siparis_kalem.iskonto_yuzde_2,
            iskonto_tipi=siparis_kalem.iskonto_tipi,
            iskonto_degeri=siparis_kalem.iskonto_degeri,
            kullanici_id=fatura_donusum.kullanici_id
        )
        db.add(db_fatura_kalem)

        toplam_kdv_haric_temp += kalem_toplam_kdv_haric
        toplam_kdv_dahil_temp += kalem_toplam_kdv_dahil

        if fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS:
            urun_info.miktar -= siparis_kalem.miktar
            islem_tipi_stok = semalar.StokIslemTipiEnum.SATIŞ
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.ALIS:
            urun_info.miktar += siparis_kalem.miktar
            islem_tipi_stok = semalar.StokIslemTipiEnum.ALIŞ
        else:
            islem_tipi_stok = None

        if islem_tipi_stok:
            db.add(urun_info)

            # MODEL TUTARLILIĞI DÜZELTME: semalar.StokHareket -> modeller.StokHareket (ORM)
            db_stok_hareket = modeller.StokHareket(
                stok_id=siparis_kalem.urun_id,
                tarih=db_fatura.tarih,
                islem_tipi=islem_tipi_stok,
                miktar=siparis_kalem.miktar,
                birim_fiyat=siparis_kalem.birim_fiyat,
                kaynak=semalar.KaynakTipEnum.FATURA,
                kaynak_id=db_fatura.id,
                aciklama=f"{db_fatura.fatura_no} nolu fatura ({fatura_turu_olustur.value})",
                onceki_stok=urun_info.miktar - siparis_kalem.miktar if fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS else urun_info.miktar + siparis_kalem.miktar,
                sonraki_stok=urun_info.miktar,
                kullanici_id=fatura_donusum.kullanici_id
            )
            db.add(db_stok_hareket)

    if db_fatura.genel_iskonto_tipi == "YUZDE" and db_fatura.genel_iskonto_degeri > 0:
        uygulanan_genel_iskonto_tutari = toplam_kdv_haric_temp * (db_fatura.genel_iskonto_degeri / 100)
    elif db_fatura.genel_iskonto_tipi == "TUTAR" and db_fatura.genel_iskonto_degeri > 0:
        uygulanan_genel_iskonto_tutari = db_fatura.genel_iskonto_degeri
    else:
        uygulanan_genel_iskonto_tutari = 0.0
    
    db_fatura.toplam_kdv_haric = toplam_kdv_haric_temp - uygulanan_genel_iskonto_tutari
    db_fatura.toplam_kdv_dahil = toplam_kdv_dahil_temp - uygulanan_genel_iskonto_tutari
    db_fatura.genel_toplam = db_fatura.toplam_kdv_dahil

    db.add(db_fatura)

    if fatura_donusum.odeme_turu == semalar.OdemeTuruEnum.ACIK_HESAP:
        islem_yone_cari = None
        cari_turu = db_siparis.cari_tip

        if fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS:
            islem_yone_cari = semalar.IslemYoneEnum.ALACAK
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.ALIS:
            islem_yone_cari = semalar.IslemYoneEnum.BORC
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS_IADE:
            islem_yone_cari = semalar.IslemYoneEnum.BORC
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.ALIS_IADE:
            islem_yone_cari = semalar.IslemYoneEnum.ALACAK
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.DEVIR_GIRIS:
            islem_yone_cari = semalar.IslemYoneEnum.BORC

        if islem_yone_cari:
            # MODEL TUTARLILIĞI DÜZELTME: semalar.CariHareket -> modeller.CariHareket (ORM)
            db_cari_hareket = modeller.CariHareket(
                cari_id=db_fatura.cari_id,
                cari_tip=cari_turu,
                tarih=db_fatura.tarih,
                islem_turu=db_fatura.fatura_turu.value,
                islem_yone=islem_yone_cari,
                tutar=db_fatura.genel_toplam,
                aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})",
                kaynak=semalar.KaynakTipEnum.FATURA,
                kaynak_id=db_fatura.id,
                odeme_turu=db_fatura.odeme_turu,
                kasa_banka_id=db_fatura.kasa_banka_id,
                vade_tarihi=db_fatura.vade_tarihi,
                kullanici_id=fatura_donusum.kullanici_id
            )
            db.add(db_cari_hareket)

    if fatura_donusum.kasa_banka_id and fatura_donusum.odeme_turu != semalar.OdemeTuruEnum.ACIK_HESAP:
        islem_yone_kasa = None
        if fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS:
            islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.ALIS:
            islem_yone_kasa = semalar.IslemYoneEnum.CIKIS
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.SATIS_IADE:
            islem_yone_kasa = semalar.IslemYoneEnum.CIKIS
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.ALIS_IADE:
            islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
        elif fatura_turu_olustur == semalar.FaturaTuruEnum.DEVIR_GIRIS:
            islem_yone_kasa = semalar.IslemYoneEnum.GIRIS

        if islem_yone_kasa:
            # MODEL TUTARLILIĞI DÜZELTME: semalar.KasaBankaHareket -> modeller.KasaBankaHareket (ORM)
            db_kasa_banka_hareket = modeller.KasaBankaHareket(
                kasa_banka_id=fatura_donusum.kasa_banka_id,
                tarih=db_fatura.tarih,
                islem_turu=fatura_turu_olustur.value,
                islem_yone=islem_yone_kasa,
                tutar=db_fatura.genel_toplam,
                aciklama=f"{db_fatura.fatura_no} nolu fatura ({fatura_turu_olustur.value})",
                kaynak=semalar.KaynakTipEnum.FATURA,
                kaynak_id=db_fatura.id,
                kullanici_id=fatura_donusum.kullanici_id
            )
            db.add(db_kasa_banka_hareket)
            
            # MODEL TUTARLILIĞI DÜZELTME: semalar.KasaBanka -> modeller.KasaBankaHesap (ORM)
            db_kasa_banka = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.id == fatura_donusum.kasa_banka_id, modeller.KasaBankaHesap.kullanici_id == fatura_donusum.kullanici_id).first()
            if db_kasa_banka:
                if islem_yone_kasa == semalar.IslemYoneEnum.GIRIS:
                    db_kasa_banka.bakiye += db_fatura.genel_toplam
                else:
                    db_kasa_banka.bakiye -= db_fatura.genel_toplam
                db.add(db_kasa_banka)

    db_siparis.durum = semalar.SiparisDurumEnum.FATURALASTIRILDI
    db_siparis.fatura_id = db_fatura.id
    db.add(db_siparis)

    db.commit()
    db.refresh(db_fatura)
    return db_fatura

@siparisler_router.get("/{siparis_id}/kalemler", response_model=List[modeller.SiparisKalemiRead])
def get_siparis_kalemleri_endpoint(siparis_id: int, kullanici_id: int = Query(..., description="Kullanıcı ID"), db: Session = Depends(get_db)):
    kalemler = db.query(semalar.SiparisKalemi).options(joinedload(semalar.SiparisKalemi.urun)).filter(semalar.SiparisKalemi.siparis_id == siparis_id, semalar.SiparisKalemi.kullanici_id == kullanici_id).all()
    if not kalemler:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sipariş kalemleri bulunamadı")

    response_kalemler = []
    for kalem in kalemler:
        urun = kalem.urun
        urun_adi = urun.ad if urun else None
        urun_kodu = urun.kod if urun else None

        birim_fiyat_kdv_haric_kalem = kalem.birim_fiyat
        iskontolu_birim_fiyat_kdv_haric_kalem = birim_fiyat_kdv_haric_kalem * (1 - kalem.iskonto_yuzde_1 / 100) * (1 - kalem.iskonto_yuzde_2 / 100)
        iskontolu_birim_fiyat_kdv_dahil_kalem = iskontolu_birim_fiyat_kdv_haric_kalem * (1 + kalem.kdv_orani / 100)
        
        kalem_toplam_kdv_haric = iskontolu_birim_fiyat_kdv_haric_kalem * kalem.miktar
        kalem_toplam_kdv_dahil = iskontolu_birim_fiyat_kdv_dahil_kalem * kalem.miktar
        kdv_tutari = kalem_toplam_kdv_dahil - kalem_toplam_kdv_haric

        kalem_pydantic = modeller.SiparisKalemiRead(
            id=kalem.id,
            siparis_id=kalem.siparis_id,
            urun_id=kalem.urun_id,
            miktar=kalem.miktar,
            birim_fiyat=kalem.birim_fiyat,
            kdv_orani=kalem.kdv_orani,
            alis_fiyati_siparis_aninda=kalem.alis_fiyati_siparis_aninda,
            iskonto_yuzde_1=kalem.iskonto_yuzde_1,
            iskonto_yuzde_2=kalem.iskonto_yuzde_2,
            iskonto_tipi=kalem.iskonto_tipi,
            iskonto_degeri=kalem.iskonto_degeri,
            kalem_toplam_kdv_haric=kalem_toplam_kdv_haric,
            kalem_toplam_kdv_dahil=kalem_toplam_kdv_dahil,
            kdv_tutari=kdv_tutari,
            urun_kodu=urun_kodu,
            urun_adi=urun_adi
        )
        response_kalemler.append(kalem_pydantic)

    return response_kalemler

# --- FATURALAR ENDPOINT'leri ---

@faturalar_router.post("/", response_model=modeller.FaturaRead, status_code=status.HTTP_201_CREATED)
def create_fatura(fatura_data: modeller.FaturaCreate, current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), db: Session = Depends(get_db)):
    db.begin_nested()
    kullanici_id = current_user.id
    
    try:
        if db.query(modeller.Fatura).filter(modeller.Fatura.fatura_no == fatura_data.fatura_no, modeller.Fatura.kullanici_id == kullanici_id).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu fatura numarası zaten mevcut.")
            
        toplam_kdv_haric_calc = 0.0
        toplam_kdv_dahil_calc = 0.0
        
        for kalem in fatura_data.kalemler:
            miktar = kalem.miktar
            birim_fiyat_kdv_haric_orig = kalem.birim_fiyat
            kdv_orani = kalem.kdv_orani
            iskonto_yuzde_1 = kalem.iskonto_yuzde_1
            iskonto_yuzde_2 = kalem.iskonto_yuzde_2

            bf_kdv_dahil_orig = birim_fiyat_kdv_haric_orig * (1 + kdv_orani / 100)
            bf_iskonto_1 = bf_kdv_dahil_orig * (1 - iskonto_yuzde_1 / 100)
            bf_iskontolu_dahil = bf_iskonto_1 * (1 - iskonto_yuzde_2 / 100)

            bf_iskontolu_haric = bf_iskontolu_dahil / (1 + kdv_orani / 100) if kdv_orani != 0 else bf_iskontolu_dahil
            
            toplam_kdv_haric_calc += bf_iskontolu_haric * miktar
            toplam_kdv_dahil_calc += bf_iskontolu_dahil * miktar
            
        genel_iskonto_tutari = 0.0
        if fatura_data.genel_iskonto_tipi == "YUZDE" and fatura_data.genel_iskonto_degeri > 0:
            # Not: Bu hesaplama KDV DAHİL üzerinden yapılıyor, harice çevirmemiz gerekebilir. 
            # Şu anki mantığı koruyorum, ancak maliyet analizinde buna dikkat edilmelidir.
            genel_iskonto_tutari = toplam_kdv_dahil_calc * (fatura_data.genel_iskonto_degeri / 100) 
        elif fatura_data.genel_iskonto_tipi == "TUTAR" and fatura_data.genel_iskonto_degeri > 0:
            genel_iskonto_tutari = fatura_data.genel_iskonto_degeri
            
        genel_toplam_final = toplam_kdv_dahil_calc - genel_iskonto_tutari
        
        # Genel iskonto sonrası KDV hariç toplamı yeniden hesaplayalım (Daha doğru bir yaklaşım)
        if genel_iskonto_tutari > 0:
            # Oran bazında indirim yapıldıysa KDV hariç toplamı bulmak için, KDV dahil genel toplamdan 
            # genel iskonto tutarını düşüp, ardından KDV dahil/hariç oranını kullanmak gerekir.
            # Basitçe, KDV hariç toplamı da aynı oranla düşürelim.
            genel_iskonto_oran_dahil = genel_iskonto_tutari / toplam_kdv_dahil_calc if toplam_kdv_dahil_calc > 0 else 0
            toplam_kdv_haric_iskontolu = toplam_kdv_haric_calc * (1 - genel_iskonto_oran_dahil)
        else:
            toplam_kdv_haric_iskontolu = toplam_kdv_haric_calc

        cari_tip_final = fatura_data.cari_tip # Arayüzden gelen cari_tip'e güveniyoruz.

        fatura_dict = fatura_data.model_dump(exclude_unset=True)
        
        fatura_dict.pop('kalemler', None) 
        fatura_dict.pop('olusturan_kullanici_id', None)
        fatura_dict.pop('kullanici_id', None)
        fatura_dict.pop('original_fatura_id', None) 
        
        db_fatura = modeller.Fatura(
            **fatura_dict,
            kullanici_id=kullanici_id,
            genel_toplam=genel_toplam_final,
            toplam_kdv_haric=toplam_kdv_haric_iskontolu,
            toplam_kdv_dahil=genel_toplam_final, # KDV Dahil toplam, genel toplama eşittir
            toplam_kdv=genel_toplam_final - toplam_kdv_haric_iskontolu
        )
        
        db.add(db_fatura)
        db.flush()

        for kalem_data in fatura_data.kalemler:
            kalem_dict = kalem_data.model_dump()
            db_kalem = modeller.FaturaKalemi(fatura_id=db_fatura.id, **kalem_dict) 
            db.add(db_kalem)
            
            db_stok = db.query(modeller.Stok).filter(modeller.Stok.id == kalem_data.urun_id, modeller.Stok.kullanici_id == kullanici_id).first()
            if not db_stok:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ürün ID {kalem_data.urun_id} bulunamadı.")
            
            stok_miktar_oncesi = db_stok.miktar
            
            if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS:
                db_stok.miktar -= kalem_data.miktar
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS:
                db_stok.miktar += kalem_data.miktar
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE:
                db_stok.miktar += kalem_data.miktar
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE:
                db_stok.miktar -= kalem_data.miktar
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS:
                db_stok.miktar += kalem_data.miktar

            islem_tipi_stok = None
            if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS: islem_tipi_stok = semalar.StokIslemTipiEnum.SATIŞ 
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS: islem_tipi_stok = semalar.StokIslemTipiEnum.ALIŞ 
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE: islem_tipi_stok = semalar.StokIslemTipiEnum.SATIŞ_İADE
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE: islem_tipi_stok = semalar.StokIslemTipiEnum.ALIŞ_İADE
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS: islem_tipi_stok = semalar.StokIslemTipiEnum.GİRİŞ
            
            if islem_tipi_stok:
                db.add(db_stok)
                db_stok_hareket = modeller.StokHareket(
                    urun_id=kalem_data.urun_id, tarih=db_fatura.tarih, islem_tipi=islem_tipi_stok,
                    miktar=kalem_data.miktar, birim_fiyat=kalem_data.birim_fiyat,
                    aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})",
                    kaynak=semalar.KaynakTipEnum.FATURA, kaynak_id=db_fatura.id,
                    onceki_stok=stok_miktar_oncesi, sonraki_stok=db_stok.miktar,
                    kullanici_id=kullanici_id
                )
                db.add(db_stok_hareket)

        # 1. CARI HAREKET - FATURA KAYDI (Borç/Alacak Oluşturma)
        # Ödeme türü ne olursa olsun, ekstrede faturanın kendisinin görünmesi için bu hareket oluşturulur.
        # AÇIK HESAP ise bakiye bu hareketle değişir, değilse 2. hareketle hemen dengelenir.
        if db_fatura.cari_id:
            islem_yone_fatura = None
            if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS: 
                islem_yone_fatura = semalar.IslemYoneEnum.ALACAK # Müşteriden Alacak
            elif db_fatura.fatura_turu in [semalar.FaturaTuruEnum.ALIS, semalar.FaturaTuruEnum.SATIS_IADE, semalar.FaturaTuruEnum.DEVIR_GIRIS]: 
                islem_yone_fatura = semalar.IslemYoneEnum.BORC # Tedarikçiye Borç / Müşteriye Borç (İade)
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE: 
                islem_yone_fatura = semalar.IslemYoneEnum.ALACAK # Tedarikçiden Alacak (İade)
                
            if islem_yone_fatura:
                # Cari tipini belirleyelim (Fatura modelindeki cari_tip kullanıldı)
                cari_tip_fatura_kaydi = cari_tip_final.value if cari_tip_final else db_fatura.cari_tip # Fatura modelindeki Enum değeri
                
                fatura_cari_hareket = modeller.CariHareket(
                    cari_id=db_fatura.cari_id, cari_tip=cari_tip_fatura_kaydi, tarih=db_fatura.tarih,
                    islem_turu=semalar.KaynakTipEnum.FATURA.value, islem_yone=islem_yone_fatura,
                    tutar=db_fatura.genel_toplam, aciklama=f"{db_fatura.fatura_no} nolu Fatura Kaydı ({db_fatura.fatura_turu.value})",
                    kaynak=semalar.KaynakTipEnum.FATURA, kaynak_id=db_fatura.id,
                    odeme_turu=db_fatura.odeme_turu, vade_tarihi=db_fatura.vade_tarihi,
                    kullanici_id=kullanici_id
                )
                db.add(fatura_cari_hareket)

        # 2. CARI HAREKET ve KASA/BANKA HAREKETİ - Ödeme/Tahsilat (Sadece ACIK_HESAP olmayanlar için)
        if fatura_data.odeme_turu != semalar.OdemeTuruEnum.ACIK_HESAP and fatura_data.kasa_banka_id:
            
            # 2a. CARI HAREKET - Ödeme/Tahsilat Kaydı (Fatura Kaydını Kapatır)
            if db_fatura.cari_id and islem_yone_fatura:
                islem_yone_odeme = None
                if islem_yone_fatura == semalar.IslemYoneEnum.ALACAK: 
                    islem_yone_odeme = semalar.IslemYoneEnum.BORC # Alacağı kapattık (tahsilat)
                elif islem_yone_fatura == semalar.IslemYoneEnum.BORC: 
                    islem_yone_odeme = semalar.IslemYoneEnum.ALACAK # Borcu kapattık (ödeme)

                if islem_yone_odeme:
                    # Cari tipini belirleyelim (Fatura modelindeki cari_tip kullanıldı)
                    cari_tip_odeme_kaydi = cari_tip_final.value if cari_tip_final else db_fatura.cari_tip
                    
                    odeme_cari_hareket = modeller.CariHareket(
                        cari_id=db_fatura.cari_id, cari_tip=cari_tip_odeme_kaydi, tarih=db_fatura.tarih,
                        islem_turu=db_fatura.odeme_turu.value, # İşlem Türü: NAKIT, KREDI_KARTI vb.
                        islem_yone=islem_yone_odeme,
                        tutar=db_fatura.genel_toplam, aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.odeme_turu.value}) ile ödendi/tahsil edildi",
                        kaynak=semalar.KaynakTipEnum.FATURA,
                        kaynak_id=db_fatura.id,
                        odeme_turu=db_fatura.odeme_turu,
                        kasa_banka_id=db_fatura.kasa_banka_id,
                        kullanici_id=kullanici_id
                    )
                    db.add(odeme_cari_hareket)

            # 2b. KASA/BANKA HAREKETİ ve Bakiye Güncelleme
            islem_yone_kasa = None
            if db_fatura.fatura_turu in [semalar.FaturaTuruEnum.SATIS, semalar.FaturaTuruEnum.ALIS_IADE, semalar.FaturaTuruEnum.DEVIR_GIRIS]: 
                islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
            elif db_fatura.fatura_turu in [semalar.FaturaTuruEnum.ALIS, semalar.FaturaTuruEnum.SATIS_IADE]: 
                islem_yone_kasa = semalar.IslemYoneEnum.CIKIS

            if islem_yone_kasa:
                db_kasa_banka_hareket = modeller.KasaBankaHareket(
                    kasa_banka_id=fatura_data.kasa_banka_id, tarih=db_fatura.tarih,
                    islem_turu=db_fatura.fatura_turu.value, islem_yone=islem_yone_kasa,
                    tutar=db_fatura.genel_toplam, aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})",
                    kaynak=semalar.KaynakTipEnum.FATURA, kaynak_id=db_fatura.id,
                    kullanici_id=kullanici_id
                )
                db.add(db_kasa_banka_hareket)
                
                db_kasa_banka = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.id == fatura_data.kasa_banka_id, modeller.KasaBankaHesap.kullanici_id == kullanici_id).first()
                if db_kasa_banka:
                    if islem_yone_kasa == semalar.IslemYoneEnum.GIRIS:
                        db_kasa_banka.bakiye += db_fatura.genel_toplam
                    else:
                        db_kasa_banka.bakiye -= db_fatura.genel_toplam
                    db.add(db_kasa_banka)

        db.commit()
        db.refresh(db_fatura)
        
        return db_fatura
    except Exception as e:
        db.rollback()
        logger.error(f"Fatura oluşturulurken hata: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fatura oluşturulurken hata: {str(e)}")
    
@faturalar_router.get("/", response_model=modeller.FaturaListResponse) 
@faturalar_router.get("", response_model=modeller.FaturaListResponse)
def read_faturalar(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000000),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    arama: str = Query(None, min_length=1, max_length=50),
    fatura_turu: Optional[semalar.FaturaTuruEnum] = Query(None),
    baslangic_tarihi: date = Query(None),
    bitis_tarihi: date = Query(None),
    cari_id: int = Query(None),
    odeme_turu: Optional[semalar.OdemeTuruEnum] = Query(None),
    kasa_banka_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id 

    query = db.query(modeller.Fatura).filter(modeller.Fatura.kullanici_id == kullanici_id) \
                                   .join(modeller.Musteri, modeller.Fatura.cari_id == modeller.Musteri.id, isouter=True) \
                                   .join(modeller.Tedarikci, modeller.Fatura.cari_id == modeller.Tedarikci.id, isouter=True)

    if arama:
        query = query.filter(
            (modeller.Fatura.fatura_no.ilike(f"%{arama}%")) |
            (modeller.Musteri.ad.ilike(f"%{arama}%")) | 
            (modeller.Tedarikci.ad.ilike(f"%{arama}%")) |
            (modeller.Fatura.misafir_adi.ilike(f"%{arama}%"))
        )
    
    if fatura_turu:
        query = query.filter(modeller.Fatura.fatura_turu == fatura_turu)
    
    if baslangic_tarihi:
        query = query.filter(modeller.Fatura.tarih >= baslangic_tarihi)
    
    if bitis_tarihi:
        query = query.filter(modeller.Fatura.tarih <= bitis_tarihi)
    
    if cari_id:
        query = query.filter(modeller.Fatura.cari_id == cari_id)

    if odeme_turu:
        query = query.filter(modeller.Fatura.odeme_turu == odeme_turu)
        
    if kasa_banka_id:
        query = query.filter(modeller.Fatura.kasa_banka_id == kasa_banka_id)

    total_count = query.count()
    faturalar = query.order_by(modeller.Fatura.tarih.desc()).offset(skip).limit(limit).all()

    return {"items": [
        modeller.FaturaRead.model_validate(fatura, from_attributes=True)
        for fatura in faturalar
    ], "total": total_count}

@faturalar_router.get("/{fatura_id}", response_model=modeller.FaturaRead)
def read_fatura(fatura_id: int, current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), db: Session = Depends(get_db)):
    fatura = db.query(modeller.Fatura).filter(modeller.Fatura.id == fatura_id, modeller.Fatura.kullanici_id == current_user.id).first()
    if not fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadı")
    return fatura

@faturalar_router.put("/{fatura_id}", response_model=modeller.FaturaRead)
def update_fatura(fatura_id: int, fatura: modeller.FaturaUpdate, current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), db: Session = Depends(get_db)):
    # KRİTİK DÜZELTME: kullanici_id Query parametresi kaldırıldı.
    kullanici_id = current_user.id
    db_fatura = db.query(modeller.Fatura).filter(modeller.Fatura.id == fatura_id, modeller.Fatura.kullanici_id == kullanici_id).first()
    if not db_fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadı")
    
    db.begin_nested()

    try:
        # DÜZELTME: Tüm sorgularda modeller kullanıldı ve Enumlar düzeltildi.
        old_kalemler = db.query(modeller.FaturaKalemi).filter(modeller.FaturaKalemi.fatura_id == fatura_id, modeller.FaturaKalemi.kullanici_id == kullanici_id).all()

        for old_kalem in old_kalemler:
            stok = db.query(modeller.Stok).filter(modeller.Stok.id == old_kalem.urun_id, modeller.Stok.kullanici_id == kullanici_id).first()
            if stok:
                if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS:
                    stok.miktar += old_kalem.miktar
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS:
                    stok.miktar -= old_kalem.miktar
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE:
                    stok.miktar -= old_kalem.miktar
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE:
                    stok.miktar += old_kalem.miktar
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS:
                    stok.miktar -= old_kalem.miktar
                db.add(stok)

            db.query(modeller.StokHareket).filter(
                and_(
                    modeller.StokHareket.kaynak == semalar.KaynakTipEnum.FATURA,
                    modeller.StokHareket.kaynak_id == fatura_id,
                    modeller.StokHareket.stok_id == old_kalem.urun_id,
                    modeller.StokHareket.kullanici_id == kullanici_id
                )
            ).delete(synchronize_session=False)

        db.query(modeller.CariHareket).filter(
            and_(
                modeller.CariHareket.kaynak == semalar.KaynakTipEnum.FATURA,
                modeller.CariHareket.kaynak_id == fatura_id,
                modeller.CariHareket.kullanici_id == kullanici_id
            )
        ).delete(synchronize_session=False)
        
        db.query(modeller.KasaBankaHareket).filter(
            and_(
                modeller.KasaBankaHareket.kaynak == semalar.KaynakTipEnum.FATURA,
                modeller.KasaBankaHareket.kaynak_id == fatura_id,
                modeller.KasaBankaHareket.kullanici_id == kullanici_id
            )
        ).delete(synchronize_session=False)

        old_cari_hareketler = db.query(modeller.CariHareket).filter(
            and_(
                modeller.CariHareket.kaynak == modeller.KaynakTipEnum.FATURA,
                modeller.CariHareket.kaynak_id == fatura_id,
                modeller.CariHareket.kullanici_id == kullanici_id
            )
        ).all()
        for old_cari_hareket in old_cari_hareketler:
            db.delete(old_cari_hareket)

        old_kasa_banka_hareketler = db.query(semalar.KasaBankaHareket).filter(
            and_(
                semalar.KasaBankaHareket.kaynak == semalar.KaynakTipEnum.FATURA,
                semalar.KasaBankaHareket.kaynak_id == fatura_id,
                semalar.KasaBankaHareket.kullanici_id == kullanici_id
            )
        ).all()
        for old_kasa_banka_hareket in old_kasa_banka_hareketler:
            kasa_banka = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == old_kasa_banka_hareket.kasa_banka_id, semalar.KasaBanka.kullanici_id == kullanici_id).first()
            if kasa_banka:
                if old_kasa_banka_hareket.islem_yone == semalar.IslemYoneEnum.GIRIS:
                    kasa_banka.bakiye -= old_kasa_banka_hareket.tutar
                elif old_kasa_banka_hareket.islem_yone == semalar.IslemYoneEnum.CIKIS:
                    kasa_banka.bakiye += old_kasa_banka_hareket.tutar
                db.add(kasa_banka)
            db.delete(old_kasa_banka_hareket)

        db.query(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.fatura_id == fatura_id, semalar.FaturaKalemi.kullanici_id == kullanici_id).delete(synchronize_session=False)

        update_data = fatura.model_dump(exclude_unset=True, exclude={"kalemler"})
        for key, value in update_data.items():
            setattr(db_fatura, key, value)
        
        new_toplam_kdv_haric_temp = 0.0
        new_toplam_kdv_dahil_temp = 0.0
        for kalem_data in fatura.kalemler or []:
            birim_fiyat_kdv_haric_temp = kalem_data.birim_fiyat
            if kalem_data.kdv_orani > 0:
                birim_fiyat_kdv_dahil_temp_calc = kalem_data.birim_fiyat * (1 + kalem_data.kdv_orani / 100)
            else:
                birim_fiyat_kdv_dahil_temp_calc = kalem_data.birim_fiyat

            fiyat_iskonto_1_sonrasi_dahil = birim_fiyat_kdv_dahil_temp_calc * (1 - kalem_data.iskonto_yuzde_1 / 100)
            iskontolu_birim_fiyat_kdv_dahil = fiyat_iskonto_1_sonrasi_dahil * (1 - kalem_data.iskonto_yuzde_2 / 100)
            
            if iskontolu_birim_fiyat_kdv_dahil < 0: iskontolu_birim_fiyat_kdv_dahil = 0.0

            if kalem_data.kdv_orani > 0:
                iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil / (1 + kalem_data.kdv_orani / 100)
            else:
                iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil

            new_toplam_kdv_haric_temp += iskontolu_birim_fiyat_kdv_haric * kalem_data.miktar
            new_toplam_kdv_dahil_temp += iskontolu_birim_fiyat_kdv_dahil * kalem_data.miktar

        if db_fatura.genel_iskonto_tipi == "YUZDE" and db_fatura.genel_iskonto_degeri > 0:
            uygulanan_genel_iskonto_tutari_yeni = new_toplam_kdv_haric_temp * (db_fatura.genel_iskonto_degeri / 100)
        elif db_fatura.genel_iskonto_tipi == "TUTAR" and db_fatura.genel_iskonto_degeri > 0:
            uygulanan_genel_iskonto_tutari_yeni = db_fatura.genel_iskonto_degeri
        else:
            uygulanan_genel_iskonto_tutari_yeni = 0.0
        
        db_fatura.toplam_kdv_haric = new_toplam_kdv_haric_temp - uygulanan_genel_iskonto_tutari_yeni
        db_fatura.toplam_kdv_dahil = new_toplam_kdv_dahil_temp - uygulanan_genel_iskonto_tutari_yeni
        db_fatura.genel_toplam = db_fatura.toplam_kdv_dahil
        db_fatura.son_guncelleme_tarihi_saat = datetime.now()
        db_fatura.son_guncelleyen_kullanici_id = kullanici_id

        db.add(db_fatura)

        for kalem_data in fatura.kalemler or []:
            db_kalem = semalar.FaturaKalemi(fatura_id=db_fatura.id, **kalem_data.model_dump(), kullanici_id=kullanici_id)
            db.add(db_kalem)

            db_stok = db.query(semalar.Stok).filter(semalar.Stok.id == kalem_data.urun_id, semalar.Stok.kullanici_id == kullanici_id).first()
            if db_stok:
                miktar_degisimi = kalem_data.miktar
                islem_tipi = None

                if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIŞ:
                    db_stok.miktar -= miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.SATIŞ
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS:
                    db_stok.miktar += miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.ALIŞ
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE:
                    db_stok.miktar += miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.SATIŞ_İADE
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE:
                    db_stok.miktar -= miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.ALIŞ_İADE
                elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS:
                    db_stok.miktar += miktar_degisimi
                    islem_tipi = semalar.StokIslemTipiEnum.GİRİŞ

                if islem_tipi:
                    db.add(db_stok)

                    db_stok_hareket = semalar.StokHareket(
                        stok_id=kalem_data.urun_id,
                        tarih=db_fatura.tarih,
                        islem_tipi=islem_tipi,
                        miktar=miktar_degisimi,
                        birim_fiyat=kalem_data.birim_fiyat,
                        kaynak=semalar.KaynakTipEnum.FATURA,
                        kaynak_id=db_fatura.id,
                        aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})",
                        onceki_stok=db_stok.miktar - miktar_degisimi if islem_tipi in [semalar.StokIslemTipiEnum.SATIŞ, semalar.StokIslemTipiEnum.ALIŞ_İADE] else db_stok.miktar + miktar_degisimi,
                        sonraki_stok=db_stok.miktar,
                        kullanici_id=kullanici_id
                    )
                    db.add(db_stok_hareket)

        if db_fatura.cari_id:
            islem_yone_cari = None
            cari_turu = None

            if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIŞ:
                islem_yone_cari = semalar.IslemYoneEnum.ALACAK
                cari_turu = semalar.CariTipiEnum.MUSTERI
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS:
                islem_yone_cari = semalar.IslemYoneEnum.BORC
                cari_turu = semalar.CariTipiEnum.TEDARIKCI
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE:
                islem_yone_cari = semalar.IslemYoneEnum.BORC
                cari_turu = semalar.CariTipiEnum.MUSTERI
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE:
                islem_yone_cari = semalar.IslemYoneEnum.ALACAK
                cari_turu = semalar.CariTipiEnum.TEDARIKCI
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS:
                islem_yone_cari = semalar.IslemYoneEnum.BORC
                cari_turu = semalar.CariTipiEnum.TEDARIKCI

            if islem_yone_cari and cari_turu:
                db_cari_hareket = semalar.CariHareket(
                    cari_id=db_fatura.cari_id,
                    cari_turu=cari_turu,
                    tarih=db_fatura.tarih,
                    islem_turu=semalar.KaynakTipEnum.FATURA.value,
                    islem_yone=islem_yone_cari,
                    tutar=db_fatura.genel_toplam,
                    aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})",
                    kaynak=semalar.KaynakTipEnum.FATURA,
                    kaynak_id=db_fatura.id,
                    odeme_turu=db_fatura.odeme_turu,
                    vade_tarihi=db_fatura.vade_tarihi,
                    kullanici_id=kullanici_id
                )
                db.add(db_cari_hareket)

        if db_fatura.odeme_turu != semalar.OdemeTuruEnum.ACIK_HESAP and db_fatura.kasa_banka_id:
            islem_yone_kasa = None
            if db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIŞ:
                islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS:
                islem_yone_kasa = semalar.IslemYoneEnum.CIKIS
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE:
                islem_yone_kasa = semalar.IslemYoneEnum.CIKIS
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE:
                islem_yone_kasa = semalar.IslemYoneEnum.GIRIS
            elif db_fatura.fatura_turu == semalar.FaturaTuruEnum.DEVIR_GIRIS:
                islem_yone_kasa = semalar.IslemYoneEnum.GIRIS

            if islem_yone_kasa:
                db_kasa_banka_hareket = semalar.KasaBankaHareket(
                    kasa_banka_id=db_fatura.kasa_banka_id,
                    tarih=db_fatura.tarih,
                    islem_turu=db_fatura.fatura_turu.value,
                    islem_yone=islem_yone_kasa,
                    tutar=db_fatura.genel_toplam,
                    aciklama=f"{db_fatura.fatura_no} nolu fatura ({db_fatura.fatura_turu.value})",
                    kaynak=semalar.KaynakTipEnum.FATURA,
                    kaynak_id=db_fatura.id,
                    kullanici_id=kullanici_id
                )
                db.add(db_kasa_banka_hareket)
                
                db_kasa_banka = db.query(semalar.KasaBanka).filter(semalar.KasaBanka.id == db_fatura.kasa_banka_id, semalar.KasaBanka.kullanici_id == kullanici_id).first()
                if db_kasa_banka:
                    if islem_yone_kasa == semalar.IslemYoneEnum.GIRIS:
                        db_kasa_banka.bakiye += db_fatura.genel_toplam
                    else:
                        db_kasa_banka.bakiye -= db_fatura.genel_toplam
                    db.add(db_kasa_banka)

        db.commit()
        db.refresh(db_fatura)
        return db_fatura

    except Exception as e:  
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Fatura güncellenirken bir hata oluştu")

@faturalar_router.delete("/{fatura_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fatura(fatura_id: int, current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), db: Session = Depends(get_db)):
    # GÜVENLİK KURALI UYGULANDI: kullanici_id parametresi kaldırıldı, JWT'den alınıyor.
    kullanici_id = current_user.id
    db_fatura = db.query(modeller.Fatura).filter(modeller.Fatura.id == fatura_id, modeller.Fatura.kullanici_id == kullanici_id).first()
    if not db_fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadı")
    
    try:
        db.begin_nested()
        
        # 1. FATURA KALEMLERİNİ SİL (FaturaKalemi.kullanici_id filtresi kaldırıldı)
        db.query(modeller.FaturaKalemi).filter(modeller.FaturaKalemi.fatura_id == fatura_id).delete(synchronize_session=False)

        # 2. STOK HAREKETLERİNİ GERİ AL ve STOK MİKTARINI DÜZELT
        stok_hareketleri = db.query(modeller.StokHareket).filter(
            and_(
                modeller.StokHareket.kaynak == semalar.KaynakTipEnum.FATURA,
                modeller.StokHareket.kaynak_id == fatura_id,
                modeller.StokHareket.kullanici_id == kullanici_id
            )
        ).all()
        for hareket in stok_hareketleri:
            # KRİTİK DÜZELTME: hareket.stok_id yerine hareket.urun_id kullanıldı
            stok = db.query(modeller.Stok).filter(modeller.Stok.id == hareket.urun_id, modeller.Stok.kullanici_id == kullanici_id).first()
            if stok:
                # Stok geri alma mantığı (İşlem tipini tersine çeviriyoruz)
                if hareket.islem_tipi == semalar.StokIslemTipiEnum.SATIŞ:
                    stok.miktar += hareket.miktar
                elif hareket.islem_tipi == semalar.StokIslemTipiEnum.ALIŞ:
                    stok.miktar -= hareket.miktar
                elif hareket.islem_tipi == semalar.StokIslemTipiEnum.SATIŞ_İADE:
                    stok.miktar -= hareket.miktar
                elif hareket.islem_tipi == semalar.StokIslemTipiEnum.ALIŞ_İADE:
                    stok.miktar += hareket.miktar
                elif hareket.islem_tipi == semalar.StokIslemTipiEnum.GİRİŞ: # DEVIR_GIRIS
                    stok.miktar -= hareket.miktar
                db.add(stok)
            db.delete(hareket)

        # 3. CARİ HAREKETLERİ SİL
        cari_hareketleri = db.query(modeller.CariHareket).filter(
            and_(
                modeller.CariHareket.kaynak == semalar.KaynakTipEnum.FATURA,
                modeller.CariHareket.kaynak_id == fatura_id,
                modeller.CariHareket.kullanici_id == kullanici_id
            )
        ).all()
        for hareket in cari_hareketleri:
            db.delete(hareket)
        
        # 4. KASA/BANKA HAREKETLERİNİ GERİ AL ve BAKİYEYİ DÜZELT
        kasa_banka_hareketleri = db.query(modeller.KasaBankaHareket).filter(
            and_(
                modeller.KasaBankaHareket.kaynak == semalar.KaynakTipEnum.FATURA,
                modeller.KasaBankaHareket.kaynak_id == fatura_id,
                modeller.KasaBankaHareket.kullanici_id == kullanici_id
            )
        ).all()
        for hareket in kasa_banka_hareketleri:
            kasa_banka = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.id == hareket.kasa_banka_id, modeller.KasaBankaHesap.kullanici_id == kullanici_id).first()
            if kasa_banka:
                # Kasa bakiye düzeltme mantığı
                if hareket.islem_yone == semalar.IslemYoneEnum.GIRIS:
                    kasa_banka.bakiye -= hareket.tutar # Girişi geri al
                elif hareket.islem_yone == semalar.IslemYoneEnum.CIKIS:
                    kasa_banka.bakiye += hareket.tutar # Çıkışı geri al
                db.add(kasa_banka)
            db.delete(hareket)

        # 5. ANA FATURAYI SİL
        db.delete(db_fatura)
        db.commit()
        return

    except Exception as e:
        db.rollback()
        logger.error(f"Fatura silinirken kritik hata: {e}", exc_info=True) 
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fatura silinirken bir hata oluştu: {str(e)}")

@faturalar_router.get("/get_next_fatura_number", response_model=modeller.NextFaturaNoResponse)
def get_next_fatura_number_endpoint(
    fatura_turu: str = Query(..., description="Fatura türünün Enum üye adı (örn: SATIS, ALIS)"),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id

    try:
        fatura_turu_enum = semalar.FaturaTuruEnum[fatura_turu.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Geçersiz fatura türü: '{fatura_turu}'. Beklenenler: SATIS, ALIS, SATIS_IADE, ALIS_IADE, DEVIR_GIRIS"
        )

    last_fatura = db.query(modeller.Fatura).filter(
        modeller.Fatura.fatura_turu == fatura_turu_enum,
        modeller.Fatura.kullanici_id == kullanici_id
    ).order_by(modeller.Fatura.fatura_no.desc()).first()

    prefix = ""
    if fatura_turu_enum == semalar.FaturaTuruEnum.SATIS: prefix = "SF"
    elif fatura_turu_enum == semalar.FaturaTuruEnum.ALIS: prefix = "AF"
    elif fatura_turu_enum == semalar.FaturaTuruEnum.SATIS_IADE: prefix = "SI"
    elif fatura_turu_enum == semalar.FaturaTuruEnum.ALIS_IADE: prefix = "AI"
    else: prefix = "DG"

    next_sequence = 1
    if last_fatura and last_fatura.fatura_no.startswith(prefix):
        try:
            current_sequence = int(last_fatura.fatura_no[len(prefix):])
            next_sequence = current_sequence + 1
        except (ValueError, IndexError):
            pass

    next_fatura_no = f"{prefix}{next_sequence:09d}"
    return {"fatura_no": next_fatura_no}

@faturalar_router.get("/{fatura_id}/kalemler", response_model=List[modeller.FaturaKalemiRead])
def get_fatura_kalemleri_endpoint(
    fatura_id: int,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id
    fatura = db.query(modeller.Fatura).filter(modeller.Fatura.id == fatura_id, modeller.Fatura.kullanici_id == kullanici_id).first()
    if not fatura:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadı")

    fatura_kalemleri_query = (
        db.query(semalar.FaturaKalemi, semalar.Stok)
        .join(semalar.Stok, semalar.FaturaKalemi.urun_id == semalar.Stok.id)
        .filter(semalar.FaturaKalemi.fatura_id == fatura_id, semalar.FaturaKalemi.kullanici_id == kullanici_id)
        .order_by(semalar.FaturaKalemi.id)
    )
    
    kalemler = []
    for kalem, stok in fatura_kalemleri_query.all():
        kalem_dict = kalem.__dict__.copy()
        kalem_dict.update({
            "urun_adi": stok.ad,
            "urun_kodu": stok.kod
        })
        
        birim_fiyat_kdv_haric_kalem = kalem.birim_fiyat
        iskontolu_birim_fiyat_kdv_haric_kalem = birim_fiyat_kdv_haric_kalem * (1 - kalem.iskonto_yuzde_1 / 100) * (1 - kalem.iskonto_yuzde_2 / 100)
        iskontolu_birim_fiyat_kdv_dahil_kalem = iskontolu_birim_fiyat_kdv_haric_kalem * (1 + kalem.kdv_orani / 100)
        
        kalem_dict["kdv_tutari"] = (iskontolu_birim_fiyat_kdv_dahil_kalem - iskontolu_birim_fiyat_kdv_haric_kalem) * kalem.miktar
        kalem_dict["kalem_toplam_kdv_haric"] = iskontolu_birim_fiyat_kdv_haric_kalem * kalem.miktar
        kalem_dict["kalem_toplam_kdv_dahil"] = iskontolu_birim_fiyat_kdv_dahil_kalem * kalem.miktar
        
        kalemler.append(modeller.FaturaKalemiRead.model_validate(kalem_dict, from_attributes=True))

    if not kalemler:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura kalemleri bulunamadı")

    return kalemler

@faturalar_router.get("/urun_faturalari", response_model=modeller.FaturaListResponse)
def get_urun_faturalari_endpoint(
    urun_id: int,
    fatura_turu: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(semalar.Fatura).join(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.urun_id == urun_id)

    if fatura_turu:
        query = query.filter(semalar.Fatura.fatura_turu == fatura_turu.upper())
    
    faturalar = query.distinct(semalar.Fatura.id).order_by(semalar.Fatura.tarih.desc()).all()

    if not faturalar:
        return {"items": [], "total": 0}
    
    return {"items": [
        modeller.FaturaRead.model_validate(fatura, from_attributes=True)
        for fatura in faturalar
    ], "total": len(faturalar)}