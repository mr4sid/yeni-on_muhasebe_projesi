# hizmetler.py Dosyasının TAMAMI
import requests
import openpyxl
import json
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union
from yardimcilar import normalize_turkish_chars
from api import modeller
from api.modeller import Kullanici
from api.modeller import (Base, Stok, Musteri, Tedarikci, Fatura, FaturaKalemi,
                           CariHesap, CariHareket, Siparis, SiparisKalemi, UrunKategori, UrunGrubu,
                           KasaBankaHesap, StokHareket, GelirGider, Nitelik, Ulke, UrunMarka, 
                           SenkronizasyonKuyrugu, GelirSiniflandirma, GiderSiniflandirma, UrunBirimi)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class FaturaService:
    def __init__(self, db_manager, app_ref=None):
        self.db = db_manager
        self.app = app_ref
        
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Eğer db_manager'da (OnMuhasebe) app referansı atanmadıysa, buradaki referansı atıyoruz.
        if self.app is not None:
             self.db.app = self.app
             
        logger.info("FaturaService başlatıldı.")

    def fatura_olustur(self, fatura_no: str, tarih: str, fatura_turu: str, cari_id: int, cari_tip: str, kalemler: List[dict], odeme_turu: str, olusturan_kullanici_id: int, kasa_banka_id: Optional[int] = None, misafir_adi: Optional[str] = None, fatura_notlari: Optional[str] = None, vade_tarihi: Optional[str] = None, genel_iskonto_tipi: Optional[str] = "YOK", genel_iskonto_degeri: Optional[float] = 0.0, original_fatura_id: Optional[int] = None):
        """
        Yeni bir fatura oluşturur ve API'ye göndermeden önce Enum değerlerini dönüştürür.
        """
        # 1. Kalem hesaplamaları (Mevcut kodunuzdaki gibi)
        toplam_kdv_haric = 0.0
        toplam_kdv_dahil = 0.0
        
        for kalem in kalemler:
            miktar = self.db.safe_float(kalem.get('miktar'))
            birim_fiyat_kdv_haric_orig = self.db.safe_float(kalem.get('birim_fiyat'))
            kdv_orani = self.db.safe_float(kalem.get('kdv_orani'))
            iskonto_yuzde_1 = self.db.safe_float(kalem.get('iskonto_yuzde_1'))
            iskonto_yuzde_2 = self.db.safe_float(kalem.get('iskonto_yuzde_2'))

            bf_kdv_dahil_orig = birim_fiyat_kdv_haric_orig * (1 + kdv_orani / 100)
            bf_iskonto_1 = bf_kdv_dahil_orig * (1 - iskonto_yuzde_1 / 100)
            bf_iskontolu_dahil = bf_iskonto_1 * (1 - iskonto_yuzde_2 / 100)

            bf_iskontolu_haric = bf_iskontolu_dahil / (1 + kdv_orani / 100) if kdv_orani != 0 else bf_iskontolu_dahil

            kalem_toplam_haric = bf_iskontolu_haric * miktar
            kalem_toplam_dahil = bf_iskontolu_dahil * miktar
            
            kalem['kalem_toplam_kdv_haric'] = kalem_toplam_haric
            kalem['kalem_toplam_kdv_dahil'] = kalem_toplam_dahil
            kalem['kdv_tutari'] = kalem_toplam_dahil - kalem_toplam_haric
            
            toplam_kdv_haric += kalem_toplam_haric
            toplam_kdv_dahil += kalem_toplam_dahil

        # 2. Genel İskontoyu Uygula (Mevcut kodunuzdaki gibi)
        uygulanan_genel_iskonto = 0.0
        if genel_iskonto_tipi == 'YUZDE' and genel_iskonto_degeri > 0:
            uygulanan_genel_iskonto = toplam_kdv_dahil * (genel_iskonto_degeri / 100)
        elif genel_iskonto_tipi == 'TUTAR':
            uygulanan_genel_iskonto = genel_iskonto_degeri
            
        genel_toplam = toplam_kdv_dahil - uygulanan_genel_iskonto

        # API'nin beklediği İngilizce karakterli Enum değerlerine dönüştür
        fatura_turu_api = fatura_turu.replace('Ş', 'S').replace('İ', 'I')
        odeme_turu_api = odeme_turu.replace('İ', 'I').replace('Ç', 'C')

        # 3. API'ye gönderilecek ana veri paketini oluştur
        fatura_data = {
            "fatura_no": fatura_no,
            "fatura_turu": fatura_turu_api, # <-- DÖNÜŞTÜRÜLMÜŞ DEĞER
            "tarih": tarih,
            "cari_id": cari_id,
            "cari_tip": cari_tip,
            "odeme_turu": odeme_turu_api, # <-- DÖNÜŞTÜRÜLMÜŞ DEĞER
            "kasa_banka_id": kasa_banka_id,
            "fatura_notlari": fatura_notlari,
            "vade_tarihi": vade_tarihi,
            "genel_iskonto_tipi": genel_iskonto_tipi,
            "genel_iskonto_degeri": genel_iskonto_degeri,
            "misafir_adi": misafir_adi,
            "original_fatura_id": original_fatura_id,
            "kalemler": kalemler,
            "genel_toplam": genel_toplam,
            "toplam_kdv_haric": toplam_kdv_haric,
            "toplam_kdv_dahil": toplam_kdv_dahil,
            "olusturan_kullanici_id": olusturan_kullanici_id 
        }
        
        if original_fatura_id is None:
            if "original_fatura_id" in fatura_data:
                del fatura_data["original_fatura_id"]

        # 4. API'ye gönder
        try:
            response = self.db.fatura_ekle(fatura_data)
            if response and response.get("id"):
                return True, f"Fatura {fatura_no} başarıyla oluşturuldu. ID: {response['id']}"
            else:
                error_detail = response.get('detail', "Bilinmeyen bir API hatası oluştu.") if isinstance(response, dict) else str(response)
                return False, f"Fatura oluşturulamadı: {error_detail}"

        except Exception as e:
            self.logger.error(f"Fatura API'ye gönderilirken hata: {e}")
            return False, f"API Hatası: {e}"

    def fatura_guncelle(self, fatura_id, fatura_no, tarih, cari_id, odeme_turu, kalemler_data,
                          kasa_banka_id=None, misafir_adi=None, fatura_notlari=None, vade_tarihi=None,
                          genel_iskonto_tipi=None, genel_iskonto_degeri=None):
        fatura_data = {
            "fatura_no": fatura_no,
            "tarih": tarih,
            "cari_id": cari_id,
            "odeme_turu": odeme_turu,
            "kasa_banka_id": kasa_banka_id,
            "misafir_adi": misafir_adi,
            "fatura_notlari": fatura_notlari,
            "vade_tarihi": vade_tarihi,
            "genel_iskonto_tipi": genel_iskonto_tipi,
            "genel_iskonto_degeri": genel_iskonto_degeri,
            "kalemler": kalemler_data,
            "olusturan_kullanici_id": self.db.app.current_user_id # Geriye dönük uyumluluk ve API loglaması için eklenmiştir.
        }
        try:
            response_data = self.db.fatura_guncelle(fatura_id, fatura_data)
            return True, response_data.get("message", "Fatura başarıyla güncellendi.")
        except ValueError as e:
            logger.error(f"Fatura güncellenirken API hatası: {e}")
            return False, f"Fatura güncellenemedi: {e}"
        except Exception as e:
            logger.error(f"Fatura güncellenirken beklenmeyen bir hata oluştu: {e}")
            return False, f"Fatura güncellenirken beklenmeyen bir hata oluştu: {e}"

    def siparis_faturaya_donustur(self, siparis_id: int, fatura_donusum_data: dict, kullanici_id: int):
        fatura_donusum_data['kullanici_id'] = kullanici_id # DÜZELTME: kullanici_id eklendi
        try:
            response = requests.post(f"{self.db.api_base_url}/siparisler/{siparis_id}/faturaya_donustur", json=fatura_donusum_data)
            response.raise_for_status()
            
            response_data = response.json()
            return True, response_data.get("message", "Sipariş başarıyla faturaya dönüştürüldü.")
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', error_detail)
                except ValueError:
                    pass
            logger.error(f"Siparişi faturaya dönüştürürken API hatası: {error_detail}")
            return False, f"Sipariş faturaya dönüştürülemedi: {error_detail}"
        except Exception as e:
            logger.error(f"Siparişi faturaya dönüştürürken beklenmeyen bir hata oluştu: {e}")
            return False, f"Siparişi faturaya dönüştürülürken beklenmeyen bir hata oluştu: {e}"

