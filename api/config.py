import os
from dotenv import load_dotenv
from datetime import timedelta

# Projenin kök dizininde .env dosyasını yükleyin
load_dotenv()

# JWT için gizli anahtar
# Ortam değişkeninden alın, yoksa varsayılan bir değer kullanın.
SECRET_KEY = os.getenv("SECRET_KEY", "gizli-anahtar-cok-gizli-kimse-bilmesin")

# Token için kullanılacak algoritma
ALGORITHM = "HS256"

# Token'ın geçerlilik süresi
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Veritabanı bağlantı URL'sini ortam değişkenlerinden oluşturun
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Alembic ayarları için veritabanı URL'si
ALEMBIC_DATABASE_URL = SQLALCHEMY_DATABASE_URL