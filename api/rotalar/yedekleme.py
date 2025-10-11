# api/rotalar/yedekleme.py (Database-per-Tenant Uyumlu)
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
# DÜZELTME 1: get_db yerine sadece reset_db_connection import edilir
from ..veritabani import reset_db_connection, get_tenant_engine 
from datetime import datetime
import subprocess
from sqlalchemy import text 
from typing import Optional
from .. import guvenlik, modeller # KRİTİK: modeller ve guvenlik eklendi
import os

router = APIRouter(prefix="/yedekleme", tags=["Veritabanı Yedekleme"])

# KRİTİK DÜZELTME 2: Tenant bağlantı bilgileri doğrudan env'den okunur
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "admin")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

BACKUP_DIR = os.path.join(os.getcwd(), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

@router.post("/backup", summary="Veritabanını Yedekle", status_code=status.HTTP_200_OK)
def create_db_backup(
    # KRİTİK DÜZELTME 3: Sadece current_user bağımlılığı yeterlidir.
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) 
):
    # Yedeklenecek DB adı, JWT'den alınan tenant'a özel isimdir.
    TENANT_DB_NAME = current_user.tenant_db_name
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{TENANT_DB_NAME}_backup_{timestamp}.sql"
    backup_filepath = os.path.join(BACKUP_DIR, backup_filename)

    try:
        os.environ['PGPASSWORD'] = DB_PASSWORD
        command = [
            "pg_dump",
            "-h", DB_HOST,
            "-p", DB_PORT,
            "-U", DB_USER,
            "-F", "p",
            "-d", TENANT_DB_NAME, # KRİTİK DÜZELTME 4: Tenant DB adı kullanılır
            "-f", backup_filepath
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        if result.stderr:
            # pg_dump stdout'a da yazabildiği için kontrol sadece stderr'a yapılır
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Yedekleme sırasında hata oluştu: {result.stderr}")

        return {"message": f"Veritabanı başarıyla yedeklendi: {backup_filename}", "filepath": backup_filepath}
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="pg_dump komutu bulunamadı. PostgreSQL client tools kurulu olduğundan ve PATH'inizde olduğundan emin olun.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Yedekleme komutu hatası: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Beklenmedik bir hata oluştu: {e}")
    finally:
        if 'PGPASSWORD' in os.environ:
            del os.environ['PGPASSWORD']

@router.post("/restore", summary="Veritabanını Geri Yükle", status_code=status.HTTP_200_OK)
def restore_db_backup(
    backup_file: UploadFile = File(...),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user) # Dinamik Tenant adı için
):
    if not backup_file.filename.endswith(".sql"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sadece .sql uzantılı dosyalar kabul edilir.")

    TENANT_DB_NAME = current_user.tenant_db_name

    temp_filepath = os.path.join(BACKUP_DIR, f"restore_temp_{backup_file.filename}")
    try:
        # 1. Yüklenen dosyayı geçici olarak kaydet
        with open(temp_filepath, "wb") as buffer:
            buffer.write(backup_file.file.read())

        # 2. Geri yükleme komutunu çalıştır
        os.environ['PGPASSWORD'] = DB_PASSWORD
        command = [
            "psql",
            "-h", DB_HOST,
            "-p", DB_PORT,
            "-U", DB_USER,
            "-d", TENANT_DB_NAME, # KRİTİK DÜZELTME 5: Tenant DB adı kullanılır
            "-f", temp_filepath
        ]

        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        # 3. Bağlantı havuzunu sıfırla (Şema değiştiği için zorunludur)
        reset_db_connection()

        # 4. Bağlantı testi (Tenant Engine'ini yeniden başlatarak)
        try:
            # get_tenant_engine çağrısıyla bağlantı kurulur
            tenant_engine = get_tenant_engine(TENANT_DB_NAME) 
            with tenant_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.close()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Geri yükleme başarılı, ancak veritabanı bağlantısı tekrar kurulamadı: {e}"
            ) from e

        return {"message": f"Veritabanı başarıyla geri yüklendi: {backup_file.filename}"}
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="psql/pg_dump komutu bulunamadı.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Geri yükleme komutu hatası: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Beklenmedik bir hata oluştu: {e}")
    finally:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        if 'PGPASSWORD' in os.environ:
            del os.environ['PGPASSWORD']