class CariService:
    def __init__(self, db_manager):
        self.db = db_manager

    def cari_ekle(self, data: dict):
        """Müşteri ekleme işlemini db_manager'a yönlendirir (YeniMusteriEklePenceresi için)."""
        return self.db.musteri_ekle(data)

    # KRİTİK DÜZELTME 2: Müşteri güncelleme için cari_guncelle metodu eklendi
    def cari_guncelle(self, cari_id: int, data: dict):
        """Müşteri güncelleme işlemini db_manager'a yönlendirir (YeniMusteriEklePenceresi için)."""
        return self.db.musteri_guncelle(cari_id, data)

    def musteri_listesi_al(self, **kwargs):
        if 'kullanici_id' in kwargs:
            del kwargs['kullanici_id']
            
        cleaned_params = {k: v for k, v in kwargs.items() if v is not None}
        try:
            return self.db.musteri_listesi_al(**cleaned_params)
        except Exception as e:
            logger.error(f"Müşteri listesi CariService üzerinden alınırken hata: {e}", exc_info=True)
            return {"items": [], "total": 0}

    def musteri_getir_by_id(self, musteri_id: int):
        try:
            return self.db.musteri_getir_by_id(musteri_id)
        except Exception as e:
            logger.error(f"Müşteri ID {musteri_id} CariService üzerinden çekilirken hata: {e}")
            raise

    def musteri_sil(self, musteri_id: int):
        try:
            return self.db.musteri_sil(musteri_id)
        except Exception as e:
            logger.error(f"Müşteri ID {musteri_id} CariService üzerinden silinirken hata: {e}")
            raise

    def tedarikci_listesi_al(self, **kwargs):
        if 'kullanici_id' in kwargs:
            del kwargs['kullanici_id']
            
        cleaned_params = {k: v for k, v in kwargs.items() if v is not None}
        try:
            return self.db.tedarikci_listesi_al(**cleaned_params)
        except Exception as e:
            logger.error(f"Tedarikçi listesi CariService üzerinden alınırken hata: {e}", exc_info=True)
            return {"items": [], "total": 0}

    def tedarikci_getir_by_id(self, tedarikci_id: int):
        try:
            return self.db.tedarikci_getir_by_id(tedarikci_id)
        except Exception as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} CariService üzerinden çekilirken hata: {e}")
            raise

    def tedarikci_sil(self, tedarikci_id: int):
        try:
            return self.db.tedarikci_sil(tedarikci_id)
        except Exception as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} CariService üzerinden silinirken hata: {e}")
            raise

    def cari_getir_by_id(self, cari_id: int, cari_tipi: str):
        if cari_tipi == self.db.CARI_TIP_MUSTERI:
            return self.db.musteri_getir_by_id(cari_id)
        elif cari_tipi == self.db.CARI_TIP_TEDARIKCI:
            return self.db.tedarikci_getir_by_id(cari_id)
        else:
            raise ValueError("Geçersiz cari tipi belirtildi. 'MUSTERI' veya 'TEDARIKCI' olmalı.")

