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
    QMessageBox, QInputDialog, QComboBox, QHeaderView,
    QLineEdit
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
        self.firma_tablosu.setColumnCount(10) # Sütun sayısı 10'a çıkarıldı
        self.firma_tablosu.setHorizontalHeaderLabels([
            "ID", "Firma Adı", "Firma No", "Telefon", "Email", # Yeni sütunlar eklendi
            "Lisans Başlangıç", "Lisans Bitiş", "Kalan Gün", "Durum", "Kurucu ID" # Sıralama güncellendi
        ])
        self.firma_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.firma_tablosu.setSelectionBehavior(QTableWidget.SelectRows)
        self.firma_tablosu.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.firma_tablosu)
        
        # Filtreleme
        filtre_layout = QHBoxLayout() # Yatay layout

        # Arama kutusu
        self.arama_input = QLineEdit()
        self.arama_input.setPlaceholderText("🔍 Firma adı veya no ile ara...")
        self.arama_input.textChanged.connect(self.firmalar_filtrele) # Filtreleme fonksiyonuna bağla
        filtre_layout.addWidget(QLabel("Ara:"))
        filtre_layout.addWidget(self.arama_input)

        # Durum filtresi (ComboBox)
        self.durum_filtre = QComboBox()
        self.durum_filtre.addItems(["Tümü", "AKTIF", "DENEME", "SURESI_BITMIS", "ASKIDA"]) # Durumları ekle
        self.durum_filtre.currentTextChanged.connect(self.firmalar_filtrele) # Filtreleme fonksiyonuna bağla
        filtre_layout.addWidget(QLabel("Durum:"))
        filtre_layout.addWidget(self.durum_filtre)

        filtre_layout.addStretch() # Elemanları sola yaslamak için boşluk ekle
        layout.addLayout(filtre_layout)
        
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
        """SUPERADMIN API'sinden tüm firmaları çeker ve tabloya yükler. (Düzeltilmiş Versiyon)"""
        try:
            logger.info("Firmalar yüklenmeye başlanıyor...")
            self.firma_tablosu.setRowCount(0)

            logger.info("API'ye istek gönderiliyor: /superadmin/firmalar")
            response = self.db_manager.api_get("/superadmin/firmalar")
            logger.info(f"API yanıtı alındı: {type(response)}")

            if isinstance(response, dict) and "error" in response:
                error_msg = response.get('detail', 'Bilinmeyen API Hatası')
                logger.error(f"API hatası: {error_msg}")
                QMessageBox.warning(self, "API Hata", f"Firmalar yüklenemedi:\n{error_msg}")
                return

            if not isinstance(response, list):
                logger.error(f"Beklenmeyen veri formatı: {type(response)}")
                QMessageBox.warning(self, "Hata", "API'den beklenmeyen veri formatı.")
                return

            logger.info(f"{len(response)} firma bulundu")
            firmalar = response

            if len(firmalar) == 0:
                logger.warning("Firma listesi boş")
                QMessageBox.information(self, "Bilgi", "Hiç firma kaydı bulunamadı.")
                return

            self.firma_tablosu.setRowCount(len(firmalar))
            logger.info(f"Tablo {len(firmalar)} satıra ayarlandı")

            # Firmaları tabloya ekle
            for row, firma in enumerate(firmalar):
                try:
                    # Sütun 0: ID
                    try:
                        self.firma_tablosu.setItem(row, 0, QTableWidgetItem(str(firma.get("id", "N/A"))))
                    except Exception as e: logger.error(f"ID atama hatası: {e}"); self.firma_tablosu.setItem(row, 0, QTableWidgetItem("ERROR"))

                    # Sütun 1: Firma Adı
                    try:
                        self.firma_tablosu.setItem(row, 1, QTableWidgetItem(str(firma.get("unvan", "N/A"))))
                    except Exception as e: logger.error(f"Unvan atama hatası: {e}"); self.firma_tablosu.setItem(row, 1, QTableWidgetItem("ERROR"))

                    # Sütun 2: Firma No (DÜZELTME)
                    try:
                        firma_no_val = firma.get("firma_no") # Anahtar: firma_no
                        self.firma_tablosu.setItem(row, 2, QTableWidgetItem(str(firma_no_val) if firma_no_val else "N/A"))
                    except Exception as e: logger.error(f"Firma no atama hatası: {e}"); self.firma_tablosu.setItem(row, 2, QTableWidgetItem("ERROR"))

                    # Sütun 3: Telefon (DÜZELTME)
                    try:
                        kurucu_personel = firma.get("kurucu_personel") # İç içe nesneyi al
                        telefon_val = kurucu_personel.get("telefon") if kurucu_personel else None
                        self.firma_tablosu.setItem(row, 3, QTableWidgetItem(str(telefon_val) if telefon_val else "N/A"))
                    except Exception as e: logger.error(f"Telefon atama hatası: {e}"); self.firma_tablosu.setItem(row, 3, QTableWidgetItem("ERROR"))

                    # Sütun 4: Email (DÜZELTME)
                    try:
                        kurucu_personel = firma.get("kurucu_personel") # İç içe nesneyi al
                        email_val = kurucu_personel.get("email") if kurucu_personel else None
                        self.firma_tablosu.setItem(row, 4, QTableWidgetItem(str(email_val) if email_val else "N/A"))
                    except Exception as e: logger.error(f"Email atama hatası: {e}"); self.firma_tablosu.setItem(row, 4, QTableWidgetItem("ERROR"))

                    # Sütun 5: Lisans Başlangıç
                    try:
                        self.firma_tablosu.setItem(row, 5, QTableWidgetItem(str(firma.get("lisans_baslangic_tarihi", "N/A"))))
                    except Exception as e: logger.error(f"Lisans başlangıç atama hatası: {e}"); self.firma_tablosu.setItem(row, 5, QTableWidgetItem("ERROR"))

                    # Sütun 6: Lisans Bitiş
                    try:
                        self.firma_tablosu.setItem(row, 6, QTableWidgetItem(str(firma.get("lisans_bitis_tarihi", "N/A"))))
                    except Exception as e: logger.error(f"Lisans bitiş atama hatası: {e}"); self.firma_tablosu.setItem(row, 6, QTableWidgetItem("ERROR"))

                    # Sütun 7: Kalan Gün
                    try:
                        lisans_bitis_str = firma.get("lisans_bitis_tarihi")
                        kalan_gun = None
                        if lisans_bitis_str:
                            lisans_bitis = datetime.strptime(lisans_bitis_str, "%Y-%m-%d").date()
                            bugun = date.today()
                            kalan_gun = (lisans_bitis - bugun).days
                            kalan_gun_item = QTableWidgetItem(str(kalan_gun))
                            self.firma_tablosu.setItem(row, 7, kalan_gun_item)
                            if kalan_gun < 0: kalan_gun_item.setBackground(QColor(255, 200, 200))
                            elif kalan_gun <= 7: kalan_gun_item.setBackground(QColor(255, 255, 200))
                            else: kalan_gun_item.setBackground(QColor(200, 255, 200))
                        else:
                            self.firma_tablosu.setItem(row, 7, QTableWidgetItem("N/A"))
                    except Exception as e: logger.error(f"Kalan gün hesaplama/renklendirme hatası: {e}"); self.firma_tablosu.setItem(row, 7, QTableWidgetItem("ERROR"))

                    # Sütun 8: Durum
                    try:
                        durum = firma.get("lisans_durum", "N/A")
                        durum_item = QTableWidgetItem(durum)
                        if durum == "SURESI_BITMIS": durum_item.setBackground(QColor(255, 200, 200))
                        elif durum == "DENEME": durum_item.setBackground(QColor(255, 255, 200))
                        elif durum == "ASKIDA": durum_item.setBackground(QColor(200, 200, 200))
                        elif durum == "AKTIF": durum_item.setBackground(QColor(200, 255, 200))
                        self.firma_tablosu.setItem(row, 8, durum_item)
                    except Exception as e: logger.error(f"Durum atama/renklendirme hatası: {e}"); self.firma_tablosu.setItem(row, 8, QTableWidgetItem("ERROR"))

                    # Sütun 9: Kurucu ID (DÜZELTME)
                    try:
                        kurucu_id_val = firma.get("kurucu_personel_id") # Anahtar: kurucu_personel_id
                        self.firma_tablosu.setItem(row, 9, QTableWidgetItem(str(kurucu_id_val) if kurucu_id_val else "N/A"))
                    except Exception as e: logger.error(f"Kurucu ID atama hatası: {e}"); self.firma_tablosu.setItem(row, 9, QTableWidgetItem("ERROR"))

                except Exception as row_error:
                    logger.error(f"Satır {row} işlenirken genel hata: {row_error}", exc_info=True)
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
        """Seçili firmanın lisansını uzatır."""
        firma_id = self.secili_firma_id_al()
        if not firma_id:
            return

        gun_sayisi, ok = QInputDialog.getInt(self, "Lisans Uzat", "Kaç gün uzatmak istersiniz?", 30, 1, 3650)

        if ok:
            try:
                # HATA DÜZELTİLDİ: api_put yerine api_post kullanılıyor.
                response = self.db_manager.api_post(f"/superadmin/{firma_id}/lisans-uzat?gun_ekle={gun_sayisi}")
                QMessageBox.information(self, "Başarılı", "Lisans başarıyla uzatıldı.")
                self.firmalari_yukle()  # Listeyi yenile
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Lisans uzatma hatası: {e}")
    
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
        """Seçili firmanın detaylı bilgilerini ve istatistiklerini gösterir."""
        firma_id = self.secili_firma_id_al()
        if not firma_id:
            return

        try:
            # 1. Firma detaylarını al
            response = self.db_manager.api_get(f"/superadmin/{firma_id}/detay")

            if not response or "firma_detay" not in response:
                if isinstance(response, dict) and "detail" in response:
                    raise Exception(response.get('detail'))
                QMessageBox.critical(self, "Hata", "Firma detayları yüklenemedi.")
                return

            detay = response['firma_detay']

            # --- YENİ EKLENEN KISIM (Telefon/Email) ---
            # API'den gelen iç içe kurucu_personel nesnesini oku
            kurucu_personel_detay = detay.get('kurucu_personel')
            kurucu_telefon = "N/A"
            kurucu_email = "N/A"
            if kurucu_personel_detay: # Eğer kurucu_personel nesnesi varsa
                kurucu_telefon = kurucu_personel_detay.get('telefon', 'N/A')
                kurucu_email = kurucu_personel_detay.get('email', 'N/A')
            # --- YENİ EKLENEN KISIM SONU ---

            # 2. Firma istatistiklerini al
            try:
                istatistikler = self.db_manager.api_get(f"/superadmin/{firma_id}/istatistikler")
                if isinstance(istatistikler, dict) and "detail" in istatistikler:
                    logger.warning(f"İstatistikler alınamadı: {istatistikler.get('detail')}")
                    istatistikler = None
            except Exception as stat_error:
                logger.warning(f"İstatistikler API çağrısı sırasında hata: {stat_error}")
                istatistikler = None

            # 3. Detay mesajını oluştur (GÜNCELLENDİ)
            detay_mesaj = f"""
📊 **Firma Bilgileri:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Firma ID: {detay.get('id')}
Firma Adı: {detay.get('unvan')}
Firma No: {detay.get('firma_no')}
Veritabanı: {detay.get('db_adi')}

📅 **Lisans Bilgileri:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Başlangıç: {detay.get('lisans_baslangic_tarihi')}
Bitiş: {detay.get('lisans_bitis_tarihi')}
Durum: {detay.get('lisans_durum')}

👤 **Kurucu Bilgileri:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kurucu ID: {detay.get('kurucu_personel_id')}
Telefon: {kurucu_telefon}
Email: {kurucu_email}
Oluşturma: {detay.get('olusturma_tarihi')}
"""

            # 4. İstatistikler varsa ekle
            if istatistikler:
                detay_mesaj += f"""
📈 **İstatistikler (Tenant DB):**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fatura Sayısı: {istatistikler.get('fatura_sayisi', 0)}
Müşteri Sayısı: {istatistikler.get('musteri_sayisi', 0)}
Stok Sayısı: {istatistikler.get('stok_sayisi', 0)}
Toplam Ciro: {istatistikler.get('toplam_ciro', 0):.2f} TL
"""
            else:
                detay_mesaj += f"""
📈 **İstatistikler (Tenant DB):**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
İstatistikler alınamadı veya hesaplanamadı.
(Tenant DB bağlantısını veya logları kontrol edin)
"""

            # QMessageBox'u zengin metin (Rich Text) kabul edecek şekilde ayarla
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Firma Detayları")
            msg_box.setTextFormat(Qt.RichText) # Zengin metin formatını etkinleştir
            msg_box.setText(detay_mesaj.replace("\n", "<br>")) # Yeni satırları <br> ile değiştir
            msg_box.setIcon(QMessageBox.Information)
            msg_box.exec()

        except Exception as e:
            logger.error(f"Detay görüntüleme hatası: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"Detaylar görüntülenirken hata oluştu: {e}")

    def firmalar_filtrele(self):
        """Arama kutusu ve durum filtresine göre firma tablosundaki satırları gizler/gösterir."""
        arama_text = self.arama_input.text().lower().strip()
        durum_filtre = self.durum_filtre.currentText()

        logger.debug(f"Filtreleme tetiklendi: Arama='{arama_text}', Durum='{durum_filtre}'")

        for row in range(self.firma_tablosu.rowCount()):
            # Firma adı (sütun 1) ve durum (sütun 6) bilgilerini al
            firma_adi_item = self.firma_tablosu.item(row, 1)
            durum_item = self.firma_tablosu.item(row, 8)
            firma_no_item = self.firma_tablosu.item(row, 2) # Firma no (sütun 2) eklendi

            # Eğer hücreler (item) henüz oluşturulmadıysa veya boşsa, bu satırı atla
            if not firma_adi_item or not durum_item or not firma_no_item:
                logger.warning(f"Satır {row} için hücre bilgisi eksik, filtreleme atlanıyor.")
                continue

            firma_adi = firma_adi_item.text().lower()
            durum = durum_item.text()
            firma_no = firma_no_item.text().lower() # Firma no'yu da küçük harfe çevir

            # Filtreleme mantığı
            goster = True # Varsayılan olarak göster

            # Arama filtresi (Firma adı VEYA Firma no içinde geçiyorsa göster)
            if arama_text and not (arama_text in firma_adi or arama_text in firma_no):
                goster = False

            # Durum filtresi ("Tümü" seçili değilse ve durum eşleşmiyorsa gizle)
            if durum_filtre != "Tümü" and durum != durum_filtre:
                goster = False
            
            # Satırı gizle/göster
            self.firma_tablosu.setRowHidden(row, not goster)
        logger.debug("Filtreleme tamamlandı.")