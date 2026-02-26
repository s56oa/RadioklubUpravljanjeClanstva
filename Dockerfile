FROM python:3.12-slim

WORKDIR /app

# Namesti odvisnosti
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiraj kodo
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY LICENSE .

# Ustvari mapo za bazo podatkov
RUN mkdir -p data

# Neprivilegirani uporabnik
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
