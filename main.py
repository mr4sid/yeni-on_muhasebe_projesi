#main.py Dosyasının. Tam içeriği
import sys
import os
import json
import logging  
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QFileDialog,
    QWidget, QMenuBar, QStatusBar, QTabWidget,QDialog, QVBoxLayout
)
from PySide6.QtGui import QAction,QPalette, QColor, QIcon
from PySide6.QtCore import Qt, QDate, Signal, QTimer, QThread, QObject, Slot
import multiprocessing
import threading
# Kendi modüllerimiz
from arayuz import ( # arayuz.py'den tüm gerekli sayfaları içe aktarın
    AnaSayfa, StokYonetimiSayfasi, MusteriYonetimiSayfasi,
    KasaBankaYonetimiSayfasi, FinansalIslemlerSayfasi,
    FaturaListesiSayfasi, SiparisListesiSayfasi,
    GelirGiderSayfasi, RaporlamaMerkeziSayfasi,
    TedarikciYonetimiSayfasi,
    UrunNitelikYonetimiSekmesi, VeriYonetimiSekmesi
)
from veritabani import OnMuhasebe, update_local_user_credentials, authenticate_offline_user 
from hizmetler import FaturaService, TopluIslemService, CariService, lokal_db_servisi 
from raporlar import Raporlama
# Logger kurulumu
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Veri dizini oluşturma (mevcutsa atla)
_data_dir = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(_data_dir, exist_ok=True)

# Config dosyasını yükle veya oluştur
_config_path = os.path.join(_data_dir, 'config.json')

