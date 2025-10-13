# api/modeller.py Dosyasının Tam ve güncel içeriği.
from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import date, datetime
from typing import List, Optional, Union, Literal
import enum
from sqlalchemy.sql import func
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
    ForeignKey, Date, Enum, or_, and_, text, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base, foreign

# --- ENUM TANIMLARI ---
class FaturaTuruEnum(str, enum.Enum): SATIS = "SATIS"; ALIS = "ALIS"; SATIS_IADE = "SATIS_IADE"; ALIS_IADE = "ALIS_IADE"; DEVIR_GIRIS = "DEVIR_GIRIS"
class OdemeTuruEnum(str, enum.Enum): NAKIT = "NAKIT"; KART = "KART"; EFT_HAVALE = "EFT_HAVALE"; CEK = "CEK"; SENET = "SENET"; ACIK_HESAP = "ACIK_HESAP"; ETKISIZ_FATURA = "ETKISIZ_FATURA"
class CariTipiEnum(str, enum.Enum): MUSTERI = "MUSTERI"; TEDARIKCI = "TEDARIKCI"
class IslemYoneEnum(str, enum.Enum): GIRIS = "GIRIS"; CIKIS = "CIKIS"; BORC = "BORC"; ALACAK = "ALACAK"
class KasaBankaTipiEnum(str, enum.Enum): KASA = "KASA"; BANKA = "BANKA"
class StokIslemTipiEnum(str, enum.Enum): GIRIS = "GIRIS"; CIKIS = "CIKIS"; SAYIM_FAZLASI = "SAYIM_FAZLASI"; SAYIM_EKSİĞİ = "SAYIM_EKSİĞİ"; SATIŞ = "SATIŞ"; ALIŞ = "ALIŞ"; SATIŞ_İADE = "SATIŞ_İADE"; ALIŞ_İADE = "ALIŞ_İADE"; KONSİNYE_GIRIS = "KONSİNYE_GIRIS"; KONSİNYE_CIKIS = "KONSİNYE_CIKIS"
class SiparisTuruEnum(str, enum.Enum): SATIS_SIPARIS = "SATIŞ_SIPARIS"; ALIS_SIPARIS = "ALIŞ_SIPARIS"
class SiparisDurumEnum(str, enum.Enum): BEKLEMEDE = "BEKLEMEDE"; TAMAMLANDI = "TAMAMLANDI"; KISMİ_TESLIMAT = "KISMİ_TESLİMAT"; IPTAL_EDILDI = "İPTAL_EDİLDİ"; FATURALASTIRILDI = "FATURALAŞTIRILDI"
class KaynakTipEnum(str, enum.Enum): FATURA = "FATURA"; SIPARIS = "SIPARIS"; GELIR_GIDER = "GELIR_GIDER"; MANUEL = "MANUEL"; TAHSILAT = "TAHSİLAT"; ODEME = "ÖDEME"; VERESIYE_BORC_MANUEL = "VERESİYE_BORÇ_MANUEL"
class GelirGiderTipEnum(str, enum.Enum): GELİR = "GELİR"; GİDER = "GİDER"

Base = declarative_base()

# --- PYDANTIC ŞEMALARI İÇİN TEMEL MODELLER ---
class BaseOrmModel(BaseModel): model_config = ConfigDict(from_attributes=True)

class Firma(Base):
    __tablename__ = 'firmalar'

    id = Column(Integer, primary_key=True)
    firma_adi = Column(String(200), unique=True, nullable=False)
    tenant_db_name = Column(String(200), unique=True, nullable=False)

    # Bu ForeignKey tanımı doğru
    kurucu_personel_id = Column(Integer, ForeignKey('kullanicilar.id'))

    # SQLAlchemy'ye hangi ForeignKey'i kullanacağını söylüyoruz
    kullanicilar = relationship("Kullanici", back_populates="firma", foreign_keys="[Kullanici.firma_id]")
    kurucu_personel = relationship("Kullanici", back_populates="kurdugu_firma", foreign_keys=[kurucu_personel_id])

# --- SİRKET MODELLERİ (ORM) ---
class SirketBilgileri(Base):
    __tablename__ = 'sirket_bilgileri'; id = Column(Integer, primary_key=True); sirket_adi = Column(String(100), nullable=False); adres = Column(String(200)); telefon = Column(String(20)); email = Column(String(50)); vergi_dairesi = Column(String(100)); vergi_no = Column(String(20)); kullanici_id = Column(Integer, unique=True, nullable=False)
class SirketAyarlari(Base):
    __tablename__ = 'sirket_ayarlari'; id = Column(Integer, primary_key=True); ayar_adi = Column(String(100), unique=True, nullable=False); ayar_degeri = Column(String(255)); kullanici_id = Column(Integer, unique=True, nullable=False)

class Sirket(Base): # Tenant DB'deki eski Sirket modelinin adı
    __tablename__ = 'sirketler'
    id = Column(Integer, primary_key=True)
    sirket_adi = Column(String)
    sirket_adresi = Column(Text, nullable=True)
    sirket_telefonu = Column(String, nullable=True)
    sirket_email = Column(String, nullable=True)
    sirket_vergi_dairesi = Column(String, nullable=True)
    sirket_vergi_no = Column(String, nullable=True)
    sirket_logo_yolu = Column(String, nullable=True)

# Şirket Bilgileri (Pydantic)
class SirketBase(BaseOrmModel):
    sirket_adi: Optional[str] = None
    sirket_adresi: Optional[str] = None
    sirket_telefonu: Optional[str] = None
    sirket_email: Optional[EmailStr] = None
    sirket_vergi_dairesi: Optional[str] = None
    sirket_vergi_no: Optional[str] = None
    sirket_logo_yolu: Optional[str] = None

class SirketCreate(SirketBase):
    sirket_adi: str

class SirketRead(SirketBase):
    id: int
    sirket_adi: str

class SirketListResponse(BaseModel):
    items: List[SirketRead]
    total: int
# --- SİRKET MODELLERİ SONU ---

# --- AYARLAR MODELLERİ ---
class Ayarlar(Base):
    __tablename__ = 'ayarlar'
    __table_args__ = (UniqueConstraint('ad', 'kullanici_id'),) 
    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String(100), index=True, nullable=False) 
    deger = Column(Text, nullable=True)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)
    kullanici = relationship("Kullanici", back_populates="master_ayarlar", foreign_keys=[kullanici_id])
