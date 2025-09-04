# ✅ Base image
FROM python:3.11-slim

# ✅ ติดตั้ง system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# ✅ สร้างโฟลเดอร์สำหรับ app
WORKDIR /app

# ✅ คัดลอก requirements.txt และติดตั้ง lib
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ คัดลอกไฟล์โปรเจกต์ทั้งหมด (รวม KanchaStay.ttf ด้วย)
COPY . .

# ✅ ย้ายฟอนต์ KanchaStay.ttf ไป system fonts
RUN mkdir -p /usr/share/fonts/truetype/custom && \
    cp KanchaStay.ttf /usr/share/fonts/truetype/custom/ && \
    fc-cache -f -v

# ✅ Port ที่ Flask จะใช้
EXPOSE 8080

# ✅ Run Flask app ด้วย Gunicorn
CMD ["gunicorn", "111:app", "--bind", "0.0.0.0:8080", "--workers", "2"]
