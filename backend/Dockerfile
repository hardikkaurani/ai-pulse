FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose API port
EXPOSE 8000

# Run FastAPI via Uvicorn with proper package module path
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
