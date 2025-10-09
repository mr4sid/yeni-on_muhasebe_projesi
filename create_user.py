import requests
import json
import logging
import os
from config import API_BASE_URL

# Logger kurulumu
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    def create_initial_user():
        """
        API üzerinden başlangıç admin kullanıcısını oluşturur.
        """
        api_url = f"{API_BASE_URL}/dogrulama/register"
        
        # Oluşturulacak kullanıcı bilgileri
        user_data = {
            "kullanici_adi": "admin",
            # DEĞİŞİKLİK BURADA: Şifreyi istediğiniz gibi bırakabilirsiniz, 
            # ancak giriş yaparken burada ne yazıyorsa onu kullanmalısınız.
            "sifre": "755397", 
            "ad": "Varsayılan",      # EKLENDİ: Model ile uyumlu hale getirmek için
            "soyad": "Yönetici",    # EKLENDİ: Model ile uyumlu hale getirmek için
            "email": "admin@example.com", # EKLENDİ: Model ile uyumlu hale getirmek için
            "telefon": "0",             # EKLENDİ: Model ile uyumlu hale getirmek için
            "rol": "admin"          # DÜZELTİLDİ: 'yetki' anahtarı 'rol' olarak değiştirildi
        }

        try:
            response = requests.post(api_url, json=user_data)
            response.raise_for_status()  # HTTP hataları için istisna fırlatır
            
            response_data = response.json()
            if "id" in response_data:
                logger.info("Başlangıç admin kullanıcısı başarıyla oluşturuldu.")
                print("Başlangıç admin kullanıcısı başarıyla oluşturuldu: admin/admin")
                
                # Ekleme: Başlangıç verilerini de oluşturalım
                response = requests.post(f"{API_BASE_URL}/admin/ilk_veri_olustur?kullanici_id={response_data['id']}")
                response.raise_for_status()
                logger.info("Başlangıç verileri başarıyla oluşturuldu.")
                print("Başlangıç verileri başarıyla oluşturuldu.")
            else:
                logger.warning(f"Kullanıcı oluşturma isteği gönderildi, ancak beklenmeyen bir yanıt alındı: {response_data}")
                print(f"Uyarı: Kullanıcı oluşturma isteği gönderildi, ancak beklenmeyen bir yanıt alındı: {response_data}")

        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code == 409:
                logger.warning("Kullanıcı zaten mevcut. Admin hesabı oluşturulamadı.")
                print("Uyarı: Kullanıcı zaten mevcut. Admin hesabı oluşturulamadı.")
            else:
                logger.error(f"HTTP hatası oluştu: {http_err}")
                print(f"Hata: HTTP hatası oluştu: {http_err}")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"API'ye bağlanılamadı. Lütfen sunucunun çalıştığından emin olun. Hata: {req_err}")
            print(f"Hata: API'ye bağlanılamadı. Lütfen sunucunun çalıştığından emin olun. Hata: {req_err}")
        except Exception as e:
            logger.error(f"Beklenmeyen bir hata oluştu: {e}")
            print(f"Hata: Beklenmeyen bir hata oluştu: {e}")

if __name__ == "__main__":
    create_initial_user()