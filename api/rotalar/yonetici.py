# api/rotalar/yonetici.py dosyasının tamamı
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from datetime import timedelta, date
from typing import List, Optional
from ..guvenlik import get_password_hash, get_current_user, modul_yetki_kontrol
from .. import modeller, guvenlik, veritabani
from ..veritabani import get_master_db, get_tenant_db, reset_db_connection, get_master_engine, create_tenant_db_and_tables, add_default_user_data, get_db
from sqlalchemy.exc import IntegrityError
import os
import uuid
import shutil
import subprocess
import logging
from datetime import datetime
from pydantic import BaseModel

# 1. GÜNCELLEME: Rota adresi "/yonetici" olarak düzeltildi.
router = APIRouter(
    prefix="/yonetici",
    tags=["Yönetici İşlemleri"]
)

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

BACKUP_DIR = os.path.join(os.getcwd(), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BackupRequest(BaseModel):
    file_path: Optional[str] = None

class RestoreRequest(BaseModel):
    file_path: str

@router.post("/firma_olustur", status_code=status.HTTP_201_CREATED)
def firma_olustur(firma_data: modeller.FirmaOlustur, db: Session = Depends(get_master_db)):
    """
    Yeni bir firma (tenant), ona ait veritabanı ve yönetici kullanıcısını oluşturur.
    """
    # E-posta kontrolü
    db_kullanici = db.query(modeller.Kullanici).filter(
        modeller.Kullanici.email == firma_data.yonetici_email
    ).first()
    if db_kullanici:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Bu e-posta adresi zaten kayıtlı."
        )

    # Firma ünvanı kontrolü
    db_firma = db.query(modeller.Firma).filter(
        modeller.Firma.unvan == firma_data.firma_unvani
    ).first()
    if db_firma:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Bu firma ünvanı zaten kayıtlı."
        )

    # Tenant DB adı oluştur
    db_name_prefix = "".join(
        e for e in firma_data.firma_unvani.lower() 
        if e.isalnum() or e in " _"
    ).replace(" ", "_")
    tenant_db_name = f"tenant_{db_name_prefix[:50]}"

    # ✅ YENİ: Benzersiz firma numarası oluştur
    firma_no = f"F{uuid.uuid4().hex[:8].upper()}"
    
    # Firma numarasının benzersiz olduğundan emin ol (çok düşük ihtimal ama kontrol edelim)
    while db.query(modeller.Firma).filter(modeller.Firma.firma_no == firma_no).first():
        firma_no = f"F{uuid.uuid4().hex[:8].upper()}"

    try:
        # Tenant DB oluştur
        create_tenant_db_and_tables(tenant_db_name)

        lisans_baslangic = date.today()
        lisans_bitis = lisans_baslangic + timedelta(days=7)

        # ✅ GÜNCELLEME: firma_no alanı eklendi
        yeni_firma = modeller.Firma(
            unvan=firma_data.firma_unvani, 
            db_adi=tenant_db_name,
            firma_no=firma_no,
            lisans_baslangic_tarihi=lisans_baslangic,
            lisans_bitis_tarihi=lisans_bitis,
            lisans_durum=modeller.LisansDurumEnum.DENEME
        )
        db.add(yeni_firma)
        db.flush()

        # Ad-Soyad ayrıştırma (iyileştirilmiş)
        ad_soyad_temiz = " ".join(firma_data.yonetici_ad_soyad.strip().split())
        if not ad_soyad_temiz:
            raise HTTPException(
                status_code=400, 
                detail="Yönetici adı soyadı boş olamaz."
            )
        
        ad_soyad_split = ad_soyad_temiz.split(" ", 1)
        ad = ad_soyad_split[0]
        soyad = ad_soyad_split[1] if len(ad_soyad_split) > 1 else ""

        # Kullanıcı oluştur
        hashed_sifre = guvenlik.get_password_hash(firma_data.yonetici_sifre)
        yeni_kullanici = modeller.Kullanici(
            ad=ad,
            soyad=soyad,
            email=firma_data.yonetici_email,
            sifre_hash=hashed_sifre,
            telefon=firma_data.yonetici_telefon,
            rol=modeller.RolEnum.ADMIN,
            firma_id=yeni_firma.id
        )
        db.add(yeni_kullanici)
        db.commit()
        db.refresh(yeni_firma)
        db.refresh(yeni_kullanici)

        # Tenant DB'ye varsayılan veri ekle
        with next(get_tenant_db(tenant_db_name)) as tenant_session:
            add_default_user_data(tenant_session, kullanici_id_master=yeni_kullanici.id)

        return {
            "mesaj": f"'{firma_data.firma_unvani}' firması başarıyla oluşturuldu.",
            "firma_no": firma_no  # ← Kullanıcıya firma numarasını döndür
        }

    except IntegrityError as e:
        db.rollback()
        logger.error(f"IntegrityError: {e}", exc_info=True)
        
        # Hatalı DB'yi temizle
        try:
            engine = get_master_engine()
            with engine.connect() as connection:
                connection.execute(text("COMMIT"))
                connection.execute(text(f"DROP DATABASE IF EXISTS \"{tenant_db_name}\""))
        except Exception as drop_e:
            logger.error(f"Hata sonrası veritabanı silinemedi: {drop_e}")
        
        # Kullanıcı dostu hata mesajı
        if "email" in str(e).lower():
            raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kayıtlı.")
        elif "unvan" in str(e).lower():
            raise HTTPException(status_code=400, detail="Bu firma ünvanı zaten kayıtlı.")
        elif "firma_no" in str(e).lower():
            raise HTTPException(status_code=500, detail="Firma numarası oluşturulamadı. Lütfen tekrar deneyin.")
        else:
            raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    
    except Exception as e:
        db.rollback()
        logger.error(f"Firma oluşturma sırasında kritik hata: {e}", exc_info=True)
        
        # Hatalı DB'yi temizle
        try:
            engine = get_master_engine()
            with engine.connect() as connection:
                connection.execute(text("COMMIT"))
                connection.execute(text(f"DROP DATABASE IF EXISTS \"{tenant_db_name}\""))
        except Exception as drop_e:
            logger.error(f"Hata sonrası veritabanı silinemedi: {drop_e}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Firma oluşturulurken beklenmedik bir hata oluştu: {str(e)}"
        )

