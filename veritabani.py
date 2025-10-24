# (ana dizindeki) veritabani.py dosyasının TAM İÇERİĞİ
from hizmetler import lokal_db_servisi 
import requests
import json
import logging
from passlib.context import CryptContext
import os
import time
import locale
from config import API_BASE_URL
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, DateTime, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, case
from requests.exceptions import ConnectionError, Timeout, RequestException 
# KRİTİK DÜZELTME: Kullanici modeli ve offline doğrulama için verify_password eklendi.
from api.modeller import Base, Nitelik, Kullanici, Ayarlar, Fatura, Stok, StokHareket, GelirGider, Musteri, Tedarikci

from api.guvenlik import verify_password 
# Logger kurulumu
logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class OnMuhasebe:
    # Sabitler (UI ve diğer modüllerle uyumlu olması için burada tutuluyor)
    FATURA_TIP_SATIS = "SATIŞ"
    FATURA_TIP_ALIS = "ALIŞ"
    FATURA_TIP_SATIS_IADE = "SATIŞ İADE"
    FATURA_TIP_ALIS_IADE = "ALIŞ İADE"
    FATURA_TIP_DEVIR_GIRIS = "DEVİR GİRİŞ"

    ODEME_TURU_NAKIT = "NAKİT"
    ODEME_TURU_KART = "KART"
    ODEME_TURU_EFT_HAVALE = "EFT/HAVALE"
    ODEME_TURU_CEK = "ÇEK"
    ODEME_TURU_SENET = "SENET"
    ODEME_TURU_ACIK_HESAP = "AÇIK_HESAP"
    ODEME_TURU_ETKISIZ_FATURA = "ETKİSİZ_FATURA"
    
    pesin_odeme_turleri = [ODEME_TURU_NAKIT, ODEME_TURU_KART, ODEME_TURU_EFT_HAVALE, ODEME_TURU_CEK, ODEME_TURU_SENET]

    CARI_TIP_MUSTERI = "MUSTERI"
    CARI_TIP_TEDARIKCI = "TEDARIKCI"

    SIPARIS_TIP_SATIS = "SATIŞ_SIPARIS"
    SIPARIS_TIP_ALIS = "ALIŞ_SIPARIS"
    
    SIPARIS_DURUM_BEKLEMEDE = "BEKLEMEDE"
    SIPARIS_DURUM_TAMAMLANDI = "TAMAMLANDI"
    SIPARIS_DURUM_KISMİ_TESLIMAT = "KISMİ_TESLİMAT"
    SIPARIS_DURUM_IPTAL_EDILDI = "İPTAL_EDİLDİ"

    # API ile uyumlu olacak şekilde düzeltildi (Türkçe karakterler kaldırıldı)
    STOK_ISLEM_TIP_GIRIS_MANUEL_DUZELTME = "GIRIS_MANUEL_DUZELTME"
    STOK_ISLEM_TIP_CIKIS_MANUEL_DUZELTME = "CIKIS_MANUEL_DUZELTME"
    STOK_ISLEM_TIP_GIRIS_MANUEL = "GIRIS_MANUEL"
    STOK_ISLEM_TIP_CIKIS_MANUEL = "CIKIS_MANUEL"
    STOK_ISLEM_TIP_SAYIM_FAZLASI = "SAYIM_FAZLASI"
    STOK_ISLEM_TIP_SAYIM_EKSIGI = "SAYIM_EKSIGI"
    STOK_ISLEM_TIP_ZAYIAT = "ZAYIAT"
    STOK_ISLEM_TIP_IADE_GIRIS = "IADE_GIRIS"
    STOK_ISLEM_TIP_FATURA_ALIS = "FATURA_ALIS"
    STOK_ISLEM_TIP_FATURA_SATIS = "FATURA_SATIS"

    # Kaynak Tipleri (Cari Hareketler ve Stok Hareketleri için)
    KAYNAK_TIP_FATURA = "FATURA"
    KAYNAK_TIP_IADE_FATURA = "IADE_FATURA"
    KAYNAK_TIP_FATURA_SATIS_PESIN = "FATURA_SATIS_PESIN"
    KAYNAK_TIP_FATURA_ALIS_PESIN = "FATURA_ALIS_PESIN"
    KAYNAK_TIP_TAHSILAT = "TAHSILAT"
    KAYNAK_TIP_ODEME = "ODEME"
    KAYNAK_TIP_VERESIYE_BORC_MANUEL = "VERESIYE_BORC_MANUEL"
    KAYNAK_TIP_MANUEL = "MANUEL"

    # Kullanıcı Rolleri
    USER_ROLE_ADMIN = "ADMIN"
    USER_ROLE_MANAGER = "MANAGER"
    USER_ROLE_SALES = "SALES"
    USER_ROLE_USER = "USER"
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")    
    def __init__(self, api_base_url):
        self.api_base_url = api_base_url
        self.access_token = None
        self.current_user_id = None
        self.is_online = False
        self.timeout = 10

        # Lokal veritabanı bağlantısını başlat
        try:
            self.lokal_db = lokal_db_servisi 
            self.lokal_db.initialize_database()
            logger.info("Yerel veritabanı başarıyla başlatıldı.")
        except Exception as e:
            logger.critical(f"Yerel veritabanı başlatılırken kritik bir hata oluştu: {e}", exc_info=True)
            raise

        self.check_online_status()
        self._load_access_token()

    def verify_password(self, plain_password, hashed_password):
        """
        Düz metin şifreyi, hashlenmiş şifreyle karşılaştırır.
        """
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Parola doğrulama hatası: {e}", exc_info=True)
            return False

    def check_online_status(self):
        """
        API bağlantısını kontrol eder ve self.is_online bayrağını ayarlar.
        """
        try:
            response = requests.get(f"{self.api_base_url}/sistem/status", timeout=5)
            response.raise_for_status()
            if response.status_code == 200:
                self.is_online = True
                logger.info("API bağlantısı başarıyla kuruldu.")
            else:
                self.is_online = False
                logger.warning(f"API bağlantısı kurulamadı. Durum kodu: {response.status_code}")
        except (ConnectionError, Timeout, RequestException) as e:
            logger.warning(f"API bağlantısı kurulamadı. Çevrimdışı modda başlatılıyor. Hata: {e}")
            self.is_online = False
        except Exception as e:
            logger.error(f"Beklenmedik bir hata oluştu: {e}", exc_info=True)
            self.is_online = False

    def _make_api_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None, headers: Optional[Dict] = None, files=None):
        """
        API'ye kontrollü bir şekilde istek gönderir.
        GÜVENLİK: URL'ye kullanici_id parametresini EKLEMEZ. Tüm yetkilendirme JWT Token üzerinden yapılır.
        """
        if not self.is_online:
            logger.warning(f"Çevrimdışı mod: API isteği iptal edildi: {method} {endpoint}")
            raise ValueError(f"Çevrimdışı mod: '{endpoint}' API isteği yapılamadı.")

        # Headers'a oturum açma tokenını ekleyin (eğer varsa)
        api_headers = {"Content-Type": "application/json"}
        if self.access_token:
            api_headers["Authorization"] = f"Bearer {self.access_token}"

        if headers:
            api_headers.update(headers)

        if params is None:
            params = {}
        
        # KRİTİK TEMİZLİK: URL manipülasyon mantığı KALDIRILDI. Endpoint olduğu gibi kullanılır.
        url = f"{self.api_base_url}{endpoint}"
        try:
            # POST veya PUT istekleri için 'data' parametresini 'json' olarak gönder.
            if method.upper() == 'POST' or method.upper() == 'PUT':
                response = requests.request(method, url, json=data, params=params, headers=api_headers, files=files, timeout=self.timeout)
            else:
                response = requests.request(method, url, params=params, headers=api_headers, files=files, timeout=self.timeout)

            response.raise_for_status()

            if response.text:
                return response.json()
            else:
                return {}

        except requests.exceptions.HTTPError as http_err:
            error_message = f"HTTP Hatası: {http_err}"
            if http_err.response is not None and http_err.response.text:
                try:
                    error_detail = http_err.response.json().get('detail', http_err.response.text)
                    error_message = f"API Hatası: {error_detail}"
                except json.JSONDecodeError:
                    error_message = f"API Hatası: {http_err.response.text}"
            logger.error(f"API isteği sırasında HTTP hatası oluştu: {url}. Hata: {error_message}")
            raise ValueError(error_message)
        except (ConnectionError, Timeout, RequestException) as e:
            logger.error(f"API isteği sırasında bağlantı hatası oluştu: {url}. Hata: {e}")
            self.is_online = False
            raise ValueError(f"Bağlantı hatası: {e}")
        except Exception as e:
            logger.error(f"API isteği sırasında genel hata oluştu: {url}. Hata: {e}", exc_info=True)
            raise ValueError(f"Genel hata: {e}")
                
    # --- ŞİRKET BİLGİLERİ ---
    def sirket_bilgilerini_yukle(self):
        try:
            # DÜZELTME: _make_api_request'in artık kullanici_id'yi otomatik eklemesi nedeniyle parametre kaldırıldı
            return self._make_api_request("GET", "/sistem/bilgiler")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Şirket bilgileri API'den yüklenemedi: {e}")
            return {}

    def sirket_bilgilerini_kaydet(self, data: dict):
        try:
            self._make_api_request("PUT", "/sistem/bilgiler", data=data)
            return True, "Şirket bilgileri başarıyla kaydedildi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Şirket bilgileri API'ye kaydedilemedi: {e}")
            return False, f"Şirket bilgileri kaydedilirken hata: {e}"

    def sirket_bilgilerini_getir(self):
        """API'den mevcut firmanın bilgilerini çeker."""
        if not self.is_online:
            return False, "Bu işlem için internet bağlantısı gereklidir."
        try:
            endpoint = f"{self.api_base_url}/sistem/sirket_bilgileri"
            response = self.session.get(endpoint, timeout=10)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, response.json().get("detail", "Bilgiler alınamadı.")
        except requests.exceptions.RequestException as e:
            return False, f"API bağlantı hatası: {e}"
        
    def sirket_bilgilerini_guncelle(self, data: dict):
        """API'ye güncel firma bilgilerini gönderir."""
        if not self.is_online:
            return False, "Bu işlem için internet bağlantısı gereklidir."
        try:
            endpoint = f"{self.api_base_url}/sistem/sirket_bilgileri"
            response = self.session.put(endpoint, json=data, timeout=15)
            if response.status_code == 200:
                return True, response.json().get("mesaj", "Başarıyla güncellendi.")
            else:
                return False, response.json().get("detail", "Güncelleme başarısız.")
        except requests.exceptions.RequestException as e:
            return False, f"API bağlantı hatası: {e}"        

    # --- KULLANICI YÖNETİMİ ---
    def kullanici_dogrula(self, email: str, sifre: str) -> Optional[dict]:
        """
        Kullanıcıyı öncelikli olarak API üzerinden, başarısız olursa yerel veritabanı üzerinden doğrular.
        Kilitlenme sorununu çözmek için güncellendi.
        """
        # Kilitlenmeyi önlemek için her giriş denemesinde token'ı sıfırla
        self.access_token = None
        self.token_type = None
        self.lokal_db.ayarlari_kaydet({"access_token": None, "token_type": None})

        # 1. Adım: Çevrimiçi modda API üzerinden doğrulamayı dene.
        if self.is_online:
            logger.info(f"API üzerinden kullanıcı doğrulaması deneniyor: {email}")
            try:
                # KİLİTLENME DÜZELTMESİ:
                # _make_api_request kullanmıyoruz, çünkü o, var olan (belki de geçersiz)
                # token'ı login isteğine ekleyerek 401 hatasına neden oluyor.
                # Login isteği (token alma) için her zaman temiz bir istek göndermeliyiz.
                login_data = {"email": email, "sifre": sifre}
                url = f"{self.api_base_url}/dogrulama/login"

                response = requests.post(
                    url, 
                    json=login_data, # API'niz Pydantic modeli (KullaniciLogin) beklediği için json=
                    timeout=self.timeout
                )

                # API'den gelen hatayı (4xx, 5xx) fırlat
                response.raise_for_status() 

                response_data = response.json()

                if response_data and "access_token" in response_data and "token_type" in response_data:
                    self.access_token = response_data["access_token"]
                    self.token_type = response_data["token_type"]

                    # Token'ı yerel DB'ye kaydet
                    self.lokal_db.ayarlari_kaydet({
                        "access_token": self.access_token,
                        "token_type": self.token_type
                    })

                    logger.info(f"Kullanıcı API üzerinden başarıyla doğrulandı: {email}")

                    # Başarılı giriş sonrası yerel DB'yi de güncelleyelim (offline kullanım için)
                    # (dogrulama.py'den sifre_hash'i de döndürmelisiniz)
                    if "sifre_hash" in response_data:
                        update_local_user_credentials(
                            response_data.get('kullanici_id'),
                            response_data.get('email'),
                            response_data.get('sifre_hash'),
                            response_data.get('rol')
                        )

                    return response_data
                else:
                    logger.warning("Kullanıcı doğrulama API üzerinden başarısız: Yanıt formatı hatalı veya token yok.")
                    raise Exception("API yanıtı hatalı (token yok).")

            except requests.exceptions.HTTPError as http_err:
                # API'den gelen 4xx ve 5xx hatalarını burada yakalıyoruz
                self.is_online = True # Bağlantı var, ama API reddetti
                status_code = http_err.response.status_code
                try:
                    detail = http_err.response.json().get('detail', 'Bilinmeyen API hatası')
                except json.JSONDecodeError:
                    detail = http_err.response.text

                if status_code == 401:
                    logger.warning(f"Giriş hatası (401): {detail}")
                    raise Exception(detail) # Örn: "Hatalı e-posta veya şifre."
                elif status_code == 403:
                    logger.warning(f"Giriş engellendi (403): {detail}")
                    raise Exception(detail) # Örn: "Hesabınız askıya alınmıştır."
                else:
                    logger.error(f"API isteği sırasında HTTP hatası oluştu: {status_code} - {detail}")
                    raise Exception(f"Sunucu Hatası ({status_code}): {detail}")

            except (ConnectionError, Timeout, RequestException) as e:
                logger.error(f"API bağlantı hatası oluştu: {e}. Çevrimdışı moda geçiliyor.")
                self.is_online = False
                # Sadece bağlantı hatası durumunda yerel veritabanına düş
                return authenticate_offline_user(email, sifre)
            except Exception as e:
                # Diğer beklenmedik hatalar (örn: JSON parse hatası)
                logger.error(f"Giriş sırasında beklenmedik bir hata oluştu: {e}", exc_info=True)
                raise Exception(f"Bilinmeyen bir hata oluştu: {e}")

        # 2. Adım: Çevrimdışı modda yerel veritabanı üzerinden doğrula.
        else:
            logger.info("Çevrimdışı mod: Yerel veritabanı üzerinden kullanıcı doğrulaması deneniyor...")
            offline_user = authenticate_offline_user(email, sifre)
            if not offline_user:
                raise Exception("Çevrimdışı giriş başarısız. Kullanıcı adı veya şifre hatalı.")
            return offline_user

    def kullanici_dogrula_yerel(self, kullanici_adi, sifre):
        """
        DEPRECATED: Bu metot artık kullanılmamalıdır.
        """
        logging.warning("kullanici_dogrula_yerel metodu artık DEPRECATED. Lütfen authenticate_offline_user kullanın.")
        return authenticate_offline_user(kullanici_adi, sifre) # Hatalı da olsa, geriye dönük uyumluluk için bırakıldı.
    
    def personel_giris_yap(self, firma_no: str, kullanici_adi: str, sifre: str) -> Optional[dict]:
        """
        Personel girişini API üzerinden doğrular. Çevrimdışı desteklemez.
        """
        # Personel girişi sadece online modda çalışır
        if not self.is_online:
            logger.warning("Personel girişi için çevrimiçi mod gereklidir.")
            raise Exception("Personel girişi yalnızca çevrimiçi modda yapılabilir.")

        # Her giriş denemesinde token'ı sıfırla (kullanici_dogrula'daki gibi)
        self.access_token = None
        self.token_type = None
        self.lokal_db.ayarlari_kaydet({"access_token": None, "token_type": None})

        logger.info(f"API üzerinden personel girişi deneniyor: FirmaNo={firma_no}, KullaniciAdi={kullanici_adi}")
        try:
            # _make_api_request kullanmıyoruz, çünkü bu bir token alma işlemi.
            personel_login_data = {
                "firma_no": firma_no,
                "kullanici_adi": kullanici_adi,
                "sifre": sifre
            }
            url = f"{self.api_base_url}/dogrulama/personel-giris"

            response = requests.post(
                url, 
                json=personel_login_data, # API Pydantic modeli (PersonelGirisSema) bekliyor
                timeout=self.timeout
            )

            response.raise_for_status() # API'den gelen 4xx/5xx hatalarını fırlat

            response_data = response.json()

            if response_data and "access_token" in response_data and "token_type" in response_data:
                self.access_token = response_data["access_token"]
                self.token_type = response_data["token_type"]

                # Token'ı yerel DB'ye kaydet
                self.lokal_db.ayarlari_kaydet({
                    "access_token": self.access_token,
                    "token_type": self.token_type
                })

                logger.info(f"Personel API üzerinden başarıyla doğrulandı: {kullanici_adi}")

                # Personel için yerel DB güncellemesi (update_local_user_credentials)
                # GEREKLİ Mİ? Personel bilgilerinin offline tutulması gerekiyor mu? Şimdilik eklemiyorum.
                # Eğer gerekirse, response_data'dan gerekli bilgileri alıp update_local_user_credentials çağrılabilir.

                return response_data
            else:
                logger.warning("Personel doğrulama API üzerinden başarısız: Yanıt formatı hatalı veya token yok.")
                raise Exception("API yanıtı hatalı (token yok).")

        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code
            try:
                detail = http_err.response.json().get('detail', 'Bilinmeyen API hatası')
            except json.JSONDecodeError:
                detail = http_err.response.text

            if status_code == 401:
                logger.warning(f"Personel giriş hatası (401): {detail}")
                raise Exception(detail) # Örn: "Kullanıcı adı veya şifre yanlış."
            elif status_code == 403:
                logger.warning(f"Personel giriş engellendi (403): {detail}")
                raise Exception(detail) # Örn: "Firmanız askıya alınmıştır."
            elif status_code == 404:
                logger.warning(f"Personel giriş hatası (404): {detail}")
                raise Exception(detail) # Örn: "Bu firma numarasına sahip bir firma bulunamadı."
            else:
                logger.error(f"Personel API isteği sırasında HTTP hatası: {status_code} - {detail}")
                raise Exception(f"Sunucu Hatası ({status_code}): {detail}")

        except (ConnectionError, Timeout, RequestException) as e:
            logger.error(f"Personel API bağlantı hatası: {e}.")
            self.is_online = False # Bağlantı koptu
            raise Exception(f"Sunucuya bağlanılamadı: {e}")
        except Exception as e:
            logger.error(f"Personel girişi sırasında beklenmedik hata: {e}", exc_info=True)
            raise Exception(f"Bilinmeyen bir hata oluştu: {e}")
    
    def _get_current_user(self) -> Optional[dict]:
        """
        API'den mevcut kullanıcının bilgilerini çeker.
        """
        try:
            if not self.access_token:
                logger.warning("Kullanıcı bilgileri çekilemedi: Access token mevcut değil.")
                return None
            
            response_data = self._make_api_request("GET", "/kullanicilar/me")
            
            if response_data:
                logger.info("Mevcut kullanıcı bilgileri başarıyla çekildi.")
                return response_data
            else:
                logger.warning("API'den kullanıcı bilgileri çekilirken beklenmedik bir yanıt alındı.")
                return None
        except Exception as e:
            logger.error(f"Mevcut kullanıcı bilgileri çekilirken hata oluştu: {e}", exc_info=True)
            return None

    def kullanici_listele(self) -> List[dict]:
        """API'den kullanıcı listesini çeker. Yanıtı 'items' listesi olarak döndürür."""
        try:
            # DÜZELTME: kullanici_id parametresi _make_api_request tarafından otomatik olarak eklendiği için çıkarıldı
            response = self._make_api_request("GET", "/kullanicilar/")
            return response.get("items", [])
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı listesi API'den alınamadı: {e}")
            return []
                
    def kullanici_ekle(self, data: dict):
        """API'ye yeni bir kullanıcı ekler."""
        try:
            response = self._make_api_request("POST", "/kullanicilar/ekle", data=data)
            if response:
                return True, "Kullanıcı başarıyla eklendi."
            return False, "Kullanıcı eklenirken bilinmeyen bir hata oluştu."
        except Exception as e:
            logger.error(f"Kullanıcı ekleme hatası: {e}")
            return False, f"Kullanıcı eklenirken bir hata oluştu: {e}"

    def kullanici_guncelle(self, kullanici_id: int, data: dict):
        """API'deki mevcut bir kullanıcıyı günceller."""
        try:
            self._make_api_request("PUT", f"/kullanicilar/{kullanici_id}", data=data)
            return True, "Kullanıcı başarıyla güncellendi."
        except Exception as e:
            logger.error(f"Kullanıcı güncelleme hatası: {e}")
            return False, f"Kullanıcı güncellenirken bir hata oluştu: {e}"

    def kullanici_adi_guncelle(self, user_id, new_username):
        try:
            self._make_api_request("PUT", f"/kullanicilar/{user_id}", data={"kullanici_adi": new_username})
            return True, "Kullanıcı adı başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kullanıcı adı güncellenirken hata: {e}")
            return False, f"Kullanıcı adı güncellenirken hata: {e}"

    def kullanici_sil(self, user_id: int):
        """API'deki bir kullanıcıyı siler."""
        try:
            # DÜZELTME: kullanici_id parametresi _make_api_request tarafından otomatik olarak eklendiği için çıkarıldı
            self._make_api_request("DELETE", f"/kullanicilar/{user_id}")
            return True, "Kullanıcı başarıyla silindi."
        except Exception as e:
            logger.error(f"Kullanıcı silinirken hata: {e}")
            return False, f"Kullanıcı silinirken hata: {e}"

    # --- CARİLER (Müşteri/Tedarikçi) ---
    def musteri_ekle(self, data: dict):
        if self.current_user_id:
            data['kullanici_id'] = self.current_user_id
            
        try:
            # Bir önceki adımda düzeltilen data=data kullanımı
            self._make_api_request("POST", "/musteriler/", data=data) 
            return True, "Müşteri başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri eklenirken hata: {e}")
            return False, f"Müşteri eklenirken hata: {e}"

    def musteri_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, aktif_durum: bool = None):
        if self.is_online:
            try:
                params = {"skip": skip, "limit": limit, "arama": arama, "aktif_durum": aktif_durum}
                response = self._make_api_request("GET", "/musteriler/", params=params)
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"Müşteri listesi API'den çekilirken hata: {e}", exc_info=True)
                self.is_online = False

        # OFFLINE KISMI:
        filtre = {"aktif_durum": aktif_durum} if aktif_durum is not None else {}
        lokal_musteriler_orm = self.lokal_db.listele(model_adi="Musteri", filtre=filtre)
        
        # KRİTİK DÜZELTME: ORM objelerini dictionary'ye çevirerek AttributeError'ı çöz.
        lokal_musteriler = []
        for m in lokal_musteriler_orm:
            # SQLAlchemy ORM objesini sözlüğe çevirme (lokal_db_servisi içinde obj_to_dict metodu varsayılmıyor)
            m_dict = {c.name: getattr(m, c.name) for c in m.__table__.columns}
            lokal_musteriler.append(m_dict)
            
        return {"items": lokal_musteriler, "total": len(lokal_musteriler)}

    def musteri_getir_by_id(self, musteri_id: int):
        # DÜZELTME: kullanici_id parametresi _make_api_request tarafından otomatik olarak eklendiği için çıkarıldı
        try:
            return self._make_api_request("GET", f"/musteriler/{musteri_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} çekilirken hata: {e}")
            return None

    def musteri_guncelle(self, musteri_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/musteriler/{musteri_id}", data=data)
            return True, "Müşteri başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} güncellenirken hata: {e}")
            return False, f"Müşteri güncellenirken hata: {e}"

    def musteri_sil(self, musteri_id: int):
        try:
            self._make_api_request("DELETE", f"/musteriler/{musteri_id}")
            return True, "Müşteri başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} silinirken hata: {e}")
            return False, f"Müşteri silinirken hata: {e}"
            
    def get_perakende_musteri_id(self) -> Optional[int]:
        """API'den varsayılan perakende müşteri ID'sini çeker veya yerel DB'den bulur."""
        if self.is_online:
            try:
                response_data = self._make_api_request("GET", "/sistem/varsayilan_cariler/perakende_musteri_id")
                return response_data.get('id')
            except Exception as e:
                logger.warning(f"Varsayılan perakende müşteri ID'si API'den alınamadı: {e}. Yerel DB deneniyor.")
        
        # OFFLINE FALLBACK: Yerel DB'den doğrudan çekme
        try:
            from api.modeller import Musteri # Yerel DB modeli
            with lokal_db_servisi.get_db() as db:
                # KRİTİK DÜZELTME: Doğrudan ORM sorgusu yapıldı, getir_by_kod çağrısı kaldırıldı.
                lokal_musteri = db.query(Musteri).filter(
                    Musteri.kod == "PERAKENDE_MUSTERI",
                    Musteri.kullanici_id == self.current_user_id
                ).first()
                if lokal_musteri:
                    return lokal_musteri.id
                logger.warning("Yerel DB'de 'PERAKENDE_MUSTERI' bulunamadı.")
                return None
        except Exception as e:
            logger.error(f"Yerel DB'den varsayılan müşteri ID'si çekilirken hata: {e}", exc_info=True)
            return None
                    
    def get_cari_ekstre_ozet(self, cari_id: int, cari_tip: str, baslangic_tarihi: str, bitis_tarihi: str):
        """
        Cari hesap ekstresindeki hareketleri alarak finansal özet verilerini hesaplar.
        """
        try:
            hareketler, devreden_bakiye, success, message = self.cari_hesap_ekstresi_al(
                cari_id, cari_tip, baslangic_tarihi, bitis_tarihi
            )

            if not success:
                raise Exception(f"Ekstre verisi alınamadı: {message}")

            toplam_borc = 0.0
            toplam_alacak = 0.0
            toplam_tahsilat_odeme = 0.0
            vadesi_gelmis = 0.0
            vadesi_gelecek = 0.0

            for h in hareketler:
                tutar = h.get('tutar', 0.0)
                islem_yone = h.get('islem_yone')
                odeme_turu = h.get('odeme_turu')
                vade_tarihi_str = h.get('vade_tarihi')
                
                # Borç ve Alacak Toplamlarını Hesapla
                if islem_yone == 'BORC':
                    toplam_borc += tutar
                elif islem_yone == 'ALACAK':
                    toplam_alacak += tutar

                # Tahsilat/Ödeme Toplamını Hesapla
                if odeme_turu in self.pesin_odeme_turleri:
                    # Bu kontrol, Tahsilat/Ödeme hareketlerinin de tahsilat/ödeme toplamına dahil edilmesini sağlar
                    if h.get('kaynak') in [self.KAYNAK_TIP_TAHSILAT, self.KAYNAK_TIP_ODEME]:
                        toplam_tahsilat_odeme += tutar
                    # Faturalar, sadece peşin ödeme türünde ise tahsilat toplamına eklenir.
                    # Buradaki mantık, fatura tutarının ödeme türüne göre ayrıştırılmasıdır.
                    elif h.get('kaynak') in [self.KAYNAK_TIP_FATURA, self.KAYNAK_TIP_IADE_FATURA]:
                        toplam_tahsilat_odeme += tutar


                # Vade bilgileri için hesaplama
                if odeme_turu == self.ODEME_TURU_ACIK_HESAP and vade_tarihi_str:
                    try:
                        vade_tarihi = datetime.strptime(vade_tarihi_str, '%Y-%m-%d').date()
                        if vade_tarihi < datetime.now().date():
                            vadesi_gelmis += tutar
                        else:
                            vadesi_gelecek += tutar
                    except ValueError:
                        logger.warning(f"Geçersiz vade tarihi formatı: {vade_tarihi_str}")

            # Dönem sonu bakiyesi
            donem_sonu_bakiye = devreden_bakiye + toplam_alacak - toplam_borc

            return {
                "donem_basi_bakiye": devreden_bakiye,
                "toplam_borc_hareketi": toplam_borc,
                "toplam_alacak_hareketi": toplam_alacak,
                "toplam_tahsilat_odeme": toplam_tahsilat_odeme,
                "vadesi_gelmis": vadesi_gelmis,
                "vadesi_gelecek": vadesi_gelecek,
                "donem_sonu_bakiye": donem_sonu_bakiye
            }
        except Exception as e:
            logger.error(f"Cari ekstre özeti hesaplanırken hata oluştu: {e}", exc_info=True)
            return {
                "donem_basi_bakiye": 0.0,
                "toplam_borc_hareketi": 0.0,
                "toplam_alacak_hareketi": 0.0,
                "toplam_tahsilat_odeme": 0.0,
                "vadesi_gelmis": 0.0,
                "vadesi_gelecek": 0.0,
                "donem_sonu_bakiye": 0.0
            }

    def get_musteri_net_bakiye(self, musteri_id: int):
        try:
            response = self._make_api_request("GET", f"/musteriler/{musteri_id}/net_bakiye")
            return response.get("net_bakiye")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Müşteri ID {musteri_id} net bakiye çekilirken hata: {e}")
            return None

    def tedarikci_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/tedarikciler/", data=data)
            return True, "Tedarikçi başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi eklenirken hata: {e}")
            return False, f"Tedarikçi eklenirken hata: {e}"

    def tedarikci_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, aktif_durum: bool = None):
        if self.is_online:
            try:
                params = {"skip": skip, "limit": limit, "arama": arama, "aktif_durum": aktif_durum}
                response = self._make_api_request("GET", "/tedarikciler/", params=params)
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"Tedarikçi listesi API'den çekilirken hata: {e}", exc_info=True)
                self.is_online = False

        # OFFLINE KISMI:
        filtre = {"aktif_durum": aktif_durum} if aktif_durum is not None else {}
        lokal_tedarikciler_orm = self.lokal_db.listele(model_adi="Tedarikci", filtre=filtre)

        # KRİTİK DÜZELTME: ORM objelerini dictionary'ye çevirerek AttributeError'ı çöz.
        lokal_tedarikciler = []
        for t in lokal_tedarikciler_orm:
            t_dict = {c.name: getattr(t, c.name) for c in t.__table__.columns}
            lokal_tedarikciler.append(t_dict)
            
        return {"items": lokal_tedarikciler, "total": len(lokal_tedarikciler)}

    def tedarikci_getir_by_id(self, tedarikci_id: int, kullanici_id: int):
        try:
            return self._make_api_request("GET", f"/tedarikciler/{tedarikci_id}", params={"kullanici_id": kullanici_id})
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} çekilirken hata: {e}")
            return None

    def tedarikci_guncelle(self, tedarikci_id: int, data: dict):
        try:
            self._make_api_request("PUT", f"/tedarikciler/{tedarikci_id}", data=data)
            return True, "Tedarikçi başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} güncellenirken hata: {e}")
            return False, f"Tedarikçi güncellenirken hata: {e}"

    def tedarikci_sil(self, tedarikci_id: int):
        try:    
            self._make_api_request("DELETE", f"/tedarikciler/{tedarikci_id}")
            return True, "Tedarikçi başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} silinirken hata: {e}")
            return False, f"Tedarikçi silinirken hata: {e}"
            
    def get_genel_tedarikci_id(self) -> Optional[int]:
        """API'den varsayılan genel tedarikçi ID'sini çeker veya yerel DB'den bulur."""
        if self.is_online:
            try:
                response_data = self._make_api_request("GET", "/sistem/varsayilan_cariler/genel_tedarikci_id")
                return response_data.get('id')
            except Exception as e:
                logger.warning(f"Varsayılan genel tedarikçi ID'si API'den alınamadı: {e}. Yerel DB deneniyor.")
        
        # OFFLINE FALLBACK: Yerel DB'den doğrudan çekme
        try:
            from api.modeller import Tedarikci # Yerel DB modeli
            with lokal_db_servisi.get_db() as db:
                 # KRİTİK DÜZELTME: Doğrudan ORM sorgusu yapıldı, getir_by_kod çağrısı kaldırıldı.
                lokal_tedarikci = db.query(Tedarikci).filter(
                    Tedarikci.kod == "GENEL_TEDARIKCI",
                    Tedarikci.kullanici_id == self.current_user_id
                ).first()
                if lokal_tedarikci:
                    return lokal_tedarikci.id
                logger.warning("Yerel DB'de 'GENEL_TEDARIKCI' bulunamadı.")
                return None
        except Exception as e:
            logger.error(f"Yerel DB'den varsayılan tedarikçi ID'si çekilirken hata: {e}", exc_info=True)
            return None
        
    def get_kasa_banka_by_odeme_turu(self, odeme_turu: str) -> Optional[tuple]:
        """Varsayılan kasa/banka ID'sini odeme_turu'ne göre çeker. (kullanici_id kaldırıldı)"""
        try:
            # DÜZELTME: kullanici_id parametresi imzadan ve params'tan kaldırıldı
            response_data = self._make_api_request("GET", f"/sistem/varsayilan_kasa_banka/{odeme_turu}")
            return (response_data.get('id'), response_data.get('hesap_adi'))
        except Exception as e:
            logger.warning(f"Varsayılan kasa/banka ({odeme_turu}) API'den alınamadı: {e}. None dönülüyor.")
            return None

    def get_tedarikci_net_bakiye(self, tedarikci_id: int, kullanici_id: int):
        try:
            response = self._make_api_request("GET", f"/tedarikciler/{tedarikci_id}/net_bakiye", params={"kullanici_id": kullanici_id})
            return response.get("net_bakiye")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Tedarikçi ID {tedarikci_id} net bakiye çekilirken hata: {e}")
            return None

    # --- KASA/BANKA ---
    def kasa_banka_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/kasalar_bankalar/", data=data)
            return True, "Kasa/Banka hesabı başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka eklenirken hata: {e}")
            return False, f"Kasa/Banka eklenirken hata: {e}"

    def kasa_banka_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, hesap_turu: str = None, aktif_durum: bool = None):
        """Kasa/Banka listesini çeker. (kullanici_id kaldırıldı)"""
        # DÜZELTME: kullanici_id imzadan kaldırıldı.
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "tip": hesap_turu,
            "aktif_durum": aktif_durum
        }
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}
        
        if self.is_online:
            try:
                # API çağrısından kullanici_id kaldırıldı, _make_api_request otomatik ekler.
                response = self._make_api_request("GET", "/kasalar_bankalar/", params=cleaned_params)
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False
                
        # OFFLINE KISIM: Yerel DB için filtreyi self.current_user_id ile oluştur
        filtre = {
            "aktif_durum": aktif_durum,
            "tip": hesap_turu,
            "kullanici_id": self.current_user_id 
        }
        cleaned_filtre = {k: v for k, v in filtre.items() if v is not None}
        return {"items": self.lokal_db.listele("KasaBankaHesap", cleaned_filtre), "total": 0}

    def kasa_banka_getir_by_id(self, hesap_id: int, kullanici_id: int):
        try:
            return self._make_api_request("GET", f"/kasalar_bankalar/{hesap_id}", params={"kullanici_id": kullanici_id})
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka ID {hesap_id} çekilirken hata: {e}")
            return None

    def kasa_banka_guncelle(self, hesap_id: int, data: dict, kullanici_id: int):
        data['kullanici_id'] = kullanici_id
        try:
            self._make_api_request("PUT", f"/kasalar_bankalar/{hesap_id}", data=data)
            return True, "Kasa/Banka hesabı başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka ID {hesap_id} güncellenirken hata: {e}")
            return False, f"Kasa/Banka güncellenirken hata: {e}"

    def kasa_banka_sil(self, hesap_id: int, kullanici_id: int):
        try:
            self._make_api_request("DELETE", f"/kasalar_bankalar/{hesap_id}", params={"kullanici_id": kullanici_id})
            return True, "Kasa/Banka hesabı başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Kasa/Banka ID {hesap_id} silinirken hata: {e}")
            return False, f"Kasa/Banka silinirken hata: {e}"

    # --- STOKLAR ---
    def stok_ekle(self, stok_data: dict):
        endpoint = "/stoklar/"
        
        try:
            if self.current_user_id:
                stok_data['kullanici_id'] = self.current_user_id

            stok_data_to_save = stok_data.copy()
            
            # --- 1. LOCAL WRITE (Yerel Kayıt) ---
            lokal_kayit = self.lokal_db.ekle(model_adi="Stok", veri=stok_data_to_save)
            
            # --- 2. ASENKRON PUSH KUYRUĞUNA EKLEME ---
            self.lokal_db.senkronizasyon_kuyruguna_ekle(
                kaynak_tablo="Stok", 
                kaynak_id=lokal_kayit.id, 
                islem_tipi="POST", 
                endpoint=endpoint, 
                veri=stok_data_to_save
            )
            
            success = True
            message = f"'{stok_data['ad']}' adlı ürün yerel veritabanına kaydedildi. Senkronizasyon kuyruğuna eklendi."

            # --- 3. API WRITE (Anlık Teyit, ONLINE ise) ---
            if self.is_online:
                try:
                    # Anlık API teyidi için gönderim (PUSH)
                    self._make_api_request("POST", endpoint, data=stok_data)
                    message = f"'{stok_data['ad']}' adlı ürün API'ye başarıyla gönderildi."
                except Exception as e:
                    logger.warning(f"Ürün API'ye anlık gönderilemedi. Hata: {e}. Kuyrukta bekleyecek.")
                    # Burada hata olsa bile local kaydı başarılı sayıyoruz.
            
            return success, message

        except Exception as e:
            logger.error(f"Stok eklenirken yerel kayıt sırasında kritik hata: {e}", exc_info=True)
            return False, f"Ürün eklenirken yerel kayıt sırasında hata: {e}"

    def stok_ozet_al(self, baslangic_tarihi: str = None, bitis_tarihi: str = None):
        """
        API'den tüm stokların özet bilgilerini çeker. (kullanici_id kaldırıldı)
        """
        if self.is_online:
            try:
                # DÜZELTME: kullanici_id imzadan ve params'tan kaldırıldı.
                response = self._make_api_request("GET", "/raporlar/dashboard_ozet", params={"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi})
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False
        
        # Offline modda veya API'den yanıt gelmezse boş sözlük döndür
        return {
            "toplam_satislar": 0.0,
            "toplam_tahsilatlar": 0.0,
            "toplam_odemeler": 0.0,
            "en_cok_satan_urunler": [],
        }

    def bulk_stok_upsert(self, stok_listesi: List[Dict[str, Any]], kullanici_id: int):
        for stok_data in stok_listesi:
            stok_data['kullanici_id'] = kullanici_id
        endpoint = "/stoklar/bulk_upsert"
        try:
            return self._make_api_request("POST", endpoint, data=stok_listesi)
        except ValueError as e:
            logger.error(f"Toplu stok ekleme/güncelleme API'den hata döndü: {e}")
            raise
        except Exception as e:
            logger.error(f"Toplu stok ekleme/güncelleme sırasında beklenmedik hata: {e}", exc_info=True)
            raise

    def stok_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None,
                         aktif_durum: Optional[bool] = None, kritik_stok_altinda: Optional[bool] = None,
                         kategori_id: Optional[int] = None, marka_id: Optional[int] = None,
                         urun_grubu_id: Optional[int] = None, stokta_var: Optional[bool] = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "aktif_durum": aktif_durum,
            "kritik_stok_altinda": kritik_stok_altinda,
            "kategori_id": kategori_id,
            "marka_id": marka_id,
            "urun_grubu_id": urun_grubu_id,
            "stokta_var": stokta_var
        }
        cleaned_params = {k: v for k, v in params.items() if v is not None}
        
        if self.is_online:
            try:
                response = self._make_api_request("GET", "/stoklar/", params=cleaned_params)
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"Stok listesi API'den çekilirken hata: {e}", exc_info=True)
                self.is_online = False
                
        # OFFLINE KISMI BAŞLANGICI: ORM nesnesi geliyor, sözlüğe çevrilmeli.
        filtre = {
            "aktif": aktif_durum,
            "kategori_id": kategori_id,
            "marka_id": marka_id,
            "urun_grubu_id": urun_grubu_id,
            "kullanici_id": getattr(self, "current_user_id", None)
        }
        
        lokal_stoklar_orm = self.lokal_db.listele(model_adi="Stok", filtre=filtre)
        
        # KRİTİK DÜZELTME: ORM objelerini dictionary'ye çeviriyoruz. (Çökme Hatası Çözümü)
        lokal_stoklar = []
        for s in lokal_stoklar_orm:
            s_dict = {c.name: getattr(s, c.name) for c in s.__table__.columns}
            lokal_stoklar.append(s_dict)

        # Filtreleme mantığı artık dictionary listesi üzerinde çalışacak
        if kritik_stok_altinda:
            lokal_stoklar = [s for s in lokal_stoklar if s.get('miktar', 0.0) < s.get('min_stok_seviyesi', 0.0)]
        if stokta_var:
            lokal_stoklar = [s for s in lokal_stoklar if s.get('miktar', 0.0) > 0]
        
        return {"items": lokal_stoklar, "total": len(lokal_stoklar)}

    def stok_hareketleri_listele(self, stok_id: Optional[int] = None, islem_tipi: Optional[str] = None, baslangic_tarihi: Optional[str] = None, bitis_tarihi: Optional[str] = None, limit: int = 1000, skip: int = 0):
        """Stok hareketlerini listeler."""
        endpoint = "/stoklar/hareketler/" 
        params = {
            "skip": skip,
            "limit": limit,
            "stok_id": stok_id,
            "islem_tipi": islem_tipi,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi
        }
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        if self.is_online:
            try:
                response = self._make_api_request("GET", endpoint, params=cleaned_params)
                if response is not None:
                    return response.get("items", [])
            except Exception as e:
                logger.error(f"Stok hareketleri API'den çekilirken hata: {e}", exc_info=True)
                self.is_online = False
        
        # OFFLINE KISIM: Lokal DB'den veriyi çekmek için çağrılır
        filtre = {"stok_id": stok_id, "kullanici_id": self.current_user_id}
        # Bu kısım sadece lokal_db'nizin bu metodu desteklemesi durumunda çalışması için tasarlanmıştır.
        return []

    def get_top_selling_products(self, baslangic_tarihi: str, bitis_tarihi: str, limit: int = 5):
        """En çok satan ürünleri çeker. (kullanici_id kaldırıldı)"""
        if self.is_online:
            try:
                # DÜZELTME: kullanici_id imzadan ve params'tan kaldırıldı.
                summary = self._make_api_request("GET", "/raporlar/dashboard_ozet", params={"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi})
                if summary is not None:
                    return summary.get("en_cok_satan_urunler", [])
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False
        return []

    def get_urun_faturalari(self, urun_id: int, fatura_tipi: Optional[str] = None):
        """Ürün faturalarını çeker. (kullanici_id kaldırıldı)"""
        endpoint = "/raporlar/urun_faturalari"
        # DÜZELTME: kullanici_id imzadan ve params'tan kaldırıldı.
        params = {"urun_id": urun_id, "fatura_tipi": fatura_tipi}
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}
        
        try:
            response = self._make_api_request("GET", endpoint, params=cleaned_params)
            if isinstance(response, dict) and "items" in response:
                return response.get("items", [])
            elif isinstance(response, list):
                return response
            else:
                logger.warning(f"Ürün faturaları için API'den beklenmeyen yanıt formatı: {response}")
                return []
        except Exception as e:
            logger.error(f"Ürün faturaları API'den alınamadı: {e}", exc_info=True)
            return []        

    def urun_faturalari_al(self, urun_id: int):
        """
        Belirli bir ürüne ait ilgili faturaları API'den çeker.
        Args:
            urun_id (int): İlgili faturaları listelenecek ürünün ID'si.
        Returns:
            list: İlgili faturalar listesi.
        """
        endpoint = "/raporlar/urun_faturalari"
        params = {"urun_id": urun_id}
        
        try:
            response = self._make_api_request("GET", endpoint, params=params)
            if isinstance(response, dict) and "items" in response:
                return response.get("items", [])
            elif isinstance(response, list):
                return response
            else:
                logger.warning(f"Ürün faturaları için API'den beklenmeyen yanıt formatı: {response}")
                return []
        except Exception as e:
            logger.error(f"Ürün faturaları API'den alınamadı: {e}", exc_info=True)
            return []        

    def stok_getir_by_id(self, stok_id: int, kullanici_id: int):
        """
        [MİMARİ PRENSİP: LOCAL DB FIRST]
        Ürün detaylarını her zaman önce yerel veritabanından çeker.
        Yerelde bulunamazsa ve çevrimiçi ise API'yi yedek mekanizma olarak kullanır.
        """
        # 1. HER ZAMAN yerel veritabanını dene (Hız ve Yerel Veri Bütünlüğü)
        try:
            # _get_item_by_id_lokal: Bu metot ORM objesini sözlüğe çevrilmiş olarak döndürür (UI'ın istediği format).
            lokal_stok_dict = _get_item_by_id_lokal(
                model_name="Stok", 
                item_id=stok_id, 
                kullanici_id=kullanici_id
            )
            
            if lokal_stok_dict:
                # Lokal kopyayı bulduk, HIZLI ERİŞİM için hemen döndür. API çağrısı yapılmaz.
                return lokal_stok_dict
        except Exception as e:
            logger.error(f"Stok ID {stok_id} yerel DB'den çekilirken kritik hata: {e}")
            # Hata olsa bile API'ye düşmeye devam et.
            
        # 2. Eğer yerelde bulunamazsa ve ONLINE ise API'yi dene (Yedek Mekanizma)
        if self.is_online:
            try:
                # API çağrısı, yerel kopyanın bulunmaması durumunda YEDEK MEKANİZMA olarak çalışır.
                return self._make_api_request("GET", f"/stoklar/{stok_id}", params={"kullanici_id": kullanici_id}) 
            except (ValueError, ConnectionError, Exception) as e:
                logger.error(f"Stok ID {stok_id} çekilirken API hatası: {e}. Yerel DB'de de bulunamadı.")
        
        # 3. Sonuç yoksa Hata döndür
        logger.warning(f"Stok ID {stok_id} hiçbir yerde (Yerel/API) bulunamadı.")
        return None

    def stok_guncelle(self, stok_id: int, data: dict, kullanici_id: int):
        data['kullanici_id'] = kullanici_id
        try:
            self._make_api_request("PUT", f"/stoklar/{stok_id}", data=data)
            return True, "Stok başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok ID {stok_id} güncellenirken hata: {e}")
            return False, f"Stok güncellenirken hata: {e}"

    def stok_sil(self, stok_id: int, kullanici_id: int):
        try:
            self._make_api_request("DELETE", f"/stoklar/{stok_id}", params={"kullanici_id": kullanici_id})
            return True, "Stok başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok ID {stok_id} silinirken hata: {e}")
            return False, f"Stok silinirken hata: {e}"
            
    def stok_hareket_ekle(self, stok_id: int, data: dict):
        try:
            self._make_api_request("POST", f"/stoklar/{stok_id}/hareket", data=data)
            return True, "Stok hareketi başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Stok hareketi eklenirken hata: {e}")
            return False, f"Stok hareketi eklenirken hata: {e}"
            
    def get_stok_miktari_for_kontrol(self, stok_id: int, kullanici_id: int, fatura_id_duzenle: Optional[int] = None) -> float:
        try:
            anlik_miktar_response = self._make_api_request("GET", f"/stoklar/{stok_id}/anlik_miktar", params={"kullanici_id": kullanici_id})
            anlik_miktar = anlik_miktar_response.get("anlik_miktar", 0.0)

            if fatura_id_duzenle is not None:
                fatura_kalemleri = self.fatura_kalemleri_al(fatura_id_duzenle)
                for kalem in fatura_kalemleri:
                    if kalem.get('urun_id') == stok_id:
                        fatura_tipi_db = self.fatura_getir_by_id(fatura_id_duzenle).get('fatura_turu')
                        
                        if fatura_tipi_db == self.FATURA_TIP_SATIS or fatura_tipi_db == self.FATURA_TIP_ALIS_IADE:
                            anlik_miktar += kalem.get('miktar', 0.0)
                        elif fatura_tipi_db == self.FATURA_TIP_ALIS or fatura_tipi_db == self.FATURA_TIP_SATIS_IADE:
                             anlik_miktar -= kalem.get('miktar', 0.0)
                        
                        break
            return anlik_miktar
        except Exception as e:
            logger.error(f"Stok ID {stok_id} için anlık miktar kontrol edilirken hata: {e}")
            return 0.0

    # --- FATURALAR ---
    def fatura_ekle(self, fatura_data: Dict[str, Any]):
        try:
            return self._make_api_request("POST", "/faturalar/", data=fatura_data)
        except Exception as e:
            raise ValueError(f"API'den hata: {e}")

    def fatura_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, fatura_turu: str = None, baslangic_tarihi: str = None, bitis_tarihi: str = None, cari_id: int = None, odeme_turu: str = None, kasa_banka_id: int = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "fatura_turu": fatura_turu,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi,
            "cari_id": cari_id,
            "odeme_turu": odeme_turu,
            "kasa_banka_id": kasa_banka_id
        }
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        # KRİTİK ÇÖZÜM: Türkçe Fatura Türü Değerini, API'nin beklediği İngilizce Üye Adına Çevirme
        if 'fatura_turu' in cleaned_params:
            fatura_turu_degeri = cleaned_params['fatura_turu']
            
            # Bu, API'deki ENUM'ların üye adlarıyla (SATIS, ALIS, vb.) eşleşmelidir.
            mapping = {
                "SATIŞ": "SATIS",
                "ALIŞ": "ALIS",
                "SATIŞ İADE": "SATIS_IADE",
                "ALIŞ İADE": "ALIS_IADE",
                "DEVİR GİRİŞ": "DEVIR_GIRIS"
            }
            # Eğer değer map'te varsa, üye adıyla günceller. Yoksa, gelen değeri korur.
            cleaned_params['fatura_turu'] = mapping.get(fatura_turu_degeri, fatura_turu_degeri)

        if self.is_online:
            try:
                response = self._make_api_request("GET", "/faturalar/", params=cleaned_params)
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False

        filtre = {
            "fatura_turu": fatura_turu,
            "cari_id": cari_id,
            "odeme_turu": odeme_turu,
            "kasa_banka_id": kasa_banka_id
        }
        lokal_faturalar = self.lokal_db.listele(model_adi="Fatura", filtre=filtre)
        return {"items": lokal_faturalar, "total": len(lokal_faturalar)}
                
    def fatura_getir_by_id(self, fatura_id: int):
        try:
            return self._make_api_request("GET", f"/faturalar/{fatura_id}")
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} çekilirken hata: {e}")
            return None

    def fatura_guncelle(self, fatura_id: int, data: dict):
        try:
            return self._make_api_request("PUT", f"/faturalar/{fatura_id}", data=data)
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} güncellenirken hata: {e}")
            raise

    def fatura_sil(self, fatura_id: int, kullanici_id: int):
        try:
            self._make_api_request("DELETE", f"/faturalar/{fatura_id}", params={"kullanici_id": kullanici_id})
            return True, "Fatura başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} silinirken hata: {e}")
            return False, f"Fatura silinirken hata: {e}"

    def fatura_kalemleri_al(self, fatura_id: int, kullanici_id: int):
        try:
            return self._make_api_request("GET", f"/faturalar/{fatura_id}/kalemler", params={"kullanici_id": kullanici_id})
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura ID {fatura_id} kalemleri çekilirken hata: {e}")
            return []
        
    def son_fatura_no_getir(self, fatura_tipi: str) -> str:
        """
        API'den bir sonraki fatura numarasını alır.
        Çevrimdışı modda ise manuel bir fatura numarası oluşturur.
        """
        if not self.is_online:
            yeni_fatura_no = f"MANUEL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            logger.warning(f"Çevrimdışı mod: Manuel fatura numarası oluşturuldu: {yeni_fatura_no}")
            return yeni_fatura_no
        
        mapping = {
            self.FATURA_TIP_SATIS: "SATIS",
            self.FATURA_TIP_ALIS: "ALIS",
            self.FATURA_TIP_SATIS_IADE: "SATIS_IADE",
            self.FATURA_TIP_ALIS_IADE: "ALIS_IADE",
            self.FATURA_TIP_DEVIR_GIRIS: "DEVIR_GIRIS",
        }
        api_fatura_turu = mapping.get(fatura_tipi) 

        if not api_fatura_turu:
            logger.error(f"Geçersiz veya tanınmayan fatura türü: {fatura_tipi}")
            return "FATURA_TURU_HATA"

        try:
            params = {"fatura_turu": api_fatura_turu}
            
            # DOĞRU ADRES: Rota /sistem altına taşındığı için adres güncellendi.
            response_data = self._make_api_request(
                "GET", "/sistem/next_fatura_no", params=params
            )

            # DOĞRU YANIT ANAHTARI: Pydantic modeli NextCodeResponse olduğu için 'next_code' kullanılıyor.
            if response_data and "next_code" in response_data:
                return response_data["next_code"]
            else:
                logger.warning(f"API'den beklenen fatura numarası alınamadı. Yanıt: {response_data}")
                return "FATURA_NO_HATA"
                
        except (ValueError, ConnectionError, Timeout, RequestException) as e:
            logger.error(f"API'den son fatura numarası çekilirken hata: {e}")
            self.is_online = False
            yeni_fatura_no = f"MANUEL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            return yeni_fatura_no
                
    def fatura_detay_al(self, fatura_id: int, kullanici_id: int):
        try:
            return self._make_api_request("GET", f"/faturalar/{fatura_id}", params={"kullanici_id": kullanici_id})
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Fatura detayları {fatura_id} API'den alınamadı: {e}")
            return None

    # --- SİPARİŞLER ---
    def siparis_ekle(self, data: dict):
        try:
            return self._make_api_request("POST", "/siparisler/", data=data)
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş eklenirken hata: {e}")
            raise

    def siparis_listesi_al(self, skip: int = 0, limit: int = 100, arama: str = None, siparis_turu: str = None, durum: str = None, baslangic_tarihi: str = None, bitis_tarihi: str = None, cari_id: int = None):
        params = {
            "skip": skip,
            "limit": limit,
            "arama": arama,
            "siparis_turu": siparis_turu,
            "durum": durum,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi,
            "cari_id": cari_id
        }
        params = {k: v for k, v in params.items() if v is not None}
        
        if self.is_online:
            try:
                return self._make_api_request("GET", "/siparisler/", params=params)
            except Exception as e:
                logger.error(f"Sipariş listesi alınırken hata: {e}")
                self.is_online = False
                
        filtre = {
            "cari_id": cari_id,
            "durum": durum,
            "siparis_tipi": siparis_turu
        }
        lokal_siparisler = self.lokal_db.listele(model_adi="Siparis", filtre=filtre)
        return {"items": lokal_siparisler, "total": len(lokal_siparisler)}

    def siparis_getir_by_id(self, siparis_id: int, kullanici_id: int):
        try:
            return self._make_api_request("GET", f"/siparisler/{siparis_id}", params={"kullanici_id": kullanici_id})
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} çekilirken hata: {e}")
            return None

    def siparis_guncelle(self, siparis_id: int, data: dict, kullanici_id: int):
        data['kullanici_id'] = kullanici_id
        try:
            self._make_api_request("PUT", f"/siparisler/{siparis_id}", data=data)
            return True, "Sipariş başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} güncellenirken hata: {e}")
            return False, f"Sipariş güncellenirken hata: {e}"

    def siparis_sil(self, siparis_id: int, kullanici_id: int):
        try:
            self._make_api_request("DELETE", f"/siparisler/{siparis_id}", params={"kullanici_id": kullanici_id})
            return True, "Sipariş başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Sipariş ID {siparis_id} silinirken hata: {e}")
            return False, f"Sipariş silinirken hata: {e}"

    def siparis_kalemleri_al(self, siparis_id: int, kullanici_id: int):
        try:
            return self._make_api_request("GET", f"/siparisler/{siparis_id}/kalemler", params={"kullanici_id": kullanici_id})
        except ValueError as e:
            if "bulunamadı" in str(e):
                logger.warning(f"Sipariş ID {siparis_id} için sipariş kalemi bulunamadı.")
                return []
            else:
                logger.error(f"Sipariş ID {siparis_id} kalemleri çekilirken beklenmeyen bir hata oluştu: {e}", exc_info=True)
                return []
        except Exception as e:
            logger.error(f"Sipariş ID {siparis_id} kalemleri çekilirken beklenmeyen bir hata oluştu: {e}", exc_info=True)
            return []

    def get_next_siparis_kodu(self, kullanici_id: int):
        try:
            response_data = self._make_api_request("GET", "/sistem/next_siparis_kodu", params={"kullanici_id": kullanici_id})
            return response_data.get("next_code", "OTOMATIK")
        except Exception as e:
            logger.error(f"Bir sonraki sipariş kodu API'den alınamadı: {e}")
            return "OTOMATIK"

    # --- GELİR/GİDER ---
    def gelir_gider_ekle(self, data: dict):
        try:
            self._make_api_request("POST", "/gelir_gider/", data=data)
            return True, "Gelir/Gider kaydı başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider eklenirken hata: {e}")
            return False, f"Gelir/Gider eklenirken hata: {e}"

    def gelir_gider_listesi_al(self, skip: int = 0, limit: int = 20, tip_filtre: str = None,
                            baslangic_tarihi: str = None, bitis_tarihi: str = None,
                            aciklama_filtre: str = None):
        """Gelir/Gider listesini çeker."""
        params = {"skip": skip, "limit": limit, "tip_filtre": tip_filtre, "baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi, "aciklama_filtre": aciklama_filtre}
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        if self.is_online:
            try:                
                response = self._make_api_request("GET", "/gelir_gider/", params=cleaned_params)
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False
        
        # OFFLINE KISIM: Yerel DB için filtreyi self.current_user_id ile oluştur.
        filtre = {"tip": tip_filtre, "kullanici_id": self.current_user_id} if tip_filtre else {"kullanici_id": self.current_user_id}
        lokal_list = self.lokal_db.listele(model_adi="GelirGider", filtre=filtre)
        return {"items": lokal_list, "total": len(lokal_list)}

    def gelir_gider_sil(self, gg_id: int, kullanici_id: int):
        try:
            self._make_api_request("DELETE", f"/gelir_gider/{gg_id}", params={"kullanici_id": kullanici_id})
            return True, "Gelir/Gider kaydı başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider ID {gg_id} silinirken hata: {e}")
            return False, f"Gelir/Gider silinirken hata: {e}"

    def gelir_gider_getir_by_id(self, gg_id: int, kullanici_id: int):
        try:
            return self._make_api_request("GET", f"/gelir_gider/{gg_id}", params={"kullanici_id": kullanici_id})
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Gelir/Gider ID {gg_id} çekilirken hata: {e}")
            return None

    # --- CARİ HAREKETLER (Manuel oluşturma ve silme) ---
    def cari_hareket_ekle_manuel(self, data: dict):
        try:
            self._make_api_request("POST", "/cari_hareketler/manuel", data=data)
            return True, "Manuel cari hareket başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Manuel cari hareket eklenirken hata: {e}")
            return False, f"Manuel cari hareket eklenirken hata: {e}"

    def cari_hareket_sil_manuel(self, hareket_id: int, kullanici_id: int):
        try:
            self._make_api_request("DELETE", f"/cari_hareketler/manuel/{hareket_id}", params={"kullanici_id": kullanici_id})
            return True, "Manuel cari hareket başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Manuel cari hareket silinirken hata: {e}")
            return False, f"Manuel cari hareket silinirken hata: {e}"

    def cari_hesap_ekstresi_al(self, cari_id: int, cari_tip: str, baslangic_tarihi: str, bitis_tarihi: str):
        params = {
            "cari_id": cari_id,
            "cari_turu": cari_tip, 
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi
        }
        try:
            response = self._make_api_request("GET", "/raporlar/cari_hesap_ekstresi", params=params)
            return response.get("items", []), response.get("devreden_bakiye", 0.0), True, "Başarılı"
        except Exception as e:
            logger.error(f"Cari hesap ekstresi API'den alınamadı: {e}")
            return [], 0.0, False, f"Ekstre alınırken hata: {e}"
        
    def cari_hareketleri_listele(self, cari_id: int = None, islem_turu: str = None, baslangic_tarihi: Optional[str] = None, bitis_tarihi: Optional[str] = None, limit: int = 20, skip: int = 0):
        """Cari hareketleri listeler. (kullanici_id kaldırıldı)"""
        endpoint = "/cari_hareketler/"
        # DÜZELTME: kullanici_id imzadan ve params'tan kaldırıldı.
        params = {
            "skip": skip,
            "limit": limit,
            "baslangic_tarihi": baslangic_tarihi,
            "bitis_tarihi": bitis_tarihi,
            "islem_turu": islem_turu
        }
        if cari_id is not None:
            params["cari_id"] = cari_id
        
        cleaned_params = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}

        try:
            response = self._make_api_request("GET", endpoint, params=cleaned_params)
            return response
        except ValueError as e:
            logger.error(f"Cari hareketleri listelenirken API hatası: {e}")
            return {"items": [], "total": 0}
        except Exception as e:
            logger.error(f"Cari hareketleri listelenirken beklenmeyen hata: {e}", exc_info=True)
            return {"items": [], "total": 0}

    # --- NİTELİKLER (Kategori, Marka, Grup, Birim, Ülke, Gelir/Gider Sınıflandırma) ---
    def nitelik_ekle(self, nitelik_tipi: str, data: dict):
        # 1. API'ye göndermeyi dene
        if self.is_online:
            try:
                response = self._make_api_request("POST", f"/nitelikler/{nitelik_tipi}", data=data)
                if response:
                    # API'den gelen veriyi yerel veritabanına kaydet
                    self.lokal_db.ekle(model_adi="Nitelik", veri=response)
                    return True, f"Nitelik ({nitelik_tipi}) başarıyla API'ye ve yerel veritabanına eklendi."
            except Exception as e:
                logger.warning(f"Nitelik eklenirken API'ye erişilemedi. Hata: {e}. Yerel veritabanına kaydediliyor.")
                self.is_online = False # Bağlantı kesildi, durumu güncelle
                
        # 2. Eğer API'ye erişim yoksa veya hata oluştuysa, yerel veritabanına kaydet.
        try:
            # Sadece yerel veritabanına kaydet
            self.lokal_db.ekle(model_adi="Nitelik", veri=data)
            
            # Senkronizasyon kuyruğuna ekleme
            self.lokal_db.senkronizasyon_kuyruguna_ekle("Nitelik", "POST", f"/nitelikler/{nitelik_tipi}", data)
            
            return True, f"Nitelik ({nitelik_tipi}) başarıyla yerel veritabanına eklendi. Bağlantı kurulduğunda senkronize edilecek."
        except Exception as e:
            logger.error(f"Nitelik yerel veritabanına eklenirken hata: {e}")
            return False, f"Nitelik eklenirken hata: {e}"
        
    def nitelik_guncelle(self, nitelik_tipi: str, nitelik_id: int, data: dict, kullanici_id: int):
        data['kullanici_id'] = kullanici_id
        try:
            self._make_api_request("PUT", f"/nitelikler/{nitelik_tipi}/{nitelik_id}", data=data)
            return True, f"Nitelik ({nitelik_tipi}) başarıyla güncellendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Nitelik tipi {nitelik_tipi} ID {nitelik_id} güncellenirken hata: {e}")
            raise

    def nitelik_sil(self, nitelik_tipi: str, nitelik_id: int, kullanici_id: int):
        try:
            self._make_api_request("DELETE", f"/nitelikler/{nitelik_tipi}/{nitelik_id}", params={"kullanici_id": kullanici_id})
            return True, f"Nitelik ({nitelik_tipi}) başarıyla silindi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Nitelik tipi {nitelik_tipi} ID {nitelik_id} silinirken hata: {e}")
            raise

    def kategori_listele(self, skip: int = 0, limit: int = 1000) -> Dict[str, Any]:
        if self.is_online:
            try:
                params = {"skip": skip, "limit": limit}
                response = self._make_api_request("GET", "/nitelikler/kategoriler", params=params)
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"Kategori listesi API'den alınamadı: {e}", exc_info=True)

        return self.lokal_db.listele(model_adi="Nitelik", filtre={"tip": "kategori"})

    def marka_listele(self, skip: int = 0, limit: int = 1000) -> Dict[str, Any]:
        if self.is_online:
            try:
                params = {"skip": skip, "limit": limit}
                response = self._make_api_request("GET", "/nitelikler/markalar", params=params)
                if isinstance(response, dict) and "items" in response:
                    return response
                elif isinstance(response, list):
                    return {"items": response, "total": len(response)}
                else:
                    logger.warning(f"marka_listele: API'den beklenmedik yanıt formatı. Yanıt: {response}")
                    return {"items": [], "total": 0}
            except Exception as e:
                logger.error(f"Marka listesi API'den alınamadı: {e}", exc_info=True)
                return {"items": [], "total": 0}
                        
    def urun_grubu_listele(self, skip: int = 0, limit: int = 1000) -> Dict[str, Any]:
        if self.is_online:
            try:
                params = {"skip": skip, "limit": limit}
                response = self._make_api_request("GET", "/nitelikler/urun_gruplari", params=params)
                if isinstance(response, dict) and "items" in response:
                    return response
                elif isinstance(response, list):
                    return {"items": response, "total": len(response)}
                else:
                    logger.warning(f"urun_grubu_listele: API'den beklenmedik yanıt formatı. Yanıt: {response}")
                    return {"items": [], "total": 0}
            except Exception as e:
                logger.error(f"Ürün grubu listesi API'den alınamadı: {e}", exc_info=True)
                return {"items": [], "total": 0}

    def urun_birimi_listele(self, kullanici_id: int, skip: int = 0, limit: int = 1000) -> Dict[str, Any]:
        params = {"skip": skip, "limit": limit, "kullanici_id": kullanici_id}
        
        if self.is_online:
            try:
                response = self._make_api_request("GET", "/nitelikler/urun_birimleri", params=params)
                if isinstance(response, dict) and "items" in response:
                    return response
            except Exception as e:
                logger.error(f"Ürün birimi listesi API'den alınamadı: {e}", exc_info=True)
                self.is_online = False
                
        # OFFLINE FALLBACK: Yerel veritabanından çek (Çevrimdışı hatası çözüldü)
        return self.lokal_db.listele(model_adi="Nitelik", filtre={"nitelik_tipi": "birim", "kullanici_id": kullanici_id})
            
    def ulke_listele(self, kullanici_id: int, skip: int = 0, limit: int = 1000) -> Dict[str, Any]:
        params = {"skip": skip, "limit": limit, "kullanici_id": kullanici_id}

        if self.is_online:
            try:
                response = self._make_api_request("GET", "/nitelikler/ulkeler", params=params)
                if isinstance(response, dict) and "items" in response:
                    return response
            except Exception as e:
                logger.error(f"Ülke listesi API'den alınamadı: {e}", exc_info=True)
                self.is_online = False
                
        # OFFLINE FALLBACK: Yerel veritabanından çek (Çevrimdışı hatası çözüldü)
        return self.lokal_db.listele(model_adi="Nitelik", filtre={"nitelik_tipi": "ulke", "kullanici_id": kullanici_id})

    def gelir_siniflandirma_listele(self, kullanici_id: int, skip: int = 0, limit: int = 1000, id: int = None):
        params = {"skip": skip, "limit": limit, "id": id, "kullanici_id": kullanici_id}
        cleaned_params = {k: v for k, v in params.items() if v is not None}

        if self.is_online:
            try:
                response = self._make_api_request("GET", "/nitelikler/gelir_siniflandirmalari", params=cleaned_params)
                if response is not None:
                    return response
            except Exception as e:
                self.app.set_status_message(f"API hatası. Yerel veritabanı kullanılıyor: {e}", "orange")
                self.is_online = False
        
        filtre = {"tip": "gelir_siniflandirma", "id": id, "kullanici_id": kullanici_id} if id else {"tip": "gelir_siniflandirma", "kullanici_id": kullanici_id}
        lokal_list = self.lokal_db.listele(model_adi="Nitelik", filtre=filtre)
        return {"items": lokal_list, "total": len(lokal_list)}

    def gider_siniflandirma_listele(self, kullanici_id: int, skip: int = 0, limit: int = 1000, id: int = None):
        params = {"skip": skip, "limit": limit, "id": id, "kullanici_id": kullanici_id}
        cleaned_params = {k: v for k, v in params.items() if v is not None}
        
        if self.is_online:
            try:
                response = self._make_api_request("GET", "/nitelikler/gider_siniflandirmalari", params=cleaned_params)
                if response is not None:
                    return response
            except Exception as e:
                self.app.set_status_message(f"API hatası. Yerel veritabanı kullanılıyor: {e}", "orange")
                self.is_online = False

        filtre = {"tip": "gider_siniflandirma", "id": id, "kullanici_id": kullanici_id} if id else {"tip": "gider_siniflandirma", "kullanici_id": kullanici_id}
        lokal_list = self.lokal_db.listele(model_adi="Nitelik", filtre=filtre)
        return {"items": lokal_list, "total": len(lokal_list)}
    
    # --- RAPORLAR ---
    def get_dashboard_summary(self, baslangic_tarihi: str = None, bitis_tarihi: str = None):
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        
        if self.is_online:
            try:
                response = self._make_api_request("GET", "/raporlar/dashboard_ozet", params=params)
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"Dashboard özeti API'den çekilirken hata: {e}", exc_info=True)
                self.is_online = False

        return {
            "toplam_satislar": 0.0,
            "toplam_alislar": 0.0,
            "toplam_tahsilatlar": 0.0,
            "toplam_odemeler": 0.0,
            "kritik_stok_sayisi": 0,
            "en_cok_satan_urunler": [],
            "vadesi_yaklasan_alacaklar_toplami": 0.0,
            "vadesi_gecmis_borclar_toplami": 0.0
        }

    def get_total_sales(self, baslangic_tarihi: str = None, bitis_tarihi: str = None):
        if self.is_online:
            try:
                summary = self._make_api_request(
                    "GET",
                    "/raporlar/dashboard_ozet",
                    params={"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
                )
                if summary is not None:
                    return summary.get("toplam_satislar", 0.0)
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False
        return 0.0

    def get_satislar_detayli_rapor(self, kullanici_id: int, baslangic_tarihi: str, bitis_tarihi: str, cari_id: int = None):
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi, "cari_id": cari_id, "kullanici_id": kullanici_id}
        if self.is_online:
            try:
                response = self._make_api_request("GET", "/raporlar/satislar_detayli_rapor", params=params)
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False

        return {"items": [], "total": 0}

    def get_kar_zarar_verileri(self, baslangic_tarihi: str, bitis_tarihi: str) -> dict:
        """
        Belirtilen tarih aralığı için kar/zarar verilerini API üzerinden çeker.
        """
        # GÜNCELLEME: 'kullanici_id' parametresi kaldırıldı.
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        
        if self.is_online:
            try:
                # GÜNCELLEME: API isteğinden 'kullanici_id' parametresi kaldırıldı.
                response = self._make_api_request("GET", "/raporlar/kar_zarar_verileri", params=params)
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"Kar/Zarar verileri API isteği sırasında hata oluştu: {e}", exc_info=True)
                self.is_online = False
        
        # Hata durumunda veya çevrimdışı modda dönecek varsayılan değer
        return {
            "toplam_satis_geliri": 0.0,
            "toplam_satis_maliyeti": 0.0,
            "toplam_alis_gideri": 0.0,
            "diger_gelirler": 0.0,
            "diger_giderler": 0.0,
            "brut_kar": 0.0,
            "net_kar": 0.0
        }
                
    def get_monthly_income_expense_summary(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Aylık gelir/gider özetini çeker. (kullanici_id kaldırıldı)"""
        if self.is_online:
            try:
                yil = int(baslangic_tarihi.split('-')[0])
                # DÜZELTME: kullanici_id imzadan ve params'tan kaldırıldı.
                response = self._make_api_request("GET", "/raporlar/gelir_gider_aylik_ozet", params={"yil": yil})
                if response is not None:
                    if isinstance(response, list):
                        return response
                    return response.get("aylik_ozet", [])
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False
        
        # OFFLINE KISIM: Lokal DB'den veriyi çekmek için çağrıldı
        return self.get_gelir_gider_aylik_ozet(baslangic_tarihi, bitis_tarihi).get("aylik_ozet", [])

    def get_gross_profit_and_cost(self, baslangic_tarihi: str, bitis_tarihi: str):
        """Brüt kâr ve maliyet verilerini çeker. (kullanici_id kaldırıldı)"""
        # DÜZELTME: kullanici_id imzadan ve params'tan kaldırıldı.
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
        try:
            data = self._make_api_request("GET", "/raporlar/kar_zarar_verileri", params=params)
            brut_kar = data.get("brut_kar", 0.0)
            cogs = data.get("toplam_satis_maliyeti", 0.0)
            toplam_satis_geliri = data.get("toplam_satis_geliri", 0.0)
            brut_kar_orani = (brut_kar / toplam_satis_geliri) * 100 if toplam_satis_geliri > 0 else 0.0
            return brut_kar, cogs, brut_kar_orani
        except Exception as e:
            logger.error(f"Brüt kar ve maliyet verileri çekilirken hata: {e}")
            return 0.0, 0.0, 0.0

    def get_nakit_akisi_verileri(self, baslangic_tarihi: str, bitis_tarihi: str):
        if self.is_online:
            try:
                response = self._make_api_request(
                    "GET",
                    "/raporlar/nakit_akisi_raporu",
                    params={"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi}
                )
                if response is not None:
                    return response
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False

        return {"nakit_girisleri": 0.0, "nakit_cikislar": 0.0, "net_nakit_akisi": 0.0}

    def get_tum_kasa_banka_bakiyeleri(self):
        """Tüm kasa/banka bakiyelerini çeker. (kullanici_id kaldırıldı)"""
        try:
            response = self.kasa_banka_listesi_al(limit=1000) 
            return response.get("items", [])
        except Exception as e:
            logger.error(f"Tüm kasa/banka bakiyeleri çekilirken hata: {e}")
            return []

    def get_cari_yaslandirma_verileri(self, tarih: str = None):
        params = {"tarih": tarih} if tarih else {}
        try:
            response = self._make_api_request("GET", "/raporlar/cari_yaslandirma_raporu", params=params)
            return response
        except Exception as e:
            logger.error(f"Cari yaşlandırma verileri çekilirken hata: {e}")
            return {"musteri_alacaklar": [], "tedarikci_borclar": []}

    def get_critical_stock_items(self):
        if self.is_online:
            try:
                response = self.stok_listesi_al(kritik_stok_altinda=True, limit=1000)
                if response is not None:
                    return response.get("items", [])
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False
        return []

    def get_top_selling_products(self, baslangic_tarihi: str, bitis_tarihi: str, limit: int = 5):
        """En çok satan ürünleri çeker. (kullanici_id kaldırıldı)"""
        if self.is_online:
            try:
                # DÜZELTME: kullanici_id imzadan ve params'tan kaldırıldı.
                summary = self._make_api_request("GET", "/raporlar/dashboard_ozet", params={"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi})
                if summary is not None:
                    return summary.get("en_cok_satan_urunler", [])
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False
        return []

    def tarihsel_satis_raporu_verilerini_al(self, kullanici_id: int, baslangic_tarihi: str, bitis_tarihi: str, cari_id: int = None):
        params = {"baslangic_tarihi": baslangic_tarihi, "bitis_tarihi": bitis_tarihi, "cari_id": cari_id, "kullanici_id": kullanici_id}
        if self.is_online:
            try:
                response_data = self._make_api_request("GET", "/raporlar/satislar_detayli_rapor", params=params)
                if response_data is not None:
                    return response_data.get("items", [])
            except Exception as e:
                logger.error(f"API hatası. Yerel veritabanı kullanılıyor: {e}", exc_info=True)
                self.is_online = False
        return []
            
    # --- YARDIMCI FONKSİYONLAR ---
    def _format_currency(self, value):
        """Sayısal değeri Türkçe para birimi formatına dönüştürür."""
        try:
            locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.1254')
            except locale.Error:
                logger.warning("Sistemde Türkçe locale bulunamadı, varsayılan formatlama kullanılacak.")
        
        try:
            return locale.format_string("%.2f", self.safe_float(value), grouping=True) + " TL"
        except Exception:
            return f"{self.safe_float(value):.2f} TL".replace('.', ',')
        
    def _format_numeric(self, value, decimals):
        """Sayısal değeri Türkçe formatına dönüştürür. `_format_currency`'nin para birimi olmayan versiyonu."""
        try:
            locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.1254')
            except locale.Error:
                logger.warning("Sayısal formatlama için Türkçe locale bulunamadı.")
        
        try:
            return locale.format_string(f"%.{decimals}f", self.safe_float(value), grouping=True).replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return f"{self.safe_float(value):.{decimals}f}".replace('.', ',')

    def safe_float(self, value):
        """String veya None değeri güvenli bir şekilde float'a dönüştürür, hata durumunda 0.0 döner."""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            
            # DÜZELTME: Önce binlik ayıracını kaldır, sonra ondalık ayıracını noktaya çevir
            cleaned_value = str(value).strip()
            if cleaned_value:
                # Binlik ayıracını kaldır (örn. 10.000 -> 10000)
                cleaned_value = cleaned_value.replace(".", "")
                # Ondalık ayıracını noktaya çevir (örn. 10000,00 -> 10000.00)
                cleaned_value = cleaned_value.replace(",", ".")
            
            return float(cleaned_value)
        except (ValueError, TypeError):
            return 0.0
        
    def create_tables(self, cursor=None):
        logger.info("create_tables çağrıldı ancak artık veritabanı doğrudan yönetilmiyor. Tabloların API veya create_pg_tables.py aracılığıyla oluşturulduğu varsayılıyor.")
        pass

    def gecmis_hatali_kayitlari_temizle(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_ghost_records", data={})
            return True, response.get("message", "Geçmiş hatalı kayıtlar temizlendi.")
        except Exception as e:
            logger.error(f"Geçmiş hatalı kayıtlar temizlenirken hata: {e}")
            return False, f"Geçmiş hatalı kayıtlar temizlenirken hata: {e}"

    def stok_envanterini_yeniden_hesapla(self):
        try:
            response = self._make_api_request("POST", "/admin/recalculate_stock_inventory", data={})
            return True, response.get("message", "Stok envanteri yeniden hesaplandı.")
        except Exception as e:
            logger.error(f"Stok envanteri yeniden hesaplanırken hata: {e}")
            return False, f"Stok envanteri yeniden hesaplanırken hata: {e}"

    def clear_stok_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_stock_data", data={})
            return True, response.get("message", "Stok verileri temizlendi.")
        except Exception as e:
            logger.error(f"Stok verileri temizlenirken hata: {e}")
            return False, f"Stok verileri temizlenirken hata: {e}"

    def clear_musteri_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_customer_data", data={})
            return True, response.get("message", "Müşteri verileri temizlendi.")
        except Exception as e:
            logger.error(f"Müşteri verileri temizlenirken hata: {e}")
            return False, f"Müşteri verileri temizlenirken hata: {e}"

    def clear_tedarikci_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_supplier_data", data={})
            return True, response.get("message", "Tedarikçi verileri temizlendi.")
        except Exception as e:
            logger.error(f"Tedarikçi verileri temizlenirken hata: {e}")
            return False, f"Tedarikçi verileri temizlenirken hata: {e}"

    def clear_kasa_banka_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_cash_bank_data", data={})
            return True, response.get("message", "Kasa/Banka verileri temizlendi.")
        except Exception as e:
            logger.error(f"Kasa/Banka verileri temizlenirken hata: {e}")
            return False, f"Kasa/Banka verileri temizlenirken hata: {e}"

    def clear_all_transaction_data(self):
        try:
            response = self._make_api_request("POST", "/admin/clear_all_transactions", data={})
            return True, response.get("message", "Tüm işlem verileri temizlendi.")
        except Exception as e:
            logger.error(f"Tüm işlem verileri temizlenirken hata: {e}")
            return False, f"Tüm işlem verileri temizlenirken hata: {e}"

    def clear_all_data(self):
        """
        Tüm verileri API üzerinden temizleme işlemini tetikler.
        """
        try:
            # API'ye DELETE isteği gönderiyoruz.
            response = self._make_api_request(
                method="DELETE",
                endpoint="/admin/clear_all_data"
            )
            if response is None:
                return False, "API'den yanıt alınamadı. İşlem tamamlanamadı."

            return True, response.get("message", "Tüm veriler temizlendi (kullanıcılar hariç).")
        except Exception as e:
            logger.error(f"Tüm veriler temizlenirken hata: {e}")
            return False, f"Tüm veriler temizlenirken hata: {e}"

    def tarihsel_satis_raporu_excel_olustur(self, rapor_verileri, dosya_yolu, bas_t, bit_t):
        logger.info(f"Excel raporu oluşturma tetiklendi: {dosya_yolu}")
        return True, f"Rapor '{dosya_yolu}' adresine başarıyla kaydedildi."
    
    def cari_ekstresi_pdf_olustur(self, data_dir, cari_tip, cari_id, bas_t, bit_t, file_path, result_queue):
        logger.info(f"PDF ekstresi oluşturma tetiklendi: {file_path}")
        success = True
        message = f"Cari ekstresi '{file_path}' adresine başarıyla kaydedildi."
        result_queue.put((success, message))

    def get_gecmis_fatura_kalemi_bilgileri(self, cari_id: int, urun_id: int, fatura_tipi: str, kullanici_id: int):
        try:
            params = {
                "cari_id": cari_id,
                "urun_id": urun_id,
                "fatura_tipi": fatura_tipi,
                "kullanici_id": kullanici_id
            }
            response = self._make_api_request("GET", "/raporlar/fatura_kalem_gecmisi", params=params)
            return response.get('items', [])
        except Exception as e:
            logger.error(f"Geçmiş fatura kalemleri API'den alınamadı: {e}")
            return []
                                                                
    def veresiye_borc_ekle(self, cari_id, cari_tip, tarih, tutar, aciklama):
        """
        Veresiye borç ekleme işlemini API'ye gönderir.
        """
        data = {
            "cari_id": cari_id,
            "cari_tip": cari_tip,
            "tarih": tarih,
            "islem_turu": "VERESİYE_BORÇ",
            "islem_yone": self.CARI_ISLEM_YON_BORC, # HATA: Cari islem yonu sabiti tanimli degil, varsayimsal olarak borc yazildi
            "tutar": tutar,
            "aciklama": aciklama,
            "kaynak": self.KAYNAK_TIP_VERESIYE_BORC_MANUEL
        }
        try:
            self._make_api_request("POST", "/cari_hareketler/manuel", data=data)
            return True, "Veresiye borç başarıyla eklendi."
        except (ValueError, ConnectionError, Exception) as e:
            logger.error(f"Veresiye borç eklenirken hata: {e}")
            return False, f"Veresiye borç eklenirken hata: {e}"

    def get_next_stok_kodu(self):
        if self.is_online:
            try:
                response_data = self._make_api_request("GET", "/sistem/next_stok_code")
                return response_data.get("next_code", "STK-HATA")
            except (ValueError, ConnectionError, Exception) as e:
                logger.error(f"Bir sonraki stok kodu API'den alınamadı, çevrimdışı moda geçiliyor: {e}")
                self.is_online = False

        return f"MANUEL-{int(time.time())}"
        
    def get_next_musteri_kodu(self, kullanici_id: int):
        try:
            response_data = self._make_api_request("GET", "/sistem/next_musteri_code", params={"kullanici_id": kullanici_id})
            return response_data.get("next_code", "M-HATA")
        except Exception as e:
            logger.error(f"Bir sonraki müşteri kodu API'den alınamadı: {e}")
            return "M-HATA"
        
    def get_next_tedarikci_kodu(self, kullanici_id: int):
        try:
            response_data = self._make_api_request("GET", "/sistem/next_tedarikci_code", params={"kullanici_id": kullanici_id})
            return response_data.get("next_code", "T-HATA")
        except Exception as e:
            logger.error(f"Bir sonraki tedarikci kodu API'den alınamadı: {e}")
            return "T-HATA"

    def siparis_listele(self, kullanici_id: int, baslangic_tarih: Optional[str] = None, bitis_tarihi: Optional[str] = None,
                             arama_terimi: Optional[str] = None, cari_id_filter: Optional[int] = None,
                             durum_filter: Optional[str] = None, siparis_tipi_filter: Optional[str] = None,
                             limit: int = 100, offset: int = 0) -> dict:
        params = {
            "skip": offset,
            "limit": limit,
            "baslangic_tarihi": baslangic_tarih,
            "bitis_tarihi": bitis_tarihi,
            "arama": arama_terimi,
            "cari_id": cari_id_filter,
            "durum": durum_filter,
            "siparis_tipi": siparis_tipi_filter,
            "kullanici_id": kullanici_id
        }
        params = {k: v for k, v in params.items() if v is not None}
        
        if self.is_online:
            try:
                response = self._make_api_request("GET", "/siparisler/", params=params)
                if response is not None:
                    return response
            except Exception as e:
                self.app.set_status_message(f"API hatası. Yerel veritabanı kullanılıyor: {e}", "orange")
                self.is_online = False

        filtre = {
            "cari_id": cari_id_filter,
            "durum": durum_filter,
            "siparis_tipi": siparis_tipi_filter,
            "kullanici_id": kullanici_id
        }
        lokal_siparisler = self.lokal_db.listele(model_adi="Siparis", filtre=filtre)
        return {"items": lokal_siparisler, "total": len(lokal_siparisler)}

    def get_gelir_gider_aylik_ozet(self, baslangic_tarihi: str, bitis_tarihi: str) -> Dict[str, Any]:
        """
        Belirtilen tarih aralığına göre aylık gelir ve giderlerin özetini döndürür.
        """
        try:
            with lokal_db_servisi.get_db() as db:
                query = db.query(
                    func.strftime('%Y-%m', GelirGider.tarih).label('ay_yil'),
                    func.strftime('%Y', GelirGider.tarih).label('yil'),
                    func.strftime('%m', GelirGider.tarih).label('ay_numarasi'),
                    func.sum(case((GelirGider.tip == 'GELİR', GelirGider.tutar), else_=0)).label('toplam_gelir'),
                    func.sum(case((GelirGider.tip == 'GİDER', GelirGider.tutar), else_=0)).label('toplam_gider')
                ).filter(
                    GelirGider.tarih >= baslangic_tarihi,
                    GelirGider.tarih <= bitis_tarihi
                ).group_by(
                    'ay_yil', 'yil', 'ay_numarasi'
                ).order_by('ay_yil')

                aylik_ozet = query.all()
                
                result = []
                for row in aylik_ozet:
                    ay_adi = locale.nl_langinfo(locale.MON_1 + int(row.ay_numarasi) - 1)
                    result.append({
                        "ay_yil": row.ay_yil,
                        "ay_adi": ay_adi,
                        "yil": int(row.yil),
                        "ay_numarasi": int(row.ay_numarasi),
                        "toplam_gelir": float(row.toplam_gelir),
                        "toplam_gider": float(row.toplam_gider)
                    })
                    
            return {"aylik_ozet": result}
        except Exception as e:
            logger.error(f"Aylık gelir/gider özeti alınırken hata: {e}", exc_info=True)
            return {"aylik_ozet": []}

    def get_monthly_gross_profit_summary(self, kullanici_id: int, baslangic_tarihi: str, bitis_tarihi: str) -> List[Dict[str, Any]]:
        """
        Belirtilen tarih aralığı için aylık brüt kâr özetini hesaplar.
        """
        try:
            with lokal_db_servisi.get_db() as db:
                query = db.query(
                    func.strftime('%Y-%m', Fatura.tarih).label('ay_yil'),
                    func.strftime('%Y', Fatura.tarih).label('yil'),
                    func.strftime('%m', Fatura.tarih).label('ay_numarasi'),
                    func.sum(case((Fatura.fatura_turu == self.FATURA_TIP_SATIS, Fatura.genel_toplam), else_=0)).label('toplam_satis_geliri'),
                    func.sum(case((Fatura.fatura_turu == self.FATURA_TIP_ALIS, Fatura.genel_toplam), else_=0)).label('toplam_alis_gideri'),
                ).filter(
                    Fatura.kullanici_id == kullanici_id,
                    Fatura.tarih >= baslangic_tarihi,
                    Fatura.tarih <= bitis_tarihi
                ).group_by(
                    'ay_yil', 'yil', 'ay_numarasi'
                ).order_by('ay_yil')

                aylik_ozet = query.all()
                
                result = []
                for row in aylik_ozet:
                    ay_adi = locale.nl_langinfo(locale.MON_1 + int(row.ay_numarasi) - 1)
                    
                    # Satılan Malın Maliyetini (COGS) hesapla
                    cogs_subquery = db.query(func.sum(StokHareket.miktar * Stok.alis_fiyati)) \
                                    .join(Stok, Stok.id == StokHareket.urun_id) \
                                    .filter(
                                        StokHareket.kaynak == 'FATURA',
                                        StokHareket.islem_tipi == self.STOK_ISLEM_TIP_CIKIS_FATURA_SATIS,
                                        StokHareket.kullanici_id == kullanici_id,
                                        StokHareket.tarih >= f"{row.ay_yil}-01",
                                        StokHareket.tarih <= f"{row.ay_yil}-31"
                                    ).scalar() or 0.0

                    brut_kar = (row.toplam_satis_geliri or 0) - cogs_subquery
                    
                    result.append({
                        "ay_yil": row.ay_yil,
                        "ay_adi": ay_adi,
                        "toplam_satis_geliri": float(row.toplam_satis_geliri),
                        "satilan_malin_maliyeti": float(cogs_subquery),
                        "brut_kar": float(brut_kar)
                    })
                    
            return result
        except Exception as e:
            logger.error(f"Aylık brüt kâr özeti alınırken hata: {e}", exc_info=True)
            return []

    def dosya_indir_api_den(self, api_dosya_yolu: str, yerel_kayit_yolu: str) -> tuple:
        """
        API'den belirli bir dosyayı indirir ve yerel olarak kaydeder.
        """
        full_api_url = f"{self.api_base_url}{api_dosya_yolu}"
        try:
            with requests.get(full_api_url, stream=True) as r:
                r.raise_for_status() # HTTP 4xx/5xx hataları için hata fırlat
                with open(yerel_kayit_yolu, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True, f"Dosya başarıyla indirildi: {yerel_kayit_yolu}"
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if r is not None and r.response is not None:
                try:
                    error_detail = r.response.json().get('detail', error_detail)
                except ValueError: # JSON decode hatası
                    pass
            logger.error(f"API'den dosya indirilirken hata oluştu: {full_api_url}. Hata: {error_detail}")
            return False, f"Dosya indirilemedi: {error_detail}"
        except Exception as e:
            logger.error(f"Beklenmedik bir hata oluştu: {e}")
            return False, f"Dosya indirilirken beklenmedik bir hata oluştu: {e}"    
        
    def satis_raporu_excel_olustur_api_den(self, bas_tarihi: str, bit_tarihi: str, cari_id: Optional[int] = None) -> tuple:
        """
        API'yi çağırarak sunucu tarafında satış raporu Excel dosyasını oluşturur.
        """
        api_generation_path = "/raporlar/generate_satis_raporu_excel"
        generation_params = {
            "baslangic_tarihi": bas_tarihi,
            "bitis_tarihi": bit_tarihi
        }
        if cari_id:
            generation_params["cari_id"] = cari_id

        try:
            # KRİTİK DÜZELTME: 'path' yerine 'endpoint' ve 'json' yerine 'data' kullanıldı.
            response = self._make_api_request(
                method="POST",
                endpoint=api_generation_path,
                data=generation_params
            )
            message = response.get("message", "Rapor oluşturma isteği gönderildi.")
            filepath = response.get("filepath") # Sunucudaki dosya yolu

            return True, message, filepath
        except ValueError as e:
            logger.error(f"Satış raporu Excel oluşturma API çağrısı başarısız: {e}")
            return False, f"Rapor oluşturulamadı: {e}", None
        except Exception as e:
            logger.error(f"Satış raporu Excel oluşturma sırasında beklenmedik hata: {e}")
            return False, f"Rapor oluşturulurken beklenmedik bir hata oluştu: {e}", None
        
    def database_backup(self, file_path: str):
        """
        Veritabanını API üzerinden yedekleme işlemini tetikler.
        """
        try:
            response = self._make_api_request("POST", "/admin/yedekle", data={"file_path": file_path})
            created_file_path = response.get("file_path", file_path)
            return True, response.get("message", "Yedekleme işlemi tamamlandı."), created_file_path
        except Exception as e:
            logger.error(f"Veritabanı yedekleme API isteği başarısız: {e}")
            return False, f"Yedekleme başarısız oldu: {e}", None

    def database_restore(self, file_path: str):
        """
        Veritabanını API üzerinden geri yükleme işlemini tetikler.
        """
        try:
            # API'ye geri yükleme isteği gönderin
            response = self._make_api_request("POST", "/admin/geri_yukle", data={"file_path": file_path})
            return True, response.get("message", "Geri yükleme işlemi tamamlandı."), None
        except Exception as e:
            logger.error(f"Veritabanı geri yükleme API isteği başarısız: {e}")
            return False, f"Geri yükleme başarısız oldu: {e}", None
        
    def senkronize_veriler_lokal_db_icin(self, kullanici_id: int):
        """
        Lokal veritabanı senkronizasyonunu başlatmak için bir aracı metot.
        KRİTİK DÜZELTME: current_user_id yerine metoda gelen kullanici_id kullanıldı.
        """
        # API'den veri çekerken access_token'ın olması gerekir.
        if self.access_token is None:
            self._load_access_token() 
            if self.access_token is None:
                return False, "JWT Token mevcut değil. Lütfen önce giriş yapın."

        return lokal_db_servisi.senkronize_veriler(
            self.api_base_url, 
            access_token=self.access_token,
            current_user_id=kullanici_id # KRİTİK DÜZELTME: Fonksiyona gelen argüman kullanılıyor.
        )
    
    def _close_local_db_connections(self):
        """
        Uygulamanın lokal veritabanı bağlantılarını sonlandırır.
        """
        try:
            lokal_db_servisi.engine.dispose()
            logging.info("Lokal veritabanı bağlantıları başarıyla sonlandırıldı.")
        except Exception as e:
            logging.error(f"Lokal veritabanı bağlantıları sonlandırılırken hata: {e}", exc_info=True)    

    def temizle_veritabani_dosyasi(self):
        """
        Yerel veritabanı dosyasını güvenli bir şekilde siler.
        """
        db_path = os.path.join(os.path.dirname(__file__), 'onmuhasebe.db')
        
        if os.path.exists(db_path):
            try:
                # Dosya kilitlerini serbest bırakmak için motoru sonlandırın
                lokal_db_servisi.engine.dispose()
                time.sleep(1) # OS'in kilitleri serbest bırakması için 1 saniye bekleyin
                
                os.remove(db_path)
                return True, "Yerel veritabanı dosyası başarıyla silindi."
            except Exception as e:
                return False, f"Veritabanı dosyası silinirken bir hata oluştu: {e}"
        else:
            return False, "Yerel veritabanı dosyası zaten mevcut değil."

    def _close_api_db_connections(self):
        try:
            response = requests.post(f"{self.api_base_url}/sistem/veritabani_baglantilarini_kapat")
            response.raise_for_status()
            return True, response.text
        except Exception as e:
            return False, f"API bağlantıları kapatılırken hata: {e}"
        
    def _load_access_token(self):
        """Yerel veritabanından access token'ı yükler."""
        try:
            # Buradaki metod adlarını kendi lokal_db_servisi'nizdeki karşılıklarıyla doğrulayın
            ayarlar = self.lokal_db.ayarlari_yukle() 
            self.access_token = ayarlar.get("access_token")
            self.token_type = ayarlar.get("token_type")
            if self.access_token:
                logger.info("Kalıcı depolamadan access token başarıyla yüklendi.")
        except Exception as e:
            logger.warning(f"Access token yüklenirken hata oluştu: {e}")
            pass

    def yeni_firma_olustur(self, firma_data: dict):
        """Yeni bir firma (tenant) ve yönetici hesabı oluşturmak için API'ye istek gönderir."""
        if not self.is_online:
            return False, "Bu işlem için internet bağlantısı gereklidir."
        
        try:
            # Sunucunuzdaki ilgili endpoint'in bu olduğunu varsayıyoruz.
            # Gerekirse endpoint yolunu (örn: '/yonetici/firma_olustur') güncelleyin.
            endpoint = f"{self.api_base_url}/yonetici/firma_olustur"
            response = requests.post(endpoint, json=firma_data, timeout=20)
            
            if response.status_code == 201: # 201 Created
                return True, response.json().get("mesaj", "Firma başarıyla oluşturuldu.")
            else:
                # Sunucudan gelen hata mesajını göster
                error_detail = response.json().get("detail", "Bilinmeyen bir sunucu hatası.")
                return False, f"Hata Kodu: {response.status_code} - {error_detail}"

        except requests.exceptions.RequestException as e:
            logging.error(f"Firma oluşturma API isteği sırasında hata: {e}")
            return False, f"API sunucusuna bağlanılamadı: {e}"

    def personel_listesi_getir(self):
        """Giriş yapmış yöneticinin personel listesini API'den alır."""
        if not self.is_online:
            logger.warning("Personel listesi için çevrimiçi mod gereklidir.")
            return None, "Çevrimdışı veya yetkisiz."
        try:
            # KRİTİK DÜZELTME: self.session yerine _make_api_request kullanıldı.
            # _make_api_request, Authorization header'ını otomatik ekler.
            response = self._make_api_request("GET", "/yonetici/personel-listesi")
            
            # _make_api_request başarılı olursa JSON objesini döner, hatayı kendisi fırlatır.
            return response, None
        
        except ValueError as e:
            # _make_api_request'in fırlattığı hataları yakalar (API/Bağlantı hataları)
            error_message = str(e)
            logger.error(f"Personel listesi alınırken hata: {error_message}")
            return None, error_message
        except Exception as e:
            logger.error(f"Personel listesi alınırken beklenmedik hata: {e}", exc_info=True)
            return None, "Personel listesi alınırken beklenmedik bir hata oluştu."

    def personel_olustur(self, data: dict):
        """Yeni bir personel oluşturmak için API'ye istek gönderir."""
        if not self.is_online or not self.access_token:
            logger.warning("Personel oluşturmak için çevrimiçi mod ve yetkilendirme gereklidir.")
            # Hata mesajı döndürülürken, ValueError fırlatmak yerine uyumlu formatta döndürüldü.
            return None, "Çevrimdışı veya yetkisiz. Personel oluşturulamaz."
        try:
            # KRİTİK DÜZELTME: Artık data sözlüğü doğrudan alınıp API'ye gönderiliyor.
            response = self._make_api_request(
                method="POST", 
                endpoint="/yonetici/personel-olustur",
                data=data
            )
            # _make_api_request başarılı olursa JSON objesini döner, hatayı kendisi fırlatır.
            return response, None
            
        except ValueError as e:
            logger.error(f"Personel oluşturulurken API hatası: {e}")
            return None, str(e)
        except Exception as e:
            logger.error(f"Personel oluşturulurken beklenmedik hata: {e}", exc_info=True)
            return None, "Personel oluşturulurken beklenmedik bir hata oluştu."

    def personel_detay_getir(self, personel_id: int):
        """API'den tek bir personelin detayını çeker."""
        if not self.is_online or not self.access_token:
            return None, "Çevrimdışı modda detay çekilemez."
        try:
            # API'deki rotanın /kullanicilar/{id} olduğu varsayılıyor
            response = self._make_api_request("GET", f"/kullanicilar/{personel_id}")
            return response, None
        except Exception as e:
            logger.error(f"Personel ID {personel_id} detayları çekilemedi: {e}")
            return None, str(e)

    def personel_guncelle(self, personel_id: int, data: dict):
        """Mevcut personeli günceller."""
        if not self.is_online or not self.access_token:
            return False, "Çevrimdışı veya yetkisiz."
        try:
            # API'deki rotanın /yonetici/personel-guncelle/{id} olduğu varsayılıyor
            self._make_api_request("PUT", f"/yonetici/personel-guncelle/{personel_id}", data=data)
            return True, "Personel başarıyla güncellendi."
        except Exception as e:
            logger.error(f"Personel güncelleme başarısız: {e}")
            return False, str(e)

    def api_get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """SUPERADMIN ve genel amaçlı GET istekleri için."""
        try:
            return self._make_api_request("GET", endpoint, params=params)
        except ValueError as e:
            # _make_api_request'ten gelen hatayı yakalar ve SuperAdminPaneli'nin beklediği sözlük formatına çevirir.
            return {"error": "API Hatası", "detail": str(e)}
        except Exception as e:
            return {"error": "Genel Hata", "detail": str(e)}

    def api_post(self, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """SUPERADMIN ve genel amaçlı POST istekleri için (Örn: Lisans Uzat)."""
        try:
            return self._make_api_request("POST", endpoint, data=data, params=params)
        except ValueError as e:
            return {"error": "API Hatası", "detail": str(e)}
        except Exception as e:
            return {"error": "Genel Hata", "detail": str(e)}

    def api_put(self, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """SUPERADMIN ve genel amaçlı PUT istekleri için (Örn: Durum Değiştir)."""
        try:
            return self._make_api_request("PUT", endpoint, data=data, params=params)
        except ValueError as e:
            return {"error": "API Hatası", "detail": str(e)}
        except Exception as e:
            return {"error": "Genel Hata", "detail": str(e)}

# --- YENİ YARDIMCI FONKSİYONLAR (OnMuhasebe sınıfı dışına taşındı) ---
# SessionLocal hatasını çözmek için, bu fonksiyonlar lokal_db_servisi.get_db() kullanacak.
def update_local_user_credentials(kullanici_id: int, email: str, sifre_hash: str, rol: str): 
    """
    Başarılı API girişinden sonra dönen kritik bilgileri (şifre hash dahil) 
    yerel SQLite veritabanındaki Kullanici kaydına yazar/günceller.
    """
    try:
        with lokal_db_servisi.get_db() as db: 
            user = db.query(Kullanici).filter(Kullanici.id == kullanici_id).first()

            if user:
                # KRİTİK DÜZELTME 2: email güncellenir. kullanici_adi kaldırıldı.
                user.email = email 
                user.sifre_hash = sifre_hash
                user.rol = rol 
            else:
                # Kullanıcı yoksa (ilk giriş), oluştur
                user = Kullanici(
                    id=kullanici_id,
                    email=email, # email kullanılır
                    sifre_hash=sifre_hash,
                    rol=rol,
                )
                db.add(user)
            
            db.commit() 
            logger.info(f"Yerel DB: Kullanıcı '{email}' (ID: {kullanici_id}) şifre hash'i güncellendi/kaydedildi.")
            return True
    except Exception as e:
        logger.error(f"Yerel kullanıcı bilgilerini güncellerken KRİTİK HATA: {e}", exc_info=True)
        return False

def authenticate_offline_user(email: str, password: str) -> Optional[Dict[str, Any]]: 
    """
    Çevrimdışı modda yerel veritabanı üzerinden e-posta ve şifre ile doğrular.
    """
    try:
        with lokal_db_servisi.get_db() as db: 
            
            # KRİTİK DÜZELTME 3: Kullanici.kullanici_adi yerine Kullanici.email ile sorgulama yapılır
            user = db.query(Kullanici).filter(Kullanici.email == email).first()

            if not user or not user.sifre_hash:
                logger.warning(f"Yerel DB: Kullanıcı '{email}' bulunamadı veya şifre hash'i eksik.")
                return None

            is_password_correct = verify_password(password, user.sifre_hash)

            if is_password_correct:
                logger.info(f"Yerel DB: Kullanıcı '{email}' için doğrulama başarılı.")
                # KRİTİK DÜZELTME 4: Response'ta email döndürülür
                return {
                    "kullanici_id": user.id,
                    "email": user.email,
                    "rol": user.rol if user.rol else "user",
                }
            else:
                logger.warning("Yerel veritabanı üzerinden doğrulama başarısız: Hatalı şifre.")
                return None

    except Exception as e:
        logger.error(f"Yerel doğrulama sırasında beklenmedik hata: {e}", exc_info=True)
        return None

def _get_item_by_code_lokal(model_name: str, kod: str, kullanici_id: int):
    """Verilen modelden kodu eşleşen tek bir öğeyi yerel DB'den getirir."""
    # Musteri, Tedarikci, Stok modellerinin üstte import edildiği varsayılır.
    model_mapping = {"Musteri": Musteri, "Tedarikci": Tedarikci}
    Model = model_mapping.get(model_name)
    if not Model:
        return None
        
    try:
        with lokal_db_servisi.get_db() as db:
            return db.query(Model).filter(
                Model.kod == kod,
                Model.kullanici_id == kullanici_id
            ).first()
    except Exception as e:
        logger.error(f"Yerel {model_name} '{kod}' çekilirken hata: {e}", exc_info=True)
        return None

def _get_item_by_id_lokal(model_name: str, item_id: int, kullanici_id: int):
    """Verilen modelden ID'si eşleşen tek bir öğeyi yerel DB'den getirir ve sözlüğe çevirir."""
    from api.modeller import Stok, Musteri, Tedarikci # Modellerin import edildiği varsayılır.

    model_mapping = {"Stok": Stok, "Musteri": Musteri, "Tedarikci": Tedarikci}
    Model = model_mapping.get(model_name)
    if not Model:
        return None

    try:
        with lokal_db_servisi.get_db() as db:
            lokal_item = db.query(Model).filter(
                Model.id == item_id,
                Model.kullanici_id == kullanici_id
            ).first()

            if lokal_item:
                # KRİTİK DÜZELTME: ORM objesini sözlüğe çevir (UI'ın beklediği format)
                return {c.name: getattr(lokal_item, c.name) for c in lokal_item.__table__.columns}
            return None
    except Exception as e:
        logger.error(f"Yerel {model_name} ID {item_id} çekilirken hata: {e}", exc_info=True)
        return None