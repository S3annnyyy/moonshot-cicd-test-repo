# Use official Python base image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Expose the port that your FastAPI app listens on
EXPOSE 3123

# Run your app directly
CMD ["python", "app.py"]
