# api/rotalar/sistem.py dosyasının TAMAMI (DbT Health Check Fix)
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from .. import modeller 
# KRİTİK DÜZELTME 1: get_master_db import edildi
from ..veritabani import get_db as get_tenant_db, reset_db_connection, get_master_db 
from .. import guvenlik

router = APIRouter(prefix="/sistem", tags=["Sistem"])

TENANT_DB_DEPENDENCY = get_tenant_db # Tenant DB dependency (diğer rotalar için)

# HEALTH CHECK ROTASI
@router.get("/status", response_model=dict)
def get_sistem_status(db: Session = Depends(get_master_db)): # KRİTİK DÜZELTME 2: Master DB kullanılır
    try:
        # Master DB bağlantı kontrolü
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Veritabanı bağlantısı kurulamadı! Hata: {e}"
        )
# --- Geriye Kalan Rotalar (DbT Uyumlu Haliyle Aynı Kalır) ---

@router.get("/varsayilan_cariler/perakende_musteri_id", response_model=modeller.DefaultIdResponse)
def get_perakende_musteri_id_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI!
    musteri = db.query(modeller.Musteri).filter(modeller.Musteri.kod == "PERAKENDE_MUSTERI").first()
    if not musteri:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Varsayılan perakende müşteri bulunamadı."
        )
    return {"id": musteri.id}

@router.get("/varsayilan_cariler/genel_tedarikci_id", response_model=modeller.DefaultIdResponse)
def get_genel_tedarikci_id_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI!
    tedarikci = db.query(modeller.Tedarikci).filter(modeller.Tedarikci.kod == "GENEL_TEDARIKCI").first()
    if not tedarikci:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Varsayılan genel tedarikçi bulunamadı."
        )
    return {"id": tedarikci.id}

@router.get("/varsayilan_kasa_banka/{odeme_turu}", response_model=modeller.KasaBankaRead)
def get_varsayilan_kasa_banka_endpoint(
    odeme_turu: str, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    hesap_tipi = None
    varsayilan_ad = None
    
    if odeme_turu.upper() == "NAKİT":
        hesap_tipi = modeller.KasaBankaTipiEnum.KASA
        varsayilan_ad = "NAKİT KASA" # Hardcoded ad
    elif odeme_turu.upper() in ["KART", "EFT/HAVALE", "ÇEK", "SENET"]: 
        hesap_tipi = modeller.KasaBankaTipiEnum.BANKA
        varsayilan_ad = "BANKA" # Varsayılan Banka adı
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Desteklenmeyen ödeme türü: {odeme_turu}. 'NAKİT', 'KART', 'EFT/HAVALE' vb. olmalıdır."
        )

    # Önce tam eşleşme ile bulmaya çalış (NAKİT KASA)
    if odeme_turu.upper() == "NAKİT":
         # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI!
         hesap = db.query(modeller.KasaBankaHesap).filter(
             modeller.KasaBankaHesap.hesap_adi == varsayilan_ad
         ).first()
    else:
         # Nakit dışı tipler için: tipi Banka olan ilk hesabı bul
         # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI!
         hesap = db.query(modeller.KasaBankaHesap).filter(
             modeller.KasaBankaHesap.tip == hesap_tipi
         ).first()

    if not hesap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Varsayılan {odeme_turu} hesabı bulunamadı. Lütfen bir {varsayilan_ad or hesap_tipi.value} hesabı tanımlayın."
        )
    return hesap

@router.get("/bilgiler", response_model=modeller.SirketRead)
def get_sirket_bilgileri_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), 
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI! 
    sirket_bilgisi = db.query(modeller.Sirket).first() 
    if not sirket_bilgisi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Şirket bilgileri bulunamadı. Lütfen şirket bilgilerini kaydedin."
        )
    return sirket_bilgisi

@router.put("/bilgiler", response_model=modeller.SirketRead)
def update_sirket_bilgileri_endpoint(
    sirket_update: modeller.SirketCreate, 
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user), 
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI!
    sirket_bilgisi = db.query(modeller.Sirket).first() 
    if not sirket_bilgisi:
        # Yeni kayıtta kullanici_id Tenant DB'deki Kurucu Personel ID'si olmalıdır (ID: 1)
        db_sirket = modeller.Sirket(**sirket_update.model_dump(), kullanici_id=1) 
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
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI!
    last_fatura = db.query(modeller.Fatura).filter(modeller.Fatura.fatura_turu == fatura_turu.upper()) \
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

@router.get("/next_musteri_code", response_model=modeller.NextCodeResponse)
def get_next_musteri_code_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI!
    last_musteri = db.query(modeller.Musteri).order_by(modeller.Musteri.kod.desc()).first()

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

@router.get("/next_tedarikci_code", response_model=modeller.NextCodeResponse)
def get_next_tedarikci_code_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI!
    last_tedarikci = db.query(modeller.Tedarikci).order_by(modeller.Tedarikci.kod.desc()).first()

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

@router.get("/next_stok_code", response_model=modeller.NextCodeResponse)
def get_next_stok_code_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI!
    last_stok = db.query(modeller.Stok).order_by(modeller.Stok.kod.desc()).first()

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
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(TENANT_DB_DEPENDENCY) # Tenant DB kullanılır
):
    # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI!
    son_siparis = db.query(modeller.Siparis).order_by(modeller.Siparis.id.desc()).first() 
    
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
def get_sistem_status(db: Session = Depends(get_master_db)):
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
    fatura_turu: modeller.FaturaTuruEnum = Query(..., description="Fatura türü (SATIS/ALIŞ)"),
    db: Session = Depends(TENANT_DB_DEPENDENCY), # Tenant DB kullanılır
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # DÜZELTME: IZOLASYON FILTRESI KALDIRILDI!
    last_fatura = db.query(modeller.Fatura).filter(
        modeller.Fatura.fatura_turu == fatura_turu
    ).order_by(modeller.Fatura.fatura_no.desc()).first()

    prefix = ""
    if fatura_turu == modeller.FaturaTuruEnum.SATIS: prefix = "SF" 
    elif fatura_turu == modeller.FaturaTuruEnum.ALIS: prefix = "AF" 
    elif fatura_turu == modeller.FaturaTuruEnum.SATIS_IADE: prefix = "SI" 
    elif fatura_turu == modeller.FaturaTuruEnum.ALIS_IADE: prefix = "AI" 
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