"""
sampling_engine.py
==================
Mesin sampling wilayah multistage berbasis MFD (Master File Desa) BPS.

Dirancang untuk Asisten Random Sampling (Populi Center / SILOGNAS).
Memperbaiki kelemahan skrip lama yang "tidak semua wilayah bisa tersampling":
  * Alokasi proporsional antar provinsi/wilayah dengan JAMINAN MINIMUM
    (metode largest-remainder/Hamilton) -> setiap wilayah pasti kebagian.
  * Basis alokasi bisa dikombinasikan: Jumlah Penduduk, DPT, dan jumlah
    desa/kelurahan MFD (dengan bobot).
  * Stratifikasi Perkotaan (Kota/Urban) vs Perdesaan (Desa/Rural) via kolom UR.
  * Loader MFD yang toleran terhadap sheet dengan kolom tidak konsisten.
  * Reproducible via random seed.

Penulis: Asisten Claude untuk Populi Center.
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Konstanta
# ---------------------------------------------------------------------------
UR_LABEL = {1: "Perkotaan", 2: "Perdesaan"}
NAME_COLS = ["NMKAB", "NMKEC", "NMDESA"]
CODE_COLS = ["KODEPROP", "KAB", "KEC", "DESA"]

LEVEL_COL = {
    "NASIONAL": "NMPROP",   # alokasi antar provinsi
    "PROVINSI": "NMKAB",    # alokasi antar kabupaten/kota dlm provinsi terpilih
    "KABUPATEN": "NMKEC",   # alokasi antar kecamatan dlm kab/kota terpilih
}


def _clean_prov(sheet_name: str) -> str:
    """Ambil nama provinsi bersih dari nama sheet, mis. '15. JAWA TIMUR' -> 'JAWA TIMUR'."""
    return re.sub(r"^\s*\d+\s*[.\-]\s*", "", str(sheet_name)).strip().upper()


# ---------------------------------------------------------------------------
# 1. LOADER MFD (toleran)
# ---------------------------------------------------------------------------
def load_mfd(path_or_buffer) -> tuple[pd.DataFrame, dict]:
    """Muat semua sheet provinsi dari file MFD Excel menjadi satu DataFrame rapi.

    Toleran terhadap kolom tak konsisten antar sheet: nama provinsi selalu
    diambil dari NAMA SHEET (sumber paling bersih & lengkap).

    Returns
    -------
    df : DataFrame dengan kolom NMPROP, NMKAB, NMKEC, NMDESA, UR, URLABEL (+ kode bila ada)
    info : dict ringkasan pemuatan (jumlah baris, baris dibuang, dll.)
    """
    warnings.filterwarnings("ignore")
    xl = pd.ExcelFile(path_or_buffer)
    frames: list[pd.DataFrame] = []
    dropped = 0
    raw_total = 0

    for sheet in xl.sheet_names:
        d = pd.read_excel(xl, sheet_name=sheet)
        d.columns = [str(c).strip() for c in d.columns]
        prov = _clean_prov(sheet)

        out = pd.DataFrame(index=d.index)
        # Provinsi: default dari NAMA SHEET (konvensi MFD BPS = 1 sheet per provinsi).
        # Tapi bila sheet ternyata GABUNGAN (kolom NMPROP berisi >1 provinsi berbeda,
        # mis. file dari template satu-sheet), pakai NMPROP per baris.
        if "NMPROP" in d.columns:
            colp = d["NMPROP"].astype(str).str.strip().str.upper()
            distinct = colp[(colp != "") & (colp != "NAN")].nunique()
            if distinct > 1:
                colp = colp.replace({"DI YOGYAKARTA": "D.I YOGYAKARTA"})
                out["NMPROP"] = colp.where((colp != "") & (colp != "NAN"), prov)
            else:
                out["NMPROP"] = prov
        else:
            out["NMPROP"] = prov
        for c in NAME_COLS:
            out[c] = d[c].astype(str).str.strip() if c in d.columns else pd.NA
        out["UR"] = pd.to_numeric(d["UR"], errors="coerce") if "UR" in d.columns else pd.NA
        for c in CODE_COLS:
            out[c] = d[c] if c in d.columns else pd.NA

        raw_total += len(out)
        # buang baris tak valid: tanpa nama desa/kab atau UR bukan 1/2 (header sisa, total, kosong)
        valid = (
            out["NMDESA"].notna()
            & (out["NMDESA"].astype(str).str.strip().str.lower() != "nan")
            & out["NMKAB"].notna()
            & out["UR"].isin([1, 2])
        )
        dropped += int((~valid).sum())
        frames.append(out[valid])

    df = pd.concat(frames, ignore_index=True)
    df["UR"] = df["UR"].astype(int)
    df["URLABEL"] = df["UR"].map(UR_LABEL)
    # id unik tiap titik (urut & stabil)
    df.insert(0, "ID", np.arange(1, len(df) + 1))

    info = {
        "n_provinsi": df["NMPROP"].nunique(),
        "n_kabupaten": df.groupby("NMPROP")["NMKAB"].nunique().sum(),
        "n_desa": len(df),
        "n_kota": int((df["UR"] == 1).sum()),
        "n_desa_rural": int((df["UR"] == 2).sum()),
        "baris_dibuang": dropped,
        "baris_mentah": raw_total,
    }
    return df, info


def _norm_ref(ref: pd.DataFrame) -> pd.DataFrame:
    """Rapikan tabel referensi: nama provinsi kapital & DPT/PENDUDUK numerik."""
    ref = ref.copy()
    ref.columns = [str(c).strip().upper() for c in ref.columns]
    # toleransi nama kolom alternatif
    alias = {"PROVINSI": "NMPROP", "PROV": "NMPROP", "NAMA PROVINSI": "NMPROP",
             "JUMLAH PENDUDUK": "PENDUDUK", "POPULASI": "PENDUDUK",
             "JUMLAH DPT": "DPT", "DPT**": "DPT"}
    ref = ref.rename(columns={k: v for k, v in alias.items() if k in ref.columns})
    if "NMPROP" not in ref.columns:
        raise ValueError("File referensi harus punya kolom NMPROP (atau 'Provinsi').")
    ref["NMPROP"] = ref["NMPROP"].astype(str).str.strip().str.upper()
    ref["NMPROP"] = ref["NMPROP"].replace({"DI YOGYAKARTA": "D.I YOGYAKARTA"})
    for c in ("DPT", "PENDUDUK"):
        if c in ref.columns:
            ref[c] = pd.to_numeric(ref[c], errors="coerce")
    keep = ["NMPROP"] + [c for c in ("DPT", "PENDUDUK") if c in ref.columns]
    return ref[keep].dropna(subset=["NMPROP"]).drop_duplicates(subset=["NMPROP"])


def read_reference(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Baca file referensi yang diunggah (.xlsx/.xls/.csv) -> DataFrame ternormalisasi."""
    import io as _io
    if str(filename).lower().endswith(".csv"):
        ref = pd.read_csv(_io.BytesIO(file_bytes))
    else:
        ref = pd.read_excel(_io.BytesIO(file_bytes), sheet_name=0)
    return _norm_ref(ref)