# --- AYARLAR MODELLERİ SONU ---

# --- KULLANICI MODELLERİ (ORM) ---
class Kullanici(Base):
    __tablename__ = 'kullanicilar'

    id = Column(Integer, primary_key=True)
    sifre_hash = Column(String(255))
    ad = Column(String(50))
    soyad = Column(String(50))
    email = Column(String(100), unique=True)
    telefon = Column(String(20))

    # Bu ForeignKey tanımı doğru
    firma_id = Column(Integer, ForeignKey('firmalar.id', ondelete="SET NULL"), nullable=True)
    rol = Column(String(50), default='kullanici')
    aktif = Column(Boolean, default=True)
    olusturma_tarihi = Column(DateTime, server_default=func.now())
    son_giris_tarihi = Column(DateTime, nullable=True)
    # SQLAlchemy'ye hangi ForeignKey'i kullanacağını söylüyoruz
    firma = relationship("Firma", back_populates="kullanicilar", foreign_keys=[firma_id])
    # Diğer ilişkiler (bunlar doğru)
    faturalar = relationship("Fatura", back_populates="kullanici")
    stoklar = relationship("Stok", back_populates="kullanici")
    kurdugu_firma = relationship("Firma", back_populates="kurucu_personel", foreign_keys=[Firma.kurucu_personel_id])
    master_ayarlar = relationship("Ayarlar", back_populates="kullanici")
    
class FirmaRead(BaseOrmModel): id: int; firma_adi: str; tenant_db_name: str; olusturma_tarihi: datetime

# Kullanıcı Modelleri (Pydantic)
class KullaniciBase(BaseOrmModel): ad: str; soyad: str; email: EmailStr; telefon: Optional[str] = None; rol: Optional[str] = "admin"; aktif: Optional[bool] = True

class KullaniciCreate(KullaniciBase): sifre: str; firma_adi: str

class KullaniciLogin(BaseModel):
    """Giriş artık e-posta ile yapılır."""
    email: EmailStr
    sifre: str

class KullaniciRead(KullaniciBase):
    id: int
    firma_id: Optional[int] = None
    firma_adi: Optional[str] = None
    tenant_db_name: Optional[str] = None 
    olusturma_tarihi: datetime
    son_giris_tarihi: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True, exclude={'sifre_hash'})

class KullaniciUpdate(BaseModel):
    kullanici_adi: Optional[str] = None
    sifre: Optional[str] = None
    aktif: Optional[bool] = None
    rol: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    firma_adi: str

class TokenData(BaseModel):
    kullanici_adi: Optional[str] = None

class KullaniciListResponse(BaseModel):
    items: List[KullaniciRead]
    total: int
# --- KULLANICI MODELLERİ SONU ---

# --- CARİ (MÜŞTERİ/TEDARİKÇİ) MODELLERİ (ORM) ---
class Musteri(Base):
    __tablename__ = 'musteriler'; id = Column(Integer, primary_key=True); ad = Column(String(100)); kod = Column(String(50)); adres = Column(String(255)); telefon = Column(String(50)); email = Column(String(100)); vergi_dairesi = Column(String(100)); vergi_no = Column(String(50)); aktif = Column(Boolean, default=True); olusturma_tarihi = Column(DateTime, server_default=func.now()); kullanici_id = Column(Integer, nullable=False)

class Tedarikci(Base):
    __tablename__ = 'tedarikciler'; id = Column(Integer, primary_key=True); ad = Column(String(100)); kod = Column(String(50)); adres = Column(String(255)); telefon = Column(String(20)); email = Column(String(100)); vergi_dairesi = Column(String(100)); vergi_no = Column(String(20)); aktif = Column(Boolean, default=True); olusturma_tarihi = Column(DateTime, server_default=func.now()); kullanici_id = Column(Integer, nullable=False)

# Cari (Müşteri/Tedarikçi) Modelleri (Pydantic)
class CariBase(BaseOrmModel):
    ad: str
    telefon: Optional[str] = None
    adres: Optional[str] = None
    vergi_dairesi: Optional[str] = None
    vergi_no: Optional[str] = None
    aktif: Optional[bool] = True
    email: Optional[EmailStr] = None

class MusteriCreate(CariBase):
    kod: Optional[str] = None
    kullanici_id: Optional[int] = None

class MusteriUpdate(CariBase):
    ad: Optional[str] = None
    kod: Optional[str] = None
    telefon: Optional[str] = None
    adres: Optional[str] = None
    vergi_dairesi: Optional[str] = None
    vergi_no: Optional[str] = None
    aktif: Optional[bool] = None
    kullanici_id: Optional[int] = None
    email: Optional[EmailStr] = None

class MusteriRead(CariBase):
    id: int
    kod: Optional[str] = None
    olusturma_tarihi: datetime
    net_bakiye: Optional[float] = Field(0.0, description="Cari net bakiyesi")

class MusteriListResponse(BaseModel):
    items: List[MusteriRead]
    total: int

class TedarikciCreate(CariBase):
    kod: Optional[str] = None
    kullanici_id: Optional[int] = None

class TedarikciUpdate(CariBase):
    ad: Optional[str] = None
    kod: Optional[str] = None
    telefon: Optional[str] = None
    adres: Optional[str] = None
    vergi_dairesi: Optional[str] = None
    vergi_no: Optional[str] = None
    aktif: Optional[bool] = None
    kullanici_id: Optional[int] = None
    email: Optional[EmailStr] = None

class TedarikciRead(CariBase):
    id: int
    kod: Optional[str] = None
    olusturma_tarihi: datetime
    net_bakiye: Optional[float] = Field(0.0, description="Cari net bakiyesi")

class TedarikciListResponse(BaseModel):
    items: List[TedarikciRead]
    total: int

class CariListResponse(BaseModel):
    items: List[Union[MusteriRead, TedarikciRead]]
    total: int
# --- CARİ MODELLERİ SONU ---