class TopluIslemService:
    def __init__(self, db_manager):
        self.db = db_manager
        self._nitelik_cache = {}

    def _load_nitelik_cache(self, nitelik_tipi: str):
        if nitelik_tipi not in self._nitelik_cache:
            self._nitelik_cache[nitelik_tipi] = {}
            if nitelik_tipi == "kategoriler":
                items = self.db.kategori_listele(kullanici_id=self.db.app.current_user_id)
                for item in items:
                    self._nitelik_cache[nitelik_tipi][item.get("ad").lower()] = item.get("id")
            elif nitelik_tipi == "markalar":
                response = self.db.marka_listele(kullanici_id=self.db.app.current_user_id)
                items = response.get("items", [])
                for item in items:
                    self._nitelik_cache[nitelik_tipi][item.get("ad").lower()] = item.get("id")
            elif nitelik_tipi == "urun_gruplari":
                response = self.db.urun_grubu_listele(kullanici_id=self.db.app.current_user_id)
                items = response.get("items", [])
                for item in items:
                    self._nitelik_cache[nitelik_tipi][item.get("ad").lower()] = item.get("id")
            elif nitelik_tipi == "urun_birimleri":
                response = self.db.urun_birimi_listele(kullanici_id=self.db.app.current_user_id)
                items = response.get("items", [])
                for item in items:
                    self._nitelik_cache[nitelik_tipi][item.get("ad").lower()] = item.get("id")
            elif nitelik_tipi == "ulkeler":
                response = self.db.ulke_listele(kullanici_id=self.db.app.current_user_id)
                items = response.get("items", [])
                for item in items:
                    self._nitelik_cache[nitelik_tipi][item.get("ad").lower()] = item.get("id")

    def _get_nitelik_id_from_cache(self, nitelik_ad: str, nitelik_tipi: str):
        if not nitelik_ad:
            return None
        self._load_nitelik_cache(nitelik_tipi)
        return self._nitelik_cache[nitelik_tipi].get(nitelik_ad.lower())

    def toplu_musteri_analiz_et(self, excel_veri: List[List[Any]]):
        pass # Bu metot yer tutucudur.

    def toplu_tedarikci_analiz_et(self, excel_veri: List[List[Any]]):
        pass # Bu metot yer tutucudur.

    def toplu_stok_analiz_et(self, excel_veri: List[List[Any]], guncellenecek_alanlar: List[str]):
        pass # Bu metot yer tutucudur.

    def toplu_musteri_ice_aktar(self, dosya_yolu: str):
        pass # Bu metot yer tutucudur.

    def toplu_tedarikci_ice_aktar(self, dosya_yolu: str):
        pass # Bu metot yer tutucudur.

    def toplu_stok_ice_aktar(self, dosya_yolu: str):
        pass # Bu metot yer tutucudur.

    def musteri_listesini_disa_aktar(self):
        pass # Bu metot yer tutucudur.

    def tedarikci_listesini_disa_aktar(self):
        pass # Bu metot yer tutucudur.

    def stok_listesini_disa_aktar(self):
        pass # Bu metot yer tutucudur.

    def stok_excel_aktar(self, dosya_yolu: str, kullanici_id: int):
        if not self.db.is_online:
            return False, "Çevrimdışı modda toplu veri aktarımı yapılamaz."
        
        try:
            workbook = openpyxl.load_workbook(dosya_yolu)
            sheet = workbook.active
            header = [cell.value.lower().replace(" ", "_").replace("ç", "c").replace("ş", "s").replace("ü", "u").replace("ğ", "g").replace("ö", "o").replace("ı", "i") for cell in sheet[1]]
            stok_listesi = []

            for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True)):
                row_dict = dict(zip(header, row))
                if row_dict.get('kod') and row_dict.get('ad'):
                    stok_listesi.append({
                        "kod": row_dict.get('kod'),
                        "ad": row_dict.get('ad'),
                        "alis_fiyati": self.db.safe_float(row_dict.get('alis_fiyati')),
                        "satis_fiyati": self.db.safe_float(row_dict.get('satis_fiyati')),
                        "kdv_orani": self.db.safe_float(row_dict.get('kdv_orani')),
                        "miktar": self.db.safe_float(row_dict.get('miktar')),
                        "aktif": self.db.safe_float(row_dict.get('aktif')) == 1,
                        "min_stok_seviyesi": self.db.safe_float(row_dict.get('min_stok_seviyesi')),
                        "kategori_ad": row_dict.get('kategori_ad'),
                        "marka_ad": row_dict.get('marka_ad'),
                        "urun_grubu_ad": row_dict.get('urun_grubu_ad')
                    })

            if not stok_listesi:
                return False, "Excel dosyasında geçerli stok verisi bulunamadı."
            
            sonuc = self.db.bulk_stok_upsert(stok_listesi, kullanici_id)
            
            mesaj = (f"Stok içe aktarma tamamlandı.\n"
                     f"Yeni eklenen: {sonuc.get('yeni_eklenen_sayisi', 0)}\n"
                     f"Güncellenen: {sonuc.get('guncellenen_sayisi', 0)}\n"
                     f"Hata sayısı: {sonuc.get('hata_sayisi', 0)}")
                     
            if sonuc.get('hatalar'):
                mesaj += "\n\nDetaylı hatalar için logları kontrol edin."
                for hata in sonuc['hatalar']:
                    self.app.set_status_message(f"Hata: {hata}", "red")

            return True, mesaj
            
        except FileNotFoundError:
            return False, "Dosya bulunamadı."
        except Exception as e:
            logger.error(f"Excel'den stok içe aktarma hatası: {e}", exc_info=True)
            return False, f"Beklenmeyen bir hata oluştu: {e}"

