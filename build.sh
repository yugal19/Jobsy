#!/bin/bash

set -e  # Fail on error

# Install system dependencies
apt-get update && apt-get install -y \
    chromium-browser \
    chromium-chromedriver \
    python3-pip \
    libnss3 \
    libgconf-2-4 \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    wget \
    unzip

# Make Chrome available under expected alias
ln -s /usr/bin/chromium-browser /usr/bin/google-chrome || true

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
