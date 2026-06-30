"""
Smoke test mandiri (tanpa pytest) untuk Asisten Random Sampling.

Membuat MFD sintetis kecil, lalu menguji jalur inti engine + I/O Excel +
inisialisasi app Streamlit. Keluar dengan kode != 0 bila ada yang gagal,
sehingga bisa dipakai langsung di CI:  python tests/smoke_test.py
"""
import io
import os
import sys

import pandas as pd

# pastikan root proyek ada di path saat dijalankan dari mana pun
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import sampling_engine as E  # noqa: E402


def _make_synthetic_mfd() -> bytes:
    """MFD sintetis: 3 provinsi (nama cocok dgn referensi), tiap sheet 1 provinsi."""
    provs = ["ACEH", "BALI", "JAWA BARAT"]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        for pi, prov in enumerate(provs, start=1):
            rows = []
            for kab in range(1, 4):            # 3 kab/kota
                for kec in range(1, 4):        # 3 kecamatan
                    for desa in range(1, 8):   # 7 desa
                        ur = 1 if (desa % 2 == 0) else 2
                        rows.append([prov, f"{prov} KAB {kab}",
                                     f"KEC {kab}-{kec}", f"DESA {kab}-{kec}-{desa}", ur])
            d = pd.DataFrame(rows, columns=["NMPROP", "NMKAB", "NMKEC", "NMDESA", "UR"])
            d.to_excel(xw, sheet_name=f"{pi}. {prov}", index=False)
    return buf.getvalue()


def _excel_ok(sheets: dict) -> int:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        for n, dd in sheets.items():
            dd.to_excel(xw, sheet_name=n[:31], index=False)
    return len(pd.ExcelFile(io.BytesIO(buf.getvalue())).sheet_names)


def main() -> None:
    # 1. Loader MFD sintetis (jalur per-sheet)
    df, info = E.load_mfd(io.BytesIO(_make_synthetic_mfd()))
    assert info["n_provinsi"] == 3, info
    assert info["n_desa"] == 3 * 3 * 3 * 7, info
    print("[OK] load_mfd:", info["n_provinsi"], "provinsi,", info["n_desa"], "desa")

    # 2. Referensi (CSV bawaan) menempel & cocok
    ref = pd.read_csv(os.path.join(ROOT, "data", "referensi_provinsi.csv"))
    df, unmatched = E.attach_reference(df, ref)
    assert "PENDUDUK" in df.columns and unmatched == [], unmatched
    print("[OK] attach_reference: unmatched =", unmatched)

    # 3. Sampling nasional unit DESA -> total responden persis & semua provinsi tercakup
    cfg = E.SamplingConfig(scope="NASIONAL", unit="DESA", n_total=100, cluster_size=10,
                           weights={"PENDUDUK": 0.5, "DPT": 0.5}, min_per_unit=1, seed=1)
    res = E.run_sampling(df, cfg)
    assert int(res.sample["RESPONDEN"].sum()) == 100, res.sample["RESPONDEN"].sum()
    assert res.coverage["provinsi_tercakup"] == 3, res.coverage
    print("[OK] sampling DESA: 100 responden,", res.coverage["provinsi_tercakup"], "provinsi")

    # 4. Recap Kerangka punya baris TOTAL
    recap = E.build_kerangka_recap(df, res, cfg)
    assert (recap.iloc[-1].astype(str).str.contains("TOTAL")).any(), recap.tail(1)
    print("[OK] build_kerangka_recap (DESA):", recap.shape)

    # 5. Sampling unit KABUPATEN
    cfgk = E.SamplingConfig(scope="NASIONAL", unit="KABUPATEN", n_total=5,
                            weights={"MFD": 1.0}, min_per_unit=1, pps=True, seed=2)
    resk = E.run_sampling(df, cfgk)
    assert len(resk.sample) == 5, len(resk.sample)
    E.build_kerangka_recap(df, resk, cfgk)
    print("[OK] sampling KABUPATEN:", len(resk.sample), "kab terpilih")

    # 5b. Pratinjau alokasi = hasil run (deterministik), kedua mode
    prev = E.preview_allocation(df, cfg)
    pv = prev.iloc[:-1].set_index("Provinsi")["Total_Titik"].astype(int).sort_index()
    act = res.sample.groupby("NMPROP").size().sort_index()
    assert (pv.values == act.values).all(), "pratinjau != hasil"
    assert len(E.preview_allocation(df, cfgk)), "pratinjau KABUPATEN kosong"
    print("[OK] preview_allocation cocok dgn hasil run")

    # 6. Template MFD bisa dimuat balik (jalur satu-sheet gabungan)
    tpl = E.build_template()
    tdf, tinfo = E.load_mfd(io.BytesIO(_excel_bytes(tpl)))
    assert tinfo["n_provinsi"] == 2, tinfo
    print("[OK] build_template -> reload:", tinfo["n_provinsi"], "provinsi")

    # 7. Template referensi + round-trip read_reference
    rtpl = E.build_reference_template(ref)
    rb = _excel_bytes(rtpl)
    ref2 = E.read_reference(rb, "template_referensi.xlsx")
    assert {"NMPROP"}.issubset(ref2.columns) and len(ref2) == 38, ref2.shape
    print("[OK] reference template round-trip:", ref2.shape)

    # 8. I/O Excel multi-sheet (hasil & kerangka)
    assert _excel_ok({"Ringkasan": res.ringkasan, "Sampel": res.sample, "Alokasi": res.alokasi}) == 3
    assert _excel_ok({"Kerangka": recap, "Ringkasan": res.ringkasan}) == 2
    print("[OK] export Excel multi-sheet")

    # 9. Inisialisasi app Streamlit (tanpa MFD -> harus berhenti rapi, tanpa exception)
    try:
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=120).run()
        assert not at.exception, at.exception
        print("[OK] app.py init via AppTest (no exception)")
    except ModuleNotFoundError:
        print("[skip] streamlit testing tak tersedia")

    print("\nSEMUA SMOKE TEST LULUS ✓")


def _excel_bytes(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        for n, dd in sheets.items():
            dd.to_excel(xw, sheet_name=n[:31], index=False)
    return buf.getvalue()


if __name__ == "__main__":
    main()