class LokalVeritabaniServisi:
    def __init__(self, db_path="onmuhasebe.db"):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.initialized = False
        self.logger = logging.getLogger(__name__)

    def initialize_database(self):
        if not self.initialized:
            Base.metadata.create_all(bind=self.engine)
            self.initialized = True
            self.logger.info("Yerel veritabanı şeması başarıyla oluşturuldu/güncellendi.")

    def get_db(self):
        db = self.SessionLocal()
        try:
            return db
        finally:
            db.close()

    def senkronize_veriler(self, sunucu_adresi: str, access_token: Optional[str] = None, current_user_id: Optional[int] = None):
        """
        Yerel verileri sunucudan senkronize eder.
        KRİTİK DÜZELTME: current_user_id parametresi eklendi ve veriye atandı.
        """
        if not sunucu_adresi:
            return False, "Sunucu adresi belirtilmedi. Senkronizasyon atlandı."
        if not access_token:
            print("JWT Token mevcut değil. Senkronizasyon atlandı.")
            return False, "JWT Token mevcut değil. Lütfen önce giriş yapın."
        if current_user_id is None: # Kullanıcı ID'si yoksa senkronizasyon başarısız olur.
             return False, "Kullanıcı ID'si mevcut değil. Senkronizasyon atlandı."

        lokal_db = None
        api_headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            lokal_db = self.get_db()

            def _convert_dates(data, date_keys, datetime_keys):
                for key, value in data.items():
                    if isinstance(value, str):
                        if key in date_keys:
                            try:
                                data[key] = datetime.strptime(value, '%Y-%m-%d').date()
                            except (ValueError, TypeError):
                                pass
                        elif key in datetime_keys:
                            try:
                                data[key] = datetime.fromisoformat(value)
                            except (ValueError, TypeError):
                                pass
                return data

            endpoints = {
                'stoklar': Stok,
                'musteriler': Musteri,
                'tedarikciler': Tedarikci,
                'faturalar': Fatura,
                'siparisler': Siparis,
                'cari_hareketler': CariHareket,
                'nitelikler/kategoriler': UrunKategori,
                'nitelikler/markalar': UrunMarka,
                'nitelikler/urun_gruplari': UrunGrubu,
                'nitelikler/urun_birimleri': UrunBirimi,
                'nitelikler/ulkeler': Ulke,
                'nitelikler/gelir_siniflandirmalari': GelirSiniflandirma,
                'nitelikler/gider_siniflandirmalari': GiderSiniflandirma
            }

            date_fields = {
                'faturalar': ['tarih', 'vade_tarihi'],
                'siparisler': ['tarih', 'teslimat_tarihi'],
                'cari_hareketler': ['tarih', 'vade_tarihi']
            }
            datetime_fields = {
                'stoklar': ['olusturma_tarihi'],
                'musteriler': ['olusturma_tarihi'],
                'tedarikciler': ['olusturma_tarihi'],
                'kasalar_bankalar': ['olusturma_tarihi'],
                'faturalar': ['olusturma_tarihi_saat', 'son_guncelleme_tarihi_saat'],
                'siparisler': ['olusturma_tarihi_saat', 'son_guncelleme_tarihi_saat'],
                'cari_hareketler': ['olusturma_tarihi_saat'],
                'gelir_gider': ['olusturma_tarihi_saat']
            }

            for endpoint, model in endpoints.items():
                # Fatura/Sipariş Kalemleri gibi alt öğeler listenmez.
                if endpoint.endswith('kalemleri'):
                    continue 

                response = requests.get(f"{sunucu_adresi}/{endpoint}", params={"limit": 999999}, headers=api_headers)
                response.raise_for_status()
                response_data = response.json()
                if isinstance(response_data, dict) and "items" in response_data:
                    server_data = response_data["items"]
                elif isinstance(response_data, list):
                    server_data = response_data
                else:
                    raise ValueError(f"API'den beklenmeyen veri formatı: {response_data}")

                for item_data in server_data:
                    item_data = _convert_dates(item_data, date_fields.get(endpoint.split('/')[-1], []), datetime_fields.get(endpoint.split('/')[-1], []))
                    
                    if "kullanici_id" in model.__table__.columns.keys():
                        item_data['kullanici_id'] = current_user_id

                    existing_item = lokal_db.query(model).filter_by(id=item_data["id"]).first()

                    valid_data = {k: v for k, v in item_data.items() if k in model.__table__.columns.keys()}

                    if existing_item:
                        for key, value in valid_data.items():
                            setattr(existing_item, key, value)
                    else:
                        yeni_item = model(**valid_data)
                        lokal_db.add(yeni_item)

            lokal_db.commit()
            print("Veriler başarıyla lokal veritabanına senkronize edildi.")
            return True, "Senkronizasyon başarılı."
        except requests.exceptions.RequestException as e:
            if lokal_db: lokal_db.rollback()
            print(f"Sunucuya bağlanırken hata oluştu: {e}")
            return False, f"Sunucu bağlantı hatası: {e}"
        except Exception as e:
            if lokal_db: lokal_db.rollback()
            print(f"Senkronizasyon hatası: {e}")
            return False, f"Beklenmedik bir hata oluştu: {e}"
        finally:
            if lokal_db: lokal_db.close()

    def listele(self, model_adi: str, filtre: Optional[Dict[str, Any]] = None):
        """
        Yerel veritabanındaki belirtilen modelden verileri listeler.
        """
        db = self.SessionLocal()

        models = {
            "Stok": Stok,
            "Musteri": Musteri,
            "Tedarikci": Tedarikci,
            "Fatura": Fatura,
            "FaturaKalemi": FaturaKalemi,
            "CariHesap": CariHesap,
            "CariHareket": CariHareket,
            "Siparis": Siparis,
            "SiparisKalemi": SiparisKalemi,
            "KasaBankaHesap": KasaBankaHesap,
            "StokHareket": StokHareket,
            "GelirGider": GelirGider,
            "Nitelik": Nitelik,
            "SenkronizasyonKuyrugu": SenkronizasyonKuyrugu
        }

        try:
            model = models.get(model_adi)
            if not model:
                raise ValueError(f"Model bulunamadı: {model_adi}")

            sorgu = db.query(model)
            if filtre:
                for key, value in filtre.items():
                    if hasattr(model, key):
                        sorgu = sorgu.filter(getattr(model, key) == value)

            return [item for item in sorgu.all()]
        except Exception as e:
            self.logger.error(f"Yerel DB listeleme hatası: {e}", exc_info=True)
            return []
        finally:
            if db:
                db.close()

    def kullanici_kaydet_veya_guncelle(self, user_data: dict):
        """
        API'den veya yerel doğrulamadan gelen kullanıcı verisini yerel DB'ye kaydeder/günceller.
        """
        db = self.SessionLocal()
        try:
            # API'den gelen tarih verisini Python datetime objesine dönüştür
            if user_data.get('olusturma_tarihi'):
                user_data['olusturma_tarihi'] = datetime.fromisoformat(user_data['olusturma_tarihi'])

            existing_user = db.query(Kullanici).filter_by(id=user_data.get('id')).first()
            
            valid_user_data = {
                key: value for key, value in user_data.items()
                if key in [column.name for column in Kullanici.__table__.columns]
            }

            if existing_user:
                for key, value in valid_user_data.items():
                    setattr(existing_user, key, value)
                existing_user.son_giris_tarihi = datetime.now()
                self.logger.info(f"Kullanıcı verisi güncellendi: {existing_user.kullanici_adi}")
            else:
                new_user = Kullanici(**valid_user_data)
                new_user.son_giris_tarihi = datetime.now()
                db.add(new_user)
                self.logger.info(f"Yeni kullanıcı yerel veritabanına kaydedildi: {new_user.kullanici_adi}")
            
            db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Kullanıcı yerel veritabanına kaydedilirken hata oluştu: {e}", exc_info=True)
            db.rollback()
            return False
        finally:
            db.close()

    def kullanici_getir(self, kullanici_adi: str) -> Optional[dict]:
        """
        Yerel veritabanından kullanıcı adı ile kullanıcıyı getirir.
        """
        try:
            with self.SessionLocal() as session:
                kullanici_orm = session.query(Kullanici).filter(Kullanici.kullanici_adi == kullanici_adi).first()
                if kullanici_orm:
                    return {
                        "id": kullanici_orm.id,
                        "kullanici_adi": kullanici_orm.kullanici_adi,
                        "hashed_sifre": kullanici_orm.hashed_sifre,
                        "aktif": kullanici_orm.aktif,
                        "yetki": kullanici_orm.yetki,
                        "rol": kullanici_orm.yetki,
                        "token": kullanici_orm.token,
                        "token_tipi": kullanici_orm.token_tipi
                    }
                return None
        except Exception as e:
            self.logger.error(f"Yerel veritabanından kullanıcı çekilirken hata oluştu: {e}", exc_info=True)
            return None

    def ayarlari_kaydet(self, ayarlar: Dict[str, Any]):
        """
        Uygulama ayarlarını yerel veritabanına kaydeder.
        """
        from api.modeller import Ayarlar # Veya Nitelik modelini kullanıyorsanız onu import edin
        
        with self.get_db() as db:
            for key, value in ayarlar.items():
                # Ayar kaydının adı 'SISTEM_AYARLARI_{anahtar}' şeklinde olsun
                ayar_adi = f"SISTEM_AYARLARI_{key.upper()}" 
                
                # Mevcut kaydı bul
                mevcut_ayar = db.query(Ayarlar).filter(Ayarlar.ad == ayar_adi).first()

                if mevcut_ayar:
                    mevcut_ayar.deger = str(value)
                else:
                    yeni_ayar = Ayarlar(ad=ayar_adi, deger=str(value), kullanici_id=None) # Kullanici ID burada None olabilir veya ana kullanıcı ID'si verilir.
                    db.add(yeni_ayar)
            db.commit()

    def ayarlari_yukle(self) -> Dict[str, Any]:
        """
        Uygulama ayarlarını yerel veritabanından yükler.
        """
        from api.modeller import Ayarlar # Veya Nitelik modelini kullanıyorsanız onu import edin
        
        ayarlar = {}
        with self.get_db() as db:
            # Sadece sistem ayarlarını çek
            kayitlar = db.query(Ayarlar).all()
            
            for kayit in kayitlar:
                if kayit.ad.startswith("SISTEM_AYARLARI_"):
                    # 'SISTEM_AYARLARI_' ön ekini kaldırarak anahtarı belirle
                    key = kayit.ad.replace("SISTEM_AYARLARI_", "").lower()
                    ayarlar[key] = kayit.deger # Değeri string olarak sakla
        return ayarlar

    def _get_model_by_name(self, model_adi: str) -> Any:
        """String adına göre ORM modelini (hizmetler.py'nin kapsamından) döndürür."""
        
        # KRİTİK DÜZELTME 1: ORM_MODEL_MAPPING import hatasını çözmek için güvenli model erişimi.
        import api.modeller as modeller_module 
        
        Model = getattr(modeller_module, model_adi, None)
        if not Model:
            logger.error(f"Lokal DB Hatası: '{model_adi}' model adı api.modeller içinde bulunamadı.")
            return None
        return Model
    
    def ekle(self, model_adi: str, veri: dict) -> Any:
        """[LOCAL WRITE] Yeni bir kaydı yerel veritabanına ekler ve ID'li objeyi döndürür."""
        
        # Kullanılacak modeli al
        Model = self._get_model_by_name(model_adi)
        if not Model:
            raise ValueError(f"Bilinmeyen model adı: {model_adi}")

        with self.get_db() as db:
            # Pydantic'ten gelen 'veri' sözlüğünü kullanarak bir ORM nesnesi oluştur
            db_obj = Model(**veri)
            
            # SQLAlchemy, yerel DB'de otomatik olarak ID atar (pozitif veya negatif).
            db.add(db_obj)
            db.flush() # ID'yi elde etmek için KRİTİK
            db.commit()
            db.refresh(db_obj)
            logger.info(f"Yerel DB: Yeni {model_adi} kaydı başarıyla eklendi. ID: {db_obj.id}")
            return db_obj    

    def senkronizasyon_kuyruguna_ekle(self, kaynak_tablo: str, kaynak_id: int, islem_tipi: str, endpoint: str, veri: dict):
        """[ASENKRON PUSH] Senkronizasyon kuyruğuna yeni bir görev ekler."""
        from api.modeller import SenkronizasyonKuyrugu
        
        # KRİTİK DÜZELTME 2: Endpoint bilgisini 'veri' JSON bloğunun içine dahil et.
        # SenkronizasyonKuyrugu modelinde 'endpoint' kolonu OLMADIĞI için bu zorunludur.
        veri_payload = {
            "endpoint": endpoint, # Endpoint'i JSON verisinin içine gömdük
            "data": veri
        }
        
        with self.get_db() as db:
            kuyruk_kaydi = SenkronizasyonKuyrugu(
                kaynak_tablo=kaynak_tablo,
                kaynak_id=kaynak_id,
                islem_tipi=islem_tipi, # POST, PUT, DELETE
                veri=json.dumps(veri_payload) # Endpoint ve data JSON olarak kaydedilir
            )
            db.add(kuyruk_kaydi)
            db.commit()
            logger.info(f"Senkronizasyon Kuyruğu: {kaynak_tablo} ID {kaynak_id} için {islem_tipi} görevi eklendi.")

    def kuyruk_kaydini_sil(self, kuyruk_id: int):
        """Senkronizasyon kuyruğundan başarılı bir görevi siler."""
        from api.modeller import SenkronizasyonKuyrugu
        with self.get_db() as db:
            kayit = db.query(SenkronizasyonKuyrugu).filter(SenkronizasyonKuyrugu.id == kuyruk_id).first()
            if kayit:
                db.delete(kayit)
                db.commit()
                logger.info(f"Senkronizasyon Kuyruğu: ID {kuyruk_id} başarıyla silindi (PUSH başarılı).")
                return True
            return False

lokal_db_servisi = LokalVeritabaniServisi()