# --- YÖNETİCİ İŞLEMLERİ (Backup/Restore Logic) ---

def run_backup_command(file_path: str, tenant_db_name: str) -> str:
    """PostgreSQL pg_dump komutunu çalıştırarak belirtilen Tenant DB'yi yedekler."""
    
    # pg_dump komutunu sistem PATH'inde veya PG_BIN_PATH'te arar
    pg_dump_command = shutil.which("pg_dump")
    if not pg_dump_command:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="pg_dump komutu bulunamadı.")
        
    os.environ['PGPASSWORD'] = DB_PASSWORD
    command = [
        pg_dump_command,
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-F", "p",
        "-d", tenant_db_name, # KRİTİK DÜZELTME 3: Tenant DB adı kullanılır
        "-f", file_path
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.stderr:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Yedekleme sırasında hata oluştu: {result.stderr}")
        return f"Yedekleme başarıyla tamamlandı: {file_path}"
    finally:
        if 'PGPASSWORD' in os.environ:
            del os.environ['PGPASSWORD']

def run_restore_command(file_path: str, tenant_db_name: str) -> str:
    """PostgreSQL psql komutunu çalıştırarak belirtilen Tenant DB'yi geri yükler."""
    
    psql_command_path = shutil.which("psql")
    if not psql_command_path:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="psql komutu bulunamadı.")

    env_vars = os.environ.copy()
    env_vars["PGPASSWORD"] = DB_PASSWORD
    
    try:
        # KRİTİK DÜZELTME 4: Geri Yükleme için Tenant DB'yi sıfırla (psql ile)
        
        # 1. Bağlantıları Kes (FORCE DROP için)
        drop_force_command = f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{tenant_db_name}';"
        subprocess.run([psql_command_path, f"--host={DB_HOST}", f"--port={DB_PORT}", f"--username={DB_USER}", "--dbname=postgres", f"--command={drop_force_command}"], check=False, env=env_vars)

        # 2. Veritabanını Sil (DROP)
        drop_db_command = [psql_command_path, f"--host={DB_HOST}", f"--port={DB_PORT}", f"--username={DB_USER}", "--dbname=postgres", f"--command=DROP DATABASE IF EXISTS \"{tenant_db_name}\";"]
        subprocess.run(drop_db_command, check=True, env=env_vars)

        # 3. Veritabanını Yeniden Oluştur (CREATE)
        create_db_command = [psql_command_path, f"--host={DB_HOST}", f"--port={DB_PORT}", f"--username={DB_USER}", "--dbname=postgres", f"--command=CREATE DATABASE \"{tenant_db_name}\";"]
        subprocess.run(create_db_command, check=True, env=env_vars)

        # 4. Geri Yükleme Komutu (psql -f)
        restore_command = [
            psql_command_path,
            f"--host={DB_HOST}",
            f"--port={DB_PORT}",
            f"--username={DB_USER}",
            f"--dbname={tenant_db_name}",
            "-f", file_path
        ]
        result = subprocess.run(restore_command, check=True, env=env_vars, capture_output=True, text=True)

        # 5. Bağlantı havuzunu sıfırla
        reset_db_connection()

        return f"Veritabanı başarıyla geri yüklendi: {file_path}"
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Geri yükleme komutu hatası: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Beklenmeyen bir hata oluştu: {e}")

