# api/rotalar/dogrulama.py dosyasının Dosyasının tam ve güncel içeriğidir.
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload 
from datetime import timedelta
from sqlalchemy.exc import IntegrityError
import logging

from .. import modeller, semalar
from ..veritabani import get_master_db, get_tenant_engine, get_master_engine, get_tenant_session_by_name
from ..guvenlik import create_access_token, verify_password, get_password_hash
from ..config import settings
from sqlalchemy import text 
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dogrulama", tags=["Kimlik Doğrulama"])


# --- YARDIMCI FONKSİYON: Tenant DB'ye Varsayılan Veri Ekleme (Aynı Kalır) ---
def _add_default_tenant_data(db: Session, olusturan_kullanici_id: int):
    """Yeni oluşturulan boş tenant veritabanına varsayılan verileri ekler."""
    
    logger.info(f"Yeni Tenant DB için varsayılan veriler ekleniyor. Master Kullanıcı ID: {olusturan_kullanici_id}")

    try:
        master_db = next(get_master_db())
        kurucu_kullanici = master_db.query(modeller.Kullanici).filter(modeller.Kullanici.id == olusturan_kullanici_id).first()
        master_db.close()

        if not kurucu_kullanici:
            raise Exception(f"Master DB'de ID'si {olusturan_kullanici_id} olan kurucu kullanıcı bulunamadı.")

        # --- KRİTİK DEĞİŞİKLİK: firma_id olmadan kullanıcı oluşturma ---
        # Tenant DB içindeki kullanıcının firma ile bir bağlantısı yoktur.
        tenant_ilk_kullanici = modeller.Kullanici(
            id=1, 
            ad=kurucu_kullanici.ad,
            soyad=kurucu_kullanici.soyad,
            email=kurucu_kullanici.email,
            sifre_hash=kurucu_kullanici.sifre_hash,
            rol="yonetici"
            # firma_id BURADAN KALDIRILDI!
        )
        db.add(tenant_ilk_kullanici)
        db.commit()
        db.refresh(tenant_ilk_kullanici)
        logger.info(f"Tenant DB için ilk kullanıcı '{tenant_ilk_kullanici.email}' ID=1 ile başarıyla oluşturuldu.")
        
        TENANT_USER_ID = 1

        perakende_musteri = modeller.Musteri(ad="Perakende Müşterisi", kod="PERAKENDE_MUSTERI", aktif=True, kullanici_id=TENANT_USER_ID)
        db.add(perakende_musteri)
        
        genel_tedarikci = modeller.Tedarikci(ad="Genel Tedarikçi", kod="GENEL_TEDARIKCI", aktif=True, kullanici_id=TENANT_USER_ID)
        db.add(genel_tedarikci)

        db.add(modeller.KasaBankaHesap(hesap_adi="NAKİT KASA", tip=modeller.KasaBankaTipiEnum.KASA, bakiye=0.0, para_birimi="TL", aktif=True, kullanici_id=TENANT_USER_ID))
        db.add(modeller.UrunBirimi(ad="Adet", kullanici_id=TENANT_USER_ID))
        
        db.commit()
        
        db.refresh(perakende_musteri)
        db.refresh(genel_tedarikci)
        db.add(modeller.CariHesap(cari_id=perakende_musteri.id, cari_tip=modeller.CariTipiEnum.MUSTERI.value, bakiye=0.0))
        db.add(modeller.CariHesap(cari_id=genel_tedarikci.id, cari_tip=modeller.CariTipiEnum.TEDARIKCI.value, bakiye=0.0))

        db.commit()
        logger.info(f"Varsayılan veriler başarıyla Tenant DB'ye eklendi.")

    except Exception as e:
        db.rollback()
        logger.error(f"Varsayılan veriler Tenant DB'ye eklenirken kritik bir hata oluştu: {e}", exc_info=True)
        raise

# --- ROTALAR ---

