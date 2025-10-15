#arayuz.py dosyası içeriğinin Tamamım, şu şekildedir lütfen çok dikkatli bir şekilde incele.
import os
import logging
import traceback
import multiprocessing
import threading
import time
from datetime import datetime, date, timedelta

# PySide6 modülleri
from PySide6.QtWidgets import (QApplication,
    QWidget,QDialog, QLabel, QPushButton, QTabWidget, QMessageBox,
    QGridLayout, QVBoxLayout, QHBoxLayout, QFrame,
    QLineEdit, QMainWindow, QFileDialog, QComboBox, QTreeWidget, QTreeWidgetItem, QAbstractItemView,
    QHeaderView, QTextEdit, QGroupBox, QMenu, QTableWidgetItem, QCheckBox, QListWidget, QListWidgetItem)

from PySide6.QtCore import Qt, QTimer, Signal, QLocale
from PySide6.QtGui import QIcon, QPixmap, QFont, QBrush, QColor, QDoubleValidator # QBrush, QColor, QDoubleValidator eklendi
# Üçüncü Parti Kütüphaneler (PySide6 ile uyumlu olanlar kalır)
import openpyxl
from PIL import Image
# Matplotlib importları (PySide6 ile entegrasyon için)
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas # PySide6 (Qt) için Matplotlib Canvas
from matplotlib.figure import Figure

# Yerel Uygulama Modülleri
from veritabani import OnMuhasebe
from hizmetler import lokal_db_servisi # Değiştirilen satır
from pencereler import StokKartiPenceresi, KullaniciKayitPenceresi
from yardimcilar import DatePickerDialog, normalize_turkish_chars, setup_locale, format_and_validate_numeric_input
from datetime import datetime
import requests
import locale
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFrame, QVBoxLayout,
    QHBoxLayout, QGridLayout, QSizePolicy )
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from api.modeller import (Stok, Musteri, Fatura, Tedarikci, FaturaKalemi,
                           StokHareket, CariHareket, Siparis, SiparisKalemi,
                           UrunKategori, UrunGrubu, UrunBirimi, UrunMarka, KasaBankaHesap, Ulke)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# arayuz.py dosyasında, setup_numeric_entry fonksiyonunun TAMAMI
def setup_numeric_entry(parent_app, entry_widget, allow_negative=False, decimal_places=2, max_value=None):
    validator = QDoubleValidator()

    # Yerel ayarı QLocale nesnesiyle ayarla
    current_locale = QLocale(locale.getlocale()[0])
    validator.setLocale(current_locale)

    validator.setBottom(0.0 if not allow_negative else -999999999.0)
    validator.setTop(999999999999.0 if max_value is None else float(max_value))
    validator.setDecimals(decimal_places)
    validator.setNotation(QDoubleValidator.StandardNotation)
    entry_widget.setValidator(validator)

    # SADECE ODAK KAYBINDA VEYA ENTER TUŞUNA BASILDIĞINDA FORMATLAMA YAP
    # Bu, kullanıcının serbestçe karakterleri silmesine olanak tanır.
    entry_widget.editingFinished.connect(lambda: format_and_validate_numeric_input(entry_widget, parent_app))

    # Başlangıçta 0'dan farklı bir değer varsa, onu formatla
    if entry_widget.text() and entry_widget.text().strip() != "0,00":
        format_and_validate_numeric_input(entry_widget, parent_app)

# AnaSayfa Sınıfının Tamamı
class AnaSayfa(QWidget):
    def __init__(self, parent_window, db_manager, app_ref):
        super().__init__(parent_window)
        self.app = app_ref
        self.db = db_manager
        self.main_layout = QVBoxLayout(self)

        self.title_label = QLabel("Çınar Yapı Ön Muhasebe Programı - Genel Bakış")
        self.title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.main_layout.addWidget(self.title_label, alignment=Qt.AlignCenter)

        self.ozet_bilgiler_frame = QFrame(self)
        self.ozet_bilgiler_layout = QHBoxLayout(self.ozet_bilgiler_frame)
        self.main_layout.addWidget(self.ozet_bilgiler_frame)

        self.ozet_satislar_group = QGroupBox("Toplam Satışlar")
        self.lbl_toplam_satis_degeri = QLabel("0,00 TL")
        self.lbl_toplam_satis_degeri.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.ozet_satislar_group.setLayout(QVBoxLayout())
        self.ozet_satislar_group.layout().addWidget(self.lbl_toplam_satis_degeri, alignment=Qt.AlignCenter)
        self.ozet_bilgiler_layout.addWidget(self.ozet_satislar_group)

        self.ozet_alislar_group = QGroupBox("Toplam Alışlar")
        self.lbl_toplam_alis_degeri = QLabel("0,00 TL")
        self.lbl_toplam_alis_degeri.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.ozet_alislar_group.setLayout(QVBoxLayout())
        self.ozet_alislar_group.layout().addWidget(self.lbl_toplam_alis_degeri, alignment=Qt.AlignCenter)
        self.ozet_bilgiler_layout.addWidget(self.ozet_alislar_group)

        self.ozet_tahsilatlar_group = QGroupBox("Toplam Tahsilatlar")
        self.lbl_toplam_tahsilat_degeri = QLabel("0,00 TL")
        self.lbl_toplam_tahsilat_degeri.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.ozet_tahsilatlar_group.setLayout(QVBoxLayout())
        self.ozet_tahsilatlar_group.layout().addWidget(self.lbl_toplam_tahsilat_degeri, alignment=Qt.AlignCenter)
        self.ozet_bilgiler_layout.addWidget(self.ozet_tahsilatlar_group)

        self.ozet_odemeler_group = QGroupBox("Toplam Ödemeler")
        self.lbl_toplam_odeme_degeri = QLabel("0,00 TL")
        self.lbl_toplam_odeme_degeri.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.ozet_odemeler_group.setLayout(QVBoxLayout())
        self.ozet_odemeler_group.layout().addWidget(self.lbl_toplam_odeme_degeri, alignment=Qt.AlignCenter)
        self.ozet_bilgiler_layout.addWidget(self.ozet_odemeler_group)

        self.ozet_kritik_stok_group = QGroupBox("Kritik Stok")
        self.lbl_kritik_stok_sayisi = QLabel("0")
        self.lbl_kritik_stok_sayisi.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.ozet_kritik_stok_group.setLayout(QVBoxLayout())
        self.ozet_kritik_stok_group.layout().addWidget(self.lbl_kritik_stok_sayisi, alignment=Qt.AlignCenter)
        self.ozet_bilgiler_layout.addWidget(self.ozet_kritik_stok_group)
        self.main_layout.addSpacing(20)

        self.hizli_menuler_frame = QFrame(self)
        self.hizli_menuler_layout = QGridLayout(self.hizli_menuler_frame)
        self.main_layout.addWidget(self.hizli_menuler_frame)
        self.main_layout.addStretch()

        button_style = "QPushButton { padding: 25px; font-size: 14pt; border-radius: 10px; border: 1px solid #ccc; background-color: #fdfdfd; } QPushButton:hover { background-color: #e6e6e6; border: 1px solid #aaa; }"
        
        btn_yeni_satis_faturasi = QPushButton("📝 Yeni Satış Faturası")
        btn_yeni_satis_faturasi.setStyleSheet(button_style)
        btn_yeni_satis_faturasi.clicked.connect(lambda: self.app.fatura_listesi_sayfasi.yeni_fatura_ekle_ui(self.db.FATURA_TIP_SATIS))
        self.hizli_menuler_layout.addWidget(btn_yeni_satis_faturasi, 0, 0)
        
        btn_yeni_alis_faturasi = QPushButton("🛒 Yeni Alış Faturası")
        btn_yeni_alis_faturasi.setStyleSheet(button_style)
        btn_yeni_alis_faturasi.clicked.connect(lambda: self.app.fatura_listesi_sayfasi.yeni_fatura_ekle_ui(self.db.FATURA_TIP_ALIS))
        self.hizli_menuler_layout.addWidget(btn_yeni_alis_faturasi, 0, 1)

        btn_faturalar = QPushButton("🧾 Faturalar")
        btn_faturalar.setStyleSheet(button_style)
        btn_faturalar.clicked.connect(lambda: self.app.show_tab("Faturalar"))
        self.hizli_menuler_layout.addWidget(btn_faturalar, 0, 2)
        
        btn_kasa_banka_yonetimi = QPushButton("🏦 Kasa/Banka Yönetimi")
        btn_kasa_banka_yonetimi.setStyleSheet(button_style)
        btn_kasa_banka_yonetimi.clicked.connect(lambda: self.app.show_tab("Kasa/Banka"))
        self.hizli_menuler_layout.addWidget(btn_kasa_banka_yonetimi, 1, 0)
        
        btn_musteri_yonetimi = QPushButton("👥 Müşteri Yönetimi")
        btn_musteri_yonetimi.setStyleSheet(button_style)
        btn_musteri_yonetimi.clicked.connect(lambda: self.app.show_tab("Müşteri Yönetimi"))
        self.hizli_menuler_layout.addWidget(btn_musteri_yonetimi, 1, 1)
        
        btn_tedarikci_yonetimi = QPushButton("🚚 Tedarikçi Yönetimi")
        btn_tedarikci_yonetimi.setStyleSheet(button_style)
        btn_tedarikci_yonetimi.clicked.connect(lambda: self.app.show_tab("Tedarikçi Yönetimi"))
        self.hizli_menuler_layout.addWidget(btn_tedarikci_yonetimi, 1, 2)

        self.hizli_menuler_layout.setColumnStretch(0, 1)
        self.hizli_menuler_layout.setColumnStretch(1, 1)
        self.hizli_menuler_layout.setColumnStretch(2, 1)

        self.aylik_grafik_frame = QFrame(self)
        self.aylik_grafik_layout = QVBoxLayout(self.aylik_grafik_frame)
        self.main_layout.addWidget(self.aylik_grafik_frame)
        self.aylik_grafik_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.en_cok_satanlar_frame = QFrame(self)
        self.en_cok_satanlar_layout = QVBoxLayout(self.en_cok_satanlar_frame)
        self.main_layout.addWidget(self.en_cok_satanlar_frame)

        self.en_cok_satanlar_label = QLabel("En Çok Satan Ürünler")
        self.en_cok_satanlar_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.en_cok_satanlar_layout.addWidget(self.en_cok_satanlar_label)

        self.en_cok_satanlar_list = QListWidget(self.en_cok_satanlar_frame)
        self.en_cok_satanlar_layout.addWidget(self.en_cok_satanlar_list)

        self.aylik_grafik_figure = Figure()
        self.aylik_grafik_canvas = FigureCanvas(self.aylik_grafik_figure)
        self.aylik_grafik_layout.addWidget(self.aylik_grafik_canvas)
        
        self.guncelle_ozet_bilgiler()

    def closeEvent(self, event):
        """
        Pencere kapatılmaya çalışıldığında bu fonksiyon otomatik olarak çağrılır.
        Kullanıcıya bir onay penceresi gösterir.
        """
        yanit = QMessageBox.question(self, 
                                     'Çıkışı Onayla', 
                                     "Programı kapatmak istediğinizden emin misiniz?", 
                                     QMessageBox.Yes | QMessageBox.No, 
                                     QMessageBox.No)

        if yanit == QMessageBox.Yes:
            # Kullanıcı "Evet" derse, kapatma olayını kabul et ve programı kapat.
            event.accept()
        else:
            # Kullanıcı "Hayır" derse, kapatma olayını yoksay ve pencereyi açık tut.
            event.ignore()

    def _create_metric_card(self, parent_frame, title, initial_value, card_type):
        card_frame = QFrame(parent_frame)
        card_frame.setFrameShape(QFrame.StyledPanel)
        card_frame.setFrameShadow(QFrame.Raised)
        card_frame.setLineWidth(2)
        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title_label)

        value_label = QLabel(initial_value)
        value_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        value_label.setStyleSheet("color: navy;")
        value_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(value_label)

        setattr(self, f"lbl_metric_{card_type}", value_label)
        return card_frame

    def guncelle_sirket_adi(self):
        sirket_adi = "Şirket Adı (API'den Gelecek)"
        self.sirket_adi_label.setText(f"Hoş Geldiniz, {sirket_adi}")

    def guncelle_ozet_bilgiler(self):
        try:
            baslangic_tarihi = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            bitis_tarihi = datetime.now().strftime('%Y-%m-%d')
            
            ozet_data = self.db.get_dashboard_summary(
                baslangic_tarihi=baslangic_tarihi,
                bitis_tarihi=bitis_tarihi
            )
            
            if ozet_data:
                self.lbl_toplam_satis_degeri.setText(self.db._format_currency(ozet_data.get('toplam_satislar', 0.0)))
                self.lbl_toplam_alis_degeri.setText(self.db._format_currency(ozet_data.get('toplam_alislar', 0.0)))
                self.lbl_toplam_tahsilat_degeri.setText(self.db._format_currency(ozet_data.get('toplam_tahsilatlar', 0.0)))
                self.lbl_toplam_odeme_degeri.setText(self.db._format_currency(ozet_data.get('toplam_odemeler', 0.0)))
                self.lbl_kritik_stok_sayisi.setText(str(ozet_data.get('kritik_stok_sayisi', 0)))
                
                self.en_cok_satanlar_list.clear()
                for urun in ozet_data.get('en_cok_satan_urunler', []):
                    self.en_cok_satanlar_list.addItem(f"{urun.get('ad', '-')}")
                
                self.ciz_aylik_satis_alıs_grafik()

        except Exception as e:
            QMessageBox.critical(self.app, "API Hatası", f"Dashboard özeti yüklenirken hata: {e}")
            logger.error(f"Dashboard özeti yüklenirken hata: {e}")

    def ciz_aylik_satis_alıs_grafik(self):
        """Aylık satış ve alış grafiklerini çizer."""
        try:
            fig = self.aylik_grafik_canvas.figure
            fig.clear()
            ax = fig.add_subplot(111)

            simdi = datetime.now()
            gecmis_bir_yil = simdi - timedelta(days=365)
            
            aylik_satis_ozeti = self.db.get_monthly_sales_summary(
                baslangic_tarihi=gecmis_bir_yil.strftime('%Y-%m-%d'),
                bitis_tarihi=simdi.strftime('%Y-%m-%d')
            )
            
            if not isinstance(aylik_satis_ozeti, list):
                aylik_satis_ozeti = []
            
            aylar = [item.get('ay_adi', '-') for item in aylik_satis_ozeti]
            satislar = [item.get('toplam_satis', 0) for item in aylik_satis_ozeti]
            alislar = [item.get('toplam_alis', 0) for item in aylik_satis_ozeti]
            
            if not aylar:
                ax.text(0.5, 0.5, "Grafik verisi bulunamadı.", horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=12)
            else:
                x = np.arange(len(aylar))
                width = 0.35
                
                rects1 = ax.bar(x - width/2, satislar, width, label='Satış', color='green')
                rects2 = ax.bar(x + width/2, alislar, width, label='Alış', color='red')

                ax.set_ylabel('Tutar (TL)')
                ax.set_title('Aylık Satış ve Alış Özeti')
                ax.set_xticks(x)
                ax.set_xticklabels(aylar, rotation=45, ha="right")
                ax.legend()
                
                def autolabel(rects):
                    for rect in rects:
                        height = rect.get_height()
                        if height > 0:
                            ax.annotate(f'{height:,.0f}',
                                        xy=(rect.get_x() + rect.get_width() / 2, height),
                                        xytext=(0, 3),
                                        textcoords="offset points",
                                        ha='center', va='bottom', fontsize=8)

                autolabel(rects1)
                autolabel(rects2)

            fig.tight_layout()
            self.aylik_grafik_canvas.draw()
            
        except Exception as e:
            logger.error(f"Aylık satış/alış grafiği çizilirken hata: {e}", exc_info=True)
            self.app.set_status_message(f"Aylık grafik çizilirken hata: {e}", "red")

class FinansalIslemlerSayfasi(QWidget): 
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.setLayout(QVBoxLayout(self)) # Ana layout QVBoxLayout

        self.layout().addWidget(QLabel("Finansal İşlemler (Tahsilat / Ödeme)", 
                                       font=QFont("Segoe UI", 16, QFont.Bold)))

        # Finansal işlemler için ana QTabWidget (Tahsilat ve Ödeme sekmeleri için)
        self.main_tab_widget = QTabWidget(self)
        self.layout().addWidget(self.main_tab_widget)

        # Tahsilat Sekmesi (Placeholder - Daha sonra gerçek içeriği eklenecek)
        self.tahsilat_frame = TahsilatSayfasi(self.main_tab_widget, self.db, self.app)
        self.main_tab_widget.addTab(self.tahsilat_frame, "💰 Tahsilat Girişi")

        # Ödeme Sekmesi (Placeholder - Daha sonra gerçek içeriği eklenecek)
        self.odeme_frame = OdemeSayfasi(self.main_tab_widget, self.db, self.app)
        self.main_tab_widget.addTab(self.odeme_frame, "💸 Ödeme Girişi")
        
        # Sekme değiştiğinde ilgili formu yenilemek için bir olay bağlayabiliriz
        self.main_tab_widget.currentChanged.connect(self._on_tab_change)

    def _on_tab_change(self, index):
        selected_widget = self.main_tab_widget.widget(index)
        selected_tab_text = self.main_tab_widget.tabText(index)

        # Bu kısım, TahsilatSayfasi ve OdemeSayfasi PySide6'ya dönüştürüldüğünde etkinleşecektir.
        # Şimdilik placeholder metotları çağırıyoruz.
        if selected_tab_text == "💰 Tahsilat Girişi":
            if hasattr(self.tahsilat_frame, '_yukle_ve_cachele_carileri'):
                self.tahsilat_frame._yukle_ve_cachele_carileri()
            if hasattr(self.tahsilat_frame, '_yukle_kasa_banka_hesaplarini'):
                self.tahsilat_frame._yukle_kasa_banka_hesaplarini()
            if hasattr(self.tahsilat_frame, 'tarih_entry'): # QLineEdit için
                self.tahsilat_frame.tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
            if hasattr(self.tahsilat_frame, 'tutar_entry'): # QLineEdit için
                self.tahsilat_frame.tutar_entry.setText("")
            if hasattr(self.tahsilat_frame, 'odeme_sekli_combo'): # QComboBox için
                self.tahsilat_frame.odeme_sekli_combo.setCurrentText(self.db.ODEME_TURU_NAKIT)
            if hasattr(self.tahsilat_frame, '_odeme_sekli_degisince'):
                self.tahsilat_frame._odeme_sekli_degisince()

        elif selected_tab_text == "💸 Ödeme Girişi":
            if hasattr(self.odeme_frame, '_yukle_ve_cachele_carileri'):
                self.odeme_frame._yukle_ve_cachele_carileri()
            if hasattr(self.odeme_frame, '_yukle_kasa_banka_hesaplarini'):
                self.odeme_frame._yukle_kasa_banka_hesaplarini()
            if hasattr(self.odeme_frame, 'tarih_entry'): # QLineEdit için
                self.odeme_frame.tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
            if hasattr(self.odeme_frame, 'tutar_entry'): # QLineEdit için
                self.odeme_frame.tutar_entry.setText("")
            if hasattr(self.odeme_frame, 'odeme_sekli_combo'): # QComboBox için
                self.odeme_frame.odeme_sekli_combo.setCurrentText(self.db.ODEME_TURU_NAKIT)
            if hasattr(self.odeme_frame, '_odeme_sekli_degisince'):
                self.odeme_frame._odeme_sekli_degisince()

class StokYonetimiSayfasi(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref       
        self.current_user = getattr(self.app, 'current_user', {})
        self.main_layout = QGridLayout(self)
        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)
        self.kayit_sayisi_per_sayfa = 50
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0
        self.total_pages = 1
        
        title_label = QLabel("STOK YÖNETİM SİSTEMİ")
        title_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.main_layout.addWidget(title_label, 0, 0, 1, 1, Qt.AlignCenter | Qt.AlignTop)
        
        top_filter_and_action_frame = QFrame(self)
        top_filter_and_action_layout = QGridLayout(top_filter_and_action_frame)
        self.main_layout.addWidget(top_filter_and_action_frame, 1, 0, 1, 1)
        top_filter_and_action_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_filter_and_action_layout.setColumnStretch(1, 1)
        
        row_idx = 0
        top_filter_and_action_layout.addWidget(QLabel("Ürün Kodu/Adı:"), row_idx, 0, Qt.AlignCenter)
        self.arama_entry = QLineEdit()
        self.arama_entry.setPlaceholderText("Ürün Kodu veya Adı ile ara...")
        self.arama_entry.textChanged.connect(self._delayed_stok_yenile)
        top_filter_and_action_layout.addWidget(self.arama_entry, row_idx, 1)
        
        top_filter_and_action_layout.addWidget(QLabel("Kategori:"), row_idx, 2, Qt.AlignCenter)
        self.kategori_filter_cb = QComboBox()
        self.kategori_filter_cb.currentIndexChanged.connect(self.stok_listesini_yenile)
        top_filter_and_action_layout.addWidget(self.kategori_filter_cb, row_idx, 3)
        
        top_filter_and_action_layout.addWidget(QLabel("Marka:"), row_idx, 4, Qt.AlignCenter)
        self.marka_filter_cb = QComboBox()
        self.marka_filter_cb.currentIndexChanged.connect(self.stok_listesini_yenile)
        top_filter_and_action_layout.addWidget(self.marka_filter_cb, row_idx, 5)
        
        top_filter_and_action_layout.addWidget(QLabel("Ürün Grubu:"), row_idx, 6, Qt.AlignCenter)
        self.urun_grubu_filter_cb = QComboBox()
        self.urun_grubu_filter_cb.currentIndexChanged.connect(self.stok_listesini_yenile)
        top_filter_and_action_layout.addWidget(self.urun_grubu_filter_cb, row_idx, 7)
        
        row_idx += 1
        top_filter_and_action_layout.addWidget(QLabel("Stok Durumu:"), row_idx, 0, Qt.AlignCenter)
        self.stok_durumu_comboBox = QComboBox()
        self.stok_durumu_comboBox.addItems(["Tümü", "Stokta Var", "Stokta Yok"])
        self.stok_durumu_comboBox.currentIndexChanged.connect(self.stok_listesini_yenile)
        top_filter_and_action_layout.addWidget(self.stok_durumu_comboBox, row_idx, 1)
        
        self.kritik_stok_altinda_checkBox = QCheckBox("Kritik Stok Altındaki Ürünler")
        self.kritik_stok_altinda_checkBox.setChecked(False)
        self.kritik_stok_altinda_checkBox.stateChanged.connect(self.stok_listesini_yenile)
        top_filter_and_action_layout.addWidget(self.kritik_stok_altinda_checkBox, row_idx, 2, 1, 2)
        
        self.aktif_urun_checkBox = QCheckBox("Aktif Ürünler")
        self.aktif_urun_checkBox.setChecked(True)
        self.aktif_urun_checkBox.stateChanged.connect(self.stok_listesini_yenile)
        top_filter_and_action_layout.addWidget(self.aktif_urun_checkBox, row_idx, 4, 1, 2)
        
        sorgula_button = QPushButton("Sorgula")
        sorgula_button.clicked.connect(self.stok_listesini_yenile)
        top_filter_and_action_layout.addWidget(sorgula_button, row_idx, 8)
        
        temizle_button = QPushButton("Temizle")
        temizle_button.clicked.connect(self._filtreleri_temizle)
        top_filter_and_action_layout.addWidget(temizle_button, row_idx, 9)
        
        summary_info_frame = QFrame(self)
        summary_info_layout = QGridLayout(summary_info_frame)
        self.main_layout.addWidget(summary_info_frame, 2, 0, 1, 1)
        summary_info_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        summary_info_layout.setColumnStretch(0,1); summary_info_layout.setColumnStretch(1,1);
        summary_info_layout.setColumnStretch(2,1); summary_info_layout.setColumnStretch(3,1)
        font_summary = QFont("Segoe UI", 10, QFont.Bold)
        
        self.lbl_toplam_listelenen_urun = QLabel("Toplam Listelenen Ürün: 0 adet")
        self.lbl_toplam_listelenen_urun.setFont(font_summary)
        summary_info_layout.addWidget(self.lbl_toplam_listelenen_urun, 0, 0, Qt.AlignCenter)
        
        self.lbl_stoktaki_toplam_urun = QLabel("Stoktaki Toplam Ürün Miktarı: 0.00")
        self.lbl_stoktaki_toplam_urun.setFont(font_summary)
        summary_info_layout.addWidget(self.lbl_stoktaki_toplam_urun, 0, 1, Qt.AlignCenter)
        
        self.lbl_toplam_maliyet = QLabel("Listelenen Ürünlerin Toplam Maliyeti: 0.00 TL")
        self.lbl_toplam_maliyet.setFont(font_summary)
        summary_info_layout.addWidget(self.lbl_toplam_maliyet, 0, 2, Qt.AlignCenter)
        
        self.lbl_toplam_satis_tutari = QLabel("Listelenen Ürünlerin Toplam Satış Tutarı: 0.00 TL")
        self.lbl_toplam_satis_tutari.setFont(font_summary)
        summary_info_layout.addWidget(self.lbl_toplam_satis_tutari, 0, 3, Qt.AlignCenter)
        
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        self.main_layout.addWidget(button_frame, 3, 0, 1, 1)
        
        self.yeni_urun_ekle_button = QPushButton("Yeni Ürün Ekle")
        self.yeni_urun_ekle_button.clicked.connect(self.yeni_urun_ekle_penceresi)
        button_layout.addWidget(self.yeni_urun_ekle_button)
        
        self.secili_urun_duzenle_button = QPushButton("Seçili Ürünü Düzenle")
        self.secili_urun_duzenle_button.clicked.connect(self.secili_urun_duzenle)
        button_layout.addWidget(self.secili_urun_duzenle_button)
        
        self.secili_urun_sil_button = QPushButton("Seçili Ürünü Sil")
        self.secili_urun_sil_button.clicked.connect(self.secili_urun_sil)
        button_layout.addWidget(self.secili_urun_sil_button)
        
        kritik_stok_uyarisi_button = QPushButton("Kritik Stok Uyarısı")
        # kritik_stok_uyarisi_button.clicked.connect(self.app.show_critical_stock_warning)
        button_layout.addWidget(kritik_stok_uyarisi_button)
        
        tree_frame = QFrame(self)
        tree_layout = QVBoxLayout(tree_frame)
        self.main_layout.addWidget(tree_frame, 4, 0, 1, 1)
        tree_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        cols = ("ID", "Ürün Kodu", "Ürün Adı", "Miktar", "Satış Fiyatı (KDV Dahil)", "KDV %", "Min. Stok")
        self.tree_stok = QTreeWidget(tree_frame)
        self.tree_stok.setHeaderLabels(cols)
        
        font_header = QFont("Segoe UI", 12, QFont.Bold)
        for i in range(self.tree_stok.columnCount()):
            self.tree_stok.headerItem().setTextAlignment(i, Qt.AlignCenter)
            self.tree_stok.headerItem().setFont(i, font_header)

        self.tree_stok.header().setSectionResizeMode(QHeaderView.Interactive)
        self.tree_stok.header().setStretchLastSection(False)
        self.tree_stok.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree_stok.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.tree_stok.setColumnWidth(1, 150)
        self.tree_stok.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tree_stok.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tree_stok.header().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tree_stok.header().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.tree_stok.header().setSectionResizeMode(6, QHeaderView.ResizeToContents)

        self.tree_stok.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_stok.setSortingEnabled(True)
        
        tree_layout.addWidget(self.tree_stok)
        
        pagination_frame = QFrame(self)
        pagination_layout = QHBoxLayout(pagination_frame)
        self.main_layout.addWidget(pagination_frame, 5, 0, 1, 1)

        self.onceki_sayfa_button = QPushButton("Önceki Sayfa")
        self.onceki_sayfa_button.clicked.connect(self.onceki_sayfa)
        pagination_layout.addWidget(self.onceki_sayfa_button)
        
        self.sayfa_bilgisi_label = QLabel(f"Sayfa {self.mevcut_sayfa} / {self.total_pages}")
        pagination_layout.addWidget(self.sayfa_bilgisi_label)
        
        self.sonraki_sayfa_button = QPushButton("Sonraki Sayfa")
        self.sonraki_sayfa_button.clicked.connect(self.sonraki_sayfa)
        pagination_layout.addWidget(self.sonraki_sayfa_button)
        
        self.tree_stok.itemDoubleClicked.connect(self.secili_urun_duzenle)
        self._yukle_filtre_comboboxlari()
        self.stok_listesini_yenile()
        self._yetkileri_uygula()

    def _yukle_filtre_comboboxlari(self):
        """Kategori, Marka ve diğer filtre combobox'larını doldurur."""
        try:
            self.kategori_filter_cb.clear()
            self.marka_filter_cb.clear()
            self.urun_grubu_filter_cb.clear()

            self.kategori_filter_cb.addItem("Tümü", None)
            self.marka_filter_cb.addItem("Tümü", None)
            self.urun_grubu_filter_cb.addItem("Tümü", None)
            
            # API'den kategorileri çek
            try:
                kategoriler_response = self.db.kategori_listele(limit=1000)
                if isinstance(kategoriler_response, dict):
                    kategoriler = kategoriler_response.get("items", [])
                elif isinstance(kategoriler_response, list):
                    kategoriler = kategoriler_response
                else:
                    kategoriler = []
                
                for k in sorted(kategoriler, key=lambda x: x.get('ad', '')):
                    self.kategori_filter_cb.addItem(k.get('ad'), k.get('id'))
            except Exception as e:
                logger.error(f"Kategori filtre combobox yüklenirken hata: {e}", exc_info=True)
                self.app.set_status_message(f"Hata: Kategori filtreleri yüklenemedi. {e}", "red")

            # API'den markaları çek
            try:
                markalar_response = self.db.marka_listele(limit=1000)
                if isinstance(markalar_response, dict):
                    markalar = markalar_response.get("items", [])
                elif isinstance(markalar_response, list):
                    markalar = markalar_response
                else:
                    markalar = []
                
                for m in sorted(markalar, key=lambda x: x.get('ad', '')):
                    self.marka_filter_cb.addItem(m.get('ad'), m.get('id'))
            except Exception as e:
                logger.error(f"Marka filtre combobox yüklenirken hata: {e}", exc_info=True)
                self.app.set_status_message(f"Hata: Marka filtreleri yüklenemedi. {e}", "red")

            # API'den ürün gruplarını çek
            try:
                urun_gruplari_response = self.db.urun_grubu_listele(limit=1000)
                if isinstance(urun_gruplari_response, dict):
                    urun_gruplari = urun_gruplari_response.get("items", [])
                elif isinstance(urun_gruplari_response, list):
                    urun_gruplari = urun_gruplari_response
                else:
                    urun_gruplari = []
                
                for g in sorted(urun_gruplari, key=lambda x: x.get('ad', '')):
                    self.urun_grubu_filter_cb.addItem(g.get('ad'), g.get('id'))
            except Exception as e:
                logger.error(f"Ürün grubu filtre combobox yüklenirken hata: {e}", exc_info=True)
                self.app.set_status_message(f"Hata: Ürün grubu filtreleri yüklenemedi. {e}", "red")

        except Exception as e:
            logger.error(f"Stok filtre comboboxları yüklenirken genel hata: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Stok filtreleri yüklenemedi. {e}", "red")
            
    def _filtreleri_temizle(self):
        self.arama_entry.clear()
        self.kategori_filter_cb.setCurrentText("TÜMÜ")
        self.marka_filter_cb.setCurrentText("TÜMÜ")
        self.stok_listesini_yenile()
        self.arama_entry.setFocus()

    def _delayed_stok_yenile(self):
        if self.after_timer.isActive(): self.after_timer.stop()
        self.after_timer.singleShot(300, self.stok_listesini_yenile)

    def stok_listesini_yenile(self):
        self.tree_stok.clear()
        try:
            stok_listesi_response = self.db.stok_listesi_al(
                arama=self.arama_entry.text(),
                aktif_durum=self.aktif_urun_checkBox.isChecked(),
                kritik_stok_altinda=self.kritik_stok_altinda_checkBox.isChecked(),
                kategori_id=self.kategori_filter_cb.currentData(),
                marka_id=self.marka_filter_cb.currentData(),
                urun_grubu_id=self.urun_grubu_filter_cb.currentData()
            )
            
            if not isinstance(stok_listesi_response, dict) or "items" not in stok_listesi_response:
                raise ValueError("API'den geçersiz stok listesi yanıtı alındı.")
            
            stok_listesi = stok_listesi_response["items"]
            
            for stok_item in stok_listesi:
                item = QTreeWidgetItem(self.tree_stok)
                item.setData(0, Qt.UserRole, stok_item.get('id', -1))
                item.setText(0, str(stok_item.get('id', '')))
                item.setText(1, stok_item.get('kod', ''))
                item.setText(2, stok_item.get('ad', ''))
                item.setText(3, self.db._format_numeric(stok_item.get('miktar', 0), 2))
                item.setText(4, self.db._format_currency(stok_item.get('satis_fiyati', 0.0)))
                item.setText(5, f"%{stok_item.get('kdv_orani', 0):.0f}")
                item.setText(6, self.db._format_numeric(stok_item.get('min_stok_seviyesi', 0), 2))
                
                if stok_item.get('miktar', 0) <= stok_item.get('min_stok_seviyesi', 0):
                    for i in range(7):
                        item.setBackground(i, QBrush(QColor("#FFCDD2")))
                
                if not stok_item.get('aktif', True):
                    for i in range(7):
                        item.setForeground(i, QBrush(QColor("gray")))
                
                self.tree_stok.addTopLevelItem(item)

            self.app.set_status_message(f"{len(stok_listesi)} stok kartı listelendi.", "blue")

        except Exception as e:
            QMessageBox.critical(self.app, "API Hatası", f"Stok listesi çekilirken hata: {e}")
            logging.error(f"Stok listesi yükleme hatası: {e}", exc_info=True)

    def _doldur_stok_tree(self, stok_listesi):
        """Mevcut stok listesini QTreeWidget'a doldurur ve biçimlendirir."""
        self.tree_stok.clear()
        
        font_item = QFont("Segoe UI", 12)
        
        for item in stok_listesi:
            item_qt = QTreeWidgetItem(self.tree_stok)
            
            item_qt.setData(0, Qt.UserRole, item.id)
            
            if item.miktar <= item.min_stok_seviyesi:
                for col in range(self.tree_stok.columnCount()):
                    item_qt.setBackground(col, QBrush(QColor("#ffcdd2")))
                    
            item_qt.setText(0, str(item.id))
            item_qt.setText(1, item.kod)
            item_qt.setText(2, item.ad)
            
            miktar_str = f"{item.miktar:,.2f}".replace('.', ',')
            satis_fiyat_str = self.db._format_currency(item.satis_fiyati)
            kdv_str = f"%{item.kdv_orani:.0f}"
            min_stok_str = f"{item.min_stok_seviyesi:,.2f}".replace('.', ',')

            item_qt.setText(3, miktar_str)
            item_qt.setText(4, satis_fiyat_str)
            item_qt.setText(5, kdv_str)
            item_qt.setText(6, min_stok_str)
            item_qt.setText(7, "Evet" if item.aktif else "Hayır")
            
            for i in range(self.tree_stok.columnCount()):
                item_qt.setTextAlignment(i, Qt.AlignCenter)
                item_qt.setFont(i, font_item)

    def _sayfalama_butonlarini_guncelle(self):
        self.btn_ilk_sayfa.setEnabled(self.mevcut_sayfa > 1)
        self.btn_onceki_sayfa.setEnabled(self.mevcut_sayfa > 1)
        self.btn_sonraki_sayfa.setEnabled(self.mevcut_sayfa < self.total_pages)
        self.btn_son_sayfa.setEnabled(self.mevcut_sayfa < self.total_pages)

    def yeni_urun_ekle_penceresi(self):
        logger.info("Yeni ürün ekle butonu tıklandı. StokKartiPenceresi açılmaya çalışılıyor.")
        try:
            dialog = StokKartiPenceresi(
                self, self.db, self.stok_listesini_yenile,
                urun_duzenle=None, app_ref=self.app
            )
            if dialog.exec() == QDialog.Accepted:
                self.stok_listesini_yenile()
            logger.info("StokKartiPenceresi kapatıldı.")
        except Exception as e:
            logger.error(f"Yeni ürün ekleme penceresi açılırken beklenmeyen bir hata oluştu: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"Yeni ürün ekleme penceresi açılırken bir hata oluştu:\n{e}")
                                        
    def secili_urun_duzenle(self):
        selected_items = self.tree_stok.selectedItems()
        if not selected_items:
            self.app.set_status_message("Lütfen düzenlemek istediğiniz ürünü seçin.", "orange")
            return

        urun_id = int(selected_items[0].text(0))

        try:
            urun_data = self.db.stok_getir_by_id(stok_id=urun_id, kullanici_id=self.app.current_user_id)
            
            if not urun_data:
                self.app.set_status_message(f"Hata: ID {urun_id} olan ürün yerel veritabanında bulunamadı.", "red")
                return
        except Exception as e:
            logging.error(f"Ürün bilgileri yerel veritabanından çekilirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Ürün bilgileri yüklenemedi. {e}", "red")
            return

        from pencereler import StokKartiPenceresi
        dialog = StokKartiPenceresi(
            self, self.db, self.stok_listesini_yenile,
            urun_duzenle=urun_data, app_ref=self.app
        )
        if dialog.exec() == QDialog.Accepted:
            self.stok_listesini_yenile()
            
    def secili_urun_sil(self):
        selected_items = self.tree_stok.selectedItems()
        if not selected_items:
            self.app.set_status_message("Lütfen silmek istediğiniz ürünü seçin.", "orange")
            return

        urun_id = int(selected_items[0].text(0))
        urun_adi = selected_items[0].text(2)

        reply = QMessageBox.question(self, 'Ürün Sil Onayı',
                                    f"'{urun_adi}' adlı ürünü silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.stok_sil(stok_id=urun_id, kullanici_id=self.app.current_user_id)
                if success:
                    self.app.set_status_message(f"'{urun_adi}' başarıyla silindi.", "green")
                    self.stok_listesini_yenile()
                else:
                    self.app.set_status_message(f"Hata: '{urun_adi}' silinemedi. API'den hata döndü.", "red")
            except Exception as e:
                logging.error(f"Ürün silinirken hata oluştu: {e}", exc_info=True)
                self.app.set_status_message(f"Hata: Ürün silinemedi. {e}", "red")

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.stok_listesini_yenile()

    def sonraki_sayfa(self):
        if self.mevcut_sayfa < self.total_pages:
            self.mevcut_sayfa += 1
            self.stok_listesini_yenile()
        else:
            self.app.set_status_message("Son sayfadasınız.", "orange")

    def _yetkileri_uygula(self):
        """Bu sayfadaki butonları kullanıcının rolüne göre ayarlar."""
        kullanici_rolu = self.current_user.get('rol', 'yok')

        if kullanici_rolu.upper() != 'YONETICI':
            self.yeni_urun_ekle_button.setEnabled(False)
            self.secili_urun_duzenle_button.setEnabled(False)
            self.secili_urun_sil_button.setEnabled(False)
            print("Stok Yönetimi sayfası için personel yetkileri uygulandı.")

class KasaBankaYonetimiSayfasi(QWidget): 
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.main_layout = QVBoxLayout(self) # Ana layout QVBoxLayout
        self.current_user = getattr(self.app, 'current_user', {})

        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)

        # Sayfalama değişkenleri
        self.kayit_sayisi_per_sayfa = 25
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0
        self.total_pages = 1
        
        self.main_layout.addWidget(QLabel("Kasa ve Banka Hesap Yönetimi", 
                                          font=QFont("Segoe UI", 16, QFont.Bold)), alignment=Qt.AlignCenter)

        # Arama ve Filtreleme Çerçevesi
        arama_frame = QFrame(self)
        arama_layout = QHBoxLayout(arama_frame)
        self.main_layout.addWidget(arama_frame)

        arama_layout.addWidget(QLabel("Hesap Ara (Ad/No/Banka):"))
        self.arama_entry_kb = QLineEdit()
        self.arama_entry_kb.setPlaceholderText("Hesap adı, numarası veya banka adı ile ara...")
        self.arama_entry_kb.textChanged.connect(self._delayed_hesap_yenile)
        arama_layout.addWidget(self.arama_entry_kb)

        arama_layout.addWidget(QLabel("Tip:"))
        self.tip_filtre_kb = QComboBox()
        self.tip_filtre_kb.addItems(["TÜMÜ", "KASA", "BANKA"])
        self.tip_filtre_kb.setCurrentText("TÜMÜ")
        self.tip_filtre_kb.currentIndexChanged.connect(self.hesap_listesini_yenile)
        arama_layout.addWidget(self.tip_filtre_kb)

        # Aktif hesap checkbox TANIMLANDI
        self.aktif_hesap_checkBox = QCheckBox("Aktif Hesaplar")
        self.aktif_hesap_checkBox.setChecked(True) # Varsayılan olarak aktif
        self.aktif_hesap_checkBox.stateChanged.connect(self.hesap_listesini_yenile)
        arama_layout.addWidget(self.aktif_hesap_checkBox)

        yenile_button = QPushButton("Yenile")
        yenile_button.clicked.connect(self.hesap_listesini_yenile)
        arama_layout.addWidget(yenile_button)

        # Hesap Listesi (QTreeWidget)
        tree_frame_kb = QFrame(self)
        tree_layout_kb = QVBoxLayout(tree_frame_kb)
        self.main_layout.addWidget(tree_frame_kb)
        tree_frame_kb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_kb = ("ID", "Hesap Adı", "Tip", "Banka Adı", "Hesap No", "Bakiye", "Para Birimi", "Aktif")
        self.tree_kb = QTreeWidget(tree_frame_kb)
        self.tree_kb.setHeaderLabels(cols_kb)
        self.tree_kb.setColumnCount(len(cols_kb))
        self.tree_kb.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_kb.setSortingEnabled(True)
        
        # Sütun ayarları
        col_definitions_kb = [
            ("ID", 40, Qt.AlignCenter),
            ("Hesap Adı", 200, Qt.AlignCenter),
            ("Tip", 80, Qt.AlignCenter),
            ("Banka Adı", 150, Qt.AlignCenter),
            ("Hesap No", 150, Qt.AlignCenter),
            ("Bakiye", 120, Qt.AlignCenter),
            ("Para Birimi", 80, Qt.AlignCenter),
            ("Aktif", 60, Qt.AlignCenter)
        ]
        for i, (col_name, width, alignment) in enumerate(col_definitions_kb):
            self.tree_kb.setColumnWidth(i, width)
            self.tree_kb.headerItem().setTextAlignment(i, alignment)
            self.tree_kb.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))

        self.tree_kb.header().setStretchLastSection(False)
        self.tree_kb.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree_kb.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tree_kb.header().setSectionResizeMode(4, QHeaderView.Stretch)
        
        tree_layout_kb.addWidget(self.tree_kb)
        
        self.tree_kb.itemDoubleClicked.connect(self.hesap_duzenle_event)

        # Butonlar Çerçevesi
        button_frame_kb = QFrame(self)
        button_layout_kb = QHBoxLayout(button_frame_kb)
        self.main_layout.addWidget(button_frame_kb)

        self.yeni_hesap_ekle_button = QPushButton("Yeni Hesap Ekle")
        self.yeni_hesap_ekle_button.clicked.connect(self.yeni_hesap_ekle_penceresi)
        button_layout_kb.addWidget(self.yeni_hesap_ekle_button)

        self.secili_hesap_duzenle_button = QPushButton("Seçili Hesabı Düzenle")
        self.secili_hesap_duzenle_button.clicked.connect(self.secili_hesap_duzenle)
        button_layout_kb.addWidget(self.secili_hesap_duzenle_button)

        self.secili_hesap_sil_button = QPushButton("Seçili Hesabı Sil")
        self.secili_hesap_sil_button.clicked.connect(self.secili_hesap_sil)
        button_layout_kb.addWidget(self.secili_hesap_sil_button)
        
        # Sayfalama
        pagination_frame_kb = QFrame(self)
        pagination_layout_kb = QHBoxLayout(pagination_frame_kb)
        self.main_layout.addWidget(pagination_frame_kb)
        onceki_sayfa_button_kb = QPushButton("Önceki Sayfa")
        onceki_sayfa_button_kb.clicked.connect(self.onceki_sayfa_kb)
        pagination_layout_kb.addWidget(onceki_sayfa_button_kb)
        self.sayfa_bilgisi_label_kb = QLabel(f"Sayfa {self.mevcut_sayfa} / {self.total_pages}")
        pagination_layout_kb.addWidget(self.sayfa_bilgisi_label_kb)
        sonraki_sayfa_button_kb = QPushButton("Sonraki Sayfa")
        sonraki_sayfa_button_kb.clicked.connect(self.sonraki_sayfa_kb)
        pagination_layout_kb.addWidget(sonraki_sayfa_button_kb)

        self.hesap_listesini_yenile() # İlk yüklemeyi yap
        self._yetkileri_uygula()

    def hesap_listesini_yenile(self):
        """API'den güncel kasa/banka listesini çeker ve TreeView'i günceller."""
        self.tree_kb.clear()
        try:
            hesaplar_response = self.db.kasa_banka_listesi_al(
                arama=self.arama_entry_kb.text(),
                hesap_turu=self.tip_filtre_kb.currentText() if self.tip_filtre_kb.currentText() != "TÜMÜ" else None,
                aktif_durum=self.aktif_hesap_checkBox.isChecked()
            )
            
            if not isinstance(hesaplar_response, dict) or "items" not in hesaplar_response:
                raise ValueError("API'den geçersiz kasa/banka listesi yanıtı alındı.")

            hesaplar = hesaplar_response["items"]
            
            for hesap in hesaplar:
                item = QTreeWidgetItem(self.tree_kb)
                item.setData(0, Qt.UserRole, hesap.get('id', -1))
                item.setText(0, str(hesap.get('id', '')))
                item.setText(1, hesap.get('hesap_adi', '-'))
                item.setText(2, hesap.get('tip', '-'))
                item.setText(3, hesap.get('banka_adi', '-') if hesap.get('tip') == 'BANKA' else '-')
                item.setText(4, hesap.get('hesap_no', '-') if hesap.get('tip') == 'BANKA' else '-')
                item.setText(5, self.db._format_currency(hesap.get('bakiye', 0.0)))
                item.setText(6, hesap.get('para_birimi', '-'))
                item.setText(7, "Evet" if hesap.get('aktif', True) else "Hayır")
                
                if hesap.get('bakiye', 0.0) < 0:
                    item.setForeground(5, QBrush(QColor("red")))
                
                if not hesap.get('aktif', True):
                    for i in range(8):
                        item.setForeground(i, QBrush(QColor("gray")))
                
                self.tree_kb.addTopLevelItem(item)

            self.app.set_status_message(f"{len(hesaplar)} kasa/banka hesabı listelendi.", "blue")

        except Exception as e:
            QMessageBox.critical(self.app, "API Hatası", f"Kasa/Banka listesi çekilirken hata: {e}")
            logging.error(f"Kasa/Banka listesi yükleme hatası: {e}", exc_info=True)

    def _delayed_hesap_yenile(self): # event=None kaldırıldı
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.hesap_listesini_yenile)

    def yeni_hesap_ekle_penceresi(self):
        try:
            from pencereler import YeniKasaBankaEklePenceresi
            dialog = YeniKasaBankaEklePenceresi(
                self,
                self.db,
                self.hesap_listesini_yenile,
                hesap_duzenle=None,
                app_ref=self.app
            )
            # DÜZELTİLDİ: Pencere kabul edildiğinde listeyi yenile
            if dialog.exec() == QDialog.Accepted:
                self.hesap_listesini_yenile()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yeni hesap ekleme penceresi açılırken bir hata oluştu:\n{e}")

    def hesap_duzenle_event(self, item, column):
        """QTreeWidget'ta bir hesaba çift tıklandığında düzenleme penceresini açar."""
        hesap_id = item.data(0, Qt.UserRole)
        if hesap_id:
            self.secili_hesap_duzenle_penceresi_ac(hesap_id=int(hesap_id))

    def secili_hesap_duzenle_penceresi_ac(self, hesap_id=None):
        """Seçili hesabı düzenleme penceresinde açar."""
        if hesap_id is None:
            selected_items = self.tree_kb.selectedItems()
            if not selected_items:
                self.app.set_status_message("Lütfen düzenlemek istediğiniz hesabı seçin.", "orange")
                return
            
            hesap_id = selected_items[0].data(0, Qt.UserRole)

        if not hesap_id:
            self.app.set_status_message("Geçersiz bir hesap seçimi yapıldı. Lütfen tekrar deneyin.", "red")
            return

        try:
            hesap_data = self.db.kasa_banka_getir_by_id(hesap_id=int(hesap_id), kullanici_id=self.app.current_user_id)
            
            if not hesap_data:
                self.app.set_status_message(f"Hata: ID {hesap_id} olan hesap yerel veritabanında bulunamadı.", "red")
                return

            if hesap_data.get('kod', '') == "NAKİT_KASA":
                QMessageBox.information(self.app, "Bilgi", "Bu varsayılan bir hesaptır. Sadece düzenlenebilir, silinemez.")

        except Exception as e:
            logging.error(f"Kasa/Banka hesap bilgileri yerel veritabanından çekilirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Hesap bilgileri yüklenemedi. {e}", "red")
            return

        from pencereler import YeniKasaBankaEklePenceresi
        dialog = YeniKasaBankaEklePenceresi(
            self.app,
            self.db,
            self.hesap_listesini_yenile,
            hesap_duzenle=hesap_data,
            app_ref=self.app
        )
        if dialog.exec() == QDialog.Accepted:
            self.hesap_listesini_yenile()

    def secili_hesap_duzenle(self):
        self.secili_hesap_duzenle_penceresi_ac()

    def secili_hesap_sil(self):
        selected_items = self.tree_kb.selectedItems()
        if not selected_items:
            self.app.set_status_message("Lütfen silmek istediğiniz hesabı seçin.", "orange")
            return

        hesap_id = selected_items[0].data(0, Qt.UserRole)
        hesap_adi = selected_items[0].text(1)

        if not hesap_id:
            self.app.set_status_message("Geçersiz bir hesap seçimi yapıldı. Lütfen tekrar deneyin.", "red")
            return

        try:
            hesap_data = self.db.kasa_banka_getir_by_id(hesap_id=int(hesap_id), kullanici_id=self.app.current_user_id)

            if hesap_data and hesap_data.get('kod', '') == "NAKİT_KASA":
                QMessageBox.critical(self.app, "Silme Hatası", "Varsayılan 'Nakit Kasa' hesabı silinemez. Sadece düzenlenebilir.")
                self.app.set_status_message("Varsayılan hesap silme işlemi engellendi.", "red")
                return
        except Exception as e:
            logging.error(f"Hesap verileri API'den çekilirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Hesap verileri yüklenemedi. Silme işlemi durduruldu.", "red")
            return

        reply = QMessageBox.question(self, 'Hesap Sil Onayı',
                                     f"'{hesap_adi}' adlı hesabı silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.kasa_banka_sil(hesap_id=int(hesap_id), kullanici_id=self.app.current_user_id)
                if success:
                    self.app.set_status_message(f"'{hesap_adi}' başarıyla silindi.", "green")
                    self.hesap_listesini_yenile()
                else:
                    self.app.set_status_message(f"Hata: '{hesap_adi}' silinemedi. API'den hata döndü.", "red")
            except Exception as e:
                logging.error(f"Hesap silinirken hata oluştu: {e}", exc_info=True)
                self.app.set_status_message(f"Hata: Hesap silinemedi. {e}", "red")
                
    def onceki_sayfa_kb(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.hesap_listesini_yenile()
        else:
            self.app.set_status_message("İlk sayfadasınız.", "orange")

    def sonraki_sayfa_kb(self):
        if self.mevcut_sayfa < self.total_pages:
            self.mevcut_sayfa += 1
            self.hesap_listesini_yenile()
        else:
            self.app.set_status_message("Son sayfadasınız.", "orange")    

    def _yetkileri_uygula(self):
        """Bu sayfadaki butonları kullanıcının rolüne göre ayarlar."""
        kullanici_rolu = self.current_user.get('rol', 'yok')

        if kullanici_rolu.upper() != 'YONETICI':
            self.yeni_hesap_ekle_button.setEnabled(False)
            self.secili_hesap_duzenle_button.setEnabled(False)
            self.secili_hesap_sil_button.setEnabled(False)
            print("Kasa/Banka Yönetimi sayfası için personel yetkileri uygulandı.")

class MusteriYonetimiSayfasi(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.current_user = getattr(self.app, 'current_user', {})
        
        # CariService entegrasyonu için servisleri burada başlatıyoruz
        from hizmetler import CariService
        self.cari_service = CariService(self.db)       

        self.main_layout = QVBoxLayout(self)

        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)

        # Sayfalama değişkenleri
        self.kayit_sayisi_per_sayfa = 25
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0
        self.total_pages = 1
        
        # Sayfa Başlığı
        self.main_layout.addWidget(QLabel("Müşteri Yönetimi", font=QFont("Segoe UI", 16, QFont.Bold)), 
                                   alignment=Qt.AlignCenter)

        # Hızlı Bakış ve Durum Butonları Alanı
        summary_frame = QFrame(self)
        summary_layout = QHBoxLayout(summary_frame)
        self.main_layout.addWidget(summary_frame)
        summary_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.lbl_toplam_alacak = QLabel("Kalan alacağınız: 0,00 TL")
        self.lbl_toplam_alacak.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_toplam_alacak.setStyleSheet("color: red;")
        summary_layout.addWidget(self.lbl_toplam_alacak)

        # Durum Butonları
        self.btn_borc_alacak_devam = QPushButton("Borcu / Alacağı Devam Edenler")
        self.btn_borc_alacak_devam.setStyleSheet("background-color: #f0f0f0;")
        summary_layout.addWidget(self.btn_borc_alacak_devam)

        self.btn_borcu_olanlar = QPushButton("Borcu Olanlar")
        summary_layout.addWidget(self.btn_borcu_olanlar)

        self.btn_artan_borc = QPushButton("Kalan Borcu artanlar")
        summary_layout.addWidget(self.btn_artan_borc)

        self.btn_azalan_borc = QPushButton("Kalan Borcu azalanlar")
        summary_layout.addWidget(self.btn_azalan_borc)
        
        # Arama ve Eylem Butonları
        arama_frame = QFrame(self)
        arama_layout = QHBoxLayout(arama_frame)
        self.main_layout.addWidget(arama_frame)
        
        arama_layout.addWidget(QLabel("Müşteri adını giriniz:"))
        self.arama_entry = QLineEdit()
        self.arama_entry.setPlaceholderText("Müşteri ara...")
        self.arama_entry.textChanged.connect(self._delayed_musteri_yenile)
        arama_layout.addWidget(self.arama_entry)
        
        self.btn_yeni_musteri = QPushButton("Yeni müşteri tanımla")
        self.btn_yeni_musteri.clicked.connect(self.yeni_musteri_ekle_penceresi)
        arama_layout.addWidget(self.btn_yeni_musteri)
        
        self.btn_ara = QPushButton("Ara")
        self.btn_ara.clicked.connect(self.musteri_listesini_yenile)
        arama_layout.addWidget(self.btn_ara)

        # Müşteri Listesi (QTreeWidget)
        tree_frame = QFrame(self)
        tree_layout = QVBoxLayout(tree_frame)
        self.main_layout.addWidget(tree_frame)
        tree_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        cols = ("Sıra", "Müşteri", "Alışveriş Sayısı", "Açık Hesap", "Ödeme", "Kalan Borcu", "Son Ödeme Tarihi")
        self.tree = QTreeWidget(tree_frame)
        self.tree.setHeaderLabels(cols)
        self.tree.setColumnCount(len(cols))
        
        # YAZI FONTU VE SATIR GENİŞLİĞİ AYARLARI
        self.tree.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.tree.setStyleSheet("QTreeWidget::item { height: 35px; }") # DARALTILDI
        
        col_definitions = [
            ("Sıra", 40, Qt.AlignCenter, QHeaderView.ResizeToContents),
            ("Müşteri", 450, Qt.AlignCenter, QHeaderView.Stretch),
            ("Alışveriş Sayısı", 160, Qt.AlignCenter, QHeaderView.Interactive),
            ("Açık Hesap", 120, Qt.AlignCenter, QHeaderView.Interactive),
            ("Ödeme", 120, Qt.AlignCenter, QHeaderView.Interactive),
            ("Kalan Borcu", 120, Qt.AlignCenter, QHeaderView.Interactive),
            ("Son Ödeme Tarihi", 90, Qt.AlignCenter, QHeaderView.Interactive),
        ]

        for i, (col_name, width, alignment, resize_mode) in enumerate(col_definitions):
            self.tree.setColumnWidth(i, width)
            self.tree.headerItem().setTextAlignment(i, alignment)
            self.tree.headerItem().setFont(i, QFont("Segoe UI", 14, QFont.Bold))
            self.tree.header().setSectionResizeMode(i, resize_mode)

        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setSortingEnabled(True)
        tree_layout.addWidget(self.tree)
        self.tree.itemDoubleClicked.connect(self.secili_musteri_ekstresi_goster)
        
        # Sayfalama Çerçevesi
        pagination_frame = QFrame(self)
        pagination_layout = QHBoxLayout(pagination_frame)
        self.main_layout.addWidget(pagination_frame)
        
        self.btn_ilk_sayfa = QPushButton("<< İlk sayfa")
        self.btn_ilk_sayfa.clicked.connect(self.ilk_sayfa)
        pagination_layout.addWidget(self.btn_ilk_sayfa)
        
        self.btn_onceki_sayfa = QPushButton("< Önceki")
        self.btn_onceki_sayfa.clicked.connect(self.onceki_sayfa)
        pagination_layout.addWidget(self.btn_onceki_sayfa)
        
        self.sayfa_bilgisi_label = QLabel(f"Sayfa {self.mevcut_sayfa} / {self.total_pages}")
        self.sayfa_bilgisi_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        pagination_layout.addWidget(self.sayfa_bilgisi_label)
        
        self.btn_sonraki_sayfa = QPushButton("Sonraki >")
        self.btn_sonraki_sayfa.clicked.connect(self.sonraki_sayfa)
        pagination_layout.addWidget(self.btn_sonraki_sayfa)
        
        self.btn_son_sayfa = QPushButton(">> Son sayfa")
        self.btn_son_sayfa.clicked.connect(self.son_sayfa)
        pagination_layout.addWidget(self.btn_son_sayfa)
        
        self.tree.itemSelectionChanged.connect(self._on_item_selection_changed)
        
        self.musteri_listesini_yenile()
        self.arama_entry.setFocus()
        self._yetkileri_uygula()

    def secili_musteri_ekstre_buton_guncelle(self):
        selected_items = self.tree.selectedItems()
        self.ekstre_button.setEnabled(bool(selected_items))

    def musteri_listesini_yenile(self):
        self.tree.clear()
        try:
            musteriler_response = self.db.musteri_listesi_al(
                arama=self.arama_entry.text(),
                aktif_durum=True
            )

            if not isinstance(musteriler_response, dict) or "items" not in musteriler_response:
                 raise ValueError("API'den geçersiz müşteri listesi yanıtı alındı.")

            musteriler = musteriler_response["items"]
            
            for musteri_item in musteriler:
                item = QTreeWidgetItem(self.tree)
                item.setData(0, Qt.UserRole, musteri_item.get('id'))
                item.setText(0, str(musteri_item.get('id')))
                item.setText(1, musteri_item.get('ad', '-'))
                item.setText(2, str(musteri_item.get('alisveris_sayisi', 0)))
                item.setText(3, self.db._format_currency(musteri_item.get('acik_hesap', 0.0)))
                item.setText(4, self.db._format_currency(musteri_item.get('odeme', 0.0)))
                item.setText(5, self.db._format_currency(musteri_item.get('kalan_borcu', 0.0)))
                item.setText(6, musteri_item.get('son_odeme_tarihi', '-'))
                
                if musteri_item.get('kalan_borcu', 0.0) > 0:
                    item.setForeground(5, QBrush(QColor("red")))
                elif musteri_item.get('kalan_borcu', 0.0) < 0:
                    item.setForeground(5, QBrush(QColor("green")))
                
                self.tree.addTopLevelItem(item)

            self.app.set_status_message(f"{len(musteriler)} müşteri listelendi.", "blue")

        except Exception as e:
            QMessageBox.critical(self.app, "API Hatası", f"Müşteri listesi çekilirken hata: {e}")
            logging.error(f"Müşteri listesi yükleme hatası: {e}", exc_info=True)
                
    def _sayfalama_butonlarini_guncelle(self):
        # Sadece sayfalama butonlarının durumunu yönetir.
        self.btn_ilk_sayfa.setEnabled(self.mevcut_sayfa > 1)
        self.btn_onceki_sayfa.setEnabled(self.mevcut_sayfa > 1)
        self.btn_sonraki_sayfa.setEnabled(self.mevcut_sayfa < self.total_pages)
        self.btn_son_sayfa.setEnabled(self.mevcut_sayfa < self.total_pages)
                
    def secili_musteri_sil(self):
        kullanici_rolu = self.current_user.get('rol', 'yok')
        if kullanici_rolu.upper() != 'YONETICI':
            QMessageBox.warning(self.app, "Yetki Hatası", "Bu işlemi yapmak için yetkiniz yok.")
            return

        selected_items = self.tree.selectedItems()
        if not selected_items:
            self.app.set_status_message("Lütfen silmek istediğiniz müşteriyi seçin.")
            return

        selected_item = selected_items[0]
        musteri_id = selected_item.data(0, Qt.UserRole)
        musteri_adi = selected_item.text(1)

        reply = QMessageBox.question(self, 'Müşteri Sil Onayı',
                                     f"'{musteri_adi}' adlı müşteriyi silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.musteri_sil(musteri_id=musteri_id, kullanici_id=self.app.current_user_id)
                if success:
                    self.app.set_status_message(f"'{musteri_adi}' başarıyla silindi.")
                    self.musteri_listesini_yenile()
                else:
                    self.app.set_status_message(f"Hata: '{musteri_adi}' silinemedi. API'den hata döndü.")
            except Exception as e:
                logging.error(f"Müşteri silinirken hata oluştu: {e}", exc_info=True)
                self.app.set_status_message(f"Hata: Müşteri silinemedi. {e}")
                
    def _on_arama_entry_return(self):
        self.musteri_listesini_yenile()
    
    def _delayed_musteri_yenile(self):
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.musteri_listesini_yenile)

    def guncelle_toplam_ozet_bilgiler(self):
        self.lbl_toplam_alacak.setText("Kalan alacağınız: 0,00 TL")

    def _on_item_selection_changed(self):
        selected_items = self.tree.selectedItems()
        is_item_selected = bool(selected_items)
        
        # Seçim durumuna göre "Yeni müşteri" ve "Ara" butonlarını yönet.
        self.btn_yeni_musteri.setEnabled(not is_item_selected)
        self.btn_ara.setEnabled(not is_item_selected)
        
        # Sayfalama butonları artık bu metot tarafından yönetilmiyor.

    def ilk_sayfa(self):
        if self.mevcut_sayfa != 1:
            self.mevcut_sayfa = 1
            self.musteri_listesini_yenile()
        else:
            self.app.set_status_message("Zaten ilk sayfadasınız.", "orange")

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.musteri_listesini_yenile()
        else:
            self.app.set_status_message("İlk sayfadasınız.", "orange")

    def sonraki_sayfa(self):
        if self.mevcut_sayfa < self.total_pages:
            self.mevcut_sayfa += 1
            self.musteri_listesini_yenile()
        else:
            self.app.set_status_message("Son sayfadasınız.", "orange")

    def son_sayfa(self):
        if self.mevcut_sayfa != self.total_pages:
            self.mevcut_sayfa = self.total_pages
            self.musteri_listesini_yenile()
        else:
            self.app.set_status_message("Zaten son sayfadasınız.", "orange")

    def yeni_musteri_ekle_penceresi(self):
        try:
            from pencereler import YeniMusteriEklePenceresi
            dialog = YeniMusteriEklePenceresi(
                self,
                self.db,
                self.musteri_listesini_yenile,
                musteri_duzenle=None,
                app_ref=self.app
            )
            if dialog.exec() == QDialog.Accepted:
                self.musteri_listesini_yenile()

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yeni müşteri ekleme penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Yeni müşteri ekleme penceresi açılamadı - {e}")
            
    def secili_musteri_duzenle(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            self.app.set_status_message("Lütfen düzenlemek istediğiniz müşteriyi seçin.") 
            return
        
        selected_item = selected_items[0]
        musteri_id = selected_item.data(0, Qt.UserRole)
        
        try:
            musteri_data = self.db.musteri_getir_by_id(musteri_id=musteri_id, kullanici_id=self.app.current_user_id)

            if not musteri_data:
                self.app.set_status_message(f"Hata: ID {musteri_id} olan müşteri yerel veritabanında bulunamadı.", "red") 
                return
        except Exception as e:
            logging.error(f"Müşteri bilgileri yerel veritabanından çekilirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Müşteri bilgileri yüklenemedi. {e}") 
            return

        from pencereler import YeniMusteriEklePenceresi
        dialog = YeniMusteriEklePenceresi(
            self,
            self.db,
            self.musteri_listesini_yenile,
            musteri_duzenle=musteri_data,
            app_ref=self.app
        )
        if dialog.exec() == QDialog.Accepted:
            self.musteri_listesini_yenile()
                    
    def secili_musteri_ekstresi_goster(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen ekstresini görmek için bir müşteri seçin.")
            return

        selected_item = selected_items[0]
        # Müşteri Adı, 1. sütun (indeks 1)
        musteri_adi = selected_item.text(1) 
        musteri_id = selected_item.data(0, Qt.UserRole)
        
        if musteri_id == -1: 
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir müşteri seçimi yaptınız.")
             return
        
        try:
            from pencereler import CariHesapEkstresiPenceresi 
            
            cari_ekstre_penceresi = CariHesapEkstresiPenceresi(
                self.app, 
                self.db, 
                musteri_id, 
                self.db.CARI_TIP_MUSTERI, 
                musteri_adi, 
                parent_list_refresh_func=self.musteri_listesini_yenile
            )
            cari_ekstre_penceresi.show()
            self.app.set_status_message(f"'{musteri_adi}' için cari hesap ekstresi açıldı.")

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Cari Hesap Ekstresi penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Cari Hesap Ekstresi penceresi açılamadı - {e}")

    def _yetkileri_uygula(self):
        """Bu sayfadaki butonları kullanıcının rolüne göre ayarlar."""
        kullanici_rolu = self.current_user.get('rol', 'yok')

        if kullanici_rolu.upper() != 'YONETICI':
            self.btn_yeni_musteri.setEnabled(False)
            # Silme işlemi doğrudan bir butonla değil, secili_musteri_sil metodu ile yapılıyor.
            # Bu metodu çağıran bir context menu veya başka bir UI elemanı varsa
            # onu da burada pasifleştirmek gerekir. Şimdilik sadece ana butonu pasifleştiriyoruz.
            print("Müşteri Yönetimi sayfası için personel yetkileri uygulandı.")

class TedarikciYonetimiSayfasi(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.current_user = getattr(self.app, 'current_user', {})
        # CariService entegrasyonu için servisleri burada başlatıyoruz
        from hizmetler import CariService
        self.cari_service = CariService(self.db)

        self.main_layout = QVBoxLayout(self)

        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)
        
        # Sayfalama değişkenleri
        self.kayit_sayisi_per_sayfa = 25
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0
        self.total_pages = 1

        # Sayfa Başlığı
        self.main_layout.addWidget(QLabel("Tedarikçi Yönetimi", font=QFont("Segoe UI", 16, QFont.Bold)), 
                                   alignment=Qt.AlignCenter)

        # Hızlı Bakış ve Durum Butonları Alanı
        summary_frame = QFrame(self)
        summary_layout = QHBoxLayout(summary_frame)
        self.main_layout.addWidget(summary_frame)
        summary_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.lbl_toplam_borc = QLabel("Kalan borcunuz: 0,00 TL")
        self.lbl_toplam_borc.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_toplam_borc.setStyleSheet("color: red;")
        summary_layout.addWidget(self.lbl_toplam_borc)

        # Durum Butonları
        self.btn_borc_alacak_devam = QPushButton("Borcu / Alacağı Devam Edenler")
        self.btn_borc_alacak_devam.setStyleSheet("background-color: #f0f0f0;")
        summary_layout.addWidget(self.btn_borc_alacak_devam)

        self.btn_alacagi_olanlar = QPushButton("Alacağı Olanlar")
        summary_layout.addWidget(self.btn_alacagi_olanlar)

        self.btn_artan_alacak = QPushButton("Kalan Alacağı artanlar")
        summary_layout.addWidget(self.btn_artan_alacak)

        self.btn_azalan_alacak = QPushButton("Kalan Alacağı azalanlar")
        summary_layout.addWidget(self.btn_azalan_alacak)

        # Arama ve Eylem Butonları
        arama_frame = QFrame(self)
        arama_layout = QHBoxLayout(arama_frame)
        self.main_layout.addWidget(arama_frame)
        
        arama_layout.addWidget(QLabel("Tedarikçi adını giriniz:"))
        self.arama_entry = QLineEdit()
        self.arama_entry.setPlaceholderText("Tedarikçi ara...")
        self.arama_entry.textChanged.connect(self._delayed_tedarikci_yenile)
        arama_layout.addWidget(self.arama_entry)
        
        self.btn_yeni_tedarikci = QPushButton("Yeni tedarikçi tanımla")
        self.btn_yeni_tedarikci.clicked.connect(self.yeni_tedarikci_ekle_penceresi)
        arama_layout.addWidget(self.btn_yeni_tedarikci)
        
        self.btn_ara = QPushButton("Ara")
        self.btn_ara.clicked.connect(self.tedarikci_listesini_yenile)
        arama_layout.addWidget(self.btn_ara)

        # Tedarikçi Listesi (QTreeWidget)
        tree_frame = QFrame(self)
        tree_layout = QVBoxLayout(tree_frame)
        self.main_layout.addWidget(tree_frame)
        tree_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        cols = ("Sıra", "Tedarikçi", "Alışveriş Sayısı", "Açık Hesap", "Ödeme", "Kalan Borcu", "Son Ödeme Tarihi")
        self.tree = QTreeWidget(tree_frame)
        self.tree.setHeaderLabels(cols)
        self.tree.setColumnCount(len(cols))
        
        # YAZI FONTU VE SATIR GENİŞLİĞİ AYARLARI
        self.tree.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.tree.setStyleSheet("QTreeWidget::item { height: 35px; }") # DARALTILDI

        col_definitions = [
            ("Sıra", 40, Qt.AlignCenter, QHeaderView.ResizeToContents),
            ("Tedarikçi", 450, Qt.AlignCenter, QHeaderView.Stretch),
            ("Alışveriş Sayısı", 160, Qt.AlignCenter, QHeaderView.Interactive),
            ("Açık Hesap", 120, Qt.AlignCenter, QHeaderView.Interactive),
            ("Ödeme", 120, Qt.AlignCenter, QHeaderView.Interactive),
            ("Kalan Borcu", 120, Qt.AlignCenter, QHeaderView.Interactive),
            ("Son Ödeme Tarihi", 90, Qt.AlignCenter, QHeaderView.Interactive),
        ]

        for i, (col_name, width, alignment, resize_mode) in enumerate(col_definitions):
            self.tree.setColumnWidth(i, width)
            self.tree.headerItem().setTextAlignment(i, alignment)
            self.tree.headerItem().setFont(i, QFont("Segoe UI", 14, QFont.Bold))
            self.tree.header().setSectionResizeMode(i, resize_mode)

        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setSortingEnabled(True)
        tree_layout.addWidget(self.tree)
        self.tree.itemDoubleClicked.connect(self.secili_tedarikci_ekstresi_goster)
        
        # Sayfalama Çerçevesi
        pagination_frame = QFrame(self)
        pagination_layout = QHBoxLayout(pagination_frame)
        self.main_layout.addWidget(pagination_frame)
        
        self.btn_ilk_sayfa = QPushButton("<< İlk sayfa")
        self.btn_ilk_sayfa.clicked.connect(self.ilk_sayfa)
        pagination_layout.addWidget(self.btn_ilk_sayfa)
        
        self.btn_onceki_sayfa = QPushButton("< Önceki")
        self.btn_onceki_sayfa.clicked.connect(self.onceki_sayfa)
        pagination_layout.addWidget(self.btn_onceki_sayfa)
        
        self.sayfa_bilgisi_label = QLabel(f"Sayfa {self.mevcut_sayfa} / {self.total_pages}")
        self.sayfa_bilgisi_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        pagination_layout.addWidget(self.sayfa_bilgisi_label)
        
        self.btn_sonraki_sayfa = QPushButton("Sonraki >")
        self.btn_sonraki_sayfa.clicked.connect(self.sonraki_sayfa)
        pagination_layout.addWidget(self.btn_sonraki_sayfa)
        
        self.btn_son_sayfa = QPushButton(">> Son sayfa")
        self.btn_son_sayfa.clicked.connect(self.son_sayfa)
        pagination_layout.addWidget(self.btn_son_sayfa)
        
        self.tree.itemSelectionChanged.connect(self._on_item_selection_changed)

        self.tedarikci_listesini_yenile()
        self.arama_entry.setFocus()
        self._yetkileri_uygula()

    def secili_tedarikci_ekstre_buton_guncelle(self):
        selected_items = self.tree.selectedItems()
        self.ekstre_button_ted.setEnabled(bool(selected_items))

    def tedarikci_listesini_yenile(self):
        self.tree.clear()
        try:
            tedarikciler_response = self.db.tedarikci_listesi_al(
                arama=self.arama_entry.text(),
                aktif_durum=True
            )

            if not isinstance(tedarikciler_response, dict) or "items" not in tedarikciler_response:
                 raise ValueError("API'den geçersiz tedarikçi listesi yanıtı alındı.")

            tedarikciler = tedarikciler_response["items"]
            
            for tedarikci_item in tedarikciler:
                item = QTreeWidgetItem(self.tree)
                item.setData(0, Qt.UserRole, tedarikci_item.get('id'))
                item.setText(0, str(tedarikci_item.get('id')))
                item.setText(1, tedarikci_item.get('ad', '-'))
                item.setText(2, str(tedarikci_item.get('alisveris_sayisi', 0)))
                item.setText(3, self.db._format_currency(tedarikci_item.get('acik_hesap', 0.0)))
                item.setText(4, self.db._format_currency(tedarikci_item.get('odeme', 0.0)))
                item.setText(5, self.db._format_currency(tedarikci_item.get('kalan_borcu', 0.0)))
                item.setText(6, tedarikci_item.get('son_odeme_tarihi', '-'))
                
                if tedarikci_item.get('kalan_borcu', 0.0) > 0:
                    item.setForeground(5, QBrush(QColor("red")))
                elif tedarikci_item.get('kalan_borcu', 0.0) < 0:
                    item.setForeground(5, QBrush(QColor("green")))
                
                self.tree.addTopLevelItem(item)

            self.app.set_status_message(f"{len(tedarikciler)} tedarikçi listelendi.", "blue")

        except Exception as e:
            QMessageBox.critical(self.app, "API Hatası", f"Tedarikçi listesi çekilirken hata: {e}")
            logging.error(f"Tedarikçi listesi yükleme hatası: {e}", exc_info=True)

    def _sayfalama_butonlarini_guncelle(self):
        # Sadece sayfalama butonlarının durumunu yönetir.
        self.btn_ilk_sayfa.setEnabled(self.mevcut_sayfa > 1)
        self.btn_onceki_sayfa.setEnabled(self.mevcut_sayfa > 1)
        self.btn_sonraki_sayfa.setEnabled(self.mevcut_sayfa < self.total_pages)
        self.btn_son_sayfa.setEnabled(self.mevcut_sayfa < self.total_pages)

    def secili_tedarikci_sil(self):
        kullanici_rolu = self.current_user.get('rol', 'yok')
        if kullanici_rolu.upper() != 'YONETICI':
            QMessageBox.warning(self.app, "Yetki Hatası", "Bu işlemi yapmak için yetkiniz yok.")
            return

        selected_items = self.tree.selectedItems()
        if not selected_items:
            self.app.set_status_message("Lütfen silmek istediğiniz tedarikçiyi seçin.")
            return

        selected_item = selected_items[0]
        tedarikci_id = selected_item.data(0, Qt.UserRole)
        tedarikci_adi = selected_item.text(1)

        reply = QMessageBox.question(self, 'Tedarikçi Sil Onayı',
                                     f"'{tedarikci_adi}' adlı tedarikçiyi silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.tedarikci_sil(tedarikci_id=tedarikci_id, kullanici_id=self.app.current_user_id)
                if success:
                    self.app.set_status_message(f"'{tedarikci_adi}' başarıyla silindi.")
                    self.tedarikci_listesini_yenile()
                else:
                    self.app.set_status_message(f"Hata: '{tedarikci_adi}' silinemedi. API'den hata döndü.")
            except Exception as e:
                logging.error(f"Tedarikçi silinirken hata oluştu: {e}", exc_info=True)
                self.app.set_status_message(f"Hata: Tedarikçi silinemedi. {e}")
            
    def guncelle_toplam_ozet_bilgiler(self):
        self.lbl_toplam_borc.setText("Kalan borcunuz: 0,00 TL")

    def _on_arama_entry_return(self):
        self.tedarikci_listesini_yenile()
    
    def _delayed_tedarikci_yenile(self):
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.tedarikci_listesini_yenile)

    def _on_item_selection_changed(self):
        selected_items = self.tree.selectedItems()
        is_item_selected = bool(selected_items)
        
        # Seçim durumuna göre "Yeni tedarikçi" ve "Ara" butonlarını yönet.
        self.btn_yeni_tedarikci.setEnabled(not is_item_selected)
        self.btn_ara.setEnabled(not is_item_selected)

        # Sayfalama butonları artık bu metot tarafından yönetilmiyor.

    def ilk_sayfa(self):
        if self.mevcut_sayfa != 1:
            self.mevcut_sayfa = 1
            self.tedarikci_listesini_yenile()
        else:
            self.app.set_status_message("Zaten ilk sayfadasınız.", "orange")

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.tedarikci_listesini_yenile()
        else:
            self.app.set_status_message("İlk sayfadasınız.", "orange")

    def sonraki_sayfa(self):
        if self.mevcut_sayfa < self.total_pages:
            self.mevcut_sayfa += 1
            self.tedarikci_listesini_yenile()
        else:
            self.app.set_status_message("Son sayfadasınız.", "orange")

    def son_sayfa(self):
        if self.mevcut_sayfa != self.total_pages:
            self.mevcut_sayfa = self.total_pages
            self.tedarikci_listesini_yenile()
        else:
            self.app.set_status_message("Zaten son sayfadasınız.", "orange")

    def yeni_tedarikci_ekle_penceresi(self):
        try:
            from pencereler import YeniTedarikciEklePenceresi
            dialog = YeniTedarikciEklePenceresi(
                self,
                self.db,
                self.tedarikci_listesini_yenile,
                tedarikci_duzenle=None,
                app_ref=self.app
            )
            if dialog.exec() == QDialog.Accepted:
                self.tedarikci_listesini_yenile()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yeni tedarikçi ekleme penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Yeni tedarikçi ekleme penceresi açılamadı - {e}")

    def secili_tedarikci_duzenle(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            self.app.set_status_message("Lütfen düzenlemek istediğiniz tedarikçiyi seçin.")
            return

        selected_item = selected_items[0]
        tedarikci_id = selected_item.data(0, Qt.UserRole)

        try:
            tedarikci_data = self.db.tedarikci_getir_by_id(tedarikci_id=tedarikci_id, kullanici_id=self.app.current_user_id)
            
            if not tedarikci_data:
                self.app.set_status_message(f"Hata: ID {tedarikci_id} olan tedarikçi yerel veritabanında bulunamadı.", "red")
                return
        except Exception as e:
            logging.error(f"Tedarikçi bilgileri yerel veritabanından çekilirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Tedarikçi bilgileri yüklenemedi. {e}")
            return

        from pencereler import YeniTedarikciEklePenceresi
        dialog = YeniTedarikciEklePenceresi(
            self,
            self.db,
            self.tedarikci_listesini_yenile,
            tedarikci_duzenle=tedarikci_data,
            app_ref=self.app
        )
        if dialog.exec() == QDialog.Accepted:
            self.tedarikci_listesini_yenile()
                
    def secili_tedarikci_ekstresi_goster(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen ekstresini görmek için bir tedarikçi seçin.")
            return

        selected_item = selected_items[0]
        # Tedarikçi Adı, 1. sütun (indeks 1)
        tedarikci_adi = selected_item.text(1) 
        tedarikci_id = selected_item.data(0, Qt.UserRole)

        if tedarikci_id == -1: 
             QMessageBox.warning(self, "Uyarı", "Geçersiz bir tedarikçi seçimi yaptınız.")
             return
        
        try:
            from pencereler import CariHesapEkstresiPenceresi 
            
            cari_ekstre_penceresi = CariHesapEkstresiPenceresi(
                self.app, 
                self.db, 
                tedarikci_id, 
                self.db.CARI_TIP_TEDARIKCI, 
                tedarikci_adi, 
                parent_list_refresh_func=self.tedarikci_listesini_yenile 
            )
            cari_ekstre_penceresi.show()
            self.app.set_status_message(f"'{tedarikci_adi}' için cari hesap ekstresi açıldı.")

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Cari Hesap Ekstresi penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Cari Hesap Ekstresi penceresi açılamadı - {e}")

    def _yetkileri_uygula(self):
        """Bu sayfadaki butonları kullanıcının rolüne göre ayarlar."""
        kullanici_rolu = self.current_user.get('rol', 'yok')

        if kullanici_rolu.upper() != 'YONETICI':
            self.btn_yeni_tedarikci.setEnabled(False)
            print("Tedarikçi Yönetimi sayfası için personel yetkileri uygulandı.")

# FaturaListesiSayfasi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class FaturaListesiSayfasi(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.main_layout = QVBoxLayout(self)

        self.main_layout.addWidget(QLabel("Faturalar", font=QFont("Segoe UI", 16, QFont.Bold)), 
                                   alignment=Qt.AlignCenter)

        self.main_tab_widget = QTabWidget(self)
        self.main_layout.addWidget(self.main_tab_widget)

        # Sekme 1: Satış Faturaları
        self.satis_fatura_frame = SatisFaturalariListesi(self.main_tab_widget, self.db, self.app, fatura_tipi='SATIŞ')
        self.main_tab_widget.addTab(self.satis_fatura_frame, "🛍️ Satış Faturaları")

        # Sekme 2: Alış Faturaları
        self.alis_fatura_frame = AlisFaturalariListesi(self.main_tab_widget, self.db, self.app, fatura_tipi='ALIŞ')
        self.main_tab_widget.addTab(self.alis_fatura_frame, "🛒 Alış Faturaları")
        
        # Sekme değiştiğinde _on_tab_change metodunu çağırıyoruz.
        self.main_tab_widget.currentChanged.connect(self._on_tab_change)

    def _on_tab_change(self, index):
        """Sekme değiştiğinde ilgili listeyi yeniler."""
        selected_widget = self.main_tab_widget.widget(index)
        if hasattr(selected_widget, 'fatura_listesini_yukle'):
            selected_widget.fatura_listesini_yukle()
            
    def fatura_listesini_yukle(self):
        """
        [KRİTİK DÜZELTME] FaturaListesiSayfasi bir konteynırdır ve fatura_tree'ye sahip değildir. 
        Yenileme işini alt sınıflara (BaseFaturaListesi'nden miras alan sekmeler) devreder.
        """
        current_widget = self.main_tab_widget.currentWidget()
        
        # Eğer aktif widget'ın listeyi yükleme metodu varsa, sadece onu çağır.
        if hasattr(current_widget, 'fatura_listesini_yukle'):
            current_widget.fatura_listesini_yukle()
            self.app.set_status_message(f"Aktif sekme ('{self.main_tab_widget.tabText(self.main_tab_widget.currentIndex())}') güncellendi.", "blue")
        else:
            # Eğer aktif sekme bulunamazsa (ki bu normalde olmamalı) yedekleme olarak her iki listeyi de yenilemeye zorla.
            self.satis_fatura_frame.fatura_listesini_yukle()
            self.alis_fatura_frame.fatura_listesini_yukle()
            self.app.set_status_message("Tüm fatura listeleri yeniden yüklendi.", "blue")

    def yeni_fatura_ekle_ui(self, fatura_tipi):
        """
        Yeni bir fatura oluşturma penceresi açar.
        Ana sayfadaki butonlar bu metodu çağırır.
        """
        
        yeni_fatura_penceresi = QDialog(self)
        yeni_fatura_penceresi.setWindowTitle("Yeni Fatura Oluştur")
        
        # KRİTİK DÜZELTME: Pencereyi tam ekran aç
        yeni_fatura_penceresi.setWindowState(Qt.WindowMaximized) 
        
        # YENİ EKLEME: Bazı sistemlerde maksimizasyonu zorlamak için büyük bir minimum boyut ipucu verilir.
        yeni_fatura_penceresi.setMinimumSize(1200, 800) 
        
        fatura_form_page = FaturaOlusturmaSayfasi(
            yeni_fatura_penceresi, 
            self.db, 
            self.app, 
            fatura_tipi=fatura_tipi,
            yenile_callback=self.fatura_listesini_yukle 
        )
        
        layout = QVBoxLayout(yeni_fatura_penceresi)
        layout.addWidget(fatura_form_page)
        
        fatura_form_page.saved_successfully.connect(yeni_fatura_penceresi.accept)
        fatura_form_page.cancelled_successfully.connect(yeni_fatura_penceresi.reject)
        
        yeni_fatura_penceresi.exec()
        # Pencere kapatıldığında listeyi yenile.
        self.fatura_listesini_yukle()

class SiparisListesiSayfasi(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.current_user = getattr(self.app, 'current_user', {})
        from hizmetler import CariService
        self.cari_service = CariService(self.db)
        
        self.main_layout = QVBoxLayout(self)
        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)
        
        # Sayfalama değişkenleri
        self.kayit_sayisi_per_sayfa = 20
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0
        self.total_pages = 1
        self.main_layout.addWidget(QLabel("Sipariş Yönetimi", font=QFont("Segoe UI", 16, QFont.Bold)), 
                                   alignment=Qt.AlignCenter)
        # Filtreleme ve Arama Çerçevesi
        filter_top_frame = QFrame(self)
        filter_top_layout = QHBoxLayout(filter_top_frame)
        self.main_layout.addWidget(filter_top_frame)
        filter_top_layout.addWidget(QLabel("Başlangıç Tarihi:"))
        self.bas_tarih_entry = QLineEdit()
        self.bas_tarih_entry.setText((datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        filter_top_layout.addWidget(self.bas_tarih_entry)
        
        takvim_button_bas = QPushButton("🗓️")
        takvim_button_bas.setFixedWidth(30)
        takvim_button_bas.clicked.connect(lambda: DatePickerDialog(self.app, self.bas_tarih_entry))
        filter_top_layout.addWidget(takvim_button_bas)
        filter_top_layout.addWidget(QLabel("Bitiş Tarihi:"))
        self.bit_tarih_entry = QLineEdit()
        self.bit_tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        filter_top_layout.addWidget(self.bit_tarih_entry)
        
        takvim_button_bit = QPushButton("🗓️")
        takvim_button_bit.setFixedWidth(30)
        takvim_button_bit.clicked.connect(lambda: DatePickerDialog(self.app, self.bit_tarih_entry))
        filter_top_layout.addWidget(takvim_button_bit)
        filter_top_layout.addWidget(QLabel("Ara (Sipariş No/Cari/Ürün):"))
        self.arama_siparis_entry = QLineEdit()
        self.arama_siparis_entry.setPlaceholderText("Sipariş No, Cari Adı veya Ürün ara...")
        self.arama_siparis_entry.textChanged.connect(self._delayed_siparis_listesi_yukle)
        filter_top_layout.addWidget(self.arama_siparis_entry)
        temizle_button = QPushButton("Temizle")
        temizle_button.clicked.connect(self._arama_temizle)
        filter_top_layout.addWidget(temizle_button)
        filtre_yenile_button = QPushButton("Filtrele/Yenile")
        filtre_yenile_button.clicked.connect(self.siparis_listesini_yukle)
        filter_top_layout.addWidget(filtre_yenile_button)
        # Filtreleme Alanları (Cari, Durum, Sipariş Tipi)
        filter_bottom_frame = QFrame(self)
        filter_bottom_layout = QHBoxLayout(filter_bottom_frame)
        self.main_layout.addWidget(filter_bottom_frame)
        filter_bottom_layout.addWidget(QLabel("Cari Filtre:"))
        self.cari_filter_cb = QComboBox() # Cari filtre combobox'ı tanımlandı
        self.cari_filter_cb.currentIndexChanged.connect(self.siparis_listesini_yukle)
        filter_bottom_layout.addWidget(self.cari_filter_cb)
        filter_bottom_layout.addWidget(QLabel("Durum:"))
        self.durum_combo = QComboBox() # Durum combobox'ı tanımlandı
        self.durum_combo.addItems(["TÜMÜ", self.db.SIPARIS_DURUM_BEKLEMEDE, 
                                       self.db.SIPARIS_DURUM_TAMAMLANDI, 
                                       self.db.SIPARIS_DURUM_KISMİ_TESLIMAT, 
                                       self.db.SIPARIS_DURUM_IPTAL_EDILDI])
        self.durum_combo.setCurrentText("TÜMÜ")
        self.durum_combo.currentIndexChanged.connect(self.siparis_listesini_yukle)
        filter_bottom_layout.addWidget(self.durum_combo)
        filter_bottom_layout.addWidget(QLabel("Sipariş Tipi:"))
        self.siparis_tipi_filter_cb = QComboBox() # Sipariş Tipi combobox'ı tanımlandı
        self.siparis_tipi_filter_cb.addItems(["TÜMÜ", self.db.SIPARIS_TIP_SATIS, self.db.SIPARIS_TIP_ALIS])
        self.siparis_tipi_filter_cb.setCurrentText("TÜMÜ")
        self.siparis_tipi_filter_cb.currentIndexChanged.connect(self.siparis_listesini_yukle)
        filter_bottom_layout.addWidget(self.siparis_tipi_filter_cb)
        # Butonlar Çerçevesi
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        self.main_layout.addWidget(button_frame)
        
        self.yeni_musteri_siparisi_button = QPushButton("Yeni Müşteri Siparişi")
        self.yeni_musteri_siparisi_button.clicked.connect(lambda: self.yeni_siparis_penceresi_ac(self.db.SIPARIS_TIP_SATIS))
        button_layout.addWidget(self.yeni_musteri_siparisi_button)

        self.yeni_tedarikci_siparisi_button = QPushButton("Yeni Tedarikçi Siparişi")
        self.yeni_tedarikci_siparisi_button.clicked.connect(lambda: self.yeni_siparis_penceresi_ac(self.db.SIPARIS_TIP_ALIS))
        button_layout.addWidget(self.yeni_tedarikci_siparisi_button)
        
        self.detay_goster_button = QPushButton("Seçili Sipariş Detayları")
        self.detay_goster_button.clicked.connect(self.secili_siparis_detay_goster)
        self.detay_goster_button.setEnabled(False)
        button_layout.addWidget(self.detay_goster_button)

        self.duzenle_button = QPushButton("Seçili Siparişi Düzenle")
        self.duzenle_button.clicked.connect(self.secili_siparisi_duzenle)
        self.duzenle_button.setEnabled(False)
        button_layout.addWidget(self.duzenle_button)

        self.faturaya_donustur_button = QPushButton("Seçili Siparişi Faturaya Dönüştür")
        self.faturaya_donustur_button.clicked.connect(self.secili_siparisi_faturaya_donustur)
        self.faturaya_donustur_button.setEnabled(False)
        button_layout.addWidget(self.faturaya_donustur_button)

        self.sil_button = QPushButton("Seçili Siparişi Sil")
        self.sil_button.clicked.connect(self.secili_siparisi_sil)
        self.sil_button.setEnabled(False)
        button_layout.addWidget(self.sil_button)

        # Sayfalama için gerekli değişkenler ve widget'lar
        pagination_frame = QFrame(self)
        pagination_layout = QHBoxLayout(pagination_frame)
        self.main_layout.addWidget(pagination_frame)
        onceki_sayfa_button = QPushButton("Önceki Sayfa")
        onceki_sayfa_button.clicked.connect(self.onceki_sayfa)
        pagination_layout.addWidget(onceki_sayfa_button)
        self.sayfa_bilgisi_label = QLabel(f"Sayfa {self.mevcut_sayfa} / {self.total_pages}") # Güncellendi
        self.sayfa_bilgisi_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        pagination_layout.addWidget(self.sayfa_bilgisi_label)
        sonraki_sayfa_button = QPushButton("Sonraki Sayfa")
        sonraki_sayfa_button.clicked.connect(self.sonraki_sayfa)
        pagination_layout.addWidget(sonraki_sayfa_button)
        # Sipariş Listesi (QTreeWidget)
        cols = ("ID", "Sipariş No", "Tarih", "Cari Adı", "Sipariş Tipi", "Toplam Tutar", "Durum", "Teslimat Tarihi")
        self.siparis_tree = QTreeWidget(self) # siparis_tree tanımlandı
        self.siparis_tree.setHeaderLabels(cols)
        self.siparis_tree.setColumnCount(len(cols))
        self.siparis_tree.setSelectionBehavior(QAbstractItemView.SelectRows) # Satır seçimi
        self.siparis_tree.setSortingEnabled(True) # Sıralama aktif
        
        # Sütun ayarları
        col_definitions = [
            ("ID", 40, Qt.AlignCenter), # DÜZELTME: Ortala
            ("Sipariş No", 100, Qt.AlignCenter), # DÜZELTME: Ortala
            ("Tarih", 85, Qt.AlignCenter),
            ("Cari Adı", 180, Qt.AlignCenter), # DÜZELTME: Ortala
            ("Sipariş Tipi", 100, Qt.AlignCenter),
            ("Toplam Tutar", 110, Qt.AlignCenter), # DÜZELTME: Ortala
            ("Durum", 100, Qt.AlignCenter),
            ("Teslimat Tarihi", 90, Qt.AlignCenter)
        ]
        for i, (col_name, width, alignment) in enumerate(col_definitions):
            self.siparis_tree.setColumnWidth(i, width)
            self.siparis_tree.headerItem().setTextAlignment(i, alignment)
            self.siparis_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
        self.siparis_tree.header().setStretchLastSection(False) # Son sütun otomatik genişlemesini kapat
        self.siparis_tree.header().setSectionResizeMode(3, QHeaderView.Stretch) # Cari Adı genişlesin
        self.main_layout.addWidget(self.siparis_tree) # Treeview'i ana layout'a ekle
        self.siparis_tree.itemSelectionChanged.connect(self._on_siparis_select)
        self.siparis_tree.itemDoubleClicked.connect(self.on_double_click_detay_goster)
        self._yukle_filtre_comboboxlari() # Comboboxlar tanımlandıktan sonra çağır
        self.siparis_listesini_yukle() # Tüm UI elemanları kurulduktan sonra çağır
        self._on_siparis_select() # Buton durumlarını ayarla
        self._yetkileri_uygula()

    def _open_date_picker(self, target_entry_qlineedit: QLineEdit):
        """
        PySide6 DatePickerDialog'u açar ve seçilen tarihi target_entry_qlineedit'e yazar.
        """
        # DatePickerDialog'un yeni PySide6 versiyonunu kullanıyoruz.
        # (yardimcilar.py'den import edildiğinden emin olun)

        # Mevcut tarihi al (eğer varsa) ve diyaloğa gönder
        initial_date_str = target_entry_qlineedit.text() if target_entry_qlineedit.text() else None

        dialog = DatePickerDialog(self.app, initial_date_str) # parent: self.app (ana uygulama penceresi)

        # Diyalogtan tarih seçildiğinde (date_selected sinyali)
        # QLineEdit'in setText metoduna bağlanır.
        dialog.date_selected.connect(target_entry_qlineedit.setText)

        # Diyaloğu modal olarak çalıştır
        dialog.exec()

    def _delayed_siparis_listesi_yukle(self): # event=None kaldırıldı
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.siparis_listesini_yukle)

    def _yukle_filtre_comboboxlari(self):
        cari_display_values = ["TÜMÜ"]
        self.cari_filter_map = {"TÜMÜ": None}
        kullanici_id = self.app.current_user_id # Düzeltme: kullanıcı ID'si alındı

        try:
            # Düzeltme: musteri_listesi_al metoduna kullanici_id parametresi eklendi
            musteriler = self.cari_service.musteri_listesi_al(kullanici_id=kullanici_id, limit=10000)
            
            # Gelen verinin türüne göre döngüyü ayarlıyoruz
            if isinstance(musteriler, dict) and 'items' in musteriler:
                musteriler_list = musteriler.get("items", [])
            elif isinstance(musteriler, list):
                musteriler_list = musteriler
            else:
                musteriler_list = []
                self.app.set_status_message(f"Hata: Müşteri listesi API yanıt formatı hatalı.", "red")
                logger.warning(f"Müşteri listesi yüklenirken hata: API'den beklenmeyen yanıt formatı. Yanıt: {musteriler}")

            for m in musteriler_list:
                if isinstance(m, dict):
                    display_text = f"{m.get('ad', '')} (M: {m.get('kod', '')})"
                    self.cari_filter_map[display_text] = m.get('id')
                    cari_display_values.append(display_text)
                else: # SQLAlchemy nesnesi
                    display_text = f"{m.ad} (M: {m.kod})"
                    self.cari_filter_map[display_text] = m.id
                    cari_display_values.append(display_text)

        except Exception as e:
            logger.warning(f"Müşteri listesi yüklenirken hata: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Müşteri listesi alınamadı - {e}")

        try:
            # Düzeltme: tedarikci_listesi_al metoduna kullanici_id parametresi eklendi
            tedarikciler = self.cari_service.tedarikci_listesi_al(kullanici_id=kullanici_id, limit=10000)
            
            # Gelen verinin türüne göre döngüyü ayarlıyoruz
            if isinstance(tedarikciler, dict) and 'items' in tedarikciler:
                tedarikciler_list = tedarikciler.get("items", [])
            elif isinstance(tedarikciler, list):
                tedarikciler_list = tedarikciler
            else:
                tedarikciler_list = []
                self.app.set_status_message(f"Hata: Tedarikçi listesi API yanıt formatı hatalı.", "red")
                logger.warning(f"Tedarikçi listesi yüklenirken hata: API'den beklenmeyen yanıt formatı. Yanıt: {tedarikciler}")

            for t in tedarikciler_list:
                if isinstance(t, dict):
                    display_text = f"{t.get('ad', '')} (T: {t.get('kod', '')})"
                    self.cari_filter_map[display_text] = t.get('id')
                    cari_display_values.append(display_text)
                else: # SQLAlchemy nesnesi
                    display_text = f"{t.ad} (T: {t.kod})"
                    self.cari_filter_map[display_text] = t.id
                    cari_display_values.append(display_text)

        except Exception as e:
            logger.warning(f"Tedarikçi listesi yüklenirken hata: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Tedarikçi listesi alınamadı - {e}")

        self.cari_filter_cb.clear()
        self.cari_filter_cb.addItem("TÜMÜ", userData=None)
        sorted_cari_display_values = sorted([v for v in cari_display_values if v != "TÜMÜ"])
        self.cari_filter_cb.addItems(sorted(list(set(sorted_cari_display_values)))) # Düzeltme: Benzersiz öğeler eklendi
        self.cari_filter_cb.setCurrentText("TÜMÜ")

        self.durum_combo.setCurrentText("TÜMÜ")
        self.siparis_tipi_filter_cb.setCurrentText("TÜMÜ")

    def _on_siparis_select(self): # event=None kaldırıldı
        selected_items = self.siparis_tree.selectedItems()
        if selected_items:
            # Durum sütunu 7. sırada (indeks 6)
            durum = selected_items[0].text(6) 
            self.detay_goster_button.setEnabled(True)
            self.sil_button.setEnabled(True)
            
            # TAMAMLANDI veya İPTAL EDİLDİ ise Düzenle ve Faturaya Dönüştür pasif olsun
            if durum == 'TAMAMLANDI' or durum == 'İPTAL_EDİLDİ':
                self.duzenle_button.setEnabled(False)
                self.faturaya_donustur_button.setEnabled(False)
            else: # BEKLEMEDE veya KISMİ_TESLİMAT ise aktif olsun
                self.duzenle_button.setEnabled(True)
                self.faturaya_donustur_button.setEnabled(True)
        else:
            self.detay_goster_button.setEnabled(False)
            self.duzenle_button.setEnabled(False)
            self.faturaya_donustur_button.setEnabled(False)
            self.sil_button.setEnabled(False)

    def _arama_temizle(self):
        self.arama_siparis_entry.clear()
        self.cari_filter_cb.setCurrentText("TÜMÜ")
        self.durum_filter_cb.setCurrentText("TÜMÜ")
        self.siparis_tipi_filter_cb.setCurrentText("TÜMÜ")
        self.siparis_listesini_yukle()

    def siparis_listesini_yukle(self):
        self.app.set_status_message("Sipariş listesi güncelleniyor...")
        self.siparis_tree.clear()

        bas_t = self.bas_tarih_entry.text()
        bit_t = self.bit_tarih_entry.text()
        arama_terimi = self.arama_siparis_entry.text().strip()

        cari_id_filter_val = self.cari_filter_cb.currentData()
        durum_filter_val = self.durum_combo.currentText() if self.durum_combo.currentText() != "TÜMÜ" else None
        siparis_tipi_filter_val = self.siparis_tipi_filter_cb.currentText() if self.siparis_tipi_filter_cb.currentText() != "TÜMÜ" else None
        
        try:
            siparisler_response = self.db.siparis_listesi_al(
                skip=(self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa,
                limit=self.kayit_sayisi_per_sayfa,
                arama=arama_terimi,
                siparis_turu=siparis_tipi_filter_val,
                durum=durum_filter_val,
                baslangic_tarihi=bas_t,
                bitis_tarihi=bit_t,
                cari_id=cari_id_filter_val
            )

            if not isinstance(siparisler_response, dict) or "items" not in siparisler_response:
                raise ValueError("API'den geçersiz sipariş listesi yanıtı alındı.")

            siparis_verileri = siparisler_response.get("items", [])
            self.toplam_kayit_sayisi = siparisler_response.get("total", len(siparis_verileri))

            self.total_pages = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
            if self.total_pages == 0: self.total_pages = 1

            if self.mevcut_sayfa > self.total_pages:
                self.mevcut_sayfa = self.total_pages
            
            self.sayfa_bilgisi_label.setText(f"Sayfa {self.mevcut_sayfa} / {self.total_pages}")
            
            for item in siparis_verileri:
                siparis_id = item.get('id')
                siparis_no = item.get('siparis_no')
                tarih_obj = item.get('tarih')
                cari_adi_display = item.get('cari_adi', 'Bilinmiyor')
                siparis_tipi_gosterim = item.get('siparis_turu', '-')
                toplam_tutar = item.get('toplam_tutar')
                durum = item.get('durum')
                teslimat_tarihi_obj = item.get('teslimat_tarihi')
                
                formatted_tarih = tarih_obj.strftime('%d.%m.%Y') if isinstance(tarih_obj, (date, datetime)) else str(tarih_obj or "")
                formatted_teslimat_tarihi = teslimat_tarihi_obj.strftime('%d.%m.%Y') if isinstance(teslimat_tarihi_obj, (date, datetime)) else (teslimat_tarihi_obj or "-")

                item_qt = QTreeWidgetItem(self.siparis_tree)
                item_qt.setText(0, str(siparis_id))
                item_qt.setText(1, siparis_no)
                item_qt.setText(2, formatted_tarih)
                item_qt.setText(3, cari_adi_display)
                item_qt.setText(4, siparis_tipi_gosterim)
                item_qt.setText(5, self.db._format_currency(toplam_tutar))
                item_qt.setText(6, durum)
                item_qt.setText(7, formatted_teslimat_tarihi)

                if durum == 'TAMAMLANDI':
                    for col_idx in range(self.siparis_tree.columnCount()):
                        item_qt.setBackground(col_idx, QBrush(QColor("#D5F5E3")))
                        item_qt.setForeground(col_idx, QBrush(QColor("green")))
                elif durum in ['BEKLEMEDE', 'KISMİ_TESLİMAT']:
                    for col_idx in range(self.siparis_tree.columnCount()):
                        item_qt.setBackground(col_idx, QBrush(QColor("#FCF3CF")))
                        item_qt.setForeground(col_idx, QBrush(QColor("#874F15")))
                elif durum == 'İPTAL_EDİLDİ':
                    for col_idx in range(self.siparis_tree.columnCount()):
                        item_qt.setBackground(col_idx, QBrush(QColor("#FADBD8")))
                        item_qt.setForeground(col_idx, QBrush(QColor("gray")))
                        font = item_qt.font(col_idx)
                        font.setStrikeOut(True)
                        item_qt.setFont(col_idx, font)

                item_qt.setData(0, Qt.UserRole, siparis_id)
                item_qt.setData(5, Qt.UserRole, toplam_tutar)

            self.app.set_status_message(f"{len(siparis_verileri)} sipariş listelendi. Toplam {self.toplam_kayit_sayisi} kayıt.")
            self._on_siparis_select()
        except Exception as e:
            logger.error(f"Sipariş listesi yüklenirken hata oluştu: {e}", exc_info=True)
            QMessageBox.critical(self.app, "API Hatası", f"Sipariş listesi çekilirken hata: {e}")
            self.app.set_status_message(f"Hata: Sipariş listesi yüklenemedi. {e}", "red")

    def on_item_double_click(self, item, column): # item ve column sinyalden gelir
        QMessageBox.information(self.app, "Bilgi", "Bu işlem bir fatura değildir, detayı görüntülenemez (Placeholder).")

    def yeni_siparis_penceresi_ac(self, siparis_tipi):
        try:
            from pencereler import SiparisPenceresi
            
            siparis_penceresi = SiparisPenceresi(
                self.app,
                self.db,
                self.app,
                siparis_tipi,
                siparis_id_duzenle=None,
                yenile_callback=self.siparis_listesini_yukle
            )
            # DÜZELTİLDİ: Pencerenin başarılı bir şekilde kaydedilmesi durumunda listeyi yenile
            if siparis_penceresi.exec() == QDialog.Accepted:
                self.siparis_listesini_yukle()
            
            self.app.set_status_message(f"Yeni {siparis_tipi.lower().replace('_', ' ')} penceresi açıldı.") 

        except ImportError:
            QMessageBox.critical(self.app, "Hata", "SiparisPenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message(f"Hata: Yeni {siparis_tipi.lower().replace('_', ' ')} penceresi açılamadı.") 
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Yeni sipariş penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Yeni sipariş penceresi açılamadı - {e}")

    def secili_siparis_detay_goster(self):
        selected_items = self.siparis_tree.selectedItems()
        if not selected_items:
            self.app.set_status_message("Lütfen detaylarını görmek istediğiniz siparişi seçin.")
            return

        selected_item = selected_items[0]
        siparis_id = selected_item.data(0, Qt.UserRole)

        try:
            from pencereler import SiparisDetayPenceresi
            dialog = SiparisDetayPenceresi(self.app, self.db, siparis_id=siparis_id, app_ref=self.app)
            dialog.exec()
            self.app.set_status_message(f"Sipariş ID: {siparis_id} için detay penceresi açıldı.")
        except Exception as e:
            logger.error(f"Sipariş detayları çekilirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Sipariş detayları yüklenemedi. {e}", "red")

    def on_double_click_detay_goster(self, item, column): # item ve column sinyalden gelir
        self.secili_siparis_detay_goster()

    def secili_siparisi_duzenle(self):
        selected_items = self.siparis_tree.selectedItems()
        if not selected_items:
            self.app.set_status_message("Lütfen düzenlemek istediğiniz siparişi seçin.")
            return

        selected_item = selected_items[0]
        siparis_id = selected_item.data(0, Qt.UserRole)
        
        try:
            siparis_data = self.db.siparis_getir_by_id(siparis_id=siparis_id, kullanici_id=self.app.current_user_id)
            
            if not siparis_data:
                self.app.set_status_message(f"Hata: ID {siparis_id} olan sipariş bulunamadı.", "red")
                return
        except Exception as e:
            logger.error(f"Sipariş bilgileri çekilirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Sipariş bilgileri yüklenemedi. {e}", "red")
            return

        from pencereler import SiparisPenceresi

        siparis_tipi_db = siparis_data.get('siparis_turu', '-')

        dialog = SiparisPenceresi(
            parent=self.app,
            db_manager=self.db,
            app_ref=self.app,
            siparis_tipi=siparis_tipi_db,
            siparis_id_duzenle=siparis_id,
            yenile_callback=self.siparis_listesini_yukle
        )
        if dialog.exec() == QDialog.Accepted:
            self.siparis_listesini_yukle()

    def secili_siparisi_faturaya_donustur(self):
        selected_items = self.siparis_tree.selectedItems()
        if not selected_items:
            self.app.set_status_message("Lütfen faturaya dönüştürmek istediğiniz siparişi seçin.")
            return

        selected_item = selected_items[0]
        siparis_id = selected_item.data(0, Qt.UserRole)
        siparis_no = selected_item.text(1)

        try:
            # YENİ KOD: Sipariş detaylarını yerel veritabanından çekiyoruz.
            with lokal_db_servisi.get_db() as db:
                siparis_detay = db.query(Siparis).filter(Siparis.id == siparis_id).first()
                if not siparis_detay:
                    self.app.set_status_message(f"Hata: ID {siparis_id} olan sipariş yerel veritabanında bulunamadı.", "red")
                    return
        except Exception as e:
            logger.error(f"Sipariş detayları yerel veritabanından çekilirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Sipariş detayları yüklenemedi. {e}")
            return
            
        from pencereler import OdemeTuruSecimDialog
        dialog = OdemeTuruSecimDialog(
            self.app,
            db_manager=self.db,
            islem_tipi="FATURA",
            islem_turu=siparis_detay.siparis_turu,
            cari_id=siparis_detay.cari_id
        )
        if dialog.exec() == QDialog.Accepted:
            odeme_turu, kasa_banka_id, vade_tarihi = dialog.get_data()

            # Dönüşüm işlemini API'ye gönder
            try:
                # API çağrısı için gerekli verileri topla
                api_data = {
                    "odeme_turu": odeme_turu,
                    "kasa_banka_id": kasa_banka_id,
                    "vade_tarihi": vade_tarihi.strftime('%Y-%m-%d') if vade_tarihi else None,
                    "olusturan_kullanici_id": 1 # Varsayılan kullanıcı ID'si
                }
                
                # FaturaServisi üzerinden API çağrısı
                success, message = self.app.fatura_servisi.siparis_faturaya_donustur(siparis_id, api_data)
                
                if success:
                    QMessageBox.information(self.app, "Başarılı", message)
                    # DÜZELTİLDİ: Listeleri yerel veritabanından yenile
                    self.siparis_listesini_yukle()
                    self.app.fatura_listesi_sayfasi.fatura_listesini_yukle()
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self.app, "Hata", message)
                    self.app.set_status_message(f"Sipariş faturaya dönüştürme başarısız: {message}")
            
            except Exception as e:
                logger.error(f"Siparişi faturaya dönüştürürken beklenmeyen bir hata oluştu: {e}", exc_info=True)
                QMessageBox.critical(self.app, "Kritik Hata", f"Siparişi faturaya dönüştürürken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: Siparişi faturaya dönüştürme - {e}")

    def _on_fatura_donustur_dialog_closed(self, siparis_id, s_no, odeme_turu, kasa_banka_id, vade_tarihi):
        """
        OdemeTuruSecimDialog kapatıldığında ve onaylandığında çağrılır.
        Siparişi faturaya dönüştürme işlemini başlatır.
        """
        if odeme_turu is None: # Kullanıcı iptal ettiyse
            self.app.set_status_message("Siparişi faturaya dönüştürme işlemi iptal edildi.")
            return

        confirm_msg = (f"'{s_no}' numaralı siparişi '{odeme_turu}' ödeme türü ile faturaya dönüştürmek istediğinizden emin misiniz?\n"
                       f"Bu işlem sonucunda yeni bir fatura oluşturulacak ve sipariş durumu güncellenecektir.")
        if odeme_turu == "AÇIK HESAP" and vade_tarihi:
            confirm_msg += f"\nVade Tarihi: {vade_tarihi}"
        if kasa_banka_id:
            # Kasa/banka adını almak için API'ye istek atabiliriz, şimdilik ID ile idare edelim.
            # Veya bu bilgi OdemeTuruSecimDialog'dan da döndürülebilir.
            confirm_msg += f"\nİşlem Kasa/Banka ID: {kasa_banka_id}"

        reply = QMessageBox.question(self.app, "Faturaya Dönüştür Onayı", confirm_msg,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # Kullanıcı ID'sini al (Örnek olarak self.app.current_user[0] veya bir varsayılan)
                olusturan_kullanici_id = self.app.current_user[0] if hasattr(self.app, 'current_user') and self.app.current_user else 1 # Varsayılan olarak 1 (admin)
                
                # FaturaService üzerinden API çağrısı
                # NOT: hizmetler.py içindeki FaturaService.siparis_faturaya_donustur metodu API'den çağrılmıyor.
                # Bu kısım API backend'ine eklenmeli ve requests.post ile çağrılmalıdır.
                # Şimdilik direkt hizmetler.py metodunu çağırıyoruz.

                # FaturaService bir veritabanı yöneticisiyle başlatıldığı için ona erişmemiz gerekiyor.
                # self.app.fatura_servisi doğrudan hizmetler.py'deki FaturaService'e bir referans olmalıdır.
                success, message = self.app.fatura_servisi.siparis_faturaya_donustur(
                    siparis_id,
                    olusturan_kullanici_id,
                    odeme_turu,
                    kasa_banka_id,
                    vade_tarihi
                )

                if success:
                    QMessageBox.information(self.app, "Başarılı", message)
                    self.siparis_listesini_yukle() # Sipariş listesini yenile
                    # İlgili Fatura listelerini de yenile
                    if hasattr(self.app, 'fatura_listesi_sayfasi'):
                        if hasattr(self.app.fatura_listesi_sayfasi.satis_fatura_frame, 'fatura_listesini_yukle'):
                            self.app.fatura_listesi_sayfasi.satis_fatura_frame.fatura_listesini_yukle()
                        if hasattr(self.app.fatura_listesi_sayfasi.alis_fatura_frame, 'fatura_listesini_yukle'):
                            self.app.fatura_listesi_sayfasi.alis_fatura_frame.fatura_listesini_yukle()
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self.app, "Hata", message)
                    self.app.set_status_message(f"Siparişi faturaya dönüştürme başarısız: {message}")

            except Exception as e:
                logging.error(f"Siparişi faturaya dönüştürürken beklenmeyen bir hata oluştu: {e}\n{traceback.format_exc()}")
                QMessageBox.critical(self.app, "Kritik Hata", f"Siparişi faturaya dönüştürürken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: Siparişi faturaya dönüştürme - {e}")
        else:
            self.app.set_status_message("Siparişi faturaya dönüştürme işlemi kullanıcı tarafından iptal edildi.")

    def secili_siparisi_sil(self):
        selected_items = self.siparis_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir sipariş seçin.")
            return

        siparis_id = int(selected_items[0].text(0))
        siparis_no = selected_items[0].text(1)

        reply = QMessageBox.question(self.app, "Sipariş Silme Onayı", 
                                     f"'{siparis_no}' numaralı siparişi silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.siparis_sil(siparis_id=siparis_id, kullanici_id=self.app.current_user_id)
                if success:
                    QMessageBox.information(self.app, "Başarılı", message)
                    self.siparis_listesini_yukle()
                    self.app.set_status_message(message) 
                else:
                    QMessageBox.critical(self.app, "Hata", message)
                    self.app.set_status_message(f"Sipariş silme başarısız: {message}", "red")
            except Exception as e:
                QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Sipariş silinirken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Sipariş silinirken hata: {e}", "red")

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.siparis_listesini_yukle()

    def sonraki_sayfa(self):
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0: toplam_sayfa = 1

        if self.mevcut_sayfa < toplam_sayfa:
            self.mevcut_sayfa += 1
            self.siparis_listesini_yukle()

    def _yetkileri_uygula(self):
        """Bu sayfadaki butonları kullanıcının rolüne göre ayarlar."""
        kullanici_rolu = self.current_user.get('rol', 'yok')

        if kullanici_rolu.upper() != 'YONETICI':
            self.yeni_musteri_siparisi_button.setEnabled(False)
            self.yeni_tedarikci_siparisi_button.setEnabled(False)
            self.duzenle_button.setEnabled(False)
            self.faturaya_donustur_button.setEnabled(False)
            self.sil_button.setEnabled(False)
            print("Sipariş Listesi sayfası için personel yetkileri uygulandı.")

class BaseFaturaListesi(QWidget):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.current_user = getattr(self.app, 'current_user', {})
        self.parent = parent
        self.fatura_tipi = fatura_tipi
        self.main_layout = QVBoxLayout(self)

        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)
        self.after_timer.timeout.connect(self.fatura_listesini_yukle)

        self.kayit_sayisi_per_sayfa = 20
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0

        self.cari_filter_map = {"TÜMÜ": None}
        self.odeme_turu_map = {"TÜMÜ": None}
        self.kasa_banka_map = {"TÜMÜ": None}

        # BU KISIM GÜNCELLENDİ
        if self.fatura_tipi == self.db.FATURA_TIP_SATIS:
            self.fatura_tipleri_filter_options = ["TÜMÜ", self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE]
        elif self.fatura_tipi == self.db.FATURA_TIP_ALIS:
            self.fatura_tipleri_filter_options = ["TÜMÜ", self.db.FATURA_TIP_ALIS, self.db.FATURA_TIP_DEVIR_GIRIS, self.db.FATURA_TIP_ALIS_IADE]
        else:
            # Hata durumunda boş bir liste ile başlatıyoruz, bu da uygulamanın çökmesini önler.
            self.fatura_tipleri_filter_options = ["TÜMÜ"]
            self.app.set_status_message(f"Uyarı: Geçersiz fatura tipi ({self.fatura_tipi}) kullanıldı, varsayılan filtreler ayarlandı.", "orange")

        self._create_ui_elements()
        self._yukle_filtre_comboboxlari()
        self.fatura_listesini_yukle()
        self._on_fatura_select()
        self._yetkileri_uygula()

    def _create_ui_elements(self):
        """Tüm UI elemanlarını (filtreler, butonlar, treeview) oluşturan yardımcı metod."""
        filter_top_frame = QFrame(self)
        filter_top_layout = QHBoxLayout(filter_top_frame)
        self.main_layout.addWidget(filter_top_frame)

        filter_top_layout.addWidget(QLabel("Başlangıç Tarihi:"))
        self.bas_tarih_entry = QLineEdit((datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        filter_top_layout.addWidget(self.bas_tarih_entry)

        takvim_button_bas = QPushButton("🗓️")
        takvim_button_bas.setFixedWidth(30)
        takvim_button_bas.clicked.connect(lambda: self._open_date_picker(self.bas_tarih_entry))
        filter_top_layout.addWidget(takvim_button_bas)

        filter_top_layout.addWidget(QLabel("Bitiş Tarihi:"))
        self.bit_tarih_entry = QLineEdit(datetime.now().strftime('%Y-%m-%d'))
        filter_top_layout.addWidget(self.bit_tarih_entry)

        takvim_button_bit = QPushButton("🗓️")
        takvim_button_bit.setFixedWidth(30)
        takvim_button_bit.clicked.connect(lambda: self._open_date_picker(self.bit_tarih_entry))
        filter_top_layout.addWidget(takvim_button_bit)

        filter_top_layout.addWidget(QLabel("Fatura Tipi:"))
        self.fatura_tipi_filter_cb = QComboBox()
        self.fatura_tipi_filter_cb.addItems(self.fatura_tipleri_filter_options)
        
        if self.fatura_tipi == self.db.FATURA_TIP_SATIS:
            self.fatura_tipi_filter_cb.setCurrentText(self.db.FATURA_TIP_SATIS)
        elif self.fatura_tipi == self.db.FATURA_TIP_ALIS:
            self.fatura_tipi_filter_cb.setCurrentText(self.db.FATURA_TIP_ALIS)

        self.fatura_tipi_filter_cb.currentIndexChanged.connect(self.fatura_listesini_yukle)
        filter_top_layout.addWidget(self.fatura_tipi_filter_cb)

        filter_top_layout.addWidget(QLabel("Ara (F.No/Cari/Misafir/Ürün):"))
        self.arama_fatura_entry = QLineEdit()
        self.arama_fatura_entry.setPlaceholderText("Fatura No, Cari Adı, Misafir veya Ürün ara...")
        self.arama_fatura_entry.textChanged.connect(self._delayed_fatura_listesi_yukle)
        filter_top_layout.addWidget(self.arama_fatura_entry)

        temizle_button = QPushButton("Temizle")
        temizle_button.clicked.connect(self._arama_temizle)
        filter_top_layout.addWidget(temizle_button)

        filtre_yenile_button = QPushButton("Filtrele/Yenile")
        filtre_yenile_button.clicked.connect(self.fatura_listesini_yukle)
        filter_top_layout.addWidget(filtre_yenile_button)

        filter_bottom_frame = QFrame(self)
        filter_bottom_layout = QHBoxLayout(filter_bottom_frame)
        self.main_layout.addWidget(filter_bottom_frame)
        
        filter_bottom_layout.addWidget(QLabel("Cari Filtre:"))
        self.cari_filter_cb = QComboBox()
        self.cari_filter_cb.currentIndexChanged.connect(self.fatura_listesini_yukle)
        filter_bottom_layout.addWidget(self.cari_filter_cb)
        
        filter_bottom_layout.addWidget(QLabel("Ödeme Türü:"))
        self.odeme_turu_filter_cb = QComboBox()
        self.odeme_turu_filter_cb.currentIndexChanged.connect(self.fatura_listesini_yukle)
        filter_bottom_layout.addWidget(self.odeme_turu_filter_cb)

        filter_bottom_layout.addWidget(QLabel("Kasa/Banka:"))
        self.kasa_banka_filter_cb = QComboBox()
        self.kasa_banka_filter_cb.currentIndexChanged.connect(self.fatura_listesini_yukle)
        filter_bottom_layout.addWidget(self.kasa_banka_filter_cb)

        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        self.main_layout.addWidget(button_frame)

        self.btn_fatura_detay = QPushButton("Seçili Fatura Detayları")
        self.btn_fatura_detay.clicked.connect(self.secili_fatura_detay_goster)
        button_layout.addWidget(self.btn_fatura_detay)

        self.btn_fatura_pdf_yazdir = QPushButton("Seçili Faturayı PDF Yazdır")
        self.btn_fatura_pdf_yazdir.clicked.connect(self.secili_faturayi_yazdir)
        button_layout.addWidget(self.btn_fatura_pdf_yazdir)

        self.btn_fatura_guncelle = QPushButton("Seçili Faturayı Güncelle")
        self.btn_fatura_guncelle.clicked.connect(self.secili_faturayi_guncelle)
        button_layout.addWidget(self.btn_fatura_guncelle)

        self.btn_fatura_sil = QPushButton("Seçili Faturayı Sil")
        self.btn_fatura_sil.clicked.connect(self.secili_faturayi_sil)
        button_layout.addWidget(self.btn_fatura_sil)

        self.btn_iade_faturasi = QPushButton("İade Faturası Oluştur")
        if hasattr(self.parent, '_iade_faturasi_olustur_ui'):
            self.btn_iade_faturasi.clicked.connect(self.parent._iade_faturasi_olustur_ui)
        button_layout.addWidget(self.btn_iade_faturasi)

        pagination_frame = QFrame(self)
        pagination_layout = QHBoxLayout(pagination_frame)
        self.main_layout.addWidget(pagination_frame)

        onceki_sayfa_button = QPushButton("Önceki Sayfa")
        onceki_sayfa_button.clicked.connect(self.onceki_sayfa)
        pagination_layout.addWidget(onceki_sayfa_button)

        self.sayfa_bilgisi_label = QLabel("Sayfa 1 / 1")
        pagination_layout.addWidget(self.sayfa_bilgisi_label)

        sonraki_sayfa_button = QPushButton("Sonraki Sayfa")
        sonraki_sayfa_button.clicked.connect(self.sonraki_sayfa)
        pagination_layout.addWidget(sonraki_sayfa_button)

        # Güncellendi: Daha iyi okunabilirlik için sütun başlıkları ve boyutları ayarlandı
        cari_adi_col_text = "Cari Adı"
        cols = ("ID", "Fatura No", "Tarih", cari_adi_col_text, "Fatura Tipi", "Ödeme Türü", "Toplam", "Vade Tarihi")
        self.fatura_tree = QTreeWidget(self)
        self.fatura_tree.setHeaderLabels(cols)
        self.fatura_tree.setColumnCount(len(cols))
        self.fatura_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.fatura_tree.setSortingEnabled(True)

        col_definitions = [
            ("ID", 40, Qt.AlignCenter, QHeaderView.ResizeToContents),
            ("Fatura No", 120, Qt.AlignCenter, QHeaderView.Interactive),
            ("Tarih", 85, Qt.AlignCenter, QHeaderView.Interactive),
            (cari_adi_col_text, 250, Qt.AlignCenter, QHeaderView.Stretch),
            ("Fatura Tipi", 120, Qt.AlignCenter, QHeaderView.Interactive),
            ("Ödeme Türü", 120, Qt.AlignCenter, QHeaderView.Interactive),
            ("Toplam", 110, Qt.AlignCenter, QHeaderView.Interactive),
            ("Vade Tarihi", 90, Qt.AlignCenter, QHeaderView.Interactive),
        ]
        
        for i, (col_name, width, alignment, resize_mode) in enumerate(col_definitions):
            self.fatura_tree.setColumnWidth(i, width)
            self.fatura_tree.headerItem().setTextAlignment(i, alignment)
            self.fatura_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            self.fatura_tree.header().setSectionResizeMode(i, resize_mode)

        self.fatura_tree.itemDoubleClicked.connect(self.on_double_click_detay_goster)
        self.main_layout.addWidget(self.fatura_tree)
        self.fatura_tree.itemSelectionChanged.connect(self._on_fatura_select)

    def _open_date_picker(self, target_entry_qlineedit: QLineEdit):
        from yardimcilar import DatePickerDialog
        initial_date_str = target_entry_qlineedit.text() if target_entry_qlineedit.text() else None
        dialog = DatePickerDialog(self.app, initial_date_str)
        dialog.date_selected.connect(target_entry_qlineedit.setText)
        dialog.exec()

    def _delayed_fatura_listesi_yukle(self):
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.fatura_listesini_yukle)

    def _yukle_filtre_comboboxlari(self):
        self.cari_filter_cb.clear()
        self.cari_filter_map = {"TÜMÜ": None}
        self.odeme_turu_map = {"TÜMÜ": None}
        self.kasa_banka_map = {"TÜMÜ": None}

        self.cari_filter_cb.addItem("TÜMÜ", userData=None)
        self.odeme_turu_filter_cb.addItem("TÜMÜ", userData=None)
        self.kasa_banka_filter_cb.addItem("TÜMÜ", userData=None)
        
        try:
            cariler = []
            if self.fatura_tipi == self.db.FATURA_TIP_SATIS:
                cariler_response = self.db.musteri_listesi_al() 
                cariler = cariler_response.get('items', []) if isinstance(cariler_response, dict) else cariler_response
            elif self.fatura_tipi == self.db.FATURA_TIP_ALIS:
                cariler_response = self.db.tedarikci_listesi_al()
                cariler = cariler_response.get('items', []) if isinstance(cariler_response, dict) else cariler_response

            for cari in cariler:
                cari_id = cari.get('id')
                cari_ad = cari.get('ad', 'Bilinmiyor')
                cari_kod = cari.get('kod', '')
                
                display_text = f"{cari_ad} (Kod: {cari_kod})"
                self.cari_filter_map[display_text] = cari_id
                self.cari_filter_cb.addItem(display_text, cari_id)

            # Ödeme türleri
            for odeme_turu in [self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, self.db.ODEME_TURU_SENET, self.db.ODEME_TURU_ACIK_HESAP, self.db.ODEME_TURU_ETKISIZ_FATURA]:
                self.odeme_turu_map[odeme_turu] = odeme_turu
                self.odeme_turu_filter_cb.addItem(odeme_turu, userData=odeme_turu)

            # Kasa/Banka hesaplarını çekme
            kasalar_bankalar_response = self.db.kasa_banka_listesi_al()
            kasalar_bankalar = kasalar_bankalar_response.get('items', []) if isinstance(kasalar_bankalar_response, dict) else kasalar_bankalar_response
            
            for kb in kasalar_bankalar:
                kb_id = kb.get('id')
                kb_adi = kb.get('hesap_adi', 'Bilinmiyor')
                kb_tip = kb.get('tip', 'Bilinmiyor')
                    
                display_text = f"{kb_adi} ({kb_tip})"
                self.kasa_banka_map[display_text] = kb_id
                self.kasa_banka_filter_cb.addItem(display_text, userData=kb_id)

        except Exception as e:
            self.app.set_status_message(f"Hata: Filtre verileri yüklenemedi: {e}")
            logging.error(f"Filtre verileri yüklenirken hata oluştu: {e}", exc_info=True)

    def _arama_temizle(self):
        self.arama_fatura_entry.clear()
        self.cari_filter_cb.setCurrentIndex(0)
        self.odeme_turu_filter_cb.setCurrentIndex(0)
        self.kasa_banka_filter_cb.setCurrentIndex(0)
        self.fatura_tipi_filter_cb.setCurrentIndex(0)
        self.fatura_listesini_yukle()

    def fatura_listesini_yukle(self):
        self.app.set_status_message("Fatura listesi güncelleniyor...")
        self.fatura_tree.clear()
        self.sayfa_bilgisi_label.setText("Sayfa 0 / 0")

        try:
            fatura_listesi_response = self.db.fatura_listesi_al(
                arama=self.arama_fatura_entry.text(),
                fatura_turu=self.fatura_tipi_filter_cb.currentText() if self.fatura_tipi_filter_cb.currentText() != "TÜMÜ" else None,
                odeme_turu=self.odeme_turu_filter_cb.currentData(),
                baslangic_tarihi=self.bas_tarih_entry.text(),
                bitis_tarihi=self.bit_tarih_entry.text(),
                kasa_banka_id=self.kasa_banka_filter_cb.currentData()
            )

            if not isinstance(fatura_listesi_response, dict) or "items" not in fatura_listesi_response:
                raise ValueError("API'den geçersiz fatura listesi yanıtı alındı.")
            
            faturalar = fatura_listesi_response.get("items", [])
            self.toplam_kayit_sayisi = fatura_listesi_response.get("total", len(faturalar))
            
            toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
            if toplam_sayfa == 0: toplam_sayfa = 1

            if self.mevcut_sayfa > toplam_sayfa:
                self.mevcut_sayfa = toplam_sayfa

            self.sayfa_bilgisi_label.setText(f"Sayfa {self.mevcut_sayfa} / {toplam_sayfa}")

            for fatura in faturalar:
                item_qt = QTreeWidgetItem(self.fatura_tree)
                item_qt.setData(0, Qt.UserRole, fatura.get('id', -1))
                item_qt.setText(0, str(fatura.get('id', '')))
                item_qt.setText(1, fatura.get('fatura_no', '-'))
                tarih_obj = fatura.get('tarih')
                item_qt.setText(2, tarih_obj.strftime('%d.%m.%Y') if isinstance(tarih_obj, (datetime, date)) else str(tarih_obj or ""))
                
                cari_adi_display = fatura.get('cari_adi', 'Misafir') if fatura.get('misafir_adi') else fatura.get('cari_adi', 'Bilinmiyor')
                item_qt.setText(3, cari_adi_display)
                
                item_qt.setText(4, fatura.get('fatura_turu', '-'))
                item_qt.setText(5, fatura.get('odeme_turu', '-'))
                item_qt.setText(6, self.db._format_currency(fatura.get('genel_toplam', 0.0)))
                
                vade_tarihi_obj = fatura.get('vade_tarihi')
                vade_tarihi_str = vade_tarihi_obj.strftime('%d.%m.%Y') if isinstance(vade_tarihi_obj, (datetime, date)) else (str(vade_tarihi_obj or '-'))
                item_qt.setText(7, vade_tarihi_str)
                
                for col_idx in range(self.fatura_tree.columnCount()):
                    item_qt.setTextAlignment(col_idx, Qt.AlignCenter)

            self.app.set_status_message(f"{len(faturalar)} fatura listelendi. Toplam {self.toplam_kayit_sayisi} kayıt.", "blue")
            self._on_fatura_select()

        except Exception as e:
            logger.error(f"Fatura listesi yüklenirken hata: {e}", exc_info=True)
            QMessageBox.critical(self.app, "Veri Yükleme Hatası", f"Fatura listesi yüklenirken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Fatura listesi yüklenemedi. {e}", "red")
            
    def _on_fatura_select(self):
        selected_items = self.fatura_tree.selectedItems()
        is_selected = bool(selected_items)
        self.btn_fatura_detay.setEnabled(is_selected)
        self.btn_fatura_sil.setEnabled(is_selected)
        self.btn_iade_faturasi.setEnabled(is_selected)
        self.btn_fatura_guncelle.setEnabled(is_selected)
        self.btn_fatura_pdf_yazdir.setEnabled(is_selected)

    def secili_fatura_detay_goster(self):
        selected_items = self.fatura_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen detaylarını görmek için bir fatura seçin.")
            return

        selected_item = selected_items[0]
        fatura_id = int(selected_item.data(0, Qt.UserRole))

        if fatura_id == -1:
            QMessageBox.warning(self, "Uyarı", "Geçersiz bir fatura seçimi yaptınız.")
            return

        try:
            from pencereler import FaturaDetayPenceresi
            fatura_detay_penceresi = FaturaDetayPenceresi(
                self.app,
                self.db,
                fatura_id
            )
            fatura_detay_penceresi.exec()
            self.app.set_status_message(f"Fatura ID: {fatura_id} için detay penceresi açıldı.")
        except ImportError:
            QMessageBox.critical(self.app, "Hata", "FaturaDetayPenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message(f"Hata: Fatura Detay penceresi açılamadı.", "red")
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Fatura Detay penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Fatura Detay penceresi açılamadı - {e}", "red")

    def on_double_click_detay_goster(self, item, column):
        fatura_id = int(item.text(0))
        self.secili_fatura_detay_goster()

    def secili_faturayi_yazdir(self):
        selected_items = self.fatura_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen PDF olarak yazdırmak için bir fatura seçin.")
            return

        selected_item = selected_items[0]
        fatura_id = int(selected_item.data(0, Qt.UserRole))
        fatura_no = selected_item.text(1)
        fatura_tipi = selected_item.text(4)

        if fatura_id == -1:
            QMessageBox.warning(self, "Uyarı", "Geçersiz bir fatura seçimi yaptınız.")
            return

        initial_file_name = f"{fatura_tipi.replace(' ', '')}_Faturasi_{fatura_no.replace('/', '-')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self.app,
                                                "Faturayı PDF olarak kaydet",
                                                initial_file_name,
                                                "PDF Dosyaları (*.pdf);;Tüm Dosyalar (*)")

        if file_path:
            try:
                success, message = self.db.fatura_pdf_olustur(fatura_id=fatura_id, file_path=file_path, result_queue=multiprocessing.Queue(), kullanici_id=self.app.current_user_id)

                if success:
                    QMessageBox.information(self, "Başarılı", message)
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self, "Hata", message)
                    self.app.set_status_message(f"PDF yazdırma başarısız: {message}", "red")

            except Exception as e:
                logging.error(f"Faturayı PDF olarak yazdırırken beklenmeyen bir hata oluştu: {e}", exc_info=True)
                QMessageBox.critical(self, "Kritik Hata", f"Faturayı PDF olarak yazdırırken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: PDF yazdırma - {e}", "red")
        else:
            self.app.set_status_message("PDF kaydetme işlemi iptal edildi.")

    def secili_faturayi_sil(self):
        selected_items = self.fatura_tree.selectedItems()
        if not selected_items:
            self.app.set_status_message("Lütfen silmek istediğiniz ürünü seçin.", "orange")
            return

        selected_item = selected_items[0]
        fatura_id = int(selected_item.data(0, Qt.UserRole))
        fatura_no = selected_item.text(1)
        fatura_tipi = selected_item.text(4)

        if fatura_id == -1:
            QMessageBox.warning(self, "Uyarı", "Geçersiz bir fatura seçimi yaptınız.")
            return

        reply = QMessageBox.question(self, "Fatura Silme Onayı",
                                    f"'{fatura_no}' numaralı {fatura_tipi} faturasını silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz!",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.fatura_sil(fatura_id=fatura_id, kullanici_id=self.app.current_user_id)
                if success:
                    QMessageBox.information(self, "Başarılı", f"'{fatura_no}' numaralı fatura başarıyla silindi.")
                    self.fatura_listesini_yukle()
                    self.app.set_status_message(f"'{fatura_no}' numaralı fatura başarıyla silindi.")
                else:
                    QMessageBox.critical(self, "Hata", f"Fatura silinirken bir hata oluştu.")
                    self.app.set_status_message(f"Fatura silme başarısız.", "red")
            except Exception as e:
                logging.error(f"Fatura silinirken bir hata oluştu: {e}", exc_info=True)
                QMessageBox.critical(self, "Hata", f"Fatura silinirken bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Fatura silme başarısız: {e}", "red")
        else:
            self.app.set_status_message("Fatura silme işlemi kullanıcı tarafından iptal edildi.")
            
    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.fatura_listesini_yukle()
        else:
            self.app.set_status_message("İlk sayfadasınız.", "orange")

    def sonraki_sayfa(self):
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0: toplam_sayfa = 1

        if self.mevcut_sayfa < toplam_sayfa:
            self.mevcut_sayfa += 1
            self.fatura_listesini_yukle()
        else:
            self.app.set_status_message("Son sayfadasınız.", "orange")

    def secili_faturayi_guncelle(self):
        selected_items = self.fatura_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir fatura seçin.")
            return

        selected_item = selected_items[0]
        fatura_id = int(selected_item.data(0, Qt.UserRole))

        if fatura_id == -1:
            QMessageBox.warning(self, "Uyarı", "Geçersiz bir fatura seçimi yaptınız.")
            return

        try:
            fatura_data = self.db.fatura_getir_by_id(fatura_id=fatura_id, kullanici_id=self.app.current_user_id)
            if not fatura_data:
                QMessageBox.critical(self.app, "Hata", "Fatura detayları çekilirken bir hata oluştu.")
                self.app.set_status_message("Fatura güncelleme hatası: Detaylar alınamadı.", "red")
                return
            
            from pencereler import FaturaGuncellemePenceresi
            fatura_guncelle_penceresi = FaturaGuncellemePenceresi(
                self.app,
                self.db,
                fatura_id,
                yenile_callback_liste=self.fatura_listesini_yukle
            )
            fatura_guncelle_penceresi.exec()
        except ImportError:
            QMessageBox.critical(self.app, "Hata", "FaturaGuncellemePenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message(f"Hata: Fatura Güncelleme penceresi açılamadı.", "red")
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Fatura Güncelleme penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Fatura Güncelleme penceresi açılamadı - {e}", "red")

    def _yetkileri_uygula(self):
        """Bu sayfadaki butonları kullanıcının rolüne göre ayarlar."""
        kullanici_rolu = self.current_user.get('rol', 'yok')

        if kullanici_rolu.upper() != 'YONETICI':
            # Butonlar _create_ui_elements içinde self'e atanmıştı
            if hasattr(self, 'btn_fatura_guncelle'):
                self.btn_fatura_guncelle.setEnabled(False)
            
            if hasattr(self, 'btn_fatura_sil'):
                self.btn_fatura_sil.setEnabled(False)
            
            if hasattr(self, 'btn_iade_faturasi'):
                self.btn_iade_faturasi.setEnabled(False) # İade de bir nevi yeni fatura oluşturmaktır
            
            print(f"Fatura Listesi ({self.fatura_tipi}) sayfası için personel yetkileri uygulandı.")

class SatisFaturalariListesi(BaseFaturaListesi):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        super().__init__(parent, db_manager, app_ref, fatura_tipi=fatura_tipi)

class AlisFaturalariListesi(BaseFaturaListesi):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        super().__init__(parent, db_manager, app_ref, fatura_tipi=fatura_tipi)
        
class TumFaturalarListesi(QWidget): # BaseFaturaListesi'nden değil, QWidget'ten miras alıyor.
    def __init__(self, parent, db_manager, app_ref, fatura_tipi):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.fatura_tipi = fatura_tipi
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(QLabel(f"Tüm Faturalar Listesi ({fatura_tipi}) (Placeholder)"))
        self.fatura_listesini_yukle = lambda: print(f"Tüm Fatura Listesini Yükle ({fatura_tipi}) (Placeholder)") # Yer tutucu

class BaseIslemSayfasi(QWidget):
    # Sinaller, parent pencerenin aksiyon alması için tanımlanır.
    saved_successfully = Signal()
    cancelled_successfully = Signal()

    def __init__(self, parent, db_manager, app_ref, islem_tipi, duzenleme_id=None, yenile_callback=None, initial_cari_id=None, initial_urunler=None, initial_data=None, **kwargs):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.parent = parent
        self.islem_tipi = islem_tipi
        self.duzenleme_id = duzenleme_id
        self.yenile_callback = yenile_callback
        self.initial_cari_id = initial_cari_id
        self.initial_urunler = initial_urunler
        self.initial_data = initial_data

        # Ortak Değişkenler
        self.fatura_kalemleri_ui = []
        self.tum_urunler_cache = []
        self.urun_map_filtrelenmis = {}
        self.kasa_banka_map = {}
        self.tum_cariler_cache_data = []
        self.cari_map_display_to_id = {}
        self.cari_id_to_display_map = {}
        self.secili_cari_id = None
        self.secili_cari_adi = None
        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)
        self.after_timer.timeout.connect(self._urun_listesini_filtrele_anlik)
        
        # UI elemanlarının oluşturulması ve düzenlenmesi
        self.main_layout = QGridLayout(self)
        
        # UI panellerini oluşturan ana metot
        self._setup_paneller()

    def _bind_keyboard_navigation(self):
        """
        Formdaki klavye navigasyonunu sağlar (TAB ile gezinme sırasını ayarlar).
        Hata vermemesi için sadece ana bileşenler arasında geçişi ayarlıyoruz.
        """
        # Bu metodun, FaturaOlusturmaSayfasi'na özel `self.f_no_e` gibi bileşenlere
        # doğrudan erişememesi gerekir. Bu yüzden bu metodu BaseIslemSayfasi'ndan kaldırıyoruz.
        pass

    # --- ABSTRACT METHODS (Alt sınıflar tarafından doldurulacak) ---
    def _get_baslik(self):
        raise NotImplementedError("Bu metot alt sınıf tarafından ezilmelidir.")
        
    def _setup_ozel_alanlar(self, parent_frame):
        raise NotImplementedError("Bu metot alt sınıf tarafından ezilmelidir.")

    def _load_initial_data(self):
        raise NotImplementedError("Bu metodun her alt sınıfta özel olarak uygulanması gerekmektedir.")

    def kaydet(self):
        """
        Faturayı/Siparişi ve ilişkili kalemlerini kaydeder veya günceller.
        Bu metodun alt sınıflar tarafından override edilmesi beklenir.
        """
        raise NotImplementedError("Bu metot alt sınıf tarafından ezilmelidir.")
        
    def _iptal_et(self):
        """Formu kapatır ve geçici veriyi temizler."""
        reply = QMessageBox.question(self.app, "İptal Onayı", "Sayfadaki tüm bilgileri kaydetmeden kapatmak istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # İptal edildiğinde ilgili taslak verisini temizle (App sınıfında tutuluyorsa)
            if hasattr(self.app, 'temp_sales_invoice_data') and self.islem_tipi == 'SATIŞ': self.app.temp_sales_invoice_data = None
            elif hasattr(self.app, 'temp_purchase_invoice_data') and self.islem_tipi == 'ALIŞ': self.app.temp_purchase_invoice_data = None
            elif hasattr(self.app, 'temp_sales_order_data') and self.islem_tipi == 'SATIŞ_SIPARIS': self.app.temp_sales_order_data = None
            elif hasattr(self.app, 'temp_purchase_order_data') and self.islem_tipi == 'ALIŞ_SIPARIS': self.app.temp_purchase_order_data = None

            self.app.set_status_message(f"{self.islem_tipi} işlemi iptal edildi ve taslak temizlendi.")
            if isinstance(self.parent, QDialog):
                 self.parent.reject()
            elif hasattr(self.parent, 'close'):
                self.parent.close()
            else:
                logging.warning("BaseIslemSayfasi: _iptal_et metodu parent'ı kapatamadı. Muhtemelen bir sekme.")
                self._reset_form_explicitly(ask_confirmation=False)

    def _reset_form_explicitly(self, ask_confirmation=True):
        """
        Formu tamamen sıfırlar ve temizler, varsayılan değerleri atar.
        Bu metod, formdaki tüm giriş alanlarını temizler, sepeti sıfırlar ve
        alt sınıfların (Fatura/Sipariş) kendi sıfırlama mantıklarını çağırır.
        """
        if ask_confirmation:
            reply = QMessageBox.question(self.app, "Sıfırlama Onayı", "Sayfadaki tüm bilgileri temizlemek istediğinizden emin misiniz?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return False

        self.fatura_kalemleri_ui = []
        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()

        if hasattr(self, 'f_no_e'): self.f_no_e.clear()
        if hasattr(self, 'fatura_tarihi_entry'): self.fatura_tarihi_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        if hasattr(self, 'entry_misafir_adi'): self.entry_misafir_adi.clear()
        if hasattr(self, 'fatura_notlari_text'): self.fatura_notlari_text.clear()
        if hasattr(self, 'entry_vade_tarihi'): self.entry_vade_tarihi.clear()
        if hasattr(self, 'genel_iskonto_degeri_e'): self.genel_iskonto_degeri_e.setText("0,00")
        if hasattr(self, 'urun_arama_entry'): self.urun_arama_entry.clear()
        if hasattr(self, 'mik_e'): self.mik_e.setText("1")
        if hasattr(self, 'birim_fiyat_e'): self.birim_fiyat_e.setText("0,00")
        if hasattr(self, 'stk_l'): self.stk_l.setText("-")
        if hasattr(self, 'iskonto_yuzde_1_e'): self.iskonto_yuzde_1_e.setText("0,00")
        if hasattr(self, 'iskonto_yuzde_2_e'): self.iskonto_yuzde_2_e.setText("0,00")
        if hasattr(self, 's_no_e'): self.s_no_e.clear()
        if hasattr(self, 'siparis_tarihi_entry'): self.siparis_tarihi_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        if hasattr(self, 'teslimat_tarihi_entry'): self.teslimat_tarihi_entry.setText((datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        if hasattr(self, 'siparis_notlari_text'): self.siparis_notlari_text.clear()
        
        if hasattr(self, 'odeme_turu_cb'): self.odeme_turu_cb.setCurrentText(self.db.ODEME_TURU_NAKIT)
        if hasattr(self, 'islem_hesap_cb'): self.islem_hesap_cb.clear()
        if hasattr(self, 'genel_iskonto_tipi_cb'): self.genel_iskonto_tipi_cb.setCurrentText("YOK")
        if hasattr(self, 'durum_combo'): self.durum_combo.setCurrentText(self.db.SIPARIS_DURUM_BEKLEMEDE)
        
        self._temizle_cari_secimi()

        if self.islem_tipi == self.db.FATURA_TIP_SATIS or self.islem_tipi == self.db.FATURA_TIP_ALIS:
            if hasattr(self, '_reset_form_for_new_invoice'):
                self._reset_form_for_new_invoice(ask_confirmation=False, skip_default_cari_selection=True)

        elif self.islem_tipi == self.db.SIPARIS_TIP_SATIS or self.islem_tipi == self.db.SIPARIS_TIP_ALIS:
            if hasattr(self, '_reset_form_for_new_siparis'):
                self._reset_form_for_new_siparis(ask_confirmation=False, skip_default_cari_selection=True)

        if hasattr(self, '_on_genel_iskonto_tipi_changed'): self._on_genel_iskonto_tipi_changed()
        if hasattr(self, '_odeme_turu_degisince_event_handler'): self._odeme_turu_degisince_event_handler()

        QTimer.singleShot(0, self._urunleri_yukle_ve_cachele_ve_goster)
        
        self.app.set_status_message("Form başarıyla sıfırlandı.")
        self.urun_arama_entry.setFocus()

        return True

    def _setup_paneller(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        header_frame = QFrame(self)
        header_layout = QHBoxLayout(header_frame)
        baslik_label = QLabel(self._get_baslik())
        baslik_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header_layout.addWidget(baslik_label)
        header_layout.addStretch()
        
        self.btn_sayfa_yenile = QPushButton("Sayfayı Yenile")
        self.btn_sayfa_yenile.clicked.connect(self._reset_form_explicitly)
        header_layout.addWidget(self.btn_sayfa_yenile)
        
        self.main_layout.addWidget(header_frame, 0, 0, 1, 2)

        content_frame = QFrame(self)
        content_layout = QGridLayout(content_frame)
        
        self.main_layout.addWidget(content_frame, 1, 0, 1, 2)
        content_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        left_panel_frame = QFrame(content_frame)
        self.left_panel_layout = QVBoxLayout(left_panel_frame)
        content_layout.addWidget(left_panel_frame, 0, 0)
        left_panel_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        right_panel_frame = QFrame(content_frame)
        self.right_panel_layout = QVBoxLayout(right_panel_frame)
        content_layout.addWidget(right_panel_frame, 0, 1)
        right_panel_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        sepet_panel_frame = QFrame(content_frame)
        self.sepet_panel_layout = QVBoxLayout(sepet_panel_frame)
        content_layout.addWidget(sepet_panel_frame, 1, 0, 1, 2)
        sepet_panel_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 1)
        content_layout.setRowStretch(1, 1)

        self._setup_sol_panel(left_panel_frame)

        self._setup_sag_panel(right_panel_frame)

        self._setup_sepet_paneli(sepet_panel_frame)

        self.alt_f = QFrame(self)
        self.main_layout.addWidget(self.alt_f, 2, 0, 1, 2)
        
        self._setup_alt_bar()

    def _yukle_kasa_banka_hesaplarini(self):
        """Kasa/Banka hesaplarını API'den çeker ve ilgili combobox'ı doldurur."""
        try:
            hesaplar_response = self.db.kasa_banka_listesi_al(limit=10000)

            hesaplar = []
            if isinstance(hesaplar_response, dict) and "items" in hesaplar_response:
                hesaplar = hesaplar_response["items"]
            elif isinstance(hesaplar_response, list):
                hesaplar = hesaplar_response
                self.app.set_status_message("Uyarı: Kasa/Banka listesi API yanıtı beklenen formatta değil. Doğrudan liste olarak işleniyor.", "orange")
            else:
                self.app.set_status_message("Hata: Kasa/Banka listesi API'den alınamadı veya formatı geçersiz.", "red")
                logging.error(f"Kasa/Banka listesi API'den beklenen formatta gelmedi: {type(hesaplar_response)} - {hesaplar_response}")
                self.islem_hesap_cb.clear()
                self.islem_hesap_cb.setPlaceholderText("Hesap Yok")
                self.islem_hesap_cb.setEnabled(False)
                return

            self.islem_hesap_cb.clear()
            self.kasa_banka_map.clear()

            display_values = []
            if hesaplar:
                for h in hesaplar:
                    display_text = f"{h.get('hesap_adi')} ({h.get('tip')})"
                    if h.get('tip') == "BANKA" and h.get('banka_adi'):
                        display_text += f" - {h.get('banka_adi')}"
                    if h.get('tip') == "BANKA" and h.get('hesap_no'):
                        display_text += f" ({h.get('hesap_no')})"

                    self.kasa_banka_map[display_text] = h.get('id')
                    display_values.append(display_text)

                self.islem_hesap_cb.addItems(display_values)
                self.islem_hesap_cb.setCurrentIndex(0)
                self.islem_hesap_cb.setEnabled(True)
            else:
                self.islem_hesap_cb.clear()
                self.islem_hesap_cb.setPlaceholderText("Hesap Yok")
                self.islem_hesap_cb.setEnabled(False)

            self.app.set_status_message(f"{len(hesaplar)} kasa/banka hesabı API'den yüklendi.")

        except Exception as e:
            QMessageBox.critical(self.app, "API Bağlantı Hatası", f"Kasa/Banka hesapları API'den alınamadı:\n{e}")
            self.app.set_status_message(f"Hata: Kasa/Banka hesapları yüklenemedi - {e}")

    def _setup_sol_panel(self, parent_frame):
        raise NotImplementedError("Bu metot alt sınıf tarafından ezilmelidir.")

    def _setup_sag_panel(self, parent):
        right_panel_layout = parent.layout()
        urun_ekle_groupbox = QGroupBox("Ürün Ekleme", parent)
        urun_ekle_layout = QGridLayout(urun_ekle_groupbox)
        right_panel_layout.addWidget(urun_ekle_groupbox)
        urun_ekle_layout.addWidget(QLabel("Ürün Ara (Kod/Ad):"), 0, 0)
        self.urun_arama_entry = QLineEdit()
        self.urun_arama_entry.setPlaceholderText("Ürün kodu veya adı ile ara...")
        self.urun_arama_entry.textChanged.connect(self._delayed_stok_yenile)
        urun_ekle_layout.addWidget(self.urun_arama_entry, 0, 1)

        # DEĞİŞİKLİK: Ürün bulunamadığında gösterilecek etiketi ekliyoruz.
        self.lbl_urun_bulunamadi = QLabel("Ürün bulunamadı.")
        self.lbl_urun_bulunamadi.setAlignment(Qt.AlignCenter)
        self.lbl_urun_bulunamadi.setStyleSheet("font-style: italic; color: gray;")
        self.lbl_urun_bulunamadi.setVisible(False) # Başlangıçta gizli
        urun_ekle_layout.addWidget(self.lbl_urun_bulunamadi, 1, 0, 1, 2)
        
        # DÜZELTME: Sütun başlıkları ve genişlik ayarları güncellendi
        self.urun_arama_sonuclari_tree = QTreeWidget()
        self.urun_arama_sonuclari_tree.setHeaderLabels(["Kod", "Ürün Adı", "Stok", "Fiyat"])
        self.urun_arama_sonuclari_tree.setColumnCount(4)
        self.urun_arama_sonuclari_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.urun_arama_sonuclari_tree.setSortingEnabled(True)
        
        header = self.urun_arama_sonuclari_tree.header()
        
        # Her sütuna ayrı ayrı piksel cinsinden genişlikler atıyoruz.
        self.urun_arama_sonuclari_tree.setColumnWidth(0, 130) # Kod
        header.setSectionResizeMode(0, QHeaderView.Fixed)

        self.urun_arama_sonuclari_tree.setColumnWidth(1, 385) # Ürün Adı
        header.setSectionResizeMode(1, QHeaderView.Fixed)

        self.urun_arama_sonuclari_tree.setColumnWidth(2, 70) # Stok
        header.setSectionResizeMode(2, QHeaderView.Fixed)

        self.urun_arama_sonuclari_tree.setColumnWidth(3, 100) # Fiyat
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        for i in range(self.urun_arama_sonuclari_tree.columnCount()):
            self.urun_arama_sonuclari_tree.headerItem().setTextAlignment(i, Qt.AlignCenter)
            self.urun_arama_sonuclari_tree.headerItem().setFont(i, QFont("Segoe UI", 12, QFont.Bold))
        self.urun_arama_sonuclari_tree.itemDoubleClicked.connect(self._double_click_add_to_cart)
        self.urun_arama_sonuclari_tree.itemSelectionChanged.connect(self.secili_urun_bilgilerini_goster_arama_listesinden)

        # DEĞİŞİKLİK: Arama listesinin maksimum yüksekliğini kısıtlıyoruz.
        self.urun_arama_sonuclari_tree.setMaximumHeight(200) # Örneğin 200px olarak ayarla

        urun_ekle_layout.addWidget(self.urun_arama_sonuclari_tree, 1, 0, 1, 2)
        alt_urun_ekle_frame = QFrame(urun_ekle_groupbox)
        alt_urun_ekle_layout = QHBoxLayout(alt_urun_ekle_frame)
        urun_ekle_layout.addWidget(alt_urun_ekle_frame, 2, 0, 1, 2)
        alt_urun_ekle_layout.addWidget(QLabel("Mik.:"))
        self.mik_e = QLineEdit("1")
        self.mik_e.setFixedWidth(50)
        setup_numeric_entry(self.app, self.mik_e, decimal_places=2)
        self.mik_e.returnPressed.connect(self.kalem_ekle_arama_listesinden)
        alt_urun_ekle_layout.addWidget(self.mik_e)
        alt_urun_ekle_layout.addWidget(QLabel("B.Fiyat:"))
        self.birim_fiyat_e = QLineEdit("0,00")
        self.birim_fiyat_e.setFixedWidth(80)
        setup_numeric_entry(self.app, self.birim_fiyat_e, decimal_places=2)
        alt_urun_ekle_layout.addWidget(self.birim_fiyat_e)
        alt_urun_ekle_layout.addWidget(QLabel("Stok:"))
        self.stk_l = QLabel("-")
        self.stk_l.setFont(QFont("Segoe UI", 9, QFont.Bold))
        alt_urun_ekle_layout.addWidget(self.stk_l)
        alt_urun_ekle_layout.addWidget(QLabel("İsk.1(%):"))
        self.iskonto_yuzde_1_e = QLineEdit("0,00")
        self.iskonto_yuzde_1_e.setFixedWidth(50)
        setup_numeric_entry(self.app, self.iskonto_yuzde_1_e, decimal_places=2)
        alt_urun_ekle_layout.addWidget(self.iskonto_yuzde_1_e)
        alt_urun_ekle_layout.addWidget(QLabel("İsk.2(%):"))
        self.iskonto_yuzde_2_e = QLineEdit("0,00")
        self.iskonto_yuzde_2_e.setFixedWidth(50)
        setup_numeric_entry(self.app, self.iskonto_yuzde_2_e, decimal_places=2)
        alt_urun_ekle_layout.addWidget(self.iskonto_yuzde_2_e)
        self.btn_sepete_ekle = QPushButton("Sepete Ekle")
        self.btn_sepete_ekle.clicked.connect(self.kalem_ekle_arama_listesinden)
        alt_urun_ekle_layout.addWidget(self.btn_sepete_ekle)

    def _select_product_from_search_list_and_focus_quantity(self, item): # item itemDoubleClicked sinyalinden gelir
        self.secili_urun_bilgilerini_goster_arama_listesinden(item) # Ürün bilgilerini doldur
        self.mik_e.setFocus() # Miktar kutusuna odaklan
        self.mik_e.selectAll() # Metni seçili yap

    def _setup_sepet_paneli(self, parent):
        sepet_layout = parent.layout()

        self.sep_tree = QTreeWidget(parent)
        self.sep_tree.setHeaderLabels(["#", "Ürün Adı", "Mik.", "B.Fiyat", "KDV%", "İsk 1 (%)", "İsk 2 (%)", "İsk. Tutarı", "Tutar(Dah.)", "Fiyat Geçmişi", "Ürün ID"])
        self.sep_tree.setColumnCount(11)
        self.sep_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sep_tree.setSortingEnabled(True)

        header = self.sep_tree.header()
        
        # DÜZELTME: Her sütun için ayrı ayrı genişlik ve yeniden boyutlandırma modunu ayarlıyoruz.
        self.sep_tree.setColumnWidth(0, 40)  # # sütunu
        header.setSectionResizeMode(0, QHeaderView.Fixed)

        self.sep_tree.setColumnWidth(1, 500)  # Ürün Adı
        header.setSectionResizeMode(1, QHeaderView.Fixed) # Ürün Adı sütunu genişleyerek boşluğu doldurur

        self.sep_tree.setColumnWidth(2, 70)  # Mik.
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        
        self.sep_tree.setColumnWidth(3, 185)  # B.Fiyat
        header.setSectionResizeMode(3, QHeaderView.Fixed)

        self.sep_tree.setColumnWidth(4, 70)  # KDV%
        header.setSectionResizeMode(4, QHeaderView.Fixed)

        self.sep_tree.setColumnWidth(5, 85)  # İsk 1 (%)
        header.setSectionResizeMode(5, QHeaderView.Fixed)

        self.sep_tree.setColumnWidth(6, 85)  # İsk 2 (%)
        header.setSectionResizeMode(6, QHeaderView.Fixed)

        self.sep_tree.setColumnWidth(7, 110) # Uyg. İsk. Tutarı
        header.setSectionResizeMode(7, QHeaderView.Fixed)

        self.sep_tree.setColumnWidth(8, 200) # Tutar(Dah.)
        header.setSectionResizeMode(8, QHeaderView.Fixed)
        
        self.sep_tree.setColumnWidth(9, 60)  # Fiyat Geçmişi
        header.setSectionResizeMode(9, QHeaderView.Stretch)

        self.sep_tree.setColumnWidth(10, 0) # Ürün ID
        header.setSectionResizeMode(10, QHeaderView.Fixed)
        
        for i in range(self.sep_tree.columnCount()):
            self.sep_tree.headerItem().setTextAlignment(i, Qt.AlignCenter)
            self.sep_tree.headerItem().setFont(i, QFont("Segoe UI", 12, QFont.Bold))

        # ID sütununu gizliyoruz (index 10)
        self.sep_tree.hideColumn(10)

        # Sinyalleri metotlara bağlıyoruz
        self.sep_tree.itemClicked.connect(self._on_sepet_item_click)
        self.sep_tree.itemDoubleClicked.connect(self._on_sepet_item_double_click)
        self.sep_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sep_tree.customContextMenuRequested.connect(self._open_sepet_context_menu)
        sepet_layout.addWidget(self.sep_tree, 1)

        btn_s_f = QFrame(parent)
        btn_s_f_layout = QHBoxLayout(btn_s_f)
        btn_s_f_layout.setContentsMargins(0, 0, 0, 0)
        btn_s_f_layout.setSpacing(5)
        sepet_layout.addWidget(btn_s_f)
        
        self.btn_secili_kalemi_sil = QPushButton("Seçili Kalemi Sil")
        self.btn_secili_kalemi_sil.clicked.connect(self.secili_kalemi_sil)
        btn_s_f_layout.addWidget(self.btn_secili_kalemi_sil)

        self.btn_sepeti_temizle = QPushButton("Tüm Kalemleri Sil")
        self.btn_sepeti_temizle.clicked.connect(self.sepeti_temizle)
        btn_s_f_layout.addWidget(self.btn_sepeti_temizle)
        btn_s_f_layout.addStretch()

    def _on_sepet_item_click(self, item, column):
        """Sepet listesindeki bir öğeye tek tıklandığında çağrılır."""
        # Eğer Fiyat Geçmişi sütununa (index 9) tek tıklandıysa
        if column == 9:
            self._open_fiyat_gecmisi_penceresi(item)

    def _on_sepet_item_double_click(self, item, column):
        # Sadece diğer sütunlara çift tıklandığında kalem düzenleme penceresini aç
        if column != 9:
            self._kalem_duzenle_penceresi_ac(item, column)

    def _setup_alt_bar(self):
        """Genel toplamlar ve kaydetme butonunu içeren alt barı oluşturur."""
        # Ana yatay layout
        self.alt_layout = QHBoxLayout(self.alt_f)
        self.alt_f.setContentsMargins(10, 10, 10, 10)
        self.alt_f.setFrameShape(QFrame.StyledPanel)
        self.alt_f.setStyleSheet("background-color: #f0f0f0;")

        font_t = QFont("Segoe UI", 10, QFont.Bold)
        font_d = QFont("Segoe UI", 12, QFont.Bold)
        
        # Etiketleri oluşturma
        self.alt_layout.addWidget(QLabel("KDV Hariç Toplam:", font=font_t))
        self.tkh_l = QLabel("0.00 TL", font=font_d)
        self.alt_layout.addWidget(self.tkh_l)

        self.alt_layout.addSpacing(20)

        self.alt_layout.addWidget(QLabel("Toplam KDV:", font=font_t))
        self.tkdv_l = QLabel("0.00 TL", font=font_d)
        self.alt_layout.addWidget(self.tkdv_l)
        
        self.alt_layout.addSpacing(20)

        self.alt_layout.addWidget(QLabel("Uygulanan Genel İsk:", font=font_t))
        self.lbl_uygulanan_genel_iskonto = QLabel("0.00 TL", font=font_d)
        self.alt_layout.addWidget(self.lbl_uygulanan_genel_iskonto)
        
        self.alt_layout.addSpacing(20)

        self.alt_layout.addWidget(QLabel("Genel Toplam:", font=font_t))
        self.gt_l = QLabel("0.00 TL", font=font_d)
        self.alt_layout.addWidget(self.gt_l)
        
        # Esneklik ekleyerek butonları sağa yaslıyoruz
        self.alt_layout.addStretch()

        self.btn_iptal = QPushButton("İptal")
        self.btn_iptal.setMinimumWidth(100)
        self.btn_iptal.clicked.connect(self.cancelled_successfully.emit)
        self.alt_layout.addWidget(self.btn_iptal)

        self.btn_kaydet = QPushButton("Kaydet")
        self.btn_kaydet.setMinimumWidth(100)
        self.btn_kaydet.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_kaydet.setStyleSheet("padding: 5px 10px; background-color: #4CAF50; color: white;")
        self.btn_kaydet.clicked.connect(self.kaydet)
        self.alt_layout.addWidget(self.btn_kaydet)

    def _open_sepet_context_menu(self, pos): # pos parametresi customContextMenuRequested sinyalinden gelir
        item = self.sep_tree.itemAt(pos) # Tıklanan öğeyi al
        if not item:
            return

        self.sep_tree.setCurrentItem(item) # Tıklanan öğeyi seçili yap

        context_menu = QMenu(self) # Yeni QMenu objesi oluştur

        # Komutları menüye ekleyin
        edit_action = context_menu.addAction("Kalemi Düzenle")
        edit_action.triggered.connect(lambda: self._kalem_duzenle_penceresi_ac(item, None)) # item'ı direkt gönder

        delete_action = context_menu.addAction("Seçili Kalemi Sil")
        delete_action.triggered.connect(self.secili_kalemi_sil)

        history_action = context_menu.addAction("Fiyat Geçmişi")
        # DEĞİŞİKLİK BURADA: Yeni bir lambda fonksiyonu kullanarak FiyatGecmisiPenceresi'ni doğrudan açan bir metot çağırıyoruz.
        history_action.triggered.connect(lambda: self._open_fiyat_gecmisi_penceresi(item))

        # Menüyü göster
        context_menu.exec(self.sep_tree.mapToGlobal(pos)) # Menüyü global koordinatlarda göster

    def _open_fiyat_gecmisi_penceresi(self, item):
        """Fiyat Geçmişi penceresini açar."""
        urun_id = item.data(10, Qt.UserRole)
        kalem_index_str = item.text(0)
        try:
            kalem_index = int(kalem_index_str) - 1
        except ValueError:
            QMessageBox.critical(self.app, "Hata", "Kalem indeksi okunamadı.")
            return

        if not self.secili_cari_id:
            QMessageBox.warning(self.app, "Uyarı", "Fiyat geçmişini görmek için lütfen önce bir cari seçin.")
            return
        
        from pencereler import FiyatGecmisiPenceresi
        dialog = FiyatGecmisiPenceresi(
            parent_app=self.app, 
            db_manager=self.db, 
            cari_id=self.secili_cari_id, 
            urun_id=urun_id, 
            fatura_tipi=self.islem_tipi,
            update_callback=self._update_sepet_kalem_from_history,
            current_kalem_index=kalem_index
        )
        dialog.exec()

    # --- ORTAK METOTLAR ---
    def _on_genel_iskonto_tipi_changed(self): # event=None kaldırıldı
        selected_type = self.genel_iskonto_tipi_cb.currentText() # QComboBox'tan metin al
        if selected_type == "YOK":
            self.genel_iskonto_degeri_e.setEnabled(False)
            self.genel_iskonto_degeri_e.setText("0,00")
        else:
            self.genel_iskonto_degeri_e.setEnabled(True)
        self.toplamlari_hesapla_ui()

    def _carileri_yukle_ve_cachele(self): # Yaklaşık 3450. satır
        logging.debug(f"BaseIslemSayfasi: _carileri_yukle_ve_cachele çağrıldı. self.islem_tipi: {self.islem_tipi}")
        kullanici_id = self.app.current_user_id 

        self.tum_cariler_cache_data = []
        self.cari_map_display_to_id = {}
        self.cari_id_to_display_map = {}
        
        try:
            cariler_list = []
            if self.islem_tipi in ["SATIŞ", "SATIŞ_SIPARIS", "SATIŞ İADE"]:
                # KRİTİK DÜZELTME 1: musteri_listesi_al() metodundan kullanici_id parametresi KALDIRILDI
                cariler_response = self.db.musteri_listesi_al()
                cariler_list = cariler_response.get("items", []) if isinstance(cariler_response, dict) else cariler_response
            elif self.islem_tipi in ["ALIŞ", "ALIŞ_SIPARIS", "ALIŞ İADE"]:
                # KRİTİK DÜZELTME 1: tedarikci_listesi_al() metodundan kullanici_id parametresi KALDIRILDI
                cariler_response = self.db.tedarikci_listesi_al()
                cariler_list = cariler_response.get("items", []) if isinstance(cariler_response, dict) else cariler_response
            else:
                self.app.set_status_message("Uyarı: Geçersiz işlem tipi için cari listesi yüklenemedi.", "orange")
                logging.warning(f"BaseIslemSayfasi._carileri_yukle_ve_cachele: Geçersiz self.islem_tipi: {self.islem_tipi}")
                return

            for c in cariler_list:
                cari_id = c.get('id')
                cari_ad = c.get('ad')
                cari_kodu_gosterim = c.get('kod')
                
                if cari_id is None:
                    continue

                display_text = f"{cari_ad} (Kod: {cari_kodu_gosterim})" 
                self.cari_map_display_to_id[display_text] = str(cari_id)
                self.cari_id_to_display_map[str(cari_id)] = display_text
                self.tum_cariler_cache_data.append(c)

            logging.debug(f"BaseIslemSayfasi: _carileri_yukle_ve_cachele bitiş. Yüklenen cari sayısı: {len(self.tum_cariler_cache_data)}")
            self.app.set_status_message(f"{len(self.tum_cariler_cache_data)} cari API'den önbelleğe alındı.", "black") 

        except Exception as e:
            logger.error(f"Cari listesi yüklenirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Cari listesi yüklenemedi. Detay: {e}", "red")
                    
    def _cari_secim_penceresi_ac(self):
        """
        Cari Seçim penceresini açar ve seçimi aldıktan sonra formu günceller.
        """
        try:
            from pencereler import CariSecimPenceresi
            
            cari_tip_for_dialog = None
            if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.SIPARIS_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE]:
                cari_tip_for_dialog = 'MUSTERI'
            elif self.islem_tipi in [self.db.FATURA_TIP_ALIS, self.db.SIPARIS_TIP_ALIS, self.db.FATURA_TIP_ALIS_IADE]:
                cari_tip_for_dialog = 'TEDARIKCI'
            else:
                QMessageBox.critical(self.app, "Hata", "Geçersiz işlem tipi için cari seçimi yapılamaz.")
                self.app.set_status_message("Hata: Geçersiz işlem tipi.")
                return

            dialog = CariSecimPenceresi(self.app, self.db, cari_tip_for_dialog)
            
            if dialog.exec() == QDialog.Accepted:
                selected_cari_id = dialog.secili_cari_id
                selected_cari_adi = dialog.secili_cari_adi

                if selected_cari_id is not None:
                    self._on_cari_secildi_callback(selected_cari_id, selected_cari_adi)
            
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Cari Seçim penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Cari Seçim penceresi açılamadı - {e}")
            logging.error(f"Cari seçim penceresi açma hatası: {e}", exc_info=True)

    def _sec(self):
        """Seçili cariyi kaydeder ve diyalog penceresini kapatır."""
        selected_items = self.cari_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Seçim Yok", "Lütfen bir cari seçin.")
            return

        selected_item = selected_items[0]
        # Seçilen verileri sınıf özelliklerine kaydet
        self.secili_cari_id = selected_item.data(0, Qt.UserRole)
        self.secili_cari_adi = selected_item.text(0)
        
        # Diyalogu kapat ve sonucu ACCEPTED olarak işaretle
        self.accept()

    def _guncelle_cari_bilgileri_ve_bakiye_ui(self, cari_id, cari_display_text):
        """
        Seçili cariye ait ID ve Adı'nı kaydeder, UI'ı (buton/label) günceller ve bakiyeyi çeker.
        Bu metod, ComboBox bağımlılığını ortadan kaldırır.
        """
        self.secili_cari_id = cari_id
        self.secili_cari_adi = cari_display_text

        # UI Elementlerini Güncelle
        if hasattr(self, 'btn_cari_sec'):
             self.btn_cari_sec.setText(f"{cari_display_text}")

        # Bakiye Çekme ve Güncelleme (Fatura/Sipariş formları için geçerli)
        if self.secili_cari_id is not None and hasattr(self, 'lbl_cari_bakiye'):
            # islem_tipi SATIŞ_SIPARIS gibi olabilir. İlk kelimeyi alıyoruz.
            cari_tip_str = self.islem_tipi.split("_")[0].upper() 
            
            # Cari tipini belirle
            cari_tip_enum = self.db.CARI_TIP_MUSTERI if cari_tip_str in ["SATIŞ", "SATIŞ İADE", "SATIŞ_SIPARIS"] else self.db.CARI_TIP_TEDARIKCI
            
            net_bakiye = 0.0
            if cari_tip_enum == self.db.CARI_TIP_MUSTERI:
                 net_bakiye = self.db.get_musteri_net_bakiye(musteri_id=self.secili_cari_id)
            else:
                 net_bakiye = self.db.get_tedarikci_net_bakiye(tedarikci_id=self.secili_cari_id, kullanici_id=self.app.current_user_id) 
            
            bakiye_text, bakiye_color = "Bakiye: Yüklenemedi", "black"
            if net_bakiye is not None:
                if net_bakiye > 0:
                    bakiye_text, bakiye_color = f"Borç: {self.db._format_currency(net_bakiye)}", "red"
                elif net_bakiye < 0:
                    bakiye_text, bakiye_color = f"Alacak: {self.db._format_currency(abs(net_bakiye))}", "green"
                else:
                    bakiye_text, bakiye_color = "Bakiye: 0,00 TL", "black"
            
            self.lbl_cari_bakiye.setText(bakiye_text)
            self.lbl_cari_bakiye.setStyleSheet(f"color: {bakiye_color};")
        elif hasattr(self, 'lbl_cari_bakiye'):
            self.lbl_cari_bakiye.setText("Bakiye: ---")
            self.lbl_cari_bakiye.setStyleSheet("color: black;")
            
        # Ek UI güncellemeleri
        if hasattr(self, '_guncel_stok_miktarlarini_getir'):
             self._guncel_stok_miktarlarini_getir()

    def _on_cari_secildi_callback(self, selected_cari_id, selected_cari_display_text):
        """
        Cari Seçim penceresi kapatıldığında çağrılır ve seçilen cariye göre formu günceller.
        """
        self._guncelle_cari_bilgileri_ve_bakiye_ui(selected_cari_id, selected_cari_display_text)
        
        # YENİ EKLENEN KOD: Cari değiştiğinde, ödeme türü listesini yeniden değerlendir.
        # Bu, "Açık Hesap" mantığının doğru çalışmasını sağlar.
        self._odeme_turu_ve_misafir_adi_kontrol()

    def _on_cari_selected(self):
        selected_cari_id = self.cari_combo.currentData()
        if selected_cari_id:
            cari_tip = self.cari_combo.currentText().split(":")[0].strip()
            cari = self.db.cari_getir_by_id(selected_cari_id, cari_tip)
            
            if cari:
                # Cari nesnesinin türünü kontrol et
                if isinstance(cari, dict):
                    cari_adi = cari.get('ad', 'Bilinmiyor')
                else: # SQLAlchemy modeli
                    cari_adi = cari.ad
                
                self.cari_adi_label.setText(cari_adi)
                
                # Bakiye kontrolü
                net_bakiye_response = self.db.cari_getir_net_bakiye(selected_cari_id, cari_tip)
                
                net_bakiye = None
                if isinstance(net_bakiye_response, dict):
                    net_bakiye = net_bakiye_response.get('bakiye')
                elif net_bakiye_response is not None:
                    net_bakiye = net_bakiye_response

                # NoneType hatasını önlemek için kontrol
                if net_bakiye is not None and isinstance(net_bakiye, (int, float)):
                    self.bakiye_label.setText(f"Bakiye: {net_bakiye:.2f} TL")
                    if net_bakiye > 0:
                        self.bakiye_label.setStyleSheet("color: red;")
                    elif net_bakiye < 0:
                        self.bakiye_label.setStyleSheet("color: green;")
                    else:
                        self.bakiye_label.setStyleSheet("color: black;")
                else:
                    self.bakiye_label.setText("Bakiye: Yok")
                    self.bakiye_label.setStyleSheet("color: black;")

            self.fatura_kalemleri_tablosunu_yukle([])
            self._guncel_stok_miktarlarini_getir()
            self._yenile_butonu_durum_guncelle()

    def _temizle_cari_secimi(self):
        self.secili_cari_id = None
        self.secili_cari_adi = None
        if hasattr(self, 'lbl_secili_cari_adi'):
            self.lbl_secili_cari_adi.setText("Seçilen Cari: Yok")
        if hasattr(self, 'lbl_cari_bakiye'):
            self.lbl_cari_bakiye.setText("")
            self.lbl_cari_bakiye.setStyleSheet("color: black;")

    def _urunleri_yukle_ve_cachele_ve_goster(self):
        try:
            # DÜZELTİLDİ: Veriler artık yerel veritabanından çekiliyor.
            with lokal_db_servisi.get_db() as db:
                urunler_listesi_local = db.query(Stok).filter(Stok.aktif == True).all()

            self.tum_urunler_cache.clear()
            for urun_data in urunler_listesi_local:
                # SQLAlchemy nesnesini sözlüğe dönüştürerek önbelleğe alıyoruz.
                self.tum_urunler_cache.append({
                    'id': urun_data.id,
                    'kod': urun_data.kod,
                    'ad': urun_data.ad,
                    'miktar': urun_data.miktar,
                    'alis_fiyati': urun_data.alis_fiyati,
                    'satis_fiyati': urun_data.satis_fiyati,
                    'kdv_orani': urun_data.kdv_orani,
                    'birim': {'ad': 'Adet'} # Yerel şemanızda birim bilgisi yok, sabit değer atandı
                })
            
            self._urun_listesini_filtrele_anlik()
            self.app.set_status_message(f"{len(self.tum_urunler_cache)} ürün yerel veritabanından önbelleğe alındı.")

        except Exception as e:
            logger.error(f"Ürün listesi yüklenirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Ürünler yüklenemedi. Detay: {e}")

    def _urun_listesini_filtrele_anlik(self):
        arama_terimi = self.urun_arama_entry.text().strip()
        normalized_arama_terimi = normalize_turkish_chars(arama_terimi).lower()
        self.urun_arama_sonuclari_tree.clear()
        self.urun_map_filtrelenmis.clear()

        if not normalized_arama_terimi:
            filtered_list = self.tum_urunler_cache
        else:
            filtered_list = [urun_item for urun_item in self.tum_urunler_cache
                            if (normalized_arama_terimi in normalize_turkish_chars(urun_item.get('ad', '')).lower()) or
                                (normalized_arama_terimi in normalize_turkish_chars(urun_item.get('kod', '')).lower())]

        # DEĞİŞİKLİK: Ürün listesi boş bile olsa Treeview'i gizlemiyoruz.
        # Sadece içeriğini temizliyoruz, başlıklar görünür kalır.
        
        for urun_item in filtered_list:
            urun_id = urun_item.get('id')
            if urun_id is None:
                continue

            item_qt = QTreeWidgetItem(self.urun_arama_sonuclari_tree)
            
            # DÜZELTME: Sütunlara yeni sıraya göre veriler atandı
            item_qt.setText(0, urun_item.get('kod', '')) # Kod
            item_qt.setText(1, urun_item.get('ad', ''))  # Ürün Adı

            fiyat_gosterim = 0.0
            if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_DEVIR_GIRIS, self.db.SIPARIS_TIP_SATIS]:
                fiyat_gosterim = urun_item.get('satis_fiyati', 0.0)
            elif self.islem_tipi in [self.db.FATURA_TIP_ALIS, self.db.SIPARIS_TIP_ALIS]:
                fiyat_gosterim = urun_item.get('alis_fiyati', 0.0)
            elif self.islem_tipi == self.db.FATURA_TIP_SATIS_IADE:
                fiyat_gosterim = urun_item.get('alis_fiyati', 0.0)
            elif self.islem_tipi == self.db.FATURA_TIP_ALIS_IADE:
                fiyat_gosterim = urun_item.get('satis_fiyati', 0.0)
            
            item_qt.setText(2, f"{urun_item.get('miktar', 0):.2f}".rstrip('0').rstrip('.')) # Stok
            item_qt.setText(3, self.db._format_currency(fiyat_gosterim))                     # Fiyat
            
            # Sütunlara eski sıraya göre veri atama satırları kaldırıldı
            # item_qt.setText(0, urun_item.get('ad', ''))
            # item_qt.setText(1, urun_item.get('kod', ''))
            # item_qt.setText(2, self.db._format_currency(fiyat_gosterim))
            # item_qt.setText(3, f"{urun_item.get('miktar', 0):.2f}".rstrip('0').rstrip('.'))

            item_qt.setData(0, Qt.UserRole, urun_id)

            for col_idx in range(item_qt.columnCount()):
                item_qt.setTextAlignment(col_idx, Qt.AlignCenter)
                item_qt.setFont(col_idx, QFont("Segoe UI", 12))

            self.urun_map_filtrelenmis[urun_id] = {
                'id': urun_id,
                'kod': urun_item.get('kod'),
                'ad': urun_item.get('ad'),
                'alis_fiyati': urun_item.get('alis_fiyati'),
                'satis_fiyati': urun_item.get('satis_fiyati'),
                'kdv_orani': urun_item.get('kdv_orani', 0.0),
                'miktar': urun_item.get('miktar'),
                'birim': urun_item.get('birim')
            }

        if len(filtered_list) == 1:
            self.urun_arama_sonuclari_tree.setCurrentItem(self.urun_arama_sonuclari_tree.topLevelItem(0))
            self.urun_arama_sonuclari_tree.setFocus()

        self.secili_urun_bilgilerini_goster_arama_listesinden()

    def _delayed_stok_yenile(self):
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self._urun_listesini_filtrele_anlik)

    def secili_urun_bilgilerini_goster_arama_listesinden(self):
        selected_items = self.urun_arama_sonuclari_tree.selectedItems()

        if selected_items and len(selected_items) > 0:
            item_qt = selected_items[0]
            urun_id = item_qt.data(0, Qt.UserRole) # ID'yi UserRole'dan al

            if urun_id in self.urun_map_filtrelenmis:
                urun_detaylari = self.urun_map_filtrelenmis[urun_id]

                # Fatura tipine göre fiyatı belirle
                fiyat_to_fill = 0.0
                if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.SIPARIS_TIP_SATIS]:
                    fiyat_to_fill = urun_detaylari.get('satis_fiyati', 0.0)
                else:
                    fiyat_to_fill = urun_detaylari.get('alis_fiyati', 0.0)

                self.birim_fiyat_e.setText(f"{fiyat_to_fill:.2f}".replace('.',','))
                self.stk_l.setText(f"{urun_detaylari['miktar']:.2f}".rstrip('0').rstrip('.'))
                self.stk_l.setStyleSheet("color: black;")
                self._check_stock_on_quantity_change()
            else:
                self.birim_fiyat_e.setText("0,00")
                self.stk_l.setText("-")
                self.stk_l.setStyleSheet("color: black;")
                self.app.set_status_message("Seçili ürün detayları bulunamadı.", "red")
        else:
            self.birim_fiyat_e.setText("0,00")
            self.stk_l.setText("-")
            self.stk_l.setStyleSheet("color: black;")

    def kalem_ekle_arama_listesinden(self):
        selected_items = self.urun_arama_sonuclari_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Geçersiz Ürün", "Lütfen arama listesinden geçerli bir ürün seçin.")
            return

        item_qt = selected_items[0]
        u_id = item_qt.data(0, Qt.UserRole) # ID'yi UserRole'dan al

        if u_id not in self.urun_map_filtrelenmis:
            QMessageBox.warning(self.app, "Geçersiz Ürün", "Seçili ürün detayları bulunamadı.")
            return

        urun_detaylari = self.urun_map_filtrelenmis[u_id]
        # u_id zaten int olduğu için tekrar atamaya gerek yok.
        
        eklenecek_miktar_str = self.mik_e.text().replace(',', '.')
        try:
            eklenecek_miktar = float(eklenecek_miktar_str)
        except ValueError:
            QMessageBox.critical(self.app, "Geçersiz Miktar", "Miktar sayısal bir değer olmalıdır.")
            return

        if eklenecek_miktar <= 0:
            QMessageBox.critical(self.app, "Geçersiz Miktar", "Miktar pozitif bir değer olmalıdır.")
            return

        existing_kalem_index = -1
        for i, kalem in enumerate(self.fatura_kalemleri_ui):
            if kalem[0] == u_id:
                existing_kalem_index = i
                break
            
        istenen_toplam_miktar_sepette = eklenecek_miktar
        if existing_kalem_index != -1:
            eski_miktar = float(self.fatura_kalemleri_ui[existing_kalem_index][2])
            istenen_toplam_miktar_sepette = eski_miktar + eklenecek_miktar
            
        if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.SIPARIS_TIP_SATIS, self.db.FATURA_TIP_ALIS_IADE]:
            # Burada stok kontrolü yapmak için urun_db_info'yu yeniden çekmeye gerek yok,
            # _urunleri_yukle_ve_cachele_ve_goster metodunda zaten `tum_urunler_cache` içinde var.
            # Ancak, anlık stok değişmiş olabilir, bu nedenle API'den teyit almak en güvenlisi.
            try:
                urun_db_info = self.db.stok_getir_by_id(u_id)
                mevcut_stok = urun_db_info.get('miktar', 0.0) if urun_db_info else 0.0
            except Exception as e:
                logger.warning(f"Stok bilgisi API'den çekilirken hata oluştu: {e}")
                mevcut_stok = 0.0

            orijinal_fatura_kalem_miktari = 0
            if self.duzenleme_id:
                try:
                    # API'den fatura kalemlerini alıyoruz.
                    original_items_on_invoice = self.db.fatura_detay_al(self.duzenleme_id)
                    for item in original_items_on_invoice:
                        if item.get('urun_id') == u_id:
                            orijinal_fatura_kalem_miktari = item.get('miktar', 0.0)
                            break
                except Exception as e:
                    logger.warning(f"Orijinal fatura kalemleri çekilirken hata: {e}")

            kullanilabilir_stok = mevcut_stok + orijinal_fatura_kalem_miktari

            if istenen_toplam_miktar_sepette > kullanilabilir_stok:
                reply = QMessageBox.question(self.app, "Stok Uyarısı", 
                                            f"'{urun_detaylari['ad']}' için stok yetersiz!\n\n"
                                            f"Kullanılabilir Stok: {kullanilabilir_stok:.2f} adet\n"
                                            f"Talep Edilen Toplam Miktar: {istenen_toplam_miktar_sepette:.2f} adet\n\n"
                                            f"Bu işlem negatif stok yaratacaktır. Devam etmek istiyor musunuz?",
                                            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No: return

        b_f_kdv_dahil_orijinal_str = self.birim_fiyat_e.text().replace(',', '.')
        yeni_iskonto_1_str = self.iskonto_yuzde_1_e.text().replace(',', '.')
        yeni_iskonto_2_str = self.iskonto_yuzde_2_e.text().replace(',', '.')
        
        try:
            b_f_kdv_dahil_orijinal = float(b_f_kdv_dahil_orijinal_str)
            yeni_iskonto_1 = float(yeni_iskonto_1_str)
            yeni_iskonto_2 = float(yeni_iskonto_2_str)
        except ValueError:
            QMessageBox.critical(self.app, "Giriş Hatası", "Fiyat veya iskonto değerleri sayısal olmalıdır.")
            return

        # Fatura anındaki alış fiyatını al (stok kartından)
        urun_tam_detay = self.db.stok_getir_by_id(u_id)
        alis_fiyati_fatura_aninda = urun_tam_detay.get('alis_fiyati', 0.0) if urun_tam_detay else 0.0

        if existing_kalem_index != -1:
            self.kalem_guncelle(existing_kalem_index, istenen_toplam_miktar_sepette, b_f_kdv_dahil_orijinal, yeni_iskonto_1, yeni_iskonto_2, alis_fiyati_fatura_aninda)
        else:
            self.kalem_guncelle(None, eklenecek_miktar, b_f_kdv_dahil_orijinal, yeni_iskonto_1, yeni_iskonto_2, alis_fiyati_fatura_aninda, u_id=u_id, urun_adi=urun_detaylari["ad"])

        # Sepete ekledikten sonra arama kutusunu ve miktar kutusunu sıfırlayıp odaklanmayı arama kutusuna verin.
        self.mik_e.setText("1")
        self.iskonto_yuzde_1_e.setText("0,00") 
        self.iskonto_yuzde_2_e.setText("0,00")
        self.birim_fiyat_e.setText("0,00") 
        self.stk_l.setText("-")
        self.stk_l.setStyleSheet("color: black;") 

        self.urun_arama_entry.clear()
        self._urun_listesini_filtrele_anlik() # Arama listesini temizleyip yenileyin
        self.urun_arama_entry.setFocus()
        
    def kalem_guncelle(self, kalem_index, yeni_miktar, yeni_fiyat_kdv_dahil_orijinal, yeni_iskonto_yuzde_1, yeni_iskonto_yuzde_2, yeni_alis_fiyati_fatura_aninda, u_id=None, urun_adi=None):
        # Veri tiplerini güvenli bir şekilde dönüştür
        yeni_miktar = self.db.safe_float(yeni_miktar)
        yeni_fiyat_kdv_dahil_orijinal = self.db.safe_float(yeni_fiyat_kdv_dahil_orijinal)
        yeni_iskonto_yuzde_1 = self.db.safe_float(yeni_iskonto_yuzde_1)
        yeni_iskonto_yuzde_2 = self.db.safe_float(yeni_iskonto_yuzde_2)
        yeni_alis_fiyati_fatura_aninda = self.db.safe_float(yeni_alis_fiyati_fatura_aninda)
        kullanici_id = self.app.current_user.get("id")

        if kalem_index != -1 and kalem_index is not None:
            item_to_update = list(self.fatura_kalemleri_ui[kalem_index])
            urun_id_current = item_to_update[0]
            # KDV oranını mevcut kalemden al
            kdv_orani_current = self.db.safe_float(item_to_update[4])
            alis_fiyati_aninda = self.db.safe_float(item_to_update[8])
        else:
            if u_id is None or urun_adi is None:
                QMessageBox.critical(self.app, "Hata", "Yeni kalem eklenirken ürün bilgileri eksik.")
                return
            urun_id_current = u_id
            
            urun_detaylari_db = self.db.stok_getir_by_id(u_id, kullanici_id=kullanici_id)
            
            kdv_orani_current = self.db.safe_float(urun_detaylari_db.get('kdv_orani', 0.0)) if urun_detaylari_db else 0.0
            alis_fiyati_aninda = self.db.safe_float(urun_detaylari_db.get('alis_fiyati', 0.0)) if urun_detaylari_db else 0.0
            
            # Yeni kalem için gerekli 15 elemanlı listeyi oluştur
            item_to_update = [
                urun_id_current, urun_adi, yeni_miktar, 0.0, kdv_orani_current, 
                0.0, 0.0, 0.0, alis_fiyati_aninda, kdv_orani_current, 
                yeni_iskonto_yuzde_1, yeni_iskonto_yuzde_2, "YOK", 0.0, 0.0
            ]

        # Miktar ve iskonto yüzdelerini güncelle
        item_to_update[2] = yeni_miktar
        item_to_update[10] = yeni_iskonto_yuzde_1
        item_to_update[11] = yeni_iskonto_yuzde_2

        # Fatura anı alış fiyatını güncelle (sadece Sales/Satış İade'de gereklidir)
        if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE]:
            item_to_update[8] = yeni_alis_fiyati_fatura_aninda # Yeni değeri ata

        # İskları uygula
        fiyat_iskonto_1_sonrasi_dahil = yeni_fiyat_kdv_dahil_orijinal * (1 - yeni_iskonto_yuzde_1 / 100)
        iskontolu_birim_fiyat_kdv_dahil = fiyat_iskonto_1_sonrasi_dahil * (1 - yeni_iskonto_yuzde_2 / 100)
        
        # Fiyat sıfırın altına düşerse sıfır yap
        if iskontolu_birim_fiyat_kdv_dahil < 0:
            iskontolu_birim_fiyat_kdv_dahil = 0.0

        # İsk sonrası KDV hariç fiyatı hesapla
        if kdv_orani_current == 0:
            iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil
            original_birim_fiyat_kdv_haric = yeni_fiyat_kdv_dahil_orijinal
        else:
            iskontolu_birim_fiyat_kdv_haric = iskontolu_birim_fiyat_kdv_dahil / (1 + kdv_orani_current / 100)
            original_birim_fiyat_kdv_haric = yeni_fiyat_kdv_dahil_orijinal / (1 + kdv_orani_current / 100)

        item_to_update[3] = original_birim_fiyat_kdv_haric
        item_to_update[14] = iskontolu_birim_fiyat_kdv_dahil

        # Kalem toplamlarını hesapla
        kalem_toplam_kdv_haric = iskontolu_birim_fiyat_kdv_haric * yeni_miktar
        kalem_toplam_kdv_dahil = iskontolu_birim_fiyat_kdv_dahil * yeni_miktar
        kdv_tutari = kalem_toplam_kdv_dahil - kalem_toplam_kdv_haric

        item_to_update[5] = kdv_tutari
        item_to_update[6] = kalem_toplam_kdv_haric
        item_to_update[7] = kalem_toplam_kdv_dahil

        # Listeyi güncelle veya yeni kalem olarak ekle
        if kalem_index != -1 and kalem_index is not None:
            self.fatura_kalemleri_ui[kalem_index] = tuple(item_to_update)
        else:
            self.fatura_kalemleri_ui.append(tuple(item_to_update))

        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()
        
    def sepeti_guncelle_ui(self):
        if not hasattr(self, 'sep_tree'):
            return

        self.sep_tree.clear()

        for i, k in enumerate(self.fatura_kalemleri_ui):
            miktar_f = self.db.safe_float(k[2])
            birim_fiyat_gosterim_f = self.db.safe_float(k[14])
            original_bf_haric_f = self.db.safe_float(k[3])
            kdv_orani_f = self.db.safe_float(k[4])
            iskonto_yuzde_1_f = self.db.safe_float(k[10])
            iskonto_yuzde_2_f = self.db.safe_float(k[11])
            kalem_toplam_dahil_f = self.db.safe_float(k[7])
            
            miktar_gosterim = f"{miktar_f:.2f}".rstrip('0').rstrip('.')
            original_bf_dahil = original_bf_haric_f * (1 + kdv_orani_f / 100)
            uygulanan_iskonto = (original_bf_dahil - birim_fiyat_gosterim_f) * miktar_f

            item_qt = QTreeWidgetItem(self.sep_tree)
            item_qt.setText(0, str(i + 1))
            item_qt.setText(1, k[1])
            item_qt.setText(2, miktar_gosterim)
            item_qt.setText(3, self.db._format_currency(birim_fiyat_gosterim_f))
            item_qt.setText(4, f"%{kdv_orani_f:.0f}")
            item_qt.setText(5, f"{iskonto_yuzde_1_f:.2f}".replace('.',','))
            item_qt.setText(6, f"{iskonto_yuzde_2_f:.2f}".replace('.',','))
            item_qt.setText(7, self.db._format_currency(uygulanan_iskonto))
            item_qt.setText(8, self.db._format_currency(kalem_toplam_dahil_f))
            item_qt.setText(9, "Geçmişi Gör")
            item_qt.setText(10, str(k[0]))

            for col_idx in range(item_qt.columnCount()):
                item_qt.setTextAlignment(col_idx, Qt.AlignCenter)
                item_qt.setFont(col_idx, QFont("Segoe UI", 18))

            item_qt.setData(2, Qt.UserRole, miktar_f)
            item_qt.setData(3, Qt.UserRole, birim_fiyat_gosterim_f)
            item_qt.setData(4, Qt.UserRole, kdv_orani_f)
            item_qt.setData(5, Qt.UserRole, iskonto_yuzde_1_f)
            item_qt.setData(6, Qt.UserRole, iskonto_yuzde_2_f)
            item_qt.setData(7, Qt.UserRole, uygulanan_iskonto)
            item_qt.setData(8, Qt.UserRole, kalem_toplam_dahil_f)
            item_qt.setData(10, Qt.UserRole, k[0])

        self.toplamlari_hesapla_ui()

    def toplamlari_hesapla_ui(self):
        """Sipariş/Fatura kalemlerinin toplamlarını hesaplar ve UI'daki etiketleri günceller."""
        if not hasattr(self, 'tkh_l'): # QLabel objelerinin varlığını kontrol et
            # Bu durum genellikle UI elemanları henüz oluşturulmadığında meydana gelir.
            # Metot çağrısının UI kurulumundan sonra olduğundan emin olun.
            # print("DEBUG: toplamlari_hesapla_ui: UI etiketleri veya temel değişkenler henüz tanımlanmadı. Atlanıyor.")
            return 
        
        # self.db.safe_float kullanarak tüm sayısal değerleri güvenli bir şekilde alıyoruz
        toplam_kdv_haric_kalemler = sum(self.db.safe_float(k[6]) for k in self.fatura_kalemleri_ui)
        toplam_kdv_dahil_kalemler = sum(self.db.safe_float(k[7]) for k in self.fatura_kalemleri_ui)
        # toplam_kdv_kalemler = sum(self.db.safe_float(k[5]) for k in self.fatura_kalemleri_ui) # Eğer ayrı bir KDV toplamı etiketi varsa kullanılabilir
        
        genel_iskonto_tipi = self.genel_iskonto_tipi_cb.currentText() # QComboBox'tan al
        genel_iskonto_degeri = self.db.safe_float(self.genel_iskonto_degeri_e.text()) # QLineEdit'ten al
        
        # Eğer iskonto alanı etkin değilse, değeri 0 olarak kabul et
        if not self.genel_iskonto_degeri_e.isEnabled():
            genel_iskonto_degeri = 0.0

        uygulanan_genel_iskonto_tutari = 0.0

        if genel_iskonto_tipi == 'YUZDE' and genel_iskonto_degeri > 0:
            uygulanan_genel_iskonto_tutari = toplam_kdv_haric_kalemler * (genel_iskonto_degeri / 100)
        elif genel_iskonto_tipi == 'TUTAR' and genel_iskonto_degeri > 0:
            uygulanan_genel_iskonto_tutari = genel_iskonto_degeri
        
        # Nihai toplamları hesapla
        nihai_toplam_kdv_dahil = toplam_kdv_dahil_kalemler - uygulanan_genel_iskonto_tutari
        nihai_toplam_kdv_haric = toplam_kdv_haric_kalemler - uygulanan_genel_iskonto_tutari
        nihai_toplam_kdv = nihai_toplam_kdv_dahil - nihai_toplam_kdv_haric

        # UI etiketlerini güncelle
        self.tkh_l.setText(self.db._format_currency(nihai_toplam_kdv_haric))
        self.tkdv_l.setText(self.db._format_currency(nihai_toplam_kdv))
        self.gt_l.setText(self.db._format_currency(nihai_toplam_kdv_dahil))
        self.lbl_uygulanan_genel_iskonto.setText(self.db._format_currency(uygulanan_genel_iskonto_tutari))

    def secili_kalemi_sil(self):
        selected_items = self.sep_tree.selectedItems() # QTreeWidget'tan seçili öğeleri al
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir kalem seçin.")
            return
            
        selected_item_qt = selected_items[0]
        kalem_index_str = selected_item_qt.text(0) # İlk sütun sıra numarası ("1", "2" vb.)
        try:
            kalem_index = int(kalem_index_str) - 1 # Listede 0 tabanlı indeks
        except ValueError:
            QMessageBox.critical(self.app, "Hata", "Seçili kalemin indeksi okunamadı.")
            return

        del self.fatura_kalemleri_ui[kalem_index]
        
        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()
        
    def sepeti_temizle(self):
        if self.fatura_kalemleri_ui and QMessageBox.question(self.app, "Onay", "Tüm kalemleri silmek istiyor musunuz?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.fatura_kalemleri_ui.clear()
            self.sepeti_guncelle_ui()
            self.toplamlari_hesapla_ui()

    def _kalem_duzenle_penceresi_ac(self, item, column): # item ve column sinyalden gelir
        # QTreeWidget'ta tıklanan öğenin verisini al.
        kalem_index_str = item.text(0) # İlk sütun sıra numarası (1 tabanlı)
        try:
            kalem_index = int(kalem_index_str) - 1 # 0 tabanlı indekse çevir
        except ValueError:
            QMessageBox.critical(self.app, "Hata", "Seçili kalemin indeksi okunamadı.")
            return

        kalem_verisi = self.fatura_kalemleri_ui[kalem_index]
        
        # Yeni Kod: KalemDuzenlePenceresi'ni başlatıp gösteriyoruz.
        from pencereler import KalemDuzenlePenceresi
        dialog = KalemDuzenlePenceresi(
            parent_page=self,
            db_manager=self.db,
            kalem_index=kalem_index,
            kalem_verisi=kalem_verisi,
            islem_tipi=self.islem_tipi,
            fatura_id_duzenle=self.duzenleme_id
        )
        dialog.exec()
        
    def _double_click_add_to_cart(self, item):
        """
        Ürün arama listesindeki bir ürüne çift tıklandığında ürünü sepete ekler.
        Bu metot daha önce FaturaPenceresi'nde bulunuyordu.
        """
        selected_items = self.urun_arama_sonuclari_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Geçersiz Ürün", "Lütfen sepete eklemek için arama listesinden bir ürün seçin.")
            return

        urun_id = selected_items[0].data(0, Qt.UserRole)
        if urun_id not in self.urun_map_filtrelenmis:
            QMessageBox.warning(self.app, "Geçersiz Ürün", "Seçili ürün detayları bulunamadı.")
            return
        
        urun_detaylari = self.urun_map_filtrelenmis[urun_id]
        
        # Fatura tipine göre varsayılan birim fiyatı belirle
        birim_fiyat_kdv_dahil_input = 0.0
        if self.islem_tipi == self.db.FATURA_TIP_SATIS or self.islem_tipi == self.db.FATURA_TIP_DEVIR_GIRIS:
            birim_fiyat_kdv_dahil_input = urun_detaylari.get('satis_fiyati', 0.0)
        elif self.islem_tipi == self.db.FATURA_TIP_ALIS:
            birim_fiyat_kdv_dahil_input = urun_detaylari.get('alis_fiyati', 0.0)
        elif self.islem_tipi == self.db.FATURA_TIP_SATIS_IADE:
            birim_fiyat_kdv_dahil_input = urun_detaylari.get('alis_fiyati', 0.0)
        elif self.islem_tipi == self.db.FATURA_TIP_ALIS_IADE:
            birim_fiyat_kdv_dahil_input = urun_detaylari.get('satis_fiyati', 0.0)

        # Varsayılan miktar 1 ve iskonto 0 olacak
        eklenecek_miktar = 1.0
        iskonto_yuzde_1 = 0.0
        iskonto_yuzde_2 = 0.0

        # Satış ve Satış İade faturalarında stok kontrolü yap
        if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_ALIS_IADE]:
            mevcut_stok = urun_detaylari.get('miktar', 0.0)
            
            sepetteki_urun_miktari = sum(k[2] for k in self.fatura_kalemleri_ui if k[0] == urun_id)
            
            # Eğer mevcut bir fatura düzenleniyorsa, orijinal fatura kalemindeki miktarı mevcut stoka geri ekle
            if self.duzenleme_id:
                original_fatura_kalemleri = self._get_original_invoice_items_from_db(self.duzenleme_id)
                for orig_kalem in original_fatura_kalemleri:
                    if orig_kalem['urun_id'] == urun_id:
                        if self.islem_tipi == self.db.FATURA_TIP_SATIS:
                            mevcut_stok += orig_kalem['miktar']
                        elif self.islem_tipi == self.db.FATURA_TIP_ALIS_IADE:
                            mevcut_stok += orig_kalem['miktar']
                        break
            
            if (sepetteki_urun_miktari + eklenecek_miktar) > mevcut_stok:
                reply = QMessageBox.question(self.app, "Stok Uyarısı",
                                            f"'{urun_detaylari['ad']}' için stok yetersiz!\n"
                                            f"Mevcut stok: {mevcut_stok:.2f} adet\n"
                                            f"Sepete eklenecek toplam: {sepetteki_urun_miktari + eklenecek_miktar:.2f} adet\n\n"
                                            "Devam etmek negatif stok oluşturacaktır. Emin misiniz?",
                                            QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No: return

        # Ürünün orijinal alış fiyatı, eğer satış faturasıysa. Kalem detayına kaydedilecek.
        alis_fiyati_fatura_aninda = urun_detaylari.get('alis_fiyati', 0.0)

        # Ürün sepette zaten varsa, sadece miktarını artır
        existing_kalem_index = -1
        for i, kalem in enumerate(self.fatura_kalemleri_ui):
            if kalem[0] == urun_id:
                existing_kalem_index = i
                # Çift tıklamada miktarını 1 artır
                eklenecek_miktar = kalem[2] + 1.0
                # Birim fiyat ve iskonto oranları aynı kalsın (ilk eklendiği gibi)
                birim_fiyat_kdv_dahil_input = kalem[14]
                iskonto_yuzde_1 = kalem[10]
                iskonto_yuzde_2 = kalem[11]
                break

        # kalem_guncelle metodunu kullanarak kalemi sepete ekle veya güncelle
        self.kalem_guncelle(
            kalem_index=existing_kalem_index,
            yeni_miktar=eklenecek_miktar,
            yeni_fiyat_kdv_dahil_orijinal=birim_fiyat_kdv_dahil_input,
            yeni_iskonto_yuzde_1=iskonto_yuzde_1,
            yeni_iskonto_yuzde_2=iskonto_yuzde_2,
            yeni_alis_fiyati_fatura_aninda=alis_fiyati_fatura_aninda,
            u_id=urun_id,
            urun_adi=urun_detaylari['ad'],
        )

        # Alanları temizle ve arama kutusuna odaklan
        self.urun_arama_entry.clear()
        self.mik_e.setText("1")
        self.birim_fiyat_e.setText("0,00")
        self.iskonto_yuzde_1_e.setText("0,00")
        self.iskonto_yuzde_2_e.setText("0,00")
        self.stk_l.setText("-") # Stok etiketini temizle
        self.urun_arama_entry.setFocus()

    def _on_sepet_kalem_click(self, item, column): # item ve column sinyalden gelir
        # QTreeWidget'ta sütun bazlı tıklama algılama (Fiyat Geçmişi butonu için)
        header_text = self.sep_tree.headerItem().text(column)
        if header_text == "Fiyat Geçmişi":
            urun_id_str = item.text(10) # Ürün ID sütunu (gizli sütun)
            kalem_index_str = item.text(0) # Sıra numarası
            try:
                urun_id = int(urun_id_str)
                kalem_index = int(kalem_index_str) - 1
            except ValueError:
                QMessageBox.critical(self.app, "Hata", "Ürün ID veya kalem indeksi okunamadı.")
                return

            if not self.secili_cari_id:
                QMessageBox.warning(self.app, "Uyarı", "Fiyat geçmişini görmek için lütfen önce bir cari seçin.")
                return
            
            # Yeni Kod: FiyatGecmisiPenceresi'ni başlatıp gösteriyoruz.
            from pencereler import FiyatGecmisiPenceresi
            dialog = FiyatGecmisiPenceresi(
                parent_app=self.app, 
                db_manager=self.db, 
                cari_id=self.secili_cari_id, 
                urun_id=urun_id, 
                fatura_tipi=self.islem_tipi,
                update_callback=self._update_sepet_kalem_from_history,
                current_kalem_index=kalem_index
            )
            dialog.exec()

    def _update_sepet_kalem_from_history(self, kalem_index, new_price_kdv_dahil, new_iskonto_1, new_iskonto_2):
        if not (0 <= kalem_index < len(self.fatura_kalemleri_ui)): return
        current_kdv_orani = self.fatura_kalemleri_ui[kalem_index][4]
        iskonto_carpan_1 = (1 - new_iskonto_1 / 100)
        iskonto_carpan_2 = (1 - new_iskonto_2 / 100)
        calculated_original_price_kdv_dahil = new_price_kdv_dahil / (iskonto_carpan_1 * iskonto_carpan_2) if (iskonto_carpan_1 * iskonto_carpan_2) > 0 else new_price_kdv_dahil
        
        # self.kalem_guncelle metodunun yeni_fiyat_kdv_dahil_orijinal parametresini doğru formatta göndermeliyiz.
        # Bu durumda, kalem_guncelle'ye orijinal kdv dahil fiyatı olarak calculated_original_price_kdv_dahil'i ve
        # göstermek için de new_price_kdv_dahil'i göndermeliyiz.
        # Basitçe orijinal birim fiyat ve iskontolu birim fiyatı tekrar hesaplayıp göndereceğiz.
        
        # Bu kısım, kalem_guncelle'nin beklediği orijinal KDV hariç fiyatı yeniden hesaplamayı içerir.
        original_birim_fiyat_kdv_haric_calc = new_price_kdv_dahil / (1 + current_kdv_orani / 100)
        
        self.kalem_guncelle(kalem_index, self.fatura_kalemleri_ui[kalem_index][2], 
                            original_birim_fiyat_kdv_haric_calc, # Yeni KDV hariç orijinal birim fiyat
                            new_iskonto_1, new_iskonto_2, # Yeni iskontolar
                            0.0, # Bu parametre fatura anı alış fiyatı, fiyat geçmişinden gelmez
                            urun_adi=self.fatura_kalemleri_ui[kalem_index][1]) # Ürün adı
                
    def _check_stock_on_quantity_change(self): # event=None kaldırıldı
        selected_items = self.urun_arama_sonuclari_tree.selectedItems()
        if not selected_items: self.stk_l.setStyleSheet("color: black;"); return
        
        urun_id = selected_items[0].data(0, Qt.UserRole) # Ürün ID'sini UserRole'dan al
        
        urun_detaylari = None
        for iid, details in self.urun_map_filtrelenmis.items():
            if details['id'] == urun_id:
                urun_detaylari = details
                break

        if not urun_detaylari:
            self.stk_l.setStyleSheet("color: black;"); return

        mevcut_stok_db = self.db.get_stok_miktari_for_kontrol(urun_id, self.duzenleme_id)
        
        try:
            girilen_miktar = float(self.mik_e.text().replace(',', '.'))
        except ValueError:
            self.stk_l.setStyleSheet("color: black;"); return

        sepetteki_miktar = sum(k[2] for k in self.fatura_kalemleri_ui if k[0] == urun_id)
        
        if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.SIPARIS_TIP_SATIS, self.db.FATURA_TIP_ALIS_IADE]:
            if (sepetteki_miktar + girilen_miktar) > mevcut_stok_db:
                self.stk_l.setStyleSheet("color: red;")
            else:
                self.stk_l.setStyleSheet("color: green;")
        else: 
            self.stk_l.setStyleSheet("color: black;")

    def _open_urun_karti_from_sep_item(self, item, column): # item ve column sinyalden gelir
        # Ürün ID'si gizli sütunda olduğu için onu alacağız.
        urun_id_str = item.text(10) # 11. sütun (indeks 10)
        try:
            urun_id = int(urun_id_str)
        except ValueError:
            return
        
        # StokKartiPenceresi'nin PySide6 versiyonu burada çağrılacak.
        QMessageBox.information(self.app, "Ürün Kartı", f"Ürün ID: {urun_id} için ürün kartı açılacak (Placeholder).")

    def _add_date_entry_with_button(self, parent_layout, row, col, label_text, initial_date_str, entry_width=130):
        # Etiketi ekle
        parent_layout.addWidget(QLabel(label_text), row, col, Qt.AlignVCenter)
        
        # Giriş kutusu ve butonu bir araya getirecek bir container oluştur
        container_frame = QFrame(self)
        container_layout = QHBoxLayout(container_frame)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0) # Boşluğu kaldırmak için

        # Tarih giriş kutusunu oluştur ve genişliğini ayarla
        date_entry = QLineEdit()
        date_entry.setText(initial_date_str)
        date_entry.setFixedWidth(entry_width)
        container_layout.addWidget(date_entry)

        # Takvim butonunu oluştur
        calendar_button = QPushButton("🗓️")
        calendar_button.setFixedWidth(30)
        calendar_button.clicked.connect(lambda: DatePickerDialog(self.app, date_entry))
        container_layout.addWidget(calendar_button)

        # Container'ı ana layout'a ekle
        parent_layout.addWidget(container_frame, row, col + 1)
        
        return date_entry, calendar_button

class FaturaOlusturmaSayfasi(BaseIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref, fatura_tipi, duzenleme_id=None, yenile_callback=None, initial_cari_id=None, initial_urunler=None, initial_data=None):
        self.iade_modu_aktif = False
        self.original_fatura_id_for_iade = None

        self.sv_fatura_no = ""
        self.sv_tarih = datetime.now().strftime('%Y-%m-%d')
        self.sv_odeme_turu = db_manager.ODEME_TURU_NAKIT
        self.sv_vade_tarihi = ""
        self.sv_misafir_adi = ""
        self.sv_fatura_notlari = ""
        self.sv_genel_iskonto_tipi = "YOK"
        self.sv_genel_iskonto_degeri = "0,00"
        self.form_entries_order = [] 

        if initial_data and initial_data.get('iade_modu'):
            self.iade_modu_aktif = True
            self.original_fatura_id_for_iade = initial_data.get('orijinal_fatura_id')

        # BaseIslemSayfasi'nın __init__ metodunu çağırıyoruz
        super().__init__(parent, db_manager, app_ref, fatura_tipi, duzenleme_id, yenile_callback,
                         initial_cari_id=initial_cari_id, initial_urunler=initial_urunler, initial_data=initial_data)

        # DEĞİŞİKLİK BURADA: FaturaService'i app_ref parametresi ile başlatıyoruz
        from hizmetler import FaturaService
        self.fatura_service = FaturaService(self.db, app_ref=self.app)

        # Veri yükleme ve UI'ı güncelleme işlemlerini burada çağırıyoruz.
        self._load_initial_data()
        QTimer.singleShot(0, self._on_iade_modu_changed)

        self.btn_sayfa_yenile.clicked.connect(self._reset_form_for_new_invoice)
        
    def _setup_sol_panel(self, parent_frame):
        """Faturaya özel UI bileşenlerini sol panele yerleştirir."""
        parent_layout = parent_frame.layout()

        form_groupbox = QGroupBox("Fatura Bilgileri", parent_frame)
        form_layout = QGridLayout(form_groupbox)
        form_layout.setSpacing(10)
        parent_layout.addWidget(form_groupbox)

        # 1. Satır: Fatura No ve Tarih
        form_layout.addWidget(QLabel("Fatura No:"), 0, 0, Qt.AlignVCenter)
        self.f_no_e = QLineEdit()
        form_layout.addWidget(self.f_no_e, 0, 1, Qt.AlignVCenter)

        form_layout.addWidget(QLabel("Tarih:"), 0, 2, Qt.AlignVCenter)
        self.fatura_tarihi_entry = QLineEdit()
        self.fatura_tarihi_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        form_layout.addWidget(self.fatura_tarihi_entry, 0, 3, Qt.AlignVCenter)
        takvim_button_tarih = QPushButton("🗓️")
        takvim_button_tarih.setFixedWidth(30)
        takvim_button_tarih.clicked.connect(lambda: DatePickerDialog(self.app, self.fatura_tarihi_entry))
        form_layout.addWidget(takvim_button_tarih, 0, 4, Qt.AlignVCenter)

        # 2. Satır: Cari Seçimi, Bakiye ve Misafir Adı
        cari_btn_label_text = "Müşteri (*):" if self.islem_tipi == self.db.FATURA_TIP_SATIS else "Tedarikçi (*):"
        form_layout.addWidget(QLabel(cari_btn_label_text), 1, 0, Qt.AlignVCenter)
        
        cari_bilgi_container = QFrame(parent_frame)
        cari_bilgi_layout = QHBoxLayout(cari_bilgi_container)
        cari_bilgi_layout.setContentsMargins(0, 0, 0, 0)
        cari_bilgi_layout.setSpacing(5)
        
        self.btn_cari_sec = QPushButton("Cari Seç...")
        self.btn_cari_sec.clicked.connect(self._cari_secim_penceresi_ac)
        self.btn_cari_sec.setMinimumWidth(250)
        cari_bilgi_layout.addWidget(self.btn_cari_sec, 2)

        self.lbl_cari_bakiye = QLabel("Bakiye: ---")
        self.lbl_cari_bakiye.setFont(QFont("Segoe UI", 9, QFont.Bold))
        cari_bilgi_layout.addWidget(self.lbl_cari_bakiye, 1)

        self.misafir_adi_container_frame = QFrame(parent_frame)
        self.misafir_adi_container_layout = QHBoxLayout(self.misafir_adi_container_frame)
        self.misafir_adi_container_layout.setContentsMargins(0,0,0,0)
        
        self.misafir_adi_container_layout.addWidget(QLabel("Misafir Adı:"))
        self.entry_misafir_adi = QLineEdit()
        self.entry_misafir_adi.setText(self.sv_misafir_adi)
        self.entry_misafir_adi.setFixedWidth(100)
        self.misafir_adi_container_layout.addWidget(self.entry_misafir_adi)
        
        cari_bilgi_layout.addWidget(self.misafir_adi_container_frame)
        self.misafir_adi_container_frame.setVisible(False)
        
        form_layout.addWidget(cari_bilgi_container, 1, 1, 1, 4, Qt.AlignVCenter)

        # 3. Satır: Ödeme Tipi ve İşlem Kasa/Banka
        form_layout.addWidget(QLabel("Ödeme Türü:"), 2, 0, Qt.AlignVCenter)
        self.odeme_turu_cb = QComboBox()
        self.odeme_turu_cb.addItems([self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART,
                                     self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK,
                                     self.db.ODEME_TURU_SENET, self.db.ODEME_TURU_ACIK_HESAP,
                                     self.db.ODEME_TURU_ETKISIZ_FATURA])
        self.odeme_turu_cb.setCurrentText(self.sv_odeme_turu)
        self.odeme_turu_cb.currentIndexChanged.connect(self._odeme_turu_degisince_event_handler)
        form_layout.addWidget(self.odeme_turu_cb, 2, 1, Qt.AlignVCenter)

        form_layout.addWidget(QLabel("İşlem Kasa/Banka:"), 2, 2, Qt.AlignVCenter)
        self.islem_hesap_cb = QComboBox()
        self.islem_hesap_cb.setEnabled(False)
        form_layout.addWidget(self.islem_hesap_cb, 2, 3, 1, 2, Qt.AlignVCenter)

        # 4. Satır: Vade Tarihi
        self.lbl_vade_tarihi = QLabel("Vade Tarihi:")
        form_layout.addWidget(self.lbl_vade_tarihi, 3, 0, Qt.AlignVCenter)
        self.entry_vade_tarihi = QLineEdit()
        self.entry_vade_tarihi.setText(self.sv_vade_tarihi)
        self.entry_vade_tarihi.setEnabled(False)
        form_layout.addWidget(self.entry_vade_tarihi, 3, 1, Qt.AlignVCenter)
        self.btn_vade_tarihi = QPushButton("🗓️")
        self.btn_vade_tarihi.setFixedWidth(30)
        self.btn_vade_tarihi.clicked.connect(lambda: DatePickerDialog(self.app, self.entry_vade_tarihi))
        self.btn_vade_tarihi.setEnabled(False)
        form_layout.addWidget(self.btn_vade_tarihi, 3, 2, Qt.AlignVCenter)
        self.lbl_vade_tarihi.hide()
        self.entry_vade_tarihi.hide()
        self.btn_vade_tarihi.hide()

        # 5. Satır: Fatura Notları
        form_layout.addWidget(QLabel("Fatura Notları:"), 4, 0, Qt.AlignTop)
        self.fatura_notlari_text = QTextEdit()
        self.fatura_notlari_text.setFixedHeight(80)
        form_layout.addWidget(self.fatura_notlari_text, 4, 1, 1, 4)

        # 6. Satır: Genel İsk
        form_layout.addWidget(QLabel("Genel İsk Tipi:"), 5, 0, Qt.AlignVCenter)
        self.genel_iskonto_tipi_cb = QComboBox()
        self.genel_iskonto_tipi_cb.addItems(["YOK", "YUZDE", "TUTAR"])
        self.genel_iskonto_tipi_cb.setCurrentText(self.sv_genel_iskonto_tipi)
        self.genel_iskonto_tipi_cb.currentIndexChanged.connect(self._on_genel_iskonto_tipi_changed)
        form_layout.addWidget(self.genel_iskonto_tipi_cb, 5, 1, Qt.AlignVCenter)

        form_layout.addWidget(QLabel("Genel İsk Değeri:"), 5, 2, Qt.AlignVCenter)
        self.genel_iskonto_degeri_e = QLineEdit()
        self.genel_iskonto_degeri_e.setText(self.sv_genel_iskonto_degeri)
        self.genel_iskonto_degeri_e.setEnabled(False)
        self.genel_iskonto_degeri_e.textChanged.connect(self.toplamlari_hesapla_ui)
        form_layout.addWidget(self.genel_iskonto_degeri_e, 5, 3, Qt.AlignVCenter)
        
        form_layout.setColumnStretch(1, 1)
        form_layout.setColumnStretch(3, 1)
                                
    def _setup_alt_bar(self):
        """Genel toplamlar ve kaydetme butonunu içeren alt barı oluşturur."""
        # Ana yatay layout
        self.alt_layout = QHBoxLayout(self.alt_f)
        self.alt_f.setContentsMargins(10, 10, 10, 10)
        self.alt_f.setFrameShape(QFrame.StyledPanel)
        self.alt_f.setStyleSheet("background-color: #f0f0f0;")

        # DÜZELTME: Yazı tipi boyutlarını ve boşlukları güncelliyoruz.
        font_t = QFont("Segoe UI", 12, QFont.Bold)
        font_d_kucuk = QFont("Segoe UI", 16, QFont.Bold)
        font_d_buyuk = QFont("Segoe UI", 20, QFont.Bold)
        
        # Etiketleri oluşturma
        self.alt_layout.addWidget(QLabel("KDV Hariç Toplam:", font=font_t))
        self.tkh_l = QLabel("0.00 TL", font=font_d_kucuk)
        self.alt_layout.addWidget(self.tkh_l)

        self.alt_layout.addSpacing(36)

        self.alt_layout.addWidget(QLabel("Toplam KDV:", font=font_t))
        self.tkdv_l = QLabel("0.00 TL", font=font_d_kucuk)
        self.alt_layout.addWidget(self.tkdv_l)
        
        self.alt_layout.addSpacing(36)

        self.alt_layout.addWidget(QLabel("Uygulanan Genel İsk:", font=font_t))
        self.lbl_uygulanan_genel_iskonto = QLabel("0.00 TL", font=font_d_kucuk)
        self.alt_layout.addWidget(self.lbl_uygulanan_genel_iskonto)
        
        self.alt_layout.addSpacing(36)

        self.alt_layout.addWidget(QLabel("Genel Toplam:", font=font_t))
        self.gt_l = QLabel("0.00 TL", font=font_d_buyuk)
        self.alt_layout.addWidget(self.gt_l)
        
        # Esneklik ekleyerek butonları sağa yaslıyoruz
        self.alt_layout.addStretch()

        self.btn_iptal = QPushButton("İptal")
        self.btn_iptal.setMinimumWidth(100)
        self.btn_iptal.clicked.connect(self.cancelled_successfully.emit)
        self.alt_layout.addWidget(self.btn_iptal)

        self.btn_kaydet = QPushButton("Kaydet")
        self.btn_kaydet.setMinimumWidth(100)
        self.btn_kaydet.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_kaydet.setStyleSheet("padding: 5px 10px; background-color: #4CAF50; color: white;")
        self.btn_kaydet.clicked.connect(self.kaydet)
        self.alt_layout.addWidget(self.btn_kaydet)

    def _on_iade_modu_changed(self):
        # DÜZELTME: self.parent() yerine self.parent kullanıldı
        if isinstance(self.parent, QDialog):
            self.parent.setWindowTitle(self._get_baslik())
        elif isinstance(self.parent, QMainWindow):
            self.parent.setWindowTitle(self._get_baslik())
        
        if self.iade_modu_aktif:
            if hasattr(self, 'f_no_e'):
                # GÜNCELLEME: Çağrıdan 'kullanici_id' parametresi kaldırıldı.
                self.f_no_e.setText(self.db.son_fatura_no_getir(self.islem_tipi))
            if hasattr(self, 'cari_sec_button'):
                self.cari_sec_button.setEnabled(False)
            
            self.app.set_status_message("İade Faturası oluşturma modu aktif.")
            
            if hasattr(self, 'odeme_turu_cb'):
                self.odeme_turu_cb.setEnabled(True)
            if hasattr(self, 'islem_hesap_cb'):
                self.islem_hesap_cb.setEnabled(True)
            if hasattr(self, 'entry_vade_tarihi'):
                self.entry_vade_tarihi.setEnabled(True)
            if hasattr(self, 'btn_vade_tarihi'):
                self.btn_vade_tarihi.setEnabled(True)
            
            if hasattr(self, '_odeme_turu_degisince_event_handler'):
                self._odeme_turu_degisince_event_handler()

            if hasattr(self, 'misafir_adi_container_frame'):
                if hasattr(self, 'entry_misafir_adi'):
                    self.entry_misafir_adi.clear()
                self.misafir_adi_container_frame.setVisible(False)
        else:
            if hasattr(self, 'f_no_e'):
                # GÜNCELLEME: Çağrıdan 'kullanici_id' parametresi kaldırıldı.
                self.f_no_e.setText(self.db.son_fatura_no_getir(self.islem_tipi))
            if hasattr(self, 'cari_sec_button'):
                self.cari_sec_button.setEnabled(True)
            if not self.duzenleme_id and hasattr(self, 'f_no_e'):
                pass
            
            if hasattr(self, '_odeme_turu_ve_misafir_adi_kontrol'):
                self._odeme_turu_ve_misafir_adi_kontrol()

    def _get_baslik(self):
        if self.iade_modu_aktif:
            return "İade Faturası Oluştur"
        if self.duzenleme_id:
            return "Fatura Güncelleme"
        return "Yeni Satış Faturası" if self.islem_tipi == self.db.FATURA_TIP_SATIS else "Yeni Alış Faturası"
                
    def _setup_ozel_alanlar(self, parent_frame):
        """Ana sınıfın sol paneline faturaya özel alanları ekler ve klavye navigasyon sırasını belirler."""
        layout = QGridLayout(parent_frame) # parent_frame'in layout'unu ayarla

        # Fatura No ve Tarih
        layout.addWidget(QLabel("Fatura No:"), 0, 0)
        self.f_no_e = QLineEdit()
        self.f_no_e.setText(self.sv_fatura_no) # Değeri ata
        layout.addWidget(self.f_no_e, 0, 1)
        self.form_entries_order.append(self.f_no_e)

        layout.addWidget(QLabel("Tarih:"), 0, 2)
        self.fatura_tarihi_entry = QLineEdit()
        self.fatura_tarihi_entry.setText(self.sv_tarih) # Değeri ata
        layout.addWidget(self.fatura_tarihi_entry, 0, 3)
        takvim_button_tarih = QPushButton("🗓️")
        takvim_button_tarih.setFixedWidth(30)
        takvim_button_tarih.clicked.connect(lambda: DatePickerDialog(self.app, self.fatura_tarihi_entry))
        layout.addWidget(takvim_button_tarih, 0, 4)
        self.form_entries_order.append(self.fatura_tarihi_entry)

        # Cari Seçim
        cari_btn_label_text = "Müşteri Seç:" if self.islem_tipi == self.db.FATURA_TIP_SATIS else "Tedarikçi Seç:"
        layout.addWidget(QLabel(cari_btn_label_text), 1, 0)
        self.cari_sec_button = QPushButton("Cari Seç...")
        layout.addWidget(self.cari_sec_button, 1, 1)
        self.lbl_secili_cari_adi = QLabel("Seçilen Cari: Yok")
        self.lbl_secili_cari_adi.setFont(QFont("Segoe UI", 9, QFont.Bold))
        layout.addWidget(self.lbl_secili_cari_adi, 1, 2, 1, 3) # 1 satır, 3 sütun kapla
        self.form_entries_order.append(self.cari_sec_button)

        # Bakiye ve Misafir Adı
        self.lbl_cari_bakiye = QLabel("Bakiye: ...")
        self.lbl_cari_bakiye.setFont(QFont("Segoe UI", 9, QFont.Bold))
        layout.addWidget(self.lbl_cari_bakiye, 2, 0, 1, 2)
        
        self.misafir_adi_container_frame = QFrame(parent_frame)
        self.misafir_adi_container_layout = QHBoxLayout(self.misafir_adi_container_frame)
        self.misafir_adi_container_layout.setContentsMargins(0,0,0,0) # İç boşlukları sıfırla
        layout.addWidget(self.misafir_adi_container_frame, 2, 2, 1, 3) # Grid'e yerleştir
        self.misafir_adi_container_frame.setVisible(False) # Başlangıçta gizli

        self.misafir_adi_container_layout.addWidget(QLabel("Misafir Adı :"))
        self.entry_misafir_adi = QLineEdit()
        self.entry_misafir_adi.setText(self.sv_misafir_adi) # Değeri ata
        self.misafir_adi_container_layout.addWidget(self.entry_misafir_adi)
        self.form_entries_order.append(self.entry_misafir_adi)

        # Ödeme Türü
        layout.addWidget(QLabel("Ödeme Türü:"), 3, 0)
        self.odeme_turu_cb = QComboBox()
        self.odeme_turu_cb.addItems([self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
                                     self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
                                     self.db.ODEME_TURU_SENET, self.db.ODEME_TURU_ACIK_HESAP, 
                                     self.db.ODEME_TURU_ETKISIZ_FATURA])
        self.odeme_turu_cb.setCurrentText(self.sv_odeme_turu) # Değeri ata
        self.odeme_turu_cb.currentIndexChanged.connect(self._odeme_turu_degisince_event_handler)
        layout.addWidget(self.odeme_turu_cb, 3, 1)
        self.form_entries_order.append(self.odeme_turu_cb)

        # Kasa/Banka
        layout.addWidget(QLabel("İşlem Kasa/Banka:"), 4, 0)
        self.islem_hesap_cb = QComboBox()
        # QComboBox'a değerler _yukle_kasa_banka_hesaplarini metodunda eklenecek.
        self.islem_hesap_cb.setEnabled(False) # Başlangıçta pasif
        layout.addWidget(self.islem_hesap_cb, 4, 1, 1, 3) # 1 satır, 3 sütun kapla
        self.form_entries_order.append(self.islem_hesap_cb)

        # Vade Tarihi
        self.lbl_vade_tarihi = QLabel("Vade Tarihi:")
        layout.addWidget(self.lbl_vade_tarihi, 5, 0)
        self.entry_vade_tarihi = QLineEdit()
        self.entry_vade_tarihi.setText(self.sv_vade_tarihi) # Değeri ata
        self.entry_vade_tarihi.setEnabled(False) # Başlangıçta pasif
        layout.addWidget(self.entry_vade_tarihi, 5, 1)
        self.btn_vade_tarihi = QPushButton("🗓️")
        self.btn_vade_tarihi.setFixedWidth(30)
        self.btn_vade_tarihi.clicked.connect(lambda: DatePickerDialog(self.app, self.entry_vade_tarihi))
        self.btn_vade_tarihi.setEnabled(False) # Başlangıçta pasif
        layout.addWidget(self.btn_vade_tarihi, 5, 2)
        self.form_entries_order.append(self.entry_vade_tarihi)


        # Fatura Notları
        layout.addWidget(QLabel("Fatura Notları:"), 6, 0, Qt.AlignTop)
        self.fatura_notlari_text = QTextEdit()
        # self.fatura_notlari_text.setPlainText(self.sv_fatura_notlari) # QTextEdit'in setText'i direkt string alır
        layout.addWidget(self.fatura_notlari_text, 6, 1, 1, 4) # 1 satır, 4 sütun kapla
        self.form_entries_order.append(self.fatura_notlari_text)

        # Genel İsk
        layout.addWidget(QLabel("Genel İsk Tipi:"), 7, 0)
        self.genel_iskonto_tipi_cb = QComboBox()
        self.genel_iskonto_tipi_cb.addItems(["YOK", "YUZDE", "TUTAR"])
        self.genel_iskonto_tipi_cb.setCurrentText(self.sv_genel_iskonto_tipi) # Değeri ata
        self.genel_iskonto_tipi_cb.currentIndexChanged.connect(self._on_genel_iskonto_tipi_changed)
        layout.addWidget(self.genel_iskonto_tipi_cb, 7, 1)
        self.form_entries_order.append(self.genel_iskonto_tipi_cb)

        layout.addWidget(QLabel("Genel İsk Değeri:"), 7, 2)
        self.genel_iskonto_degeri_e = QLineEdit()
        self.genel_iskonto_degeri_e.setText(self.sv_genel_iskonto_degeri) # Değeri ata
        self.genel_iskonto_degeri_e.setEnabled(False) # Başlangıçta pasif
        self.genel_iskonto_degeri_e.textChanged.connect(self.toplamlari_hesapla_ui) # Klavye inputu için
        layout.addWidget(self.genel_iskonto_degeri_e, 7, 3)
        self.form_entries_order.append(self.genel_iskonto_degeri_e)

        # Column stretch for appropriate columns (Ödeme Türü, Kasa/Banka, Fatura Notları)
        layout.setColumnStretch(1, 1) # Fatura No, Ödeme Türü, Genel İsk Tipi
        layout.setColumnStretch(3, 1) # Tarih, Genel İsk Değeri

    def _ot_odeme_tipi_degisince(self, *args): # event=None kaldırıldı
        """Hızlı işlem formunda ödeme tipi değiştiğinde kasa/banka seçimini ayarlar."""
        selected_odeme_sekli = self.ot_odeme_tipi_combo.currentText() # QComboBox'tan metin al
        varsayilan_kb_db = self.db.get_kasa_banka_by_odeme_turu(selected_odeme_sekli)

        if varsayilan_kb_db:
            varsayilan_kb_id = varsayilan_kb_db[0]
            found_and_set = False
            for text, id_val in self.kasa_banka_map.items():
                if id_val == varsayilan_kb_id:
                    self.ot_kasa_banka_combo.setCurrentText(text) # QComboBox'a metin ata
                    found_and_set = True
                    break
            if not found_and_set and self.ot_kasa_banka_combo.count() > 1: # İlk öğe boş olabilir
                self.ot_kasa_banka_combo.setCurrentIndex(1) # İlk geçerli hesabı seç
        elif self.ot_kasa_banka_combo.count() > 0: # Eğer varsayılan yoksa, ilkini seç (eğer varsa)
            self.ot_kasa_banka_combo.setCurrentIndex(0) # İlk öğeyi seç
        else:
            self.ot_kasa_banka_combo.clear() # Hiç hesap yoksa temizle

    def _load_initial_data(self):
        """
        FaturaOlusturmaSayfasi'na özel başlangıç veri yükleme mantığı.
        """
        # Fatura sayfasında kullanılan widget'ları oluşturmak için özel metotları çağırıyoruz.
        self._yukle_kasa_banka_hesaplarini()
        self._carileri_yukle_ve_cachele() 
        self._urunleri_yukle_ve_cachele_ve_goster()
        
        if self.duzenleme_id:
            self._mevcut_faturayi_yukle()
            logging.debug("FaturaOlusturmaSayfasi - Düzenleme modunda, mevcut fatura yüklendi.")
        elif self.initial_data:
            self._load_temp_form_data(forced_temp_data=self.initial_data)
            logging.debug("FaturaOlusturmaSayfasi - initial_data ile taslak veri yüklendi.")
        else:
            # Yeni bir fatura oluşturuluyor. Önce formu sıfırla.
            self._reset_form_for_new_invoice(ask_confirmation=False)
            logging.debug("FaturaOlusturmaSayfasi - Yeni fatura için form sıfırlandı.")
                    
        if hasattr(self, 'urun_arama_entry'):
            self.urun_arama_entry.setFocus()

    def kaydet(self):
        fatura_no = self.f_no_e.text().strip()
        fatura_tarihi = self.fatura_tarihi_entry.text().strip()
        odeme_turu = self.odeme_turu_cb.currentText()
        vade_tarihi = self.entry_vade_tarihi.text().strip() if self.entry_vade_tarihi.isVisible() and self.entry_vade_tarihi.text().strip() else None
        fatura_notlari = self.fatura_notlari_text.toPlainText().strip()
        genel_iskonto_tipi = self.genel_iskonto_tipi_cb.currentText()
        genel_iskonto_degeri = float(self.genel_iskonto_degeri_e.text().replace(',', '.')) if self.genel_iskonto_degeri_e.isEnabled() else 0.0
        misafir_adi = self.entry_misafir_adi.text().strip() if self.misafir_adi_container_frame.isVisible() else None

        kasa_banka_id = self.islem_hesap_cb.currentData() if self.islem_hesap_cb.isEnabled() else None

        if not fatura_no: QMessageBox.critical(self.app, "Eksik Bilgi", "Fatura Numarası boş olamaz."); return
        try: datetime.strptime(fatura_tarihi, '%Y-%m-%d')
        except ValueError: QMessageBox.critical(self.app, "Hata", "Fatura Tarihi formatı (YYYY-AA-GG) olmalıdır."); return

        if not self.secili_cari_id and not misafir_adi: QMessageBox.critical(self.app, "Eksik Bilgi", "Lütfen bir cari seçin veya Misafir Adı girin."); return
        if odeme_turu == self.db.ODEME_TURU_ACIK_HESAP and not vade_tarihi: QMessageBox.critical(self.app, "Eksik Bilgi", "Açık Hesap için Vade Tarihi zorunludur."); return
        if vade_tarihi:
            try: datetime.strptime(vade_tarihi, '%Y-%m-%d')
            except ValueError: QMessageBox.critical(self.app, "Hata", "Vade Tarihi formatı (YYYY-AA-GG) olmalıdır."); return

        if odeme_turu in self.db.pesin_odeme_turleri and kasa_banka_id is None: QMessageBox.critical(self.app, "Eksik Bilgi", "Peşin ödeme türleri için Kasa/Banka seçimi zorunludur."); return
        if not self.fatura_kalemleri_ui: QMessageBox.critical(self.app, "Eksik Bilgi", "Faturada en az bir kalem olmalıdır."); return

        kalemler_to_send_to_api = []
        for k_ui in self.fatura_kalemleri_ui:
            kalemler_to_send_to_api.append({
                "urun_id": k_ui[0], "miktar": self.db.safe_float(k_ui[2]), "birim_fiyat": self.db.safe_float(k_ui[3]),
                "kdv_orani": self.db.safe_float(k_ui[4]), "alis_fiyati_fatura_aninda": self.db.safe_float(k_ui[8]),
                "iskonto_yuzde_1": self.db.safe_float(k_ui[10]), "iskonto_yuzde_2": self.db.safe_float(k_ui[11]),
                "iskonto_tipi": k_ui[12], "iskonto_degeri": self.db.safe_float(k_ui[13])
            })

        fatura_tip_to_save = self.islem_tipi
        if self.iade_modu_aktif:
            if self.islem_tipi == self.db.FATURA_TIP_SATIS: fatura_tip_to_save = self.db.FATURA_TIP_SATIS_IADE
            elif self.islem_tipi == self.db.FATURA_TIP_ALIS: fatura_tip_to_save = self.db.FATURA_TIP_ALIS_IADE
            
        # HATA DÜZELTİLDİ: 'cari_tip' bilgisi burada belirlenip API'ye gönderiliyor.
        cari_tip_to_save = self.db.CARI_TIP_MUSTERI if fatura_tip_to_save in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_SATIS_IADE] else self.db.CARI_TIP_TEDARIKCI
        
        try:
            olusturan_kullanici_id = self.app.current_user.get("id") if self.app and hasattr(self.app, 'current_user') and self.app.current_user else 1

            # Fatura servisine gönderilecek tüm veriler
            fatura_data = {
                "fatura_no": fatura_no,
                "tarih": fatura_tarihi,
                "fatura_turu": fatura_tip_to_save,
                "cari_id": self.secili_cari_id,
                "cari_tip": cari_tip_to_save, # <-- YENİ EKLENEN ALAN
                "kalemler": kalemler_to_send_to_api,
                "odeme_turu": odeme_turu,
                "olusturan_kullanici_id": olusturan_kullanici_id,
                "kasa_banka_id": kasa_banka_id,
                "misafir_adi": misafir_adi,
                "fatura_notlari": fatura_notlari,
                "vade_tarihi": vade_tarihi,
                "genel_iskonto_tipi": genel_iskonto_tipi,
                "genel_iskonto_degeri": genel_iskonto_degeri,
                "original_fatura_id": self.original_fatura_id_for_iade if self.iade_modu_aktif else None
            }

            if self.duzenleme_id:
                # Güncelleme fonksiyonu da tüm veriyi almalı
                success, message = self.fatura_service.fatura_guncelle(self.duzenleme_id, fatura_data)
            else:
                success, message = self.fatura_service.fatura_olustur(**fatura_data)

            if success:
                kayit_mesaji = "Fatura başarıyla güncellendi." if self.duzenleme_id else f"'{fatura_no}' numaralı fatura başarıyla kaydedildi."
                QMessageBox.information(self.app, "Başarılı", kayit_mesaji)
                
                if self.yenile_callback:
                    self.yenile_callback()
                
                if not self.duzenleme_id:
                    self._reset_form_for_new_invoice(ask_confirmation=False)
                    self.app.set_status_message(f"Fatura '{fatura_no}' kaydedildi. Yeni fatura girişi için sayfa hazır.")
                else:
                    self.app.set_status_message(f"Fatura '{fatura_no}' başarıyla güncellendi.")
                self.saved_successfully.emit()
            else:
                QMessageBox.critical(self.app, "Hata", message)

        except Exception as e:
            logging.error(f"Fatura kaydedilirken beklenmeyen bir hata oluştu: {e}\nDetaylar:\n{traceback.format_exc()}")
            QMessageBox.critical(self.app, "Kritik Hata", f"Fatura kaydedilirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Fatura kaydedilemedi - {e}", "red")

    def _mevcut_faturayi_yukle(self):
        """Mevcut bir faturayı API'den çeker ve formdaki alanları doldurur."""
        logging.info(f"Fatura ID: {self.duzenleme_id} için mevcut fatura verisi yükleniyor.")
        try:
            fatura_ana = self.db.fatura_getir_by_id(self.duzenleme_id)
            if not fatura_ana:
                QMessageBox.critical(self.app, "Hata", "Düzenlenecek fatura bilgileri alınamadı.")
                self.parent().close()
                return

            self._loaded_fatura_data_for_edit = fatura_ana

            f_no = fatura_ana.get('fatura_no', '')
            tarih_db = fatura_ana.get('tarih', '')
            c_id_db = fatura_ana.get('cari_id')
            odeme_turu_db = fatura_ana.get('odeme_turu', 'NAKİT')
            misafir_adi_db = fatura_ana.get('misafir_adi', '')
            fatura_notlari_db = fatura_ana.get('fatura_notlari', '')
            vade_tarihi_db = fatura_ana.get('vade_tarihi', '')
            genel_iskonto_tipi_db = fatura_ana.get('genel_iskonto_tipi', 'YOK')
            genel_iskonto_degeri_db = fatura_ana.get('genel_iskonto_degeri', 0.0)
            kasa_banka_id_db = fatura_ana.get('kasa_banka_id')

            self.f_no_e.setText(f_no)
            self.fatura_tarihi_entry.setText(tarih_db)
            self.fatura_notlari_text.setPlainText(fatura_notlari_db)
            self.entry_vade_tarihi.setText(vade_tarihi_db if vade_tarihi_db else "")
            self.genel_iskonto_tipi_cb.setCurrentText(genel_iskonto_tipi_db)
            self.genel_iskonto_degeri_e.setText(f"{genel_iskonto_degeri_db:.2f}".replace('.', ','))
            self._on_genel_iskonto_tipi_changed()

            # Ödeme türünü ayarla ve ilgili combobox'ı güncelle
            self.odeme_turu_cb.setCurrentText(odeme_turu_db)
            self._odeme_turu_degisince_event_handler()

            # Cari bilgisini ayarla
            display_text_for_cari = self.cari_id_to_display_map.get(str(c_id_db), "Bilinmeyen Cari")
            self._on_cari_secildi_callback(c_id_db, display_text_for_cari)

            # Perakende satışlar için misafir adını ayarla
            if str(c_id_db) == str(self.db.get_perakende_musteri_id()) and misafir_adi_db:
                self.entry_misafir_adi.setText(misafir_adi_db)

            # Kasa/Banka combobox'ını ayarla
            if kasa_banka_id_db is not None:
                kb_text_to_set = ""
                for text, kb_id in self.kasa_banka_map.items():
                    if kb_id == kasa_banka_id_db:
                        kb_text_to_set = text
                        break
                if kb_text_to_set:
                    self.islem_hesap_cb.setCurrentText(kb_text_to_set)

            # Fatura kalemlerini yükle
            fatura_kalemleri_db = self.db.fatura_kalemleri_al(self.duzenleme_id)
            self.fatura_kalemleri_ui.clear()
            for k_db in fatura_kalemleri_db:
                iskontolu_birim_fiyat_kdv_dahil = (k_db.get('kalem_toplam_kdv_dahil', 0.0) / k_db.get('miktar', 1.0)) if k_db.get('miktar', 1.0) != 0 else 0.0
                self.fatura_kalemleri_ui.append((
                    k_db.get('urun_id'), k_db.get('urun_adi'), k_db.get('miktar'),
                    k_db.get('birim_fiyat'), k_db.get('kdv_orani'), k_db.get('kdv_tutari'),
                    k_db.get('kalem_toplam_kdv_haric'), k_db.get('kalem_toplam_kdv_dahil'),
                    k_db.get('alis_fiyati_fatura_aninda'), k_db.get('kdv_orani'),
                    k_db.get('iskonto_yuzde_1'), k_db.get('iskonto_yuzde_2'),
                    k_db.get('iskonto_tipi'), k_db.get('iskonto_degeri'),
                    iskontolu_birim_fiyat_kdv_dahil
                ))

            self.sepeti_guncelle_ui()
            self.toplamlari_hesapla_ui()
            self.urun_arama_entry.setFocus()
            logging.info(f"Fatura ID: {self.duzenleme_id} verileri başarıyla yüklendi.")

        except Exception as e:
            logging.error(f"Mevcut fatura verileri yüklenirken hata oluştu: {e}", exc_info=True)
            QMessageBox.critical(self.app, "Hata", f"Mevcut fatura verileri yüklenirken bir hata oluştu: {e}")
            
    def _reset_form_for_new_invoice(self, ask_confirmation=True, skip_default_cari_selection=False):
        # YENİ EKLENEN KOD: Onay mekanizması
        if ask_confirmation:
            reply = QMessageBox.question(self.app, "Sayfayı Yenile",
                                         "Formdaki tüm kaydedilmemiş veriler silinecek ve sayfa sıfırlanacaktır. Emin misiniz?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return False # Kullanıcı iptal ettiyse işlem yapma

        self.duzenleme_id = None
        self.fatura_kalemleri_ui = []
        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()

        try:
            fatura_no = self.db.son_fatura_no_getir(self.islem_tipi)
            if "HATA" in fatura_no or "MANUEL" in fatura_no:
                raise Exception("API'den otomatik fatura numarası alınamadı.")
            self.f_no_e.setText(fatura_no)
        except Exception as e:
            QMessageBox.warning(self.app, "Fatura Numarası Hatası", f"Otomatik fatura numarası alınırken bir hata oluştu: {e}. Lütfen manuel olarak giriniz.")
            logging.error(f"Otomatik fatura numarası hatası: {e}", exc_info=True)
            self.f_no_e.clear()

        self.fatura_tarihi_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        self.odeme_turu_cb.setCurrentText(self.db.ODEME_TURU_NAKIT)
        self.fatura_notlari_text.clear()
        self.genel_iskonto_tipi_cb.setCurrentText("YOK")
        self.genel_iskonto_degeri_e.setText("0,00")
        
        self._temizle_cari_secimi()
        
        if not skip_default_cari_selection:
            try:
                if self.islem_tipi == self.db.FATURA_TIP_SATIS:
                    perakende_id = self.db.get_perakende_musteri_id()
                    if perakende_id:
                        perakende_data = self.db.musteri_getir_by_id(musteri_id=perakende_id)
                        if perakende_data:
                            self._on_cari_secildi_callback(perakende_data.get('id'), perakende_data.get('ad'))
                
                elif self.islem_tipi == self.db.FATURA_TIP_ALIS:
                    genel_tedarikci_id = self.db.get_genel_tedarikci_id()
                    if genel_tedarikci_id:
                        genel_tedarikci_data = self.db.tedarikci_getir_by_id(
                            tedarikci_id=genel_tedarikci_id, 
                            kullanici_id=self.app.current_user_id
                        )
                        if genel_tedarikci_data:
                            self._on_cari_secildi_callback(genel_tedarikci_data.get('id'), genel_tedarikci_data.get('ad'))
            except Exception as e:
                logging.warning(f"Varsayılan cari yüklenirken hata: {e}")
                self.app.set_status_message(f"Uyarı: Varsayılan cari bilgisi yüklenemedi. {e}", "orange")

        self.urun_arama_entry.clear()
        self.mik_e.setText("1")
        self.birim_fiyat_e.setText("0,00")
        self.stk_l.setText("-")
        self.stk_l.setStyleSheet("color: black;")
        self.iskonto_yuzde_1_e.setText("0,00")
        self.iskonto_yuzde_2_e.setText("0,00")
        
        # Bu çağrılar formun durumunu son haline getirir
        self._on_genel_iskonto_tipi_changed()
        self._odeme_turu_degisince_event_handler()
        
        self.app.set_status_message(f"Yeni {self.islem_tipi.lower()} faturası için sayfa sıfırlandı.", "blue")
        QTimer.singleShot(0, self._urunleri_yukle_ve_cachele_ve_goster)
        self.urun_arama_entry.setFocus()
        return True

    def _odeme_turu_degisince_event_handler(self):
        selected_odeme_turu = self.odeme_turu_cb.currentText()
        
        is_acik_hesap = (selected_odeme_turu == self.db.ODEME_TURU_ACIK_HESAP)

        # 'Vade Tarihi' alanlarının görünürlüğünü ve etkinliğini ayarla
        if hasattr(self, 'lbl_vade_tarihi'):
            self.lbl_vade_tarihi.setVisible(is_acik_hesap)
        if hasattr(self, 'entry_vade_tarihi'):
            self.entry_vade_tarihi.setVisible(is_acik_hesap)
            self.entry_vade_tarihi.setEnabled(is_acik_hesap)
        if hasattr(self, 'btn_vade_tarihi'):
            self.btn_vade_tarihi.setVisible(is_acik_hesap)
            self.btn_vade_tarihi.setEnabled(is_acik_hesap)

        if is_acik_hesap and hasattr(self, 'entry_vade_tarihi') and not self.entry_vade_tarihi.text():
            self.entry_vade_tarihi.setText((datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'))
        elif not is_acik_hesap and hasattr(self, 'entry_vade_tarihi'):
            self.entry_vade_tarihi.clear()

        # Diğer ilgili kontrolleri çağır
        self._odeme_turu_ve_misafir_adi_kontrol()
        self._odeme_turu_degisince_hesap_combobox_ayarla()

    def _odeme_turu_ve_misafir_adi_kontrol(self):
        """
        Cari seçimine göre Misafir Adı alanının görünürlüğünü/aktifliğini ve 
        ödeme türü seçeneklerini dinamik olarak yönetir.
        """
        secili_cari_id_str = str(self.secili_cari_id) if self.secili_cari_id is not None else None

        perakende_musteri_id_str = "-1"
        genel_tedarikci_id_str = "-1"
        try:
            perakende_musteri_id_str = str(self.db.get_perakende_musteri_id())
        except Exception: pass
        try:
            genel_tedarikci_id_str = str(self.db.get_genel_tedarikci_id())
        except Exception: pass

        is_default_cari = (
            (self.islem_tipi == self.db.FATURA_TIP_SATIS and secili_cari_id_str == perakende_musteri_id_str) or
            (self.islem_tipi == self.db.FATURA_TIP_ALIS and secili_cari_id_str == genel_tedarikci_id_str)
        )

        is_perakende_satis = (self.islem_tipi == self.db.FATURA_TIP_SATIS and secili_cari_id_str == perakende_musteri_id_str)
        if hasattr(self, 'misafir_adi_container_frame'):
            self.misafir_adi_container_frame.setVisible(is_perakende_satis and not self.iade_modu_aktif)
            if hasattr(self, 'entry_misafir_adi'):
                self.entry_misafir_adi.setEnabled(is_perakende_satis and not self.iade_modu_aktif)
                if not is_perakende_satis:
                    self.entry_misafir_adi.clear()

        all_payment_values = [
            self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
            self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
            self.db.ODEME_TURU_SENET, self.db.ODEME_TURU_ACIK_HESAP
        ]
        
        target_payment_values = [p for p in all_payment_values if p != self.db.ODEME_TURU_ACIK_HESAP] if is_default_cari else all_payment_values[:]
        current_selected_odeme_turu = self.odeme_turu_cb.currentText()
        
        self.odeme_turu_cb.blockSignals(True)
        try:
            self.odeme_turu_cb.clear()
            self.odeme_turu_cb.addItems(target_payment_values)

            if current_selected_odeme_turu in target_payment_values:
                self.odeme_turu_cb.setCurrentText(current_selected_odeme_turu)
            elif is_default_cari:
                self.odeme_turu_cb.setCurrentText(self.db.ODEME_TURU_NAKIT)
            else:
                self.odeme_turu_cb.setCurrentText(self.db.ODEME_TURU_ACIK_HESAP)
        finally:
            self.odeme_turu_cb.blockSignals(False)
        
        # HATA DÜZELTİLDİ: Sonsuz döngüye neden olan bu çağrı kaldırıldı.
        # self._odeme_turu_degisince_event_handler()  
        
        # Sadece bu metodun sorumluluğunda olan diğer fonksiyonları çağırıyoruz.
        self._odeme_turu_degisince_hesap_combobox_ayarla()

    def _odeme_turu_degisince_hesap_combobox_ayarla(self):
        selected_odeme_turu = self.odeme_turu_cb.currentText()
        pesin_odeme_turleri = ["NAKİT", "KART", "EFT/HAVALE", "ÇEK", "SENET"]
        
        # Sinyalleri geçici olarak engelle
        self.islem_hesap_cb.blockSignals(True)
        self.islem_hesap_cb.clear()
        self.kasa_banka_map.clear()

        # Eğer ödeme türü 'AÇIK HESAP' ise Kasa/Banka devre dışı kalmalı
        if selected_odeme_turu == self.db.ODEME_TURU_ACIK_HESAP:
            self.islem_hesap_cb.addItem("Hesap Yok", userData=None)
            self.islem_hesap_cb.setEnabled(False)
        elif selected_odeme_turu in pesin_odeme_turleri:
            try:
                hesaplar_response = self.db.kasa_banka_listesi_al(limit=10000)
                hesaplar = hesaplar_response.get("items", [])
                
                if hesaplar:
                    for h in hesaplar:
                        display_text = f"{h.get('hesap_adi')} ({h.get('tip')})"
                        if h.get('tip') == "BANKA" and h.get('banka_adi'):
                            display_text += f" - {h.get('banka_adi')}"
                        self.kasa_banka_map[display_text] = h.get('id')
                        self.islem_hesap_cb.addItem(display_text, h.get('id'))
                    
                    self.islem_hesap_cb.setEnabled(True)
                    varsayilan_kb_info = self.db.get_kasa_banka_by_odeme_turu(selected_odeme_turu)
                    if varsayilan_kb_info and varsayilan_kb_info[0]:
                        varsayilan_kb_id = varsayilan_kb_info[0]
                        index_to_set = self.islem_hesap_cb.findData(varsayilan_kb_id)
                        if index_to_set != -1:
                            self.islem_hesap_cb.setCurrentIndex(index_to_set)
                        else:
                            if self.islem_hesap_cb.count() > 0: self.islem_hesap_cb.setCurrentIndex(0)
                    elif self.islem_hesap_cb.count() > 0:
                        self.islem_hesap_cb.setCurrentIndex(0)
                    else:
                        self.islem_hesap_cb.addItem("Hesap Yok", None)
                        self.islem_hesap_cb.setEnabled(False)
                else:
                    self.islem_hesap_cb.addItem("Hesap Yok", None)
                    self.islem_hesap_cb.setEnabled(False)
                    
            except Exception as e:
                logging.warning(f"Kasa/Banka hesapları yüklenirken hata: {e}")
                self.islem_hesap_cb.clear()
                self.islem_hesap_cb.addItem("Hesap Yok", None)
                self.islem_hesap_cb.setEnabled(False)
        else:
            self.islem_hesap_cb.addItem("Hesap Yok", userData=None)
            self.islem_hesap_cb.setEnabled(False)

        self.islem_hesap_cb.blockSignals(False)

    def _connect_signals(self):
        """UI elementlerinin sinyallerini ilgili metotlara bağlar."""
        self.btn_cari_sec.clicked.connect(self._cari_secim_penceresi_ac)
        self.odeme_turu_cb.currentIndexChanged.connect(self._odeme_turu_degisince_event_handler)
        self.genel_iskonto_tipi_cb.currentIndexChanged.connect(self._on_genel_iskonto_tipi_changed)
        self.genel_iskonto_degeri_e.textChanged.connect(self.toplamlari_hesapla_ui)
        self.urun_arama_entry.textChanged.connect(self._delayed_stok_yenile)
        self.urun_arama_sonuclari_tree.itemDoubleClicked.connect(self._double_click_add_to_cart)
        self.urun_arama_sonuclari_tree.itemSelectionChanged.connect(self.secili_urun_bilgilerini_goster_arama_listesinden)
        self.btn_sepete_ekle.clicked.connect(self.kalem_ekle_arama_listesinden)
        self.btn_secili_kalemi_sil.clicked.connect(self.secili_kalemi_sil)
        self.btn_sepeti_temizle.clicked.connect(self.sepeti_temizle)
        self.btn_kaydet.clicked.connect(self.kaydet)
        self.sep_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sep_tree.customContextMenuRequested.connect(self._open_sepet_context_menu)
        self.urun_arama_sonuclari_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.urun_arama_sonuclari_tree.customContextMenuRequested.connect(self._open_urun_arama_context_menu)
        
    def _get_urun_adi_by_id(self, urun_id):
        """
        Verilen ürün ID'sine göre önbellekten ürün adını döndürür.
        Bu metot daha önce FaturaPenceresi'nde bulunuyordu.
        """
        for urun in self.tum_urunler_cache:
            if urun.get('id') == urun_id:
                return urun.get('ad')
        return "Bilinmeyen Ürün"

    def _get_original_invoice_items_from_db(self, fatura_id):
        """
        Orijinal fatura kalemlerini veritabanından çeker.
        Bu metot daha önce FaturaPenceresi'nde bulunuyordu.
        """
        try:
            return self.db.fatura_kalemleri_al(fatura_id)
        except Exception as e:
            logging.error(f"Orijinal fatura kalemleri çekilirken hata: {e}", exc_info=True)
            return []

    def _open_urun_karti_from_sep_item(self, item, column):
        """
        Sepetteki ürüne çift tıklandığında ürün kartı penceresini açar.
        Bu metot daha önce FaturaPenceresi'nde bulunuyordu.
        """
        urun_id_str = item.text(10)
        try:
            urun_id = int(urun_id_str)
        except ValueError:
            QMessageBox.critical(self.app, "Hata", "Ürün ID okunamadı.")
            return
        
        try:
            urun_detaylari = self.db.stok_getir_by_id(urun_id)
            if not urun_detaylari:
                QMessageBox.critical(self.app, "Hata", "Ürün detayları bulunamadı.")
                return
            from pencereler import StokKartiPenceresi
            dialog = StokKartiPenceresi(self.app, self.db, urun_duzenle=urun_detaylari, app_ref=self.app)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Ürün kartı açılamadı: {e}")
            logging.error(f"Ürün kartı açma hatası: {e}", exc_info=True)

    def _double_click_add_to_cart(self, item):
        """
        Ürün arama listesindeki bir ürüne çift tıklandığında ürünü sepete ekler.
        Bu metot daha önce FaturaPenceresi'nde bulunuyordu.
        """
        selected_items = self.urun_arama_sonuclari_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Geçersiz Ürün", "Lütfen sepete eklemek için arama listesinden bir ürün seçin.")
            return

        urun_id = selected_items[0].data(0, Qt.UserRole)
        if urun_id not in self.urun_map_filtrelenmis:
            QMessageBox.warning(self.app, "Geçersiz Ürün", "Seçili ürün detayları bulunamadı.")
            return
        
        urun_detaylari = self.urun_map_filtrelenmis[urun_id]
        
        # Fatura tipine göre varsayılan birim fiyatı belirle
        birim_fiyat_kdv_dahil_input = 0.0
        if self.islem_tipi == self.db.FATURA_TIP_SATIS or self.islem_tipi == self.db.FATURA_TIP_DEVIR_GIRIS:
            birim_fiyat_kdv_dahil_input = urun_detaylari.get('satis_fiyati', 0.0)
        elif self.islem_tipi == self.db.FATURA_TIP_ALIS:
            birim_fiyat_kdv_dahil_input = urun_detaylari.get('alis_fiyati', 0.0)
        elif self.islem_tipi == self.db.FATURA_TIP_SATIS_IADE:
            birim_fiyat_kdv_dahil_input = urun_detaylari.get('alis_fiyati', 0.0)
        elif self.islem_tipi == self.db.FATURA_TIP_ALIS_IADE:
            birim_fiyat_kdv_dahil_input = urun_detaylari.get('satis_fiyati', 0.0)

        # Varsayılan miktar 1 ve iskonto 0 olacak
        eklenecek_miktar = 1.0
        iskonto_yuzde_1 = 0.0
        iskonto_yuzde_2 = 0.0

        # Satış ve Satış İade faturalarında stok kontrolü yap
        if self.islem_tipi in [self.db.FATURA_TIP_SATIS, self.db.FATURA_TIP_ALIS_IADE]:
            mevcut_stok = urun_detaylari.get('miktar', 0.0)
            
            sepetteki_urun_miktari = sum(k[2] for k in self.fatura_kalemleri_ui if k[0] == urun_id)
            
            # Eğer mevcut bir fatura düzenleniyorsa, orijinal fatura kalemindeki miktarı mevcut stoka geri ekle
            if self.duzenleme_id:
                original_fatura_kalemleri = self._get_original_invoice_items_from_db(self.duzenleme_id)
                for orig_kalem in original_fatura_kalemleri:
                    if orig_kalem['urun_id'] == urun_id:
                        if self.islem_tipi == self.db.FATURA_TIP_SATIS:
                            mevcut_stok += orig_kalem['miktar']
                        elif self.islem_tipi == self.db.FATURA_TIP_ALIS_IADE:
                            mevcut_stok += orig_kalem['miktar']
                        break
            
            if (sepetteki_urun_miktari + eklenecek_miktar) > mevcut_stok:
                reply = QMessageBox.question(self.app, "Stok Uyarısı",
                                            f"'{urun_detaylari['ad']}' için stok yetersiz!\n"
                                            f"Mevcut stok: {mevcut_stok:.2f} adet\n"
                                            f"Sepete eklenecek toplam: {sepetteki_urun_miktari + eklenecek_miktar:.2f} adet\n\n"
                                            "Devam etmek negatif stok oluşturacaktır. Emin misiniz?",
                                            QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No: return

        # Ürünün orijinal alış fiyatı, eğer satış faturasıysa. Kalem detayına kaydedilecek.
        alis_fiyati_fatura_aninda = urun_detaylari.get('alis_fiyati', 0.0)

        # Ürün sepette zaten varsa, sadece miktarını artır
        existing_kalem_index = -1
        for i, kalem in enumerate(self.fatura_kalemleri_ui):
            if kalem[0] == urun_id:
                existing_kalem_index = i
                # Çift tıklamada miktarını 1 artır
                eklenecek_miktar = kalem[2] + 1.0
                # Birim fiyat ve iskonto oranları aynı kalsın (ilk eklendiği gibi)
                birim_fiyat_kdv_dahil_input = kalem[14]
                iskonto_yuzde_1 = kalem[10]
                iskonto_yuzde_2 = kalem[11]
                break

        # kalem_guncelle metodunu kullanarak kalemi sepete ekle veya güncelle
        self.kalem_guncelle(
            kalem_index=existing_kalem_index,
            yeni_miktar=eklenecek_miktar,
            yeni_fiyat_kdv_dahil_orijinal=birim_fiyat_kdv_dahil_input,
            yeni_iskonto_yuzde_1=iskonto_yuzde_1,
            yeni_iskonto_yuzde_2=iskonto_yuzde_2,
            yeni_alis_fiyati_fatura_aninda=alis_fiyati_fatura_aninda,
            u_id=urun_id,
            urun_adi=urun_detaylari['ad'],
        )

        # Alanları temizle ve arama kutusuna odaklan
        self.urun_arama_entry.clear()
        self.mik_e.setText("1")
        self.birim_fiyat_e.setText("0,00")
        self.iskonto_yuzde_1_e.setText("0,00")
        self.iskonto_yuzde_2_e.setText("0,00")
        self.stk_l.setText("-") # Stok etiketini temizle
        self.urun_arama_entry.setFocus()

    def fatura_listesini_yukle(self):
        self.app.set_status_message("Fatura listesi güncelleniyor...")
        current_widget = self.main_tab_widget.currentWidget()
        if hasattr(current_widget, 'fatura_listesini_yukle'):
            current_widget.fatura_listesini_yukle()

class SiparisOlusturmaSayfasi(BaseIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref, islem_tipi, duzenleme_id=None, yenile_callback=None, initial_cari_id=None, initial_urunler=None, initial_data=None):
        self.iade_modu_aktif = False 
        self.original_fatura_id_for_iade = None

        if initial_data and initial_data.get('iade_modu'):
            self.iade_modu_aktif = True
            self.original_fatura_id_for_iade = initial_data.get('orijinal_fatura_id')

        # BaseIslemSayfasi'nın __init__ metodunu çağırıyoruz
        # DÜZELTME: db_manager ve app_ref parametreleri doğru şekilde iletildi.
        super().__init__(parent, db_manager, app_ref, islem_tipi, duzenleme_id, yenile_callback,
                         initial_cari_id=initial_cari_id, initial_urunler=initial_urunler, initial_data=initial_data)

        # UI oluştuktan sonra ürün listesini doğrudan yükle
        self._urunleri_yukle_ve_cachele_ve_goster()
        
        # UI'a başlangıç verilerini yükle
        self._load_initial_data()

    def _setup_sol_panel(self, parent_frame):
        """Siparişe özel UI bileşenlerini sol panele yerleştirir."""
        parent_layout = parent_frame.layout()

        # Form elemanlarını tutacak ana grup kutusunu oluşturuyoruz
        form_groupbox = QGroupBox("Sipariş Bilgileri", parent_frame)
        form_layout = QGridLayout(form_groupbox)
        form_layout.setSpacing(10)
        parent_layout.addWidget(form_groupbox)

        # 1. Satır: Sipariş No ve Tarih
        form_layout.addWidget(QLabel("Sipariş No:"), 0, 0, Qt.AlignVCenter)
        self.s_no_e = QLineEdit()
        self.s_no_e.setPlaceholderText("Otomatik atanır")
        form_layout.addWidget(self.s_no_e, 0, 1)

        form_layout.addWidget(QLabel("Sipariş Tarihi:"), 0, 2, Qt.AlignVCenter)
        self.siparis_tarihi_entry = QLineEdit()
        self.siparis_tarihi_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        self.siparis_tarihi_entry.setFixedWidth(130) # Daraltıldı
        form_layout.addWidget(self.siparis_tarihi_entry, 0, 3)
        takvim_button_siparis_tarihi = QPushButton("🗓️")
        takvim_button_siparis_tarihi.setFixedWidth(30)
        takvim_button_siparis_tarihi.clicked.connect(lambda: DatePickerDialog(self.app, self.siparis_tarihi_entry))
        form_layout.addWidget(takvim_button_siparis_tarihi, 0, 4)

        # 2. Satır: Cari Seçimi ve Durum
        cari_btn_label_text = "Müşteri (*):" if self.islem_tipi == self.db.SIPARIS_TIP_SATIS else "Tedarikçi (*):"
        form_layout.addWidget(QLabel(cari_btn_label_text), 1, 0, Qt.AlignVCenter)
        self.btn_cari_sec = QPushButton("Cari Seç...")
        self.btn_cari_sec.clicked.connect(self._cari_secim_penceresi_ac)
        form_layout.addWidget(self.btn_cari_sec, 1, 1)
        
        # Durum menüsü ve etiketi aynı satırda olacak
        form_layout.addWidget(QLabel("Durum:"), 1, 2, Qt.AlignVCenter)
        self.durum_combo = QComboBox()
        self.durum_combo.setFixedWidth(150) # Genişlik ayarı eklendi
        self.durum_combo.addItems([self.db.SIPARIS_DURUM_BEKLEMEDE, self.db.SIPARIS_DURUM_TAMAMLANDI, self.db.SIPARIS_DURUM_KISMİ_TESLIMAT, self.db.SIPARIS_DURUM_IPTAL_EDILDI])
        form_layout.addWidget(self.durum_combo, 1, 3)

        # 3. Satır: Teslimat Tarihi ve Bakiye Bilgisi
        form_layout.addWidget(QLabel("Teslimat Tarihi:"), 2, 0, Qt.AlignVCenter)
        self.teslimat_tarihi_entry = QLineEdit()
        self.teslimat_tarihi_entry.setText((datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        self.teslimat_tarihi_entry.setFixedWidth(234) # Genişlik ayarı eklendi
        form_layout.addWidget(self.teslimat_tarihi_entry, 2, 1)
        teslimat_takvim_button = QPushButton("🗓️")
        teslimat_takvim_button.setFixedWidth(30)
        teslimat_takvim_button.clicked.connect(lambda: DatePickerDialog(self.app, self.teslimat_tarihi_entry))
        form_layout.addWidget(teslimat_takvim_button, 2, 2)
        
        self.lbl_cari_bakiye = QLabel("Bakiye: ---")
        self.lbl_cari_bakiye.setFont(QFont("Segoe UI", 9, QFont.Bold))
        form_layout.addWidget(self.lbl_cari_bakiye, 2, 3, 1, 2, Qt.AlignVCenter)

        # 4. Satır: Notlar
        form_layout.addWidget(QLabel("Sipariş Notları:"), 3, 0, Qt.AlignTop)
        self.siparis_notlari_text = QTextEdit()
        self.siparis_notlari_text.setFixedHeight(80)
        form_layout.addWidget(self.siparis_notlari_text, 3, 1, 1, 4)

        # 5. Satır: Genel İskonto
        form_layout.addWidget(QLabel("Genel İsk Tipi:"), 4, 0, Qt.AlignVCenter)
        self.genel_iskonto_tipi_cb = QComboBox()
        self.genel_iskonto_tipi_cb.addItems(["YOK", "YUZDE", "TUTAR"])
        self.genel_iskonto_tipi_cb.currentIndexChanged.connect(self._on_genel_iskonto_tipi_changed)
        form_layout.addWidget(self.genel_iskonto_tipi_cb, 4, 1)

        form_layout.addWidget(QLabel("Genel İsk Değeri:"), 4, 2, Qt.AlignVCenter)
        self.genel_iskonto_degeri_e = QLineEdit("0,00")
        self.genel_iskonto_degeri_e.setEnabled(False)
        setup_numeric_entry(self.app, self.genel_iskonto_degeri_e, decimal_places=2)
        self.genel_iskonto_degeri_e.textChanged.connect(self.toplamlari_hesapla_ui)
        form_layout.addWidget(self.genel_iskonto_degeri_e, 4, 3)

        # Esneklik ayarları
        form_layout.setColumnStretch(1, 1)
        form_layout.setColumnStretch(3, 1)

    def _get_baslik(self):
        if self.duzenleme_id:
            return "Sipariş Güncelleme"
        return "Yeni Müşteri Siparişi" if self.islem_tipi == self.db.SIPARIS_TIP_SATIS else "Yeni Tedarikçi Siparişi"

    def _setup_ozel_alanlar(self, parent_frame):
        """Ana sınıfın sol paneline siparişe özel alanları ekler ve klavye navigasyon sırasını belirler."""
        layout = QGridLayout(parent_frame)

        # Satır 0: Sipariş No ve Sipariş Tarihi
        layout.addWidget(QLabel("Sipariş No:"), 0, 0)
        self.s_no_e = QLineEdit()
        # self.s_no_e.setText(self.sv_siparis_no) # Değeri yükleme _load_initial_data'da yapılacak
        layout.addWidget(self.s_no_e, 0, 1)
        self.form_entries_order.append(self.s_no_e)

        layout.addWidget(QLabel("Sipariş Tarihi:"), 0, 2)
        self.siparis_tarihi_entry = QLineEdit()
        # self.siparis_tarihi_entry.setText(self.sv_siparis_tarihi) # Değeri yükleme _load_initial_data'da yapılacak
        layout.addWidget(self.siparis_tarihi_entry, 0, 3)
        takvim_button_siparis_tarihi = QPushButton("🗓️")
        takvim_button_siparis_tarihi.setFixedWidth(30)
        takvim_button_siparis_tarihi.clicked.connect(lambda: DatePickerDialog(self.app, self.siparis_tarihi_entry))
        layout.addWidget(takvim_button_siparis_tarihi, 0, 4)
        self.form_entries_order.append(self.siparis_tarihi_entry)

        # Satır 1: Cari Seçim
        cari_btn_label_text = "Müşteri Seç:" if self.islem_tipi == self.db.SIPARIS_TIP_SATIS else "Tedarikçi Seç:"
        layout.addWidget(QLabel(cari_btn_label_text), 1, 0)
        self.cari_sec_button = QPushButton("Cari Seç...")
        self.cari_sec_button.clicked.connect(self._cari_secim_penceresi_ac)
        layout.addWidget(self.cari_sec_button, 1, 1)
        self.lbl_secili_cari_adi = QLabel("Seçilen Cari: Yok")
        self.lbl_secili_cari_adi.setFont(QFont("Segoe UI", 9, QFont.Bold))
        layout.addWidget(self.lbl_secili_cari_adi, 1, 2, 1, 3) # 1 satır, 3 sütun kapla
        self.form_entries_order.append(self.cari_sec_button)

        # Satır 2: Cari Bakiye
        self.lbl_cari_bakiye = QLabel("Bakiye: ...")
        self.lbl_cari_bakiye.setFont(QFont("Segoe UI", 9, QFont.Bold))
        layout.addWidget(self.lbl_cari_bakiye, 2, 0, 1, 2)

        # Satır 3: Teslimat Tarihi
        layout.addWidget(QLabel("Teslimat Tarihi:"), 3, 0)
        self.teslimat_tarihi_entry = QLineEdit()
        # self.teslimat_tarihi_entry.setText(self.sv_teslimat_tarihi) # Değeri yükleme _load_initial_data'da yapılacak
        layout.addWidget(self.teslimat_tarihi_entry, 3, 1)
        teslimat_takvim_button = QPushButton("🗓️")
        teslimat_takvim_button.setFixedWidth(30)
        teslimat_takvim_button.clicked.connect(lambda: DatePickerDialog(self.app, self.teslimat_tarihi_entry))
        layout.addWidget(teslimat_takvim_button, 3, 2)
        self.form_entries_order.append(self.teslimat_tarihi_entry)

        # Satır 4: Durum
        layout.addWidget(QLabel("Durum:"), 4, 0)
        self.durum_combo = QComboBox()
        self.durum_combo.addItems(["BEKLEMEDE", "TAMAMLANDI", "KISMİ_TESLİMAT", "İPTAL_EDİLDİ"])
        # self.durum_combo.setCurrentText("BEKLEMEDE") # Değeri yükleme _load_initial_data'da yapılacak
        layout.addWidget(self.durum_combo, 4, 1)
        self.form_entries_order.append(self.durum_combo)

        # Satır 5: Notlar
        layout.addWidget(QLabel("Sipariş Notları:"), 5, 0, Qt.AlignTop)
        self.siparis_notlari_text = QTextEdit()
        # self.siparis_notlari_text.setPlainText(self.sv_siparis_notlari) # Metni _mevcut_siparisi_yukle dolduracak
        layout.addWidget(self.siparis_notlari_text, 5, 1, 1, 4)
        self.form_entries_order.append(self.siparis_notlari_text)

        # Satır 6: Genel İsk
        layout.addWidget(QLabel("Genel İsk Tipi:"), 6, 0)
        self.genel_iskonto_tipi_cb = QComboBox()
        self.genel_iskonto_tipi_cb.addItems(["YOK", "YUZDE", "TUTAR"])
        # self.genel_iskonto_tipi_cb.setCurrentText(self.sv_genel_iskonto_tipi) # Değeri yükleme _load_initial_data'da yapılacak
        self.genel_iskonto_tipi_cb.currentIndexChanged.connect(self._on_genel_iskonto_tipi_changed)
        layout.addWidget(self.genel_iskonto_tipi_cb, 6, 1)
        self.form_entries_order.append(self.genel_iskonto_tipi_cb)

        layout.addWidget(QLabel("Genel İsk Değeri:"), 6, 2)
        self.genel_iskonto_degeri_e = QLineEdit()
        # self.genel_iskonto_degeri_e.setText(self.sv_genel_iskonto_degeri) # Değeri yükleme _load_initial_data'da yapılacak
        self.genel_iskonto_degeri_e.setEnabled(False) # Başlangıçta pasif
        self.genel_iskonto_degeri_e.textChanged.connect(self.toplamlari_hesapla_ui)
        layout.addWidget(self.genel_iskonto_degeri_e, 6, 3)
        self.form_entries_order.append(self.genel_iskonto_degeri_e)

        # Column stretch
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

    def _load_initial_data(self):
        """
        SiparisOlusturmaSayfasi'na özel başlangıç veri yükleme mantığı.
        """
        if self.duzenleme_id:
            self._mevcut_siparisi_yukle()
            logging.debug("SiparisOlusturmaSayfasi - Düzenleme modunda, mevcut sipariş yüklendi.")
        elif self.initial_data:
            self._load_temp_form_data(forced_temp_data=self.initial_data)
            logging.debug("SiparisOlusturmaSayfasi - initial_data ile taslak veri yüklendi.")
        else:
            # Yeni bir sipariş oluşturuluyor. Önce formu sıfırla.
            self._reset_form_for_new_siparis(ask_confirmation=False)
            logging.debug("SiparisOlusturmaSayfasi - Yeni sipariş için form sıfırlandı.")
            
        # UI elemanları kurulduktan sonra ürünleri yükle
        QTimer.singleShot(0, self._urunleri_yukle_ve_cachele_ve_goster)
        
        # Odaklanma
        if hasattr(self, 'urun_arama_entry'):
            self.urun_arama_entry.setFocus()

    def kaydet(self):
        s_no = self.s_no_e.text().strip()
        durum = self.durum_combo.currentText()
        siparis_notlari = self.siparis_notlari_text.toPlainText().strip()
        teslimat_tarihi = self.teslimat_tarihi_entry.text().strip()
        siparis_tarihi = self.siparis_tarihi_entry.text().strip()
        genel_iskonto_tipi = self.genel_iskonto_tipi_cb.currentText()
        genel_iskonto_degeri = float(self.genel_iskonto_degeri_e.text().replace(',', '.')) if self.genel_iskonto_degeri_e.isEnabled() else 0.0

        if not s_no:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Sipariş Numarası zorunludur.")
            return
        if not self.secili_cari_id:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Lütfen bir cari seçin.")
            return
        if not self.fatura_kalemleri_ui:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Siparişte en az bir ürün olmalı.")
            return
        try:
            datetime.strptime(teslimat_tarihi, '%Y-%m-%d')
        except ValueError:
            QMessageBox.critical(self.app, "Hata", "Teslimat Tarihi formatı (YYYY-AA-GG) olmalıdır.")
            return
        try:
            datetime.strptime(siparis_tarihi, '%Y-%m-%d')
        except ValueError:
            QMessageBox.critical(self.app, "Hata", "Sipariş Tarihi formatı (YYYY-AA-GG) olmalıdır.")
            return

        kalemler_to_db = []
        for k in self.fatura_kalemleri_ui:
            kalemler_to_db.append({
                "urun_id": k[0],
                "miktar": self.db.safe_float(k[2]),
                "birim_fiyat": self.db.safe_float(k[3]),
                "kdv_orani": self.db.safe_float(k[4]),
                "alis_fiyati_fatura_aninda": self.db.safe_float(k[8]),
                "iskonto_yuzde_1": self.db.safe_float(k[10]),
                "iskonto_yuzde_2": self.db.safe_float(k[11])
            })
        
        cari_tip = "MUSTERI" if self.islem_tipi == self.db.SIPARIS_TIP_SATIS else "TEDARIKCI"

        siparis_data = {
            "tarih": siparis_tarihi,
            "cari_tip": cari_tip,
            "siparis_no": s_no,
            "siparis_turu": self.islem_tipi,
            "cari_id": self.secili_cari_id,
            "durum": durum,
            "kalemler": kalemler_to_db,
            "siparis_notlari": siparis_notlari,
            "teslimat_tarihi": teslimat_tarihi,
            "genel_iskonto_tipi": genel_iskonto_tipi,
            "genel_iskonto_degeri": genel_iskonto_degeri
        }
            
        success, message = False, ""
        try:
            if self.duzenleme_id:
                response = self.db.siparis_guncelle(siparis_id=self.duzenleme_id, data=siparis_data, kullanici_id=self.app.current_user_id)
                success, message = response
            else:
                response = self.db.siparis_ekle(data=siparis_data, kullanici_id=self.app.current_user_id)
                if isinstance(response, tuple) and len(response) == 2:
                    success, message = response
                elif response and response.get('id'):
                    success = True
                    message = "Sipariş başarıyla eklendi."
                else:
                    raise Exception("API'den beklenmeyen yanıt formatı.")
            
            if success:
                msg_title = "Sipariş Güncellendi" if self.duzenleme_id else "Sipariş Oluşturuldu"
                QMessageBox.information(self.app, msg_title, message)
                self.app.set_status_message(message)
                if self.yenile_callback:
                    self.yenile_callback()
                
                if isinstance(self.parent, QDialog):
                    self.parent.accept()
                else:
                    self._reset_form_for_new_siparis(ask_confirmation=False)
            else:
                QMessageBox.critical(self.app, "Hata", message)
        except ValueError as e:
            logger.error(f"Sipariş kaydedilirken API'den hata oluştu: {e}")
            QMessageBox.critical(self.app, "API Hatası", f"Sipariş kaydedilirken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Sipariş kaydedilemedi - {e}", "red")
        except Exception as e:
            logging.error(f"Sipariş kaydedilirken beklenmeyen bir hata oluştu: {e}\nDetaylar:\n{traceback.format_exc()}")
            QMessageBox.critical(self.app, "Kritik Hata", f"Sipariş kaydedilirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Sipariş kaydedilemedi - {e}", "red")

    def _mevcut_siparisi_yukle(self):
        siparis_ana = self.db.siparis_getir_by_id(siparis_id=self.duzenleme_id, kullanici_id=self.app.current_user_id)
        if not siparis_ana:
            QMessageBox.critical(self.app, "Hata", "Düzenlenecek sipariş bilgileri alınamadı.")
            self.parent.close()
            return

        self.s_no_e.setEnabled(True)
        self.s_no_e.setText(siparis_ana.get('siparis_no', ''))
        self.s_no_e.setEnabled(False)

        self.siparis_tarihi_entry.setText(siparis_ana.get('tarih', ''))
        self.teslimat_tarihi_entry.setText(siparis_ana.get('teslimat_tarihi', '') or "")

        self.durum_combo.setCurrentText(siparis_ana.get('durum', "BEKLEMEDE"))

        self.siparis_notlari_text.setPlainText(siparis_ana.get('siparis_notlari', '') or "")

        genel_iskonto_tipi_db = siparis_ana.get('genel_iskonto_tipi')
        genel_iskonto_degeri_db = siparis_ana.get('genel_iskonto_degeri')

        self.genel_iskonto_tipi_cb.setCurrentText(genel_iskonto_tipi_db if genel_iskonto_tipi_db else "YOK")
        self.genel_iskonto_degeri_e.setText(f"{float(genel_iskonto_degeri_db):.2f}".replace('.', ',') if genel_iskonto_degeri_db is not None else "0,00")

        self._on_genel_iskonto_tipi_changed()

        c_id_db = siparis_ana.get('cari_id')
        cari_tip_for_callback = siparis_ana.get('cari_tip')
        cari_bilgi_for_display = None

        if cari_tip_for_callback == self.db.CARI_TIP_MUSTERI:
            cari_bilgi_for_display = self.db.musteri_getir_by_id(musteri_id=c_id_db, kullanici_id=self.app.current_user_id)
        elif cari_tip_for_callback == self.db.CARI_TIP_TEDARIKCI:
            cari_bilgi_for_display = self.db.tedarikci_getir_by_id(tedarikci_id=c_id_db, kullanici_id=self.app.current_user_id)

        if cari_bilgi_for_display:
            display_text_for_cari = f"{cari_bilgi_for_display.get('ad', 'Bilinmiyor')} (Kod: {cari_bilgi_for_display.get('kod', '')})"
            self._on_cari_secildi_callback(cari_bilgi_for_display.get('id'), display_text_for_cari)
        else:
            self._temizle_cari_secimi()

        siparis_kalemleri_db_list = self.db.siparis_kalemleri_al(siparis_id=self.duzenleme_id, kullanici_id=self.app.current_user_id)
        self.fatura_kalemleri_ui.clear()
        for k_db in siparis_kalemleri_db_list:
            urun_info = self.db.stok_getir_by_id(stok_id=k_db.get('urun_id'), kullanici_id=self.app.current_user_id)
            if not urun_info: continue

            iskontolu_birim_fiyat_kdv_dahil = (k_db.get('kalem_toplam_kdv_dahil', 0.0) / k_db.get('miktar', 1.0)) if k_db.get('miktar', 1.0) != 0 else 0.0

            self.fatura_kalemleri_ui.append((
                k_db.get('urun_id'), urun_info.get('ad', 'Bilinmiyor'), k_db.get('miktar'), k_db.get('birim_fiyat'), k_db.get('kdv_orani'),
                k_db.get('kdv_tutari'), k_db.get('kalem_toplam_kdv_haric'), k_db.get('kalem_toplam_kdv_dahil'),
                urun_info.get('alis_fiyati'), urun_info.get('kdv_orani'),
                k_db.get('iskonto_yuzde_1'), k_db.get('iskonto_yuzde_2'),
                k_db.get('iskonto_tipi', "YOK"), k_db.get('iskonto_degeri', 0.0), iskontolu_birim_fiyat_kdv_dahil
            ))

        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()

        QTimer.singleShot(0, self._urunleri_yukle_ve_cachele_ve_goster)

    def _reset_form_for_new_siparis(self, ask_confirmation=True):
        if ask_confirmation:
            reply = QMessageBox.question(self.app, "Sıfırlama Onayı", "Sayfadaki tüm bilgileri temizlemek istediğinizden emin misiniz?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return False

        try:
            generated_siparis_no = self.db.get_next_siparis_kodu(kullanici_id=self.app.current_user_id)
            if generated_siparis_no == "OTOMATIK":
                 self.s_no_e.setText("OTOMATIK")
                 self.s_no_e.setReadOnly(True)
            else:
                 self.s_no_e.setText(generated_siparis_no)
                 self.s_no_e.setReadOnly(True)

        except Exception as e:
            QMessageBox.warning(self.app, "Sipariş Numarası Hatası", f"Otomatik sipariş numarası alınırken bir hata oluştu: {e}. Lütfen manuel olarak giriniz.")
            logging.error(f"Otomatik sipariş numarası hatası: {e}", exc_info=True)
            self.s_no_e.setText("MANUEL-")
            self.s_no_e.setReadOnly(False)


        self.siparis_tarihi_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        self.teslimat_tarihi_entry.setText((datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))

        self.durum_combo.setCurrentText(self.db.SIPARIS_DURUM_BEKLEMEDE)
        if hasattr(self, 'siparis_notlari_text'): self.siparis_notlari_text.clear()

        self.genel_iskonto_tipi_cb.setCurrentText("YOK")
        self.genel_iskonto_degeri_e.setText("0,00")
        self._on_genel_iskonto_tipi_changed()

        self._temizle_cari_secimi()
        
        if self.islem_tipi == self.db.SIPARIS_TIP_SATIS and self.db.get_perakende_musteri_id(kullanici_id=self.app.current_user_id) is not None:
            perakende_data = self.db.musteri_getir_by_id(musteri_id=self.db.get_perakende_musteri_id(kullanici_id=self.app.current_user_id), kullanici_id=self.app.current_user_id)
            if perakende_data:
                display_text = perakende_data.get('ad', 'Bilinmiyor')
                self._on_cari_secildi_callback(perakende_data.get('id'), display_text)
        elif self.islem_tipi == self.db.SIPARIS_TIP_ALIS and self.db.get_genel_tedarikci_id(kullanici_id=self.app.current_user_id) is not None:
            genel_tedarikci_data = self.db.tedarikci_getir_by_id(tedarikci_id=self.db.get_genel_tedarikci_id(kullanici_id=self.app.current_user_id), kullanici_id=self.app.current_user_id)
            if genel_tedarikci_data:
                display_text = genel_tedarikci_data.get('ad', 'Bilinmiyor')
                self._on_cari_secildi_callback(genel_tedarikci_data.get('id'), display_text)

        self.fatura_kalemleri_ui = []
        self.sepeti_guncelle_ui()
        self.toplamlari_hesapla_ui()
        
        QTimer.singleShot(0, self._urunleri_yukle_ve_cachele_ve_goster)
        self.urun_arama_entry.setFocus()
            
        return True
                    
    def _populate_from_initial_data_siparis(self):
        logging.debug("_populate_from_initial_data_siparis metodu çağrıldı.")
        logging.debug(f"Initial Cari ID (Sipariş): {self.initial_cari_id}")
        logging.debug(f"Initial Ürünler (Sipariş): {self.initial_urunler}")

        if self.initial_cari_id:
            selected_cari_data = None
            if self.islem_tipi == self.db.SIPARIS_TIP_ALIS:
                selected_cari_data = self.db.tedarikci_getir_by_id(self.initial_cari_id)
            elif self.islem_tipi == self.db.SIPARIS_TIP_SATIS:
                selected_cari_data = self.db.musteri_getir_by_id(self.initial_cari_id)

            if selected_cari_data:
                # API'den dönen veri dictionary olduğu için 'ad' kullanıyoruz
                kod_anahtari = 'kod'
                display_text = f"{selected_cari_data.get('ad', 'Bilinmiyor')} (Kod: {selected_cari_data.get(kod_anahtari, '')})"
                self._on_cari_secildi_callback(selected_cari_data.get('id'), display_text)
                self.app.set_status_message(f"Sipariş cari: {display_text} olarak önceden dolduruldu.")
            else:
                self.app.set_status_message("Önceden doldurulacak cari bulunamadı.")

        if self.initial_urunler:
            self.fatura_kalemleri_ui.clear()
            for urun_data in self.initial_urunler:
                urun_id = urun_data.get('id')
                miktar = urun_data.get('miktar')

                urun_db_info = self.db.stok_getir_by_id(urun_id)
                if not urun_db_info:
                    continue

                # Sipariş tipi Alış ise alış fiyatını, Satış ise satış fiyatını kullan
                birim_fiyat_kdv_dahil_display = 0.0
                if self.islem_tipi == self.db.SIPARIS_TIP_ALIS:
                    birim_fiyat_kdv_dahil_display = urun_db_info.get('alis_fiyati_kdv_dahil')
                else:
                    birim_fiyat_kdv_dahil_display = urun_db_info.get('satis_fiyati_kdv_dahil')

                self.kalem_guncelle(
                    None, miktar, birim_fiyat_kdv_dahil_display, 0.0, 0.0, urun_db_info.get('alis_fiyati', 0.0),
                    u_id=urun_id, urun_adi=urun_db_info.get('ad')
                )

            self.sepeti_guncelle_ui()
            self.toplamlari_hesapla_ui()
            self.app.set_status_message(f"Kritik stok ürünleri sepete eklendi.")
        logging.debug("SiparisOlusturmaSayfasi - _populate_from_initial_data_siparis metodu tamamlandı.")
                
class BaseGelirGiderListesi(QWidget): 
    def __init__(self, parent, db_manager, app_ref, islem_tipi):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.islem_tipi = islem_tipi # 'GELİR', 'GİDER' veya 'TÜMÜ'
        self.main_layout = QVBoxLayout(self) # Ana layout QVBoxLayout

        self.after_timer = QTimer(self)
        self.after_timer.setSingleShot(True)

        # Filtreleme alanı
        filter_frame = QFrame(self)
        filter_layout = QHBoxLayout(filter_frame)
        self.main_layout.addWidget(filter_frame)

        filter_layout.addWidget(QLabel("Başlangıç Tarihi:"))
        self.bas_tarih_entry = QLineEdit()
        self.bas_tarih_entry.setText((datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        filter_layout.addWidget(self.bas_tarih_entry)

        takvim_button_bas = QPushButton("🗓️")
        takvim_button_bas.setFixedWidth(30)
        # DÜZELTME: Doğrudan QLineEdit objesi yerine, objenin içerdiği metin gönderildi.
        takvim_button_bas.clicked.connect(lambda: self._open_date_picker_dialog(self.bas_tarih_entry))
        filter_layout.addWidget(takvim_button_bas)

        filter_layout.addWidget(QLabel("Bitiş Tarihi:"))
        self.bit_tarih_entry = QLineEdit()
        self.bit_tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        filter_layout.addWidget(self.bit_tarih_entry)

        takvim_button_bit = QPushButton("🗓️")
        takvim_button_bit.setFixedWidth(30)
        # DÜZELTME: Doğrudan QLineEdit objesi yerine, objenin içerdiği metin gönderildi.
        takvim_button_bit.clicked.connect(lambda: self._open_date_picker_dialog(self.bit_tarih_entry))
        filter_layout.addWidget(takvim_button_bit)

        filter_layout.addWidget(QLabel("Açıklama Ara:"))
        self.aciklama_arama_entry = QLineEdit()
        self.aciklama_arama_entry.setPlaceholderText("Açıklama ile ara...")
        self.aciklama_arama_entry.textChanged.connect(self._delayed_gg_listesi_yukle)
        filter_layout.addWidget(self.aciklama_arama_entry)

        filtrele_yenile_button = QPushButton("Filtrele ve Yenile")
        filtrele_yenile_button.clicked.connect(self.gg_listesini_yukle)
        filter_layout.addWidget(filtrele_yenile_button)

        # Butonlar
        button_frame_gg = QFrame(self)
        button_layout_gg = QHBoxLayout(button_frame_gg)
        self.main_layout.addWidget(button_frame_gg)

        yeni_manuel_kayit_button = QPushButton("Yeni Manuel Kayıt Ekle")
        yeni_manuel_kayit_button.clicked.connect(self.yeni_gg_penceresi_ac)
        button_layout_gg.addWidget(yeni_manuel_kayit_button)

        self.sil_button = QPushButton("Seçili Manuel Kaydı Sil")
        self.sil_button.clicked.connect(self.secili_gg_sil)
        self.sil_button.setEnabled(False) # Başlangıçta pasif
        button_layout_gg.addWidget(self.sil_button)

        # --- Gelir/Gider Listesi (QTreeWidget) ---
        tree_frame_gg = QFrame(self)
        tree_layout_gg = QVBoxLayout(tree_frame_gg)
        self.main_layout.addWidget(tree_frame_gg) 
        tree_frame_gg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Başlık etiketi, gg_listesini_yukle metodunda kullanıldığı için burada tanımlandı
        self.baslik_label = QLabel(f"{self.islem_tipi} İşlemleri") # TANIMLANDI
        self.baslik_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        tree_layout_gg.addWidget(self.baslik_label)

        # Sütun başlıkları
        cols_gg = ("ID", "Tarih", "Tip", "Tutar", "Açıklama", "Kaynak", "Kaynak ID", "Kasa/Banka Adı")
        self.gg_tree = QTreeWidget(tree_frame_gg)
        self.gg_tree.setHeaderLabels(cols_gg)
        self.gg_tree.setColumnCount(len(cols_gg))
        self.gg_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.gg_tree.setSortingEnabled(True)

        # Sütun tanımlamaları
        col_defs_gg = [
            ("ID", 60, Qt.AlignCenter),
            ("Tarih", 100, Qt.AlignCenter),
            ("Tip", 80, Qt.AlignCenter),
            ("Tutar", 120, Qt.AlignCenter),
            ("Açıklama", 300, Qt.AlignCenter),
            ("Kaynak", 100, Qt.AlignCenter),
            ("Kaynak ID", 80, Qt.AlignCenter),
            ("Kasa/Banka Adı", 120, Qt.AlignCenter)
        ]

        for i, (col_name, width, alignment) in enumerate(col_defs_gg):
            self.gg_tree.setColumnWidth(i, width)
            self.gg_tree.headerItem().setTextAlignment(i, alignment)
            self.gg_tree.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))

        self.gg_tree.header().setStretchLastSection(False)
        self.gg_tree.header().setSectionResizeMode(4, QHeaderView.Stretch) # Açıklama sütunu genişlesin

        tree_layout_gg.addWidget(self.gg_tree)
        self.gg_tree.itemSelectionChanged.connect(self.on_tree_select)

        # Sayfalama için gerekli değişkenler ve widget'lar
        self.kayit_sayisi_per_sayfa = 20
        self.mevcut_sayfa = 1
        self.toplam_kayit_sayisi = 0
        self.total_pages = 1

        pagination_frame_gg = QFrame(self)
        pagination_layout_gg = QHBoxLayout(pagination_frame_gg)
        self.main_layout.addWidget(pagination_frame_gg)

        onceki_sayfa_button = QPushButton("Önceki Sayfa")
        onceki_sayfa_button.clicked.connect(self.onceki_sayfa)
        pagination_layout_gg.addWidget(onceki_sayfa_button)

        self.sayfa_bilgisi_label = QLabel(f"Sayfa {self.mevcut_sayfa} / {self.total_pages}")
        self.sayfa_bilgisi_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        pagination_layout_gg.addWidget(self.sayfa_bilgisi_label)

        sonraki_sayfa_button = QPushButton("Sonraki Sayfa")
        sonraki_sayfa_button.clicked.connect(self.sonraki_sayfa)
        pagination_layout_gg.addWidget(sonraki_sayfa_button)

        self.gg_listesini_yukle() # İlk yüklemeyi yap

    def on_tree_select(self):
        """QTreeWidget'ta bir öğe seçildiğinde silme butonunun durumunu ayarlar."""
        selected_items = self.gg_tree.selectedItems()
        can_delete = False

        if selected_items:
            # Kaynak sütunu 6. sütun (indeks 5)
            # Kaynak ID sütunu 7. sütun (indeks 6)
            kaynak_bilgisi = selected_items[0].text(5).strip().lower()
            kaynak_id_bilgisi = selected_items[0].text(6).strip()

            # Hata ayıklama için terminale yazdırın
            print(f"Seçilen kaydın kaynak bilgisi: '{kaynak_bilgisi}'")
            print(f"Seçilen kaydın kaynak ID'si: '{kaynak_id_bilgisi}'")

            # YENİ DÜZELTME: Kaynak bilgisi 'manuel' olan veya kaynak ID'si boş olan kayıtları silinebilir olarak işaretle.
            if kaynak_bilgisi == 'manuel' or kaynak_id_bilgisi == '-':
                can_delete = True
            
        self.sil_button.setEnabled(can_delete)

    def _delayed_gg_listesi_yukle(self): # event=None kaldırıldı
        if self.after_timer.isActive():
            self.after_timer.stop()
        self.after_timer.singleShot(300, self.gg_listesini_yukle)

    def _open_date_picker_dialog(self, target_entry):
        dialog = DatePickerDialog(self.app, initial_date=target_entry.text())
        
        if dialog.exec() == QDialog.Accepted:
            selected_date = dialog.get_selected_date()
            target_entry.setText(selected_date)
            self.gg_listesini_yukle()
            
    def gg_listesini_yukle(self):
        self.app.set_status_message(f"{self.baslik_label.text()} listesi güncelleniyor...", "blue")
        self.gg_tree.clear()

        try:
            arama_terimi = self.aciklama_arama_entry.text()
            baslangic_tarihi = self.bas_tarih_entry.text()
            bitis_tarihi = self.bit_tarih_entry.text()

            params_to_send = {
                "skip": (self.mevcut_sayfa - 1) * self.kayit_sayisi_per_sayfa,
                "limit": self.kayit_sayisi_per_sayfa,
                "aciklama_filtre": arama_terimi,
                "baslangic_tarihi": baslangic_tarihi,
                "bitis_tarihi": bitis_tarihi,
                "tip_filtre": self.islem_tipi if self.islem_tipi != "TÜMÜ" else None,
            }
            
            gg_listeleme_sonucu = self.db.gelir_gider_listesi_al(**params_to_send)

            if isinstance(gg_listeleme_sonucu, dict) and "items" in gg_listeleme_sonucu:
                gg_verileri = gg_listeleme_sonucu["items"]
                toplam_kayit = gg_listeleme_sonucu["total"]
            else:
                gg_verileri = gg_listeleme_sonucu
                toplam_kayit = len(gg_verileri)
                self.app.set_status_message("Uyarı: Gelir/Gider listesi API yanıtı beklenen formatta değil. Doğrudan liste olarak işleniyor.", "orange")

            self.toplam_kayit_sayisi = toplam_kayit
            self.total_pages = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
            if self.total_pages == 0: self.total_pages = 1

            if self.mevcut_sayfa > self.total_pages:
                self.mevcut_sayfa = self.total_pages

            self.sayfa_bilgisi_label.setText(f"Sayfa {self.mevcut_sayfa} / {self.total_pages}")

            for gg in gg_verileri:
                item_qt = QTreeWidgetItem(self.gg_tree)
                item_qt.setText(0, str(gg.get("id", "")))
                item_qt.setText(1, gg.get("tarih", "").strftime('%d.%m.%Y') if isinstance(gg.get("tarih"), (date, datetime)) else str(gg.get("tarih", "")))
                item_qt.setText(2, gg.get("tip", ""))

                tutar = gg.get("tutar", 0.0)
                item_qt.setText(3, self.db._format_currency(tutar))
                item_qt.setTextAlignment(3, Qt.AlignCenter | Qt.AlignVCenter)

                item_qt.setText(4, gg.get("aciklama", ""))
                item_qt.setText(5, gg.get("kaynak", ""))
                item_qt.setText(6, str(gg.get("kaynak_id", "-")) if gg.get("kaynak_id") else "-")
                item_qt.setText(7, gg.get("kasa_banka_adi", "") if gg.get("kasa_banka_adi") else "-")

                item_qt.setData(0, Qt.UserRole, gg.get("id", 0))
                item_qt.setData(3, Qt.UserRole, tutar)

            self.app.set_status_message(f"{self.baslik_label.text()} listesi başarıyla güncellendi. Toplam {toplam_kayit} kayıt.", "green")

        except Exception as e:
            logger.error(f"{self.baslik_label.text()} listesi yüklenirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: {self.baslik_label.text()} listesi yüklenemedi. {e}", "red")

    def onceki_sayfa(self):
        if self.mevcut_sayfa > 1:
            self.mevcut_sayfa -= 1
            self.gg_listesini_yukle()

    def sonraki_sayfa(self):
        toplam_sayfa = (self.toplam_kayit_sayisi + self.kayit_sayisi_per_sayfa - 1) // self.kayit_sayisi_per_sayfa
        if toplam_sayfa == 0:
            toplam_sayfa = 1

        if self.mevcut_sayfa < toplam_sayfa:
            self.mevcut_sayfa += 1
            self.gg_listesini_yukle()

    def yeni_gg_penceresi_ac(self):
        initial_tip = self.islem_tipi if self.islem_tipi != "TÜMÜ" else "GELİR"

        # NOT: pencereler.py dosyasındaki YeniGelirGiderEklePenceresi'nin PySide6'ya dönüştürülmüş olması gerekmektedir.
        # Bu fonksiyon, YeniGelirGiderEklePenceresi'nin PySide6 versiyonu hazır olduğunda aktif olarak çalışacaktır.

        # Geçici olarak, pencereler modülünü bu fonksiyon içinde import edelim
        try:
            from pencereler import YeniGelirGiderEklePenceresi 

            # Yeni Gelir/Gider Ekleme penceresini başlat
            gg_ekle_penceresi = YeniGelirGiderEklePenceresi(
                self.app, # Ana uygulama penceresi (parent_app)
                self.db, # Veritabanı yöneticisi
                self.gg_listesini_yukle, # Pencere kapatıldığında listeyi yenilemek için callback
                initial_tip=initial_tip # Varsayılan işlem tipi (GELİR veya GİDER)
            )
            # Pencereyi göster
            gg_ekle_penceresi.show()
            self.app.set_status_message(f"Yeni manuel {initial_tip.lower()} kayıt penceresi açıldı.") 

        except ImportError:
            QMessageBox.critical(self.app, "Hata", "YeniGelirGiderEklePenceresi modülü veya PySide6 uyumlu versiyonu bulunamadı.")
            self.app.set_status_message(f"Hata: Yeni manuel {initial_tip.lower()} kayıt penceresi açılamadı.")
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Yeni manuel gelir/gider kayıt penceresi açılırken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Yeni manuel gelir/gider kayıt penceresi açılamadı - {e}")

    def secili_gg_sil(self):
        selected_items = self.gg_tree.selectedItems()
        if not selected_items:
            self.app.set_status_message(f"Lütfen silmek istediğiniz {self.baslik_label.text().lower()} kaydını seçin.")
            return

        item = selected_items[0]
        try:
            gg_id = int(item.text(0))
            aciklama = item.text(4)
            kaynak = item.text(5).strip().lower() # .strip() ve .lower() eklenerek metin temizlendi
            kaynak_id = item.text(6).strip() # Kaynak ID'si de alındı
        except (ValueError, IndexError):
            QMessageBox.critical(self.app, "Hata", "Seçili kaydın verileri okunamadı.")
            return

        # DÜZELTME: Sadece Kaynak ID'si boş olan kayıtları silmeye izin ver.
        # Bu, API'den 'kaynak' bilgisinin boş gelmesi durumunda bile doğru çalışacaktır.
        if kaynak != 'manuel' and kaynak_id != '-':
            QMessageBox.warning(self.app, "Silme Engellendi", "Sadece 'MANUEL' kaynaklı gelir/gider kayıtları silinebilir.\nOtomatik oluşan kayıtlar (Fatura, Tahsilat, Ödeme vb.) ilgili modüllerden yönetilmelidir.")
            return

        reply = QMessageBox.question(self, f'{self.baslik_label.text()} Kaydını Sil Onayı',
                                     f"'{aciklama}' açıklamalı {self.baslik_label.text().lower()} kaydını silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.gelir_gider_sil(gg_id)
                if success:
                    QMessageBox.information(self.app, "Başarılı", f"'{aciklama}' açıklamalı {self.baslik_label.text().lower()} kaydı başarıyla silindi.")
                    self.gg_listesini_yukle()
                    self.app.set_status_message(f"'{aciklama}' açıklamalı {self.baslik_label.text().lower()} kaydı başarıyla silindi.")
                else:
                    QMessageBox.critical(self.app, "Hata", f"Gelir/Gider kaydı silinirken bir hata oluştu.")
                    self.app.set_status_message(f"Hata: {self.baslik_label.text()} kaydı silinemedi. API'den hata döndü.")
            except Exception as e:
                logger.error(f"{self.baslik_label.text()} kaydı silinirken hata oluştu: {e}", exc_info=True)
                QMessageBox.critical(self.app, "Hata", f"Gelir/Gider kaydı silinirken bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: {self.baslik_label.text()} kaydı silinemedi. {e}")
                
class GelirListesi(BaseGelirGiderListesi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='GELİR')

# GiderListesi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class GiderListesi(BaseGelirGiderListesi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='GİDER')

class BaseFinansalIslemSayfasi(QWidget): 
    def __init__(self, parent, db_manager, app_ref, islem_tipi):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.islem_tipi = islem_tipi
        self.main_layout = QVBoxLayout(self)

        self.tum_cariler_cache = []
        self.cari_map = {}
        self.kasa_banka_map = {}

        if self.islem_tipi == 'TAHSILAT':
            self.cari_tip = self.db.CARI_TIP_MUSTERI
        elif self.islem_tipi == 'ODEME':
            self.cari_tip = self.db.CARI_TIP_TEDARIKCI
        else:
            self.cari_tip = None
        
        # Başlık
        baslik_text = "Müşteriden Tahsilat Girişi" if self.islem_tipi == 'TAHSILAT' else "Tedarikçiye Ödeme Girişi"
        self.main_layout.addWidget(QLabel(baslik_text, font=QFont("Segoe UI", 16, QFont.Bold)), 
                                alignment=Qt.AlignCenter)

        # Giriş Formu Çerçevesi
        entry_frame = QFrame(self)
        entry_layout = QGridLayout(entry_frame)
        self.main_layout.addWidget(entry_frame)
        entry_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Cari Seçimi
        cari_label_text = "Müşteri (*):" if self.islem_tipi == 'TAHSILAT' else "Tedarikçi (*):"
        entry_layout.addWidget(QLabel(cari_label_text), 0, 0, Qt.AlignCenter)

        self.cari_combo = QComboBox()
        self.cari_combo.setEditable(True)
        self.cari_combo.setFixedWidth(250)
        self.cari_combo.currentTextChanged.connect(self._filtre_carileri_anlik)
        self.cari_combo.activated.connect(self._on_cari_selected)
        self.cari_combo.lineEdit().editingFinished.connect(self._cari_secimi_dogrula)
        entry_layout.addWidget(self.cari_combo, 0, 1, Qt.AlignCenter)

        self.lbl_cari_bakiye = QLabel("Bakiye: Yükleniyor...")
        self.lbl_cari_bakiye.setFont(QFont("Segoe UI", 10, QFont.Bold))
        entry_layout.addWidget(self.lbl_cari_bakiye, 0, 2, 1, 2, Qt.AlignCenter)

        # Tarih
        entry_layout.addWidget(QLabel("Tarih (*):"), 1, 0, Qt.AlignCenter)
        self.tarih_entry = QLineEdit()
        self.tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        entry_layout.addWidget(self.tarih_entry, 1, 1, Qt.AlignCenter)
        takvim_button_tarih = QPushButton("🗓️")
        takvim_button_tarih.setFixedWidth(30)
        takvim_button_tarih.clicked.connect(lambda: DatePickerDialog(self.app, self.tarih_entry))
        entry_layout.addWidget(takvim_button_tarih, 1, 2, Qt.AlignCenter)

        # Tutar
        entry_layout.addWidget(QLabel("Tutar (TL) (*):"), 2, 0, Qt.AlignCenter)
        self.tutar_entry = QLineEdit()
        self.tutar_entry.setPlaceholderText("0,00")
        tutar_validator = QDoubleValidator(0.0, 999999999.0, 2, self)
        tutar_validator.setNotation(QDoubleValidator.StandardNotation)
        self.tutar_entry.setValidator(tutar_validator)
        self.tutar_entry.textChanged.connect(lambda: format_and_validate_numeric_input(self.tutar_entry, self.app))
        self.tutar_entry.editingFinished.connect(lambda: format_and_validate_numeric_input(self.tutar_entry, self.app))
        entry_layout.addWidget(self.tutar_entry, 2, 1, Qt.AlignCenter)

        # Ödeme Şekli
        entry_layout.addWidget(QLabel("Ödeme Şekli (*):"), 3, 0, Qt.AlignCenter)
        self.odeme_sekli_combo = QComboBox()
        self.odeme_sekli_combo.addItems([self.db.ODEME_TURU_NAKIT, self.db.ODEME_TURU_KART, 
                                        self.db.ODEME_TURU_EFT_HAVALE, self.db.ODEME_TURU_CEK, 
                                        self.db.ODEME_TURU_SENET])
        self.odeme_sekli_combo.setCurrentText(self.db.ODEME_TURU_NAKIT)
        self.odeme_sekli_combo.currentIndexChanged.connect(self._odeme_sekli_degisince)
        entry_layout.addWidget(self.odeme_sekli_combo, 3, 1, Qt.AlignCenter)

        # İşlem Kasa/Banka
        entry_layout.addWidget(QLabel("İşlem Kasa/Banka (*):"), 4, 0, Qt.AlignCenter)
        self.kasa_banka_combo = QComboBox()
        self.kasa_banka_combo.setPlaceholderText("Kasa veya Banka seçin...")
        entry_layout.addWidget(self.kasa_banka_combo, 4, 1, 1, 2, Qt.AlignCenter)

        # Açıklama
        entry_layout.addWidget(QLabel("Açıklama (*):"), 5, 0, Qt.AlignTop | Qt.AlignCenter)
        self.aciklama_text = QTextEdit()
        self.aciklama_text.setPlaceholderText("Açıklama girin...")
        entry_layout.addWidget(self.aciklama_text, 5, 1, 1, 3)

        entry_layout.setColumnStretch(1, 1)

        # Kaydet Butonu
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        self.main_layout.addWidget(button_frame)
        kaydet_button = QPushButton("Kaydet")
        kaydet_button.clicked.connect(self.kaydet_islem)
        button_layout.addWidget(kaydet_button, alignment=Qt.AlignCenter)

        # Hızlı İşlem Listesi (Son İşlemler)
        recent_transactions_frame = QFrame(self)
        recent_transactions_layout = QVBoxLayout(recent_transactions_frame)
        self.main_layout.addWidget(recent_transactions_frame)
        recent_transactions_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        recent_transactions_layout.addWidget(QLabel("Son İşlemler", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignCenter)

        cols_recent = ("Tarih", "Tip", "Tutar", "Açıklama", "Kasa/Banka")
        self.tree_recent_transactions = QTreeWidget(recent_transactions_frame)
        self.tree_recent_transactions.setHeaderLabels(cols_recent)
        self.tree_recent_transactions.setColumnCount(len(cols_recent))
        self.tree_recent_transactions.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_recent_transactions.setSortingEnabled(True)
        
        col_defs_recent = [
            ("Tarih", 90, Qt.AlignCenter),
            ("Tip", 70, Qt.AlignCenter),
            ("Tutar", 120, Qt.AlignCenter),
            ("Açıklama", 350, Qt.AlignCenter),
            ("Kasa/Banka", 100, Qt.AlignCenter)
        ]
        for i, (col_name, width, alignment) in enumerate(col_defs_recent):
            self.tree_recent_transactions.setColumnWidth(i, width)
            self.tree_recent_transactions.headerItem().setTextAlignment(i, alignment)
            self.tree_recent_transactions.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))

        self.tree_recent_transactions.header().setStretchLastSection(False)
        self.tree_recent_transactions.header().setSectionResizeMode(3, QHeaderView.Stretch)

        recent_transactions_layout.addWidget(self.tree_recent_transactions)

        self._yukle_ve_cachele_carileri()
        self._yukle_kasa_banka_hesaplarini()

        if self.cari_combo.count() > 0:
            self.cari_combo.setCurrentIndex(0)
        self._on_cari_selected()
        self._odeme_sekli_degisince()
        
    def _yukle_ve_cachele_carileri(self): # Yaklaşık 6138. satır
        self.tum_cariler_cache = []
        self.cari_map = {}
        kullanici_id = self.app.current_user_id # Düzeltme: kullanıcı ID'si alındı

        try:
            cariler_data = []
            if self.islem_tipi == 'TAHSILAT':
                musteriler_response = self.db.musteri_listesi_al(limit=10000)
                cariler_data = musteriler_response.get("items", []) if isinstance(musteriler_response, dict) else musteriler_response
            elif self.islem_tipi == 'ODEME':
                tedarikciler_response = self.db.tedarikci_listesi_al(limit=10000)
                cariler_data = tedarikciler_response.get("items", []) if isinstance(tedarikciler_response, dict) else tedarikciler_response
            
            if not cariler_data and self.cari_tip is None:
                QMessageBox.critical(self.app, "Hata", "Geçersiz işlem tipi için cari listesi çekilemiyor.")
                return

            display_values = []
            for c in cariler_data:
                display_text = f"{c.get('ad', 'Bilinmiyor')} (Kod: {c.get('kod', '')})"
                self.cari_map[display_text] = c.get('id')
                display_values.append(display_text)
                self.tum_cariler_cache.append(c)

            self.cari_combo.blockSignals(True)
            self.cari_combo.clear()
            self.cari_combo.addItems(display_values)

            # Perakende müşteri veya genel tedarikçi varsa, varsayılan olarak seçme mantığı
            perakende_musteri_id_val = self.db.get_perakende_musteri_id()
            genel_tedarikci_id_val = self.db.get_genel_tedarikci_id()
            
            if self.cari_combo.count() > 0:
                if self.islem_tipi == 'TAHSILAT' and perakende_musteri_id_val is not None:
                    perakende_musteri_display_text = next((text for text, _id in self.cari_map.items() if _id == perakende_musteri_id_val), None)
                    if perakende_musteri_display_text and perakende_musteri_display_text in display_values:
                        self.cari_combo.setCurrentText(perakende_musteri_display_text)
                    else:
                        self.cari_combo.setCurrentIndex(0)
                elif self.islem_tipi == 'ODEME' and genel_tedarikci_id_val is not None:
                    genel_tedarikci_display_text = next((text for text, _id in self.cari_map.items() if _id == genel_tedarikci_id_val), None)
                    if genel_tedarikci_display_text and genel_tedarikci_display_text in display_values:
                        self.cari_combo.setCurrentText(genel_tedarikci_display_text)
                    else:
                        self.cari_combo.setCurrentIndex(0)
                else:
                    self.cari_combo.setCurrentIndex(0)
            else:
                self.cari_combo.clear()

            self.cari_combo.blockSignals(False)
            self.app.set_status_message(f"{len(cariler_data)} cari API'den önbelleğe alındı.", "black")
            self._on_cari_selected()

        except Exception as e:
            logger.error(f"Cari listesi yüklenirken hata oluştu: {e}", exc_info=True)
            self.app.set_status_message(f"Hata: Cari listesi yüklenemedi - {e}")

    def _load_recent_transactions(self):
        self.tree_recent_transactions.clear()

        selected_cari_text = self.cari_combo.currentText()
        cari_id = self.cari_map.get(selected_cari_text)

        if cari_id is None:
            item_qt = QTreeWidgetItem(self.tree_recent_transactions)
            item_qt.setText(3, "Cari seçilmedi.")
            return

        try:
            hareketler_response = self.db.cari_hareketleri_listele(
                cari_id=cari_id,
                limit=10
            )

            recent_data = hareketler_response.get("items", []) if isinstance(hareketler_response, dict) else hareketler_response

            if not recent_data:
                item_qt = QTreeWidgetItem(self.tree_recent_transactions)
                item_qt.setText(3, "Son işlem bulunamadı.")
                return

            for item in recent_data:
                tarih_obj = item.get('tarih')
                if isinstance(tarih_obj, (datetime, date)):
                    tarih_formatted = tarih_obj.strftime('%d.%m.%Y')
                else:
                    tarih_formatted = str(tarih_obj or "")

                tutar_formatted = self.db._format_currency(item.get('tutar', 0.0))
                
                kasa_banka_adi = "-"
                if item.get('kasa_banka_id'):
                    kasa_banka_response = self.db.kasa_banka_getir_by_id(hesap_id=item.get('kasa_banka_id'), kullanici_id=self.app.current_user_id)
                    kasa_banka_adi = kasa_banka_response.get('hesap_adi', '-') if kasa_banka_response else '-'

                item_qt = QTreeWidgetItem(self.tree_recent_transactions)
                item_qt.setText(0, tarih_formatted)
                item_qt.setText(1, item.get('islem_turu', ''))
                item_qt.setText(2, tutar_formatted)
                item_qt.setText(3, item.get('aciklama', '-') if item.get('aciklama') else "-")
                item_qt.setText(4, kasa_banka_adi)
                
                item_qt.setData(2, Qt.UserRole, item.get('tutar'))
        
            self.app.set_status_message(f"Son {len(recent_data)} cari hareketi yüklendi.")

        except Exception as e:
            logger.error(f"Son cari hareketler yüklenirken hata oluştu: {e}", exc_info=True)
            QMessageBox.critical(self.app, "Veri Yükleme Hatası", f"Son cari hareketler yüklenirken bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Son cari hareketler yüklenemedi - {e}")

    def _filtre_carileri_anlik(self, text):
        arama_terimi = text.lower().strip()

        self.cari_combo.blockSignals(True)

        self.cari_combo.clear()

        filtered_display_values = [
            display_text for display_text in self.cari_map.keys()
            if arama_terimi in display_text.lower()
        ]
        
        self.cari_combo.addItems(sorted(filtered_display_values))

        exact_match_found = False
        if arama_terimi:
            for i in range(self.cari_combo.count()):
                if self.cari_combo.itemText(i).lower() == arama_terimi:
                    self.cari_combo.setCurrentIndex(i)
                    exact_match_found = True
                    break
        
        if not exact_match_found and self.cari_combo.count() > 0:
            self.cari_combo.setCurrentIndex(0)

        self.cari_combo.blockSignals(False)

    def _odeme_sekli_degisince(self):
        selected_odeme_sekli = self.odeme_sekli_combo.currentText()
        varsayilan_kb_db = self.db.get_kasa_banka_by_odeme_turu(selected_odeme_sekli)

        self.kasa_banka_combo.blockSignals(True)
        self.kasa_banka_combo.clear()
        self.kasa_banka_map.clear()
        
        hesaplar_response = self.db.kasa_banka_listesi_al(limit=10000)
        hesaplar = hesaplar_response.get("items", []) if isinstance(hesaplar_response, dict) else hesaplar_response

        display_values_kb = []
        if hesaplar:
            for h in hesaplar:
                display_text = f"{h.get('hesap_adi', 'Bilinmiyor')} ({h.get('tip', 'Bilinmiyor')})"
                if h.get('tip') == "BANKA" and h.get('banka_adi'):
                    display_text += f" - {h.get('banka_adi')}"
                if h.get('tip') == "BANKA" and h.get('hesap_no'):
                    display_text += f" ({h.get('hesap_no')})"
                self.kasa_banka_map[display_text] = h.get('id')
                display_values_kb.append(display_text)
            
            self.kasa_banka_combo.addItems(display_values_kb)

            if varsayilan_kb_db:
                varsayilan_kb_id = varsayilan_kb_db[0]
                index_to_set = self.kasa_banka_combo.findData(varsayilan_kb_id)
                if index_to_set != -1:
                    self.kasa_banka_combo.setCurrentIndex(index_to_set)
                else:
                    if self.kasa_banka_combo.count() > 0: self.kasa_banka_combo.setCurrentIndex(0)
            elif self.kasa_banka_combo.count() > 0:
                self.kasa_banka_combo.setCurrentIndex(0)
            else:
                self.kasa_banka_combo.clear()
                self.kasa_banka_combo.setPlaceholderText("Hesap Yok")
                self.kasa_banka_combo.setEnabled(False)
        else:
            self.kasa_banka_combo.clear()
            self.kasa_banka_combo.setPlaceholderText("Hesap Yok")
            self.kasa_banka_combo.setEnabled(False)

        self.kasa_banka_combo.blockSignals(False)

    def _cari_secimi_dogrula(self):
        current_text = self.cari_combo.currentText().strip()
        if current_text and current_text not in self.cari_map:
            QMessageBox.warning(self.app, "Geçersiz Cari", "Seçili müşteri/tedarikçi listede bulunamadı.\nLütfen listeden geçerli bir seçim yapın veya yeni bir cari ekleyin.")
            self.cari_combo.clear()
            self.lbl_cari_bakiye.setText("")
            self.lbl_cari_bakiye.setStyleSheet("color: black;")
        self._on_cari_selected()

    def _on_cari_selected(self):
        selected_cari_text = self.cari_combo.currentText()
        secilen_cari_id = self.cari_map.get(selected_cari_text)

        bakiye_text = ""
        bakiye_color = "black"

        if secilen_cari_id:
            cari_id_int = int(secilen_cari_id)
            if self.cari_tip == self.db.CARI_TIP_MUSTERI:
                net_bakiye = self.db.get_musteri_net_bakiye(musteri_id=cari_id_int) 
                if net_bakiye is not None:
                    if net_bakiye > 0:
                        bakiye_text = f"Borç: {self.db._format_currency(net_bakiye)}"
                        bakiye_color = "red"
                    elif net_bakiye < 0:
                        bakiye_text = f"Alacak: {self.db._format_currency(abs(net_bakiye))}"
                        bakiye_color = "green"
                    else:
                        bakiye_text = "Bakiye: 0,00 TL"
                        bakiye_color = "black"
                else:
                    bakiye_text = "Bakiye: Yüklenemedi"
                    bakiye_color = "black"

            elif self.cari_tip == self.db.CARI_TIP_TEDARIKCI:
                net_bakiye = self.db.get_tedarikci_net_bakiye(tedarikci_id=cari_id_int, kullanici_id=self.app.current_user_id)
                if net_bakiye is not None:
                    if net_bakiye > 0:
                        bakiye_text = f"Borç: {self.db._format_currency(net_bakiye)}"
                        bakiye_color = "red"
                    elif net_bakiye < 0:
                        bakiye_text = f"Alacak: {self.db._format_currency(abs(net_bakiye))}"
                        bakiye_color = "green"
                    else:
                        bakiye_text = "Bakiye: 0,00 TL"
                        bakiye_color = "black"
                else:
                    bakiye_text = "Bakiye: Yüklenemedi"
                    bakiye_color = "black"

            self.lbl_cari_bakiye.setText(bakiye_text)
            self.lbl_cari_bakiye.setStyleSheet(f"color: {bakiye_color};")
        else:
            self.lbl_cari_bakiye.setText("Bakiye: ---")
            self.lbl_cari_bakiye.setStyleSheet("color: black;")

        self._load_recent_transactions()

    def _yukle_kasa_banka_hesaplarini(self):
        self.kasa_banka_combo.clear()
        self.kasa_banka_map.clear()
        
        try:
            # DÜZELTİLDİ: Veriler artık yerel veritabanından çekiliyor.
            with lokal_db_servisi.get_db() as db:
                hesaplar = db.query(KasaBankaHesap).all()
            
            display_values = []
            if hesaplar:
                for h in hesaplar:
                    display_text = f"{h.hesap_adi} ({h.tip})"
                    if h.tip == "BANKA" and h.banka_adi:
                        display_text += f" - {h.banka_adi}"
                    if h.tip == "BANKA" and h.hesap_no:
                        display_text += f" ({h.hesap_no})"
                    
                    self.kasa_banka_map[display_text] = h.id
                    display_values.append(display_text)
                
                self.kasa_banka_combo.addItems(display_values)
                self.kasa_banka_combo.setCurrentIndex(0)
                self.kasa_banka_combo.setEnabled(True)
            else:
                self.kasa_banka_combo.clear()
                self.kasa_banka_combo.setPlaceholderText("Hesap Yok")
                self.kasa_banka_combo.setEnabled(False)

            self.app.set_status_message(f"{len(hesaplar)} kasa/banka hesabı yerel veritabanından yüklendi.")

        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"Kasa/Banka hesapları yerel veritabanından alınamadı:\n{e}")
            self.app.set_status_message(f"Hata: Kasa/Banka hesapları yüklenemedi - {e}")

# Kaydet işlemi artık BaseFinansalIslemSayfasi'nın bir metodu
    def kaydet_islem(self):
        selected_cari_str = self.cari_combo.currentText().strip()
        tarih_str = self.tarih_entry.text().strip()
        tutar_str = self.tutar_entry.text().strip()
        odeme_sekli_str = self.odeme_sekli_combo.currentText()
        aciklama_str = self.aciklama_text.toPlainText().strip()
        selected_kasa_banka_str = self.kasa_banka_combo.currentText()

        cari_id_val = None
        if selected_cari_str and selected_cari_str in self.cari_map:
            cari_id_val = self.cari_map.get(selected_cari_str)
        else:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Lütfen geçerli bir müşteri/tedarikçi seçin.")
            return

        kasa_banka_id_val = None
        if selected_kasa_banka_str and selected_kasa_banka_str != "Hesap Yok" and selected_kasa_banka_str in self.kasa_banka_map:
            kasa_banka_id_val = self.kasa_banka_map.get(selected_kasa_banka_str)
        else:
            QMessageBox.critical(self.app, "Eksik Bilgi", "Lütfen bir İşlem Kasa/Banka hesabı seçin.")
            return

        if not all([tarih_str, tutar_str, odeme_sekli_str, aciklama_str]):
            QMessageBox.critical(self.app, "Eksik Bilgi", "Lütfen tüm zorunlu (*) alanları doldurun.")
            return

        try:
            tutar_f = float(tutar_str.replace(',', '.'))
            if tutar_f <= 0:
                QMessageBox.critical(self.app, "Geçersiz Tutar", "Tutar pozitif bir sayı olmalıdır.")
                return
        except ValueError:
            QMessageBox.critical(self.app, "Giriş Hatası", "Tutar sayısal bir değer olmalıdır.")
            return

        # DÜZELTİLDİ: Veri API'ye gönderiliyor
        try:
            success, message = self.db.gelir_gider_ekle({
                "tarih": tarih_str,
                "tip": "GELİR" if self.islem_tipi == "TAHSILAT" else "GIDER",
                "tutar": tutar_f,
                "aciklama": aciklama_str,
                "odeme_turu": odeme_sekli_str,
                "kasa_banka_id": kasa_banka_id_val,
                "cari_id": cari_id_val,
                "cari_tip": self.cari_tip,
                "gelir_siniflandirma_id": None, # Şimdilik None olarak varsayalım
                "gider_siniflandirma_id": None # Şimdilik None olarak varsayalım
            })

            if success:
                QMessageBox.information(self.app, "Başarılı", f"İşlem başarıyla kaydedildi: {aciklama_str}")
                
                # Formu temizle ve listeleri yenile
                self.cari_combo.clear()
                self.tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
                self.tutar_entry.clear()
                self.odeme_sekli_combo.setCurrentText(self.db.ODEME_TURU_NAKIT)
                self.aciklama_text.clear()
                self._odeme_sekli_degisince()
                self.cari_combo.setFocus()

                # Listeleri yenile
                if hasattr(self.app, 'gelir_gider_sayfasi'):
                    self.app.gelir_gider_sayfasi.gelir_listesi_frame.gg_listesini_yukle()
                    self.app.gelir_gider_sayfasi.gider_listesi_frame.gg_listesini_yukle()
                if hasattr(self.app, 'kasa_banka_yonetimi_sayfasi') and hasattr(self.app.kasa_banka_yonetimi_sayfasi, 'hesap_listesini_yenile'):
                    self.app.kasa_banka_yonetimi_sayfasi.hesap_listesini_yenile()
                self._on_cari_selected()

                self.app.set_status_message(f"Finansal işlem başarıyla kaydedildi.")

            else:
                QMessageBox.critical(self.app, "Hata", "Gelir/Gider kaydı eklenirken bir hata oluştu.")
                self.app.set_status_message(f"Hata: Finansal işlem kaydedilemedi.")

        except Exception as e:
            logger.error(f"Finansal işlem kaydedilirken beklenmeyen bir hata oluştu: {e}", exc_info=True)
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Finansal işlem kaydedilirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Hata: Finansal işlem kaydedilirken hata - {e}")

class TahsilatSayfasi(BaseFinansalIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='TAHSILAT')

# OdemeSayfasi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class OdemeSayfasi(BaseFinansalIslemSayfasi):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent, db_manager, app_ref, islem_tipi='ODEME')

class RaporlamaMerkeziSayfasi(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref
        self.main_layout = QVBoxLayout(self) # Ana layout QVBoxLayout

        # --- Temel Sınıf Özellikleri ---
        self.aylik_satis_verileri = []
        self.aylik_gelir_gider_verileri = []
        self.aylik_kar_maliyet_verileri = []
        self.aylik_nakit_akis_verileri = []
        self.top_satis_urunleri = []
        self.cari_yaslandirma_data = {'musteri_alacaklari': {}, 'tedarikci_borclari': {}}
        self.stok_envanter_ozet = []

        # --- Ana UI Elemanları ---
        self.main_layout.addWidget(QLabel("Finansal Raporlar ve Analiz Merkezi", font=QFont("Segoe UI", 22, QFont.Bold)), 
                                   alignment=Qt.AlignCenter)

        # Filtreleme ve Rapor Oluşturma Kontrolleri (Üst kısımda her zaman görünür)
        filter_control_frame = QFrame(self)
        filter_control_layout = QHBoxLayout(filter_control_frame)
        self.main_layout.addWidget(filter_control_frame)

        filter_control_layout.addWidget(QLabel("Başlangıç Tarihi:"))
        self.bas_tarih_entry = QLineEdit()
        self.bas_tarih_entry.setText((datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        filter_control_layout.addWidget(self.bas_tarih_entry)
        
        takvim_button_bas = QPushButton("🗓️")
        takvim_button_bas.setFixedWidth(30)
        takvim_button_bas.clicked.connect(lambda: self._open_date_picker(self.bas_tarih_entry))
        filter_control_layout.addWidget(takvim_button_bas)

        filter_control_layout.addWidget(QLabel("Bitiş Tarihi:"))
        self.bit_tarih_entry = QLineEdit()
        self.bit_tarih_entry.setText(datetime.now().strftime('%Y-%m-%d'))
        filter_control_layout.addWidget(self.bit_tarih_entry)
        
        takvim_button_bit = QPushButton("🗓️")
        takvim_button_bit.setFixedWidth(30)
        takvim_button_bit.clicked.connect(lambda: self._open_date_picker(self.bit_tarih_entry))
        filter_control_layout.addWidget(takvim_button_bit)

        rapor_olustur_yenile_button = QPushButton("Rapor Oluştur/Yenile")
        rapor_olustur_yenile_button.clicked.connect(self.raporu_olustur_ve_yenile)
        filter_control_layout.addWidget(rapor_olustur_yenile_button)

        rapor_yazdir_pdf_button = QPushButton("Raporu Yazdır (PDF)")
        rapor_yazdir_pdf_button.clicked.connect(self.raporu_pdf_yazdir_placeholder)
        filter_control_layout.addWidget(rapor_yazdir_pdf_button)

        rapor_disa_aktar_excel_button = QPushButton("Raporu Dışa Aktar (Excel)")
        rapor_disa_aktar_excel_button.clicked.connect(self.raporu_excel_aktar)
        filter_control_layout.addWidget(rapor_disa_aktar_excel_button)

        # Rapor sekmeleri için ana QTabWidget
        self.report_notebook = QTabWidget(self)
        self.main_layout.addWidget(self.report_notebook)

        # Sekme 1: Genel Bakış (Dashboard)
        self.tab_genel_bakis = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_genel_bakis, "📊 Genel Bakış")
        self._create_genel_bakis_tab(self.tab_genel_bakis)

        # Sekme 2: Satış Raporları
        self.tab_satis_raporlari = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_satis_raporlari, "📈 Satış Raporları")
        self._create_satis_raporlari_tab(self.tab_satis_raporlari)

        # Sekme 3: Kâr ve Zarar
        self.tab_kar_zarar = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_kar_zarar, "💰 Kâr ve Zarar")
        self._create_kar_zarar_tab(self.tab_kar_zarar)

        # Sekme 4: Nakit Akışı
        self.tab_nakit_akisi = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_nakit_akisi, "🏦 Nakit Akışı")
        self._create_nakit_akisi_tab(self.tab_nakit_akisi)

        # Sekme 5: Cari Hesap Raporları
        self.tab_cari_hesaplar = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_cari_hesaplar, "👥 Cari Hesaplar")
        self._create_cari_hesaplar_tab(self.tab_cari_hesaplar)

        # Sekme 6: Stok Raporları
        self.tab_stok_raporlari = QWidget(self.report_notebook)
        self.report_notebook.addTab(self.tab_stok_raporlari, "📦 Stok Raporları")
        self._create_stok_raporlari_tab(self.tab_stok_raporlari)

        # Rapor notebook sekmesi değiştiğinde güncellemeleri tetikle
        self.report_notebook.currentChanged.connect(self._on_tab_change)

        # Başlangıçta raporları oluştur (Bu, ilk sekmenin içeriğini yükler)
        self.raporu_olustur_ve_yenile()

    # --- Ortak Yardımcı Metotlar ---
    def _open_date_picker(self, target_entry_qlineedit): # QLineEdit objesi alacak
        """
        PySide6 DatePickerDialog'u açar ve seçilen tarihi target_entry_qlineedit'e yazar.
        """
        # DatePickerDialog'un yeni PySide6 versiyonunu kullanıyoruz.
        # (yardimcilar.py'den import edildiğinden emin olun)
        from yardimcilar import DatePickerDialog # PySide6 DatePickerDialog

        # Mevcut tarihi al (eğer varsa) ve diyaloğa gönder
        initial_date_str = target_entry_qlineedit.text() if target_entry_qlineedit.text() else None

        dialog = DatePickerDialog(self.app, initial_date_str) # parent: self.app (ana uygulama penceresi)

        # Diyalogtan tarih seçildiğinde (date_selected sinyali)
        # QLineEdit'in setText metoduna bağlanır.
        dialog.date_selected.connect(target_entry_qlineedit.setText)

        # Diyaloğu modal olarak çalıştır
        dialog.exec()
        
    def _draw_plot(self, parent_frame, canvas_obj, ax_obj, title, labels, values, plot_type='bar', colors=None, bar_width=0.8, rotation=0, show_legend=True, label_prefix="", show_labels_on_bars=False, tight_layout_needed=True, group_labels=None):
        # Mevcut grafiği temizle (eğer varsa)
        if canvas_obj:
            canvas_obj.deleteLater() # PySide6'da widget'ı silmek için deleteLater kullanılır
            plt.close(ax_obj.figure)

        # parent_frame'in mevcut layout'unu kontrol edin ve gerekirse temizleyin
        if parent_frame.layout():
            for i in reversed(range(parent_frame.layout().count())):
                widget_to_remove = parent_frame.layout().itemAt(i).widget()
                if widget_to_remove:
                    widget_to_remove.setParent(None)
                    widget_to_remove.deleteLater()

        parent_width = parent_frame.width() # QWidget'ın genişliğini al
        parent_height = parent_frame.height() # QWidget'ın yüksekliğini al

        if parent_width < 100: parent_width = 400
        if parent_height < 100: parent_height = 300

        my_dpi = 100
        fig = Figure(figsize=(parent_width/my_dpi, parent_height/my_dpi), dpi=my_dpi)
        ax = fig.add_subplot(111)

        ax.clear()
        ax.set_title(title, fontsize=10)

        is_data_empty = False
        if plot_type == 'bar':
            if not values or (isinstance(values, list) and all(v == 0 for v in values)):
                is_data_empty = True
        elif plot_type == 'pie':
            valid_values_for_pie = [v for v in values if v != 0]
            if not valid_values_for_pie:
                is_data_empty = True
        elif plot_type == 'grouped_bar':
            if not values or all(not sub_list or all(v == 0 for v in sub_list) for sub_list in values):
                is_data_empty = True

        if is_data_empty:
            ax.text(0.5, 0.5, "Gösterilecek Veri Yok", horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=12)
            ax.set_xticks([])
            ax.set_yticks([])
            
            canvas = FigureCanvas(fig) # PySide6 için FigureCanvas
            # Parent frame'in layout'u kontrol edilmiş ve temizlenmiş olduğundan, doğrudan ekleyebiliriz
            if parent_frame.layout() is None: # Layout yoksa oluştur
                parent_frame.setLayout(QVBoxLayout())
            parent_frame.layout().addWidget(canvas) # Layout'a ekle
            canvas.draw()
            return canvas, ax

        # Veri doluysa çizim yap
        if plot_type == 'bar':
            bar_label = group_labels[0] if group_labels and len(group_labels) > 0 else title
            bars = ax.bar(labels, values, color=colors if colors else 'skyblue', width=bar_width, label=bar_label)

            ax.set_ylabel("Tutar (TL)", fontsize=8)
            ax.tick_params(axis='x', rotation=rotation, labelsize=7)
            ax.tick_params(axis='y', labelsize=7)
            if show_legend and any(v != 0 for v in values):
                ax.legend(fontsize=7)

            if show_labels_on_bars:
                for bar in bars:
                    yval = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2, yval + (max(values)*0.01 if values and max(values) !=0 else 0.01), f"{label_prefix}{yval:,.0f}", ha='center', va='bottom', fontsize=6, weight='bold')

            if tight_layout_needed:
                fig.tight_layout()

        elif plot_type == 'pie':
            valid_labels = [labels[i] for i, val in enumerate(values) if val != 0]
            valid_values = [val for val in values if val != 0]

            wedges, texts, autotexts = ax.pie(valid_values, labels=valid_labels, autopct='%1.1f%%', startangle=90, colors=colors if colors else plt.cm.Paired.colors)
            ax.axis('equal')
            plt.setp(autotexts, size=8, weight="bold")
            plt.setp(texts, size=9)
            fig.tight_layout()

        elif plot_type == 'grouped_bar':
            num_groups = len(values)
            num_bars_per_group = len(labels)

            bar_width_per_group = bar_width / num_groups
            ind = np.arange(num_bars_per_group)

            has_non_zero_data_in_groups = any(any(v_sub != 0 for v_sub in sub_list) for sub_list in values)

            if show_legend and has_non_zero_data_in_groups:
                for i, group_values in enumerate(values):
                    ax.bar(ind + i * bar_width_per_group, group_values, width=bar_width_per_group,
                           label=group_labels[i] if group_labels and len(group_labels) > i else f'Grup {i+1}',
                           color=colors[i] if isinstance(colors, list) and len(colors) > i else None)
                ax.legend(fontsize=7)

            ax.set_xticks(ind + (num_groups * bar_width_per_group - bar_width_per_group) / 2)
            ax.set_xticklabels(labels, rotation=rotation, ha='right', fontsize=7)
            ax.set_ylabel("Tutar (TL)", fontsize=8)
            ax.tick_params(axis='y', labelsize=7)
            fig.tight_layout()

        canvas = FigureCanvas(fig) # PySide6 için FigureCanvas
        # Parent frame'in layout'u kontrol edilmiş ve temizlenmiş olduğundan, doğrudan ekleyebiliriz
        if parent_frame.layout() is None: # Layout yoksa oluştur
            parent_frame.setLayout(QVBoxLayout())
        parent_frame.layout().addWidget(canvas) # Layout'a ekle
        canvas.draw()

        return canvas, ax
        
    # --- Rapor Sekmelerinin Oluşturma Metotları ---
    def _create_genel_bakis_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame) # Parent frame'e layout ata
        parent_layout.setColumnStretch(0, 1)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1) # Grafik dikeyde genişlesin

        # --- Metrik Kartlar Bölümü ---
        metrics_frame = QFrame(parent_frame)
        metrics_layout = QGridLayout(metrics_frame)
        parent_layout.addWidget(metrics_frame, 0, 0, 1, 2) # Row 0, Col 0, span 1 row, 2 cols
        metrics_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        for i in range(6): # Daha fazla metrik için 6 sütun
            metrics_layout.setColumnStretch(i, 1)

        # Metrik Kartları Oluşturma ve İsimlendirme (lbl_metric_ ile başlıyor)
        self.card_total_sales = self._create_metric_card(metrics_frame, "Toplam Satış (KDV Dahil)", "0.00 TL", "total_sales")
        metrics_layout.addWidget(self.card_total_sales, 0, 0) # lbl_metric_total_sales

        self.card_total_purchases = self._create_metric_card(metrics_frame, "Toplam Alış (KDV Dahil)", "0.00 TL", "total_purchases")
        metrics_layout.addWidget(self.card_total_purchases, 0, 1) # lbl_metric_total_purchases

        self.card_total_collections = self._create_metric_card(metrics_frame, "Toplam Tahsilat", "0.00 TL", "total_collections")
        metrics_layout.addWidget(self.card_total_collections, 0, 2) # lbl_metric_total_collections

        self.card_total_payments = self._create_metric_card(metrics_frame, "Toplam Ödeme", "0.00 TL", "total_payments")
        metrics_layout.addWidget(self.card_total_payments, 0, 3) # lbl_metric_total_payments

        self.card_approaching_receivables = self._create_metric_card(metrics_frame, "Vadesi Yaklaşan Alacaklar", "0.00 TL", "approaching_receivables")
        metrics_layout.addWidget(self.card_approaching_receivables, 0, 4) # lbl_metric_approaching_receivables

        self.card_overdue_payables = self._create_metric_card(metrics_frame, "Vadesi Geçmiş Borçlar", "0.00 TL", "overdue_payables")
        metrics_layout.addWidget(self.card_overdue_payables, 0, 5) # lbl_metric_overdue_payables

        # --- Finansal Özetler Bölümü ---
        summary_frame = QFrame(parent_frame)
        summary_layout = QGridLayout(summary_frame)
        parent_layout.addWidget(summary_frame, 1, 0) # Row 1, Col 0
        summary_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        summary_layout.addWidget(QLabel("Dönemlik Finansal Özetler", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 2)

        summary_layout.addWidget(QLabel("Dönem Gelirleri:", font=QFont("Segoe UI", 10, QFont.Bold)), 1, 0)
        self.lbl_genel_bakis_donem_gelir = QLabel("0.00 TL")
        summary_layout.addWidget(self.lbl_genel_bakis_donem_gelir, 1, 1)

        summary_layout.addWidget(QLabel("Dönem Giderleri:", font=QFont("Segoe UI", 10, QFont.Bold)), 2, 0)
        self.lbl_genel_bakis_donem_gider = QLabel("0.00 TL")
        summary_layout.addWidget(self.lbl_genel_bakis_donem_gider, 2, 1)

        summary_layout.addWidget(QLabel("Brüt Kâr:", font=QFont("Segoe UI", 10, QFont.Bold)), 3, 0)
        self.lbl_genel_bakis_brut_kar = QLabel("0.00 TL")
        summary_layout.addWidget(self.lbl_genel_bakis_brut_kar, 3, 1)
        
        summary_layout.addWidget(QLabel("Net Kâr:", font=QFont("Segoe UI", 10, QFont.Bold)), 4, 0)
        self.lbl_genel_bakis_net_kar = QLabel("0.00 TL")
        summary_layout.addWidget(self.lbl_genel_bakis_net_kar, 4, 1)

        summary_layout.addWidget(QLabel("Nakit Girişleri:", font=QFont("Segoe UI", 10, QFont.Bold)), 5, 0)
        self.lbl_genel_bakis_nakit_girisleri = QLabel("0.00 TL")
        summary_layout.addWidget(self.lbl_genel_bakis_nakit_girisleri, 5, 1)

        summary_layout.addWidget(QLabel("Nakit Çıkışları:", font=QFont("Segoe UI", 10, QFont.Bold)), 6, 0)
        self.lbl_genel_bakis_nakit_cikislar = QLabel("0.00 TL")
        summary_layout.addWidget(self.lbl_genel_bakis_nakit_cikislar, 6, 1)
        
        summary_layout.addWidget(QLabel("Net Nakit Akışı:", font=QFont("Segoe UI", 10, QFont.Bold)), 7, 0)
        self.lbl_genel_bakis_net_nakit_akisi = QLabel("0.00 TL")
        summary_layout.addWidget(self.lbl_genel_bakis_net_nakit_akisi, 7, 1)

        summary_layout.setRowStretch(8, 1) # Boş alan dikeyde genişlesin

        # --- Sağ Panel - Ek Bilgiler ve Listeler ---
        right_panel = QFrame(parent_frame)
        right_panel_layout = QVBoxLayout(right_panel)
        parent_layout.addWidget(right_panel, 1, 1) # Row 1, Col 1
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        right_panel_layout.addWidget(QLabel("Kasa/Banka Bakiyeleri", font=QFont("Segoe UI", 12, QFont.Bold)))
        self.kasa_banka_list_widget = QListWidget()
        right_panel_layout.addWidget(self.kasa_banka_list_widget)

        right_panel_layout.addWidget(QLabel("En Çok Satan Ürünler", font=QFont("Segoe UI", 12, QFont.Bold)))
        self.en_cok_satan_urunler_list_widget = QListWidget()
        right_panel_layout.addWidget(self.en_cok_satan_urunler_list_widget)

        right_panel_layout.addWidget(QLabel("Kritik Stok Ürünleri", font=QFont("Segoe UI", 12, QFont.Bold)))
        self.kritik_stok_urunler_list_widget = QListWidget()
        right_panel_layout.addWidget(self.kritik_stok_urunler_list_widget)

        # --- Grafik Alanı ---
        self.genel_bakis_grafik_frame = QFrame(parent_frame)
        self.genel_bakis_grafik_layout = QVBoxLayout(self.genel_bakis_grafik_frame)
        self.genel_bakis_grafik_layout.addWidget(QLabel("Aylık Finansal Trendler (Satış, Gelir, Gider)", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignCenter)
        parent_layout.addWidget(self.genel_bakis_grafik_frame, 2, 0, 1, 2) # Row 2, Col 0, span 1 row, 2 cols (Grafik en altta)
        self.genel_bakis_grafik_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.canvas_genel_bakis_main_plot = None
        self.ax_genel_bakis_main_plot = None

    def _create_metric_card(self, parent_frame, title, initial_value, card_type):
        """Metrik kartları için ortak bir çerçeve ve label oluşturur."""
        card_frame = QFrame(parent_frame)
        card_frame.setFrameShape(QFrame.StyledPanel)
        card_frame.setFrameShadow(QFrame.Raised)
        card_frame.setLineWidth(2)
        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title_label)

        value_label = QLabel(initial_value)
        value_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        value_label.setStyleSheet("color: navy;")
        value_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(value_label)

        setattr(self, f"lbl_metric_{card_type}", value_label)

        return card_frame
                
    def _create_satis_raporlari_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame)
        parent_layout.setColumnStretch(0, 2)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1)

        parent_layout.addWidget(QLabel("Detaylı Satış Raporları ve Analizi", font=QFont("Segoe UI", 16, QFont.Bold)), 0, 0, 1, 2, Qt.AlignCenter)

        left_panel = QFrame(parent_frame)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Satış Faturası Kalem Detayları", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignCenter)
        parent_layout.addWidget(left_panel, 1, 0)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_satis_detay = ("Fatura No", "Tarih", "Cari Adı", "Ürün Adı", "Miktar", "Birim Fiyat", "Toplam (KDV Dahil)")
        self.tree_satis_detay = QTreeWidget(left_panel)
        self.tree_satis_detay.setHeaderLabels(cols_satis_detay)
        self.tree_satis_detay.setColumnCount(len(cols_satis_detay))
        self.tree_satis_detay.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_satis_detay.setSortingEnabled(True)

        col_widths_satis_detay = {
            "Fatura No": 80, "Tarih": 70, "Cari Adı": 120, "Ürün Adı": 180, 
            "Miktar": 60, "Birim Fiyat": 90, "Toplam (KDV Dahil)": 100
        }
        for i, col_name in enumerate(cols_satis_detay):
            self.tree_satis_detay.setColumnWidth(i, col_widths_satis_detay.get(col_name, 100))
            if col_name == "Ürün Adı":
                self.tree_satis_detay.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.tree_satis_detay.header().setSectionResizeMode(i, QHeaderView.Interactive)
            self.tree_satis_detay.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name in ["Tarih", "Miktar", "Birim Fiyat", "Toplam (KDV Dahil)"]:
                self.tree_satis_detay.headerItem().setTextAlignment(i, Qt.AlignCenter if col_name == "Tarih" else Qt.AlignCenter)
            else:
                self.tree_satis_detay.headerItem().setTextAlignment(i, Qt.AlignCenter)
        
        left_layout.addWidget(self.tree_satis_detay)

        right_panel = QFrame(parent_frame)
        right_layout = QVBoxLayout(right_panel)
        parent_layout.addWidget(right_panel, 1, 1)
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.satis_odeme_dagilimi_frame = QFrame(right_panel)
        self.satis_odeme_dagilimi_layout = QVBoxLayout(self.satis_odeme_dagilimi_frame)
        self.satis_odeme_dagilimi_layout.addWidget(QLabel("Ödeme Türlerine Göre Satış Dağılımı", font=QFont("Segoe UI", 10, QFont.Bold)))
        right_layout.addWidget(self.satis_odeme_dagilimi_frame)
        self.satis_odeme_dagilimi_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_satis_odeme_dagilimi = None
        self.ax_satis_odeme_dagilimi = None

        self.en_cok_satan_urunler_frame = QFrame(right_panel)
        self.en_cok_satan_urunler_layout = QVBoxLayout(self.en_cok_satan_urunler_frame)
        self.en_cok_satan_urunler_layout.addWidget(QLabel("En Çok Satan Ürünler (Miktar)", font=QFont("Segoe UI", 10, QFont.Bold)))
        right_layout.addWidget(self.en_cok_satan_urunler_frame)
        self.en_cok_satan_urunler_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_en_cok_satan = None
        self.ax_en_cok_satan = None

    def _create_kar_zarar_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame)
        parent_layout.setColumnStretch(0, 1)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1)

        left_panel = QFrame(parent_frame)
        left_layout = QVBoxLayout(left_panel)
        parent_layout.addWidget(left_panel, 0, 0, 2, 1) # Row 0, Col 0, span 2 rows, 1 col
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        row_idx = 0
        left_layout.addWidget(QLabel("Dönem Brüt Kâr (Satış Geliri - Satılan Malın Maliyeti):", font=QFont("Segoe UI", 12, QFont.Bold)), alignment=Qt.AlignCenter)
        self.lbl_brut_kar = QLabel("0.00 TL")
        self.lbl_brut_kar.setFont(QFont("Segoe UI", 20))
        left_layout.addWidget(self.lbl_brut_kar, alignment=Qt.AlignCenter)
        row_idx += 2

        left_layout.addWidget(QLabel("Dönem Brüt Kâr Oranı:", font=QFont("Segoe UI", 16, QFont.Bold)), alignment=Qt.AlignCenter)
        self.lbl_brut_kar_orani = QLabel("%0.00")
        self.lbl_brut_kar_orani.setFont(QFont("Segoe UI", 20))
        left_layout.addWidget(self.lbl_brut_kar_orani, alignment=Qt.AlignCenter)
        row_idx += 2

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        left_layout.addWidget(separator)
        row_idx += 1

        left_layout.addWidget(QLabel("Dönem Satılan Malın Maliyeti (COGS - Alış Fiyatı Üzerinden):", font=QFont("Segoe UI", 16, QFont.Bold)), alignment=Qt.AlignCenter)
        self.lbl_cogs = QLabel("0.00 TL")
        self.lbl_cogs.setFont(QFont("Segoe UI", 20))
        left_layout.addWidget(self.lbl_cogs, alignment=Qt.AlignCenter)

        self.kar_zarar_grafik_frame = QFrame(parent_frame)
        self.kar_zarar_grafik_layout = QVBoxLayout(self.kar_zarar_grafik_frame)
        self.kar_zarar_grafik_layout.addWidget(QLabel("Aylık Kâr ve Maliyet Karşılaştırması", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignCenter)
        parent_layout.addWidget(self.kar_zarar_grafik_frame, 0, 1, 2, 1) # Row 0, Col 1, span 2 rows, 1 col
        self.kar_zarar_grafik_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.canvas_kar_zarar_main_plot = None
        self.ax_kar_zarar_main_plot = None

    def _create_nakit_akisi_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame)
        parent_layout.setColumnStretch(0, 1)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1)

        parent_layout.addWidget(QLabel("Nakit Akışı Detayları ve Bakiyeler", font=QFont("Segoe UI", 16, QFont.Bold)), 0, 0, 1, 2, Qt.AlignCenter)

        left_panel = QFrame(parent_frame)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("İşlem Detayları", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignCenter)
        parent_layout.addWidget(left_panel, 1, 0)
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_nakit_detay = ("Tarih", "Tip", "Tutar", "Açıklama", "Hesap Adı", "Kaynak")
        self.tree_nakit_akisi_detay = QTreeWidget(left_panel)
        self.tree_nakit_akisi_detay.setHeaderLabels(cols_nakit_detay)
        self.tree_nakit_akisi_detay.setColumnCount(len(cols_nakit_detay))
        self.tree_nakit_akisi_detay.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_nakit_akisi_detay.setSortingEnabled(True)

        col_widths_nakit_detay = {
            "Tarih": 80, "Tip": 60, "Tutar": 90, "Açıklama": 180, "Hesap Adı": 90, "Kaynak": 70
        }
        for i, col_name in enumerate(cols_nakit_detay):
            self.tree_nakit_akisi_detay.setColumnWidth(i, col_widths_nakit_detay.get(col_name, 100))
            if col_name == "Açıklama":
                self.tree_nakit_akisi_detay.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.tree_nakit_akisi_detay.header().setSectionResizeMode(i, QHeaderView.Interactive)
            self.tree_nakit_akisi_detay.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name in ["Tarih", "Tip", "Tutar", "Kaynak"]:
                self.tree_nakit_akisi_detay.headerItem().setTextAlignment(i, Qt.AlignCenter)
            else:
                self.tree_nakit_akisi_detay.headerItem().setTextAlignment(i, Qt.AlignCenter)
        
        left_layout.addWidget(self.tree_nakit_akisi_detay)

        self.nakit_akis_grafik_frame = QFrame(parent_frame)
        self.nakit_akis_grafik_layout = QVBoxLayout(self.nakit_akis_grafik_frame)
        self.nakit_akis_grafik_layout.addWidget(QLabel("Aylık Nakit Akışı Trendi", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignCenter)
        parent_layout.addWidget(self.nakit_akis_grafik_frame, 1, 1)
        self.nakit_akis_grafik_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.canvas_nakit_akisi_trend = None
        self.ax_nakit_akisi_trend = None

        # Özet bilgiler ve kasa/banka bakiyeleri
        summary_frame = QFrame(parent_frame)
        summary_layout = QVBoxLayout(summary_frame)
        parent_layout.addWidget(summary_frame, 2, 0, 1, 2) # Row 2, Col 0, span 1 row, 2 cols
        summary_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        summary_layout.addWidget(QLabel("Dönem Nakit Akışı Özetleri (Kasa/Banka Bağlantılı)", font=QFont("Segoe UI", 15, QFont.Bold)), alignment=Qt.AlignCenter)
        self.lbl_nakit_giris = QLabel("Toplam Nakit Girişi: 0.00 TL")
        self.lbl_nakit_giris.setFont(QFont("Segoe UI", 15))
        summary_layout.addWidget(self.lbl_nakit_giris, alignment=Qt.AlignCenter)
        self.lbl_nakit_cikis = QLabel("Toplam Nakit Çıkışı: 0.00 TL")
        self.lbl_nakit_cikis.setFont(QFont("Segoe UI", 15))
        summary_layout.addWidget(self.lbl_nakit_cikis, alignment=Qt.AlignCenter)
        self.lbl_nakit_net = QLabel("Dönem Net Nakit Akışı: 0.00 TL")
        self.lbl_nakit_net.setFont(QFont("Segoe UI", 15, QFont.Bold))
        summary_layout.addWidget(self.lbl_nakit_net, alignment=Qt.AlignCenter)

        self.kasa_banka_bakiye_frame = QFrame(summary_frame)
        self.kasa_banka_bakiye_layout = QHBoxLayout(self.kasa_banka_bakiye_frame)
        summary_layout.addWidget(self.kasa_banka_bakiye_frame)
        self.kasa_banka_bakiye_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _create_cari_hesaplar_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame)
        parent_layout.setColumnStretch(0, 1)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1)

        parent_layout.addWidget(QLabel("Cari Hesaplar Raporları (Yaşlandırma)", font=QFont("Segoe UI", 16, QFont.Bold)), 0, 0, 1, 2, Qt.AlignCenter)

        musteri_alacak_frame = QFrame(parent_frame)
        musteri_alacak_layout = QVBoxLayout(musteri_alacak_frame)
        musteri_alacak_layout.addWidget(QLabel("Müşteri Alacakları (Bize Borçlu)", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignCenter)
        parent_layout.addWidget(musteri_alacak_frame, 1, 0)
        musteri_alacak_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_cari_yaslandirma = ("Cari Adı", "Tutar", "Vadesi Geçen Gün")
        self.tree_cari_yaslandirma_alacak = QTreeWidget(musteri_alacak_frame)
        self.tree_cari_yaslandirma_alacak.setHeaderLabels(cols_cari_yaslandirma)
        self.tree_cari_yaslandirma_alacak.setColumnCount(len(cols_cari_yaslandirma))
        self.tree_cari_yaslandirma_alacak.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_cari_yaslandirma_alacak.setSortingEnabled(True)

        col_widths_cari_yaslandirma = {
            "Cari Adı": 150, "Tutar": 100, "Vadesi Geçen Gün": 100
        }
        for i, col_name in enumerate(cols_cari_yaslandirma):
            self.tree_cari_yaslandirma_alacak.setColumnWidth(i, col_widths_cari_yaslandirma.get(col_name, 100))
            if col_name == "Cari Adı":
                self.tree_cari_yaslandirma_alacak.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.tree_cari_yaslandirma_alacak.header().setSectionResizeMode(i, QHeaderView.Interactive)
            self.tree_cari_yaslandirma_alacak.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name in ["Tutar", "Vadesi Geçen Gün"]:
                self.tree_cari_yaslandirma_alacak.headerItem().setTextAlignment(i, Qt.AlignCenter)
            else:
                self.tree_cari_yaslandirma_alacak.headerItem().setTextAlignment(i, Qt.AlignCenter)
        
        musteri_alacak_layout.addWidget(self.tree_cari_yaslandirma_alacak)
        
        # Stil için QPalette veya item.setBackground() kullanılabilir.
        # Placeholder QBrush and QColor for now.
        # self.tree_cari_yaslandirma_alacak.tag_configure('header', font=('Segoe UI', 9, 'bold'), background='#E0E0E0')
        # self.tree_cari_yaslandirma_alacak.tag_configure('empty', foreground='gray')


        tedarikci_borc_frame = QFrame(parent_frame)
        tedarikci_borc_layout = QVBoxLayout(tedarikci_borc_frame)
        tedarikci_borc_layout.addWidget(QLabel("Tedarikçi Borçları (Biz Borçluyuz)", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignCenter)
        parent_layout.addWidget(tedarikci_borc_frame, 1, 1)
        tedarikci_borc_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.tree_cari_yaslandirma_borc = QTreeWidget(tedarikci_borc_frame)
        self.tree_cari_yaslandirma_borc.setHeaderLabels(cols_cari_yaslandirma)
        self.tree_cari_yaslandirma_borc.setColumnCount(len(cols_cari_yaslandirma))
        self.tree_cari_yaslandirma_borc.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_cari_yaslandirma_borc.setSortingEnabled(True)

        for i, col_name in enumerate(cols_cari_yaslandirma):
            self.tree_cari_yaslandirma_borc.setColumnWidth(i, col_widths_cari_yaslandirma.get(col_name, 100))
            if col_name == "Cari Adı":
                self.tree_cari_yaslandirma_borc.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.tree_cari_yaslandirma_borc.header().setSectionResizeMode(i, QHeaderView.Interactive)
            self.tree_cari_yaslandirma_borc.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name in ["Tutar", "Vadesi Geçen Gün"]:
                self.tree_cari_yaslandirma_borc.headerItem().setTextAlignment(i, Qt.AlignCenter)
            else:
                self.tree_cari_yaslandirma_borc.headerItem().setTextAlignment(i, Qt.AlignCenter)
        
        tedarikci_borc_layout.addWidget(self.tree_cari_yaslandirma_borc)
        # Stil için QPalette veya item.setBackground() kullanılabilir.
        # self.tree_cari_yaslandirma_borc.tag_configure('header', font=('Segoe UI', 9, 'bold'), background='#E0E0E0')
        # self.tree_cari_yaslandirma_borc.tag_configure('empty', foreground='gray')


        bottom_summary_frame = QFrame(parent_frame)
        bottom_summary_layout = QHBoxLayout(bottom_summary_frame)
        parent_layout.addWidget(bottom_summary_frame, 2, 0, 1, 2) # Row 2, Col 0, span 1 row, 2 cols
        bottom_summary_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.lbl_toplam_alacak_cari = QLabel("Toplam Alacak: 0.00 TL")
        self.lbl_toplam_alacak_cari.setFont(QFont("Segoe UI", 10, QFont.Bold))
        bottom_summary_layout.addWidget(self.lbl_toplam_alacak_cari)

        self.lbl_toplam_borc_cari = QLabel("Toplam Borç: 0.00 TL")
        self.lbl_toplam_borc_cari.setFont(QFont("Segoe UI", 10, QFont.Bold))
        bottom_summary_layout.addWidget(self.lbl_toplam_borc_cari)

        self.lbl_net_bakiye_cari = QLabel("Net Bakiye: 0.00 TL")
        self.lbl_net_bakiye_cari.setFont(QFont("Segoe UI", 12, QFont.Bold))
        bottom_summary_layout.addWidget(self.lbl_net_bakiye_cari, alignment=Qt.AlignCenter)

    def _create_stok_raporlari_tab(self, parent_frame):
        parent_layout = QGridLayout(parent_frame)
        parent_layout.setColumnStretch(0, 1)
        parent_layout.setColumnStretch(1, 1)
        parent_layout.setRowStretch(1, 1)

        parent_layout.addWidget(QLabel("Stok Raporları", font=QFont("Segoe UI", 16, QFont.Bold)), 0, 0, 1, 2, Qt.AlignCenter)

        envanter_frame = QFrame(parent_frame)
        envanter_layout = QVBoxLayout(envanter_frame)
        envanter_layout.addWidget(QLabel("Mevcut Stok Envanteri", font=QFont("Segoe UI", 10, QFont.Bold)), alignment=Qt.AlignCenter)
        parent_layout.addWidget(envanter_frame, 1, 0)
        envanter_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols_stok = ("Ürün Kodu", "Ürün Adı", "Miktar", "Alış Fyt (KDV Dahil)", "Satış Fyt (KDV Dahil)", "KDV %", "Min. Stok")
        self.tree_stok_envanter = QTreeWidget(envanter_frame)
        self.tree_stok_envanter.setHeaderLabels(cols_stok)
        self.tree_stok_envanter.setColumnCount(len(cols_stok))
        self.tree_stok_envanter.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_stok_envanter.setSortingEnabled(True)

        col_widths_stok = {
            "Ürün Kodu": 100, "Ürün Adı": 150, "Miktar": 80, 
            "Alış Fyt (KDV Dahil)": 120, "Satış Fyt (KDV Dahil)": 120, 
            "KDV %": 55, "Min. Stok": 80
        }
        for i, col_name in enumerate(cols_stok):
            self.tree_stok_envanter.setColumnWidth(i, col_widths_stok.get(col_name, 100))
            if col_name == "Ürün Adı":
                self.tree_stok_envanter.header().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.tree_stok_envanter.header().setSectionResizeMode(i, QHeaderView.Interactive)
            self.tree_stok_envanter.headerItem().setFont(i, QFont("Segoe UI", 9, QFont.Bold))
            if col_name in ["Miktar", "Alış Fyt (KDV Dahil)", "Satış Fyt (KDV Dahil)", "KDV %", "Min. Stok"]:
                self.tree_stok_envanter.headerItem().setTextAlignment(i, Qt.AlignCenter)
            else:
                self.tree_stok_envanter.headerItem().setTextAlignment(i, Qt.AlignCenter)
        
        envanter_layout.addWidget(self.tree_stok_envanter)

        stok_grafikler_frame = QFrame(parent_frame)
        stok_grafikler_layout = QVBoxLayout(stok_grafikler_frame)
        parent_layout.addWidget(stok_grafikler_frame, 1, 1)
        stok_grafikler_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.stok_kritik_grafik_frame = QFrame(stok_grafikler_frame)
        self.stok_kritik_grafik_layout = QVBoxLayout(self.stok_kritik_grafik_frame)
        self.stok_kritik_grafik_layout.addWidget(QLabel("Kritik Stok Durumu", font=QFont("Segoe UI", 10, QFont.Bold)))
        stok_grafikler_layout.addWidget(self.stok_kritik_grafik_frame)
        self.stok_kritik_grafik_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_stok_kritik = None
        self.ax_stok_kritik = None

        self.stok_kategori_dagilim_frame = QFrame(stok_grafikler_frame)
        self.stok_kategori_dagilim_layout = QVBoxLayout(self.stok_kategori_dagilim_frame)
        self.stok_kategori_dagilim_layout.addWidget(QLabel("Kategoriye Göre Toplam Stok Değeri", font=QFont("Segoe UI", 10, QFont.Bold)))
        stok_grafikler_layout.addWidget(self.stok_kategori_dagilim_frame)
        self.stok_kategori_dagilim_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_stok_kategori = None
        self.ax_stok_kategori = None

    def _on_tab_change(self, index): # index parametresi currentChanged sinyalinden gelir
        selected_tab_text = self.report_notebook.tabText(index) # tabText(index) ile metin alınır
        bas_t_str = self.bas_tarih_entry.text()
        bit_t_str = self.bit_tarih_entry.text()

        if selected_tab_text == "📊 Genel Bakış":
            self._update_genel_bakis_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "📈 Satış Raporları":
            self._update_satis_raporlari_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "💰 Kâr ve Zarar":
            self._update_kar_zarar_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "🏦 Nakit Akışı":
            self._update_nakit_akisi_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "👥 Cari Hesaplar":
            self._update_cari_hesaplar_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "📦 Stok Raporları":
            self._update_stok_raporlari_tab(bas_t_str, bit_t_str)

        self.app.set_status_message(f"Rapor güncellendi: {selected_tab_text} ({bas_t_str} - {bit_t_str}).")

    def raporu_olustur_ve_yenile(self):
        bas_t_str = self.bas_tarih_entry.text()
        bit_t_str = self.bit_tarih_entry.text()

        try:
            bas_t = datetime.strptime(bas_t_str, '%Y-%m-%d')
            bit_t = datetime.strptime(bit_t_str, '%Y-%m-%d')
            if bas_t > bit_t:
                QMessageBox.critical(self.app, "Tarih Hatası", "Başlangıç tarihi, bitiş tarihinden sonra olamaz.")
                return
        except ValueError:
            QMessageBox.critical(self.app, "Tarih Formatı Hatası", "Tarih formatı (`YYYY-AA-GG`) olmalıdır (örn: 2023-12-31).")
            return

        selected_tab_text = self.report_notebook.tabText(self.report_notebook.currentIndex())
        if selected_tab_text == "📊 Genel Bakış":
            self._update_genel_bakis_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "📈 Satış Raporları":
            self._update_satis_raporlari_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "💰 Kâr ve Zarar":
            self._update_kar_zarar_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "🏦 Nakit Akışı":
            self._update_nakit_akisi_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "👥 Cari Hesaplar":
            self._update_cari_hesaplar_tab(bas_t_str, bit_t_str)
        elif selected_tab_text == "📦 Stok Raporları":
            self._update_stok_raporlari_tab(bas_t_str, bit_t_str)

        self.app.set_status_message(f"Finansal Raporlar güncellendi.")

    def _update_genel_bakis_tab(self, bas_t_str, bit_t_str):
        try:
            # 1. GÜNCELLEME: kullanici_id parametresi kaldırıldı.
            dashboard_summary = self.db.get_dashboard_summary(baslangic_tarihi=bas_t_str, bitis_tarihi=bit_t_str) or {}
            
            toplam_satislar = dashboard_summary.get("toplam_satislar", 0.0)
            toplam_alislar = dashboard_summary.get("toplam_alislar", 0.0)
            toplam_tahsilatlar = dashboard_summary.get("toplam_tahsilatlar", 0.0)
            toplam_odemeler = dashboard_summary.get("toplam_odemeler", 0.0)
            vadesi_yaklasan_alacaklar_toplami = dashboard_summary.get("vadesi_yaklasan_alacaklar_toplami", 0.0)
            vadesi_gecmis_borclar_toplami = dashboard_summary.get("vadesi_gecmis_borclar_toplami", 0.0)
            kritik_stok_sayisi = dashboard_summary.get("kritik_stok_sayisi", 0)
            en_cok_satan_urunler = dashboard_summary.get("en_cok_satan_urunler", [])

            self.lbl_metric_total_sales.setText(self.db._format_currency(toplam_satislar))
            self.lbl_metric_total_purchases.setText(self.db._format_currency(toplam_alislar))
            self.lbl_metric_total_collections.setText(self.db._format_currency(toplam_tahsilatlar))
            self.lbl_metric_total_payments.setText(self.db._format_currency(toplam_odemeler))
            self.lbl_metric_approaching_receivables.setText(self.db._format_currency(vadesi_yaklasan_alacaklar_toplami))
            self.lbl_metric_overdue_payables.setText(self.db._format_currency(vadesi_gecmis_borclar_toplami))

            # 2. GÜNCELLEME: kullanici_id parametresi kaldırıldı.
            kar_zarar_data = self.db.get_kar_zarar_verileri(baslangic_tarihi=bas_t_str, bitis_tarihi=bit_t_str) or {}
            self.lbl_genel_bakis_donem_gelir.setText(self.db._format_currency(kar_zarar_data.get("diger_gelirler", 0.0)))
            self.lbl_genel_bakis_donem_gider.setText(self.db._format_currency(kar_zarar_data.get("diger_giderler", 0.0)))
            self.lbl_genel_bakis_brut_kar.setText(self.db._format_currency(kar_zarar_data.get("brut_kar", 0.0)))
            self.lbl_genel_bakis_net_kar.setText(self.db._format_currency(kar_zarar_data.get("net_kar", 0.0)))

            # 3. GÜNCELLEME: kullanici_id parametresi kaldırıldı.
            nakit_akis_data = self.db.get_nakit_akisi_verileri(baslangic_tarihi=bas_t_str, bitis_tarihi=bit_t_str) or {}
            self.lbl_genel_bakis_nakit_girisleri.setText(self.db._format_currency(nakit_akis_data.get("nakit_girisleri", 0.0)))
            self.lbl_genel_bakis_nakit_cikislar.setText(self.db._format_currency(nakit_akis_data.get("nakit_cikislar", 0.0)))
            self.lbl_genel_bakis_net_nakit_akisi.setText(self.db._format_currency(nakit_akis_data.get("net_nakit_akisi", 0.0)))

            # 4. GÜNCELLEME: kullanici_id parametresi kaldırıldı.
            kasa_banka_bakiyeleri = self.db.get_tum_kasa_banka_bakiyeleri() or []
            self.kasa_banka_list_widget.clear()
            if kasa_banka_bakiyeleri:
                for hesap in kasa_banka_bakiyeleri:
                    bakiye = hesap.get("bakiye", 0.0)
                    hesap_adi = hesap.get("hesap_adi")
                    item_text = f"{hesap_adi}: {self.db._format_currency(bakiye)}"
                    item = QListWidgetItem(item_text)
                    if bakiye < 0:
                        item.setForeground(QBrush(QColor("red")))
                    self.kasa_banka_list_widget.addItem(item)
            else:
                self.kasa_banka_list_widget.addItem("Kasa/Banka Bakiyesi Bulunamadı.")

            # 5. GÜNCELLEME: kullanici_id parametresi kaldırıldı.
            critical_stock_items = self.db.get_critical_stock_items() or []
            self.kritik_stok_urunler_list_widget.clear()
            if critical_stock_items:
                for urun in critical_stock_items:
                    item_text = f"{urun.get('ad', 'Bilinmeyen Ürün')} (Stok: {urun.get('miktar', 0):.0f}, Min: {urun.get('min_stok_seviyesi', 0):.0f})"
                    item = QListWidgetItem(item_text)
                    item.setForeground(QBrush(QColor("orange")))
                    self.kritik_stok_urunler_list_widget.addItem(item)
            else:
                self.kritik_stok_urunler_list_widget.addItem("Kritik stok altında ürün bulunamadı.")

            # 6. GÜNCELLEME: kullanici_id parametresi kaldırıldı.
            aylik_gelir_gider_ozet_data = self.db.get_gelir_gider_aylik_ozet(baslangic_tarihi=bas_t_str, bitis_tarihi=bit_t_str) or {}
            
            aylar_labels = [item.get('ay_adi') for item in aylik_gelir_gider_ozet_data.get('aylik_ozet', [])]
            toplam_gelirler = [item.get('toplam_gelir') for item in aylik_gelir_gider_ozet_data.get('aylik_ozet', [])]
            toplam_giderler = [item.get('toplam_gider') for item in aylik_gelir_gider_ozet_data.get('aylik_ozet', [])]

            self.canvas_genel_bakis_main_plot, self.ax_genel_bakis_main_plot = self._draw_plot(
                self.genel_bakis_grafik_frame,
                self.canvas_genel_bakis_main_plot,
                self.ax_genel_bakis_main_plot,
                "Aylık Finansal Trendler (Gelir ve Gider)",
                aylar_labels,
                [toplam_gelirler, toplam_giderler],
                plot_type='grouped_bar',
                group_labels=['Toplam Gelir', 'Toplam Gider'],
                colors=['mediumseagreen', 'indianred'],
                rotation=45
            )

        except Exception as e:
            logger.error(f"Genel bakış sekmesi güncellenirken hata: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"Genel bakış sekmesi yüklenirken bir hata oluştu:\n{e}")
            
    def _update_satis_raporlari_tab(self, bas_t_str, bit_t_str):
        self.tree_satis_detay.clear()

        satis_detay_data = self.db.tarihsel_satis_raporu_verilerini_al(kullanici_id=self.app.current_user_id, baslangic_tarihi=bas_t_str, bitis_tarihi=bit_t_str)
        if satis_detay_data:
            for item in satis_detay_data:
                formatted_tarih = item.get('tarih', '').strftime('%d.%m.%Y') if isinstance(item.get('tarih'), (datetime, date)) else (str(item.get('tarih')) if item.get('tarih') is not None else "")

                item_qt = QTreeWidgetItem(self.tree_satis_detay)
                item_qt.setText(0, item.get('fatura_no', ''))
                item_qt.setText(1, formatted_tarih)
                item_qt.setText(2, item.get('cari_adi', ''))
                item_qt.setText(3, item.get('urun_adi', ''))
                item_qt.setText(4, f"{item.get('miktar', 0.0):.2f}".rstrip('0').rstrip('.'))
                item_qt.setText(5, self.db._format_currency(item.get('birim_fiyat_kdv_dahil', 0.0)))
                item_qt.setText(6, self.db._format_currency(item.get('kalem_toplam_kdv_dahil', 0.0)))

                item_qt.setData(4, Qt.UserRole, item.get('miktar', 0.0))
                item_qt.setData(5, Qt.UserRole, item.get('birim_fiyat_kdv_dahil', 0.0))
                item_qt.setData(6, Qt.UserRole, item.get('kalem_toplam_kdv_dahil', 0.0))
        else:
            item_qt = QTreeWidgetItem(self.tree_satis_detay)
            item_qt.setText(2, "Veri Yok")

        sales_by_payment_type = self.db.get_sales_by_payment_type(baslangic_tarihi=bas_t_str, bitis_tarihi=bit_t_str, kullanici_id=self.app.current_user_id)
        plot_labels_odeme = [item.get('odeme_turu') for item in sales_by_payment_type]
        plot_values_odeme = [item.get('toplam_tutar') for item in sales_by_payment_type]

        self.canvas_satis_odeme_dagilimi, self.ax_satis_odeme_dagilimi = self._draw_plot(
            self.satis_odeme_dagilimi_frame,
            self.canvas_satis_odeme_dagilimi,
            self.ax_satis_odeme_dagilimi,
            "Ödeme Türlerine Göre Satış Dağılımı",
            plot_labels_odeme, plot_values_odeme, plot_type='pie'
        )

        top_selling_products = self.db.get_top_selling_products(kullanici_id=self.app.current_user_id, baslangic_tarihi=bas_t_str, bitis_tarih=bit_t_str, limit=5)
        plot_labels_top_satan = [item.get('ad') for item in top_selling_products]
        plot_values_top_satan = [item.get('toplam_miktar') for item in top_selling_products]

        self.canvas_en_cok_satan, self.ax_en_cok_satan = self._draw_plot(
            self.en_cok_satan_urunler_frame,
            self.canvas_en_cok_satan,
            self.ax_en_cok_satan,
            "En Çok Satan Ürünler (Miktar)",
            plot_labels_top_satan, plot_values_top_satan, plot_type='bar', rotation=30, show_labels_on_bars=True
        )

    def _update_kar_zarar_tab(self, bas_t_str, bit_t_str):
        gross_profit, cogs, gross_profit_rate = self.db.get_gross_profit_and_cost(kullanici_id=self.app.current_user_id, baslangic_tarihi=bas_t_str, bitis_tarih=bit_t_str)
        self.lbl_brut_kar.setText(self.db._format_currency(gross_profit))
        self.lbl_cogs.setText(self.db._format_currency(cogs))
        self.lbl_brut_kar_orani.setText(f"%{gross_profit_rate:,.2f}")

        monthly_gross_profit_data = self.db.get_monthly_gross_profit_summary(kullanici_id=self.app.current_user_id, baslangic_tarihi=bas_t_str, bitis_tarihi=bit_t_str)

        all_periods_set = set()
        for item in monthly_gross_profit_data: all_periods_set.add(item.get('ay_yil'))
        periods = sorted(list(all_periods_set))

        full_sales_income = [0] * len(periods)
        full_cogs = [0] * len(periods)

        for i, period in enumerate(periods):
            for mgp in monthly_gross_profit_data:
                if mgp.get('ay_yil') == period:
                    full_sales_income[i] = mgp.get('toplam_satis_geliri', 0)
                    full_cogs[i] = mgp.get('satilan_malin_maliyeti', 0)

        self.canvas_kar_zarar_main_plot, self.ax_kar_zarar_main_plot = self._draw_plot(
            self.kar_zarar_grafik_frame,
            self.canvas_kar_zarar_main_plot,
            self.ax_kar_zarar_main_plot,
            "Aylık Kâr ve Maliyet Karşılaştırması",
            periods,
            [full_sales_income, full_cogs],
            plot_type='grouped_bar',
            group_labels=['Toplam Satış Geliri', 'Satılan Malın Maliyeti'],
            colors=['teal', 'darkorange']
        )

    def _update_nakit_akisi_tab(self, bas_t_str, bit_t_str):
        self.tree_nakit_akisi_detay.clear()

        nakit_akis_detay_data = self.db.get_nakit_akisi_verileri(kullanici_id=self.app.current_user_id, baslangic_tarihi=bas_t_str, bitis_tarih=bit_t_str)
        if nakit_akis_detay_data:
            for item in nakit_akis_detay_data:
                formatted_tarih = item.get('tarih', '').strftime('%d.%m.%Y') if isinstance(item.get('tarih'), (datetime, date)) else (str(item.get('tarih')) if item.get('tarih') is not None else "")

                item_qt = QTreeWidgetItem(self.tree_nakit_akisi_detay)
                item_qt.setText(0, formatted_tarih)
                item_qt.setText(1, item.get('tip', ''))
                item_qt.setText(2, self.db._format_currency(item.get('tutar', 0.0)))
                item_qt.setText(3, item.get('aciklama', '-') if item.get('aciklama') else "-")
                item_qt.setText(4, item.get('hesap_adi', '-') if item.get('hesap_adi') else "-")
                item_qt.setText(5, item.get('kaynak', '-') if item.get('kaynak') else "-")

                item_qt.setData(2, Qt.UserRole, item.get('tutar', 0.0))
        else:
            item_qt = QTreeWidgetItem(self.tree_nakit_akisi_detay)
            item_qt.setText(2, "Veri Yok")

        toplam_nakit_giris = nakit_akis_detay_data.get("nakit_girisleri", 0.0)
        toplam_nakit_cikis = nakit_akis_detay_data.get("nakit_cikislar", 0.0)

        self.lbl_nakit_giris.setText(f"Toplam Nakit Girişi: {self.db._format_currency(toplam_nakit_giris)}")
        self.lbl_nakit_cikis.setText(f"Toplam Nakit Çıkışı: {self.db._format_currency(toplam_nakit_cikis)}")
        self.lbl_nakit_net.setText(f"Dönem Net Nakit Akışı: {self.db._format_currency(toplam_nakit_giris - toplam_nakit_cikis)}")

        monthly_cash_flow_data = self.db.get_monthly_cash_flow_summary(kullanici_id=self.app.current_user_id, baslangic_tarihi=bas_t_str, bitis_tarih=bit_t_str)

        all_periods_cf_set = set()
        for item in monthly_cash_flow_data: all_periods_cf_set.add(item.get('ay_yil'))
        periods_cf = sorted(list(all_periods_cf_set))

        full_cash_in = [0] * len(periods_cf)
        full_cash_out = [0] * len(periods_cf)

        for i, period in enumerate(periods_cf):
            for mcf in monthly_cash_flow_data:
                if mcf.get('ay_yil') == period:
                    full_cash_in[i] = mcf.get('toplam_giris', 0)
                    full_cash_out[i] = mcf.get('toplam_cikis', 0)

        self.canvas_nakit_akisi_trend, self.ax_nakit_akisi_trend = self._draw_plot(
            self.nakit_akis_grafik_frame,
            self.canvas_nakit_akisi_trend,
            self.ax_nakit_akisi_trend,
            "Aylık Nakit Akışı",
            periods_cf,
            [full_cash_in, full_cash_out],
            plot_type='grouped_bar',
            group_labels=['Toplam Giriş', 'Toplam Çıkış'],
            colors=['mediumseagreen', 'indianred']
        )

    def _update_cari_hesaplar_tab(self, bas_t_str, bit_t_str):
        self.cari_yaslandirma_data = self.db.get_cari_yaslandirma_verileri(kullanici_id=self.app.current_user_id, tarih=bit_t_str)

        self.tree_cari_yaslandirma_alacak.clear()
        self._populate_yaslandirma_treeview(self.tree_cari_yaslandirma_alacak, self.cari_yaslandirma_data.get('musteri_alacaklar', {}))
        
        self.tree_cari_yaslandirma_borc.clear()
        self._populate_yaslandirma_treeview(self.tree_cari_yaslandirma_borc, self.cari_yaslandirma_data.get('tedarikci_borclar', {}))

        toplam_alacak = sum(item.get('bakiye', 0.0) for item in self.cari_yaslandirma_data.get('musteri_alacaklar', []) if isinstance(item, dict))
        toplam_borc = sum(item.get('bakiye', 0.0) for item in self.cari_yaslandirma_data.get('tedarikci_borclar', []) if isinstance(item, dict))
        net_bakiye_cari = toplam_alacak - toplam_borc

        self.lbl_toplam_alacak_cari.setText(f"Toplam Alacak: {self.db._format_currency(toplam_alacak)}")
        self.lbl_toplam_borc_cari.setText(f"Toplam Borç: {self.db._format_currency(toplam_borc)}")
        self.lbl_net_bakiye_cari.setText(f"Net Bakiye: {self.db._format_currency(net_bakiye_cari)}")

    def _populate_yaslandirma_treeview(self, tree, data_dict):
        # Clear existing items is handled by the caller
        if not data_dict: # Eğer veri boşsa
            header_item = QTreeWidgetItem(tree)
            header_item.setText(0, "Veri Bulunamadı")
            for col_idx in range(tree.columnCount()):
                header_item.setForeground(col_idx, QBrush(QColor("gray")))
            return

        # data_dict artık { '0-30': [item1, ...], '31-60': [...] } formatında bekleniyor.
        # Bu yüzden dict.values() yerine dict.items() ile key'leri de alıyoruz.
        for period_key, items in data_dict.items():
            header_item = QTreeWidgetItem(tree)
            header_item.setText(0, f"--- {period_key} Gün ---") # Period key'i kullan (örn: '0-30', '31-60')
            header_item.setFont(0, QFont("Segoe UI", 9, QFont.Bold))
            for col_idx in range(tree.columnCount()):
                header_item.setBackground(col_idx, QBrush(QColor("#E0E0E0"))) # Arka plan
                header_item.setForeground(col_idx, QBrush(QColor("black"))) # Metin rengi

            if items:
                for item in items: # item: dictionary olmalı
                    child_item = QTreeWidgetItem(header_item)
                    child_item.setText(0, item.get('cari_ad', '')) # Cari Adı
                    child_item.setText(1, self.db._format_currency(item.get('bakiye', 0.0))) # Tutar (bakiyeyi kullan)
                    
                    # 'vadesi_gecen_gun' doğrudan API'den gelmeyebilir, client'ta hesaplanır veya None olabilir
                    # Bu nedenle, basitçe boş bırakabiliriz veya bir placeholder koyabiliriz.
                    vade_tarihi = item.get('vade_tarihi')
                    if vade_tarihi:
                        try:
                            # Tarih string ise datetime objesine çevir
                            if isinstance(vade_tarihi, str):
                                vade_tarihi = datetime.strptime(vade_tarihi, '%Y-%m-%d').date()
                            
                            # Vadesi geçen gün sayısını hesapla
                            delta = (date.today() - vade_tarihi).days
                            if delta > 0:
                                child_item.setText(2, f"{delta} gün")
                            else:
                                child_item.setText(2, "-") # Vadesi geçmemişse
                        except (ValueError, TypeError):
                            child_item.setText(2, "-") # Tarih formatı hatalıysa
                    else:
                        child_item.setText(2, "-") # Vade tarihi yoksa

                    # Sayısal sütunlar için sıralama anahtarları
                    child_item.setData(1, Qt.UserRole, item.get('bakiye', 0.0)) # Tutar
                    child_item.setData(2, Qt.UserRole, delta if vade_tarihi and delta > 0 else 0) # Vadesi Geçen Gün (sıralanabilir sayı)
            else:
                child_item = QTreeWidgetItem(header_item)
                child_item.setText(0, "Bu Kategori Boş")
                for col_idx in range(tree.columnCount()):
                    child_item.setForeground(col_idx, QBrush(QColor("gray"))) # Gri metin

        tree.expandAll() # Tüm header'ları aç

    def _update_stok_raporlari_tab(self, bas_t_str, bit_t_str):
        self.tree_stok_envanter.clear()

        all_stock_items_response = self.db.stok_listesi_al(kullanici_id=self.app.current_user_id, aktif_durum=True, limit=10000)
        all_stock_items = all_stock_items_response.get("items", [])

        if all_stock_items:
            for item in all_stock_items:
                item_qt = QTreeWidgetItem(self.tree_stok_envanter)
                item_qt.setText(0, item.get('kod', ''))
                item_qt.setText(1, item.get('ad', ''))
                item_qt.setText(2, f"{item.get('miktar', 0.0):.2f}".rstrip('0').rstrip('.'))
                item_qt.setText(3, self.db._format_currency(item.get('alis_fiyati', 0.0)))
                item_qt.setText(4, self.db._format_currency(item.get('satis_fiyati', 0.0)))
                item_qt.setText(5, f"{item.get('kdv_orani', 0.0):.0f}%")
                item_qt.setText(6, f"{item.get('min_stok_seviyesi', 0.0):.2f}".rstrip('0').rstrip('.'))

                item_qt.setData(2, Qt.UserRole, item.get('miktar', 0.0))
                item_qt.setData(3, Qt.UserRole, item.get('alis_fiyati', 0.0))
                item_qt.setData(4, Qt.UserRole, item.get('satis_fiyati', 0.0))
                item_qt.setData(5, Qt.UserRole, item.get('kdv_orani', 0.0))
                item_qt.setData(6, Qt.UserRole, item.get('min_stok_seviyesi', 0.0))
        else:
            item_qt = QTreeWidgetItem(self.tree_stok_envanter)
            item_qt.setText(2, "Veri Yok")

        critical_items = self.db.get_critical_stock_items(kullanici_id=self.app.current_user_id)
        
        num_critical_stock = len(critical_items)
        num_normal_stock = len(all_stock_items) - num_critical_stock

        labels_kritik = ["Kritik Stokta", "Normal Stokta"]
        values_kritik = [num_critical_stock, num_normal_stock]

        self.canvas_stok_kritik, self.ax_stok_kritik = self._draw_plot(
            self.stok_kritik_grafik_frame,
            self.canvas_stok_kritik,
            self.ax_stok_kritik,
            "Kritik Stok Durumu",
            labels_kritik, values_kritik, plot_type='pie', colors=['indianred', 'lightgreen']
        )

        stock_value_by_category_response = self.db.get_stock_value_by_category(kullanici_id=self.app.current_user_id)
        stock_value_by_category = stock_value_by_category_response.get("items", [])

        labels_kategori = [item.get('kategori_adi') for item in stock_value_by_category if item.get('kategori_adi')]
        values_kategori = [item.get('toplam_deger') for item in stock_value_by_category if item.get('kategori_adi')]

        self.canvas_stok_kategori, self.ax_stok_kategori = self._draw_plot(
            self.stok_kategori_dagilim_frame,
            self.canvas_stok_kategori,
            self.ax_stok_kategori,
            "Kategoriye Göre Toplam Stok Değeri",
            labels_kategori, values_kategori, plot_type='pie'
        )
        
    def raporu_pdf_yazdir_placeholder(self):
        # Raporu PDF olarak kaydetme işlemi için dosya kaydetme diyaloğu
        initial_file_name = f"Rapor_Ozeti_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self.app,
                                                "Raporu PDF olarak kaydet",
                                                initial_file_name,
                                                "PDF Dosyaları (*.pdf);;Tüm Dosyalar (*)")

        if file_path:
            try:
                current_tab_text = self.report_notebook.tabText(self.report_notebook.currentIndex())
                success = False
                message = ""

                # Sadece satış raporları için PDF oluşturma örneği
                if current_tab_text == "📈 Satış Raporları":
                    bas_t_str = self.bas_tarih_entry.text()
                    bit_t_str = self.bit_tarih_entry.text()

                    # db.tarihsel_satis_raporu_pdf_olustur metodu var ise
                    # (Bu metodu da veritabanı.py'ye eklemeniz gerekecek)
                    success, message = self.db.tarihsel_satis_raporu_pdf_olustur(bas_t_str, bit_t_str, file_path)
                else:
                    message = f"'{current_tab_text}' raporu için PDF yazdırma özelliği henüz geliştirilmedi."

                if success:
                    QMessageBox.information(self, "Başarılı", message)
                    self.app.set_status_message(message)
                else:
                    QMessageBox.warning(self, "Bilgi", message)
                    self.app.set_status_message(f"PDF yazdırma iptal edildi/geliştirilmedi: {message}")

            except Exception as e:
                logging.error(f"Raporu PDF olarak yazdırırken beklenmeyen bir hata oluştu: {e}")
                QMessageBox.critical(self, "Kritik Hata", f"Raporu PDF olarak yazdırırken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Hata: Rapor PDF yazdırma - {e}")
        else:
            self.app.set_status_message("PDF kaydetme işlemi iptal edildi.")

    def raporu_excel_aktar(self):
        bas_t_str = self.bas_tarih_entry.text()
        bit_t_str = self.bit_tarih_entry.text()

        if not bas_t_str or not bit_t_str:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen başlangıç ve bitiş tarihi seçin.")
            return

        initial_file_name = f"satis_raporu_{bas_t_str}_{bit_t_str}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self.app,
                                                "Satış Raporunu Excel Olarak Kaydet",
                                                initial_file_name,
                                                "Excel Dosyaları (*.xlsx);;Tüm Dosyalar (*)")

        if file_path:
            from pencereler import BeklemePenceresi
            bekleme_penceresi = BeklemePenceresi(self.app, message="Rapor oluşturuluyor ve indiriliyor, lütfen bekleyiniz...")

            def islem_thread():
                try:
                    success_gen, message_gen, server_filepath = self.db.satis_raporu_excel_olustur_api_den(
                        bas_t_str, bit_t_str
                    )

                    if not success_gen or not server_filepath:
                        raise Exception(f"Rapor oluşturma başarısız: {message_gen}")

                    server_only_filename = os.path.basename(server_filepath)
                    api_download_path = f"/raporlar/download_report/{server_only_filename}"
                    success_download, message_download = self.db.dosya_indir_api_den(api_download_path, file_path)

                    if success_download:
                        self.app.after(0, lambda: QMessageBox.information(self.app, "Başarılı", f"Rapor başarıyla kaydedildi:\n{file_path}"))
                        self.app.after(0, lambda: self.app.set_status_message(f"Rapor başarıyla indirildi: {file_path}"))
                    else:
                        self.app.after(0, lambda: QMessageBox.critical(self.app, "Hata", f"Rapor indirme başarısız:\n{message_download}"))
                        self.app.after(0, lambda: self.app.set_status_message(f"Rapor indirme başarısız: {message_download}"))
                except Exception as e:
                    self.app.after(0, lambda: QMessageBox.critical(self.app, "Rapor Oluşturma Hatası", f"Rapor oluşturulurken veya indirilirken bir hata oluştu:\n{e}"))
                    self.app.after(0, lambda: self.app.set_status_message(f"Rapor oluşturulurken hata: {e}"))
                finally:
                    self.app.after(0, bekleme_penceresi.kapat)

            thread = threading.Thread(target=islem_thread)
            thread.start()
            bekleme_penceresi.exec()
        else:
            self.app.set_status_message("Rapor kaydetme işlemi iptal edildi.")

class GelirGiderSayfasi(QWidget):
    def __init__(self, parent, db_manager, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.app = app_ref # Ana App sınıfına referans
        self.setLayout(QVBoxLayout()) # Ana layout

        self.layout().addWidget(QLabel("Gelir ve Gider İşlemleri", font=QFont("Segoe UI", 16, QFont.Bold)), alignment=Qt.AlignCenter)

        # Ana Notebook (Sekmeli Yapı)
        self.main_notebook = QTabWidget(self) # ttk.Notebook yerine QTabWidget
        self.layout().addWidget(self.main_notebook)

        # Gelir Listesi Sekmesi
        self.gelir_listesi_frame = GelirListesi(self.main_notebook, self.db, self.app)
        self.main_notebook.addTab(self.gelir_listesi_frame, "💰 Gelirler")

        # Gider Listesi Sekmesi
        self.gider_listesi_frame = GiderListesi(self.main_notebook, self.db, self.app)
        self.main_notebook.addTab(self.gider_listesi_frame, "💸 Giderler")

        # Sekme değiştiğinde ilgili formu yenilemek için bir olay bağlayabiliriz
        self.main_notebook.currentChanged.connect(self._on_tab_change) # Yeni metod

    def _on_tab_change(self, index):
        """Sekme değiştiğinde ilgili listeyi yeniler."""
        selected_widget = self.main_notebook.widget(index)
        if hasattr(selected_widget, 'gg_listesini_yukle'):
            selected_widget.gg_listesini_yukle()
        
class GirisEkrani(QDialog):
    login_success = Signal(dict)

    def __init__(self, parent=None, db_manager=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Kullanıcı Girişi")
        self.setFixedSize(350, 250)

        self._main_layout = QVBoxLayout(self)

        self.logo_label = QLabel("Çınar Yapı")
        self.logo_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        self.logo_label.setAlignment(Qt.AlignCenter)
        self._main_layout.addWidget(self.logo_label)

        self._frame = QFrame(self)
        self._frame.setFrameShape(QFrame.StyledPanel)
        self._frame.setLineWidth(1)
        self._main_layout.addWidget(self._frame)

        self._form_layout = QGridLayout(self._frame)

        # KRİTİK DÜZELTME 4: Kullanıcı Adı -> E-posta
        self._form_layout.addWidget(QLabel("E-posta:"), 0, 0)
        self._entry_username = QLineEdit() # Bu, kullanıcının e-postasını tutacak
        self._entry_username.setPlaceholderText("E-posta adresinizi giriniz") # Placeholder eklendi
        self._form_layout.addWidget(self._entry_username, 0, 1)

        self._form_layout.addWidget(QLabel("Şifre:"), 1, 0)
        self._entry_password = QLineEdit()
        self._entry_password.setEchoMode(QLineEdit.Password)
        self._form_layout.addWidget(self._entry_password, 1, 1)

        self._main_layout.addStretch()

        self._btn_login = QPushButton("Giriş Yap")
        self._btn_login.clicked.connect(self._on_login_clicked)

        self._btn_register = QPushButton("Yeni Hesap Oluştur")
        self._btn_register.clicked.connect(self._open_user_registration_window)

        self._button_layout = QHBoxLayout()
        self._button_layout.addStretch()
        self._button_layout.addWidget(self._btn_register)
        self._button_layout.addWidget(self._btn_login)
        self._button_layout.addStretch()

        self._main_layout.addLayout(self._button_layout)
        self._main_layout.addStretch()
        self._main_layout.addStretch()

        # main.py'den last_username değerini yükleyelim
        from main import load_config
        app_config = load_config()
        self._entry_username.setText(app_config.get('last_username', ''))
        self._entry_username.setFocus()

    def get_credentials(self):
        return self._entry_username.text(), self._entry_password.text()

    def _open_user_registration_window(self):
        kayit_penceresi = FirmaKayitPenceresi(self, self.db)
        kayit_penceresi.exec() 

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # İçeriği tutacak ana çerçeve
        content_frame = QFrame(self)
        content_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border-radius: 15px;
            }
        """)
        content_frame.setFrameShape(QFrame.StyledPanel)
        content_frame.setFrameShadow(QFrame.Raised)
        
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(25, 25, 25, 25)
        
        # Başlık
        title_label = QLabel("Çınar Yapı Ön Muhasebe Programı")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title_label)
        content_layout.addSpacing(15)

        # Giriş Formu
        form_layout = QGridLayout()
        form_layout.addWidget(QLabel("Kullanıcı Adı:"), 0, 0)
        self.kullanici_adi_entry = QLineEdit()
        self.kullanici_adi_entry.setPlaceholderText("Kullanıcı adınızı giriniz")
        form_layout.addWidget(self.kullanici_adi_entry, 0, 1)

        form_layout.addWidget(QLabel("Şifre:"), 1, 0)
        self.sifre_entry = QLineEdit()
        self.sifre_entry.setPlaceholderText("Şifrenizi giriniz")
        self.sifre_entry.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(self.sifre_entry, 1, 1)
        content_layout.addLayout(form_layout)
        content_layout.addSpacing(15)

        self.giris_butonu = QPushButton("Giriş")
        self.giris_butonu.setMinimumHeight(35)
        self.giris_butonu.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.giris_butonu.setStyleSheet("background-color: #4CAF50; color: white; border-radius: 5px;")
        self.giris_butonu.clicked.connect(self._on_login_clicked)
        content_layout.addWidget(self.giris_butonu)

        main_layout.addWidget(content_frame)

        from main import load_config
        app_config = load_config()
        self.kullanici_adi_entry.setText(app_config.get('last_username', ''))
        self.kullanici_adi_entry.setFocus()

    def _initial_load_data(self):
        sirket_adi_giris = "Şirket Adınız"
        if self.db.is_online:
            sirket_bilgileri = self.db.sirket_bilgilerini_yukle(self.parent_app.current_user_id) if hasattr(self.parent_app, 'current_user_id') else None
            if sirket_bilgileri:
                sirket_adi_giris = sirket_bilgileri.get("sirket_adi", "Şirket Adınız")
            else:
                sirket_adi_giris = "Şirket Bilgisi Yüklenemedi (Online)"
        else:
            sirket_adi_giris = "Şirket Bilgisi Yüklenemedi (Offline)"
            
        sirket_label_bottom = QLabel(sirket_adi_giris)
        sirket_label_bottom.setFont(QFont("Segoe UI", 10))
        self.layout().addWidget(sirket_label_bottom, alignment=Qt.AlignCenter | Qt.AlignBottom)

    def _on_login_clicked(self):
        # KRİTİK DÜZELTME 5: Kullanıcı Adı yerine E-posta gönderilir
        email = self._entry_username.text()
        sifre = self._entry_password.text()

        if not email or not sifre:
            QMessageBox.warning(self, "Hata", "Lütfen E-posta ve şifre giriniz.")
            return
            
        from main import save_config, load_config
        app_config = load_config()
        app_config['last_username'] = email # Son girilen e-postayı kaydet
        save_config(app_config)

        try:
            # 1. Doğrulama çağrısı (Artık email kullanır)
            result = self.db.kullanici_dogrula(email, sifre)

            # 2. Sonucu Kontrol Et ve Sinyali Gönder
            if isinstance(result, dict) and "kullanici_id" in result:
                self.login_success.emit(result)  
                self.accept()
            else:
                hata_mesaji = "E-posta veya şifre hatalı."
                if isinstance(result, tuple) and len(result) > 1:
                    hata_mesaji = result[1]
                
                QMessageBox.critical(self, "Giriş Hatası", hata_mesaji)
                self._entry_password.clear()
                self._entry_password.setFocus()
                
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Giriş yapılırken bir hata oluştu: {e}")
            self._entry_password.clear()
            self._entry_password.setFocus()

class FirmaKayitPenceresi(QDialog):
    def __init__(self, parent=None, db_manager=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Yeni Firma Hesabı Oluştur")
        self.setMinimumWidth(450)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(15)

        title_label = QLabel("Yeni Firma ve Yönetici Hesabı Oluşturun")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title_label)

        # --- Firma Bilgileri ---
        firma_group = QFrame(self)
        firma_group.setFrameShape(QFrame.StyledPanel)
        firma_layout = QGridLayout(firma_group)
        self.main_layout.addWidget(firma_group)

        firma_layout.addWidget(QLabel("<b>Firma Bilgileri</b>"), 0, 0, 1, 2)
        firma_layout.addWidget(QLabel("Firma Ünvanı (*):"), 1, 0)
        self.firma_unvani_entry = QLineEdit()
        self.firma_unvani_entry.setPlaceholderText("Örn: Çınar İnşaat Malzemeleri Ltd. Şti.")
        firma_layout.addWidget(self.firma_unvani_entry, 1, 1)

        # --- Yönetici Bilgileri ---
        yonetici_group = QFrame(self)
        yonetici_group.setFrameShape(QFrame.StyledPanel)
        yonetici_layout = QGridLayout(yonetici_group)
        self.main_layout.addWidget(yonetici_group)

        yonetici_layout.addWidget(QLabel("<b>Yönetici Bilgileri</b>"), 0, 0, 1, 2)
        yonetici_layout.addWidget(QLabel("Yönetici Adı Soyadı (*):"), 1, 0)
        self.yonetici_ad_soyad_entry = QLineEdit()
        yonetici_layout.addWidget(self.yonetici_ad_soyad_entry, 1, 1)

        yonetici_layout.addWidget(QLabel("Yönetici E-postası (*):"), 2, 0)
        self.yonetici_email_entry = QLineEdit()
        yonetici_layout.addWidget(self.yonetici_email_entry, 2, 1)
        
        yonetici_layout.addWidget(QLabel("Telefon Numarası (*):"), 3, 0)
        self.yonetici_telefon_entry = QLineEdit()
        self.yonetici_telefon_entry.setPlaceholderText("Örn: 5551234567")
        yonetici_layout.addWidget(self.yonetici_telefon_entry, 3, 1)

        yonetici_layout.addWidget(QLabel("Şifre (*):"), 4, 0)
        self.yonetici_sifre_entry = QLineEdit()
        self.yonetici_sifre_entry.setEchoMode(QLineEdit.Password)
        yonetici_layout.addWidget(self.yonetici_sifre_entry, 4, 1)

        yonetici_layout.addWidget(QLabel("Şifre Tekrar (*):"), 5, 0)
        self.yonetici_sifre_tekrar_entry = QLineEdit()
        self.yonetici_sifre_tekrar_entry.setEchoMode(QLineEdit.Password)
        yonetici_layout.addWidget(self.yonetici_sifre_tekrar_entry, 5, 1)

        # --- Butonlar ---
        self.kayit_ol_button = QPushButton("Hesabı Oluştur")
        self.kayit_ol_button.clicked.connect(self._kayit_ol)
        self.main_layout.addWidget(self.kayit_ol_button)

    def _kayit_ol(self):
        firma_unvani = self.firma_unvani_entry.text().strip()
        yonetici_ad_soyad = self.yonetici_ad_soyad_entry.text().strip()
        email = self.yonetici_email_entry.text().strip()
        telefon = self.yonetici_telefon_entry.text().strip()
        sifre = self.yonetici_sifre_entry.text()
        sifre_tekrar = self.yonetici_sifre_tekrar_entry.text()

        if not all([firma_unvani, yonetici_ad_soyad, email, telefon, sifre, sifre_tekrar]):
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen tüm zorunlu (*) alanları doldurun.")
            return

        if sifre != sifre_tekrar:
            QMessageBox.warning(self, "Şifre Hatası", "Girdiğiniz şifreler uyuşmuyor.")
            return

        yeni_firma_data = {
            "firma_unvani": firma_unvani,
            "yonetici_ad_soyad": yonetici_ad_soyad,
            "yonetici_email": email,
            "yonetici_telefon": telefon,
            "yonetici_sifre": sifre
        }

        try:
            success, message = self.db.yeni_firma_olustur(yeni_firma_data)
            
            if success:
                QMessageBox.information(self, "Başarılı", f"Firma hesabı başarıyla oluşturuldu!\n\nE-posta: {email}\n\nLütfen bu bilgilerle giriş yapın.")
                self.accept()
            else:
                QMessageBox.critical(self, "Kayıt Hatası", f"Hesap oluşturulamadı:\n{message}")

        except Exception as e:
            QMessageBox.critical(self, "Kritik Hata", f"Kayıt sırasında beklenmedik bir hata oluştu:\n{e}")

class StokHareketleriSekmesi(QWidget):
    def __init__(self, parent, db_manager, urun_id, urun_adi, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.urun_id = urun_id
        self.urun_adi = urun_adi
        self.app = app_ref
        
        # UI'ı oluştur. Bu, bas_tarih_entry'yi de oluşturmalıdır.
        self._setup_ui() 
        
        # Eğer ID varsa hareketleri yükle
        if self.urun_id:
            self._load_stok_hareketleri()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Filtreleme ve Buton Alanı
        filter_frame = QFrame(self)
        filter_layout = QHBoxLayout(filter_frame)
        main_layout.addWidget(filter_frame)
        
        filter_layout.addWidget(QLabel("Başlangıç Tarihi:"))
        # self.bas_tarih_entry'yi burada tanımlıyoruz
        self.bas_tarih_entry = QLineEdit((datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
        filter_layout.addWidget(self.bas_tarih_entry)
        
        filter_layout.addWidget(QLabel("Bitiş Tarihi:"))
        # self.bitis_tarih_entry'yi burada tanımlıyoruz
        self.bitis_tarih_entry = QLineEdit(datetime.now().strftime('%Y-%m-%d'))
        filter_layout.addWidget(self.bitis_tarih_entry)

        btn_filter = QPushButton("Filtrele")
        btn_filter.clicked.connect(self._load_stok_hareketleri)
        filter_layout.addWidget(btn_filter)
        
        # Ağaç Görünümü Alanı
        self.stok_hareket_tree = QTreeWidget(self) 
        self.stok_hareket_tree.setHeaderLabels(["ID", "Tarih", "İşlem Tipi", "Miktar", "Birim Fiyat", "Açıklama", "Kaynak", "Ref. ID", "Önceki Stok", "Sonraki Stok"])
        self.stok_hareket_tree.setSortingEnabled(True)
        self.stok_hareket_tree.setColumnWidth(0, 50)
        self.stok_hareket_tree.header().setSectionResizeMode(5, QHeaderView.Stretch)
        main_layout.addWidget(self.stok_hareket_tree)

    def _open_stok_hareket_context_menu(self, pos):
        item = self.stok_hareket_tree.itemAt(pos)
        if not item: return
        self.stok_hareket_tree.setCurrentItem(item)
        kaynak_tipi = item.text(7)
        context_menu = QMenu(self)
        if kaynak_tipi in ['MANUEL', 'GİRİŞ_MANUEL', 'ÇIKIŞ_MANUEL', 'SAYIM_FAZLASI', 'SAYIM_EKSİĞİ', 'ZAYİAT', 'İADE_GİRİŞ']:
            delete_action = context_menu.addAction("Stok Hareketini Sil")
            delete_action.triggered.connect(self._secili_stok_hareketini_sil)
        if context_menu.actions():
            context_menu.exec(self.stok_hareket_tree.mapToGlobal(pos))
             
    def _secili_stok_hareketini_sil(self):
        selected_items = self.stok_hareket_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir stok hareketi seçin.")
            return
        item_qt = selected_items[0]
        try:
            hareket_id = int(item_qt.text(0))
            islem_tipi = item_qt.text(2)
            miktar = float(item_qt.text(3).replace(',', '.'))
            kaynak = item_qt.text(7)
        except (ValueError, IndexError):
            QMessageBox.critical(self.app, "Hata", "Seçili hareketin verileri okunamadı.")
            return
        if kaynak not in ['MANUEL', 'GİRİŞ_MANUEL', 'ÇIKIŞ_MANUEL', 'SAYIM_FAZLASI', 'SAYIM_EKSİĞİ', 'ZAYİAT', 'İADE_GİRİŞ']:
            QMessageBox.warning(self.app, "Silme Engellendi", "Sadece manuel kaynaklı stok hareketleri silinebilir.")
            return
        reply = QMessageBox.question(self.app, "Onay", f"'{islem_tipi}' tipindeki {miktar} miktarındaki stok hareketini silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz!", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                success_api, message_api = self.db.stok_hareketini_sil(hareket_id, kullanici_id=self.app.current_user_id)
                if success_api:
                    QMessageBox.information(self.app, "Başarılı", message_api)
                    self._load_stok_hareketleri()
                    if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                        self.app.stok_yonetimi_sayfasi.stok_listesini_yenile()
                    self.app.set_status_message(message_api)
                else:
                    QMessageBox.critical(self.app, "Hata", message_api)
                    self.app.set_status_message(f"Stok hareketi silinirken hata: {message_api}")
            except Exception as e:
                QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Stok hareketi silinirken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Stok hareketi silinirken hata: {e}")
    
    def refresh_data_and_ui(self):
        self._load_stok_hareketleri()

    def _load_stok_hareketleri(self):
        # self.stok_hareket_tree'nin artık _setup_ui içinde oluşturulduğunu varsayıyoruz.
        self.stok_hareket_tree.clear() 
        
        # KRİTİK DÜZELTME: self.urun_id integer olmalı ve bas_tarih_entry var olmalı.
        if not self.urun_id or self.urun_id == 0: return

        try:
            hareketler = self.db.stok_hareketleri_listele(
                stok_id=self.urun_id,
                # self.bas_tarih_entry'nin artık var olduğu varsayılır.
                baslangic_tarihi=self.bas_tarih_entry.text(), 
                bitis_tarihi=self.bitis_tarih_entry.text()
            )

            for hareket in hareketler:
                item = QTreeWidgetItem(self.stok_hareket_tree) 
                item.setText(0, str(hareket.get('id', '-')))
                item.setText(1, hareket.get('tarih', ''))
                item.setText(2, str(hareket.get('islem_tipi', '')))
                item.setText(3, str(hareket.get('miktar', 0.0)))
                item.setText(4, str(hareket.get('birim_fiyat', 0.0)))
                item.setText(5, str(hareket.get('aciklama', '')))
                item.setText(6, str(hareket.get('kaynak', '')))
                item.setText(7, str(hareket.get('kaynak_id', '-')))
                item.setText(8, str(hareket.get('onceki_stok', 0.0)))
                item.setText(9, str(hareket.get('sonraki_stok', 0.0)))

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Stok hareketleri yüklenirken bir hata oluştu:\n{e}")
            logging.error(f"Stok hareketleri yüklenirken hata: {e}", exc_info=True)
            
class IlgiliFaturalarSekmesi(QWidget):
    def __init__(self, parent, db_manager, urun_id, urun_adi, app_ref):
        super().__init__(parent)
        self.db = db_manager
        self.urun_id = urun_id
        self.urun_adi = urun_adi
        self.app = app_ref
        
        self._setup_ui()
        if self.urun_id:
            self._load_ilgili_faturalar()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        filter_frame = QFrame(self)
        filter_layout = QHBoxLayout(filter_frame)
        main_layout.addWidget(filter_frame)

        filter_layout.addWidget(QLabel("Fatura Tipi:"))
        self.fatura_tipi_filter_cb = QComboBox()
        self.fatura_tipi_filter_cb.addItems(["TÜMÜ", "ALIŞ", "SATIŞ"])
        self.fatura_tipi_filter_cb.currentIndexChanged.connect(self._load_ilgili_faturalar)
        filter_layout.addWidget(self.fatura_tipi_filter_cb)
        filter_layout.addStretch()

        self.ilgili_faturalar_tree = QTreeWidget(self)
        self.ilgili_faturalar_tree.setHeaderLabels(["ID", "Fatura No", "Tarih", "Tip", "Cari/Misafir", "KDV Hariç Top.", "KDV Dahil Top."])
        self.ilgili_faturalar_tree.setSortingEnabled(True)
        self.ilgili_faturalar_tree.header().setSectionResizeMode(4, QHeaderView.Stretch)
        main_layout.addWidget(self.ilgili_faturalar_tree)

    def _load_ilgili_faturalar(self):
        self.ilgili_faturalar_tree.clear()
        
        # KRİTİK DÜZELTME: urun_id'yi integer'a çevirme garantisi
        urun_id_int = None
        if self.urun_id:
            try:
                # Gelen ID'yi zorla integer'a çevir
                urun_id_int = int(self.urun_id)
            except (ValueError, TypeError):
                # ID dize ise (örneğin TEST ÜRÜNÜ ADMİN), geçersiz sayılır ve çıkılır.
                return
        
        if urun_id_int is None or urun_id_int == 0: 
            return

        fatura_tipi_filtre = self.fatura_tipi_filter_cb.currentText()
        if fatura_tipi_filtre == "TÜMÜ":
            fatura_tipi_filtre = None

        try:
            # API'ye her zaman INTEGER urun_id_int gönderilir.
            response_data = self.db.get_urun_faturalari(urun_id_int, fatura_tipi_filtre)
            
            faturalar = response_data.get("items", []) if isinstance(response_data, dict) else (response_data if isinstance(response_data, list) else [])
            
            if not faturalar:
                item_qt = QTreeWidgetItem(self.ilgili_faturalar_tree)
                item_qt.setText(3, "Fatura Yok")
                return

            for fatura_item in faturalar:
                item_qt = QTreeWidgetItem(self.ilgili_faturalar_tree)
                fatura_id = fatura_item.get('id')
                fatura_no = fatura_item.get('fatura_no')
                tarih_obj = fatura_item.get('tarih')
                fatura_tip = fatura_item.get('fatura_turu')
                cari_adi = fatura_item.get('cari_adi')
                toplam_kdv_haric = fatura_item.get('toplam_kdv_haric')
                toplam_kdv_dahil = fatura_item.get('toplam_kdv_dahil')
                if isinstance(tarih_obj, (datetime, date)):
                    formatted_tarih = tarih_obj.strftime('%d.%m.%Y')
                else:
                    formatted_tarih = str(tarih_obj or "")
                item_qt = QTreeWidgetItem(self.ilgili_faturalar_tree)
                item_qt.setText(0, str(fatura_id))
                item_qt.setText(1, fatura_no)
                item_qt.setText(2, formatted_tarih)
                item_qt.setText(3, fatura_tip)
                item_qt.setText(4, cari_adi)
                item_qt.setText(5, self.db._format_currency(toplam_kdv_haric))
                item_qt.setText(6, self.db._format_currency(toplam_kdv_dahil))
                item_qt.setData(0, Qt.UserRole, fatura_id)
                item_qt.setData(5, Qt.UserRole, toplam_kdv_haric)
                item_qt.setData(6, Qt.UserRole, toplam_kdv_dahil)
            self.app.set_status_message(f"Ürün '{self.urun_adi}' için {len(faturalar)} fatura listelendi.")
            
        except Exception as e:
            QMessageBox.critical(self.app, "Hata", f"İlgili faturalar yüklenirken hata: {e}")
            logging.error(f"İlgili faturalar yükleme hatası: {e}", exc_info=True)

    def _on_fatura_double_click(self, item, column):
        fatura_id = int(item.text(0))
        if fatura_id:
            from pencereler import FaturaDetayPenceresi
            FaturaDetayPenceresi(self.app, self.db, fatura_id).exec()

class KategoriMarkaYonetimiSekmesi(QWidget): 
    def __init__(self, parent_notebook, db_manager, app_ref):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref
        self.current_user = getattr(self.app, 'current_user', {})
        self.main_layout = QHBoxLayout(self) # Ana layout yatay olacak

        # Sol taraf: Kategori Yönetimi
        kategori_frame = QFrame(self)
        kategori_layout = QGridLayout(kategori_frame)
        self.main_layout.addWidget(kategori_frame)
        kategori_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        kategori_layout.addWidget(QLabel("Kategori Yönetimi", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 5, alignment=Qt.AlignCenter)

        kategori_layout.addWidget(QLabel("Kategori Adı:"), 1, 0, Qt.AlignCenter)
        self.kategori_entry = QLineEdit()
        kategori_layout.addWidget(self.kategori_entry, 1, 1, 1, 1) # Genişlesin
        kategori_layout.setColumnStretch(1, 1) # Entry sütunu genişlesin

        self.ekle_kategori_button = QPushButton("Ekle")
        self.ekle_kategori_button.clicked.connect(self._kategori_ekle_ui)
        kategori_layout.addWidget(self.ekle_kategori_button, 1, 2)

        self.guncelle_kategori_button = QPushButton("Güncelle")
        self.guncelle_kategori_button.clicked.connect(self._kategori_guncelle_ui)
        kategori_layout.addWidget(self.guncelle_kategori_button, 1, 3)

        self.sil_kategori_button = QPushButton("Sil")
        self.sil_kategori_button.clicked.connect(self._kategori_sil_ui)
        kategori_layout.addWidget(self.sil_kategori_button, 1, 4)

        self.kategori_tree = QTreeWidget(kategori_frame)
        self.kategori_tree.setHeaderLabels(["ID", "Kategori Adı"])
        self.kategori_tree.setColumnCount(2)
        self.kategori_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.kategori_tree.setSortingEnabled(True)
        
        self.kategori_tree.setColumnWidth(0, 50)
        self.kategori_tree.header().setSectionResizeMode(0, QHeaderView.Fixed) # ID sabit
        self.kategori_tree.header().setSectionResizeMode(1, QHeaderView.Stretch) # Kategori Adı genişlesin
        self.kategori_tree.headerItem().setFont(0, QFont("Segoe UI", 9, QFont.Bold))
        self.kategori_tree.headerItem().setFont(1, QFont("Segoe UI", 9, QFont.Bold))

        kategori_layout.addWidget(self.kategori_tree, 2, 0, 1, 5) # Row 2, Col 0, span 1 row, 5 cols
        
        self.kategori_tree.itemSelectionChanged.connect(self._on_kategori_select)


        # Sağ taraf: Marka Yönetimi
        marka_frame = QFrame(self)
        marka_layout = QGridLayout(marka_frame)
        self.main_layout.addWidget(marka_frame)
        marka_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        marka_layout.addWidget(QLabel("Marka Yönetimi", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 5, alignment=Qt.AlignCenter)

        marka_layout.addWidget(QLabel("Marka Adı:"), 1, 0, Qt.AlignCenter)
        self.marka_entry = QLineEdit()
        marka_layout.addWidget(self.marka_entry, 1, 1, 1, 1) # Genişlesin
        marka_layout.setColumnStretch(1, 1) # Entry sütunu genişlesin

        self.ekle_marka_button = QPushButton("Ekle")
        self.ekle_marka_button.clicked.connect(self._marka_ekle_ui)
        marka_layout.addWidget(self.ekle_marka_button, 1, 2)

        self.guncelle_marka_button = QPushButton("Güncelle")
        self.guncelle_marka_button.clicked.connect(self._marka_guncelle_ui)
        marka_layout.addWidget(self.guncelle_marka_button, 1, 3)

        self.sil_marka_button = QPushButton("Sil")
        self.sil_marka_button.clicked.connect(self._marka_sil_ui)
        marka_layout.addWidget(self.sil_marka_button, 1, 4)

        self.marka_tree = QTreeWidget(marka_frame)
        self.marka_tree.setHeaderLabels(["ID", "Marka Adı"])
        self.marka_tree.setColumnCount(2)
        self.marka_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.marka_tree.setSortingEnabled(True)

        self.marka_tree.setColumnWidth(0, 50)
        self.marka_tree.header().setSectionResizeMode(0, QHeaderView.Fixed) # ID sabit
        self.marka_tree.header().setSectionResizeMode(1, QHeaderView.Stretch) # Marka Adı genişlesin
        self.marka_tree.headerItem().setFont(0, QFont("Segoe UI", 9, QFont.Bold))
        self.marka_tree.headerItem().setFont(1, QFont("Segoe UI", 9, QFont.Bold))

        marka_layout.addWidget(self.marka_tree, 2, 0, 1, 5) # Row 2, Col 0, span 1 row, 5 cols
        
        self.marka_tree.itemSelectionChanged.connect(self._on_marka_select)

        # İlk yüklemeleri yap
        self._kategori_listesini_yukle()
        self._marka_listesini_yukle()
        self._yetkileri_uygula()
        
    # Kategori Yönetimi Metotları
    def _kategori_listesini_yukle(self):
        self.kategori_tree.clear()
        try:
            kategoriler_response = self.db.kategori_listele(kullanici_id=self.app.current_user_id)
            if isinstance(kategoriler_response, dict) and "items" in kategoriler_response:
                kategoriler = kategoriler_response.get("items", [])
            elif isinstance(kategoriler_response, list):
                kategoriler = kategoriler_response
            else:
                raise ValueError("API'den geçersiz kategori listesi yanıtı alındı.")
            
            for kat in kategoriler:
                kat_id = kat.get('id')
                kat_ad = kat.get('ad')
                item_qt = QTreeWidgetItem(self.kategori_tree)
                item_qt.setText(0, str(kat_id))
                item_qt.setText(1, kat_ad)
                item_qt.setData(0, Qt.UserRole, kat_id)
            self.kategori_tree.sortByColumn(1, Qt.AscendingOrder)
            self.app.set_status_message(f"{len(kategoriler)} kategori listelendi.", "blue")
        except Exception as e:
            QMessageBox.critical(self.app, "API Hatası", f"Kategori listesi çekilirken hata: {e}")
            logging.error(f"Kategori listesi yükleme hatası: {e}", exc_info=True)
        
    def _on_kategori_select(self):
        selected_items = self.kategori_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            kategori_adi = item.text(1)
            self.kategori_entry.setText(kategori_adi)
        else:
            self.kategori_entry.clear()

    def _kategori_ekle_ui(self):
        kategori_adi = self.kategori_entry.text().strip()
        if not kategori_adi:
            QMessageBox.warning(self.app, "Uyarı", "Kategori adı boş olamaz.")
            return

        try:
            data = {"ad": kategori_adi}
            success, message = self.db.nitelik_ekle(nitelik_tipi='kategoriler', data=data, kullanici_id=self.app.current_user_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.kategori_entry.clear()
                self._kategori_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(message, "red")

        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Kategori eklenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Kategori eklenirken hata: {e}", "red")
            logging.error(f"Kategori ekleme hatası: {e}", exc_info=True)
            
    def _kategori_guncelle_ui(self):
        selected_items = self.kategori_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen güncellemek için bir kategori seçin.")
            return

        selected_item = selected_items[0]
        kategori_id = selected_item.data(0, Qt.UserRole)
        yeni_kategori_adi = self.kategori_entry.text().strip()

        if not yeni_kategori_adi:
            QMessageBox.warning(self.app, "Uyarı", "Kategori adı boş olamaz.")
            return
        
        try:
            data = {"ad": yeni_kategori_adi}
            success, message = self.db.nitelik_guncelle(nitelik_tipi='kategoriler', nitelik_id=kategori_id, data=data, kullanici_id=self.app.current_user_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.kategori_entry.clear()
                self._kategori_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(message, "red")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Kategori güncellenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Kategori güncelleme hatası: {e}", "red")
            logging.error(f"Kategori güncelleme hatası: {e}", exc_info=True)

    def _kategori_sil_ui(self):
        selected_items = self.kategori_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir kategori seçin.")
            return

        selected_item = selected_items[0]
        kategori_id = selected_item.data(0, Qt.UserRole)
        kategori_adi = selected_item.text(1)

        reply = QMessageBox.question(self.app, "Onay", f"'{kategori_adi}' kategorisini silmek istediğinizden emin misiniz?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.nitelik_sil(nitelik_tipi='kategoriler', nitelik_id=kategori_id, kullanici_id=self.app.current_user_id)
                if success:
                    QMessageBox.information(self.app, "Başarılı", message)
                    self.kategori_entry.clear()
                    self._kategori_listesini_yukle()
                    if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                        self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self.app, "Hata", message)
                    self.app.set_status_message(message, "red")
            except Exception as e:
                QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Kategori silinirken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Kategori silme hatası: {e}", "red")
                logging.error(f"Kategori silme hatası: {e}", exc_info=True)

    # Marka Yönetimi Metotları
    def _urun_grubu_listesini_yukle(self):
        self.urun_grubu_tree.clear()
        try:
            urun_gruplari_response = self.db.urun_grubu_listele() # API'den gelen tam yanıt
            urun_gruplari_list = urun_gruplari_response

            for grup_item in urun_gruplari_list: # urun_gruplari_list üzerinde döngü
                item_qt = QTreeWidgetItem(self.urun_grubu_tree)
                item_qt.setText(0, str(grup_item.get('id'))) # .get() ile güvenli erişim
                item_qt.setText(1, grup_item.get('ad')) # .get() ile güvenli erişim
                item_qt.setData(0, Qt.UserRole, grup_item.get('id'))
            self.urun_grubu_tree.sortByColumn(1, Qt.AscendingOrder)
        except Exception as e:
            QMessageBox.critical(self.app, "API Hatası", f"Ürün grubu listesi çekilirken hata: {e}")
            logging.error(f"Ürün grubu listesi yükleme hatası: {e}", exc_info=True)

    def _on_marka_select(self):
        selected_items = self.marka_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            marka_adi = item.text(1)
            self.marka_entry.setText(marka_adi)
        else:
            self.marka_entry.clear()

    def _marka_ekle_ui(self):
        marka_adi = self.marka_entry.text().strip()
        if not marka_adi:
            QMessageBox.warning(self.app, "Uyarı", "Marka adı boş olamaz.")
            return

        try:
            data = {"ad": marka_adi}
            success, message = self.db.nitelik_ekle(nitelik_tipi='markalar', data=data, kullanici_id=self.app.current_user_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.marka_entry.clear()
                self._marka_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(message, "red")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Marka eklenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Marka eklenirken hata: {e}", "red")
            logging.error(f"Marka ekleme hatası: {e}", exc_info=True)

    def _yetkileri_uygula(self):
        """Bu sayfadaki butonları kullanıcının rolüne göre ayarlar."""
        kullanici_rolu = self.current_user.get('rol', 'yok')

        if kullanici_rolu.upper() != 'YONETICI':
            # Kategori Butonları
            self.ekle_kategori_button.setEnabled(False)
            self.guncelle_kategori_button.setEnabled(False)
            self.sil_kategori_button.setEnabled(False)
            # Marka Butonları
            self.ekle_marka_button.setEnabled(False)
            self.guncelle_marka_button.setEnabled(False)
            self.sil_marka_button.setEnabled(False)
            print("Kategori/Marka Yönetimi sayfası için personel yetkileri uygulandı.")

    def _marka_guncelle_ui(self):
        selected_items = self.marka_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen güncellemek için bir marka seçin.")
            return

        selected_item = selected_items[0]
        marka_id = selected_item.data(0, Qt.UserRole)
        yeni_marka_adi = self.marka_entry.text().strip()

        if not yeni_marka_adi:
            QMessageBox.warning(self.app, "Uyarı", "Marka adı boş olamaz.")
            return

        try:
            data = {"ad": yeni_marka_adi}
            success, message = self.db.nitelik_guncelle(nitelik_tipi='markalar', nitelik_id=marka_id, data=data, kullanici_id=self.app.current_user_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.marka_entry.clear()
                self._marka_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(message, "red")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Marka güncellenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Marka güncelleme hatası: {e}", "red")
            logging.error(f"Marka güncelleme hatası: {e}", exc_info=True)

    def _marka_sil_ui(self):
        selected_items = self.marka_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir marka seçin.")
            return

        selected_item = selected_items[0]
        marka_id = selected_item.data(0, Qt.UserRole)
        marka_adi = selected_item.text(1)

        reply = QMessageBox.question(self.app, "Onay", f"'{marka_adi}' markasını silmek istediğinizden emin misiniz?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.nitelik_sil(nitelik_tipi='markalar', nitelik_id=marka_id, kullanici_id=self.app.current_user_id)
                if success:
                    QMessageBox.information(self.app, "Başarılı", message)
                    self.marka_entry.clear()
                    self._marka_listesini_yukle()
                    if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                        self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self.app, "Hata", message)
                    self.app.set_status_message(message, "red")
            except Exception as e:
                QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Marka silinirken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Marka silme hatası: {e}", "red")
                logging.error(f"Marka silme hatası: {e}", exc_info=True)

# UrunNitelikYonetimiSekmesi sınıfı (Dönüştürülmüş PySide6 versiyonu)
class UrunNitelikYonetimiSekmesi(QWidget): 
    def __init__(self, parent_notebook, db_manager, app_ref):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref

        self.main_layout = QHBoxLayout(self) # Ana layout yatay olacak

        # Sol taraf: Ürün Grubu Yönetimi
        urun_grubu_frame = QFrame(self)
        urun_grubu_layout = QGridLayout(urun_grubu_frame)
        self.main_layout.addWidget(urun_grubu_frame)
        urun_grubu_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        urun_grubu_layout.addWidget(QLabel("Ürün Grubu Yönetimi", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 5, alignment=Qt.AlignCenter)

        urun_grubu_layout.addWidget(QLabel("Grup Adı:"), 1, 0, Qt.AlignCenter)
        self.urun_grubu_entry = QLineEdit()
        urun_grubu_layout.addWidget(self.urun_grubu_entry, 1, 1, 1, 1)
        urun_grubu_layout.setColumnStretch(1, 1)

        ekle_urun_grubu_button = QPushButton("Ekle")
        ekle_urun_grubu_button.clicked.connect(self._urun_grubu_ekle_ui)
        urun_grubu_layout.addWidget(ekle_urun_grubu_button, 1, 2)

        guncelle_urun_grubu_button = QPushButton("Güncelle")
        guncelle_urun_grubu_button.clicked.connect(self._urun_grubu_guncelle_ui)
        urun_grubu_layout.addWidget(guncelle_urun_grubu_button, 1, 3)

        sil_urun_grubu_button = QPushButton("Sil")
        sil_urun_grubu_button.clicked.connect(self._urun_grubu_sil_ui)
        urun_grubu_layout.addWidget(sil_urun_grubu_button, 1, 4)

        self.urun_grubu_tree = QTreeWidget(urun_grubu_frame)
        self.urun_grubu_tree.setHeaderLabels(["ID", "Grup Adı"])
        self.urun_grubu_tree.setColumnCount(2)
        self.urun_grubu_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.urun_grubu_tree.setSortingEnabled(True)

        self.urun_grubu_tree.setColumnWidth(0, 50)
        self.urun_grubu_tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.urun_grubu_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.urun_grubu_tree.headerItem().setFont(0, QFont("Segoe UI", 9, QFont.Bold))
        self.urun_grubu_tree.headerItem().setFont(1, QFont("Segoe UI", 9, QFont.Bold))

        urun_grubu_layout.addWidget(self.urun_grubu_tree, 2, 0, 1, 5)
        self.urun_grubu_tree.itemSelectionChanged.connect(self._on_urun_grubu_select)


        # Orta taraf: Ürün Birimi Yönetimi
        urun_birimi_frame = QFrame(self)
        urun_birimi_layout = QGridLayout(urun_birimi_frame)
        self.main_layout.addWidget(urun_birimi_frame)
        urun_birimi_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        urun_birimi_layout.addWidget(QLabel("Ürün Birimi Yönetimi", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 5, alignment=Qt.AlignCenter)

        urun_birimi_layout.addWidget(QLabel("Birim Adı:"), 1, 0, Qt.AlignCenter)
        self.urun_birimi_entry = QLineEdit()
        urun_birimi_layout.addWidget(self.urun_birimi_entry, 1, 1, 1, 1)
        urun_birimi_layout.setColumnStretch(1, 1)

        ekle_urun_birimi_button = QPushButton("Ekle")
        ekle_urun_birimi_button.clicked.connect(self._urun_birimi_ekle_ui)
        urun_birimi_layout.addWidget(ekle_urun_birimi_button, 1, 2)

        guncelle_urun_birimi_button = QPushButton("Güncelle")
        guncelle_urun_birimi_button.clicked.connect(self._urun_birimi_guncelle_ui)
        urun_birimi_layout.addWidget(guncelle_urun_birimi_button, 1, 3)

        sil_urun_birimi_button = QPushButton("Sil")
        sil_urun_birimi_button.clicked.connect(self._urun_birimi_sil_ui)
        urun_birimi_layout.addWidget(sil_urun_birimi_button, 1, 4)

        self.urun_birimi_tree = QTreeWidget(urun_birimi_frame)
        self.urun_birimi_tree.setHeaderLabels(["ID", "Birim Adı"])
        self.urun_birimi_tree.setColumnCount(2)
        self.urun_birimi_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.urun_birimi_tree.setSortingEnabled(True)

        self.urun_birimi_tree.setColumnWidth(0, 50)
        self.urun_birimi_tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.urun_birimi_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.urun_birimi_tree.headerItem().setFont(0, QFont("Segoe UI", 9, QFont.Bold))
        self.urun_birimi_tree.headerItem().setFont(1, QFont("Segoe UI", 9, QFont.Bold))

        urun_birimi_layout.addWidget(self.urun_birimi_tree, 2, 0, 1, 5)
        self.urun_birimi_tree.itemSelectionChanged.connect(self._on_urun_birimi_select)


        # Sağ taraf: Ülke Yönetimi
        ulke_frame = QFrame(self)
        ulke_layout = QGridLayout(ulke_frame)
        self.main_layout.addWidget(ulke_frame)
        ulke_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        ulke_layout.addWidget(QLabel("Ülke Yönetimi", font=QFont("Segoe UI", 12, QFont.Bold)), 0, 0, 1, 5, alignment=Qt.AlignCenter)

        ulke_layout.addWidget(QLabel("Ülke Adı:"), 1, 0, Qt.AlignCenter)
        self.ulke_entry = QLineEdit()
        ulke_layout.addWidget(self.ulke_entry, 1, 1, 1, 1)
        ulke_layout.setColumnStretch(1, 1)

        ekle_ulke_button = QPushButton("Ekle")
        ekle_ulke_button.clicked.connect(self._ulke_ekle_ui)
        ulke_layout.addWidget(ekle_ulke_button, 1, 2)

        guncelle_ulke_button = QPushButton("Güncelle")
        guncelle_ulke_button.clicked.connect(self._ulke_guncelle_ui)
        ulke_layout.addWidget(guncelle_ulke_button, 1, 3)

        sil_ulke_button = QPushButton("Sil")
        sil_ulke_button.clicked.connect(self._ulke_sil_ui)
        ulke_layout.addWidget(sil_ulke_button, 1, 4)

        self.ulke_tree = QTreeWidget(ulke_frame)
        self.ulke_tree.setHeaderLabels(["ID", "Ülke Adı"])
        self.ulke_tree.setColumnCount(2)
        self.ulke_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ulke_tree.setSortingEnabled(True)

        self.ulke_tree.setColumnWidth(0, 50)
        self.ulke_tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.ulke_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ulke_tree.headerItem().setFont(0, QFont("Segoe UI", 9, QFont.Bold))
        self.ulke_tree.headerItem().setFont(1, QFont("Segoe UI", 9, QFont.Bold))

        ulke_layout.addWidget(self.ulke_tree, 2, 0, 1, 5)
        self.ulke_tree.itemSelectionChanged.connect(self._on_ulke_select)

        # İlk yüklemeler
        self._urun_grubu_listesini_yukle()
        self._urun_birimi_listesini_yukle()
        self._ulke_listesini_yukle()

    # Ürün Grubu Yönetimi Metotları
    def _urun_grubu_listesini_yukle(self):
        self.urun_grubu_tree.clear()
        try:
            urun_gruplari_response = self.db.urun_grubu_listele() # API'den gelen tam yanıt
            
            if isinstance(urun_gruplari_response, dict) and "items" in urun_gruplari_response:
                urun_gruplari_list = urun_gruplari_response.get("items", [])
            elif isinstance(urun_gruplari_response, list):
                urun_gruplari_list = urun_gruplari_response
            else:
                # KRİTİK DÜZELTME: Hata fırlatma yerine listeyi boşalt ve uyar
                logging.warning(f"Ürün grubu listesi API'den beklenmeyen formatta geldi: {urun_gruplari_response}")
                urun_gruplari_list = [] 
                
            if not urun_gruplari_list and self.db.is_online:
                 self.app.set_status_message("Uyarı: Ürün grubu listesi API'den boş veya hatalı formatta geldi. Yerel veritabanı kullanılıyor olabilir.", "orange")

            for grup_item in urun_gruplari_list: # urun_gruplari_list üzerinde döngü
                item_qt = QTreeWidgetItem(self.urun_grubu_tree)
                item_qt.setText(0, str(grup_item.get('id'))) # .get() ile güvenli erişim
                item_qt.setText(1, grup_item.get('ad')) # .get() ile güvenli erişim
                item_qt.setData(0, Qt.UserRole, grup_item.get('id'))
            self.urun_grubu_tree.sortByColumn(1, Qt.AscendingOrder)
            self.app.set_status_message(f"{len(urun_gruplari_list)} ürün grubu listelendi.", "blue")
        except Exception as e:
            QMessageBox.critical(self.app, "API Hatası", f"Ürün grubu listesi çekilirken hata: {e}")
            logging.error(f"Ürün grubu listesi yükleme hatası: {e}", exc_info=True)

    def _on_urun_grubu_select(self):
        selected_items = self.urun_grubu_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            grup_adi = item.text(1)
            self.urun_grubu_entry.setText(grup_adi)
        else:
            self.urun_grubu_entry.clear()

    def _urun_grubu_ekle_ui(self):
        grup_adi = self.urun_grubu_entry.text().strip()
        if not grup_adi:
            QMessageBox.warning(self.app, "Uyarı", "Grup adı boş olamaz.")
            return

        try:
            data = {"ad": grup_adi}
            success, message = self.db.nitelik_ekle(nitelik_tipi='urun_gruplari', data=data, kullanici_id=self.app.current_user_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.urun_grubu_entry.clear()
                self._urun_grubu_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(message, "red")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Ürün grubu eklenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Ürün grubu eklenirken hata: {e}", "red")
            logging.error(f"Ürün grubu ekleme hatası: {e}", exc_info=True)

    def _urun_grubu_guncelle_ui(self):
        selected_items = self.urun_grubu_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen güncellemek için bir ürün grubu seçin.")
            return

        selected_item = selected_items[0]
        grup_id = selected_item.data(0, Qt.UserRole)
        yeni_grup_adi = self.urun_grubu_entry.text().strip()

        if not yeni_grup_adi:
            QMessageBox.warning(self.app, "Uyarı", "Grup adı boş olamaz.")
            return

        try:
            data = {"ad": yeni_grup_adi}
            success, message = self.db.nitelik_guncelle(nitelik_tipi='urun_gruplari', nitelik_id=grup_id, data=data, kullanici_id=self.app.current_user_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.urun_grubu_entry.clear()
                self._urun_grubu_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(message, "red")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Ürün grubu güncellenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Ürün grubu güncelleme hatası: {e}", "red")
            logging.error(f"Ürün grubu güncelleme hatası: {e}", exc_info=True)

    def _urun_grubu_sil_ui(self):
        selected_items = self.urun_grubu_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir ürün grubu seçin.")
            return

        selected_item = selected_items[0]
        grup_id = selected_item.data(0, Qt.UserRole)
        grup_adi = selected_item.text(1)

        reply = QMessageBox.question(self.app, "Onay", f"'{grup_adi}' ürün grubunu silmek istediğinizden emin misiniz?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.nitelik_sil(nitelik_tipi='urun_gruplari', nitelik_id=grup_id, kullanici_id=self.app.current_user_id)
                if success:
                    QMessageBox.information(self.app, "Başarılı", message)
                    self.urun_grubu_entry.clear()
                    self._urun_grubu_listesini_yukle()
                    if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                        self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self.app, "Hata", message)
                    self.app.set_status_message(message, "red")
            except Exception as e:
                QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Ürün grubu silinirken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Ürün grubu silme hatası: {e}", "red")
                logging.error(f"Ürün grubu silme hatası: {e}", exc_info=True)

    # Ürün Birimi Yönetimi Metotları
    def _urun_birimi_listesini_yukle(self):
        self.urun_birimi_tree.clear()
        try:
            urun_birimleri_response = self.db.urun_birimi_listele(kullanici_id=self.app.current_user_id)
            if isinstance(urun_birimleri_response, dict) and "items" in urun_birimleri_response:
                urun_birimleri = urun_birimleri_response.get("items", [])
            elif isinstance(urun_birimleri_response, list):
                urun_birimleri = urun_birimleri_response
            else:
                # KRİTİK DÜZELTME: Hata fırlatma yerine listeyi boşalt ve uyar
                logging.warning(f"Ürün birimi listesi API'den beklenmeyen formatta geldi: {urun_birimleri_response}")
                urun_birimleri = []

            for birim_item in urun_birimleri:
                item_qt = QTreeWidgetItem(self.urun_birimi_tree)
                item_qt.setText(0, str(birim_item.get('id')))
                item_qt.setText(1, birim_item.get('ad'))
                item_qt.setData(0, Qt.UserRole, birim_item.get('id'))
            self.urun_birimi_tree.sortByColumn(1, Qt.AscendingOrder)
            self.app.set_status_message(f"{len(urun_birimleri)} ürün birimi listelendi.", "blue")
        except Exception as e:
            QMessageBox.critical(self.app, "API Hatası", f"Ürün birimi listesi çekilirken hata: {e}")
            logging.error(f"Ürün birimi listesi yükleme hatası: {e}", exc_info=True)

    def _on_urun_birimi_select(self):
        selected_items = self.urun_birimi_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            birim_adi = item.text(1)
            self.urun_birimi_entry.setText(birim_adi)
        else:
            self.urun_birimi_entry.clear()

    def _urun_birimi_ekle_ui(self):
        birim_adi = self.urun_birimi_entry.text().strip()
        if not birim_adi:
            QMessageBox.warning(self.app, "Uyarı", "Birim adı boş olamaz.")
            return

        try:
            data = {"ad": birim_adi}
            success, message = self.db.nitelik_ekle(nitelik_tipi='urun_birimleri', data=data, kullanici_id=self.app.current_user_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.urun_birimi_entry.clear()
                self._urun_birimi_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(message, "red")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Ürün birimi eklenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Ürün birimi eklenirken hata: {e}", "red")
            logging.error(f"Ürün birimi ekleme hatası: {e}", exc_info=True)

    def _urun_birimi_guncelle_ui(self):
        selected_items = self.urun_birimi_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen güncellemek için bir ürün birimi seçin.")
            return

        selected_item = selected_items[0]
        birim_id = selected_item.data(0, Qt.UserRole)
        yeni_birim_adi = self.urun_birimi_entry.text().strip()

        if not yeni_birim_adi:
            QMessageBox.warning(self.app, "Uyarı", "Birim adı boş olamaz.")
            return

        try:
            data = {"ad": yeni_birim_adi}
            success, message = self.db.nitelik_guncelle(nitelik_tipi='urun_birimleri', nitelik_id=birim_id, data=data, kullanici_id=self.app.current_user_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.urun_birimi_entry.clear()
                self._urun_birimi_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(message, "red")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Ürün birimi güncellenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Ürün birimi güncelleme hatası: {e}", "red")
            logging.error(f"Ürün birimi güncelleme hatası: {e}", exc_info=True)

    def _urun_birimi_sil_ui(self):
        selected_items = self.urun_birimi_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir ürün birimi seçin.")
            return

        selected_item = selected_items[0]
        birim_id = selected_item.data(0, Qt.UserRole)
        birim_adi = selected_item.text(1)

        reply = QMessageBox.question(self.app, "Onay", f"'{birim_adi}' ürün birimini silmek istediğinizden emin misiniz?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.nitelik_sil(nitelik_tipi='urun_birimleri', nitelik_id=birim_id, kullanici_id=self.app.current_user_id)
                if success:
                    QMessageBox.information(self.app, "Başarılı", message)
                    self.urun_birimi_entry.clear()
                    self._urun_birimi_listesini_yukle()
                    if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                        self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self.app, "Hata", message)
                    self.app.set_status_message(message, "red")
            except Exception as e:
                QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Ürün birimi silinirken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Ürün birimi silme hatası: {e}", "red")
                logging.error(f"Ürün birimi silme hatası: {e}", exc_info=True)

    # Ülke Yönetimi Metotları
    def _ulke_listesini_yukle(self):
        self.ulke_tree.clear()
        try:
            ulkeler_response = self.db.ulke_listele(kullanici_id=self.app.current_user_id)
            if isinstance(ulkeler_response, dict) and "items" in ulkeler_response:
                ulkeler = ulkeler_response.get("items", [])
            elif isinstance(ulkeler_response, list):
                ulkeler = ulkeler_response
            else:
                logging.warning(f"Ülke listesi API'den beklenmeyen formatta geldi: {ulkeler_response}")
                ulkeler = []

            for ulke_item in ulkeler:
                item_qt = QTreeWidgetItem(self.ulke_tree)
                item_qt.setText(0, str(ulke_item.get('id')))
                item_qt.setText(1, ulke_item.get('ad'))
                item_qt.setData(0, Qt.UserRole, ulke_item.get('id'))
            self.ulke_tree.sortByColumn(1, Qt.AscendingOrder)
            self.app.set_status_message(f"{len(ulkeler)} ülke listelendi.", "blue")
        except Exception as e:
            QMessageBox.critical(self.app, "API Hatası", f"Ülke listesi çekilirken hata: {e}")
            logging.error(f"Ülke listesi yükleme hatası: {e}", exc_info=True)

    def _on_ulke_select(self):
        selected_items = self.ulke_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            ulke_adi = item.text(1)
            self.ulke_entry.setText(ulke_adi)
        else:
            self.ulke_entry.clear()

    def _ulke_ekle_ui(self):
        ulke_adi = self.ulke_entry.text().strip()
        if not ulke_adi:
            QMessageBox.warning(self.app, "Uyarı", "Ülke adı boş olamaz.")
            return

        try:
            data = {"ad": ulke_adi}
            success, message = self.db.nitelik_ekle(nitelik_tipi='ulkeler', data=data, kullanici_id=self.app.current_user_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.ulke_entry.clear()
                self._ulke_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(message, "red")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Ülke eklenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Ülke eklenirken hata: {e}", "red")
            logging.error(f"Ülke ekleme hatası: {e}", exc_info=True)

    def _ulke_guncelle_ui(self):
        selected_items = self.ulke_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen güncellemek için bir ülke seçin.")
            return

        selected_item = selected_items[0]
        ulke_id = selected_item.data(0, Qt.UserRole)
        yeni_ulke_adi = self.ulke_entry.text().strip()

        if not yeni_ulke_adi:
            QMessageBox.warning(self.app, "Uyarı", "Ülke adı boş olamaz.")
            return

        try:
            data = {"ad": yeni_ulke_adi}
            success, message = self.db.nitelik_guncelle(nitelik_tipi='ulkeler', nitelik_id=ulke_id, data=data, kullanici_id=self.app.current_user_id)
            if success:
                QMessageBox.information(self.app, "Başarılı", message)
                self.ulke_entry.clear()
                self._ulke_listesini_yukle()
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                self.app.set_status_message(message)
            else:
                QMessageBox.critical(self.app, "Hata", message)
                self.app.set_status_message(message, "red")
        except Exception as e:
            QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Ülke güncellenirken beklenmeyen bir hata oluştu:\n{e}")
            self.app.set_status_message(f"Ülke güncelleme hatası: {e}", "red")
            logging.error(f"Ülke güncelleme hatası: {e}", exc_info=True)

    def _ulke_sil_ui(self):
        selected_items = self.ulke_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.app, "Uyarı", "Lütfen silmek için bir ülke seçin.")
            return

        selected_item = selected_items[0]
        ulke_id = selected_item.data(0, Qt.UserRole)
        ulke_adi = selected_item.text(1)

        reply = QMessageBox.question(self.app, "Onay", f"'{ulke_adi}' ülkesini silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success, message = self.db.nitelik_sil(nitelik_tipi='ulkeler', nitelik_id=ulke_id, kullanici_id=self.app.current_user_id)
                if success:
                    QMessageBox.information(self.app, "Başarılı", message)
                    self.ulke_entry.clear()
                    self._ulke_listesini_yukle()
                    if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                        self.app.stok_yonetimi_sayfasi._yukle_filtre_comboboxlari_stok_yonetimi()
                    self.app.set_status_message(message)
                else:
                    QMessageBox.critical(self.app, "Hata", message)
                    self.app.set_status_message(message, "red")
            except Exception as e:
                QMessageBox.critical(self.app, "Beklenmeyen Hata", f"Ülke silinirken beklenmeyen bir hata oluştu:\n{e}")
                self.app.set_status_message(f"Ülke silme hatası: {e}", "red")
                logging.error(f"Ülke silme hatası: {e}", exc_info=True)

class VeriYonetimiSekmesi(QWidget):
    def __init__(self, parent_notebook, db_manager, app_ref):
        super().__init__(parent_notebook)
        self.db = db_manager
        self.app = app_ref
        self.current_user = getattr(self.app, 'current_user', {})        
        self.main_layout = QVBoxLayout(self)

        self.main_layout.addWidget(QLabel("Veri Yönetimi ve Senkronizasyon", font=QFont("Segoe UI", 16, QFont.Bold)), alignment=Qt.AlignCenter)

        button_frame = QFrame(self)
        button_layout = QGridLayout(button_frame)
        self.main_layout.addWidget(button_frame)

        group_sync = QGroupBox("Senkronizasyon ve Veritabanı", self)
        group_sync_layout = QVBoxLayout(group_sync)
        
        self.btn_manuel_sync = QPushButton("Verileri Şimdi Senkronize Et")
        self.btn_manuel_sync.setToolTip("API'den tüm verileri çeker ve yerel veritabanını günceller.")
        group_sync_layout.addWidget(self.btn_manuel_sync)

        self.btn_temizle_db = QPushButton("Yerel Veritabanını Temizle")
        self.btn_temizle_db.setToolTip("Kullanıcılar hariç tüm yerel veritabanı verilerini siler.")
        group_sync_layout.addWidget(self.btn_temizle_db)

        # Yeni Yedekleme ve Geri Yükleme Butonları
        self.btn_yedekle = QPushButton("Veritabanı Yedekle")
        self.btn_yedekle.setToolTip("Uygulamanın veritabanını bir dosyaya yedekler.")
        group_sync_layout.addWidget(self.btn_yedekle)

        self.btn_geri_yukle = QPushButton("Veritabanını Geri Yükle")
        self.btn_geri_yukle.setToolTip("Daha önce alınmış bir yedekten veritabanını geri yükler.")
        group_sync_layout.addWidget(self.btn_geri_yukle)
        
        button_layout.addWidget(group_sync, 0, 0)
        
        group_import = QGroupBox("Toplu Veri İçe Aktarım", self)
        group_import_layout = QVBoxLayout(group_import)

        self.btn_import_stok = QPushButton("Stokları Excel'den İçe Aktar")
        group_import_layout.addWidget(self.btn_import_stok)

        self.btn_import_musteri = QPushButton("Müşterileri Excel'den İçe Aktar")
        group_import_layout.addWidget(self.btn_import_musteri)

        self.btn_import_tedarikci = QPushButton("Tedarikçileri Excel'den İçe Aktar")
        group_import_layout.addWidget(self.btn_import_tedarikci)

        button_layout.addWidget(group_import, 0, 1)

        group_export = QGroupBox("Toplu Veri Dışa Aktarım", self)
        group_export_layout = QVBoxLayout(group_export)

        self.btn_export_stok = QPushButton("Stokları Excel'e Dışa Aktar")
        group_export_layout.addWidget(self.btn_export_stok)

        self.btn_export_musteri = QPushButton("Müşterileri Excel'e Dışa Aktar")
        group_export_layout.addWidget(self.btn_export_musteri)

        self.btn_export_tedarikci = QPushButton("Tedarikçileri Excel'e Dışa Aktar")
        group_export_layout.addWidget(self.btn_export_tedarikci)

        button_layout.addWidget(group_export, 0, 2)
        
        self.btn_manuel_sync.clicked.connect(self._manuel_senkronizasyon_baslat)
        self.btn_temizle_db.clicked.connect(self._yerel_veritabanini_temizle)
        self.btn_import_stok.clicked.connect(lambda: self._toplu_veri_aktarimi_ac("Stok"))
        self.btn_import_musteri.clicked.connect(lambda: self._toplu_veri_aktarimi_ac("Müşteri"))
        self.btn_import_tedarikci.clicked.connect(lambda: self._toplu_veri_aktarimi_ac("Tedarikçi"))
        self.btn_export_stok.clicked.connect(lambda: self._toplu_veri_disa_aktarimi_ac("Stok"))
        self.btn_export_musteri.clicked.connect(lambda: self._toplu_veri_disa_aktarimi_ac("Müşteri"))
        self.btn_export_tedarikci.clicked.connect(lambda: self._toplu_veri_disa_aktarimi_ac("Tedarikçi"))

        # YENİ EKLENEN KOD: Yeni butonların bağlantılarını kur
        self.btn_yedekle.clicked.connect(self._yedekleme_baslat)
        self.btn_geri_yukle.clicked.connect(self._geri_yukleme_baslat)
        
        self.main_layout.addStretch(1)
        self._yetkileri_uygula()
        
    def _yedekleme_baslat(self):
        """
        Veritabanı yedekleme işlemini başlatır.
        """
        if not self.db.is_online:
            QMessageBox.warning(self, "Uyarı", "Veritabanı yedekleme işlemi sadece çevrimiçi modda yapılabilir.")
            self.app.set_status_message("Yedekleme işlemi çevrimdışı modda başlatılamaz.", "orange")
            return
            
        initial_filename = f"onmuhasebe_yedek_{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
        file_path, _ = QFileDialog.getSaveFileName(self, "Veritabanını Yedekle", initial_filename, "Yedek Dosyaları (*.bak);;Tüm Dosyalar (*)")

        if file_path:
            # İşin asıl yükünü App sınıfındaki _yedekle metoduna devrediyoruz.
            self.app._yedekle(file_path=file_path)

    def _geri_yukleme_baslat(self):
        """
        Veritabanı geri yükleme işlemini başlatır.
        """
        if not self.db.is_online:
            QMessageBox.warning(self, "Uyarı", "Veritabanı geri yükleme işlemi sadece çevrimiçi modda yapılabilir.")
            self.app.set_status_message("Geri yükleme işlemi çevrimdışı modda başlatılamaz.", "orange")
            return
            
        file_path, _ = QFileDialog.getOpenFileName(self, "Yedek Dosyası Seç", "", "Yedek Dosyaları (*.bak);;Tüm Dosyalar (*)")

        if file_path:
            reply = QMessageBox.question(self, "Geri Yükleme Onayı",
                                         "Veritabanı geri yüklendiğinde mevcut veriler silinir ve seçtiğiniz yedek dosyası ile değiştirilir. Devam etmek istediğinizden emin misiniz?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                # İşin asıl yükünü App sınıfındaki _geri_yukle metoduna devrediyoruz.
                self.app._geri_yukle(file_path=file_path)

    def _manuel_senkronizasyon_baslat(self):
        self.app.set_status_message("Manuel senkronizasyon başlatıldı...", "blue")
        try:
            # Senkronizasyon işlemini başlat
            success, message = self.db.senkronize_veriler_lokal_db_icin(self.app.current_user_id)
            if success:
                self.app.set_status_message(f"Senkronizasyon tamamlandı: {message}", "green")
                # İlgili UI elementlerini yenile (örneğin: stok, cari listeleri)
                if hasattr(self.app, 'stok_yonetimi_sayfasi'):
                    self.app.stok_yonetimi_sayfasi.stok_listesini_yenile()
                if hasattr(self.app, 'musteri_yonetimi_sayfasi'):
                    self.app.musteri_yonetimi_sayfasi.musteri_listesini_yenile()
                if hasattr(self.app, 'tedarikci_yonetimi_sayfasi'):
                    self.app.tedarikci_yonetimi_sayfasi.tedarikci_listesini_yenile()
            else:
                self.app.set_status_message(f"Senkronizasyon başarısız: {message}", "red")
                QMessageBox.critical(self, "Senkronizasyon Hatası", message)
        except Exception as e:
            self.app.set_status_message(f"Senkronizasyon sırasında beklenmedik bir hata oluştu: {e}", "red")
            logging.error(f"Manuel senkronizasyon hatası: {e}", exc_info=True)

    def _yerel_veritabanini_temizle(self):
        reply = QMessageBox.question(self, "Yerel Veritabanı Temizleme Onayı",
                                     "Bu işlem, kullanıcılar ve varsayılan ayarlar hariç tüm yerel veritabanı verilerini kalıcı olarak silecektir. Devam etmek istediğinizden emin misiniz?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Veritabanı dosyasını sil
                success_delete, message_delete = self.db.temizle_veritabani_dosyasi()
                if not success_delete:
                    raise Exception(message_delete)
                
                # Yeni bir boş veritabanı dosyası oluştur ve tabloları başlat
                self.db.lokal_db.initialize_database()
                
                self.app.set_status_message("Yerel veritabanı başarıyla temizlendi ve yeniden başlatıldı.", "green")
                QMessageBox.information(self, "Başarılı", "Yerel veritabanı başarıyla temizlendi ve yeniden başlatıldı. Lütfen uygulamayı yeniden başlatın.")
                self.app.quit()
                
            except Exception as e:
                self.app.set_status_message(f"Veritabanı temizleme başarısız: {e}", "red")
                QMessageBox.critical(self, "Veritabanı Hatası", f"Yerel veritabanı temizlenirken bir hata oluştu:\n{e}")

    def _toplu_veri_aktarimi_ac(self, islem_tipi):
        from pencereler import BeklemePenceresi

        if islem_tipi == "Stok":
            file_path, _ = QFileDialog.getOpenFileName(self, "Stok Excel Dosyası Seç", "", "Excel Dosyaları (*.xlsx)")
            if file_path:
                bekleme_penceresi = BeklemePenceresi(self.app, message="Stoklar içe aktarılıyor, lütfen bekleyiniz...")

                def import_thread():
                    try:
                        success, message = self.app.toplu_islem_service.stok_excel_aktar(file_path, self.app.current_user_id)
                        if success:
                            self.app.after(0, lambda: QMessageBox.information(self.app, "Başarılı", message))
                            self.app.after(0, self.app.stok_yonetimi_sayfasi.stok_listesini_yenile)
                        else:
                            self.app.after(0, lambda: QMessageBox.critical(self.app, "Hata", message))
                    except Exception as e:
                        self.app.after(0, lambda: QMessageBox.critical(self.app, "Hata", f"Stok içe aktarımı sırasında bir hata oluştu:\n{e}"))
                    finally:
                        self.app.after(0, bekleme_penceresi.kapat)

                thread = threading.Thread(target=import_thread)
                thread.start()
                bekleme_penceresi.exec()
        else:
            QMessageBox.information(self, "Bilgi", f"'{islem_tipi}' toplu veri aktarımı işlevi henüz geliştirilmedi.")
            self.app.set_status_message(f"'{islem_tipi}' toplu veri aktarımı işlevi bekleniyor.", "orange")

    def _toplu_veri_disa_aktarimi_ac(self, islem_tipi):
        QMessageBox.information(self, "Bilgi", f"'{islem_tipi}' toplu veri dışa aktarımı işlevi henüz geliştirilmedi.")
        self.app.set_status_message(f"'{islem_tipi}' toplu veri dışa aktarımı işlevi bekleniyor.", "orange")

    def _yetkileri_uygula(self):
        """Bu sayfadaki tüm butonları kullanıcının rolüne göre ayarlar."""
        kullanici_rolu = self.current_user.get('rol', 'yok')

        # Bu sayfadaki tüm işlemler yöneticiye özeldir.
        is_admin = (kullanici_rolu.upper() == 'YONETICI')
        
        self.btn_manuel_sync.setEnabled(is_admin)
        self.btn_temizle_db.setEnabled(is_admin)
        self.btn_yedekle.setEnabled(is_admin)
        self.btn_geri_yukle.setEnabled(is_admin)
        self.btn_import_stok.setEnabled(is_admin)
        self.btn_import_musteri.setEnabled(is_admin)
        self.btn_import_tedarikci.setEnabled(is_admin)
        self.btn_export_stok.setEnabled(is_admin)
        self.btn_export_musteri.setEnabled(is_admin)
        self.btn_export_tedarikci.setEnabled(is_admin)

        if not is_admin:
            print("Veri Yönetimi sayfası personel için tamamen kısıtlandı.")