# --- KASA/BANKA MODELLERİ (ORM) ---
class KasaBankaHesap(Base):
    __tablename__ = 'kasalar_bankalar'
    __table_args__ = (
        UniqueConstraint('hesap_adi', 'kullanici_id'),
        UniqueConstraint('kod', 'kullanici_id'),
        UniqueConstraint('hesap_no', 'kullanici_id'),
        UniqueConstraint('iban', 'kullanici_id')
    )
    id = Column(Integer, primary_key=True, index=True)
    hesap_adi = Column(String(100), index=True, nullable=False)
    kod = Column(String(50), nullable=True, index=True)
    tip = Column(Enum(KasaBankaTipiEnum), nullable=False)
    aktif = Column(Boolean, default=True)
    bakiye = Column(Float, default=0.0)
    para_birimi = Column(String(10), default="TL")
    banka_adi = Column(String(100), nullable=True)
    sube_adi = Column(String(100), nullable=True)
    hesap_no = Column(String(50), nullable=True, index=True)
    iban = Column(String(50), nullable=True, index=True)
    swift_kodu = Column(String(20), nullable=True)
    varsayilan_odeme_turu = Column(String(50), nullable=True)
    olusturma_tarihi = Column(DateTime, server_default=func.now())
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)

    kullanici = relationship("Kullanici", foreign_keys=[kullanici_id], viewonly=True)
    
    # İLİŞKİLERİN DÜZELTİLMİŞ HALİ
    hareketler = relationship("KasaBankaHareket", back_populates="kasa_banka_hesabi", cascade="all, delete-orphan")
    faturalar = relationship("Fatura", back_populates="kasa_banka")
    cari_hareketler = relationship("CariHareket", back_populates="kasa_banka")

# Kasa/Banka Modelleri (Pydantic)
class KasaBankaBase(BaseOrmModel):
    hesap_adi: str
    kod: Optional[str] = None 
    tip: KasaBankaTipiEnum
    bakiye: Optional[float] = 0.0
    para_birimi: str = "TL" 
    banka_adi: Optional[str] = None
    sube_adi: Optional[str] = None
    hesap_no: Optional[str] = None
    varsayilan_odeme_turu: Optional[str] = None
    aktif: Optional[bool] = True

class KasaBankaCreate(KasaBankaBase):
    kullanici_id: Optional[int] = None

class KasaBankaUpdate(KasaBankaBase):
    hesap_adi: Optional[str] = None
    tip: Optional[KasaBankaTipiEnum] = None
    bakiye: Optional[float] = None
    para_birimi: Optional[str] = None
    aktif: Optional[bool] = None
    banka_adi: Optional[str] = None
    sube_adi: Optional[str] = None
    hesap_no: Optional[str] = None
    varsayilan_odeme_turu: Optional[str] = None
    kullanici_id: Optional[int] = None    

class KasaBankaRead(KasaBankaBase):
    id: int
    aktif: bool
    olusturma_tarihi: datetime

class KasaBankaListResponse(BaseModel):
    items: List[KasaBankaRead]
    total: int
# --- KASA/BANKA MODELLERİ SONU ---

# --- STOK MODELLERİ (ORM) ---
class Stok(Base):
    __tablename__ = 'stoklar'

    id = Column(Integer, primary_key=True)
    kod = Column(String(50))
    ad = Column(String(200))
    detay = Column(Text)
    miktar = Column(Float, default=0.0)
    alis_fiyati = Column(Float, default=0.0)
    satis_fiyati = Column(Float, default=0.0)
    kdv_orani = Column(Float, default=20.0)
    min_stok_seviyesi = Column(Float, default=0.0)
    aktif = Column(Boolean, default=True)
    urun_resmi_yolu = Column(String(255))
    olusturma_tarihi = Column(DateTime, server_default=func.now())

    kategori_id = Column(Integer, ForeignKey('urun_kategorileri.id'))
    marka_id = Column(Integer, ForeignKey('urun_markalari.id'))
    urun_grubu_id = Column(Integer, ForeignKey('urun_gruplari.id'))
    birim_id = Column(Integer, ForeignKey('urun_birimleri.id'))
    mense_id = Column(Integer, ForeignKey('ulkeler.id'))
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)

    kategori = relationship("UrunKategori", back_populates="stoklar")
    marka = relationship("UrunMarka", back_populates="stoklar")
    urun_grubu = relationship("UrunGrubu", back_populates="stoklar")
    birim = relationship("UrunBirimi", back_populates="stoklar")
    mense_ulke = relationship("Ulke", back_populates="stoklar")
    kullanici = relationship("Kullanici", back_populates="stoklar")

    hareketler = relationship("StokHareket", back_populates="urun", cascade="all, delete-orphan")
    fatura_kalemleri = relationship("FaturaKalemi", back_populates="urun")

    __table_args__ = (UniqueConstraint('kod', 'kullanici_id', name='unique_kod_kullanici'),)

# Stok Modelleri (Pydantic)
class StokBase(BaseOrmModel):
    kod: str
    ad: str
    detay: Optional[str] = None
    miktar: float = Field(default=0.0)
    alis_fiyati: float = Field(default=0.0)
    satis_fiyati: float = Field(default=0.0)
    kdv_orani: float = Field(default=20.0)
    min_stok_seviyesi: float = Field(default=0.0)
    aktif: Optional[bool] = True
    urun_resmi_yolu: Optional[str] = None
    kategori_id: Optional[int] = None
    marka_id: Optional[int] = None
    urun_grubu_id: Optional[int] = None
    birim_id: Optional[int] = None
    mense_id: Optional[int] = None
    
class StokCreate(StokBase):
    kullanici_id: Optional[int] = None

class StokUpdate(StokBase):
    kod: Optional[str] = None
    ad: Optional[str] = None
    detay: Optional[str] = None
    miktar: Optional[float] = None
    alis_fiyati: Optional[float] = None
    satis_fiyati: Optional[float] = None
    kdv_orani: Optional[float] = None
    min_stok_seviyesi: Optional[float] = None
    aktif: Optional[bool] = None
    urun_resmi_yolu: Optional[str] = None
    kategori_id: Optional[int] = None
    marka_id: Optional[int] = None
    urun_grubu_id: Optional[int] = None
    birim_id: Optional[int] = None
    mense_id: Optional[int] = None
    kullanici_id: Optional[int] = None

