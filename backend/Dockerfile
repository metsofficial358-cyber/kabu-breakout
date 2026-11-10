FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Asia/Tokyo
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
# SQLite と yfinance のキャッシュは /data（ボリューム）に置く
ENV DATABASE_URL=sqlite:////data/kabu.db
VOLUME ["/data"]
EXPOSE 8000
# スケジューラとロックはプロセス内で管理するため 1 ワーカーで動かす
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
