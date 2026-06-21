# ============================================================
#  Asisten Random Sampling — image reproducible untuk jangka panjang.
#  Python & semua library DIBEKUKAN versinya -> bisa dibangun ulang
#  bertahun-tahun ke depan dengan hasil identik.
#
#  Build : docker build -t sampling-idn .
#  Run   : docker run -p 8501:8501 sampling-idn
#  Buka  : http://localhost:8501
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# Pasang dependensi versi terkunci lebih dulu (manfaatkan cache layer)
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt

# Salin kode aplikasi
COPY . .

EXPOSE 8501

# Health check tanpa perlu curl (pakai Python bawaan)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD \
    python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').status==200 else 1)" || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
            "--server.port=8501", "--server.address=0.0.0.0", \
            "--server.headless=true"]