class StokRead(StokBase):
    id: int
    olusturma_tarihi: datetime
    kategori: Optional['UrunKategoriRead'] = None 
    marka: Optional['UrunMarkaRead'] = None
    urun_grubu: Optional['UrunGrubuRead'] = None
    birim: Optional['UrunBirimiRead'] = None
    mense_ulke: Optional['UlkeRead'] = None

class StokListResponse(BaseModel):
    items: List[StokRead]
    total: int

class AnlikStokMiktariResponse(BaseModel):
    anlik_miktar: float
# --- STOK MODELLERİ SONU ---

# --- FATURA MODELLERİ (ORM) ---
class Fatura(Base):
    __tablename__ = 'faturalar'
    id = Column(Integer, primary_key=True)
    fatura_no = Column(String(50))
    tarih = Column(Date)
    fatura_turu = Column(Enum(FaturaTuruEnum))
    cari_id = Column(Integer)
    cari_tip = Column(String(20))
    odeme_turu = Column(Enum(OdemeTuruEnum))
    odeme_durumu = Column(String(20), default="ÖDENMEDİ")
    toplam_kdv_haric = Column(Float, default=0.0)
    toplam_kdv_dahil = Column(Float, default=0.0)
    toplam_kdv = Column(Float, default=0.0)
    genel_toplam = Column(Float, default=0.0)
    kasa_banka_id = Column(Integer, ForeignKey('kasalar_bankalar.id'))
    fatura_notlari = Column(Text)
    vade_tarihi = Column(Date)
    genel_iskonto_tipi = Column(String(20), default="YOK")
    genel_iskonto_degeri = Column(Float, default=0.0)
    misafir_adi = Column(String(100))
    olusturma_tarihi_saat = Column(DateTime, server_default=func.now())
    son_guncelleme_tarihi_saat = Column(DateTime, onupdate=datetime.now)
    olusturan_kullanici_id = Column(Integer)
    son_guncelleyen_kullanici_id = Column(Integer)
    kullanici_id = Column(Integer, nullable=False)
    kasa_banka = relationship("KasaBankaHesap", back_populates="faturalar")
    kalemler = relationship("FaturaKalemi", back_populates="fatura", cascade="all, delete-orphan")
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)
    kullanici = relationship("Kullanici", back_populates="faturalar")
    
class FaturaKalemi(Base):
    __tablename__ = 'fatura_kalemleri'
    id = Column(Integer, primary_key=True)
    fatura_id = Column(Integer, ForeignKey('faturalar.id'))
    urun_id = Column(Integer, ForeignKey('stoklar.id'))
    miktar = Column(Float)
    birim_fiyat = Column(Float)
    kdv_orani = Column(Float, default=0.0)
    alis_fiyati_fatura_aninda = Column(Float)
    iskonto_yuzde_1 = Column(Float, default=0.0)
    iskonto_yuzde_2 = Column(Float, default=0.0)
    iskonto_tipi = Column(String(20))
    iskonto_degeri = Column(Float, default=0.0)
    olusturma_tarihi = Column(DateTime, server_default=func.now())
    fatura = relationship("Fatura", back_populates="kalemler")
    urun = relationship("Stok", back_populates="fatura_kalemleri")

# Fatura Modelleri (Pydantic)
class FaturaKalemiBase(BaseOrmModel):
    urun_id: int
    miktar: float
    birim_fiyat: float
    kdv_orani: float
    alis_fiyati_fatura_aninda: Optional[float] = None
    iskonto_yuzde_1: float = Field(default=0.0)
    iskonto_yuzde_2: float = Field(default=0.0)
    iskonto_tipi: Optional[str] = "YOK"
    iskonto_degeri: float = Field(default=0.0)

class FaturaKalemiCreate(FaturaKalemiBase):
    pass

class FaturaKalemiUpdate(FaturaKalemiBase):
    urun_id: Optional[int] = None
    miktar: Optional[float] = None
    birim_fiyat: Optional[float] = None
    kdv_orani: Optional[float] = None
    alis_fiyati_fatura_aninda: Optional[float] = None
    iskonto_yuzde_1: Optional[float] = None
    iskonto_yuzde_2: Optional[float] = None
    iskonto_tipi: Optional[str] = None
    iskonto_degeri: Optional[float] = None

class FaturaKalemiRead(FaturaKalemiBase):
    id: int
    fatura_id: int
    urun_adi: Optional[str] = None
    urun_kodu: Optional[str] = None
    kdv_tutari: Optional[float] = None
    kalem_toplam_kdv_haric: Optional[float] = None
    kalem_toplam_kdv_dahil: Optional[float] = None
    
class FaturaBase(BaseOrmModel):
    fatura_no: str
    fatura_turu: FaturaTuruEnum
    tarih: date
    vade_tarihi: Optional[date] = None
    cari_id: int
    cari_tip: CariTipiEnum
    misafir_adi: Optional[str] = None
    odeme_turu: OdemeTuruEnum
    kasa_banka_id: Optional[int] = None
    fatura_notlari: Optional[str] = None
    genel_iskonto_tipi: str = "YOK"
    genel_iskonto_degeri: float = Field(default=0.0)
    toplam_kdv_haric: Optional[float] = None 
    toplam_kdv_dahil: Optional[float] = None 
    genel_toplam: Optional[float] = None 

class FaturaCreate(FaturaBase):
    kalemler: List[FaturaKalemiCreate] = []
    original_fatura_id: Optional[int] = None
    olusturan_kullanici_id: Optional[int] = None
    kullanici_id: Optional[int] = None

class FaturaUpdate(FaturaBase):
    fatura_no: Optional[str] = None
    fatura_turu: Optional[FaturaTuruEnum] = None
    tarih: Optional[date] = None
    vade_tarihi: Optional[date] = None
    cari_id: Optional[int] = None
    cari_tip: Optional[CariTipiEnum] = None
    misafir_adi: Optional[str] = None
    odeme_turu: Optional[OdemeTuruEnum] = None
    kasa_banka_id: Optional[int] = None
    fatura_notlari: Optional[str] = None
    genel_iskonto_tipi: Optional[str] = None
    genel_iskonto_degeri: Optional[float] = None
    original_fatura_id: Optional[int] = None
    kalemler: Optional[List[FaturaKalemiCreate]] = None
    kullanici_id: Optional[int] = None