# --- ROTALAR ---

@router.post("/yedekle")
def yedekle(
    request: BackupRequest,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    # KRİTİK DÜZELTME 5: Tenant DB adını kullan
    tenant_db_name = current_user.tenant_db_name
    
    if not request.file_path:
        backup_dir = os.path.join(os.getcwd(), 'yedekler', current_user.firma_adi or 'firma')
        os.makedirs(backup_dir, exist_ok=True)
        file_name = f"{tenant_db_name}_yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        file_path = os.path.join(backup_dir, file_name)
    else:
        file_path = request.file_path
    
    try:
        message = run_backup_command(file_path, tenant_db_name)
        return {"message": message, "file_path": file_path}
    except HTTPException as e:
        raise e

@router.post("/geri_yukle")
def geri_yukle(
    request: RestoreRequest,
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Belirtilen dosya bulunamadı: {request.file_path}")
    
    tenant_db_name = current_user.tenant_db_name
    
    try:
        message = run_restore_command(request.file_path, tenant_db_name)
        return {"message": message}
    except HTTPException as e:
        raise e

@router.delete("/clear_all_data", status_code=status.HTTP_200_OK, summary="Tüm verileri temizle (Kullanıcılar Hariç)")
def clear_all_data(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_tenant_db) # Tenant DB kullanılır
):
    # KRİTİK DÜZELTME 6: Sadece Tenant DB'deki tüm tabloları temizle (DbT UYUMU)
    try:
        tables_to_clear = [
            modeller.FaturaKalemi, modeller.SiparisKalemi, modeller.StokHareket,
            modeller.CariHareket, modeller.KasaBankaHareket, modeller.GelirGider, 
            modeller.Fatura, modeller.Siparis, modeller.Stok, modeller.Musteri,
            modeller.Tedarikci, modeller.KasaBankaHesap, modeller.UrunBirimi, 
            modeller.UrunMarka, modeller.UrunKategori, modeller.UrunGrubu, 
            modeller.Ulke, modeller.GelirSiniflandirma, modeller.GiderSiniflandirma,
            modeller.SirketBilgileri, modeller.SirketAyarlari, modeller.CariHesap
        ]
        
        for table in tables_to_clear:
             # DbT'deyiz, IZOLASYON FILTRESI OLMADAN tüm tabloyu sil
             db.query(table).delete(synchronize_session=False)

        db.commit()

        return {"message": "Kullanıcıya ait tüm veriler başarıyla temizlendi."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Veri temizleme sırasında hata oluştu: {e}")
    
@router.post("/ilk_veri_olustur", status_code=status.HTTP_200_OK)
def initial_data_setup_endpoint(
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user),
    db: Session = Depends(get_tenant_db) # Tenant DB kullanılır
):
    # KRİTİK DÜZELTME 7: dogrulama.py'deki mantığı taklit et (Tenant DB'de varsayılan verileri oluştur)
    from ..rotalar.dogrulama import _add_default_tenant_data as add_default_tenant_data
    
    try:
        add_default_tenant_data(db=db, kullanici_id_master=1) # Tenant DB'deki ilk personel ID'si 1'dir.
        return {"message": f"Varsayılan veriler kullanıcı {current_user.email} için başarıyla oluşturuldu/yenilendi."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Varsayılan veri oluşturma hatası: {e}")

# --- MEVCUT PERSONEL LİSTELEME ---
@router.get("/personel-listesi", response_model=modeller.KullaniciListResponse)
def personel_listele_endpoint(
    db: Session = Depends(veritabani.get_db),
    # DÜZELTME: Eski rol kontrolü yerine yeni modül yetki kontrolü
    current_user: dict = Depends(guvenlik.modul_yetki_kontrol("PERSONEL_YONETIMI")) 
):
    # 'modul_yetki_kontrol' zaten ADMIN veya YONETICI (izinli) olduğunu doğruladı.
    # Bu yüzden eski 'if current_user.rol not in yetkili_roller:' kontrolü kaldırıldı.
    
    # Tenant DB kullanıldığı için zaten filtrelenmiş kullanıcılar gelir
    users = db.query(modeller.Kullanici).all()
    
    return {"items": users, "total": len(users)}

# --- PERSONEL GÜNCELLEME ---
@router.put("/personel-guncelle/{personel_id}", response_model=modeller.KullaniciRead)
def personel_guncelle_endpoint(
    personel_id: int,
    personel_guncelle: modeller.KullaniciUpdate,
    db: Session = Depends(veritabani.get_db),
    # DÜZELTME: Eski rol kontrolü yerine yeni modül yetki kontrolü
    current_user: dict = Depends(guvenlik.modul_yetki_kontrol("PERSONEL_YONETIMI"))
):
    # 'modul_yetki_kontrol' zaten ADMIN veya YONETICI (izinli) olduğunu doğruladı.
    # Eski 'if current_user.rol not in yetkili_roller:' kontrolü kaldırıldı.

    # Kendi hesabını güncelleme yasağı
    if personel_id == current_user.get("id"): # current_user artık bir dict
        raise HTTPException(status_code=400, detail="Kendi kullanıcı bilginizi yönetici rotaları üzerinden güncelleyemezsiniz. Lütfen '/kullanicilar/me' rotasını kullanın.")
    
    personel = db.query(modeller.Kullanici).filter(modeller.Kullanici.id == personel_id).first()
    
    if not personel:
        raise HTTPException(status_code=404, detail="Personel bulunamadı.")
    
    # --- YENİ HİYERARŞİ KURALI ---
    # Eğer güncelleyen kişi YONETICI ise, sadece PERSONEL'i güncelleyebilir.
    if current_user.get("rol") == modeller.RolEnum.YONETICI:
        if personel.rol == modeller.RolEnum.ADMIN or personel.rol == modeller.RolEnum.YONETICI:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Yöneticiler, başka Yöneticileri veya Adminleri güncelleyemez."
            )
        # Yöneticinin, personelin rolünü ADMIN/YONETICI yapmasını engelle
        if personel_guncelle.rol and personel_guncelle.rol != modeller.RolEnum.PERSONEL:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Yöneticiler, personellerin rolünü sadece 'PERSONEL' olarak atayabilir."
            )
    # --- YENİ HİYERARŞİ KURALI SONU ---

    # ADMIN (ID=1) hesabının rolünü değiştirmeyi engelle (Talimat 1.5 - Görev 2)
    if personel_id == 1 and personel_guncelle.rol and personel_guncelle.rol != modeller.RolEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kurucu ADMIN hesabının rolü değiştirilemez."
        )
        
    update_data = personel_guncelle.model_dump(exclude_unset=True)
    
    # ROL KONTROLÜ GÜNCELLENDİ (Talimat 1.4)
    # (Bu blok korunabilir, YONETICI zaten kontrol edildi, bu diğerlerini engeller)
    if 'rol' in update_data and current_user.get("rol") not in [modeller.RolEnum.SUPERADMIN, modeller.RolEnum.ADMIN, modeller.RolEnum.YONETICI]:
        del update_data['rol']

    for key, value in update_data.items():
        if key == 'sifre':
            personel.sifre_hash = guvenlik.get_password_hash(value)
        else:
            setattr(personel, key, value)

    db.add(personel)
    db.commit()
    db.refresh(personel)
    
    return personel

