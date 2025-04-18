#!/bin/bash

# Install system dependencies
apt-get update
apt-get install -y \
    chromium-browser \
    chromium-chromedriver \
    python3-pip \
    libnss3 \          # Fixed: Added missing "s"
    libgconf-2-4

# Install Python dependencies
pip install -r app/requirements.txt

# Set up Chrome symlink
ln -s /usr/bin/chromium-browser /usr/bin/google-chrome  # Fixed: "ln" and correct path