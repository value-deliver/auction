# Copart Login Automation

This project automates login to Copart's website using Playwright in a Docker container with VNC access.

## Setup

1. **Install Docker** on your system.

2. **Clone or download** this repository.

3. **Configure credentials**:
   - Copy `.env` and update with your actual Copart credentials:
     ```
     COPART_USERNAME=your_username
     COPART_PASSWORD=your_password
     ```
   - **Important**: Never commit the `.env` file with real credentials to version control.

## Usage

### Option 1: Using the provided script (recommended)
```bash
./run_copart_docker.sh
```
This script builds the Docker image and runs the container with environment variables loaded from `.env`.

### Option 2: Manual commands
```bash
# Build the Docker image
docker build -t playwright-vnc .

# Run the container with environment variables
docker run -it --env-file .env playwright-vnc
```

## What it does

- Launches a headless Chromium browser in a Docker container
- Sets up Xvfb for virtual display
- Starts VNC server on port 5900 (accessible locally)
- Automates login to Copart with provided credentials
- Navigates to the user's wishlist

## Security Notes

- Credentials are loaded from environment variables, not hardcoded
- The `.env` file is excluded from Git commits via `.gitignore`
- For production use, consider using Docker secrets or external secret management

## Troubleshooting

- Ensure `.env` contains valid credentials
- Rebuild the image after code changes: `docker build -t playwright-vnc .`
- Check Docker logs: `docker logs <container_id>`