# --- PERSONEL SİLME ---
@router.delete("/personel-sil/{personel_id}")
def personel_sil_endpoint(
    personel_id: int,
    db: Session = Depends(veritabani.get_db),
    # DÜZELTME: Eski rol kontrolü yerine yeni modül yetki kontrolü
    current_user: dict = Depends(guvenlik.modul_yetki_kontrol("PERSONEL_YONETIMI"))
):
    # 'modul_yetki_kontrol' zaten ADMIN veya YONETICI (izinli) olduğunu doğruladı.
    # Eski 'if current_user.rol not in yetkili_roller:' kontrolü kaldırıldı.

    if personel_id == current_user.get("id"):
        raise HTTPException(status_code=400, detail="Aktif olarak kullandığınız hesabı silemezsiniz.")

    # ADMIN (ID=1) hesabını koruma (Talimat 1.5 - Görev 1)
    if personel_id == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kurucu ADMIN hesabı silinemez."
        )
        
    personel = db.query(modeller.Kullanici).filter(modeller.Kullanici.id == personel_id).first()
    
    if not personel:
        raise HTTPException(status_code=404, detail="Personel bulunamadı.")

    # --- YENİ HİYERARŞİ KURALI ---
    # Eğer silen kişi YONETICI ise, sadece PERSONEL'i silebilir.
    if current_user.get("rol") == modeller.RolEnum.YONETICI:
        if personel.rol == modeller.RolEnum.ADMIN or personel.rol == modeller.RolEnum.YONETICI:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Yöneticiler, başka Yöneticileri veya Adminleri silemez."
            )
    # --- YENİ HİYERARŞİ KURALI SONU ---

    db.delete(personel)
    db.commit()
    
    return {"mesaj": f"Personel (ID: {personel_id}) başarıyla silindi."}

