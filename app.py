"""
Asisten Random Sampling — Aplikasi Streamlit
============================================
Sampling otomatis wilayah dari database MFD (Master File Desa) BPS untuk
survei daerah, nasional, hingga quick count / exit poll.

Jalankan:  streamlit run app.py
"""
from __future__ import annotations

import io
import os

import pandas as pd
import streamlit as st

import sampling_engine as E

BASE = os.path.dirname(os.path.abspath(__file__))
REF_PATH = os.path.join(BASE, "data", "referensi_provinsi.csv")
DEFAULT_MFD = os.path.join(BASE, "mfd 2024.xlsx")

st.set_page_config(page_title="Asisten Random Sampling", page_icon="🎯", layout="wide")

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Memuat & membersihkan MFD...")
def _load_mfd(file_bytes: bytes | None, path: str | None):
    src = io.BytesIO(file_bytes) if file_bytes is not None else path
    return E.load_mfd(src)


@st.cache_data
def _read_ref(file_bytes: bytes, filename: str) -> pd.DataFrame:
    return E.read_reference(file_bytes, filename)


def _pick_excel_engine() -> str:
    """xlsxwriter lebih andal pada pandas 3.0 (openpyxl punya bug multi-sheet)."""
    try:
        import xlsxwriter  # noqa: F401
        return "xlsxwriter"
    except Exception:
        return "openpyxl"


def _sheets_to_excel(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Tulis beberapa DataFrame ke satu file Excel (multi-sheet)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine=_pick_excel_engine()) as xw:
        for name, d in sheets.items():
            d.to_excel(xw, sheet_name=name[:31], index=False)
    return buf.getvalue()


@st.cache_data
def _to_excel(sample: pd.DataFrame, alokasi: pd.DataFrame, ringkasan: pd.DataFrame) -> bytes:
    return _sheets_to_excel({"Ringkasan": ringkasan, "Sampel": sample, "Alokasi": alokasi})


@st.cache_data
def _to_excel_kerangka(recap: pd.DataFrame, ringkasan: pd.DataFrame) -> bytes:
    return _sheets_to_excel({"Kerangka": recap, "Ringkasan": ringkasan})


@st.cache_data
def _template_bytes() -> bytes:
    return _sheets_to_excel(E.build_template())


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🎯 Asisten Random Sampling Wilayah")
st.caption(
    "Sampling multistage berbasis MFD (Master File Desa) BPS — proporsional, "
    "terstratifikasi Kota/Desa, dengan **jaminan semua wilayah tersampling**."
)

