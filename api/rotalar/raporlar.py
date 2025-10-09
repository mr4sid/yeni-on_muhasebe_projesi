# api/rotalar/raporlar.py dosyasının tamamı (güncel hali)
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract, case, String
from datetime import date, datetime, timedelta
from typing import Optional, List
from fastapi.responses import FileResponse
from .. import modeller, semalar, guvenlik
from ..veritabani import get_db
from ..api_servisler import CariHesaplamaService
import openpyxl
import os

router = APIRouter(prefix="/raporlar", tags=["Raporlar"])

REPORTS_DIR = "server_reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

@router.get("/dashboard_ozet", response_model=modeller.PanoOzetiYanit)
def get_dashboard_ozet_endpoint(
    baslangic_tarihi: date = Query(None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    bitis_tarihi: date = Query(None, description="Bitiş tarihi (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    
    # KRİTİK DÜZELTME: Enum üye adları düzeltildi ve modeller kullanıldı.
    satis_query = db.query(func.sum(modeller.Fatura.genel_toplam)).filter(
        modeller.Fatura.kullanici_id == kullanici_id,
        modeller.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS # DÜZELTME
    )
    alis_query = db.query(func.sum(modeller.Fatura.genel_toplam)).filter(
        modeller.Fatura.kullanici_id == kullanici_id,
        modeller.Fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS # DÜZELTME
    )

    tahsilat_query = db.query(func.sum(modeller.GelirGider.tutar)).filter(
        modeller.GelirGider.kullanici_id == kullanici_id,
        modeller.GelirGider.tip == semalar.GelirGiderTipEnum.GELİR
    )
    odeme_query = db.query(func.sum(modeller.GelirGider.tutar)).filter(
        modeller.GelirGider.kullanici_id == kullanici_id,
        modeller.GelirGider.tip == semalar.GelirGiderTipEnum.GİDER # DÜZELTME
    )

    # Tarih filtreleri (modeller kullanılıyor)
    if baslangic_tarihi:
        satis_query = satis_query.filter(modeller.Fatura.tarih >= baslangic_tarihi)
        alis_query = alis_query.filter(modeller.Fatura.tarih >= baslangic_tarihi)
        tahsilat_query = tahsilat_query.filter(modeller.GelirGider.tarih >= baslangic_tarihi)
        odeme_query = odeme_query.filter(modeller.GelirGider.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        satis_query = satis_query.filter(modeller.Fatura.tarih <= bitis_tarihi)
        alis_query = alis_query.filter(modeller.Fatura.tarih <= bitis_tarihi)
        tahsilat_query = tahsilat_query.filter(modeller.GelirGider.tarih <= bitis_tarihi)
        odeme_query = odeme_query.filter(modeller.GelirGider.tarih <= bitis_tarihi)

    toplam_satislar = satis_query.scalar() or 0.0
    toplam_alislar = alis_query.scalar() or 0.0
    toplam_tahsilatlar = tahsilat_query.scalar() or 0.0
    toplam_odemeler = odeme_query.scalar() or 0.0

    # En çok satan ürünler (modeller kullanılıyor ve Enum düzeltildi)
    en_cok_satan_urunler_query = db.query(
        modeller.Stok.ad,
        func.sum(modeller.FaturaKalemi.miktar).label('toplam_miktar')
    ).join(
        modeller.FaturaKalemi, modeller.Stok.id == modeller.FaturaKalemi.urun_id
    ).join(
        modeller.Fatura, modeller.FaturaKalemi.fatura_id == modeller.Fatura.id
    ).filter(
        modeller.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS, # DÜZELTME
        modeller.Stok.kullanici_id == kullanici_id
    )
    if baslangic_tarihi:
        en_cok_satan_urunler_query = en_cok_satan_urunler_query.filter(modeller.Fatura.tarih >= baslangic_tarihi)
    if bitis_tarihi:
        en_cok_satan_urunler_query = en_cok_satan_urunler_query.filter(modeller.Fatura.tarih <= bitis_tarihi)

    en_cok_satan_urunler = en_cok_satan_urunler_query.group_by(
        modeller.Stok.ad
    ).order_by(
        func.sum(modeller.FaturaKalemi.miktar).desc()
    ).limit(5).all()
    
    # Vadesi geçenler (modeller kullanılıyor ve Enum düzeltildi)
    today = date.today()
    vadesi_yaklasan_alacaklar_toplami = db.query(func.sum(modeller.Fatura.genel_toplam)).filter(
        modeller.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS, # DÜZELTME
        modeller.Fatura.odeme_turu.cast(String) == semalar.OdemeTuruEnum.ACIK_HESAP.value,
        modeller.Fatura.vade_tarihi >= today,
        modeller.Fatura.vade_tarihi <= (today + timedelta(days=30)),
        modeller.Fatura.kullanici_id == kullanici_id
    ).scalar() or 0.0

    vadesi_gecmis_borclar_toplami = db.query(func.sum(modeller.Fatura.genel_toplam)).filter(
        modeller.Fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS, # DÜZELTME
        modeller.Fatura.odeme_turu.cast(String) == semalar.OdemeTuruEnum.ACIK_HESAP.value,
        modeller.Fatura.vade_tarihi < today,
        modeller.Fatura.kullanici_id == kullanici_id
    ).scalar() or 0.0
    query_stok = db.query(modeller.Stok).filter(modeller.Stok.kullanici_id == kullanici_id)
    kritik_stok_sayisi = query_stok.filter(
        modeller.Stok.aktif == True,
        modeller.Stok.miktar <= modeller.Stok.min_stok_seviyesi # Doğru alan kullanılıyor
    ).count()

    # En çok satan ürünler formatlama
    formatted_top_sellers = [
        {"urun_adi": urun_ad, "toplam_miktar": toplam_miktar}
        for urun_ad, toplam_miktar in en_cok_satan_urunler
    ]

    return {
        "toplam_satislar": toplam_satislar,
        "toplam_alislar": toplam_alislar,
        "toplam_tahsilatlar": toplam_tahsilatlar,
        "toplam_odemeler": toplam_odemeler,
        "kritik_stok_sayisi": kritik_stok_sayisi,
        "en_cok_satan_urunler": formatted_top_sellers,
        "vadesi_yaklasan_alacaklar_toplami": vadesi_yaklasan_alacaklar_toplami,
        "vadesi_gecmis_borclar_toplami": vadesi_gecmis_borclar_toplami
    }

@router.get("/satislar_detayli_rapor", response_model=modeller.FaturaListResponse)
def get_satislar_detayli_rapor_endpoint(
    baslangic_tarihi: date = Query(..., description="YYYY-MM-DD formatında başlangıç tarihi"),
    bitis_tarihi: date = Query(..., description="YYYY-MM-DD formatında bitiş tarihi"),
    cari_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    query = db.query(semalar.Fatura).filter(
        semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS,
        semalar.Fatura.tarih >= baslangic_tarihi,
        semalar.Fatura.tarih <= bitis_tarihi,
        semalar.Fatura.kullanici_id == kullanici_id
    ).order_by(semalar.Fatura.tarih.desc())

    if cari_id:
        query = query.filter(semalar.Fatura.cari_id == cari_id)

    total_count = query.count()
    faturalar = query.all()

    return {"items": [modeller.FaturaRead.model_validate(fatura, from_attributes=True) for fatura in faturalar], "total": total_count}

@router.post("/generate_satis_raporu_excel", status_code=status.HTTP_200_OK)
def generate_tarihsel_satis_raporu_excel_endpoint(
    baslangic_tarihi: date = Query(..., description="Başlangıç tarihi (YYYY-MM-DD)"),
    bitis_tarihi: date = Query(..., description="YYYY-MM-DD formatında bitiş tarihi"),
    cari_id: Optional[int] = Query(None, description="Opsiyonel Cari ID"),
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    try:
        query = db.query(semalar.Fatura).filter(
            semalar.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS,
            semalar.Fatura.tarih >= baslangic_tarihi,
            semalar.Fatura.tarih <= bitis_tarihi,
            semalar.Fatura.kullanici_id == kullanici_id
        ).order_by(semalar.Fatura.tarih.desc())

        if cari_id:
            query = query.filter(semalar.Fatura.cari_id == cari_id)

        faturalar = query.all()

        detailed_sales_data_response = modeller.FaturaListResponse(
            items=[modeller.FaturaRead.model_validate(fatura, from_attributes=True) for fatura in faturalar],
            total=len(faturalar)
        )
        detailed_sales_data = detailed_sales_data_response.items

        if not detailed_sales_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Belirtilen tarih aralığında satış faturası bulunamadı.")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Satış Raporu"

        headers = [
            "Fatura No", "Tarih", "Cari Adı", "Ürün Kodu", "Ürün Adı", "Miktar",
            "Birim Fiyat", "KDV (%)", "İskonto 1 (%)", "İskonto 2 (%)", "Uygulanan İskonto Tutarı",
            "Kalem Toplam (KDV Dahil)", "Fatura Genel Toplam (KDV Dahil)", "Ödeme Türü"
        ]
        ws.append(headers)

        for fatura_item in detailed_sales_data:
            kalemler = db.query(semalar.FaturaKalemi).filter(semalar.FaturaKalemi.fatura_id == fatura_item.id).all()

            fatura_no = fatura_item.fatura_no
            tarih = fatura_item.tarih.strftime("%Y-%m-%d") if isinstance(fatura_item.tarih, date) else str(fatura_item.tarih)
            cari_adi = fatura_item.cari_adi if fatura_item.cari_adi else "N/A"
            genel_toplam_fatura = fatura_item.genel_toplam
            odeme_turu = fatura_item.odeme_turu.value if hasattr(fatura_item.odeme_turu, 'value') else str(fatura_item.odeme_turu)

            for kalem in kalemler:
                urun = db.query(semalar.Stok).filter(semalar.Stok.id == kalem.urun_id, semalar.Stok.kullanici_id == kullanici_id).first()
                urun_kodu = urun.kod if urun else "N/A"
                urun_adi = urun.ad if urun else "N/A"

                birim_fiyat_kdv_dahil_kalem_orig = kalem.birim_fiyat * (1 + kalem.kdv_orani / 100)
                iskontolu_birim_fiyat_kdv_dahil = birim_fiyat_kdv_dahil_kalem_orig * (1 - kalem.iskonto_yuzde_1 / 100) * (1 - kalem.iskonto_yuzde_2 / 100)
                uygulanan_iskonto_tutari = (birim_fiyat_kdv_dahil_kalem_orig - iskontolu_birim_fiyat_kdv_dahil) * kalem.miktar
                kalem_toplam_kdv_dahil = iskontolu_birim_fiyat_kdv_dahil * kalem.miktar

                row_data = [
                    fatura_no, tarih, cari_adi, urun_kodu, urun_adi, kalem.miktar,
                    iskontolu_birim_fiyat_kdv_dahil, kalem.kdv_orani, kalem.iskonto_yuzde_1,
                    kalem.iskonto_yuzde_2, uygulanan_iskonto_tutari, kalem_toplam_kdv_dahil,
                    genel_toplam_fatura, odeme_turu
                ]
                ws.append(row_data)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"satis_raporu_{timestamp}.xlsx"
        filepath = os.path.join(REPORTS_DIR, filename)
        wb.save(filepath)

        return {"message": f"Satış raporu başarıyla oluşturuldu: {filename}", "filepath": filepath}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Rapor oluşturulurken beklenmedik bir hata oluştu: {e}")

@router.get("/kar_zarar_verileri", response_model=modeller.KarZararResponse)
def get_kar_zarar_verileri_endpoint(
    baslangic_tarihi: date = Query(..., description="YYYY-MM-DD formatında başlangıç tarihi"),
    bitis_tarihi: date = Query(..., description="YYYY-MM-DD formatında bitiş tarihi"),
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    
    # KRİTİK DÜZELTME: Tüm sorgularda modeller.X ve Enum üye adları düzeltildi (SATIŞ -> SATIS, ALIŞ -> ALIS vb.)
    toplam_satis_geliri = db.query(func.sum(modeller.Fatura.genel_toplam)).filter(
        modeller.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS, # Düzeltme
        modeller.Fatura.tarih >= baslangic_tarihi,
        modeller.Fatura.tarih <= bitis_tarihi,
        modeller.Fatura.kullanici_id == kullanici_id
    ).scalar() or 0.0

    toplam_satis_maliyeti = db.query(
        func.sum(modeller.FaturaKalemi.miktar * modeller.FaturaKalemi.alis_fiyati_fatura_aninda)
    ).join(modeller.Fatura, modeller.FaturaKalemi.fatura_id == modeller.Fatura.id) \
     .filter(
         modeller.Fatura.fatura_turu == semalar.FaturaTuruEnum.SATIS, # Düzeltme
         modeller.Fatura.tarih >= baslangic_tarihi,
         modeller.Fatura.tarih <= bitis_tarihi,
         modeller.Fatura.kullanici_id == kullanici_id
     ).scalar() or 0.0

    toplam_alis_gideri = db.query(func.sum(modeller.Fatura.genel_toplam)).filter(
        modeller.Fatura.fatura_turu == semalar.FaturaTuruEnum.ALIS, # Düzeltme
        modeller.Fatura.tarih >= baslangic_tarihi,
        modeller.Fatura.tarih <= bitis_tarihi,
        modeller.Fatura.kullanici_id == kullanici_id
    ).scalar() or 0.0

    diger_gelirler = db.query(func.sum(modeller.GelirGider.tutar)).filter(
        modeller.GelirGider.tip == semalar.GelirGiderTipEnum.GELİR, # Düzeltme
        modeller.GelirGider.tarih >= baslangic_tarihi,
        modeller.GelirGider.tarih <= bitis_tarihi,
        modeller.GelirGider.kullanici_id == kullanici_id
    ).scalar() or 0.0

    diger_giderler = db.query(func.sum(modeller.GelirGider.tutar)).filter(
        modeller.GelirGider.tip == semalar.GelirGiderTipEnum.GİDER, # Düzeltme
        modeller.GelirGider.tarih >= baslangic_tarihi,
        modeller.GelirGider.tarih <= bitis_tarihi,
        modeller.GelirGider.kullanici_id == kullanici_id
    ).scalar() or 0.0

    brut_kar = toplam_satis_geliri - toplam_satis_maliyeti
    net_kar = brut_kar + diger_gelirler - diger_giderler - toplam_alis_gideri

    return {
        "toplam_satis_geliri": toplam_satis_geliri,
        "toplam_satis_maliyeti": toplam_satis_maliyeti,
        "toplam_alis_gideri": toplam_alis_gideri,
        "diger_gelirler": diger_gelirler,
        "diger_giderler": diger_giderler,
        "brut_kar": brut_kar,
        "net_kar": net_kar
    }

@router.get("/nakit_akisi_raporu", response_model=modeller.NakitAkisiResponse)
def get_nakit_akisi_raporu_endpoint(
    baslangic_tarihi: date = Query(..., description="YYYY-MM-DD formatında başlangıç tarihi"),
    bitis_tarihi: date = Query(..., description="YYYY-MM-DD formatında bitiş tarihi"),
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    
    # KRİTİK ÇÖZÜM: Hardcoded NAKİT/KART/EFT filtresini ENUM değerleri ile değiştirme.
    # Bu, NAKİT (Türkçe İ) yerine NAKIT (safe) ve EFT/HAVALE yerine EFT_HAVALE gönderilmesini sağlar.
    safe_odeme_turleri = [
        semalar.OdemeTuruEnum.NAKIT.value,
        semalar.OdemeTuruEnum.KART.value,
        semalar.OdemeTuruEnum.EFT_HAVALE.value
    ]
    
    # 1.1. CARİ HAREKETLER (Tahsilat/Ödeme)
    cari_nakit_select = db.query(
        modeller.CariHareket.islem_turu.label('tip'),
        modeller.CariHareket.tutar,
        modeller.CariHareket.tarih,
        modeller.CariHareket.aciklama,
        modeller.KasaBankaHesap.hesap_adi.label('hesap_adi'),
        modeller.CariHareket.kaynak.label('kaynak')
    ).join(
        modeller.KasaBankaHesap, modeller.KasaBankaHesap.id == modeller.CariHareket.kasa_banka_id
    ).filter(
        modeller.CariHareket.kullanici_id == kullanici_id,
        modeller.CariHareket.tarih >= baslangic_tarihi if baslangic_tarihi else True,
        modeller.CariHareket.tarih <= bitis_tarihi if bitis_tarihi else True,
        modeller.CariHareket.odeme_turu.in_(safe_odeme_turleri) # DÜZELTİLDİ
    ).subquery().select()

    # 1.2. GELİR/GİDER HAREKETLERİ (Manuel Girişler) - Sadece nakit hareketler
    gg_nakit_select = db.query(
        # KRİTİK DÜZELTME: tip sütununu String'e (VARCHAR) çevirerek DatatypeMismatch hatasını çöz
        modeller.GelirGider.tip.cast(String).label('tip'),
        modeller.GelirGider.tutar,
        modeller.GelirGider.tarih,
        modeller.GelirGider.aciklama,
        modeller.KasaBankaHesap.hesap_adi.label('hesap_adi'),
        modeller.GelirGider.kaynak.label('kaynak')
    ).join(
        modeller.KasaBankaHesap, modeller.KasaBankaHesap.id == modeller.GelirGider.kasa_banka_id
    ).filter(
        modeller.GelirGider.kullanici_id == kullanici_id,
        modeller.GelirGider.tarih >= baslangic_tarihi if baslangic_tarihi else True,
        modeller.GelirGider.tarih <= bitis_tarihi if bitis_tarihi else True,
        modeller.GelirGider.kasa_banka_id.isnot(None) 
    ).subquery().select()
    
    # Her iki sorguyu birleştir (UNION ALL)
    nakit_akisi_union = cari_nakit_select.union_all(gg_nakit_select)
    
    # Birleşmiş sorguyu çalıştırıp sonuçları al ve sırala
    nakit_akisi_data = db.execute(
        nakit_akisi_union.order_by(nakit_akisi_union.c.tarih.desc())
    ).all()

    nakit_girisleri = 0.0
    nakit_cikislar = 0.0
    formatted_items = []
    
    for item in nakit_akisi_data:
        tutar = float(item.tutar)
        tip = str(item.tip).upper()
        
        # Giriş/Çıkış hesaplaması (Gelir = Giriş, Gider = Çıkış)
        if tip == 'GELİR' or tip == 'TAHSILAT' or tip == 'FATURA_SATIS_PESIN':
            nakit_girisleri += tutar
        elif tip == 'GIDER' or tip == 'ODEME' or tip == 'FATURA_ALIS_PESIN':
            nakit_cikislar += tutar

        # Rapor satırı oluşturma
        formatted_items.append({
            "tarih": item.tarih.strftime('%Y-%m-%d'),
            "tip": tip,
            "tutar": tutar,
            "aciklama": item.aciklama,
            "hesap_adi": item.hesap_adi,
            "kaynak": str(item.kaynak)
        })

    return {
        "nakit_girisleri": nakit_girisleri,
        "nakit_cikislar": nakit_cikislar,
        "net_nakit_akisi": nakit_girisleri - nakit_cikislar,
        "items": formatted_items
    }

@router.get("/cari_yaslandirma_raporu", response_model=modeller.CariYaslandirmaResponse)
def get_cari_yaslandirma_verileri_endpoint(
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    today = date.today()

    musteri_alacaklar = []
    tedarikci_borclar = []

    cari_hizmeti = CariHesaplamaService(db)

    musteriler = db.query(semalar.Musteri).filter(semalar.Musteri.aktif == True, semalar.Musteri.kullanici_id == kullanici_id).all()
    for musteri in musteriler:
        net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(musteri.id, semalar.CariTipiEnum.MUSTERI)
        if net_bakiye > 0:
            musteri_alacaklar.append({
                "cari_id": musteri.id,
                "cari_ad": musteri.ad,
                "bakiye": net_bakiye,
                "vade_tarihi": None
            })

    tedarikciler = db.query(semalar.Tedarikci).filter(semalar.Tedarikci.aktif == True, semalar.Tedarikci.kullanici_id == kullanici_id).all()
    for tedarikci in tedarikciler:
        net_bakiye = cari_hizmeti.calculate_cari_net_bakiye(tedarikci.id, semalar.CariTipiEnum.TEDARIKCI)
        if net_bakiye < 0:
            tedarikci_borclar.append({
                "cari_id": tedarikci.id,
                "cari_ad": tedarikci.ad,
                "bakiye": abs(net_bakiye),
                "vade_tarihi": None
            })

    return {
        "musteri_alacaklar": musteri_alacaklar,
        "tedarikci_borclar": tedarikci_borclar
    }

@router.get("/cari_hesap_ekstresi", response_model=modeller.CariHareketListResponse)
def get_cari_hesap_ekstresi_endpoint(
    cari_id: int = Query(..., description="Cari ID"),
    cari_turu: semalar.CariTipiEnum = Query(..., description="Cari Türü (MUSTERI veya TEDARIKCI)"),
    baslangic_tarihi: date = Query(..., description="Başlangıç tarihi (YYYY-MM-DD)"),
    bitis_tarihi: date = Query(..., description="Bitiş tarihi (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    if cari_turu == semalar.CariTipiEnum.MUSTERI:
        cari_obj = db.query(modeller.Musteri).filter(modeller.Musteri.id == cari_id, modeller.Musteri.kullanici_id == kullanici_id).first()
    else:
        cari_obj = db.query(modeller.Tedarikci).filter(modeller.Tedarikci.id == cari_id, modeller.Tedarikci.kullanici_id == kullanici_id).first()

    if not cari_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cari bulunamadı")

    devreden_bakiye_alacak = db.query(func.sum(modeller.CariHareket.tutar)).filter(
        modeller.CariHareket.cari_id == cari_id,
        modeller.CariHareket.cari_tip == cari_turu, # DÜZELTME: ORM'deki doğru alan cari_tip
        modeller.CariHareket.islem_yone == semalar.IslemYoneEnum.ALACAK,
        modeller.CariHareket.tarih < baslangic_tarihi,
        modeller.CariHareket.kullanici_id == kullanici_id
    ).scalar() or 0.0

    devreden_bakiye_borc = db.query(func.sum(modeller.CariHareket.tutar)).filter(
        modeller.CariHareket.cari_id == cari_id,
        modeller.CariHareket.cari_tip == cari_turu, # DÜZELTME: ORM'deki doğru alan cari_tip
        modeller.CariHareket.islem_yone == semalar.IslemYoneEnum.BORC,
        modeller.CariHareket.tarih < baslangic_tarihi,
        modeller.CariHareket.kullanici_id == kullanici_id
    ).scalar() or 0.0

    if cari_turu == semalar.CariTipiEnum.MUSTERI:
        devreden_bakiye = devreden_bakiye_alacak - devreden_bakiye_borc
    else:
        devreden_bakiye = devreden_bakiye_borc - devreden_bakiye_alacak

    hareketler_query = db.query(modeller.CariHareket).filter(
        modeller.CariHareket.cari_id == cari_id,
        modeller.CariHareket.cari_tip == cari_turu, # DÜZELTME: ORM'deki doğru alan cari_tip
        modeller.CariHareket.tarih >= baslangic_tarihi,
        modeller.CariHareket.tarih <= bitis_tarihi,
        modeller.CariHareket.kullanici_id == kullanici_id
    ).order_by(modeller.CariHareket.tarih.asc(), modeller.CariHareket.id.asc())

    hareketler = hareketler_query.all()

    hareket_read_models = []
    for hareket in hareketler:
        hareket_model_dict = modeller.CariHareketRead.model_validate(hareket, from_attributes=True).model_dump()

        if hareket.kaynak == semalar.KaynakTipEnum.FATURA and hareket.kaynak_id:
            fatura_obj = db.query(modeller.Fatura).filter(modeller.Fatura.id == hareket.kaynak_id, modeller.Fatura.kullanici_id == kullanici_id).first()
            if fatura_obj:
                hareket_model_dict['fatura_no'] = fatura_obj.fatura_no
                hareket_model_dict['fatura_turu'] = fatura_obj.fatura_turu

        if hareket.kasa_banka_id:
            kasa_banka_obj = db.query(modeller.KasaBankaHesap).filter(modeller.KasaBankaHesap.id == hareket.kasa_banka_id, modeller.KasaBankaHesap.kullanici_id == kullanici_id).first()
            if kasa_banka_obj:
                hareket_model_dict['kasa_banka_adi'] = kasa_banka_obj.hesap_adi

        hareket_read_models.append(hareket_model_dict)

    return {"items": hareket_read_models, "total": len(hareketler), "devreden_bakiye": devreden_bakiye}

@router.get("/stok_deger_raporu", response_model=modeller.StokDegerResponse)
def get_stok_envanter_ozet_endpoint(
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    toplam_stok_maliyeti = db.query(
        func.sum(semalar.Stok.miktar * semalar.Stok.alis_fiyati)
    ).filter(semalar.Stok.aktif == True, semalar.Stok.kullanici_id == kullanici_id).scalar() or 0.0

    return {
        "toplam_stok_maliyeti": toplam_stok_maliyeti
    }

@router.get("/download_report/{filename}", status_code=status.HTTP_200_OK)
async def download_report_excel_endpoint(filename: str, db: Session = Depends(get_db)):
    filepath = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rapor dosyası bulunamadı.")

    return FileResponse(path=filepath, filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@router.get("/gelir_gider_aylik_ozet", response_model=modeller.GelirGiderAylikOzetResponse)
def get_gelir_gider_aylik_ozet_endpoint(
    yil: int = Query(..., ge=2000, le=date.today().year),
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    gelir_gider_ozet = db.query(
        extract('month', semalar.GelirGider.tarih).label('ay'),
        func.sum(case((semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GELİR, semalar.GelirGider.tutar), else_=0)).label('toplam_gelir'),
        func.sum(case((semalar.GelirGider.tip == semalar.GelirGiderTipEnum.GİDER, semalar.GelirGider.tutar), else_=0)).label('toplam_gider')
    ).filter(
        extract('year', semalar.GelirGider.tarih) == yil,
        semalar.GelirGider.kullanici_id == kullanici_id
    ) \
     .group_by(extract('month', semalar.GelirGider.tarih)) \
     .order_by(extract('month', semalar.GelirGider.tarih)) \
     .all()

    aylik_data = []
    ay_adlari_dict = {
        1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
        7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
    }

    for i in range(1, 13):
        ay_adi = ay_adlari_dict.get(i, f"{i}. Ay")

        gelir = next((item.toplam_gelir for item in gelir_gider_ozet if item.ay == i), 0.0)
        gider = next((item.toplam_gider for item in gelir_gider_ozet if item.ay == i), 0.0)
        aylik_data.append({
            "ay": i,
            "ay_adi": ay_adi,
            "toplam_gelir": gelir,
            "toplam_gider": gider
        })

    return {"aylik_ozet": aylik_data}

@router.get("/urun_faturalari", response_model=modeller.FaturaListResponse)
def get_urun_faturalari_endpoint(
    urun_id: int,
    fatura_turu: str = Query(None),
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    query = db.query(modeller.Fatura).join(modeller.FaturaKalemi).filter(modeller.FaturaKalemi.urun_id == urun_id, modeller.Fatura.kullanici_id == kullanici_id)

    if fatura_turu:
        query = query.filter(modeller.Fatura.fatura_turu == fatura_turu.upper())

    faturalar = query.distinct(modeller.Fatura.id).order_by(modeller.Fatura.id, modeller.Fatura.tarih.desc()).all()

    if not faturalar:
        return {"items": [], "total": 0}

    return {"items": [
        modeller.FaturaRead.model_validate(fatura, from_attributes=True)
        for fatura in faturalar
    ], "total": len(faturalar)}

@router.get("/fatura_kalem_gecmisi", response_model=List[modeller.FaturaKalemiRead])
def get_fatura_kalem_gecmisi_endpoint(
    cari_id: int,
    urun_id: int,
    fatura_tipi: semalar.FaturaTuruEnum,
    db: Session = Depends(get_db),
    current_user: modeller.KullaniciRead = Depends(guvenlik.get_current_user)
):
    kullanici_id = current_user.id
    query = db.query(semalar.FaturaKalemi)\
              .join(semalar.Fatura, semalar.FaturaKalemi.fatura_id == semalar.Fatura.id)\
              .filter(
                  semalar.Fatura.cari_id == cari_id,
                  semalar.Fatura.fatura_turu == fatura_tipi,
                  semalar.FaturaKalemi.urun_id == urun_id,
                  semalar.Fatura.kullanici_id == kullanici_id
              )\
              .order_by(semalar.Fatura.tarih.desc())

    kalemler = query.all()

    return [modeller.FaturaKalemiRead.model_validate(kalem, from_attributes=True) for kalem in kalemler]