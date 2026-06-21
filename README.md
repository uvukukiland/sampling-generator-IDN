<h1 align="center">🎯 Asisten Random Sampling Wilayah</h1>

<p align="center">
  Sampling otomatis wilayah dari database <b>MFD (Master File Desa)</b> BPS —
  untuk survei daerah, nasional, hingga quick count / exit poll.
</p>

<p align="center">
  <a href="https://github.com/uvukukiland/sampling-generator-IDN/actions/workflows/ci.yml"><img src="https://github.com/uvukukiland/sampling-generator-IDN/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-app-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License: MIT">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

Aplikasi ini menggantikan skrip sampling lama yang **"tidak semua wilayah bisa tersampling"**.
Di sini setiap wilayah dijamin tercakup lewat **alokasi proporsional dengan jaminan minimum**,
mengikuti kerangka sampling **SILOGNAS / SURNAS**.

## Daftar Isi
- [Fitur](#fitur)
- [Cara Menjalankan](#cara-menjalankan)
- [Alur Pemakaian](#alur-pemakaian)
- [Metodologi](#metodologi)
- [Dua Jenis Export](#dua-jenis-export)
- [Struktur Berkas](#struktur-berkas)
- [Pakai Engine Tanpa UI](#pakai-engine-tanpa-ui-opsional)
- [Catatan Data & Privasi](#catatan-data--privasi)
- [Lisensi](#lisensi)

---

## Fitur
- ✅ **Jaminan cakupan** — setiap wilayah pasti kebagian sampel (metode *largest-remainder* + minimum per wilayah).
- 🗺️ **Tiga cakupan**: Nasional (38 provinsi) · Provinsi · Kabupaten/Kota.
- 📍 **Dua unit sampling**: Desa/Kelurahan (titik/TPD) atau Kabupaten/Kota.
- ⚖️ **Basis alokasi gabungan**: Jumlah Penduduk · DPT · Jumlah Desa (MFD), dengan bobot yang bisa diatur.
- 🏙️ **Stratifikasi Kota/Desa** (kolom `UR`) + opsi **PPS** (peluang ~ ukuran wilayah).
- 🔁 **Reproducible** lewat *random seed*.
- 📄 **Template MFD & Referensi** siap unduh + **dua jenis export** (Hasil & format Kerangka).
- 🧹 **Loader tahan-banting** terhadap MFD dengan kolom tidak konsisten antar-sheet.
- 💻 **Lintas-platform**: Windows, macOS, Linux.

## Cara Menjalankan

Aplikasi berbasis **Python + Streamlit** sehingga jalan di Windows, macOS, dan Linux.

### Windows
Klik dua kali **`jalankan.bat`** → aplikasi terbuka otomatis di browser.

### macOS / Linux
Klik dua kali **`jalankan_mac.command`**.
- Pertama kali: **klik kanan → Open** (sekali, agar lolos Gatekeeper macOS).
- Bila belum bisa diklik: jalankan sekali `chmod +x jalankan_mac.command`.
- Butuh **Python 3** (`python3 --version`; pasang dari [python.org](https://www.python.org/downloads/) atau `brew install python`).
- Script otomatis membuat virtual environment `.venv` (sekali) lalu menjalankan aplikasi.

### Manual (semua OS)
```bash
pip install -r requirements.txt      # macOS: pip3 / dalam venv
streamlit run app.py                  # atau: python -m streamlit run app.py
```
Lalu buka alamat yang muncul (biasanya `http://localhost:8501`).

### Tanpa install
- **Jaringan lokal:** jalankan di satu komputer, buka *Network URL* (mis. `http://192.168.x.x:8501`) dari perangkat lain di Wi-Fi yang sama.
- **Streamlit Community Cloud (gratis):** hubungkan repo ini ke [share.streamlit.io](https://share.streamlit.io) → akses dari browser mana pun. Untuk data internal, andalkan fitur **unggah file** (jangan menaruh MFD/PII di repo).

### Docker (paling awet / reproducible)
Untuk arsip jangka panjang (Python + semua library dibekukan versinya):
```bash
docker build -t sampling-idn .
docker run -p 8501:8501 sampling-idn
# buka http://localhost:8501
```
Image memakai `requirements-lock.txt` (versi terkunci persis) di atas Python 3.12, sehingga dapat dibangun ulang dengan hasil identik bertahun-tahun ke depan.

## Alur Pemakaian
1. **Unggah MFD** (`.xlsx`) — tiap sheet = satu provinsi; kolom wajib `NMKAB`, `NMKEC`, `NMDESA`, `UR` (1=Kota, 2=Desa). Belum punya? Unduh **Template MFD** di panel kiri.
2. **Pilih preset** survei (Daerah 800 / Nasional 1200–1500 / Quick Count 2000+) atau Kustom.
3. **Atur cakupan & unit** (Nasional/Provinsi/Kabupaten · Desa/Kabupaten).
4. **Atur basis alokasi** (Penduduk/DPT/MFD, bobot bisa dikombinasi). Untuk MFD baru, unduh **Template Referensi** (sudah terisi), edit angka DPT/Penduduk, lalu unggah.
5. **Jalankan** → lihat Ringkasan, Sampel, Alokasi, Kerangka → **unduh Excel**.

## Metodologi
Sampling **multistage proporsional terstratifikasi**:

1. **Jumlah titik (TPD)** = ⌈target responden ÷ responden per titik⌉ — mis. 1200 ÷ 10 = 120 titik.
2. **Alokasi antar wilayah** (provinsi → kab/kota → kecamatan) **proporsional** terhadap ukuran (Penduduk/DPT/jumlah desa), memakai **largest-remainder (Hamilton)** agar totalnya **persis** & tak ada wilayah ter-skip.
3. **Jaminan minimum** (`min_per_unit`, default 1) → tiap wilayah primer dapat ≥1 titik. **Inilah perbaikan utama** atas skrip lama.
4. **Stratifikasi Kota/Desa** (`UR`): jatah titik dipecah Perkotaan vs Perdesaan proporsional jumlah kota/desa.
5. **Seleksi acak** desa/kelurahan tiap strata (reproducible via seed; mode kabupaten mendukung PPS).

> **Mengapa "semua wilayah tersampling"?** Skrip lama hanya memproses satu sheet & satu kategori lalu mengisi sisa dengan interval, sehingga banyak wilayah tak pernah masuk. Engine ini memproses **seluruh 38 provinsi sekaligus**, mengalokasikan dengan **floor minimum + largest remainder**, dan **melaporkan** bila ada wilayah yang tak tercukupi (banner cakupan & tab *Catatan*).

## Dua Jenis Export
| Export | Isi |
|---|---|
| **Hasil Sampel** (`hasil_sampel_*.xlsx`) | Sheet *Ringkasan*, *Sampel* (daftar titik/desa terpilih siap lapangan), *Alokasi*. |
| **Format Kerangka** (`kerangka_*.xlsx`) | Rekap per wilayah ala **SILOGNAS SURNAS**: DPT, %, Penduduk, %, jumlah Kota/Desa (MFD), titik & responden per strata, TPD, + baris **TOTAL**. |

## Struktur Berkas
| Berkas | Fungsi |
|---|---|
| `app.py` | Antarmuka Streamlit |
| `sampling_engine.py` | Mesin sampling (loader, alokasi, seleksi) — bisa dipakai terpisah |
| `data/referensi_provinsi.csv` | Referensi DPT & Penduduk per provinsi — bisa ditimpa lewat unggahan |
| `requirements.txt` | Dependensi Python |
| `jalankan.bat` | Launcher Windows (klik dua kali) |
| `jalankan_mac.command` | Launcher macOS/Linux (klik dua kali) |
| `requirements-lock.txt` | Versi terkunci persis (dipakai Docker) |
| `Dockerfile` | Image reproducible (Python 3.12 + library terkunci) |

> File MFD (`mfd 2024.xlsx`) **tidak disertakan** di repo — unggah lewat aplikasi saat dipakai.

## Pakai Engine Tanpa UI (opsional)
```python
import pandas as pd, sampling_engine as E

df, info = E.load_mfd("mfd 2024.xlsx")
df, _ = E.attach_reference(df, pd.read_csv("data/referensi_provinsi.csv"))

cfg = E.SamplingConfig(
    scope="NASIONAL", unit="DESA", n_total=1200, cluster_size=10,
    weights={"PENDUDUK": 0.7, "DPT": 0.3, "MFD": 0.0},
    stratify_ur=True, min_per_unit=1, seed=2024,
)
res = E.run_sampling(df, cfg)
res.sample.to_excel("hasil_sampling.xlsx", index=False)
print(res.ringkasan)
```

## Catatan Data & Privasi
- Jangan menaruh file MFD/responden ber-**data pribadi** ke repo (apalagi publik). `.gitignore` sudah memblokir `*.xlsx`, `*.xls`, `*.zip`.
- Untuk berbagi aplikasi, andalkan fitur **unggah file** di antarmuka, bukan menyimpan data di repo.

## Keawetan Jangka Panjang
Agar app tetap jalan bertahun-tahun tanpa kejutan:
- **Versi dikunci** — `requirements.txt` memberi batas atas (`<major berikutnya`) supaya update besar yang merusak tidak ikut terpasang.
- **API terbaru** — tidak memakai API Streamlit yang sudah usang (memakai `width="stretch"`, bukan `use_container_width`).
- **Reproducible penuh** — `Dockerfile` + `requirements-lock.txt` membekukan Python 3.12 dan versi library persis; PyPI menyimpan versi lama selamanya sehingga dapat dibangun ulang kapan pun.

**Tested with:** Python 3.12–3.14 · Streamlit 1.58 · pandas 2.2 / 3.0 · numpy 2.x · openpyxl 3.1 · XlsxWriter 3.2.

> Catatan jujur: "10 tahun tanpa disentuh" paling terjamin lewat **Docker** (Python ikut dibekukan). Tanpa Docker, app tetap bergantung pada versi Python di komputer; pin `requirements.txt` sudah meminimalkan risiko, tapi pembaruan Python sistem suatu saat bisa menuntut penyesuaian kecil.

## Lisensi
Dirilis di bawah **[MIT License](LICENSE)** © 2026 uvukukiland.