# --- YENİ PERSONEL OLUŞTURMA ---
@router.post("/personel-olustur", response_model=modeller.KullaniciRead, status_code=status.HTTP_201_CREATED)
def personel_olustur_endpoint(
    kullanici_olustur: modeller.KullaniciCreate,
    db: Session = Depends(veritabani.get_db),
    # DÜZELTME: Eski rol kontrolü yerine yeni modül yetki kontrolü
    current_user: dict = Depends(guvenlik.modul_yetki_kontrol("PERSONEL_YONETIMI"))
):
    # 'modul_yetki_kontrol' zaten ADMIN veya YONETICI (izinli) olduğunu doğruladı.
    # Eski 'if current_user.rol not in yetkili_roller:' kontrolü kaldırıldı.

    # --- YENİ HİYERARŞİ KURALI ---
    # Eğer oluşturan kişi YONETICI ise, sadece PERSONEL oluşturabilir.
    if current_user.get("rol") == modeller.RolEnum.YONETICI and kullanici_olustur.rol != modeller.RolEnum.PERSONEL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yöneticiler sadece 'PERSONEL' rolünde kullanıcılar oluşturabilir."
        )
    # --- YENİ HİYERARŞİ KURALI SONU ---

    # 1. Kullanıcının zaten var olup olmadığını kontrol et (Tenant DB üzerinde)
    existing_user = db.query(modeller.Kullanici).filter(modeller.Kullanici.email == kullanici_olustur.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kullanımda.")

    # 2. KRİTİK DÜZELTME: Postgres sayacını en yüksek ID'den bir sonraki değere ayarla
    try:
        max_id = db.query(func.max(modeller.Kullanici.id)).scalar() or 0
        # Sayacı max_id + 1 olarak ayarla (true ile, bir sonraki ID max_id + 1 olur)
        db.execute(text(f"SELECT setval('public.kullanicilar_id_seq', {max_id}, true)"))
        logger.info(f"PostgreSQL 'kullanicilar_id_seq' sayacı en yüksek ID ({max_id}) üzerine ayarlandı.")
        db.commit() # Sayaç güncellemesini kalıcı yap
    except Exception as e:
        logger.warning(f"PostgreSQL sayacını ayarlarken geçici bir hata oluştu: {e}")
        db.rollback() # Sayaç ayarlama hatasında rollback yap
        
    # 3. Şifreyi hashle
    hashed_password = guvenlik.get_password_hash(kullanici_olustur.sifre)

    # 4. Yeni kullanıcı objesini oluştur (ID belirtmeden otomatik atanmasını sağla)
    new_user = modeller.Kullanici(
        ad=kullanici_olustur.ad,
        soyad=kullanici_olustur.soyad,
        email=kullanici_olustur.email,
        telefon=kullanici_olustur.telefon,
        sifre_hash=hashed_password,
        rol=kullanici_olustur.rol,
        aktif=kullanici_olustur.aktif
        # firma_id alanı Tenant DB'deki Kullanici modelinde olmamalı (kaldırıldı)
    )

    # 5. Veritabanına kaydet
    db.add(new_user)
    
    try:
        db.commit()
    except IntegrityError as e:
         db.rollback()
         if "kullanicilar_pkey" in str(e):
              raise HTTPException(status_code=400, detail="Yeni personel eklenirken kritik ID çakışması yaşandı. Veritabanı sayacı sıfırlanmış olabilir.")
         raise
    
    db.refresh(new_user)
    return new_user

class IzinGuncelleRequest(BaseModel):
    izinler: dict[str, bool] # Örn: {"FATURALAR": True, "STOKLAR": False}

@router.get("/{personel_id}/izinleri-getir", response_model=List[str])
def izinleri_getir(
    personel_id: int,
    db: Session = Depends(veritabani.get_db),
    current_user: dict = Depends(guvenlik.modul_yetki_kontrol("PERSONEL_YONETIMI"))
):
    """Belirtilen personelin aktif modül izinlerini bir liste olarak döndürür."""
    izinler_query = db.query(modeller.KullaniciIzinleri.modul_adi).filter(
        modeller.KullaniciIzinleri.kullanici_id == personel_id,
        modeller.KullaniciIzinleri.erisebilir == True
    ).all()

    izin_listesi = [izin[0] for izin in izinler_query]
    return izin_listesi

@router.put("/{personel_id}/izinleri-guncelle")
def izinleri_guncelle(
    personel_id: int,
    izin_request: IzinGuncelleRequest,
    db: Session = Depends(veritabani.get_db),
    current_user: dict = Depends(guvenlik.modul_yetki_kontrol("PERSONEL_YONETIMI"))
):
    """Bir personelin modül izinlerini günceller veya oluşturur."""

    personel = db.query(modeller.Kullanici).filter(modeller.Kullanici.id == personel_id).first()
    if not personel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personel bulunamadı.")

    # Yöneticinin, Admin veya Yöneticinin izinlerini değiştirmesini engelle
    if current_user.get("rol") == modeller.RolEnum.YONETICI and personel.rol != modeller.RolEnum.PERSONEL:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yöneticiler sadece Personel izinlerini değiştirebilir.")

    try:
        for modul_key, erisebilir in izin_request.izinler.items():
            # Mevcut izni bul
            mevcut_izin = db.query(modeller.KullaniciIzinleri).filter(
                modeller.KullaniciIzinleri.kullanici_id == personel_id,
                modeller.KullaniciIzinleri.modul_adi == modul_key
            ).first()
                        
            if mevcut_izin:
                # Varsa güncelle
                mevcut_izin.erisebilir = erisebilir
            else:
                # Yoksa yeni oluştur
                yeni_izin = modeller.KullaniciIzinleri(
                    kullanici_id=personel_id,
                    modul_adi=modul_key,
                    erisebilir=erisebilir
                )
                db.add(yeni_izin)
                
        db.commit()
        return {"mesaj": f"Personel (ID: {personel_id}) izinleri başarıyla güncellendi."}
    except Exception as e:
        db.rollback()
        logger.error(f"İzinler güncellenirken hata: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="İzinler güncellenirken veritabanı hatası oluştu.")