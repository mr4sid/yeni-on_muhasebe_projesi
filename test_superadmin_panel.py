#!/usr/bin/env python3
"""
SUPERADMIN Panel Test Script
Bu script, SuperAdminPaneli'nin çöküp çökmediğini test eder.
"""
import sys
import logging
from PySide6.QtWidgets import QApplication, QMessageBox

# Logging ayarları
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mock db_manager sınıfı
class MockDBManager:
    def __init__(self):
        self.access_token = "test_token"
        self.api_base_url = "http://localhost:8000"
    
    def api_get(self, endpoint, params=None):
        """Mock API GET - Boş firma listesi döndürür"""
        logger.info(f"Mock API GET çağrıldı: {endpoint}")
        return []  # Boş liste döndür
    
    def api_put(self, endpoint, data=None, params=None):
        """Mock API PUT"""
        logger.info(f"Mock API PUT çağrıldı: {endpoint}")
        return {"unvan": "Test Firma"}

def main():
    logger.info("Test başlatılıyor...")
    
    app = QApplication(sys.argv)
    
    try:
        logger.info("SuperAdminPaneli import ediliyor...")
        from superadmin_panel import SuperAdminPaneli
        
        logger.info("Mock db_manager oluşturuluyor...")
        mock_db = MockDBManager()
        
        logger.info("SuperAdminPaneli oluşturuluyor...")
        panel = SuperAdminPaneli(mock_db)
        
        logger.info("Panel gösteriliyor...")
        panel.show()
        
        logger.info("✅ Panel başarıyla açıldı! Test başarılı.")
        QMessageBox.information(None, "Test Başarılı", "SuperAdminPaneli başarıyla açıldı!")
        
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"❌ HATA: {e}", exc_info=True)
        QMessageBox.critical(None, "Test Hatası", f"Panel açılırken hata:\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

