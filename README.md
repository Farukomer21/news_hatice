# 📰 Universal News Collection & NLP Data Pipeline

Bu proje; **Türkiye, Almanya ve Rusya** odaklı 43 farklı turizm ve ekonomi haber kaynağından **günlük haberleri ve tam haber metinlerini (full body text)** otomatik olarak toplamak, temizlemek ve Doğal Dil İşleme (NLP) modelleri / veri analizi sistemleri için JSON formatında sunmak üzere tasarlanmıştır.

Sistem, her gün çalıştırıldığı zaman diliminde **TSİ gece 00:00:00'dan itibaren** yayınlanan taze haberleri süzerek veri kaybını önler ve güncel habercilik verisini filtreler.

---

## 🔄 Detaylı Veri Akışı ve Mimari (Data Flow)

Projedeki veri toplama ve işleme süreci adım adım şu şekilde gerçekleşmektedir:

```
┌─────────────────────────┐
│  43 Hedef Domain Listesi│
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  1. Google News RSS     │  --> Query: "site:{domain} when:1d"
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  2. TSİ Gece 00:00      │  --> RSS <pubDate> parsing (RFC 2822 -> TSİ UTC+3)
│     Tarih Filtresi      │  --> TSİ 00:00 öncesi yayınlar elenir.
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  3. Google News Link    │  --> "googlenewsdecoder" (new_decoderv1) ile
│     Çözümleme (Decode)  │      şifreli yönlendirme linki gerçek URL'e dönüştürülür.
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  4. Tam Metin Çıkarma   │  --> "trafilatura" kütüphanesi ile haber sitesine
│     (Text Extraction)   │      bağlanılır; reklam, menü vb. ayıklanıp gövde metni çekilir.
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  5. Çift Formatlı       │  --> news_list.json (Düz Array)
│     JSON Çıktısı        │  --> news_output.json (Kategorili Yapı)
└─────────────────────────┘
```

### Adım Adım İşleyiş Mekanizması:

1. **Google News RSS Sorgusu (Query Generation)**:
   - `TARGET_DOMAINS_BY_CATEGORY` sözlüğündeki her bir alan adı için ülkeye özel dil ve bölge parametreleri (`hl`, `gl`, `ceid`) ayarlanarak `https://news.google.com/rss/search?q=site:{domain}+when:1d` adresine HTTP isteği atılır.

2. **TSİ (UTC+3) Tarih Dönüşümü ve Bugün Filtreleme**:
   - RSS içerisindeki her bir haberin `<pubDate>` etiketi (ör: `Wed, 12 Aug 2026 06:17:00 GMT`) okunur.
   - `email.utils.parsedate_to_datetime` ve `datetime` kullanılarak zaman dilimi **Türkiye Standardı Zaman Dilimine (TSİ / UTC+3)** dönüştürülür.
   - Haber yayın tarihi, içinde bulunulan günün TSİ **gece 00:00:00** anından önce ise haber işleme alınmaz (elenir). Böylece tam olarak "bugünün haberleri" elde edilir.

3. **Google News Yönlendirme Linkinin Çözülmesi (URL Decoding)**:
   - Google News RSS servisinin döndürdüğü linkler doğrudan sitenin adresi değildir (`https://news.google.com/rss/articles/...` şeklinde şifrelenmiştir).
   - `googlenewsdecoder` (`new_decoderv1`) kullanılarak bu bağlantı çözümlenir ve haberin orijinal yayınlandığı gerçek web adresi (`real_url`) elde edilir.

4. **Web Sitesine Bağlanma ve Tam Gövde Metni Çıkarma (Full Body Extraction)**:
   - Gerçek haber URL'sine `trafilatura.fetch_url(real_url)` ile bağlanılır.
   - `trafilatura.extract(...)` motoru çalıştırılarak haber sayfasındaki reklamlar, menüler, footer metinleri ve yorumlar temizlenir; haberin **orijinal gövde metni (full text)** çıkarılır.

5. **JSON Kaydı**:
   - İşlenen haberler hem kategorize edilmiş özet formatta (`news_output.json`) hem de doğrudan dizi olarak okunabilecek düz liste formatında (`news_list.json`) kaydedilir.

---

## 📊 JSON Veri Yapısı ve Örnek Haber Çıktısı

Üretilen `news_list.json` dosyasında yer alan tek bir haber nesnesinin JSON yapısı aşağıdaki gibidir:

```json
{
    "category": "turkey_economy",
    "domain": "bloomberght.com",
    "title": "Fed üyelerinden yeni enflasyon uyarıları - Bloomberght",
    "google_link": "https://news.google.com/rss/articles/CBMijAFBVV95cUxQWTBOTTFaTDVvLVpXVjVOMDNKQmFKTzdsaldrOWNuSEZZZUZiV0NKOG9CcEdXUV9EUWJHdVZOMnFTSl8wNmpxbHBBOEFOUUtGZGh6aEpMVmtxb25GdW1YeUFDR1VmX0hORWJiR3pzcWxWRS1ySlN1S0dwUEHdzg8czFNWHVJTXV0MjN2Qg?oc=5",
    "url": "https://www.bloomberght.com/fed-uyelerinden-yeni-enflasyon-uyarilari-3785240",
    "pub_date_raw": "Wed, 12 Aug 2026 06:40:43 GMT",
    "pub_date_tsi": "2026-08-12 09:40:43 TSİ",
    "pub_timestamp_iso": "2026-08-12T09:40:43+03:00",
    "full_text_length": 1540,
    "full_text": "Federal Reserve yetkilileri yaptıkları son değerlendirmelerde enflasyon baskılarının devam edebileceği uyarısında bulundu...\n\n(Haberin tam gövde metni)..."
}
```