class FaturaRead(FaturaBase):
    id: int
    olusturma_tarihi_saat: datetime
    olusturan_kullanici_id: Optional[int] = None
    son_guncelleme_tarihi_saat: Optional[datetime] = None
    son_guncelleyen_kullanici_id: Optional[int] = None
    
    cari_adi: Optional[str] = None
    cari_kodu: Optional[str] = None
    kasa_banka_adi: Optional[str] = None
    
    toplam_kdv_haric: float
    toplam_kdv_dahil: float
    genel_toplam: float
    kalemler: List[FaturaKalemiRead] = []

class FaturaListResponse(BaseModel):
    items: List[FaturaRead]
    total: int

class NextFaturaNoResponse(BaseModel):
    fatura_no: str
# --- FATURA MODELLERİ SONU ---

# --- STOK HAREKET MODELLERİ (ORM) ---
class StokHareket(Base):
    __tablename__ = 'stok_hareketleri'

    id = Column(Integer, primary_key=True)
    tarih = Column(Date)
    urun_id = Column(Integer, ForeignKey('stoklar.id'), nullable=False)
    islem_tipi = Column(Enum(StokIslemTipiEnum))
    miktar = Column(Float)
    birim_fiyat = Column(Float, default=0.0)
    onceki_stok = Column(Float)
    sonraki_stok = Column(Float)
    aciklama = Column(Text)
    kaynak = Column(String(50))
    kaynak_id = Column(Integer)
    olusturma_tarihi = Column(DateTime, server_default=func.now())
    kullanici_id = Column(Integer, nullable=False)
    urun = relationship("Stok", back_populates="hareketler")

# Stok Hareket Modelleri (Pydantic)
class StokHareketBase(BaseOrmModel):
    stok_id: int
    tarih: date
    islem_tipi: StokIslemTipiEnum
    miktar: float
    birim_fiyat: float = Field(default=0.0)
    aciklama: Optional[str] = None
    kaynak: KaynakTipEnum
    kaynak_id: Optional[int] = None

class StokHareketCreate(StokHareketBase):
    kullanici_id: Optional[int] = None

class StokHareketUpdate(StokHareketBase):
    stok_id: Optional[int] = None
    tarih: Optional[date] = None
    islem_tipi: Optional[StokIslemTipiEnum] = None
    miktar: Optional[float] = None
    birim_fiyat: Optional[float] = None
    aciklama: Optional[str] = None
    kaynak: Optional[KaynakTipEnum] = None
    kaynak_id: Optional[int] = None
    kullanici_id: Optional[int] = None

class StokHareketRead(StokHareketBase):
    id: int
    olusturma_tarihi_saat: Optional[datetime] = None
    onceki_stok: Optional[float] = None
    sonraki_stok: Optional[float] = None
    stok: Optional[StokRead] = None

class StokHareketListResponse(BaseModel):
    items: List[StokHareketRead]
    total: int
# --- STOK HAREKET MODELLERİ SONU ---

# --- SİPARİŞ MODELLERİ (ORM) ---
class Siparis(Base):
    __tablename__ = 'siparisler'; id = Column(Integer, primary_key=True); siparis_no = Column(String(50), unique=True); siparis_turu = Column(Enum(SiparisTuruEnum)); durum = Column(Enum(SiparisDurumEnum)); tarih = Column(Date); teslimat_tarihi = Column(Date); cari_id = Column(Integer); cari_tip = Column(String(20)); siparis_notlari = Column(Text); genel_toplam = Column(Float, default=0.0); kullanici_id = Column(Integer, nullable=False); olusturma_tarihi = Column(DateTime, server_default=func.now())

class SiparisKalemi(Base):
    __tablename__ = 'siparis_kalemleri'; id = Column(Integer, primary_key=True); siparis_id = Column(Integer, ForeignKey('siparisler.id')); urun_id = Column(Integer, ForeignKey('stoklar.id')); miktar = Column(Float, default=0.0); birim_fiyat = Column(Float, default=0.0); kdv_orani = Column(Float, default=0.0); iskonto_yuzde_1 = Column(Float, default=0.0); iskonto_yuzde_2 = Column(Float, default=0.0); alis_fiyati_siparis_aninda = Column(Float); satis_fiyati_siparis_aninda = Column(Float); iskonto_tipi = Column(String(20), default="YOK"); iskonto_degeri = Column(Float, default=0.0); birim_fiyat_kdv_haric = Column(Float, default=0.0); toplam_tutar = Column(Float, default=0.0); olusturma_tarihi = Column(DateTime, server_default=func.now())

# Sipariş Modelleri (Pydantic)
class SiparisKalemiBase(BaseOrmModel):
    urun_id: int
    miktar: float
    birim_fiyat: float
    kdv_orani: float
    iskonto_yuzde_1: float = Field(default=0.0)
    iskonto_yuzde_2: float = Field(default=0.0)
    iskonto_tipi: Optional[str] = "YOK"
    iskonto_degeri: float = Field(default=0.0)
    alis_fiyati_siparis_aninda: Optional[float] = None
    satis_fiyati_siparis_aninda: Optional[float] = None

class SiparisKalemiCreate(SiparisKalemiBase):
    pass

class SiparisKalemiUpdate(SiparisKalemiBase):
    urun_id: Optional[int] = None
    miktar: Optional[float] = None
    birim_fiyat: Optional[float] = None
    kdv_orani: Optional[float] = None
    iskonto_yuzde_1: Optional[float] = None
    iskonto_yuzde_2: Optional[float] = None
    iskonto_tipi: Optional[str] = None
    iskonto_degeri: Optional[float] = None
    alis_fiyati_siparis_aninda: Optional[float] = None
    satis_fiyati_siparis_aninda: Optional[float] = None

class SiparisKalemiRead(SiparisKalemiBase):
    id: int
    siparis_id: int
    urun_adi: Optional[str] = None
    urun_kodu: Optional[str] = None
    kdv_tutari: Optional[float] = None
    kalem_toplam_kdv_haric: Optional[float] = None
    kalem_toplam_kdv_dahil: Optional[float] = None
    
