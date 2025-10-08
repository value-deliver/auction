#!/bin/bash

# Bash script to build and run Copart login script in Docker with headless=False
# This script sets up a virtual display using Xvfb for GUI mode

IMAGE_NAME="playwright-vnc"

echo "Building Docker image: $IMAGE_NAME"
docker build -t $IMAGE_NAME .

echo "Running Docker container with environment variables"
docker run -it --rm --env-file $(pwd)/.env $IMAGE_NAME