# create.py dosyasının tam işeriği
import requests
import json
import logging
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
    API üzerinden başlangıç admin kullanıcısını ve ilişkili firmasını oluşturur.
    """
    api_url = f"{API_BASE_URL}/dogrulama/register"
    
    # Oluşturulacak kullanıcı ve firma bilgileri (Yeni modele %100 uyumlu)
    user_data = {
        "sifre": "755397", 
        "ad": "Master",
        "soyad": "Yönetici",
        "email": "admin@master.com",
        "telefon": "0000000000",
        "rol": "admin",
        "firma_adi": "Master Yonetim Firmasi",
        "firma_no": "mv1000"
    }

    try:
        response = requests.post(api_url, json=user_data)
        
        if response.status_code != 200:
             try:
                 error_detail = response.json().get("detail", "Detay yok")
                 logger.error(f"Kullanıcı oluşturma başarısız. Statü Kodu: {response.status_code}, Hata: {error_detail}")
                 print(f"Hata: Kullanıcı oluşturma başarısız - {error_detail}")
             except json.JSONDecodeError:
                 logger.error(f"Kullanıcı oluşturma başarısız. Statü Kodu: {response.status_code}, Yanıt: {response.text}")
                 print(f"Hata: Sunucudan anlaşılamayan bir yanıt geldi. Statü Kodu: {response.status_code}")
             return

        response.raise_for_status()
        
        response_data = response.json()
        if "id" in response_data:
            logger.info("Başlangıç admin kullanıcısı ve firması başarıyla oluşturuldu.")
            print("Başlangıç admin kullanıcısı ve firması başarıyla oluşturuldu: admin@master.com / 755397")
        else:
            logger.warning(f"Kullanıcı oluşturma isteği başarılı, ancak yanıtta 'id' alanı bulunamadı: {response_data}")
            print(f"Uyarı: Kullanıcı oluşturma isteği başarılı, ancak beklenmedik bir yanıt alındı: {response_data}")

    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 400:
            logger.warning("Kullanıcı (admin@master.com) zaten mevcut. Oluşturma adımı atlandı.")
            print("Uyarı: Kullanıcı zaten mevcut. Oluşturma adımı atlandı.")
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