class SiparisBase(BaseOrmModel):
    siparis_no: str
    siparis_turu: SiparisTuruEnum
    durum: SiparisDurumEnum
    tarih: date
    teslimat_tarihi: Optional[date] = None
    cari_id: int
    cari_tip: CariTipiEnum
    siparis_notlari: Optional[str] = None
    genel_iskonto_tipi: str = "YOK"
    genel_iskonto_degeri: float = Field(default=0.0)
    fatura_id: Optional[int] = None
    toplam_tutar: float = Field(default=0.0)

class SiparisCreate(SiparisBase):
    kalemler: List[SiparisKalemiCreate] = []
    kullanici_id: Optional[int] = None

class SiparisUpdate(SiparisBase):
    siparis_no: Optional[str] = None
    siparis_turu: Optional[SiparisTuruEnum] = None
    durum: Optional[SiparisDurumEnum] = None
    tarih: Optional[date] = None
    teslimat_tarihi: Optional[date] = None
    cari_id: Optional[int] = None
    cari_tip: Optional[CariTipiEnum] = None
    siparis_notlari: Optional[str] = None
    genel_iskonto_tipi: Optional[str] = None
    genel_iskonto_degeri: Optional[float] = None
    fatura_id: Optional[int] = None
    toplam_tutar: Optional[float] = None
    kalemler: Optional[List[SiparisKalemiCreate]] = None
    kullanici_id: Optional[int] = None

class SiparisRead(SiparisBase):
    id: int
    olusturma_tarihi_saat: Optional[datetime] = None
    olusturan_kullanici_id: Optional[int] = None
    son_guncelleme_tarihi_saat: Optional[datetime] = None
    son_guncelleyen_kullanici_id: Optional[int] = None
    
    cari_adi: Optional[str] = None
    cari_kodu: Optional[str] = None
    kalemler: List[SiparisKalemiRead] = []

class SiparisListResponse(BaseModel):
    items: List[SiparisRead]
    total: int

class NextSiparisNoResponse(BaseModel):
    siparis_no: str

class SiparisFaturaDonusum(BaseModel):
    odeme_turu: OdemeTuruEnum
    kasa_banka_id: Optional[int] = None
    vade_tarihi: Optional[date] = None
    olusturan_kullanici_id: Optional[int] = None
# --- SİPARİŞ MODELLERİ SONU ---

# --- GELİR/GİDER MODELLERİ (ORM) ---
class GelirGider(Base):
    __tablename__ = 'gelir_giderler'; id = Column(Integer, primary_key=True); tarih = Column(Date); tip = Column(Enum(GelirGiderTipEnum)); tutar = Column(Float); aciklama = Column(Text); kasa_banka_id = Column(Integer, ForeignKey('kasalar_bankalar.id')); cari_id = Column(Integer); kaynak = Column(String(50)); kaynak_id = Column(Integer); gelir_siniflandirma_id = Column(Integer, ForeignKey('gelir_siniflandirmalari.id')); gider_siniflandirma_id = Column(Integer, ForeignKey('gider_siniflandirmalari.id')); olusturma_tarihi = Column(DateTime, server_default=func.now()); kullanici_id = Column(Integer, nullable=False)

# Gelir/Gider Modelleri (Pydantic)
class GelirGiderBase(BaseOrmModel):
    tarih: date
    tip: GelirGiderTipEnum
    aciklama: str
    tutar: float
    odeme_turu: Optional[OdemeTuruEnum] = None
    kasa_banka_id: Optional[int] = None
    cari_id: Optional[int] = None
    cari_tip: Optional[CariTipiEnum] = None
    gelir_siniflandirma_id: Optional[int] = None
    gider_siniflandirma_id: Optional[int] = None
    kaynak: Optional[KaynakTipEnum] = KaynakTipEnum.MANUEL
    kaynak_id: Optional[int] = None

class GelirGiderCreate(GelirGiderBase):
    kullanici_id: Optional[int] = None

class GelirGiderUpdate(GelirGiderBase):
    tarih: Optional[date] = None
    tip: Optional[GelirGiderTipEnum] = None
    aciklama: Optional[str] = None
    tutar: Optional[float] = None
    odeme_turu: Optional[OdemeTuruEnum] = None
    kasa_banka_id: Optional[int] = None
    cari_id: Optional[int] = None
    cari_tip: Optional[CariTipiEnum] = None
    gelir_siniflandirma_id: Optional[int] = None
    gider_siniflandirma_id: Optional[int] = None
    kaynak: Optional[KaynakTipEnum] = None
    kaynak_id: Optional[int] = None
    kullanici_id: Optional[int] = None

class GelirGiderRead(GelirGiderBase):
    id: int
    olusturma_tarihi_saat: Optional[datetime] = None
    olusturan_kullanici_id: Optional[int] = None
    kasa_banka_adi: Optional[str] = None
    cari_ad: Optional[str] = None
    gelir_siniflandirma_adi: Optional[str] = None
    gider_siniflandirma_adi: Optional[str] = None

class GelirGiderListResponse(BaseModel):
    items: List[GelirGiderRead]
    total: int
# --- GELİR/GİDER MODELLERİ SONU ---

# --- CARİ HAREKET MODELLERİ (ORM) ---
class CariHareket(Base):
    __tablename__ = 'cari_hareketler'
    id = Column(Integer, primary_key=True, index=True)
    tarih = Column(Date, nullable=False)
    islem_turu = Column(String(50), nullable=False)
    islem_yone = Column(Enum(IslemYoneEnum), nullable=False)
    cari_id = Column(Integer, nullable=False)
    cari_tip = Column(String, nullable=False)
    tutar = Column(Float, nullable=False)
    odeme_turu = Column(Enum(OdemeTuruEnum), nullable=True)
    aciklama = Column(Text, nullable=True)
    kaynak = Column(String(50), nullable=False)
    kaynak_id = Column(Integer, nullable=True)
    kasa_banka_id = Column(Integer, ForeignKey('kasalar_bankalar.id'), nullable=True)
    vade_tarihi = Column(Date, nullable=True)
    olusturma_tarihi_saat = Column(DateTime, server_default=func.now())
    olusturan_kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)

    kullanici = relationship("Kullanici", foreign_keys=[kullanici_id], viewonly=True)
    olusturan_kullanici = relationship("Kullanici", foreign_keys=[olusturan_kullanici_id], viewonly=True)

    kasa_banka = relationship("KasaBankaHesap", back_populates="cari_hareketler")

    musteri = relationship("Musteri",
                          primaryjoin="and_(foreign(CariHareket.cari_id) == Musteri.id, CariHareket.cari_tip == 'MUSTERI')",
                          overlaps="cari_hareketler, tedarikci")

    tedarikci = relationship("Tedarikci",
                             primaryjoin="and_(foreign(CariHareket.cari_id) == Tedarikci.id, CariHareket.cari_tip == 'TEDARIKCI')",
                             overlaps="cari_hareketler, musteri")