# ---------------------------------------------------------------------------
# Sumber data
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("1. Database MFD")
    up = st.file_uploader("Unggah file MFD (.xlsx)", type=["xlsx", "xls"])
    use_default = False
    if up is None and os.path.exists(DEFAULT_MFD):
        use_default = st.checkbox(f"Pakai file bawaan: {os.path.basename(DEFAULT_MFD)}", value=True)

    st.caption("Belum punya MFD? Unduh template kosong, isi, lalu unggah di atas.")
    st.download_button(
        "📄 Unduh Template MFD (kosong)",
        data=_template_bytes(),
        file_name="template_mfd.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()
    st.header("2. Referensi DPT & Penduduk")
    ref_up = st.file_uploader("Unggah referensi (opsional, .xlsx/.csv)", type=["xlsx", "xls", "csv"])
    st.caption("Tanpa unggahan, dipakai data bawaan. Untuk MFD baru, unduh template "
               "(sudah terisi nilai saat ini), edit angkanya, lalu unggah.")

if up is None and not use_default:
    st.info("⬅️ Unggah file MFD (.xlsx) di panel kiri untuk mulai. "
            "Tiap sheet = satu provinsi, dengan kolom NMKAB, NMKEC, NMDESA, UR (1=Kota, 2=Desa).")
    st.stop()

try:
    df, info = _load_mfd(up.getvalue() if up else None, None if up else DEFAULT_MFD)
except Exception as e:
    st.error(f"Gagal memuat MFD: {e}")
    st.stop()

# --- referensi DPT/Penduduk: unggahan > bawaan ---
ref_df = None
ref_src = ""
if ref_up is not None:
    try:
        ref_df = _read_ref(ref_up.getvalue(), ref_up.name)
        ref_src = f"unggahan ({ref_up.name})"
    except Exception as e:
        st.error(f"Gagal membaca referensi: {e}")
        st.stop()
elif os.path.exists(REF_PATH):
    ref_df = pd.read_csv(REF_PATH)
    ref_src = "bawaan (data/referensi_provinsi.csv)"

unmatched = []
if ref_df is not None:
    df, unmatched = E.attach_reference(df, ref_df)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Provinsi", info["n_provinsi"])
c2.metric("Kab/Kota", int(info["n_kabupaten"]))
c3.metric("Desa/Kelurahan", f"{info['n_desa']:,}")
c4.metric("Kota : Desa", f"{info['n_kota']:,} : {info['n_desa_rural']:,}")
if info["baris_dibuang"]:
    st.caption(f"ℹ️ {info['baris_dibuang']} baris tak valid (header/kosong) otomatis dibersihkan.")

# template referensi (terisi nilai saat ini) + status
with st.sidebar:
    st.download_button(
        "📄 Unduh Template Referensi",
        data=_sheets_to_excel(E.build_reference_template(ref_df)),
        file_name="template_referensi_dpt_penduduk.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        help="Berisi 38 provinsi terisi nilai saat ini — tinggal edit angkanya.",
    )

has_pop = "PENDUDUK" in df.columns
has_dpt = "DPT" in df.columns
has_ref = has_pop or has_dpt
if ref_src:
    note = f"Referensi alokasi: **{ref_src}**."
    if unmatched:
        note += f" ⚠️ {len(unmatched)} provinsi MFD tak cocok di referensi: " \
                f"{', '.join(unmatched[:6])}{'…' if len(unmatched) > 6 else ''} " \
                f"(alokasinya otomatis memakai basis lain)."
    st.caption(note)

# ---------------------------------------------------------------------------
# Parameter survei
# ---------------------------------------------------------------------------
st.header("2. Rancang Sampling")

PRESETS = {
    "Survei Daerah (Kab/Kota) — 800": dict(scope="KABUPATEN", unit="DESA", n_total=800, cluster=10),
    "Survei Provinsi — 1200": dict(scope="PROVINSI", unit="DESA", n_total=1200, cluster=10),
    "Survei Nasional — 1200": dict(scope="NASIONAL", unit="DESA", n_total=1200, cluster=10),
    "Survei Nasional — 1500": dict(scope="NASIONAL", unit="DESA", n_total=1500, cluster=10),
    "Quick Count / Exit Poll — 2000+": dict(scope="NASIONAL", unit="DESA", n_total=3000, cluster=5),
    "Kustom": dict(scope="NASIONAL", unit="DESA", n_total=1200, cluster=10),
}
preset_name = st.selectbox("Preset jenis survei", list(PRESETS.keys()))
P = PRESETS[preset_name]

colA, colB = st.columns(2)
with colA:
    scope = st.radio(
        "Cakupan survei",
        ["NASIONAL", "PROVINSI", "KABUPATEN"],
        index=["NASIONAL", "PROVINSI", "KABUPATEN"].index(P["scope"]),
        horizontal=True,
        help="NASIONAL: 38 provinsi. PROVINSI: pilih 1+ provinsi. KABUPATEN: pilih 1+ kab/kota.",
    )
    unit = st.radio(
        "Unit yang disampling (titik akhir)",
        ["DESA", "KABUPATEN"],
        index=["DESA", "KABUPATEN"].index(P["unit"]),
        horizontal=True,
        format_func=lambda x: "Desa/Kelurahan" if x == "DESA" else "Kabupaten/Kota",
    )

scope_filter: list[str] = []
with colB:
    if scope == "PROVINSI":
        provs = sorted(df["NMPROP"].unique())
        scope_filter = st.multiselect("Pilih provinsi", provs, default=provs[:1])
    elif scope == "KABUPATEN":
        provs = sorted(df["NMPROP"].unique())
        pv = st.selectbox("Provinsi", provs)
        kabs = sorted(df[df["NMPROP"] == pv]["NMKAB"].unique())
        scope_filter = st.multiselect("Pilih kabupaten/kota", kabs, default=kabs[:1])
    else:
        st.success("Cakupan: seluruh 38 provinsi.")

# jumlah & cluster
colC, colD, colE = st.columns(3)
if unit == "DESA":
    n_total = colC.number_input("Target responden", min_value=10, value=int(P["n_total"]), step=50)
    cluster = colD.number_input("Responden per titik (cluster)", min_value=1, value=int(P["cluster"]), step=1)
    n_titik = -(-n_total // cluster)
    colE.metric("Jumlah titik (TPD)", n_titik)
else:
    n_total = colC.number_input("Jumlah kab/kota yang disampling", min_value=1, value=50, step=5)
    cluster = 1
    colD.caption("Mode kabupaten: tiap unit = 1 kab/kota.")
    pps = colE.checkbox("Seleksi PPS (peluang ~ jumlah desa)", value=True)

# ---------------------------------------------------------------------------
# Basis alokasi (kombinasi)
# ---------------------------------------------------------------------------
st.subheader("Basis alokasi proporsional")
if not has_ref:
    st.warning("Data Penduduk/DPT tidak tersedia — alokasi memakai jumlah desa MFD. "
               "Unggah referensi di panel kiri untuk basis Penduduk/DPT.")
colF, colG, colH = st.columns(3)
w_pop = colF.slider("Bobot Jumlah Penduduk", 0.0, 1.0, 1.0 if has_pop else 0.0, 0.1,
                    disabled=not has_pop, help=None if has_pop else "Kolom PENDUDUK tak ada di referensi.")
w_dpt = colG.slider("Bobot DPT", 0.0, 1.0, 0.0, 0.1,
                    disabled=not has_dpt, help=None if has_dpt else "Kolom DPT tak ada di referensi.")
w_mfd = colH.slider("Bobot Jumlah Desa (MFD)", 0.0, 1.0, 0.0 if has_ref else 1.0, 0.1)
wsum = w_pop + w_dpt + w_mfd
if wsum == 0:
    st.error("Minimal satu bobot basis alokasi harus > 0.")
    st.stop()
st.caption(f"Komposisi efektif → Penduduk {w_pop/wsum:.0%} · DPT {w_dpt/wsum:.0%} · MFD {w_mfd/wsum:.0%}")

# ---------------------------------------------------------------------------
# Opsi lanjutan
# ---------------------------------------------------------------------------
with st.expander("⚙️ Opsi lanjutan"):
    colI, colJ, colK = st.columns(3)
    stratify = colI.checkbox("Stratifikasi Kota/Desa (UR)", value=True,
                             disabled=(unit == "KABUPATEN"))
    lvlname = {"NASIONAL": "provinsi", "PROVINSI": "kab/kota", "KABUPATEN": "kecamatan"}[scope]
    min_per = colJ.number_input(
        f"Minimum titik/unit per {lvlname} (jaminan cakupan)",
        min_value=0, value=1, step=1,
        help="Inti perbaikan: ≥1 menjamin tiap wilayah pasti tersampling.")
    seed = colK.number_input("Random seed (reproducible)", min_value=0, value=2024, step=1)

# ---------------------------------------------------------------------------
# Jalankan
# ---------------------------------------------------------------------------
st.header("3. Jalankan")
if scope in ("PROVINSI", "KABUPATEN") and not scope_filter:
    st.warning("Pilih minimal satu wilayah pada cakupan terpilih.")
    st.stop()

if st.button("🚀 Lakukan Sampling", type="primary", use_container_width=True):
    cfg = E.SamplingConfig(
        scope=scope,
        scope_filter=scope_filter,
        unit=unit,
        n_total=int(n_total),
        cluster_size=int(cluster),
        weights={"PENDUDUK": w_pop, "DPT": w_dpt, "MFD": w_mfd},
        stratify_ur=bool(stratify) if unit == "DESA" else False,
        min_per_unit=int(min_per),
        pps=bool(pps) if unit == "KABUPATEN" else False,
        seed=int(seed),
    )
    try:
        res = E.run_sampling(df, cfg)
    except Exception as e:
        st.error(f"Gagal sampling: {e}")
        st.stop()

    recap = E.build_kerangka_recap(df, res, cfg)
    st.session_state["res"] = res
    st.session_state["recap"] = recap
    st.session_state["res_xlsx"] = _to_excel(res.sample, res.alokasi, res.ringkasan)
    st.session_state["kerangka_xlsx"] = _to_excel_kerangka(recap, res.ringkasan)
    st.session_state["fname"] = f"{scope.lower()}_{int(n_total)}"

# ---------------------------------------------------------------------------
# Hasil
# ---------------------------------------------------------------------------
if "res" in st.session_state:
    res: E.SamplingResult = st.session_state["res"]
    st.header("4. Hasil")

    # banner cakupan
    cov = res.coverage
    if cov.get("unit") == "DESA":
        ok = len(cov["unit_tidak_tercakup"]) == 0
        msg = (f"✅ Semua {cov['unit_total']} {cov['level']} tercakup."
               if ok else
               f"⚠️ {len(cov['unit_tidak_tercakup'])} {cov['level']} TIDAK tercakup: "
               f"{', '.join(map(str, cov['unit_tidak_tercakup'][:10]))}…")
        (st.success if ok else st.warning)(msg)

    tab1, tab2, tab3, tab5, tab4 = st.tabs(
        ["📋 Ringkasan", "📍 Sampel", "📊 Alokasi", "🗂️ Kerangka", "⚠️ Catatan"])
    with tab1:
        st.dataframe(res.ringkasan, use_container_width=True, hide_index=True)
        if len(res.sample) and "URLABEL" in res.sample:
            st.bar_chart(res.sample["NMPROP"].value_counts())
    with tab2:
        show_cols = [c for c in ["ID", "NMPROP", "NMKAB", "NMKEC", "NMDESA", "URLABEL", "RESPONDEN"]
                     if c in res.sample.columns]
        st.dataframe(res.sample[show_cols] if show_cols else res.sample,
                     use_container_width=True, height=420)
    with tab3:
        st.dataframe(res.alokasi, use_container_width=True, hide_index=True, height=420)
    with tab5:
        st.caption("Rekap alokasi format SILOGNAS SURNAS (per wilayah, DPT/Penduduk, "
                   "Kota/Desa, titik & responden, TPD).")
        st.dataframe(st.session_state["recap"].astype(str), use_container_width=True,
                     hide_index=True, height=420)  # cast utk tampilan; Excel tetap numerik
    with tab4:
        if res.warnings:
            for w in res.warnings:
                st.warning(w)
        else:
            st.success("Tidak ada peringatan. Semua permintaan terpenuhi.")

    st.subheader("Unduh hasil")
    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    fn = st.session_state.get("fname", "sampling")
    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "⬇️ Hasil Sampel (Excel)",
            data=st.session_state["res_xlsx"],
            file_name=f"hasil_sampel_{fn}.xlsx",
            mime=XLSX, type="primary", use_container_width=True,
            help="Berisi sheet: Ringkasan, Sampel (daftar titik terpilih), Alokasi.",
        )
    with dl2:
        st.download_button(
            "⬇️ Format Kerangka (Excel)",
            data=st.session_state["kerangka_xlsx"],
            file_name=f"kerangka_{fn}.xlsx",
            mime=XLSX, use_container_width=True,
            help="Rekap alokasi per wilayah ala SILOGNAS SURNAS + Ringkasan.",
        )

st.divider()
st.caption("Asisten Random Sampling • Populi Center • metode multistage proporsional "
           "largest-remainder dengan jaminan cakupan minimum.")