def load_config():
    """Uygulama yapılandırmasını yükler."""
    from config import API_BASE_URL as DEFAULT_API_URL_FROM_MODULE
    from PySide6.QtWidgets import QMessageBox

    config_data = {
        "api_base_url": DEFAULT_API_URL_FROM_MODULE,
        "last_username": ""
    }
    if os.path.exists(_config_path):
        try:
            with open(_config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                config_data.update(loaded_config)
        except json.JSONDecodeError:
            # Kullanıcıya bir QMessageBox ile uyarı ver
            QMessageBox.critical(None, "Yapılandırma Hatası", 
                                 f"Hatalı config.json dosyası: {_config_path}. Uygulama varsayılan ayarları kullanacaktır.")
            logger.error(f"Hatalı config.json dosyası: {_config_path}. Varsayılan yapılandırma kullanılıyor.")
    return config_data

def save_config(config):
    """Uygulama yapılandırmasını kaydeder."""
    try:
        with open(_config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except IOError as e:
        logger.error(f"Config dosyası kaydedilirken hata oluştu: {e}")

class BackupWorker(QObject):
    is_finished = Signal(bool, str, str)

    def __init__(self, db_manager, file_path):
        super().__init__()
        self.db_manager = db_manager

    @Slot()
    def run(self):
        success, message, created_file_path = False, "Bilinmeyen bir hata oluştu.", None
        try:
            success, message, created_file_path = self.db_manager.database_backup(self.file_path)
        except Exception as e:
            message = f"Yedekleme sırasında beklenmedik bir hata oluştu: {e}"
            logger.error(message, exc_info=True)
        finally:
            self.is_finished.emit(success, message, created_file_path)

class RestoreWorker(QObject):
    is_finished = Signal(bool, str)

    def __init__(self, db_manager, file_path):
        super().__init__()
        self.db_manager = db_manager
        self.file_path = file_path

    @Slot()
    def run(self):
        success, message = False, "Bilinmeyen bir hata oluştu."
        try:
            success, message, _ = self.db_manager.database_restore(self.file_path)
        except Exception as e:
            message = f"Geri yükleme sırasında beklenmedik bir hata oluştu: {e}"
            logger.error(message, exc_info=True)
        finally:
            self.is_finished.emit(success, message)

class SyncWorker(QObject):
    is_finished = Signal(bool, str)

    def __init__(self, db_manager, kullanici_id):
        super().__init__()
        self.db_manager = db_manager
        self.kullanici_id = kullanici_id

    @Slot()
    def run(self):
        success, message = False, "Bilinmeyen bir hata oluştu."
        try:
            success, message = self.db_manager.senkronize_veriler_lokal_db_icin(self.kullanici_id)
        except Exception as e:
            message = f"Senkronizasyon sırasında beklenmedik bir hata oluştu: {e}"
            logger.error(message, exc_info=True)
        finally:
            self.is_finished.emit(success, message)

class Ui_MainWindow_Minimal:
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1200, 800)

        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)

        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        # --- QAction'ları (Menü Öğeleri) tanımlama ---
        MainWindow.actionStok_Kart = QAction(MainWindow)
        MainWindow.actionStok_Kart.setObjectName("actionStok_Kart")
        MainWindow.actionStok_Kart.setText("Stok Kartı")

        MainWindow.actionM_teri_Kart = QAction(MainWindow)
        MainWindow.actionM_teri_Kart.setObjectName("actionM_teri_Kart")
        MainWindow.actionM_teri_Kart.setText("Müşteri Kartı")
        
        MainWindow.actionTedarik_i_Kart = QAction(MainWindow)
        MainWindow.actionTedarik_i_Kart.setObjectName("actionTedarik_i_Kart")
        MainWindow.actionTedarik_i_Kart.setText("Tedarikçi Kartı")

        MainWindow.actionKasa_Banka_Kart = QAction(MainWindow)
        MainWindow.actionKasa_Banka_Kart.setObjectName("actionKasa_Banka_Kart")
        MainWindow.actionKasa_Banka_Kart.setText("Kasa/Banka Kartı")

        MainWindow.actionGelir_Gider_Kart = QAction(MainWindow)
        MainWindow.actionGelir_Gider_Kart.setObjectName("actionGelir_Gider_Kart")
        MainWindow.actionGelir_Gider_Kart.setText("Gelir/Gider Kartı")

        MainWindow.actionFatura_Kart = QAction(MainWindow)
        MainWindow.actionFatura_Kart.setObjectName("actionFatura_Kart")
        MainWindow.actionFatura_Kart.setText("Fatura Kartı")

        MainWindow.action_rsiparis = QAction(MainWindow)
        MainWindow.action_rsiparis.setObjectName("action_rsiparis")
        MainWindow.action_rsiparis.setText("Sipariş Kartı")

        MainWindow.actionCari_Hareketler = QAction(MainWindow)
        MainWindow.actionCari_Hareketler.setObjectName("actionCari_Hareketler")
        MainWindow.actionCari_Hareketler.setText("Cari Hareketler")

        MainWindow.actionNitelik_Y_netimi = QAction(MainWindow)
        MainWindow.actionNitelik_Y_netimi.setObjectName("actionNitelik_Y_netimi")
        MainWindow.actionNitelik_Y_netimi.setText("Nitelik Yönetimi")

        MainWindow.actionToplu_Veri_Aktar_m = QAction(MainWindow)
        MainWindow.actionToplu_Veri_Aktar_m.setObjectName("actionToplu_Veri_Aktar_m")
        MainWindow.actionToplu_Veri_Aktar_m.setText("Toplu Veri Aktarımı")
        
        # Raporlar Menüsü Action'ları
        MainWindow.actionM_teri_Raporu = QAction(MainWindow)
        MainWindow.actionM_teri_Raporu.setObjectName("actionM_teri_Raporu")
        MainWindow.actionM_teri_Raporu.setText("Müşteri Raporu")

        MainWindow.actionTedarik_i_Raporu = QAction(MainWindow)
        MainWindow.actionTedarik_i_Raporu.setObjectName("actionTedarik_i_Raporu")
        MainWindow.actionTedarik_i_Raporu.setText("Tedarikçi Raporu")

        MainWindow.actionStok_Raporu = QAction(MainWindow)
        MainWindow.actionStok_Raporu.setObjectName("actionStok_Raporu")
        MainWindow.actionStok_Raporu.setText("Stok Raporu")

        MainWindow.actionFatura_Raporu = QAction(MainWindow)
        MainWindow.actionFatura_Raporu.setObjectName("actionFatura_Raporu")
        MainWindow.actionFatura_Raporu.setText("Fatura Raporu")

        MainWindow.actionKasa_Banka_Raporu = QAction(MainWindow)
        MainWindow.actionKasa_Banka_Raporu.setObjectName("actionKasa_Banka_Raporu")
        MainWindow.actionKasa_Banka_Raporu.setText("Kasa/Banka Raporu")

        MainWindow.actionGelir_Gider_Raporu = QAction(MainWindow)
        MainWindow.actionGelir_Gider_Raporu.setObjectName("actionGelir_Gider_Raporu")
        MainWindow.actionGelir_Gider_Raporu.setText("Gelir/Gider Raporu")

        MainWindow.actionCari_Hareket_Raporu = QAction(MainWindow)
        MainWindow.actionCari_Hareket_Raporu.setObjectName("actionCari_Hareket_Raporu")
        MainWindow.actionCari_Hareket_Raporu.setText("Cari Hareket Raporu")

        MainWindow.actionSiparis_Raporu = QAction(MainWindow)
        MainWindow.actionSiparis_Raporu.setObjectName("actionSiparis_Raporu")
        MainWindow.actionSiparis_Raporu.setText("Sipariş Raporu")

        MainWindow.actionNitelik_Raporu = QAction(MainWindow)
        MainWindow.actionNitelik_Raporu.setObjectName("actionNitelik_Raporu")
        MainWindow.actionNitelik_Raporu.setText("Nitelik Raporu")

        # Veritabanı Menüsü Action'ları
        MainWindow.actionYedekle = QAction(MainWindow)
        MainWindow.actionYedekle.setObjectName("actionYedekle")
        MainWindow.actionYedekle.setText("Yedekle")

        MainWindow.actionGeri_Y_kle = QAction(MainWindow)
        MainWindow.actionGeri_Y_kle.setObjectName("actionGeri_Y_kle")
        MainWindow.actionGeri_Y_kle.setText("Geri Yükle")

        MainWindow.actionAPI_Ayarlar = QAction(MainWindow)
        MainWindow.actionAPI_Ayarlar.setObjectName("actionAPI_Ayarlar")
        MainWindow.actionAPI_Ayarlar.setText("API Ayarları")

        MainWindow.actionY_netici_Ayarlar = QAction(MainWindow)
        MainWindow.actionY_netici_Ayarlar.setObjectName("actionY_netici_Ayarlar")
        MainWindow.actionY_netici_Ayarlar.setText("Yönetici Ayarları")
        
        MainWindow.actionVeri_Yonetimi = QAction(MainWindow)
        MainWindow.actionVeri_Yonetimi.setObjectName("actionVeri_Yonetimi")
        MainWindow.actionVeri_Yonetimi.setText("Veri Yönetimi")

        # Menüleri oluşturma ve Action'ları ekleme
        self.menuKartlar = self.menubar.addMenu("Kartlar")
        self.menuKartlar.addAction(MainWindow.actionStok_Kart)
        self.menuKartlar.addAction(MainWindow.actionM_teri_Kart)
        self.menuKartlar.addAction(MainWindow.actionTedarik_i_Kart)
        self.menuKartlar.addAction(MainWindow.actionKasa_Banka_Kart)
        self.menuKartlar.addAction(MainWindow.actionGelir_Gider_Kart)
        self.menuKartlar.addAction(MainWindow.actionFatura_Kart)
        self.menuKartlar.addAction(MainWindow.action_rsiparis)
        self.menuKartlar.addAction(MainWindow.actionCari_Hareketler)
        self.menuKartlar.addAction(MainWindow.actionNitelik_Y_netimi)
        self.menuKartlar.addAction(MainWindow.actionToplu_Veri_Aktar_m)

        self.menuRaporlar = self.menubar.addMenu("Raporlar")
        self.menuRaporlar.addAction(MainWindow.actionM_teri_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionTedarik_i_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionStok_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionFatura_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionKasa_Banka_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionGelir_Gider_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionCari_Hareket_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionSiparis_Raporu)
        self.menuRaporlar.addAction(MainWindow.actionNitelik_Raporu)

        self.menuAyarlar = self.menubar.addMenu("Ayarlar")
        self.menuAyarlar.addAction(MainWindow.actionYedekle)
        self.menuAyarlar.addAction(MainWindow.actionGeri_Y_kle)
        self.menuAyarlar.addAction(MainWindow.actionAPI_Ayarlar)
        self.menuAyarlar.addAction(MainWindow.actionY_netici_Ayarlar)
        self.menuAyarlar.addAction(MainWindow.actionVeri_Yonetimi)

