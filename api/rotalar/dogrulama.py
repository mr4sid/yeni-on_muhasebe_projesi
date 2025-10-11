# api/rotalar/dogrulama.py dosyasının TAMAMI (Master Sorgu Fix)
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload 
from datetime import timedelta
from sqlalchemy.exc import IntegrityError
import logging

from .. import modeller 
from ..veritabani import get_master_db, get_tenant_engine, get_master_engine
from ..guvenlik import create_access_token, verify_password, get_password_hash
from ..config import ACCESS_TOKEN_EXPIRE_MINUTES
from sqlalchemy import text 
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dogrulama", tags=["Kimlik Doğrulama"])


# --- YARDIMCI FONKSİYON: Tenant DB'ye Varsayılan Veri Ekleme (Aynı Kalır) ---
def _add_default_tenant_data(db: Session):
    """Yeni oluşturulan boş tenant veritabanına varsayılan verileri ekler."""
    
    logger.info(f"Yeni Tenant DB için varsayılan veriler ekleniyor.")
    KULLANICI_ID = 1

    try:
        # 1. CARİLER
        perakende_musteri = modeller.Musteri(ad="Perakende Müşterisi", kod="PERAKENDE_MUSTERI", aktif=True, kullanici_id=KULLANICI_ID)
        db.add(perakende_musteri); db.flush()
        db.add(modeller.CariHesap(cari_id=perakende_musteri.id, cari_tip=modeller.CariTipiEnum.MUSTERI.value, bakiye=0.0))
        
        genel_tedarikci = modeller.Tedarikci(ad="Genel Tedarikçi", kod="GENEL_TEDARIKCI", aktif=True, kullanici_id=KULLANICI_ID)
        db.add(genel_tedarikci); db.flush()
        db.add(modeller.CariHesap(cari_id=genel_tedarikci.id, cari_tip=modeller.CariTipiEnum.TEDARIKCI.value, bakiye=0.0))

        # 2. KASA/BANKA
        db.add(modeller.KasaBankaHesap(hesap_adi="NAKİT KASA", tip=modeller.KasaBankaTipiEnum.KASA, bakiye=0.0, para_birimi="TL", aktif=True, kullanici_id=KULLANICI_ID))

        # 3. NİTELİKLER
        nitelik_esleme = {"kategori": modeller.UrunKategori, "marka": modeller.UrunMarka, "urun_grubu": modeller.UrunGrubu, "ulke": modeller.Ulke, "gelir_siniflandirma": modeller.GelirSiniflandirma, "gider_siniflandirma": modeller.GiderSiniflandirma}
        urun_birimleri = ["Adet", "Metre", "Kilogram", "Litre", "Kutu"]
        nitelik_listesi = [("Genel Kategori", "kategori"), ("Genel Marka", "marka"), ("Hizmet", "urun_grubu"), ("Türkiye", "ulke"), ("Satış Geliri", "gelir_siniflandirma"), ("Maaş Gideri", "gider_siniflandirma")]

        for ad in urun_birimleri: db.add(modeller.UrunBirimi(ad=ad, kullanici_id=KULLANICI_ID))
        for ad, tip in nitelik_listesi: 
            Model = nitelik_esleme.get(tip)
            if Model:
                db.add(Model(ad=ad, kullanici_id=KULLANICI_ID))

        db.commit()
        logger.info(f"Varsayılan veriler başarıyla Tenant DB'ye eklendi.")

    except Exception as e:
        db.rollback()
        logger.error(f"Varsayılan veriler Tenant DB'ye eklenirken kritik bir hata oluştu: {e}")
        raise

# --- ROTALAR ---

