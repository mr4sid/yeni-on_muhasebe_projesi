# superadmin_panel.py - TAMAMEN YENİ VE DÜZELTİLMİŞ VERSİYON
# Tarih: 22 Ekim 2025
# Düzeltmeler:
# - Çoklu buton bağlantısı kaldırıldı
# - showEvent() iyileştirildi
# - Detaylı logging eklendi
# - Her hücre için ayrı try-catch
# - Yükleme kilit mekanizması

import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QMessageBox, QInputDialog, QComboBox, QHeaderView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from datetime import datetime, date

logger = logging.getLogger(__name__)

class SuperAdminPaneli(QMainWindow):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.setWindowTitle("🔐 SUPERADMIN - Firma Yönetim Paneli")
        self.setMinimumSize(1200, 700)
        
        logger.info("SuperAdminPaneli __init__ başladı")
        
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
            "Lisans Bitiş", "Kalan Gün", "Durum", "Kurucu ID"
        ])
        self.firma_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.firma_tablosu.setSelectionBehavior(QTableWidget.SelectRows)
        self.firma_tablosu.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.firma_tablosu)
        
        # Butonlar - DÜZELTME: Bağlantılar sadece _setup_connections içinde yapılacak
        buton_layout = QHBoxLayout()
        
        self.btn_yenile = QPushButton("🔄 Yenile")
        buton_layout.addWidget(self.btn_yenile)
        
        self.btn_lisans_uzat = QPushButton("⏱️ Lisans Uzat")
        buton_layout.addWidget(self.btn_lisans_uzat)
        
        self.btn_askiya_al = QPushButton("⛔ Askıya Al")
        buton_layout.addWidget(self.btn_askiya_al)
        
        self.btn_aktif_yap = QPushButton("✅ Aktif Yap")
        buton_layout.addWidget(self.btn_aktif_yap)
        
        self.btn_detay = QPushButton("📊 Detay Görüntüle")
        buton_layout.addWidget(self.btn_detay)
        
        layout.addLayout(buton_layout)
        
        # Buton bağlantılarını yap
        self._setup_connections()
        
        # GÜVENLİK: İlk yükleme bayrağını başlangıçta ayarla
        self._first_show_done = False
        self._loading = False  # Yükleme kilit mekanizması
        
        logger.info("SuperAdminPaneli __init__ tamamlandı")
        
    def showEvent(self, event):
        """Pencere gösterildikten SONRA veri yükle (sadece bir kez)."""
        try:
            super().showEvent(event)
            logger.info(f"showEvent tetiklendi. _first_show_done={self._first_show_done}, _loading={self._loading}")
            
            # Sadece ilk gösterimde ve yükleme devam etmiyorsa
            if not self._first_show_done and not self._loading:
                self._first_show_done = True
                self._loading = True
                logger.info("Firmalar yüklenecek (QTimer ile 500ms sonra)...")
                QTimer.singleShot(500, self._safe_load_firmalar)
        except Exception as e:
            logger.error(f"showEvent hatası: {e}", exc_info=True)
    
    def _safe_load_firmalar(self):
        """Güvenli firma yükleme wrapper'i."""
        try:
            logger.info("_safe_load_firmalar çağrıldı")
            self.firmalari_yukle()
        except Exception as e:
            logger.error(f"_safe_load_firmalar hatası: {e}", exc_info=True)
            QMessageBox.critical(self, "Yükleme Hatası", f"Firmalar yüklenirken kritik hata:\n{e}")
        finally:
            self._loading = False
            logger.info("Yükleme tamamlandı, kilit kaldırıldı")

    def _setup_connections(self):
        """Tüm buton bağlantılarını merkezi olarak yönetir."""
        self.btn_yenile.clicked.connect(self.firmalari_yukle)
        self.btn_lisans_uzat.clicked.connect(self.lisans_uzat)
        self.btn_askiya_al.clicked.connect(self.askiya_al)
        self.btn_aktif_yap.clicked.connect(self.aktif_yap)
        self.btn_detay.clicked.connect(self.detay_goruntule)

    def firmalari_yukle(self):
        """SUPERADMIN API'sinden tüm firmaları çeker ve tabloya yükler."""
        try:
            logger.info("Firmalar yüklenmeye başlanıyor...")
            self.firma_tablosu.setRowCount(0)
            
            # API çağrısı
            logger.info("API'ye istek gönderiliyor: /superadmin/firmalar")
            response = self.db_manager.api_get("/superadmin/firmalar")
            logger.info(f"API yanıtı alındı: {type(response)}")
            
            # Hata kontrolü
            if isinstance(response, dict) and "error" in response:
                error_msg = response.get('detail', 'Bilinmeyen API Hatası')
                logger.error(f"API hatası: {error_msg}")
                QMessageBox.warning(self, "API Hata", f"Firmalar yüklenemedi:\n{error_msg}")
                return
            
            # Liste kontrolü
            if not isinstance(response, list):
                logger.error(f"Beklenmeyen veri formatı: {type(response)}")
                QMessageBox.warning(self, "Hata", "API'den beklenmeyen veri formatı.")
                return
            
            logger.info(f"{len(response)} firma bulundu")
            firmalar = response
            
            # Boş liste kontrolü
            if len(firmalar) == 0:
                logger.warning("Firma listesi boş")
                QMessageBox.information(self, "Bilgi", "Hiç firma kaydı bulunamadı.")
                return
            
            # Tablo satır sayısını ayarla
            self.firma_tablosu.setRowCount(len(firmalar))
            logger.info(f"Tablo {len(firmalar)} satıra ayarlandı")
            
            # Firmaları tabloya ekle
            for row, firma in enumerate(firmalar):
                try:
                    logger.debug(f"Firma {row+1}/{len(firmalar)} işleniyor...")
                    
                    # GÜVENLİ VERİ ATAMA - Her hücre için ayrı try-catch
                    try:
                        self.firma_tablosu.setItem(row, 0, QTableWidgetItem(str(firma.get("id", "N/A"))))
                    except Exception as e:
                        logger.error(f"ID atama hatası: {e}")
                        self.firma_tablosu.setItem(row, 0, QTableWidgetItem("ERROR"))
                    
                    try:
                        self.firma_tablosu.setItem(row, 1, QTableWidgetItem(str(firma.get("unvan", "N/A"))))
                    except Exception as e:
                        logger.error(f"Unvan atama hatası: {e}")
                        self.firma_tablosu.setItem(row, 1, QTableWidgetItem("ERROR"))
                    
                    try:
                        self.firma_tablosu.setItem(row, 2, QTableWidgetItem(str(firma.get("firma_no", "N/A"))))
                    except Exception as e:
                        logger.error(f"Firma no atama hatası: {e}")
                        self.firma_tablosu.setItem(row, 2, QTableWidgetItem("ERROR"))
                    
                    try:
                        self.firma_tablosu.setItem(row, 3, QTableWidgetItem(str(firma.get("lisans_baslangic_tarihi", "N/A"))))
                    except Exception as e:
                        logger.error(f"Lisans başlangıç atama hatası: {e}")
                        self.firma_tablosu.setItem(row, 3, QTableWidgetItem("ERROR"))
                    
                    try:
                        self.firma_tablosu.setItem(row, 4, QTableWidgetItem(str(firma.get("lisans_bitis_tarihi", "N/A"))))
                    except Exception as e:
                        logger.error(f"Lisans bitiş atama hatası: {e}")
                        self.firma_tablosu.setItem(row, 4, QTableWidgetItem("ERROR"))
                    
                    try:
                        self.firma_tablosu.setItem(row, 5, QTableWidgetItem("N/A"))
                    except Exception as e:
                        logger.error(f"Kalan gün atama hatası: {e}")
                        self.firma_tablosu.setItem(row, 5, QTableWidgetItem("ERROR"))
                    
                    try:
                        self.firma_tablosu.setItem(row, 6, QTableWidgetItem(str(firma.get("lisans_durum", "N/A"))))
                    except Exception as e:
                        logger.error(f"Durum atama hatası: {e}")
                        self.firma_tablosu.setItem(row, 6, QTableWidgetItem("ERROR"))
                    
                    try:
                        self.firma_tablosu.setItem(row, 7, QTableWidgetItem(str(firma.get("kurucu_personel_id", "N/A"))))
                    except Exception as e:
                        logger.error(f"Kurucu ID atama hatası: {e}")
                        self.firma_tablosu.setItem(row, 7, QTableWidgetItem("ERROR"))
                    
                except Exception as row_error:
                    logger.error(f"Satır {row} işlenirken hata: {row_error}", exc_info=True)
                    continue
            
            logger.info("Firmalar başarıyla yüklendi")
            
        except Exception as e:
            logger.error(f"Firmalar yüklenirken kritik hata: {e}", exc_info=True)
            QMessageBox.critical(self, "Kritik Hata", f"Firmalar yüklenirken hata oluştu:\n\n{str(e)}\n\nLütfen terminal loglarını kontrol edin.")
    
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
            response = self.db_manager.api_put(
                f"/superadmin/{firma_id}/lisans-uzat",
                params={"gun_ekle": uzatma_gun}
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
            response = self.db_manager.api_get(f"/superadmin/{firma_id}/detay")
            
            if not response or "firma_detay" not in response:
                QMessageBox.critical(self, "Hata", "Firma detayları yüklenemedi.")
                return
            
            detay = response['firma_detay']
            detay_mesaj = f"""
Firma ID: {detay.get('id')}
Firma Adı: {detay.get('unvan')}
Firma No: {detay.get('firma_no')}
Veritabanı: {detay.get('db_adi')}

Lisans Başlangıç: {detay.get('lisans_baslangic_tarihi')}
Lisans Bitiş: {detay.get('lisans_bitis_tarihi')}
Lisans Durum: {detay.get('lisans_durum')}

Kurucu Personel ID: {detay.get('kurucu_personel_id')}
Oluşturma Tarihi: {detay.get('olusturma_tarihi')}
            """
            
            QMessageBox.information(self, "Firma Detayları", detay_mesaj)
        
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Detaylar görüntülenirken hata oluştu: {e}")

