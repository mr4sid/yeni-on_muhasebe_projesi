# raporlar.py dosyası
import traceback
import os 
from datetime import datetime, date, timedelta
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
import requests
import logging
# PySide6 importları
from PySide6.QtWidgets import (
    QDialog, QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QAbstractItemView, 
    QHeaderView, QMessageBox, QFrame, QComboBox, QLineEdit, QSizePolicy, QTabWidget, QMenu,QTableWidgetItem,QTableWidget)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QBrush, QColor, QDoubleValidator
from veritabani import OnMuhasebe
from yardimcilar import DatePickerDialog, normalize_turkish_chars, setup_locale
# pencereler.py'deki PySide6 sınıflarını import et
from pencereler import CariHesapEkstresiPenceresi, TedarikciSecimDialog, StokKartiPenceresi, SiparisPenceresi

# Logger kurulumu
logger = logging.getLogger(__name__) # Bu satırın var olduğundan emin olun
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class CriticalStockWarningPenceresi(QDialog):
    def __init__(self, critical_stocks, parent=None):
        super().__init__(parent)
        self.critical_stocks = critical_stocks
        self.setWindowTitle("Kritik Stok Seviyesi Uyarısı")
        self.setMinimumSize(600, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title_label = QLabel("Kritik Seviyedeki Ürünler", self)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        info_label = QLabel(
            "Aşağıdaki ürünlerin stok miktarı kritik seviyenin altına düşmüştür.", self
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Ürün Adı", "Mevcut Stok", "Kritik Seviye", "Durum"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

        self.populate_table()

        close_button = QPushButton("Kapat", self)
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

    def populate_table(self):
        self.table.setRowCount(len(self.critical_stocks))
        for i, stock in enumerate(self.critical_stocks):
            self.table.setItem(i, 0, QTableWidgetItem(stock.get("urun_adi")))
            self.table.setItem(
                i, 1, QTableWidgetItem(str(stock.get("mevcut_stok")))
            )
            self.table.setItem(
                i, 2, QTableWidgetItem(str(stock.get("kritik_stok")))
            )

            item_durum = QTableWidgetItem("Kritik Seviyede")
            item_durum.setForeground(QColor("red"))
            font = QFont()
            font.setBold(True)
            item_durum.setFont(font)
            self.table.setItem(i, 3, item_durum)

class Raporlama:
    def __init__(self, db_manager):
        """
        Raporlama işlevlerini yöneten sınıf.
        API ile iletişim kurmak için db_manager'ı kullanır.
        """
        self.db = db_manager
        logger.info("Raporlama sınıfı başlatıldı.")

    def rapor_olustur(self, rapor_tipi):
        """
        Belirtilen rapor tipine göre veri çeker ve raporlama işlemini başlatır.
        Bu metod, API entegrasyonu tamamlandıkça doldurulacaktır.
        """
        logger.info(f"'{rapor_tipi}' raporu oluşturma isteği alındı (placeholder).")
        # Örnek olarak, bir rapor türüne göre API'den veri çekme başlangıcı:
        try:
            if rapor_tipi == "musteri":
                # Örneğin: musteri_verileri = self.db.musteri_listesi_al()
                # Bu verilerle bir Excel veya PDF raporu oluşturulabilir.
                pass # Şimdilik sadece placeholder
            elif rapor_tipi == "stok":
                # Örneğin: stok_verileri = self.db.stok_listesi_al()
                pass # Şimdilik sadece placeholder
            # Diğer rapor tipleri için buraya mantık eklenecektir.
            return True, f"'{rapor_tipi}' raporu için placeholder işlemi başarılı."
        except Exception as e:
            logger.error(f"Rapor oluşturulurken hata: {e}")
            return False, f"Rapor oluşturulurken hata oluştu: {e}"

class NotificationDetailsPenceresi(QDialog):
    def __init__(self, bildirim, parent=None):
        super().__init__(parent)
        self.bildirim = bildirim
        # self.app = parent.app # Bu satır eğer ana uygulama referansı gerekiyorsa aktif edilebilir
        self.setWindowTitle("Bildirim Detayı")
        self.setMinimumSize(400, 300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Başlık
        title_label = QLabel(self.bildirim.get("baslik", "Başlık Yok"), self)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Mesaj
        mesaj_label = QLabel(self.bildirim.get("mesaj", "Mesaj içeriği yok."), self)
        mesaj_label.setWordWrap(True)
        layout.addWidget(mesaj_label)

        # Tarih
        tarih_str = self.bildirim.get("tarih", "")
        tarih_label = QLabel(f"Tarih: {tarih_str}", self)
        tarih_font = QFont()
        tarih_font.setItalic(True) # Italic stilini bu şekilde ayarlıyoruz
        tarih_label.setFont(tarih_font)
        tarih_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tarih_label)

        layout.addStretch()

        # Kapat Butonu
        close_button = QPushButton("Kapat", self)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)