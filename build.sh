#!/bin/bash

# Install system dependencies
apt-get update
apt-get install -y \
    chromium-browser \
    chromium-chromedriver \
    python3-pip \
    libnss3 \
    libgconf-2-4

# Install Python dependencies
pip install -r requirements.txt
