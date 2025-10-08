FROM python:3.8-slim

# Install system dependencies for Playwright + Xvfb for GUI mode
RUN apt-get update && apt-get install -y \
    xvfb x11vnc fluxbox \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxcb1 \
    libxkbcommon0 libx11-6 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libatspi2.0-0 libgtk-3-0 libgdk-pixbuf2.0-0 \
    libx11-xcb1 libxcursor1 libcairo-gobject2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application files
COPY . .

# Set up virtual display
ENV DISPLAY=:99

# Expose ports
EXPOSE 5000 5900

# Start application with virtual display
CMD xvfb-run -a python app_simple.py