# api/rotalar/sistem.py dosyasının TAMAMI

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from .. import modeller, semalar
from ..veritabani import get_db, reset_db_connection
from .. import guvenlik # KRİTİK: guvenlik modülü eklendi

router = APIRouter(prefix="/sistem", tags=["Sistem"])

@router.get("/varsayilan_cariler/perakende_musteri_id", response_model=modeller.DefaultIdResponse)
def get_perakende_musteri_id_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id
    # KURAL UYGULANDI: Sorgular 'modeller' kullanmalı
    musteri = db.query(modeller.Musteri).filter(modeller.Musteri.kod == "PERAKENDE_MUSTERI", modeller.Musteri.kullanici_id == kullanici_id).first()
    if not musteri:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Varsayılan perakende müşteri bulunamadı."
        )
    return {"id": musteri.id}

@router.get("/varsayilan_cariler/genel_tedarikci_id", response_model=modeller.DefaultIdResponse)
def get_genel_tedarikci_id_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id
    # KURAL UYGULANDI: Sorgular 'modeller' kullanmalı
    tedarikci = db.query(modeller.Tedarikci).filter(modeller.Tedarikci.kod == "GENEL_TEDARIKCI", modeller.Tedarikci.kullanici_id == kullanici_id).first()
    if not tedarikci:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Varsayılan genel tedarikçi bulunamadı."
        )
    return {"id": tedarikci.id}

@router.get("/varsayilan_kasa_banka/{odeme_turu}", response_model=modeller.KasaBankaRead)
def get_varsayilan_kasa_banka_endpoint(
    odeme_turu: str, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # JWT'den user ID geliyor
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id 
    hesap_tipi = None
    if odeme_turu.upper() == "NAKİT":
        hesap_tipi = semalar.KasaBankaTipiEnum.KASA
    elif odeme_turu.upper() in ["KART", "EFT/HAVALE", "ÇEK", "SENET"]:
        hesap_tipi = semalar.KasaBankaTipiEnum.BANKA
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Desteklenmeyen ödeme türü: {odeme_turu}. 'Nakit' veya 'Banka' olmalıdır."
        )

    varsayilan_kod = f"VARSAYILAN_{hesap_tipi.value}_{kullanici_id}"
    
    # Model Tutarlılığı Kuralı (modeller.X) ihlali kontrol ediliyor:
    hesap = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.kod == varsayilan_kod, modeller.KasaBankaHesap.kullanici_id == kullanici_id).first()
    if not hesap:
        hesap = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.tip == hesap_tipi, modeller.KasaBankaHesap.kullanici_id == kullanici_id).first()
    if not hesap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Varsayılan {odeme_turu} hesabı bulunamadı. Lütfen bir {odeme_turu} hesabı tanımlayın."
        )
    return hesap

@router.get("/bilgiler", response_model=modeller.SirketRead)
def get_sirket_bilgileri_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    sirket_bilgisi = db.query(semalar.Sirket).filter(semalar.Sirket.kullanici_id == kullanici_id).first()
    if not sirket_bilgisi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Şirket bilgileri bulunamadı. Lütfen şirket bilgilerini kaydedin."
        )
    return sirket_bilgisi

