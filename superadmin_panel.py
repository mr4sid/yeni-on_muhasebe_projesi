# superadmin_panel.py dosyasının tam içeriği
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QMessageBox, QInputDialog, QComboBox, QHeaderView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from datetime import datetime, date

class SuperAdminPaneli(QMainWindow):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.setWindowTitle("SUPERADMIN Yönetim Paneli")
        self.setMinimumSize(1200, 700)
        
        # Ana widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Başlık
        baslik = QLabel("🔐 SUPERADMIN - Firma Yönetim Paneli")
        baslik.setStyleSheet("font-size: 20px; font-weight: bold; padding: 10px;")
        baslik.setAlignment(Qt.AlignCenter)
        layout.addWidget(baslik)
        
        # Firma listesi tablosu
        self.firma_tablosu = QTableWidget()
        self.firma_tablosu.setColumnCount(8)
        self.firma_tablosu.setHorizontalHeaderLabels([
            "ID", "Firma Adı", "Firma No", "Lisans Başlangıç",
            "Lisans Bitiş", "Kalan Gün", "Durum", "Kurucu ID" # Kullanıcı Sayısı şimdilik Kurucu ID olarak düzeltildi
        ])
        self.firma_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.firma_tablosu.setSelectionBehavior(QTableWidget.SelectRows)
        self.firma_tablosu.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.firma_tablosu)
        
        # Butonlar
        buton_layout = QHBoxLayout()
        
        self.btn_yenile = QPushButton("🔄 Yenile")
        buton_layout.addWidget(self.btn_yenile)  # ✅ Sadece ekle

        self.btn_lisans_uzat = QPushButton("⏱️ Lisans Uzat")
        self.btn_lisans_uzat.clicked.connect(self.lisans_uzat)
        buton_layout.addWidget(self.btn_lisans_uzat)
        
        self.btn_askiya_al = QPushButton("⛔ Askıya Al")
        self.btn_askiya_al.clicked.connect(self.askiya_al)
        buton_layout.addWidget(self.btn_askiya_al)
        
        self.btn_aktif_yap = QPushButton("✅ Aktif Yap")
        self.btn_aktif_yap.clicked.connect(self.aktif_yap)
        buton_layout.addWidget(self.btn_aktif_yap)
        
        self.btn_detay = QPushButton("📊 Detay Görüntüle")
        self.btn_detay.clicked.connect(self.detay_goruntule)
        buton_layout.addWidget(self.btn_detay)
        
        layout.addLayout(buton_layout)
        
        self._setup_connections() 
        
    def showEvent(self, event):
        """Pencere gösterildikten SONRA veri yükle."""
        super().showEvent(event)
        QTimer.singleShot(200, self.firmalari_yukle)

    def _setup_connections(self):
        """Tüm buton bağlantılarını merkezi olarak yönetir."""
        self.btn_yenile.clicked.connect(self.firmalari_yukle)
        self.btn_lisans_uzat.clicked.connect(self.lisans_uzat)
        self.btn_askiya_al.clicked.connect(self.askiya_al)
        self.btn_aktif_yap.clicked.connect(self.aktif_yap)
        self.btn_detay.clicked.connect(self.detay_goruntule)

    def firmalari_yukle(self):
        """SUPERADMIN API'sinden tüm firmaları çeker ve tabloya yükler. (SADECE GÜVENLİ VERİ GÖSTERİMİ)"""
        self.firma_tablosu.setRowCount(0)
        
        try:
            # API çağrısı
            response = self.db_manager.api_get("/superadmin/firmalar")
            
            if isinstance(response, dict) and "error" in response:
                error_msg = response.get('detail', 'Bilinmeyen API Hatası')
                QMessageBox.critical(self, "API Hata", f"Firmalar yüklenemedi. Detay: {error_msg}")
                return
            
            if not isinstance(response, list):
                 QMessageBox.critical(self, "Hata", "API'den beklenmeyen veri formatı (Liste bekleniyordu).")
                 return
                 
            firmalar = response 
            self.firma_tablosu.setRowCount(len(firmalar))
            
            for row, firma in enumerate(firmalar):
                
                # KRİTİK GÜVENLİK DÜZELTMESİ: Tüm dinamik tarih hesaplamaları ve renklendirmeler kaldırıldı.
                # Yalnızca ham string verisini atıyoruz. Çökme olmazsa sorun dinamik koddaydı.
                
                self.firma_tablosu.setItem(row, 0, QTableWidgetItem(str(firma.get("id", "N/A"))))
                self.firma_tablosu.setItem(row, 1, QTableWidgetItem(firma.get("unvan", "N/A")))
                self.firma_tablosu.setItem(row, 2, QTableWidgetItem(firma.get("firma_no", "N/A")))
                
                # SADECE HAM TARİH STRING'İ
                self.firma_tablosu.setItem(row, 3, QTableWidgetItem(str(firma.get("lisans_baslangic_tarihi", "N/A"))))
                self.firma_tablosu.setItem(row, 4, QTableWidgetItem(str(firma.get("lisans_bitis_tarihi", "N/A"))))
                
                # KALAN GÜN: Hesaplama kaldırıldı, sadece durum stringi eklendi
                self.firma_tablosu.setItem(row, 5, QTableWidgetItem("N/A (Hesap Kaldırıldı)")) 
                
                # DURUM: Renklendirme kaldırıldı, sadece durum stringi eklendi
                self.firma_tablosu.setItem(row, 6, QTableWidgetItem(firma.get("lisans_durum", "N/A")))
                
                # Kurucu ID
                self.firma_tablosu.setItem(row, 7, QTableWidgetItem(str(firma.get("kurucu_personel_id", "N/A"))))

        # Bu try/except bloğu, her ihtimale karşı UI kilitlenmesini engellemek için korunur.
        except Exception as e:
            QMessageBox.critical(self, "Kritik UI Hata (Geri Düzeltme)", f"Veri atama sırasında hata: {e}")
            
    # ... Diğer yardımcı metotlar (secili_firma_id_al, lisans_uzat, askiya_al, aktif_yap, detay_goruntule) 
    # Talimat 4.2'deki tam içeriği yansıtmaktadır.
    
    def secili_firma_id_al(self):
        """Tabloda seçili olan firmanın ID'sini döndürür."""
        secili_satirlar = self.firma_tablosu.selectedItems()
        if not secili_satirlar:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir firma seçin.")
            return None
        
        secili_satir = self.firma_tablosu.currentRow()
        firma_id = int(self.firma_tablosu.item(secili_satir, 0).text())
        return firma_id
    
    def lisans_uzat(self):
        """Seçili firmanın lisans süresini uzatır."""
        firma_id = self.secili_firma_id_al()
        if not firma_id:
            return
        
        uzatma_gun, ok = QInputDialog.getInt(
            self, "Lisans Uzat",
            "Kaç gün uzatmak istiyorsunuz?",
            30, 1, 365, 1
        )
        
        if not ok:
            return
        
        try:
            # KRİTİK DÜZELTME 1: POST isteği olmasına rağmen API Query parametreleri kullanıyor. 
            # API'deki rota PUT olarak tanımlandığından, api_put kullanmak daha doğru.
            response = self.db_manager.api_put(
                f"/superadmin/{firma_id}/lisans-uzat", # Rota ID içeriyor
                params={"gun_ekle": uzatma_gun} # Query parametreleri 'params' ile gönderilir
            )
            
            if response and "unvan" in response: 
                QMessageBox.information(self, "Başarılı", f"Lisans süresi {uzatma_gun} gün uzatıldı.")
                self.firmalari_yukle()
            else:
                QMessageBox.critical(self, "Hata", f"Lisans uzatma başarısız: {response.get('detail', 'Bilinmeyen Hata') if response else 'Sunucuya Ulaşılamadı'}")
        
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Lisans uzatılırken hata oluştu: {e}")
    
    def askiya_al(self):
        """Seçili firmayı askıya alır."""
        firma_id = self.secili_firma_id_al()
        if not firma_id:
            return
        
        onay = QMessageBox.question(
            self, "Onay",
            "Bu firmayı askıya almak istediğinizden emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if onay != QMessageBox.Yes:
            return
        
        try:
            # KRİTİK DÜZELTME 2: Query parametresi 'params' ile gönderilir.
            response = self.db_manager.api_put(
                f"/superadmin/{firma_id}/durum-degistir",
                params={"yeni_durum": "ASKIDA"}
            )
            
            if response and "unvan" in response:
                QMessageBox.information(self, "Başarılı", f"{response['unvan']} firması askıya alındı.")
                self.firmalari_yukle()
            else:
                QMessageBox.critical(self, "Hata", f"Askıya alma başarısız: {response.get('detail', 'Bilinmeyen Hata') if response else 'Sunucuya Ulaşılamadı'}")
        
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Askıya alınırken hata oluştu: {e}")
    
    def aktif_yap(self):
        """Seçili firmayı aktif yapar."""
        firma_id = self.secili_firma_id_al()
        if not firma_id:
            return
        
        try:
            # KRİTİK DÜZELTME 3: Query parametresi 'params' ile gönderilir.
            response = self.db_manager.api_put(
                f"/superadmin/{firma_id}/durum-degistir",
                params={"yeni_durum": "AKTIF"}
            )
            
            if response and "unvan" in response:
                QMessageBox.information(self, "Başarılı", f"{response['unvan']} firması aktifleştirildi.")
                self.firmalari_yukle()
            else:
                QMessageBox.critical(self, "Hata", f"Aktifleştirme başarısız: {response.get('detail', 'Bilinmeyen Hata') if response else 'Sunucuya Ulaşılamadı'}")
        
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Aktifleştirilirken hata oluştu: {e}")
    
    def detay_goruntule(self):
        """Seçili firmanın detaylı bilgilerini gösterir."""
        firma_id = self.secili_firma_id_al()
        if not firma_id:
            return
        
        try:
            # Talimat 4.3'te ekleyeceğimiz api_get metodu kullanılır
            response = self.db_manager.api_get(f"/superadmin/{firma_id}/detay")
            
            if not response or "firma_detay" not in response:
                QMessageBox.critical(self, "Hata", "Firma detayları yüklenemedi. API hatası veya boş yanıt.")
                return
            
            detay = response['firma_detay']
            detay_mesaj = f"""
            Firma ID: {detay.get('id')}
            Firma Adı: {detay.get('unvan')}
            Firma No: {detay.get('firma_no')}
            Veritabanı: {detay.get('db_adi')}
            
            Lisans Başlangıç: {detay.get('lisans_baslangic_tarihi')}
            Lisans Bitiş: {detay.get('lisans_bitis_tarihi')}
            Kalan Gün: {response.get('kalan_gun')} gün
            Durum: {detay.get('lisans_durum')}
            
            Oluşturulma Tarihi: {detay.get('olusturma_tarihi').split('T')[0] if detay.get('olusturma_tarihi') else 'N/A'}
            Kullanıcı Sayısı: {response.get('kullanici_sayisi')}
            Kurucu Personel ID: {detay.get('kurucu_personel_id')}
            """
            
            QMessageBox.information(self, "Firma Detayları", detay_mesaj)
        
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Detaylar görüntülenirken kritik hata oluştu: {e}")