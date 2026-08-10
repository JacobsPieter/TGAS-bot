FROM python:3.13-slim

WORKDIR /app

# Installeer tijdelijk de benodigde compilers voor C-libraries (audioop-lts, cffi, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip en installeer je requirements
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]