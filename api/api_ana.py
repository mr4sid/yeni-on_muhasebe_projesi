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
from .veritabani import DATABASE_URL, get_db, SessionLocal 
# Başlangıç verileri için kullanılacak modeller
from .modeller import (
    Base, Musteri, Tedarikci, Kullanici, Stok, Fatura, FaturaKalemi,
    CariHareket, Siparis, SiparisKalemi, StokHareket,
    SirketBilgileri, SirketAyarlari, KasaBankaHesap, GelirGider, UrunNitelik
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

# Uygulama başlangıcında tabloları oluşturacak motor
engine = create_engine(str(DATABASE_URL))

app = FastAPI(
    title="Ön Muhasebe Sistemi API",
    description="Ön muhasebe sistemi için RESTful API",
    version="1.0.0",
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uygulama başladıktan sonra çalışacak olay
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Uygulama başlangıç ve kapanışında çalışacak kod.
    Veritabanı tablolarını oluşturur ve başlangıç verilerini ekler.
    """
    logger.info("API başlatılıyor...")
    
    # Düzeltme: Veritabanı motorunu doğrudan oluşturup tabloları yaratıyoruz
    try:
        from .veritabani import get_engine
        engine = get_engine()
        # --- BU SATIRI YORUM SATIRI YAPIYORUZ ---
        # Base.metadata.create_all(bind=engine) 
        logger.info("Veritabanı tablolarının kontrolü Alembic'e devredildi.")
    except Exception as e:
        logger.error(f"Veritabanı motoru başlatılırken hata oluştu: {e}")
    
    # Başlangıç verilerini kontrol etme
    db = next(get_db()) # Düzeltme: get_db() fonksiyonu ile bir oturum alınıyor.
    try:
        if db.query(Kullanici).count() == 0:
            logger.info("Hiç kullanıcı yok. Örnek kullanıcı ve veriler oluşturulacak.")
            # Burada create_initial_data() gibi bir fonksiyon çağırılabilir
    except Exception as e:
        logger.error(f"Başlangıç verileri kontrol edilirken hata oluştu: {e}")
    finally:
        db.close()
    
    yield
    logger.info("API kapanıyor...")

app = FastAPI(
    lifespan=lifespan,
    title="Ön Muhasebe Sistemi API",
    description="Ön muhasebe sistemi için RESTful API",
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
app.include_router(kullanicilar.router, tags=["Kullanıcılar"])
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
    return {"message": "On Muhasebe API'sine hoş geldiniz!"}