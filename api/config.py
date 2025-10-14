# Lütfen api/config.py dosyasının TÜM içeriğini bununla değiştirin.
import os
from dotenv import load_dotenv

# .env dosyasını projenin kök dizininden yükle
load_dotenv()

# Ayarları .env dosyasından oku ve merkezi bir nesne olarak sun
class Settings:
    DB_USER: str = os.getenv("DB_USER")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: str = os.getenv("DB_PORT")
    DB_NAME: str = os.getenv("DB_NAME")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Veritabanı URL'sini otomatik olarak oluştur
    DATABASE_URL: str = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Ayarları diğer dosyaların kullanabilmesi için tek bir nesne oluştur
settings = Settings()