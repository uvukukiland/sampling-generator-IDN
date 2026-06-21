#!/bin/bash
# ============================================================
#  Asisten Random Sampling - Launcher (macOS / Linux)
#  Klik dua kali file ini di Finder untuk menjalankan aplikasi.
#  (Pertama kali: klik kanan -> Open, agar lolos Gatekeeper.)
# ============================================================
cd "$(dirname "$0")" || exit 1

# Pilih interpreter Python 3
PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3 belum terpasang. Pasang dari https://www.python.org/downloads/ lalu coba lagi."
  read -r -p "Tekan Enter untuk menutup..."
  exit 1
fi

# Buat virtual environment sekali saja (hindari batasan Python sistem macOS)
if [ ! -d ".venv" ]; then
  echo "Menyiapkan environment (sekali saja)..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Memeriksa dependensi..."
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

echo
echo "Membuka aplikasi di browser..."
python -m streamlit run app.py

read -r -p "Aplikasi berhenti. Tekan Enter untuk menutup..."
