FROM python:3.11-slim

WORKDIR /app

# فونت برای واترمارک
RUN apt-get update && apt-get install -y fonts-dejavu && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# دستور پیش‌فرض
CMD ["python", "-m", "cli.main", "--help"]