@router.post("/login", response_model=modeller.OfflineLoginResponse)
def authenticate_user(user_login: modeller.KullaniciLogin, db: Session = Depends(get_master_db)):
    
    # KRİTİK DÜZELTME 1: Sorgu email üzerinden yapılır ve Firma verisi joinedload ile yüklenir.
    user = db.query(modeller.Kullanici).options(
        joinedload(modeller.Kullanici.firma) 
    ).filter(
        modeller.Kullanici.email == user_login.email # KRİTİK: EMAIL ile filtreleme
    ).first()

    if not user or not verify_password(user_login.sifre, user.sifre_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Hatalı e-posta veya şifre.")
    
    # Tenant/Firma bilgisini yükle (joinedload sayesinde user.firma direkt erişilebilir)
    firma_obj = user.firma 
    tenant_db_name = firma_obj.tenant_db_name if firma_obj else None
    firma_adi = firma_obj.firma_adi if firma_obj else None

    # KRİTİK DÜZELTME 2: Firma bilgisi eksikse 401 döndür 
    if not tenant_db_name:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcının Tenant/Firma bilgisi eksik.")

    # JWT'yi email ve tenant_db ile oluştur
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "tenant_db": tenant_db_name}, 
        expires_delta=access_token_expires
    )

    # KRİTİK DÜZELTME 3: Response'ta email ve firma_adi döndürülür
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "kullanici_id": user.id, 
        "email": user.email, 
        "sifre_hash": user.sifre_hash,
        "rol": user.rol,
        "firma_adi": firma_adi,
        "tenant_db_name": tenant_db_name
    }


@router.post("/register", response_model=modeller.KullaniciRead)
def register_user(user_create: modeller.KullaniciCreate, db: Session = Depends(get_master_db)): # Master DB kullanılır
    
    # E-posta/Telefon benzersizliği kontrolü
    if db.query(modeller.Kullanici).filter(
        (modeller.Kullanici.email == user_create.email) | 
        (modeller.Kullanici.telefon == user_create.telefon)
    ).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-posta veya Telefon numarası zaten mevcut.")

    hashed_password = get_password_hash(user_create.sifre)
    
    # Kurucu Personeli Master DB'ye ekle
    db_user = modeller.Kullanici(
        sifre_hash=hashed_password,
        ad=user_create.ad,
        soyad=user_create.soyad,
        email=user_create.email,
        telefon=user_create.telefon,
        rol=user_create.rol
    )
    
    try:
        db.add(db_user)
        db.flush() 
        
        # Firma Kaydı ve Tenant DB Adını Belirle
        tenant_db_name = f"tenant_{db_user.id}_{user_create.firma_adi}".lower().replace(' ', '_')
        
        db_firma = modeller.Firma(
            firma_adi=user_create.firma_adi,
            tenant_db_name=tenant_db_name,
            kurucu_personel_id=db_user.id
        )
        db.add(db_firma)
        
        # Kullanıcıyı Firmaya Bağla
        db_user.firma_id = db_firma.id
        db.commit() # Master DB'ye ilk commit
        
        # Fiziksel Veritabanı Oluşturma
        master_engine = get_master_engine() 
        with master_engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text(f"CREATE DATABASE {tenant_db_name} ENCODING 'UTF8' TEMPLATE template0;")
            )
            conn.commit() # CREATE DATABASE komutu için gerekli
        logger.info(f"Fiziksel Veritabanı oluşturuldu: {tenant_db_name}")

        # Tenant DB'ye Bağlan ve Tabloları/Veriyi Oluştur
        tenant_engine = get_tenant_engine(tenant_db_name)
        from ..modeller import Base as TenantBase 
        TenantBase.metadata.create_all(bind=tenant_engine)
        logger.info(f"Tablolar Tenant DB'ye başarıyla oluşturuldu.")

        # Varsayılan Verileri Yeni Tenant DB'ye Ekle
        TenantSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
        tenant_db = TenantSessionLocal()
        try:
            _add_default_tenant_data(tenant_db) 
        finally:
            tenant_db.close()
        
        db.refresh(db_user)
        user_read = modeller.KullaniciRead.model_validate(db_user, from_attributes=True)
        user_read.firma_adi = db_firma.firma_adi
        return user_read

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Kullanıcı kaydı oluşturulurken IntegrityError: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-posta, Telefon veya Firma adı zaten mevcut."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Kullanıcı kaydı oluşturulurken beklenmedik hata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kullanıcı kaydı oluşturulamadı: {e}"
        )