# Cari Hareket Modelleri (Pydantic)
class CariHareketBase(BaseOrmModel):
    cari_id: int
    cari_tip: CariTipiEnum
    tarih: date
    islem_turu: str
    islem_yone: IslemYoneEnum
    tutar: float
    aciklama: Optional[str] = None
    kaynak: KaynakTipEnum
    kaynak_id: Optional[int] = None
    odeme_turu: Optional[OdemeTuruEnum] = None
    kasa_banka_id: Optional[int] = None
    vade_tarihi: Optional[date] = None

class CariHareketCreate(CariHareketBase):
    kullanici_id: Optional[int] = None

class CariHareketUpdate(CariHareketBase):
    cari_id: Optional[int] = None
    cari_tip: Optional[CariTipiEnum] = None
    tarih: Optional[date] = None
    islem_turu: Optional[str] = None
    islem_yone: Optional[IslemYoneEnum] = None
    tutar: Optional[float] = None
    aciklama: Optional[str] = None
    kaynak: Optional[KaynakTipEnum] = None
    kaynak_id: Optional[int] = None
    odeme_turu: Optional[OdemeTuruEnum] = None
    kasa_banka_id: Optional[int] = None
    vade_tarihi: Optional[date] = None
    kullanici_id: Optional[int] = None

class CariHareketRead(CariHareketBase):
    id: int
    olusturma_tarihi_saat: datetime
    olusturan_kullanici_id: Optional[int] = None
    fatura_no: Optional[str] = None
    fatura_turu: Optional[FaturaTuruEnum] = None
    islem_saati: Optional[str] = None

class CariHareketListResponse(BaseModel):
    items: List[CariHareketRead]
    total: int
# --- CARİ HAREKET MODELLERİ SONU ---

# --- KASA/BANKA HAREKET MODELLERİ (ORM) ---
class KasaBankaHareket(Base):
    __tablename__ = 'kasa_banka_hareketleri'
    id = Column(Integer, primary_key=True, index=True)
    kasa_banka_id = Column(Integer, ForeignKey('kasalar_bankalar.id'), index=True)
    tarih = Column(Date)
    islem_turu = Column(String)
    islem_yone = Column(Enum(IslemYoneEnum))
    tutar = Column(Float)
    aciklama = Column(Text, nullable=True)
    kaynak = Column(String)
    kaynak_id = Column(Integer, nullable=True)
    olusturma_tarihi_saat = Column(DateTime, default=datetime.now)
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=True)
    # EKSİK OLAN İLİŞKİ BURAYA EKLENDİ
    kasa_banka_hesabi = relationship("KasaBankaHesap", back_populates="hareketler")

# Kasa/Banka Hareket Modelleri (Pydantic)
class KasaBankaHareketBase(BaseOrmModel):
    kasa_banka_id: int
    tarih: date
    islem_turu: str
    islem_yone: IslemYoneEnum
    tutar: float
    aciklama: Optional[str] = None
    kaynak: KaynakTipEnum
    kaynak_id: Optional[int] = None

class KasaBankaHareketCreate(KasaBankaHareketBase):
    pass

class KasaBankaHareketUpdate(KasaBankaHareketBase):
    kasa_banka_id: Optional[int] = None
    tarih: Optional[date] = None
    islem_turu: Optional[str] = None
    islem_yone: Optional[IslemYoneEnum] = None
    tutar: Optional[float] = None
    aciklama: Optional[str] = None
    kaynak: Optional[KaynakTipEnum] = None
    kaynak_id: Optional[int] = None

class KasaBankaHareketRead(KasaBankaHareketBase):
    id: int
    olusturma_tarihi_saat: datetime

class KasaBankaHareketListResponse(BaseModel):
    items: List[KasaBankaHareketRead]
    total: int
# --- KASA/BANKA HAREKET MODELLERİ SONU ---

# --- NİTELİK MODELLERİ (ORM) ---
class UrunKategori(Base):
    __tablename__ = 'urun_kategorileri'
    id = Column(Integer, primary_key=True)
    ad = Column(String(100))
    kullanici_id = Column(Integer, nullable=False)
    stoklar = relationship("Stok", back_populates="kategori")

class UrunMarka(Base):
    __tablename__ = 'urun_markalari'
    id = Column(Integer, primary_key=True)
    ad = Column(String(100))
    kullanici_id = Column(Integer, nullable=False)
    stoklar = relationship("Stok", back_populates="marka")

class UrunGrubu(Base):
    __tablename__ = 'urun_gruplari'
    id = Column(Integer, primary_key=True)
    ad = Column(String(100))
    kullanici_id = Column(Integer, nullable=False)
    stoklar = relationship("Stok", back_populates="urun_grubu")

class UrunBirimi(Base):
    __tablename__ = 'urun_birimleri'
    id = Column(Integer, primary_key=True)
    ad = Column(String(50))
    kullanici_id = Column(Integer, nullable=False)
    stoklar = relationship("Stok", back_populates="birim")

class Ulke(Base):
    __tablename__ = 'ulkeler'
    id = Column(Integer, primary_key=True)
    ad = Column(String(100))
    kullanici_id = Column(Integer, nullable=False)
    stoklar = relationship("Stok", back_populates="mense_ulke")

class UrunNitelik(Base):
    __tablename__ = 'urun_nitelikleri'
    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String(100), nullable=False)
    nitelik_tipi = Column(String(50), nullable=False) # 'kategori', 'marka', 'urun_grubu'
    kullanici_id = Column(Integer, ForeignKey('kullanicilar.id'), nullable=False)

    # KRİTİK DÜZELTME: back_populates kaldırıldı ve viewonly=True eklendi.
    kullanici = relationship("Kullanici", foreign_keys=[kullanici_id], viewonly=True)

