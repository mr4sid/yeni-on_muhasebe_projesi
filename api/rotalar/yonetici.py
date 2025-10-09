# api/rotalar/yonetici.py
import os
import shutil
import subprocess
import logging
from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from sqlalchemy import text
from ..api_servisler import create_initial_data
from .. import semalar
from ..veritabani import get_db, Base

router = APIRouter(
    prefix="/admin",
    tags=["Yönetici İşlemleri"]
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BackupRequest(BaseModel):
    file_path: Optional[str] = None

class RestoreRequest(BaseModel):
    file_path: str

def run_backup_command(file_path: str) -> str:
    pg_bin_path = os.getenv("PG_BIN_PATH")
    pg_dump_command = None
    
    if pg_bin_path:
        logging.info(f"Ortam değişkeninden PG_BIN_PATH okundu: {pg_bin_path}")
        pg_dump_command = os.path.join(pg_bin_path, "pg_dump")
        pg_dump_command = f'"{pg_dump_command}"'
        if not os.path.exists(os.path.join(pg_bin_path, "pg_dump.exe")):
            logging.warning(f"PG_BIN_PATH'de belirtilen yolda pg_dump bulunamadı: {pg_dump_command}")
            pg_dump_command = None
        else:
            logging.info(f"pg_dump komutu PG_BIN_PATH'de bulundu: {pg_dump_command}")
            
    if not pg_dump_command:
        logging.info("PG_BIN_PATH kullanılamadı. Sistem PATH'inde pg_dump aranıyor.")
        pg_dump_command = shutil.which("pg_dump")
        
    if not pg_dump_command:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Yedekleme komutu (pg_dump) bulunamadı. Lütfen PostgreSQL'in 'bin' dizinini "
                "sistem PATH'inize veya PG_BIN_PATH ortam değişkenine eklediğinizden emin olun."
            )
        )
        
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    
    command_str = (
        f'"{pg_dump_command}" '
        f'--dbname=postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name} '
        f'--format=c '
        f'--file="{file_path}"'
    )
    
    try:
        result = subprocess.run(command_str, shell=True, check=True, capture_output=True, text=True)
        return f"Yedekleme başarıyla tamamlandı: {file_path}"
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Yedekleme komutu hatası: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Beklenmeyen bir hata oluştu: {e}")
    
def run_restore_command(file_path: str) -> str:
    pg_bin_path = os.getenv("PG_BIN_PATH")
    pg_restore_command = None
    psql_command_path = None
    
    if pg_bin_path:
        logging.info(f"Ortam değişkeninden PG_BIN_PATH okundu: {pg_bin_path}")
        pg_restore_command = os.path.join(pg_bin_path, "pg_restore")
        psql_command_path = os.path.join(pg_bin_path, "psql")
    
    if not pg_restore_command or not psql_command_path:
        logging.info("PG_BIN_PATH kullanılamadı. Sistem PATH'inde komutlar aranıyor.")
        pg_restore_command = shutil.which("pg_restore")
        psql_command_path = shutil.which("psql")

    if not pg_restore_command:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Geri yükleme komutu (pg_restore) bulunamadı. Lütfen PostgreSQL'in 'bin' dizinini "
                "sistem PATH'inize veya PG_BIN_PATH ortam değişkenine eklediğinizden emin olun."
            )
        )
    if not psql_command_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="psql komutu bulunamadı. Lütfen sistem PATH'inizi veya PG_BIN_PATH ortam değişkeninizi kontrol edin."
        )

    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")

    env_vars = os.environ.copy()
    env_vars["PGPASSWORD"] = db_password
    
    try:
        drop_db_command = [
            psql_command_path,
            f"--host={db_host}",
            f"--port={db_port}",
            f"--username={db_user}",
            "--dbname=postgres",
            f"--command=DROP DATABASE IF EXISTS \"{db_name}\" WITH (FORCE);"
        ]
        subprocess.run(drop_db_command, check=True, env=env_vars)

        create_db_command = [
            psql_command_path,
            f"--host={db_host}",
            f"--port={db_port}",
            f"--username={db_user}",
            "--dbname=postgres",
            f"--command=CREATE DATABASE \"{db_name}\";"
        ]
        subprocess.run(create_db_command, check=True, env=env_vars)

        restore_command = [
            pg_restore_command,
            f"--dbname=postgresql://{db_user}@{db_host}:{db_port}/{db_name}",
            "--no-owner",
            file_path
        ]
        subprocess.run(restore_command, check=True, env=env_vars)

        return f"Veritabanı başarıyla geri yüklendi: {file_path}"
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Geri yükleme komutu hatası: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Beklenmeyen bir hata oluştu: {e}")

@router.post("/yedekle")
def yedekle(request: BackupRequest):
    if not request.file_path:
        backup_dir = os.path.join(os.getcwd(), 'yedekler')
        os.makedirs(backup_dir, exist_ok=True)
        file_name = f"yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        file_path = os.path.join(backup_dir, file_name)
    else:
        file_path = request.file_path
    
    try:
        message = run_backup_command(file_path)
        return {"message": message, "file_path": file_path}
    except HTTPException as e:
        raise e

@router.post("/geri_yukle")
def geri_yukle(request: RestoreRequest):
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Belirtilen dosya bulunamadı: {request.file_path}")
    
    try:
        message = run_restore_command(request.file_path)
        return {"message": message}
    except HTTPException as e:
        raise e

@router.delete("/clear_all_data", status_code=status.HTTP_200_OK, summary="Tüm verileri temizle (Kullanıcılar Hariç)")
def clear_all_data(
    kullanici_id: int = Query(..., description="Kullanıcı ID"),
    db: Session = Depends(get_db)
):
    try:
        tables_to_clear = [
            semalar.FaturaKalemi,
            semalar.SiparisKalemi,
            semalar.StokHareket,
            semalar.CariHareket,
            semalar.KasaBankaHareket,
            semalar.GelirGider, 
            semalar.Fatura,
            semalar.Siparis,
            semalar.Stok,
            semalar.Musteri,
            semalar.Tedarikci,
            semalar.KasaBanka,
            semalar.UrunBirimi,
            semalar.UrunMarka,
            semalar.UrunKategori,
            semalar.UrunGrubu,
            semalar.Ulke,
            semalar.GelirSiniflandirma,
            semalar.GiderSiniflandirma
        ]
        
        for table in tables_to_clear:
            db.query(table).filter(table.kullanici_id == kullanici_id).delete(synchronize_session=False)

        db.commit()

        return {"message": "Kullanıcıya ait tüm veriler başarıyla temizlendi."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Veri temizleme sırasında hata oluştu: {e}")
    
@router.post("/ilk_veri_olustur", status_code=status.HTTP_200_OK)
def initial_data_setup_endpoint(
    kullanici_id: int = Query(..., description="Kullanıcı ID"),
    db: Session = Depends(get_db)
):
    """
    Kullanıcı oluşturma sonrası varsayılan nitelikleri, carileri ve kasayı ekler.
    Bu rota, create_user.py scripti tarafından çağrılır.
    """
    try:
        # Varsayılan veri oluşturma servisini çağır
        create_initial_data(db=db, kullanici_id=kullanici_id)
        
        return {"message": f"Varsayılan veriler kullanıcı {kullanici_id} için başarıyla oluşturuldu."}
        
    except Exception as e:
        db.rollback()
        # Bu hata, verilerin zaten var olmasından kaynaklanıyorsa, işlemi yoksayabiliriz.
        if "already exists" in str(e):
            return {"message": f"Varsayılan veriler zaten mevcut."}

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Varsayılan veri oluşturma hatası: {e}")    