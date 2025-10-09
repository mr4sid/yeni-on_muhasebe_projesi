from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import text
from alembic import context
import sys
import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Projenin ana dizinini Python yoluna ekle
# Bu, 'api' modülünün bulunabilmesini sağlar
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- EN KRİTİK DEĞİŞİKLİK BURADA ---
# Alembic'in modelleri tanıyabilmesi için Base'i ve modellerin bulunduğu modülü import ediyoruz.
from api.veritabani import Base
from api import semalar  # Bu satır, Alembic'in tüm tablolarınızı görmesini sağlar

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata'yı Base'den alıyoruz. Yukarıdaki import sayesinde Alembic ne yapacağını bilecek.
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    # .env dosyasından okunan verileri kullanmak için bu bölümü koruyoruz
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    conf = config.get_section(config.config_ini_section)
    conf["sqlalchemy.url"] = db_url

    connectable = engine_from_config(
        conf,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()