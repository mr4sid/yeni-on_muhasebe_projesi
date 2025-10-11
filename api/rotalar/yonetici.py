# api/rotalar/yonetici.py DOSYASININ TAM İÇERİĞİ (Database-per-Tenant Uyumlu)
import os
import shutil
import subprocess
import logging
from fastapi import APIRouter, HTTPException, Depends, status, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from sqlalchemy import text
from .. import modeller, guvenlik
# KRİTİK DÜZELTME 1: Tenant ve Master DB fonksiyonları için gerekli olanlar import edildi
from ..veritabani import get_db as get_tenant_db, reset_db_connection, get_master_engine

router = APIRouter(
    prefix="/admin",
    tags=["Yönetici İşlemleri"]
)

# KRİTİK DÜZELTME 2: DB Bağlantı Bilgileri ENV'den okunur
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
    from ..rotalar.dogrulama import _add_default_user_data as add_default_tenant_data
    
    try:
        add_default_tenant_data(db=db, kullanici_id=1) # Tenant DB'deki ilk personel ID'si 1'dir.
        return {"message": f"Varsayılan veriler kullanıcı {current_user.email} için başarıyla oluşturuldu/yenilendi."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Varsayılan veri oluşturma hatası: {e}")