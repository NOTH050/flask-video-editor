# Base image พร้อม Python
FROM python:3.11-slim

# ตั้ง working directory
WORKDIR /app

# Copy requirements และติดตั้ง
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy โค้ดทั้งหมด
COPY . .

# ใช้ Gunicorn รัน Flask
CMD ["gunicorn", "111:app", "--bind", "0.0.0.0:8080", "--workers", "2"]