class App(QMainWindow):
    def __init__(self, current_user: dict):
        super().__init__()
        self.current_user = current_user
        self.current_user_id = current_user.get("kullanici_id") or current_user.get("id")
        
        self.ui_main_window_setup = Ui_MainWindow_Minimal()
        self.ui_main_window_setup.setupUi(self)

        self.setWindowTitle("Çınar Yapı Ön Muhasebe Programı")
        self.config = load_config()

        self.db_manager = None
        self.is_online = False
        self._initialize_db_manager()

        if self.db_manager:
            self.db_manager.current_user_id = self.current_user_id

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tab_widget)

        self.tab_instances = {}
        self.tab_map = {
            "Stok Yönetimi": StokYonetimiSayfasi,
            "Müşteri Yönetimi": MusteriYonetimiSayfasi,
            "Tedarikçi Yönetimi": TedarikciYonetimiSayfasi,
            "Faturalar": FaturaListesiSayfasi,
            "Sipariş Yönetimi": SiparisListesiSayfasi,
            "Kasa/Banka": KasaBankaYonetimiSayfasi,
            "Finansal İşlemler": FinansalIslemlerSayfasi,
            "Gelir/Gider": GelirGiderSayfasi,
            "Raporlama Merkezi": RaporlamaMerkeziSayfasi,
            "Nitelik Yönetimi": UrunNitelikYonetimiSekmesi
        }

        self.open_cari_ekstre_windows = {}

        self._setup_ui_connections()
        self.yetkileri_uygula()
        self._update_status_bar()
        self.set_status_message("Uygulama başlatılıyor...")

        # --- DÜZELTME: Ana Sayfa widget'ını bir özelliğe atıyoruz ---
        # show_tab fonksiyonu AnaSayfa widget'ını oluşturup döndürecek şekilde güncellendi.
        self.ana_sayfa_widget = self.show_tab("Ana Sayfa") 
        # --- DÜZELTME SONU ---

    def _setup_ui_elements(self):
        """Kullanıcı girişi başarılı olduktan sonra arayüz elemanlarını oluşturur."""
        self.ana_sayfa_widget = AnaSayfa(self, self.db_manager, self)
        self.tab_widget.addTab(self.ana_sayfa_widget, "Ana Sayfa")

        self.stok_yonetimi_sayfasi = StokYonetimiSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.stok_yonetimi_sayfasi, "Stok Yönetimi")

        self.musteri_yonetimi_sayfasi = MusteriYonetimiSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.musteri_yonetimi_sayfasi, "Müşteri Yönetimi")

        self.tedarikci_yonetimi_sayfasi = TedarikciYonetimiSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.tedarikci_yonetimi_sayfasi, "Tedarikçi Yönetimi")

        self.fatura_listesi_sayfasi = FaturaListesiSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.fatura_listesi_sayfasi, "Faturalar")

        self.siparis_listesi_sayfasi = SiparisListesiSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.siparis_listesi_sayfasi, "Sipariş Yönetimi")
        
        self.kasa_banka_yonetimi_sayfasi = KasaBankaYonetimiSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.kasa_banka_yonetimi_sayfasi, "Kasa/Banka")

        self.finansal_islemler_sayfasi = FinansalIslemlerSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.finansal_islemler_sayfasi, "Finansal İşlemler")

        self.gelir_gider_sayfasi = GelirGiderSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.gelir_gider_sayfasi, "Gelir/Gider")

        self.raporlama_merkezi_sayfasi = RaporlamaMerkeziSayfasi(self, self.db_manager, self)
        self.tab_widget.addTab(self.raporlama_merkezi_sayfasi, "Raporlama Merkezi")
        
        self.urun_nitelik_yonetimi_sekmesi = UrunNitelikYonetimiSekmesi(self, self.db_manager, self)
        self.tab_widget.addTab(self.urun_nitelik_yonetimi_sekmesi, "Nitelik Yönetimi")
        
        self.fatura_service = FaturaService(self.db_manager)
        self.toplu_islem_service = TopluIslemService(self.db_manager)
        self.cari_service = CariService(self.db_manager)

    def _start_background_sync(self):
        self.sync_thread = QThread()
        # DÜZELTME: SyncWorker, kullanıcı kimliği parametresi ile başlatıldı.
        self.sync_worker = SyncWorker(self.db_manager, self.current_user_id)
        self.sync_worker.moveToThread(self.sync_thread)

        self.sync_thread.started.connect(self.sync_worker.run)
        self.sync_worker.is_finished.connect(self.sync_thread.quit)
        self.sync_worker.is_finished.connect(self.sync_worker.deleteLater)
        self.sync_thread.finished.connect(self.sync_thread.deleteLater)
        self.sync_worker.is_finished.connect(self._handle_sync_completion)

        self.set_status_message("Veriler güncelleniyor, lütfen bekleyiniz...")
        self.sync_thread.start()

    def _handle_sync_completion(self, success, message):
        """Senkronizasyon tamamlandığında çağrılır."""
        if success:
            final_message = f"Senkronizasyon başarıyla tamamlandı. {message}"
            self.set_status_message(final_message, "green")
            self._initial_load_data() 
        else:
            final_message = f"Senkronizasyon işlemi tamamlanamadı: {message}"
            self.set_status_message(final_message, "red")

    def register_cari_ekstre_window(self, window_instance):
        """Açık olan cari ekstre pencerelerini takip eder."""
        window_id = id(window_instance)
        self.open_cari_ekstre_windows[window_id] = window_instance
        logger.info(f"Yeni cari ekstre penceresi kaydedildi. Toplam açık: {len(self.open_cari_ekstre_windows)}")

    def unregister_cari_ekstre_window(self, window_instance):
        """Kapanan cari ekstre pencerelerini listeden çıkarır."""
        window_id = id(window_instance)
        if window_id in self.open_cari_ekstre_windows:
            del self.open_cari_ekstre_windows[window_id]
            logger.info(f"Cari ekstre penceresi kaydı silindi. Toplam açık: {len(self.open_cari_ekstre_windows)}")

    def _open_dialog_with_callback(self, dialog_class_path: str, refresh_callback=None, **kwargs):
        """
        Diyalog pencerelerini dinamik olarak açmak için genel bir metot.
        
        Args:
            dialog_class_path (str): Açılacak diyalog sınıfının 'modül.sınıf_adı' formatında yolu.
            refresh_callback (callable, optional): Diyalog kabul edildiğinde çağrılacak fonksiyon.
            **kwargs: Diyalog sınıfının __init__ metoduna gönderilecek ekstra anahtar argümanlar.
        """
        try:
            # Modülü ve sınıfı dinamik olarak içe aktar
            module_name, class_name = dialog_class_path.rsplit('.', 1)
            module = __import__(module_name, fromlist=[class_name])
            DialogClass = getattr(module, class_name)
            
            # Diyalog nesnesini oluştur
            dialog_instance = DialogClass(
                parent=self,
                db_manager=self.db_manager,
                app_ref=self,
                yenile_callback=refresh_callback,
                **kwargs
            )
            
            # Diyaloğu göster ve sonuç başarılıysa callback'i çağır
            if dialog_instance.exec() == QDialog.Accepted and refresh_callback:
                refresh_callback()
                
        except (ImportError, AttributeError) as e:
            QMessageBox.critical(self, "Hata", f"Pencere sınıfı bulunamadı: {e}")
            logger.error(f"Pencere sınıfı içe aktarma hatası: {e}", exc_info=True)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Pencere açılırken bir hata oluştu:\n{e}")
            logger.error(f"Pencere açma hatası: {e}", exc_info=True)

    def show_tab(self, tab_name: str):
        """
        Sekmeyi açar ve oluşturulan widget'ı geri döndürür. Lazy Loading uygular.
        """
        if tab_name in self.tab_instances:
            widget = self.tab_instances[tab_name]
            index = self.tab_widget.indexOf(widget)
            if index != -1:
                self.tab_widget.setCurrentIndex(index)
                return widget # Mevcut widget'ı döndür

        if tab_name == "Ana Sayfa":
            widget = AnaSayfa(self, self.db_manager, self)
        elif tab_name in self.tab_map:
            WidgetClass = self.tab_map[tab_name]
            widget = WidgetClass(self, self.db_manager, self)
        else:
            QMessageBox.warning(self, "Hata", f"'{tab_name}' sayfası bulunamadı.")
            return None

        index = self.tab_widget.addTab(widget, tab_name)
        self.tab_instances[tab_name] = widget
        self.tab_widget.setCurrentIndex(index)
        logger.info(f"Sekme '{tab_name}' oluşturuldu ve açıldı.")
        return widget # Yeni oluşturulan widget'ı döndür

    def close_tab(self, index):
        """Kullanıcının kapattığı sekmeyi yönetir."""
        widget = self.tab_widget.widget(index)
        if widget:
            tab_name = self.tab_widget.tabText(index)
            # Ana Sayfa'nın kapatılmasını engelle
            if tab_name == "Ana Sayfa":
                return
            
            # Sekmeyi ve referanslarını temizle
            self.tab_widget.removeTab(index)
            if tab_name in self.tab_instances:
                del self.tab_instances[tab_name]
            widget.deleteLater() # Bellekten güvenli bir şekilde sil
            logger.info(f"Sekme '{tab_name}' kapatıldı.")

    def show_invoice_form(self, fatura_tipi, duzenleme_id=None, initial_data=None):
        """Fatura oluşturma/düzenleme penceresini açar."""
        from pencereler import FaturaGuncellemePenceresi
        from arayuz import FaturaOlusturmaSayfasi

        if duzenleme_id:
            pencere = FaturaGuncellemePenceresi(
                parent=self,
                db_manager=self.db_manager,
                fatura_id_duzenle=duzenleme_id,
                yenile_callback_liste=self.fatura_listesi_sayfasi.fatura_listesini_yukle
            )
            pencere.exec()
        else:
            pencere = QDialog(self)
            pencere.setWindowTitle("Yeni Satış Faturası" if fatura_tipi == self.db_manager.FATURA_TIP_SATIS else "Yeni Alış Faturası")
            pencere.setWindowState(Qt.WindowMaximized)
            pencere.setModal(True)

            dialog_layout = QVBoxLayout(pencere)
            fatura_form = FaturaOlusturmaSayfasi(
                pencere,
                self.db_manager,
                self,
                fatura_tipi,
                yenile_callback=self.fatura_listesi_sayfasi.fatura_listesini_yukle,
                initial_data=initial_data
            )
            dialog_layout.addWidget(fatura_form)
            
            fatura_form.saved_successfully.connect(pencere.accept)
            fatura_form.cancelled_successfully.connect(pencere.reject)
            
            pencere.exec()
        logger.info(f"Fatura penceresi açıldı. Tip: {fatura_tipi}, ID: {duzenleme_id}")

    def set_status_message(self, message, color="black"):
        """Durum çubuğuna mesaj yazar ve rengini ayarlar."""
        self.statusBar().setStyleSheet(f"QStatusBar {{ color: {color}; }}")
        self.statusBar().showMessage(message)
        logger.info(f"Durum Mesajı ({color}): {message}")

    def _stok_karti_penceresi_ac(self, urun_data):
        """
        Stok Kartı penceresini açar.
        Bu metod, StokYonetimiSayfasi tarafından düzenleme modunda çağrılır.
        """
        from pencereler import StokKartiPenceresi
        dialog = StokKartiPenceresi(
            self.tab_widget, 
            
            self.db_manager, # <<< KRİTİK DÜZELTME: self.db yerine self.db_manager kullanıldı
            self.stok_yonetimi_sayfasi.stok_listesini_yenile,
            urun_duzenle=urun_data,
            app_ref=self
        )
        dialog.exec()
        
    def show_order_form(self, siparis_tipi, siparis_id_duzenle=None, initial_data=None):
        """Sipariş oluşturma/düzenleme penceresini açar."""
        from pencereler import SiparisPenceresi
        self.siparis_penceresi = SiparisPenceresi(
            self,
            self.db_manager,
            self,
            siparis_tipi=siparis_tipi,
            siparis_id_duzenle=siparis_id_duzenle,
            yenile_callback=self._initial_load_data,
            initial_data=initial_data
        )
        self.siparis_penceresi.show()
        logger.info(f"Sipariş penceresi açıldı. Tip: {siparis_tipi}, ID: {siparis_id_duzenle}")

    # --- App Sınıfının Metodları ---
    def _initialize_db_manager(self):
        """
        OnMuhasebe yöneticisini başlatır.
        API bağlantısı başarısız olursa uygulamayı durdurmaz, çevrimdışı moda geçer.
        """
        try:
            # API bağlantısını test ediyoruz.
            # Veritabanı yöneticisi içinde sadece API bağlantısını test eden bir metot eklemek daha mantıklı olabilir.
            # Şimdilik, doğrudan OnMuhasebe'yi API URL'si ile başlatıyoruz ve hatayı yakalıyoruz.
            self.db_manager = OnMuhasebe(api_base_url=self.config["api_base_url"])
            self.is_online = True
            logger.info("Veritabanı yöneticisi API modu ile başarıyla başlatıldı.")
            self.set_status_message("API bağlantısı başarılı.", "green")

        except ConnectionError as e:
            QMessageBox.warning(self, "API Bağlantı Hatası",
                                f"API'ye bağlanılamadı: {e}\n"
                                "Uygulama çevrimdışı (offline) modda başlatılacaktır. Veri senkronizasyonu yapılamayacaktır.")
            logger.critical(f"Uygulama başlatılırken API bağlantı hatası: {e}. Offline moda geçiliyor.")
            self.db_manager = OnMuhasebe(api_base_url=None) # API URL'si olmadan başlat
            self.is_online = False
            self.set_status_message("Çevrimdışı mod: API bağlantısı yok. Yerel veriler kullanılıyor.", "orange")
        except Exception as e:
            QMessageBox.critical(self, "Uygulama Başlatma Hatası",  
                                 f"Veritabanı yöneticisi başlatılırken beklenmeyen bir hata oluştu: {e}\n"
                                 "Uygulama kapanacak.")
            logger.critical(f"Uygulama başlatılırken beklenmeyen hata: {e}")
            sys.exit(1)

    def _setup_ui_connections(self):
        # Bu metod, menü öğelerini ilgili metotlara bağlar.
        # Menü öğelerine App sınıfı içinden doğru bir şekilde erişilir.
        self.actionStok_Kart.triggered.connect(lambda: self.show_tab("Stok Yönetimi"))
        self.actionM_teri_Kart.triggered.connect(lambda: self.show_tab("Müşteri Yönetimi"))
        self.actionTedarik_i_Kart.triggered.connect(lambda: self.show_tab("Tedarikçi Yönetimi"))
        self.actionKasa_Banka_Kart.triggered.connect(lambda: self.show_tab("Kasa/Banka"))
        self.actionGelir_Gider_Kart.triggered.connect(lambda: self.show_tab("Gelir/Gider"))
        self.actionFatura_Kart.triggered.connect(lambda: self.show_tab("Faturalar"))
        self.action_rsiparis.triggered.connect(lambda: self.show_tab("Sipariş Yönetimi"))
        self.actionNitelik_Y_netimi.triggered.connect(lambda: self.show_tab("Nitelik Yönetimi"))
        self.actionToplu_Veri_Aktar_m.triggered.connect(self._toplu_veri_aktarim_penceresi_ac)
        
        self.actionM_teri_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionTedarik_i_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionStok_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionFatura_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionKasa_Banka_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionGelir_Gider_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionCari_Hareket_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionSiparis_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        self.actionNitelik_Raporu.triggered.connect(lambda: self.show_tab("Raporlama Merkezi"))
        
        self.actionYedekle.triggered.connect(self._yedekle)
        self.actionGeri_Y_kle.triggered.connect(self._geri_yukle)
        self.actionVeri_Yonetimi.triggered.connect(self._veri_yonetimi_penceresi_ac)
        self.actionY_netici_Ayarlar.triggered.connect(self._yonetici_ayarlari_penceresi_ac)
        self.actionAPI_Ayarlar.triggered.connect(self._api_ayarlari_penceresi_ac)

    def _initial_load_data(self): 
        """
        Sadece o an açık olan sekmelerdeki verileri günceller.
        Lazy Loading ile uyumlu hale getirildi.
        """
        if not self.db_manager:
            return

        # Ana sayfa her zaman açık olduğu için onu güvenle güncelleyebiliriz.
        if self.ana_sayfa_widget:
            self.ana_sayfa_widget.guncelle_ozet_bilgiler()

        # Diğer sekmeleri, sadece eğer oluşturulmuşlarsa (açıklarsa) güncelle.
        for tab_name, widget in self.tab_instances.items():
            if hasattr(widget, 'stok_listesini_yenile'):
                widget.stok_listesini_yenile()
            # Diğer tüm 'elif hasattr...' kontrolleri buraya eklenebilir.
            # Şimdilik bu, çökme hatasını engelleyecektir.

        logger.info("Başlangıç verileri başarıyla yüklendi.")

    def _set_default_dates(self):
        # Bu metod ilgili sayfalara taşınacak.
        pass

    def _musteri_karti_penceresi_ac(self):
        from pencereler import YeniMusteriEklePenceresi
        self.musteri_karti_penceresi = YeniMusteriEklePenceresi(self, self.db_manager, self.musteri_yonetimi_sayfasi.musteri_listesini_yenile, app_ref=self)
        self.musteri_karti_penceresi.show()

    def _tedarikci_karti_penceresi_ac(self): 
        from pencereler import YeniTedarikciEklePenceresi
        self.tedarikci_karti_penceresi = YeniTedarikciEklePenceresi(self, self.db_manager, self.tedarikci_yonetimi_sayfasi.tedarikci_listesini_yenile, app_ref=self)
        self.tedarikci_karti_penceresi.show()

    def _kasa_banka_karti_penceresi_ac(self):
        from pencereler import YeniKasaBankaEklePenceresi
        self.kasa_banka_karti_penceresi = YeniKasaBankaEklePenceresi(self, self.db_manager, self.kasa_banka_yonetimi_sayfasi.hesap_listesini_yenile, app_ref=self)
        self.kasa_banka_karti_penceresi.show()

    def _gelir_gider_karti_penceresi_ac(self):
        from pencereler import YeniGelirGiderEklePenceresi
        self.gelir_gider_karti_penceresi = YeniGelirGiderEklePenceresi(self, self.db_manager, self.gelir_gider_sayfasi.gg_listesini_yukle, parent_app=self)
        self.gelir_gider_karti_penceresi.show()

    def _fatura_karti_penceresi_ac(self):
        from pencereler import FaturaPenceresi
        # Bu metodun çağrıldığı yer de güncellenmeli
        self.fatura_karti_penceresi = FaturaPenceresi(self, self.db_manager, app_ref=self, fatura_tipi=self.db_manager.FATURA_TIP_SATIS, yenile_callback=self.fatura_listesi_sayfasi.fatura_listesini_yukle)
        self.fatura_karti_penceresi.show()
        
    def _siparis_karti_penceresi_ac(self):
        from pencereler import SiparisPenceresi
        self.siparis_karti_penceresi = SiparisPenceresi(self, self.db_manager, app_ref=self, siparis_tipi="SATIŞ_SIPARIS", yenile_callback=self.siparis_listesi_sayfasi.siparis_listesini_yukle)
        self.siparis_karti_penceresi.show()

    def _on_cari_secim_yapildi(self, cari_id, cari_tip_str):
        from pencereler import CariHesapEkstresiPenceresi
        cari_tip_enum = "MUSTERI" if cari_tip_str == "Müşteri" else "TEDARIKCI"
        dialog = CariHesapEkstresiPenceresi(
            self,
            self.db_manager,
            cari_id, 
            cari_tip_enum, 
            cari_tip_str 
        )
        dialog.exec()
        self.set_status_message(f"Cari '{cari_tip_str}' ID: {cari_id} için ekstre açıldı.")

    def _cari_hareketler_penceresi_ac(self):
        from pencereler import CariSecimPenceresi
        dialog = CariSecimPenceresi(self, self.db_manager, "GENEL", self._on_cari_secim_yapildi)
        dialog.exec()

    def _nitelik_yonetimi_penceresi_ac(self):
        from pencereler import UrunNitelikYonetimiPenceresi
        self.nitelik_yonetimi_penceresi = UrunNitelikYonetimiPenceresi(self, self.db_manager, app_ref=self, refresh_callback=lambda: self.show_tab("Nitelik Yönetimi"))
        self.nitelik_yonetimi_penceresi.show()
        
    def _toplu_veri_aktarim_penceresi_ac(self):
        from pencereler import TopluVeriEklePenceresi
        self.toplu_veri_aktarim_penceresi = TopluVeriEklePenceresi(self, self.db_manager)
        self.toplu_veri_aktarim_penceresi.show()

    def _rapor_olustur(self, rapor_tipi):
        try:
            self.show_tab("Raporlama Merkezi")
            # Belirli bir rapor tipi seçimi için RaporlamaMerkeziSayfası'nda bir metot olması gerekebilir.
            # Örneğin: self.raporlama_merkezi_sayfasi.select_report_tab(rapor_tipi)
            self.set_status_message(f"{rapor_tipi.capitalize()} raporu için Raporlama Merkezi açıldı.")

        except Exception as e:
            QMessageBox.critical(self, "Rapor Hatası", f"{rapor_tipi.capitalize()} raporu oluşturulurken beklenmeyen bir hata oluştu: {e}")
            logger.error(f"{rapor_tipi.capitalize()} raporu oluşturulurken hata: {e}")

    def _yedekle(self, file_path):
        """Veritabanını yedekler ve kullanıcıya geri bildirimde bulunur."""
        self.set_status_message("Veritabanı yedekleniyor, lütfen bekleyiniz...", "blue")
        try:
            # db sınıfındaki merkezi metodu kullanıyoruz.
            success, message, created_file_path = self.db.database_backup(file_path=file_path, kullanici_id=self.current_user_id)
            if success:
                self.set_status_message(message, "green")
                QMessageBox.information(self, "Başarılı", f"{message}\nDosya Yolu: {created_file_path}")
            else:
                self.set_status_message(message, "red")
                QMessageBox.critical(self, "Yedekleme Hatası", message)
        except Exception as e:
            self.set_status_message(f"Yedekleme sırasında bir hata oluştu: {e}", "red")
            QMessageBox.critical(self, "Yedekleme Hatası", f"Beklenmeyen bir hata oluştu:\n{e}")

    def _check_backup_completion(self, result_queue, bekleme_penceresi):
        if not result_queue.empty():
            self.backup_timer.stop()
            bekleme_penceresi.kapat()
            
            success, message, created_file_path = result_queue.get()
            
            if success and created_file_path and os.path.exists(created_file_path) and os.path.getsize(created_file_path) > 0:
                final_message = f"Yedekleme başarıyla tamamlandı. Dosya: {created_file_path}"
                QMessageBox.information(self, "Yedekleme", final_message)
                self.set_status_message(final_message, "green")
            else:
                final_message = f"Yedekleme işlemi tamamlanamadı veya dosya oluşturulamadı: {message}"
                QMessageBox.critical(self, "Yedekleme Hatası", final_message)
                self.set_status_message(final_message, "red")

    def _handle_backup_completion(self, success, message, created_file_path):
        """Yedekleme tamamlandığında sinyal tarafından çağrılan metot."""
        if hasattr(self, 'bekleme_penceresi') and self.bekleme_penceresi:
            self.bekleme_penceresi.done(QDialog.Accepted)
            del self.bekleme_penceresi

        if success and created_file_path and os.path.exists(created_file_path) and os.path.getsize(created_file_path) > 0:
            final_message = f"Yedekleme başarıyla tamamlandı. Dosya: {created_file_path}"
            QMessageBox.information(self, "Yedekleme", final_message)
            self.set_status_message(final_message, "green")
        else:
            final_message = f"Yedekleme işlemi tamamlanamadı veya dosya oluşturulamadı: {message}"
            QMessageBox.critical(self, "Yedekleme Hatası", final_message)
            self.set_status_message(final_message, "red")

    def _geri_yukle(self, file_path):
        """Veritabanını geri yükler ve uygulamayı yeniden başlatır."""
        self.set_status_message("Veritabanı geri yükleniyor, lütfen bekleyiniz...", "blue")
        try:
            # db sınıfındaki merkezi metodu kullanıyoruz.
            success, message, _ = self.db.database_restore(file_path=file_path, kullanici_id=self.current_user_id)
            if success:
                self.set_status_message(message, "green")
                QMessageBox.information(self, "Başarılı", f"{message}\nUygulama yeniden başlatılacak.")
                self.quit()
            else:
                self.set_status_message(message, "red")
                QMessageBox.critical(self, "Geri Yükleme Hatası", message)
        except Exception as e:
            self.set_status_message(f"Geri yükleme sırasında bir hata oluştu: {e}", "red")
            QMessageBox.critical(self, "Geri Yükleme Hatası", f"Beklenmeyen bir hata oluştu:\n{e}")

    @Slot(bool, str)
    def _handle_restore_completion(self, success, message):
        """Geri yükleme tamamlandığında sinyal tarafından çağrılan metot."""
        if hasattr(self, 'bekleme_penceresi') and self.bekleme_penceresi:
            self.bekleme_penceresi.close()
            del self.bekleme_penceresi

        if success:
            final_message = f"Geri yükleme başarıyla tamamlandı. {message}"
            QMessageBox.information(self, "Geri Yükleme", final_message)
            self.set_status_message(final_message, "green")
            self._initial_load_data()
        else:
            final_message = f"Geri yükleme işlemi tamamlanamadı: {message}"
            QMessageBox.critical(self, "Geri Yükleme Hatası", final_message)
            self.set_status_message(final_message, "red")

    def _pdf_olusturma_islemi(self, data, filename="rapor.pdf"):
        logger.info(f"PDF oluşturma işlemi çağrıldı. Veri boyutu: {len(data)} - Dosya Adı: {filename}")
        QMessageBox.information(self, "PDF Oluşturma", "PDF oluşturma işlevi entegrasyonu tamamlanmadı. Lütfen raporlama modülünü kontrol edin.")

    def _update_status_bar(self):
        self.statusBar().showMessage("Uygulama hazır.")

    def _api_ayarlari_penceresi_ac(self):
        pass

    def _yonetici_ayarlari_penceresi_ac(self):
        from pencereler import YoneticiAyarlariPenceresi
        dialog = YoneticiAyarlariPenceresi(self, self.db_manager)
        dialog.exec()
        
    def _veri_yonetimi_penceresi_ac(self):
        """
        Veri Yönetimi arayüzünü bir diyalog penceresi olarak açar.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Veri Yönetimi ve Senkronizasyon")
        dialog.setMinimumSize(800, 600)

        dialog_layout = QVBoxLayout(dialog)
        veri_yonetimi_widget = VeriYonetimiSekmesi(dialog, self.db_manager, self)
        dialog_layout.addWidget(veri_yonetimi_widget)

        # Sinyal ve slot bağlantıları
        # Bu kısım, VeriYonetimiSekmesi'nin içinde butonlara işlevsellik eklerken kullanılacak

        dialog.exec()
        self.set_status_message("Veri Yönetimi penceresi açıldı.")

    def _handle_api_url_update(self, new_api_url):
        self.config["api_base_url"] = new_api_url
        save_config(self.config)
        try:
            self.db_manager = OnMuhasebe(api_base_url=self.config["api_base_url"])
            QMessageBox.information(self, "API Ayarları", "API URL'si güncellendi ve bağlantı yenilendi.")
            logger.info(f"API URL'si güncellendi: {new_api_url}")
            self._initial_load_data()
        except Exception as e:
            QMessageBox.critical(self, "API Bağlantı Hatası",
                                 f"Yeni API adresine bağlanılamadı: {e}\n"
                                 "Lütfen API sunucusunun çalıştığından ve doğru adreste olduğundan emin olun.")
            logger.critical(f"API URL güncellemesi sonrası bağlantı hatası: {e}")

    def yetkileri_uygula(self):
        """
        Giriş yapan kullanıcının rolüne göre arayüzdeki (UI) yetkileri ayarlar.
        """
        kullanici_rolu = self.current_user.get('rol', 'yok')
        yetkili_roller = ['YONETICI', 'SUPERADMIN', 'admin']

        if kullanici_rolu.upper() not in yetkili_roller:
            print(f"'{kullanici_rolu}' rolü için kısıtlı yetkiler uygulanıyor...")
            if hasattr(self, 'actionY_netici_Ayarlar'):
                self.actionY_netici_Ayarlar.setEnabled(False)
            if hasattr(self, 'actionVeri_Yonetimi'):
                self.actionVeri_Yonetimi.setEnabled(False)
        else:
            print(f"'{kullanici_rolu}' rolü için tüm yetkiler aktif.")

if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.AlternateBase, QColor(230, 230, 230))
    palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.Button, QColor(200, 200, 200))
    palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    
    from arayuz import GirisEkrani
    db_manager_login = OnMuhasebe(api_base_url=load_config()["api_base_url"])
    login_screen = GirisEkrani(None, db_manager_login)
    
    # login_data'yı global kapsamda tanımlayalım
    login_data = {"user_data": None}

    def on_successful_login(user_data):
        """Giriş başarılı olduğunda kullanıcı verisini depolar, yerel DB'ye hash'i kaydeder ve giriş ekranını kapatır."""
        
        # Kritik bilgileri al
        kullanici_id = user_data.get("kullanici_id")
        kullanici_adi = user_data.get("kullanici_adi")
        sifre_hash = user_data.get("sifre_hash")
        rol = user_data.get("rol", "user") # Rol yoksa varsayılan olarak "user" atandı
        
        # 1. Access Token'ı kaydet
        access_token = user_data.get("access_token")
        if access_token:
            # KRİTİK DÜZELTME: Yanlış metot çağrısı düzeltildi. Token lokal DB servisi üzerinden kaydedildi.
            db_manager_login.lokal_db.ayarlari_kaydet({
                "access_token": access_token,
                "token_type": user_data.get("token_type") # Token tipini de kaydet
            })
            logger.info("Access Token başarıyla kalıcı olarak kaydedildi.")
        
        # 2. Hash kaydı (Çevrimdışı mod için)
        if all([kullanici_id, kullanici_adi, sifre_hash]):
            # update_local_user_credentials'a artık varsayılan bir rol bilgisi gönderiliyor.
            update_local_user_credentials(
                kullanici_id, kullanici_adi, sifre_hash, rol
            )
            logger.info(f"Kullanıcı kimlik bilgileri yerel veritabanına kaydedildi: {kullanici_adi}")
        else:
             logger.warning(f"API yanıtı, yerel depolama için gerekli kritik bilgileri (ID:{kullanici_id}/Hash:{bool(sifre_hash)}/Ad:{kullanici_adi}) içermiyor. Kaydetme adımı atlandı.")

        # Kullanıcı verisini global sözlüğe kaydedin (Bu satırın çalışması Çökme 2'yi engeller)
        login_data["user_data"] = user_data
        # Giriş ekranını kapatın
        login_screen.accept()

    login_screen.login_success.connect(on_successful_login)

    # Uygulamanın ana olay döngüsünü başlatın
    if login_screen.exec() == QDialog.Accepted:
        # Eğer login başarılıysa, ana pencereyi oluşturup gösterin
        
        # Kritik Kontrol: Eğer user_data bir sözlük değilse, App'i başlatmadan önce hata ver.
        user_data = login_data["user_data"]
        if not isinstance(user_data, dict) or not user_data:
            QMessageBox.critical(None, "Kritik Hata", "Kullanıcı verisi alınamadı. Uygulama kapatılıyor.")
            sys.exit(1)
        
        main_window = App(user_data)
        db_manager_login.app = main_window 
        
        main_window.setWindowState(Qt.WindowMaximized)
        main_window.show()
        
        # UI açıldıktan hemen sonra, yerel verileri yüklüyor ve senkronizasyonu arka planda başlatıyor.
        main_window._initial_load_data() # 1. UI'ı anında yerel verilerle doldur
        main_window._start_background_sync() # 2. Ağ işlemini arka planda başlat

        sys.exit(app.exec())
    else:
        # Eğer login iptal edildiyse (kullanıcı kapattıysa), uygulamadan çıkın
        sys.exit(0)