FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    NEUROLKH_ROOT=/app/third_party/NeuroLKH

WORKDIR /app

# The SWIG extension of NeuroLKH is built with this same Python 3.11.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        g++ \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY third_party/NeuroLKH ./third_party/NeuroLKH
COPY scripts/neurolkh ./scripts/neurolkh
COPY build_neurolkh_swig.sh ./build_neurolkh_swig.sh
RUN rm -rf /app/third_party/NeuroLKH/.venv \
    && python -m venv /app/third_party/NeuroLKH/.venv \
    && /app/third_party/NeuroLKH/.venv/bin/pip install --no-cache-dir numpy scikit-learn \
    && /app/third_party/NeuroLKH/.venv/bin/pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && bash /app/build_neurolkh_swig.sh

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "api:create_app()"]
