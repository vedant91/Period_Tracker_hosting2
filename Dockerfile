FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create directory for SQLite database (optional)
RUN mkdir -p /app/data

# Set environment variable for port
ENV PORT=8080

# Use gunicorn as production server
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 API_Chatbot:app