FROM python:3.11-slim

WORKDIR /app

# Copy entire source code first
COPY src/ /app/

# Install requirements
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
