FROM python:3.11-slim

WORKDIR /app

# Install CPU-only torch first to keep image small and avoid timeouts
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create uploads dir and init DB
RUN mkdir -p uploads && python -m app.init_db

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