class GelirSiniflandirma(Base):
    __tablename__ = 'gelir_siniflandirmalari'
    id = Column(Integer, primary_key=True)
    ad = Column(String(100))
    kullanici_id = Column(Integer, nullable=False)

class GiderSiniflandirma(Base):
    __tablename__ = 'gider_siniflandirmalari'
    id = Column(Integer, primary_key=True)
    ad = Column(String(100))
    kullanici_id = Column(Integer, nullable=False)

class Nitelik(Base):
    __tablename__ = 'nitelikler'
    id = Column(Integer, primary_key=True, index=True)
    tip = Column(String(50), index=True)
    ad = Column(String, unique=True, index=True, nullable=False)
    aciklama = Column(Text, nullable=True)
    aktif_durum = Column(Boolean, default=True)

class CariHesap(Base):
    __tablename__ = 'cari_hesaplar'
    id = Column(Integer, primary_key=True)
    cari_id = Column(Integer)
    cari_tip = Column(String(20))
    bakiye = Column(Float, default=0.0)

class SenkronizasyonKuyrugu(Base):
    __tablename__ = 'senkronizasyon_kuyrugu'
    id = Column(Integer, primary_key=True)
    kaynak_tablo = Column(String)
    kaynak_id = Column(Integer)
    islem_tipi = Column(String)
    veri = Column(Text)
    islem_tarihi = Column(DateTime, default=func.now())
    senkronize_edildi = Column(Boolean, default=False)

# --- NİTELİK MODELLERİ (PYDANTIC) ---
class NitelikBase(BaseModel):
    ad: str

class UrunKategoriCreate(NitelikBase):
    pass

class UrunKategoriRead(NitelikBase):
    id: int
    kullanici_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
    
class UrunMarkaCreate(NitelikBase):
    pass

class UrunMarkaRead(NitelikBase):
    id: int
    kullanici_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class UrunGrubuCreate(NitelikBase):
    pass

class UrunGrubuRead(NitelikBase):
    id: int
    kullanici_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class UrunBirimiCreate(NitelikBase):
    pass

class UrunBirimiRead(NitelikBase):
    id: int
    kullanici_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
    
class UlkeCreate(NitelikBase):
    pass

class UlkeRead(NitelikBase):
    id: int
    kullanici_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class GelirSiniflandirmaCreate(NitelikBase):
    pass

class GelirSiniflandirmaRead(NitelikBase):
    id: int
    kullanici_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class GiderSiniflandirmaCreate(NitelikBase):
    pass

class GiderSiniflandirmaRead(NitelikBase):
    id: int
    kullanici_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class UrunKategoriUpdate(NitelikBase):
    ad: Optional[str] = None

class UrunMarkaUpdate(NitelikBase):
    ad: Optional[str] = None

class UrunGrubuUpdate(NitelikBase):
    ad: Optional[str] = None

class UrunBirimiUpdate(NitelikBase):
    ad: Optional[str] = None

class UlkeUpdate(NitelikBase):
    ad: Optional[str] = None

class GelirSiniflandirmaUpdate(NitelikBase):
    ad: Optional[str] = None

class GiderSiniflandirmaUpdate(NitelikBase):
    ad: Optional[str] = None

class NitelikListResponse(BaseModel):
    items: List[Union[UrunKategoriRead, UrunMarkaRead, UrunGrubuRead, UrunBirimiRead, UlkeRead, GelirSiniflandirmaRead, GiderSiniflandirmaRead]]
    total: int
# --- NİTELİK MODELLERİ SONU ---

# --- RAPOR MODELLERİ (PYDANTIC) ---
class PanoOzetiYanit(BaseModel):
    toplam_satislar: float
    toplam_alislar: float
    toplam_tahsilatlar: float
    toplam_odemeler: float
    kritik_stok_sayisi: int
    en_cok_satan_urunler: List['EnCokSatanUrun']
    vadesi_yaklasan_alacaklar_toplami: float
    vadesi_gecmis_borclar_toplami: float

class EnCokSatanUrun(BaseModel):
    urun_adi: str
    toplam_miktar: float

class KarZararResponse(BaseModel):
    toplam_satis_geliri: float
    toplam_satis_maliyeti: float
    toplam_alis_gideri: float
    diger_gelirler: float
    diger_giderler: float
    brut_kar: float
    net_kar: float

class NakitAkisiResponse(BaseModel):
    nakit_girisleri: float
    nakit_cikislar: float
    net_nakit_akisi: float

class CariYaslandirmaEntry(BaseModel):
    cari_id: int
    cari_ad: str
    bakiye: float
    vade_tarihi: Optional[date] = None

class CariYaslandirmaResponse(BaseModel):
    musteri_alacaklar: List[CariYaslandirmaEntry]
    tedarikci_borclar: List[CariYaslandirmaEntry]

class StokDegerResponse(BaseModel):
    toplam_stok_maliyeti: float

class GelirGiderAylikOzetEntry(BaseModel):
    ay: int
    ay_adi: str
    toplam_gelir: float
    toplam_gider: float

class GelirGiderAylikOzetResponse(BaseModel):
    aylik_ozet: List[GelirGiderAylikOzetEntry]

class DefaultIdResponse(BaseModel):
    id: int

class NetBakiyeResponse(BaseModel):
    net_bakiye: float

class TopluIslemSonucResponse(BaseModel):
    yeni_eklenen_sayisi: int
    guncellenen_sayisi: int
    hata_sayisi: int
    hatalar: List[str]
    toplam_islenen: int    

class StokOzetResponse(BaseModel):
    toplam_urun_sayisi: int
    toplam_miktar: float
    toplam_maliyet: float
    toplam_satis_tutari: float    

class NextSiparisKoduResponse(BaseModel):
    next_code: str    

class NextCodeResponse(BaseModel):
    next_code: str
    model_config = ConfigDict(from_attributes=True)    

class OfflineLoginResponse(Token):
    kullanici_id: int
    email: EmailStr
    rol: str
    tenant_db_name: str
    sifre_hash: str
    
# --- RAPOR MODELLERİ SONU ---