@router.post("/login", response_model=modeller.OfflineLoginResponse)
def authenticate_user(user_login: modeller.KullaniciLogin, db: Session = Depends(get_master_db)):
    
    user = db.query(modeller.Kullanici).options(
        joinedload(modeller.Kullanici.firma) 
    ).filter(
        modeller.Kullanici.email == user_login.email
    ).first()

    if not user or not verify_password(user_login.sifre, user.sifre_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Hatalı e-posta veya şifre.")
    
    if not user.firma or not user.firma.db_adi:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcının Tenant/Firma bilgisi eksik.")

    tenant_db_name = user.firma.db_adi
    firma_adi = user.firma.unvan
    
    try:
        tenant_engine = get_tenant_engine(tenant_db_name)
        with tenant_engine.connect() as connection:
            logger.info(f"Tenant veritabanı '{tenant_db_name}' zaten mevcut, bağlantı başarılı.")
    except Exception:
        logger.warning(f"Tenant veritabanı '{tenant_db_name}' bulunamadı. Veritabanı şimdi oluşturulacak...")
        try:
            master_engine = get_master_engine()
            with master_engine.connect() as conn:
                conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text(f"CREATE DATABASE {tenant_db_name} ENCODING 'UTF8' TEMPLATE template0;")
                )
            
            tenant_engine_new = get_tenant_engine(tenant_db_name)
            modeller.Base.metadata.create_all(bind=tenant_engine_new)
            
            TenantSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine_new)
            tenant_db_session = TenantSessionLocal()
            try:
                _add_default_tenant_data(tenant_db_session, olusturan_kullanici_id=user.id)
                logger.info(f"Yeni tenant veritabanı '{tenant_db_name}' ve varsayılan veriler başarıyla oluşturuldu.")
            finally:
                tenant_db_session.close()
        except Exception as creation_error:
            logger.error(f"Tenant veritabanı '{tenant_db_name}' oluşturulurken kritik hata: {creation_error}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Giriş sırasında firma veritabanı oluşturulamadı."
            )

    # KRİTİK DÜZELTME: Ayar artık merkezi 'settings' nesnesinden okunuyor.
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "tenant_db": tenant_db_name}, 
        expires_delta=access_token_expires
    )

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
def register_user(user_create: modeller.KullaniciCreate, db: Session = Depends(get_master_db)):
    
    # Mevcut kullanıcı veya firma adı kontrolü
    if db.query(modeller.Kullanici).filter(modeller.Kullanici.email == user_create.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-posta zaten mevcut.")
    if db.query(modeller.Firma).filter(modeller.Firma.firma_adi == user_create.firma_adi).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Firma adı zaten mevcut.")

    hashed_password = get_password_hash(user_create.sifre)
    db_user = modeller.Kullanici(
        sifre_hash=hashed_password,
        ad=user_create.ad,
        soyad=user_create.soyad,
        email=user_create.email,
        telefon=user_create.telefon,
        rol=user_create.rol
    )
    
    # Firma adından güvenli bir veritabanı adı oluştur
    tenant_db_name = f"tenant_{user_create.firma_adi}".lower().replace(' ', '_').replace('ı', 'i').replace('ö', 'o').replace('ü', 'u').replace('ş', 's').replace('ç', 'c').replace('ğ', 'g')
    
    master_engine = get_master_engine()
    
    # --- NİHAİ DÜZELTME BURADA ---
    # İşleme başlamadan önce, olası artık veritabanını temizle
    try:
        with master_engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{tenant_db_name}';"))
            conn.execute(text(f"DROP DATABASE IF EXISTS {tenant_db_name};"))
        logger.info(f"Olası artık veritabanı ({tenant_db_name}) başarıyla temizlendi.")
    except Exception as cleanup_error:
        logger.error(f"Başlangıç temizliği sırasında hata oluştu: {cleanup_error}")
        # Bu kritik bir hata değil, sadece loglayıp devam edebiliriz.
    # --- DÜZELTME SONU ---

    try:
        db.add(db_user)
        db.flush() 
        
        db_firma = modeller.Firma(
            firma_adi=user_create.firma_adi,
            tenant_db_name=tenant_db_name,
            kurucu_personel_id=db_user.id
        )
        db.add(db_firma)
        db_user.firma_id = db_firma.id
        db.commit()
        
        with master_engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text(f"CREATE DATABASE {tenant_db_name} ENCODING 'UTF8' TEMPLATE template0;")
            )
        
        tenant_engine = get_tenant_engine(tenant_db_name)
        modeller.Base.metadata.create_all(bind=tenant_engine)
        
        TenantSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
        tenant_db = TenantSessionLocal()
        try:
            _add_default_tenant_data(tenant_db, olusturan_kullanici_id=db_user.id) 
        finally:
            tenant_db.close()
        
        db.refresh(db_user)
        user_read = modeller.KullaniciRead.model_validate(db_user, from_attributes=True)
        user_read.firma_adi = db_firma.firma_adi
        return user_read

    except Exception as e:
        db.rollback()
        # Hata durumunda son bir kez daha temizlik yapmayı dene
        try:
            with master_engine.connect() as conn:
                conn.execution_options(isolation_level="AUTOCOMMIT")
                conn.execute(text(f"DROP DATABASE IF EXISTS {tenant_db_name};"))
            logger.info(f"Hata sonrası artık veritabanı ({tenant_db_name}) başarıyla silindi.")
        except Exception as final_cleanup_error:
            logger.error(f"Hata sonrası temizlik sırasında hata oluştu: {final_cleanup_error}")
                
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kullanıcı kaydı oluşturulamadı: {e}"
        )
    
@router.post("/personel-giris", response_model=semalar.Token)
def personel_giris(personel_bilgileri: semalar.PersonelGirisSema, db_public: Session = Depends(get_master_db)):
    # 1. Adım: Firma numarasını kullanarak ana veritabanından firmayı bul.
    firma = db_public.query(modeller.Firma).filter(modeller.Firma.firma_no == personel_bilgileri.firma_no).first()

    if not firma:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu firma numarasına sahip bir firma bulunamadı."
        )

    # 2. Adım: Firmanın kendine özel veritabanına (tenant) bağlan.
    db_tenant = get_tenant_session_by_name(firma.db_adi)

    try:
        # 3. Adım: Firma veritabanında kullanıcı adını ara.
        kullanici = db_tenant.query(modeller.Kullanici).filter(modeller.Kullanici.kullanici_adi == personel_bilgileri.kullanici_adi).first()

        # 4. Adım: Kullanıcıyı ve şifreyi doğrula.
        if not kullanici or not verify_password(personel_bilgileri.sifre, kullanici.sifre_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Kullanıcı adı veya şifre yanlış.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 5. Adım: Başarılı giriş sonrası token oluştur.
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": kullanici.kullanici_adi, "rol": kullanici.rol, "id": kullanici.id, "firma_db": firma.db_adi},
            expires_delta=access_token_expires
        )
        
        # Arayüzün ihtiyaç duyacağı temel bilgileri de token ile birlikte geri döndürüyoruz.
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "kullanici_id": kullanici.id,
            "kullanici_adi": kullanici.kullanici_adi,
            "rol": kullanici.rol,
            "sifre_hash": kullanici.sifre_hash
        }
    finally:
        # Oturumu kapatarak kaynakların serbest bırakıldığından emin oluyoruz.
        db_tenant.close()