def attach_reference(df: pd.DataFrame, ref: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Tempelkan kolom DPT & PENDUDUK per provinsi dari tabel referensi (match by nama).

    Returns (df_with_ref, provinsi_tak_cocok). Provinsi MFD yang tak ada di
    referensi akan ber-nilai kosong (alokasi otomatis fallback ke basis lain).
    """
    ref = _norm_ref(ref)
    keep = ["NMPROP"] + [c for c in ("DPT", "PENDUDUK") if c in ref.columns]
    out = df.merge(ref[keep], on="NMPROP", how="left")
    unmatched = []
    if keep[1:]:
        prov_mfd = set(df["NMPROP"].unique())
        prov_ref = set(ref["NMPROP"].unique())
        unmatched = sorted(prov_mfd - prov_ref)
    return out, unmatched


def build_reference_template(ref: pd.DataFrame | None = None) -> dict:
    """Template referensi DPT & Penduduk (terisi nilai saat ini bila ada) + petunjuk."""
    if ref is not None and len(ref):
        data = _norm_ref(ref)
        for c in ("DPT", "PENDUDUK"):
            if c not in data.columns:
                data[c] = pd.NA
        data = data[["NMPROP", "DPT", "PENDUDUK"]]
    else:
        data = pd.DataFrame(columns=["NMPROP", "DPT", "PENDUDUK"])
    petunjuk = pd.DataFrame({
        "Kolom": ["NMPROP", "DPT", "PENDUDUK", "", "Catatan", "Catatan"],
        "Keterangan": [
            "Nama provinsi (kapital). Harus sama dengan nama provinsi di MFD.",
            "Jumlah Daftar Pemilih Tetap provinsi (angka).",
            "Jumlah penduduk provinsi (angka).",
            "",
            "Edit angka DPT/PENDUDUK sesuai data terbaru, lalu simpan & unggah file ini.",
            "Boleh isi salah satu saja (DPT atau PENDUDUK) sesuai basis alokasi yang dipakai.",
        ],
    })
    return {"Referensi": data, "Petunjuk": petunjuk}


# ---------------------------------------------------------------------------
# 2. ALOKASI proporsional + jaminan minimum (largest-remainder / Hamilton)
# ---------------------------------------------------------------------------
def allocate(sizes: dict, total: int, minimum: int = 0) -> dict:
    """Alokasikan `total` unit bulat ke tiap key proporsional thd `sizes`,
    dengan jaminan minimal `minimum` per key bila kapasitas mencukupi.

    Memakai metode largest-remainder sehingga jumlah hasil PERSIS = total
    dan tidak ada wilayah yang ter-skip (selama total >= minimum*jumlah_key).
    """
    keys = list(sizes)
    n = len(keys)
    if n == 0 or total <= 0:
        return {k: 0 for k in keys}

    # bila total tak cukup memberi minimum ke semua, turunkan minimum efektif
    eff_min = minimum
    if total < minimum * n:
        eff_min = total // n  # bagi rata sebisanya; sisa dibagi by largest remainder

    base = {k: eff_min for k in keys}
    remaining = total - eff_min * n
    s = float(sum(max(sizes[k], 0) for k in keys))

    if remaining <= 0:
        # distribusikan sisa (bila ada karena pembulatan minimum) by ukuran
        order = sorted(keys, key=lambda k: max(sizes[k], 0), reverse=True)
        for i in range(max(remaining, 0)):
            base[order[i % n]] += 1
        return base

    if s <= 0:
        # tak ada ukuran -> bagi rata sisa
        order = keys
        for i in range(remaining):
            base[order[i % n]] += 1
        return base

    quota = {k: remaining * max(sizes[k], 0) / s for k in keys}
    floor_ = {k: int(np.floor(quota[k])) for k in keys}
    alloc = {k: base[k] + floor_[k] for k in keys}
    leftover = remaining - sum(floor_.values())
    # bagikan sisa ke pecahan terbesar
    order = sorted(keys, key=lambda k: (quota[k] - floor_[k]), reverse=True)
    for i in range(leftover):
        alloc[order[i % n]] += 1
    return alloc


def _blended_size(group: pd.DataFrame, weights: dict) -> float:
    """Hitung ukuran (size measure) gabungan untuk satu unit alokasi.

    weights: {'PENDUDUK': w1, 'DPT': w2, 'MFD': w3}. Basis yang datanya tak
    tersedia untuk unit ini diabaikan & bobot dinormalisasi ulang otomatis.
    """
    comp = {}
    if weights.get("MFD", 0) > 0:
        comp["MFD"] = float(len(group))
    if weights.get("PENDUDUK", 0) > 0 and "PENDUDUK" in group and group["PENDUDUK"].notna().any():
        comp["PENDUDUK"] = float(group["PENDUDUK"].iloc[0])
    if weights.get("DPT", 0) > 0 and "DPT" in group and group["DPT"].notna().any():
        comp["DPT"] = float(group["DPT"].iloc[0])
    return comp  # dikembalikan komponen mentah; normalisasi dilakukan di pemanggil


def compute_sizes(df: pd.DataFrame, level_col: str, weights: dict) -> dict:
    """Ukuran gabungan ternormalisasi tiap unit alokasi (share 0..1 lalu diskalakan)."""
    units = list(df[level_col].dropna().unique())
    raw = {}  # unit -> {basis: nilai}
    for u in units:
        g = df[df[level_col] == u]
        raw[u] = _blended_size(g, weights)

    # normalisasi tiap basis jadi share, lalu jumlahkan berbobot
    bases = set()
    for v in raw.values():
        bases.update(v.keys())
    totals = {b: sum(raw[u].get(b, 0.0) for u in units) for b in bases}
    # bobot efektif (hanya basis yg ada), dinormalisasi ke jumlah 1
    eff_w = {b: weights.get(b, 0.0) for b in bases}
    wsum = sum(eff_w.values()) or 1.0
    eff_w = {b: w / wsum for b, w in eff_w.items()}

    sizes = {}
    for u in units:
        val = 0.0
        for b in bases:
            if totals[b] > 0:
                val += eff_w[b] * (raw[u].get(b, 0.0) / totals[b])
        sizes[u] = val
    return sizes


# ---------------------------------------------------------------------------
# 3. SELEKSI acak
# ---------------------------------------------------------------------------
def _pick(df: pd.DataFrame, n: int, rng: np.random.Generator,
          pps_col: str | None = None) -> pd.DataFrame:
    """Pilih n baris acak tanpa pengembalian. Jika n>=tersedia, ambil semua.

    pps_col: bila diberikan, peluang sebanding nilai kolom (Probability
    Proportional to Size). Bila None, peluang sama rata.
    """
    m = len(df)
    if n <= 0 or m == 0:
        return df.iloc[0:0]
    if n >= m:
        return df
    if pps_col and pps_col in df.columns and df[pps_col].fillna(0).sum() > 0:
        p = df[pps_col].fillna(0).to_numpy(dtype=float)
        p = p / p.sum()
        idx = rng.choice(m, size=n, replace=False, p=p)
    else:
        idx = rng.choice(m, size=n, replace=False)
    return df.iloc[np.sort(idx)]


# ---------------------------------------------------------------------------
# 4. KONFIGURASI & RUNNER
# ---------------------------------------------------------------------------
@dataclass
class SamplingConfig:
    scope: str = "NASIONAL"               # NASIONAL | PROVINSI | KABUPATEN
    scope_filter: list = field(default_factory=list)  # daftar nama provinsi/kab pembatas
    unit: str = "DESA"                    # DESA | KABUPATEN  (titik akhir)
    n_total: int = 1200                   # responden (unit DESA) / jumlah kab (unit KABUPATEN)
    cluster_size: int = 10                # responden per titik/desa (unit DESA)
    weights: dict = field(default_factory=lambda: {"PENDUDUK": 1.0, "DPT": 0.0, "MFD": 0.0})
    stratify_ur: bool = True              # pisah Perkotaan/Perdesaan
    min_per_unit: int = 1                 # minimal titik/unit per stratum primer (jaminan cakupan)
    pps: bool = False                     # seleksi PPS (peluang ~ ukuran) utk unit KABUPATEN
    seed: int = 2024


@dataclass
class SamplingResult:
    sample: pd.DataFrame                  # baris terpilih
    alokasi: pd.DataFrame                 # tabel alokasi per unit primer (+UR)
    ringkasan: pd.DataFrame              # ringkasan eksekutif
    coverage: dict                       # info cakupan & peringatan
    warnings: list


def apply_scope(df: pd.DataFrame, cfg: SamplingConfig) -> pd.DataFrame:
    """Saring DataFrame sesuai cakupan survei (NASIONAL/PROVINSI/KABUPATEN)."""
    data = df.copy()
    if cfg.scope == "PROVINSI" and cfg.scope_filter:
        sel = [s.upper() for s in cfg.scope_filter]
        data = data[data["NMPROP"].str.upper().isin(sel)]
    elif cfg.scope == "KABUPATEN" and cfg.scope_filter:
        sel = [s.upper() for s in cfg.scope_filter]
        data = data[data["NMKAB"].str.upper().isin(sel)]
    return data


def run_sampling(df: pd.DataFrame, cfg: SamplingConfig) -> SamplingResult:
    rng = np.random.default_rng(cfg.seed)
    warns: list[str] = []

    # --- filter scope ---
    data = apply_scope(df, cfg)
    if data.empty:
        raise ValueError("Data kosong setelah filter scope. Periksa pilihan wilayah.")

    if cfg.unit == "KABUPATEN":
        return _run_kabupaten(data, cfg, rng, warns)
    return _run_desa(data, cfg, rng, warns)


# ---- unit = DESA/KELURAHAN (titik) -----------------------------------------
def _run_desa(data, cfg, rng, warns) -> SamplingResult:
    level_col = LEVEL_COL[cfg.scope]
    n_clusters = int(np.ceil(cfg.n_total / max(cfg.cluster_size, 1)))

    units = list(data[level_col].dropna().unique())
    if cfg.min_per_unit * len(units) > n_clusters:
        warns.append(
            f"Jumlah titik ({n_clusters}) < jumlah {level_col} ({len(units)}) x minimum "
            f"({cfg.min_per_unit}). Tidak semua {level_col} bisa kebagian minimum; "
            f"sistem membagi semerata mungkin berdasarkan ukuran."
        )

    sizes = compute_sizes(data, level_col, cfg.weights)
    alloc_primary = allocate(sizes, n_clusters, cfg.min_per_unit)

    rows = []
    alloc_records = []
    for u, k in alloc_primary.items():
        g = data[data[level_col] == u]
        if k <= 0:
            continue
        if cfg.stratify_ur:
            cnt = {ur: int((g["UR"] == ur).sum()) for ur in (1, 2)}
            ur_alloc = allocate({ur: cnt[ur] for ur in (1, 2)}, k, minimum=0)
        else:
            ur_alloc = {0: k}
        for ur, kk in ur_alloc.items():
            sub = g if ur == 0 else g[g["UR"] == ur]
            picked = _pick(sub, kk, rng)
            short = kk - len(picked)
            if short > 0:
                warns.append(
                    f"{u} / {UR_LABEL.get(ur,'Semua')}: diminta {kk} titik, "
                    f"tersedia {len(sub)} -> terpilih {len(picked)} (kurang {short})."
                )
            rows.append(picked)
            alloc_records.append({
                level_col: u,
                "Provinsi": g["NMPROP"].iloc[0],
                "Strata": UR_LABEL.get(ur, "Semua"),
                "Target_Titik": kk,
                "Terpilih": len(picked),
            })

    sample = pd.concat(rows, ignore_index=True) if rows else data.iloc[0:0].copy()

    # responden per titik (terakhir disesuaikan supaya total persis)
    sample = sample.reset_index(drop=True)
    sample["RESPONDEN"] = cfg.cluster_size
    surplus = len(sample) * cfg.cluster_size - cfg.n_total
    if surplus > 0 and len(sample) > 0:
        sample.loc[len(sample) - 1, "RESPONDEN"] = cfg.cluster_size - surplus

    alokasi = pd.DataFrame(alloc_records)
    coverage = _coverage_report(data, sample, level_col, units)
    ringkasan = _ringkasan(cfg, sample, n_clusters, level_col, coverage)
    return SamplingResult(sample, alokasi, ringkasan, coverage, warns)


# ---- unit = KABUPATEN/KOTA -------------------------------------------------
def _run_kabupaten(data, cfg, rng, warns) -> SamplingResult:
    # kerangka kab/kota unik + ukuran (jumlah desa, pop/dpt provinsi)
    kab = (data.groupby(["NMPROP", "NMKAB"])
                .agg(N_DESA=("ID", "size"),
                     PENDUDUK=("PENDUDUK", "first") if "PENDUDUK" in data else ("ID", "size"),
                     DPT=("DPT", "first") if "DPT" in data else ("ID", "size"))
                .reset_index())
    n_units = int(cfg.n_total)

    # alokasi jumlah kab antar provinsi (skala provinsi)
    if cfg.scope == "NASIONAL":
        prov_sizes = compute_sizes(data, "NMPROP", cfg.weights)
        # batasi tiap provinsi maksimal sejumlah kab tersedia
        cap = kab.groupby("NMPROP")["NMKAB"].nunique().to_dict()
        alloc_prov = allocate(prov_sizes, n_units, cfg.min_per_unit)
        # koreksi bila melebihi kapasitas provinsi
        alloc_prov = _cap_alloc(alloc_prov, cap, prov_sizes)
        groups = [("NMPROP", p, alloc_prov.get(p, 0)) for p in kab["NMPROP"].unique()]
    else:
        # PROVINSI terpilih -> bagi antar provinsi terpilih; KABUPATEN scope tak relevan
        prov_sizes = compute_sizes(data, "NMPROP", cfg.weights)
        cap = kab.groupby("NMPROP")["NMKAB"].nunique().to_dict()
        alloc_prov = allocate(prov_sizes, n_units, cfg.min_per_unit)
        alloc_prov = _cap_alloc(alloc_prov, cap, prov_sizes)
        groups = [("NMPROP", p, alloc_prov.get(p, 0)) for p in kab["NMPROP"].unique()]

    rows = []
    alloc_records = []
    pps_col = "N_DESA" if cfg.pps else None
    for _, prov, k in groups:
        g = kab[kab["NMPROP"] == prov]
        picked = _pick(g, k, rng, pps_col=pps_col)
        rows.append(picked)
        alloc_records.append({"Provinsi": prov, "Target_Kab": k, "Terpilih": len(picked)})

    sample = pd.concat(rows, ignore_index=True) if rows else kab.iloc[0:0].copy()
    alokasi = pd.DataFrame(alloc_records)
    coverage = {
        "unit": "KABUPATEN",
        "total_terpilih": len(sample),
        "target": n_units,
        "provinsi_tercakup": sample["NMPROP"].nunique() if len(sample) else 0,
        "provinsi_total": kab["NMPROP"].nunique(),
    }
    ringkasan = pd.DataFrame([
        {"Keterangan": "Mode", "Nilai": "Sampling Kabupaten/Kota"},
        {"Keterangan": "Target kab/kota", "Nilai": n_units},
        {"Keterangan": "Terpilih", "Nilai": len(sample)},
        {"Keterangan": "Provinsi tercakup",
         "Nilai": f"{coverage['provinsi_tercakup']}/{coverage['provinsi_total']}"},
        {"Keterangan": "Seleksi", "Nilai": "PPS (~jumlah desa)" if cfg.pps else "Acak merata"},
        {"Keterangan": "Seed", "Nilai": cfg.seed},
    ])
    ringkasan["Nilai"] = ringkasan["Nilai"].astype(str)
    return SamplingResult(sample, alokasi, ringkasan, coverage, warns)


def _cap_alloc(alloc: dict, cap: dict, sizes: dict) -> dict:
    """Pastikan alokasi tidak melebihi kapasitas (cap) tiap key; sisa dialihkan
    ke key lain yg masih punya ruang, prioritas ukuran terbesar."""
    alloc = dict(alloc)
    overflow = 0
    for k in alloc:
        c = cap.get(k, alloc[k])
        if alloc[k] > c:
            overflow += alloc[k] - c
            alloc[k] = c
    if overflow > 0:
        order = sorted(alloc, key=lambda k: sizes.get(k, 0), reverse=True)
        i = 0
        guard = 0
        while overflow > 0 and guard < 100000:
            k = order[i % len(order)]
            if alloc[k] < cap.get(k, alloc[k]):
                alloc[k] += 1
                overflow -= 1
            i += 1
            guard += 1
    return alloc


def _coverage_report(data, sample, level_col, units) -> dict:
    covered = set(sample[level_col].unique()) if len(sample) else set()
    not_covered = [u for u in units if u not in covered]
    return {
        "unit": "DESA",
        "level": level_col,
        "unit_total": len(units),
        "unit_tercakup": len(units) - len(not_covered),
        "unit_tidak_tercakup": not_covered,
        "provinsi_tercakup": sample["NMPROP"].nunique() if len(sample) else 0,
        "provinsi_total": data["NMPROP"].nunique(),
        "titik_terpilih": len(sample),
        "responden_total": int(sample["RESPONDEN"].sum()) if "RESPONDEN" in sample else 0,
    }


def _ringkasan(cfg, sample, n_clusters, level_col, cov) -> pd.DataFrame:
    rows = [
        {"Keterangan": "Cakupan survei", "Nilai": cfg.scope.title()},
        {"Keterangan": "Unit sampling", "Nilai": "Desa/Kelurahan (titik)"},
        {"Keterangan": "Target responden", "Nilai": cfg.n_total},
        {"Keterangan": "Responden per titik", "Nilai": cfg.cluster_size},
        {"Keterangan": "Jumlah titik (TPD)", "Nilai": n_clusters},
        {"Keterangan": "Titik terpilih", "Nilai": cov["titik_terpilih"]},
        {"Keterangan": "Responden terealisasi", "Nilai": cov["responden_total"]},
        {"Keterangan": f"{level_col} tercakup",
         "Nilai": f"{cov['unit_tercakup']}/{cov['unit_total']}"},
        {"Keterangan": "Provinsi tercakup",
         "Nilai": f"{cov['provinsi_tercakup']}/{cov['provinsi_total']}"},
        {"Keterangan": "Stratifikasi Kota/Desa", "Nilai": "Ya" if cfg.stratify_ur else "Tidak"},
        {"Keterangan": "Bobot basis alokasi",
         "Nilai": ", ".join(f"{k}:{v:g}" for k, v in cfg.weights.items() if v > 0)},
        {"Keterangan": "Random seed", "Nilai": cfg.seed},
    ]
    out = pd.DataFrame(rows)
    out["Nilai"] = out["Nilai"].astype(str)  # seragamkan tipe (hindari isu serialisasi)
    return out


LEVEL_LABEL = {"NMPROP": "Provinsi", "NMKAB": "Kabupaten/Kota", "NMKEC": "Kecamatan"}


# ---------------------------------------------------------------------------
# 5. TEMPLATE MFD KOSONG
# ---------------------------------------------------------------------------
def build_template() -> dict:
    """Hasilkan template MFD kosong (format SATU sheet gabungan) + lembar petunjuk.

    Returns dict {nama_sheet: DataFrame} siap ditulis ke Excel.
    Loader mendukung dua format:
      * Satu sheet 'MFD' dengan kolom NMPROP terisi (seperti template ini), ATAU
      * Banyak sheet, satu provinsi per sheet (konvensi MFD BPS).
    """
    contoh = pd.DataFrame([
        # KODE opsional; yang WAJIB: NMPROP, NMKAB, NMKEC, NMDESA, UR
        [11, 1, 10, 1, "ACEH", "SIMEULUE", "TEUPAH SELATAN", "LATIUNG", 2],
        [11, 1, 10, 2, "ACEH", "SIMEULUE", "TEUPAH SELATAN", "LABUHAN BAJAU", 2],
        [11, 71, 1, 1, "ACEH", "KOTA BANDA ACEH", "MEURAXA", "BLANG OI", 1],
        [12, 71, 5, 3, "SUMATERA UTARA", "KOTA MEDAN", "MEDAN KOTA", "MESJID", 1],
        [12, 1, 60, 15, "SUMATERA UTARA", "NIAS", "IDANO GAWO", "TETE GOENAAI", 2],
    ], columns=["KODEPROP", "KAB", "KEC", "DESA", "NMPROP", "NMKAB", "NMKEC", "NMDESA", "UR"])

    petunjuk = pd.DataFrame([
        ["Kolom", "Wajib?", "Keterangan"],
        ["NMPROP", "WAJIB", "Nama provinsi (huruf kapital). Atau: buat 1 sheet per provinsi & beri nama sheet = nama provinsi."],
        ["NMKAB", "WAJIB", "Nama kabupaten/kota (mis. 'KABUPATEN BANDUNG', 'KOTA MEDAN')."],
        ["NMKEC", "WAJIB", "Nama kecamatan."],
        ["NMDESA", "WAJIB", "Nama desa/kelurahan."],
        ["UR", "WAJIB", "Klasifikasi: 1 = Perkotaan (Kota), 2 = Perdesaan (Desa)."],
        ["KODEPROP/KAB/KEC/DESA", "opsional", "Kode wilayah BPS. Boleh dikosongkan; tidak memengaruhi sampling."],
        ["", "", ""],
        ["Catatan", "", "Baris kosong / tanpa NMDESA / UR selain 1-2 akan otomatis diabaikan."],
        ["Catatan", "", "Isi data mulai baris ke-2 (baris ke-1 = nama kolom). Hapus contoh sebelum dipakai."],
        ["Referensi", "", "Untuk alokasi berbasis Penduduk/DPT, sesuaikan data/referensi_provinsi.csv (kolom: NMPROP, DPT, PENDUDUK)."],
    ])
    petunjuk.columns = petunjuk.iloc[0]
    petunjuk = petunjuk[1:].reset_index(drop=True)
    return {"MFD": contoh, "Petunjuk": petunjuk}


# ---------------------------------------------------------------------------
# 6. EXPORT FORMAT KERANGKA (rekap ala SILOGNAS SURNAS)
# ---------------------------------------------------------------------------
def build_kerangka_recap(df: pd.DataFrame, res: "SamplingResult", cfg: SamplingConfig) -> pd.DataFrame:
    """Rekap hasil sampling dalam format menyerupai 'Kerangka SILOGNAS SURNAS':
    satu baris per wilayah primer (provinsi / kab / kecamatan sesuai cakupan),
    lengkap dengan DPT, Penduduk, jumlah Kota/Desa (MFD), alokasi titik & responden
    per strata, serta TPD. Ditutup baris TOTAL.
    """
    frame = apply_scope(df, cfg)

    # ---- mode unit KABUPATEN ----
    if cfg.unit == "KABUPATEN":
        tersedia = frame.groupby("NMPROP")["NMKAB"].nunique().rename("Kab_Tersedia")
        terpilih = (res.sample.groupby("NMPROP")["NMKAB"].nunique()
                    if len(res.sample) else pd.Series(dtype=int)).rename("Kab_Terpilih")
        rec = pd.concat([tersedia, terpilih], axis=1).fillna(0).astype(int).reset_index()
        if "PENDUDUK" in frame.columns:
            pen = frame.groupby("NMPROP")["PENDUDUK"].first()
            rec = rec.merge(pen.rename("Penduduk"), on="NMPROP", how="left")
            tot = rec["Penduduk"].sum()
            rec["%_Penduduk"] = (rec["Penduduk"] / tot * 100).round(2) if tot else 0
        rec.insert(0, "No", range(1, len(rec) + 1))
        rec = rec.rename(columns={"NMPROP": "Provinsi"})
        total = {c: rec[c].sum() if rec[c].dtype != object else "" for c in rec.columns}
        total["No"] = ""; total["Provinsi"] = "TOTAL"
        if "%_Penduduk" in rec.columns:
            total["%_Penduduk"] = round(rec["%_Penduduk"].sum(), 2)
        return pd.concat([rec, pd.DataFrame([total])], ignore_index=True)

    # ---- mode unit DESA ----
    lvl = LEVEL_COL[cfg.scope]
    s = res.sample.copy()

    # jumlah kota/desa tersedia di MFD per unit primer
    avail = (frame.assign(_k=(frame["UR"] == 1).astype(int),
                          _d=(frame["UR"] == 2).astype(int))
                  .groupby(lvl).agg(Kota_MFD=("_k", "sum"), Desa_MFD=("_d", "sum")).reset_index())
    avail["Total_MFD"] = avail["Kota_MFD"] + avail["Desa_MFD"]

    # titik & responden terpilih per unit primer x strata
    def _piv(values, agg):
        p = s.pivot_table(index=lvl, columns="UR", values=values, aggfunc=agg, fill_value=0)
        for u in (1, 2):
            if u not in p.columns:
                p[u] = 0
        return p[[1, 2]]
    tk = _piv("ID", "count").rename(columns={1: "Titik_Kota", 2: "Titik_Desa"})
    rp = _piv("RESPONDEN", "sum").rename(columns={1: "Resp_Kota", 2: "Resp_Desa"})

    rec = avail.merge(tk, on=lvl, how="left").merge(rp, on=lvl, how="left").fillna(0)
    for c in ["Titik_Kota", "Titik_Desa", "Resp_Kota", "Resp_Desa"]:
        rec[c] = rec[c].astype(int)
    rec["Total_Titik"] = rec["Titik_Kota"] + rec["Titik_Desa"]
    rec["Total_Responden"] = rec["Resp_Kota"] + rec["Resp_Desa"]
    rec["TPD"] = rec["Total_Titik"]

    # peta provinsi induk (hanya untuk level kab/kecamatan; di level provinsi tak perlu)
    if lvl != "NMPROP":
        prov_map = frame.groupby(lvl)["NMPROP"].first()
        rec = rec.merge(prov_map.rename("Provinsi"), on=lvl, how="left")

    rec = rec.rename(columns={lvl: LEVEL_LABEL[lvl]})

    if lvl == "NMPROP" and "PENDUDUK" in frame.columns:
        ref = frame.groupby("NMPROP")[["DPT", "PENDUDUK"]].first().reset_index()
        ref = ref.rename(columns={"NMPROP": LEVEL_LABEL[lvl]})
        rec = rec.merge(ref, on=LEVEL_LABEL[lvl], how="left")
        tdpt, tpen = rec["DPT"].sum(), rec["PENDUDUK"].sum()
        rec["%_DPT"] = (rec["DPT"] / tdpt * 100).round(2) if tdpt else 0
        rec["%_Penduduk"] = (rec["PENDUDUK"] / tpen * 100).round(2) if tpen else 0
        order = ["No", LEVEL_LABEL[lvl], "DPT", "%_DPT", "PENDUDUK", "%_Penduduk",
                 "Kota_MFD", "Desa_MFD", "Total_MFD",
                 "Titik_Kota", "Titik_Desa", "Total_Titik",
                 "Resp_Kota", "Resp_Desa", "Total_Responden", "TPD"]
    else:
        # untuk kab/kecamatan tampilkan provinsi induk sebagai kolom ke-2 konteks
        order = ["No", LEVEL_LABEL[lvl], "Provinsi",
                 "Kota_MFD", "Desa_MFD", "Total_MFD",
                              "Titik_Kota", "Titik_Desa", "Total_Titik",
                              "Resp_Kota", "Resp_Desa", "Total_Responden", "TPD"]

    rec = rec.sort_values(LEVEL_LABEL[lvl]).reset_index(drop=True)
    rec.insert(0, "No", range(1, len(rec) + 1))
    rec = rec[[c for c in order if c in rec.columns]]

    # baris TOTAL
    num_cols = [c for c in rec.columns if c not in ("No", LEVEL_LABEL[lvl], "Provinsi")]
    total = {c: "" for c in rec.columns}
    total[LEVEL_LABEL[lvl]] = "TOTAL"
    for c in num_cols:
        total[c] = round(rec[c].sum(), 2)
    return pd.concat([rec, pd.DataFrame([total])], ignore_index=True)
