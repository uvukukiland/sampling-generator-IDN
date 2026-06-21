# 🎯 Asisten Random Sampling Wilayah

Aplikasi untuk **otomatis mensampling wilayah** dari database **MFD (Master File Desa)** BPS,
sesuai kebutuhan survei: daerah (kab/kota), provinsi, nasional, hingga **quick count / exit poll**.

Menggantikan skrip Colab lama yang **"tidak semua wilayah bisa tersampling"** — di sini setiap
wilayah dijamin tercakup lewat alokasi proporsional dengan **jaminan minimum**.

---

## Cara menjalankan

Aplikasi ini **lintas-platform** (Windows, macOS, Linux) karena berbasis Python + Streamlit.

### Windows
Klik dua kali **`jalankan.bat`**. Aplikasi terbuka otomatis di browser.

### macOS / Linux
Klik dua kali **`jalankan_mac.command`**.
- Pertama kali, macOS mungkin menahan file dari sumber tak dikenal → **klik kanan → Open** (sekali saja).
- Jika belum bisa diklik, jalankan sekali di Terminal: `chmod +x jalankan_mac.command`.
- Butuh **Python 3** (cek: `python3 --version`; bila belum ada, pasang dari python.org atau `brew install python`).
- Script otomatis membuat virtual environment `.venv` (sekali saja) lalu menjalankan aplikasi.

### Cara manual (semua OS)
```bash
pip install -r requirements.txt        # macOS: pakai pip3 / dalam venv
streamlit run app.py                    # atau: python -m streamlit run app.py
```
Lalu buka alamat yang muncul (biasanya `http://localhost:8501`).

### Alternatif tanpa install
- **Akses dari perangkat lain di jaringan yang sama:** jalankan di satu komputer, lalu buka *Network URL*
  yang ditampilkan Streamlit (mis. `http://192.168.x.x:8501`) dari MacBook/HP di Wi-Fi yang sama.
- **Streamlit Community Cloud (gratis):** unggah folder ini ke repo GitHub, hubungkan ke
  [share.streamlit.io](https://share.streamlit.io) → aplikasi dapat diakses dari browser mana pun
  tanpa install. (Catatan: bila MFD/referensi bersifat internal, andalkan fitur **unggah file**
  alih-alih menyertakan data ke repo publik.)

---

## Alur pemakaian

1. **Unggah MFD** (`.xlsx`) — atau pakai file bawaan `mfd 2024.xlsx`.
   Tiap sheet = satu provinsi; kolom wajib: `NMKAB`, `NMKEC`, `NMDESA`, `UR` (1=Kota, 2=Desa).
   Belum punya MFD? Klik **"Unduh Template MFD (kosong)"** di panel kiri, isi sesuai
   lembar *Petunjuk*, lalu unggah kembali. (Template memakai format **satu sheet gabungan**
   dengan kolom `NMPROP`; loader juga tetap menerima format per-provinsi/sheet.)
2. **Pilih preset** survei (Daerah 800 / Nasional 1200–1500 / Quick Count 2000+) atau Kustom.
3. **Atur cakupan & unit**:
   - Cakupan: Nasional · Provinsi · Kabupaten/Kota
   - Unit titik akhir: **Desa/Kelurahan** atau **Kabupaten/Kota**
4. **Atur basis alokasi** (bisa dikombinasikan dengan bobot): Jumlah Penduduk · DPT · Jumlah Desa (MFD).
   Data Penduduk/DPT memakai referensi bawaan; untuk MFD baru, unduh **"Template Referensi"**
   (sudah terisi 38 provinsi), edit angkanya, lalu **unggah** di panel kiri. Nama kolom fleksibel
   (`NMPROP`/`Provinsi`, `DPT`/`Jumlah DPT`, `PENDUDUK`/`Jumlah Penduduk`). Provinsi yang tak cocok
   akan diberitahukan & alokasinya otomatis memakai basis lain.
5. **Jalankan** → lihat ringkasan, daftar sampel, tabel alokasi & kerangka, lalu **unduh Excel**.

### Dua jenis export
- **Hasil Sampel** (`hasil_sampel_*.xlsx`) — sheet *Ringkasan*, *Sampel* (daftar titik/desa
  terpilih siap lapangan), *Alokasi*.
- **Format Kerangka** (`kerangka_*.xlsx`) — rekap alokasi per wilayah menyerupai
  **SILOGNAS SURNAS**: DPT, Penduduk, jumlah Kota/Desa (MFD), titik & responden per strata,
  dan TPD, lengkap dengan baris TOTAL.

---

## Metodologi

Sampling **multistage proporsional terstratifikasi**, mengikuti kerangka SILOGNAS/SURNAS:

1. **Jumlah titik (TPD)** = ⌈target responden ÷ responden per titik⌉.
   Contoh: 1200 responden ÷ 10 = 120 titik.
2. **Alokasi antar wilayah primer** (provinsi → kab/kota → kecamatan, sesuai cakupan) secara
   **proporsional** terhadap ukuran (Penduduk/DPT/jumlah desa), memakai metode
   **largest-remainder (Hamilton)** sehingga totalnya **persis** dan tidak ada wilayah ter-skip.
3. **Jaminan minimum** (`min_per_unit`, default 1) → tiap wilayah primer pasti kebagian ≥1 titik.
   **Inilah perbaikan utama** atas skrip lama.
4. **Stratifikasi Kota/Desa** (kolom `UR`): jatah titik tiap wilayah dipecah Perkotaan vs
   Perdesaan proporsional jumlah kota/desa.
5. **Seleksi acak** desa/kelurahan dalam tiap strata (reproducible via *random seed*).
   Mode kabupaten mendukung **PPS** (peluang sebanding jumlah desa).

### Mengapa "semua wilayah tersampling"
Skrip lama hanya memproses satu sheet & satu kategori, lalu mengisi sisa dengan interval —
banyak wilayah tidak pernah masuk. Engine ini memproses **seluruh 38 provinsi sekaligus**,
mengalokasikan dengan **floor minimum + largest remainder**, dan **melaporkan** bila ada
wilayah yang tak tercukupi (lihat tab *Catatan* & banner cakupan).

---

## Struktur berkas

| Berkas | Fungsi |
|---|---|
| `app.py` | Antarmuka Streamlit |
| `sampling_engine.py` | Mesin sampling (loader, alokasi, seleksi) — bisa dipakai terpisah |
| `data/referensi_provinsi.csv` | Referensi DPT & Penduduk per provinsi (dari Kerangka SILOGNAS) — bisa ditimpa lewat unggahan |
| `mfd 2024.xlsx` | Database MFD bawaan |
| `requirements.txt` | Dependensi Python |
| `jalankan.bat` | Launcher Windows (klik dua kali) |
| `jalankan_mac.command` | Launcher macOS/Linux (klik dua kali) |

---

## Pakai engine tanpa UI (opsional)

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
