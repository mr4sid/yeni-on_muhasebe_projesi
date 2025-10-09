import subprocess
import time
import os
import sys

# Windows için .exe yolu
python_executable = sys.executable

def start_api_server():
    """
    API sunucusunu yeni bir terminal penceresinde başlatır.
    """
    try:
        # Uvicorn komutu
        command = [python_executable, "-m", "uvicorn", "api.api_ana:app", "--reload", "--port", "8001"]
        
        # Windows'ta yeni bir terminal penceresi açmak için
        if os.name == 'nt':
            subprocess.Popen(['start', 'cmd', '/k'] + command, shell=True)
        else: # Linux/macOS için
            subprocess.Popen(command)
        
        print("API sunucusu başlatılıyor...")
        time.sleep(5)  # Sunucunun başlaması için bekle
    except Exception as e:
        print(f"HATA: API sunucusu başlatılırken bir hata oluştu: {e}")

def start_desktop_app():
    """
    Masaüstü uygulamasını başlatır.
    """
    try:
        command = [python_executable, "arayuz.py"]
        
        # Uygulamayı başlat ve bekle
        subprocess.run(command)
        
    except Exception as e:
        print(f"HATA: Masaüstü uygulaması başlatılırken bir hata oluştu: {e}")

if __name__ == "__main__":
    start_api_server()
    start_desktop_app()
    print("Program sonlandı.")