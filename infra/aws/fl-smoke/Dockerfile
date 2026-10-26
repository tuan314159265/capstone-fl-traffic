FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FLWR_TELEMETRY_ENABLED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu 'torch==2.10.0+cpu'
COPY requirements.txt /tmp/fl-requirements.txt
RUN pip install --no-cache-dir -r /tmp/fl-requirements.txt
RUN useradd --uid 1000 --home-dir /tmp --no-create-home capstone
ENV HOME=/tmp USER=capstone LOGNAME=capstone \
    TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor OPENBLAS_NUM_THREADS=1
WORKDIR /app
USER capstone
ENTRYPOINT ["python", "experiments/run_experiment.py"]