### Alan Açıklamaları:

- **`category`**: Haberin ait olduğu kategori adı (`antalya_news`, `turkey_tourism`, `turkey_economy`, `germany_tourism`, `germany_economy`, `russia_tourism`, `russia_economy`).
- **`domain`**: Haberin yayınlandığı web sitesinin alan adı.
- **`title`**: Haberin başlığı.
- **`google_link`**: Google News yönlendirme köprüsü.
- **`url`**: Çözümlenmiş gerçek haber kaynağı adresi.
- **`pub_date_raw`**: RSS servisinde yer alan ham RFC 2822 yayın tarihi.
- **`pub_date_tsi`**: Okunabilir TSİ tarih ve saat string ifadesi (`YYYY-MM-DD HH:MM:SS TSİ`).
- **`pub_timestamp_iso`**: ISO-8601 standart zaman damgası.
- **`full_text_length`**: Çekilen haber tam metninin karakter uzunluğu.
- **`full_text`**: Sayfadan çekilen temizlenmiş tam metin (full body text).

---

## 🌐 Desteklenen Kaynaklar (43 Adet Benzersiz Domain)

### 🇹🇷 Türkiye
- **Antalya Yerel Haber:** `akdenizgercek.com.tr`, `akdenizmanset.com.tr`, `antalyanews.com.tr`, `gunhaber.com.tr`, `lidergazete.com`, `nehir.net`, `turizmdays.com`, `turizmgazetesi.com`, `turizmguncel.com`, `yenialanya.com`
- **Turizm Odaklı:** `turizmguncel.com`, `turizmgazetesi.com`, `turizmajansi.com`, `gmdergi.com`, `tourexpi.com`, `turizmgunlugu.com`, `tourismtoday.net`, `turizmaktuel.com`, `turizmnews.com`, `turizmekonomi.com`, `turizminsesi.com`, `turizmdosyasi.com`
- **Ekonomi Odaklı:** `bloomberght.com`, `ekonomim.com`, `news.foreks.com`, `paraanaliz.com`, `tr.investing.com`, `sabah.com.tr`, `milliyet.com.tr`

### 🇩🇪 Almanya
- **Turizm Odaklı:** `fvw.de`, `touristik-aktuell.de`, `reisevor9.de`, `travelone.de`, `trvlcounter.de`, `travelbook.de`, `germany.travel`
- **Ekonomi Odaklı:** `handelsblatt.com`, `wiwo.de`, `boersen-zeitung.de`, `finanzen.net`, `manager-magazin.de`

### 🇷🇺 Rusya
- **Turizm Odaklı:** `atorus.ru`, `tourdom.ru`, `profi.travel`, `ratanews.ru`, `trn-news.ru`, `interfax-russia.ru`
- **Ekonomi Odaklı:** `rbc.ru`, `kommersant.ru`, `vedomosti.ru`, `forbes.ru`, `finmarket.ru`, `interfax.ru`

---

## 📁 Proje Yapısı

- **`rss_news_fetch.py`**: **Giriş noktası.** Yayıncı RSS beslemelerini birincil kaynak olarak kullanan toplayıcı; çıktıları `rss_news_output.json` ve `rss_news_list.json` dosyalarına kaydeder.
- **`news_fetch.py`**: Ortak parçalar — TSİ zaman yardımcıları, kaynak listesi (`TARGET_DOMAINS_BY_CATEGORY`) ve RSS'i olmayan kaynaklar için Google News yedek yolu (`UniversalGoogleNewsScraper`). Tek başına çalıştırılmaz.
- **`rapor_tablo.py`**: Toplanan haberlerin kaynak bazlı sayı/başarı tablosunu üretir.
- **`requirements.txt`**: Proje için gerekli Python kütüphanelerinin listesi.

---

## 🚀 Kurulum ve Kullanım

### 1. Bağımlılıkları Yükleyin

```bash
pip install -r requirements.txt
```

### 2. Haber Çekme Betiğini Çalıştırın

```bash
python3 rss_news_fetch.py
```

### 3. Çıktı Dosyaları

- **`rss_news_list.json`**: Doğrudan `json.load()` ile okunup kullanılabilen düz haber dizisi.
- **`rss_news_output.json`**: Kategorilere ve domainlere göre gruplanmış, tanı raporu (`diagnostics`) da içeren JSON verisi.

### 4. Kaynak Bazlı Rapor

```bash
python3 rapor_tablo.py --csv kaynak_tablosu.csv
```
