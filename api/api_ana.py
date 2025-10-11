# api/api_ana.py dosyasının TAMAMI (Database-per-Tenant Uyumlu Import ve Yaşam Döngüsü)
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text 
import logging
from datetime import datetime
from contextlib import asynccontextmanager 
from typing import AsyncGenerator
from sqlalchemy.future import create_engine 
from sqlalchemy.orm import sessionmaker 
# KRİTİK DÜZELTME 1: SessionLocal ve get_db kaldırıldı. Master DB fonksiyonları eklendi.
from .veritabani import get_master_db, get_master_engine 
from api import modeller
# Başlangıç verileri için kullanılacak modeller
from api.modeller import (
    Base, Kullanici, Firma, Ayarlar # Master DB'deki modeller
)
# Mevcut rotaların içe aktarılması
from .rotalar import (
    dogrulama, musteriler, tedarikciler, stoklar,
    kasalar_bankalar, cari_hareketler,
    gelir_gider, nitelikler, sistem, raporlar, yedekleme, kullanicilar,
    yonetici
)
from .rotalar.siparis_faturalar import siparisler_router, faturalar_router 

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Uygulama başlangıcında Master DB motorunu hazırlar
engine = get_master_engine()

# Uygulama başladıktan sonra çalışacak olay
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Uygulama başlangıç ve kapanışında çalışacak kod.
    Master DB tablolarının varlığını kontrol eder.
    """
    logger.info("API başlatılıyor...")
    
    # Master DB tablolarının (Kullanici, Firma, Ayarlar) varlığını kontrol et
    try:
        # SADECE Master DB'yi ilgilendiren tablolar oluşturulur
        Base.metadata.create_all(bind=get_master_engine(), tables=[modeller.Kullanici.__table__, modeller.Firma.__table__, modeller.Ayarlar.__table__]) 
        logger.info("Master DB (Firma, Kullanici) şeması kontrol edildi/oluşturuldu.")
    except Exception as e:
        logger.error(f"Master DB şeması oluşturulurken hata oluştu: {e}")
    
    # Başlangıç verilerini kontrol etme (Master DB kullanılır)
    db = next(get_master_db()) # Master DB oturumu alınır.
    try:
        default_email = "admin@master.com"
        # Kullanıcı var mı kontrolü (ORM yapılandırmasını tetikler)
        if db.query(modeller.Kullanici).filter(modeller.Kullanici.email == default_email).first() is None:
             logger.warning("Master admin kullanıcısı bulunamadı. Lütfen create_or_update_pg_tables.py scriptini çalıştırın.")

    except Exception as e:
        logger.error(f"Başlangıç verileri kontrol edilirken veya ORM yapılandırılırken hata oluştu: {e}")
    finally:
        db.close()
    
    yield
    logger.info("API kapanıyor...")

app = FastAPI(
    lifespan=lifespan,
    title="Ön Muhasebe Sistemi API",
    description="Ön muhasebe sistemi için RESTful API (Database-per-Tenant)",
    version="1.0.0",
)

# CORS ayarları
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları (rotaları) uygulamaya dahil etme
app.include_router(dogrulama.router, tags=["Kimlik Doğrulama"])
app.include_router(kullanicilar.router, tags=["Personel Yönetimi"])
app.include_router(musteriler.router, tags=["Müşteriler"])
app.include_router(tedarikciler.router, tags=["Tedarikçiler"])
app.include_router(stoklar.router, tags=["Stoklar"])
app.include_router(kasalar_bankalar.router, tags=["Kasalar ve Bankalar"])
app.include_router(cari_hareketler.router, tags=["Cari Hareketler"])
app.include_router(gelir_gider.router, tags=["Gelir ve Giderler"])
app.include_router(nitelikler.router, tags=["Nitelikler"])
app.include_router(sistem.router, tags=["Sistem"])
app.include_router(raporlar.router, tags=["Raporlar"])
app.include_router(yedekleme.router, tags=["Yedekleme"])
app.include_router(yonetici.router, tags=["Yönetici"])
app.include_router(siparisler_router, tags=["Siparişler"])
app.include_router(faturalar_router, tags=["Faturalar"])

@app.get("/")
def read_root():
    return {"message": "On Muhasebe API'sine hoş geldiniz! (Database-per-Tenant Aktif)"}