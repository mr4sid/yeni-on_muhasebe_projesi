# yardimcilar.py dosyasının içeriği
import locale
from datetime import datetime
import calendar

# PySide6 tabanlı UI bileşenleri için gerekli import'lar
from PySide6.QtWidgets import QDialog, QVBoxLayout, QCalendarWidget, QPushButton, QLineEdit, QMessageBox, QFrame, QHBoxLayout
from PySide6.QtCore import QDate, Signal, Slot, Qt
from PySide6.QtGui import QDoubleValidator # Sayısal giriş doğrulaması için
import logging
# Logger kurulumu
logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Locale ayarını uygulamanın en başında bir kez yapıyoruz.
def setup_locale():
    """Sistem dil ayarını Türkçe olarak ayarlar."""
    try:
        locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.1254')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'tr_TR')
            except locale.Error:
                try:
                    locale.setlocale(locale.LC_ALL, 'tr_TR.utf8')
                except locale.Error:
                    print("UYARI: Türkçe locale (tr_TR) bulunamadı. Varsayılan formatlama kullanılacak.")

# Uygulama başladığında locale ayarını yap
setup_locale()

def normalize_turkish_chars(text):
    """Türkçe karakterleri İngilizce eşdeğerlerine dönüştürür."""
    if not isinstance(text, str):
        return text
    text = text.replace('ı', 'i').replace('İ', 'I')
    text = text.replace('ş', 's').replace('Ş', 'S')
    text = text.replace('ğ', 'g').replace('Ğ', 'G')
    text = text.replace('ç', 'c').replace('Ç', 'C')
    text = text.replace('ö', 'o').replace('Ö', 'O')
    text = text.replace('ü', 'u').replace('Ü', 'U')
    return text

class DatePickerDialog(QDialog):
    date_selected = Signal(str)

    def __init__(self, parent_app, initial_date=None):
        super().__init__(parent_app)
        self.setWindowTitle("Tarih Seç")
        self.setFixedSize(300, 300)
        self.setModal(True)
        
        main_layout = QVBoxLayout(self)
        self.takvim = QCalendarWidget()
        self.takvim.setGridVisible(True)
        self.takvim.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        main_layout.addWidget(self.takvim)

        if initial_date:
            try:
                # `initial_date` bir QDate nesnesine dönüştürülürken hata oluşursa,
                # `currentDate` kullanılır.
                q_date = QDate.fromString(initial_date, 'yyyy-MM-dd')
                if q_date.isValid():
                    self.takvim.setSelectedDate(q_date)
            except Exception as e:
                logger.warning(f"Geçersiz başlangıç tarihi formatı: {initial_date}. Bugün seçiliyor. Hata: {e}")
                self.takvim.setSelectedDate(QDate.currentDate())
        else:
            self.takvim.setSelectedDate(QDate.currentDate())

        self.takvim.setFocus()
        
        button_frame = QFrame(self)
        button_layout = QHBoxLayout(button_frame)
        main_layout.addWidget(button_frame)

        btn_ok = QPushButton("Tamam")
        btn_ok.clicked.connect(self.accept)
        button_layout.addWidget(btn_ok)
        
        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.reject)
        button_layout.addWidget(btn_iptal)

    def get_selected_date(self):
        """Seçilen tarihi 'yyyy-MM-dd' formatında döndürür."""
        return self.takvim.selectedDate().toString('yyyy-MM-dd')
    
    @Slot(QDate) # Bir QDate objesi alacağını belirtir
    def _on_date_clicked(self, date_obj):
        """Takvimde bir tarihe tıklandığında çağrılır."""
        self.selected_final_date_str = date_obj.toString("yyyy-MM-dd")

    def accept(self):
        """Diyalog "Kabul Et" (Accept) ile kapatıldığında çağrılır."""
        # Seçilen tarihi al
        selected_date = self.takvim.selectedDate().toString('yyyy-MM-dd')
        
        # Seçilen tarihi bir sinyal olarak dışarıya yay
        self.date_selected.emit(selected_date)
        
        # QDialog'un kabul metodu çağrılır.
        super().accept()

def format_and_validate_numeric_input(line_edit, app_instance=None):
    """
    QLineEdit içindeki sayısal değeri formatlar (örn. 1.000,00) ve doğrular.
    Bu versiyon, kullanıcının boş bırakmasına izin verir.
    """
    current_text = line_edit.text().strip()

    # Metin boşsa, işlem yapmadan çık. Bu, silme işlemine izin verir.
    if not current_text:
        return

    # Türkçe formatı İngilizce formata çevir (virgülü noktaya, binlik ayıracı kaldır)
    processed_text = current_text.replace(".", "").replace(",", ".")

    try:
        # Geçersiz giriş varsa yakalanacak
        value = float(processed_text)

        # Eğer değer 0'dan küçükse ve buna izin verilmiyorsa, uyarı ver ve 0'a çek
        if line_edit.validator() and line_edit.validator().bottom() >= 0 and value < 0:
            if app_instance:
                QMessageBox.warning(app_instance, "Geçersiz Giriş", "Negatif değer girilemez.")
            line_edit.setText("0,00")
            return

        # Orijinal metindeki imleç konumunu kaydet
        current_cursor_pos = line_edit.cursorPosition()

        # Locale ayarları kullanarak formatla
        formatted_value = locale.format_string("%.2f", value, grouping=True)

        # Eğer 2'den fazla ondalık basamak varsa, yuvarlayıp tekrar formatlayalım
        if ',' in formatted_value and len(formatted_value.split(',')[1]) > 2:
            value = round(value, 2)
            formatted_value = locale.format_string("%.2f", value, grouping=True)

        line_edit.setText(formatted_value)

        # İmleci mümkün olduğunca koru
        if current_cursor_pos <= len(formatted_value):
            line_edit.setCursorPosition(current_cursor_pos)
        else:
            line_edit.setCursorPosition(len(formatted_value))

    except ValueError:
        # Geçersiz bir değer girildiğinde (örn. "a", "asd"), metni olduğu gibi bırak.
        pass
    except Exception as e:
        # Diğer beklenmeyen hatalar için
        if app_instance:
            QMessageBox.critical(app_instance, "Hata", f"Giriş işlenirken bir hata oluştu: {e}")
        else:
            print(f"HATA: Sayısal giriş işleme hatası: '{current_text}' -> {e}")