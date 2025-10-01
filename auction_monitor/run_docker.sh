#!/bin/bash

# Build and run the auction monitor Docker container
# This script should be run from the auction_monitor directory

IMAGE_NAME="auction-monitor"

echo "Building Docker image: $IMAGE_NAME"
docker build -t $IMAGE_NAME .

echo "Running Docker container with environment variables"
echo "Web interface will be available at: http://localhost:5000"
echo "Press Ctrl+C to stop the container"

# Run with environment file from parent directory
docker run -p 5000:5000 --env-file ../.env $IMAGE_NAME