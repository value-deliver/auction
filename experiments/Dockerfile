FROM python:3.8-slim

# Install dependencies for Chromium + Xvfb + VNC + window manager
RUN apt-get update && apt-get install -y \
    xvfb x11vnc fluxbox \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxcb1 \
    libxkbcommon0 libx11-6 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libatspi2.0-0 libgtk-3-0 libgdk-pixbuf2.0-0 \
    libx11-xcb1 libxcursor1 libcairo-gobject2 libgstreamer1.0-0 \
    libatomic1 libxslt1.1 libvpx7 libevent-2.1-7 libopus0 \
    libgstreamer-plugins-base1.0-0 libgstreamer-gl1.0-0 \
    libgstreamer-plugins-bad1.0-0 libwebpdemux2 libharfbuzz-icu0 \
    libenchant-2-2 libsecret-1-0 libhyphen0 libmanette-0.2-0 \
    libflite1 libpsl5 libnghttp2-14 libgles2-mesa \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright + Chromium
RUN pip install playwright && playwright install chromium

WORKDIR /app

# Copy your Playwright scripts
COPY copart_login.py /app/copart_login.py
COPY iaai_login.py /app/iaai_login.py

# Copy entrypoint
COPY entrypoint.sh /app/entrypoint.sh

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Expose VNC (localhost only inside container)
EXPOSE 5900

# Use entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