@router.put("/bilgiler", response_model=modeller.SirketRead)
def update_sirket_bilgileri_endpoint(
    sirket_update: modeller.SirketCreate, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    sirket_bilgisi = db.query(semalar.Sirket).filter(semalar.Sirket.kullanici_id == kullanici_id).first()
    if not sirket_bilgisi:
        sirket_update.kullanici_id = kullanici_id
        db_sirket = semalar.Sirket(**sirket_update.model_dump())
        db.add(db_sirket)
    else:
        for key, value in sirket_update.model_dump(exclude_unset=True).items():
            setattr(sirket_bilgisi, key, value)
    
    db.commit()
    db.refresh(sirket_bilgisi)
    return sirket_bilgisi

@router.get("/next_fatura_number/{fatura_turu}", response_model=modeller.NextFaturaNoResponse)
def get_next_fatura_number_endpoint(
    fatura_turu: str, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), 
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    # GÜNCELLEME: Model Tutarlılığı Kuralı gereği semalar.Fatura yerine modeller.Fatura kullanıldı.
    last_fatura = db.query(modeller.Fatura).filter(modeller.Fatura.fatura_turu == fatura_turu.upper(), modeller.Fatura.kullanici_id == kullanici_id) \
                                       .order_by(modeller.Fatura.fatura_no.desc()).first()

    prefix = ""
    if fatura_turu.upper() == "SATIŞ":
        prefix = "SF"
    elif fatura_turu.upper() == "ALIŞ":
        prefix = "AF"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz fatura türü. 'SATIŞ' veya 'ALIŞ' olmalıdır.")

    next_sequence = 1
    if last_fatura and last_fatura.fatura_no.startswith(prefix):
        try:
            current_sequence_str = last_fatura.fatura_no[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            pass

    next_fatura_no = f"{prefix}{next_sequence:09d}"
    return {"fatura_no": next_fatura_no}

@router.get("/next_musteri_code", response_model=dict)
def get_next_musteri_code_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    last_musteri = db.query(semalar.Musteri).filter(semalar.Musteri.kullanici_id == kullanici_id).order_by(semalar.Musteri.kod.desc()).first()

    prefix = "M"
    next_sequence = 1
    if last_musteri and last_musteri.kod and last_musteri.kod.startswith(prefix):
        try:
            current_sequence_str = last_musteri.kod[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            pass

    next_musteri_code = f"{prefix}{next_sequence:09d}"
    return {"next_code": next_musteri_code}

@router.get("/next_tedarikci_code", response_model=dict)
def get_next_tedarikci_code_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    last_tedarikci = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.kullanici_id == kullanici_id).order_by(semalar.Tedarikci.kod.desc()).first()

    prefix = "T"
    next_sequence = 1
    if last_tedarikci and last_tedarikci.kod and last_tedarikci.kod.startswith(prefix):
        try:
            current_sequence_str = last_tedarikci.kod[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            pass

    next_tedarikci_code = f"{prefix}{next_sequence:09d}"
    return {"next_code": next_tedarikci_code}

@router.get("/next_stok_code", response_model=dict)
def get_next_stok_code_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    last_stok = db.query(semalar.Stok).filter(semalar.Stok.kullanici_id == kullanici_id).order_by(semalar.Stok.kod.desc()).first()

    prefix = "STK"
    next_sequence = 1
    if last_stok and last_stok.kod and last_stok.kod.startswith(prefix):
        try:
            current_sequence_str = last_stok.kod[len(prefix):]
            current_sequence = int(current_sequence_str)
            next_sequence = current_sequence + 1
        except ValueError:
            pass

    next_stok_code = f"{prefix}{next_sequence:09d}"
    return {"next_code": next_stok_code}

@router.get("/next_siparis_kodu", response_model=modeller.NextSiparisKoduResponse)
def get_next_siparis_kodu_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), # KRİTİK DÜZELTME
    db: Session = Depends(get_db)
):
    kullanici_id = current_user.id # JWT'den gelen ID kullanılıyor
    son_siparis = db.query(semalar.Siparis).filter(semalar.Siparis.kullanici_id == kullanici_id).order_by(semalar.Siparis.id.desc()).first()
    
    prefix = "S-"
    next_number = 1
    
    if son_siparis and son_siparis.siparis_no and son_siparis.siparis_no.startswith(prefix):
        try:
            last_number_str = son_siparis.siparis_no.split('-')[1]
            last_number = int(last_number_str)
            next_number = last_number + 1
        except (ValueError, IndexError):
            pass
            
    next_code = f"{prefix}{next_number:06d}"
    return {"next_code": next_code}

@router.get("/status", response_model=dict)
def get_sistem_status(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Veritabanı bağlantısı kurulamadı! Hata: {e}"
        )

@router.post("/veritabani_baglantilarini_kapat")
async def veritabani_baglantilarini_kapat():
    reset_db_connection()
    return PlainTextResponse("Veritabanı bağlantıları başarıyla kapatıldı.")

@router.get("/next_fatura_no", response_model=modeller.NextCodeResponse)
def get_next_fatura_no_endpoint(
    fatura_turu: semalar.FaturaTuruEnum = Query(..., description="Fatura türü (SATIS/ALIŞ)"),
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    
    last_fatura = db.query(modeller.Fatura).filter(
        modeller.Fatura.fatura_turu == fatura_turu,
        modeller.Fatura.kullanici_id == kullanici_id
    ).order_by(modeller.Fatura.fatura_no.desc()).first()

    prefix = ""
    if fatura_turu == semalar.FaturaTuruEnum.SATIS: prefix = "SF"
    elif fatura_turu == semalar.FaturaTuruEnum.ALIS: prefix = "AF"
    elif fatura_turu == semalar.FaturaTuruEnum.SATIS_IADE: prefix = "SI"
    elif fatura_turu == semalar.FaturaTuruEnum.ALIS_IADE: prefix = "AI"
    else: prefix = "DG"

    next_sequence = 1
    if last_fatura and last_fatura.fatura_no and last_fatura.fatura_no.startswith(prefix):
        try:
            current_sequence = int(last_fatura.fatura_no[len(prefix):])
            next_sequence = current_sequence + 1
        except (ValueError, IndexError):
            pass

    next_fatura_no = f"{prefix}{next_sequence:09d}"
    return {"next_code": next_fatura_no}