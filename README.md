# Auction Login Automation

This project automates login to Copart and IAAI websites using Playwright in a Docker container with VNC access.

## Setup

1. **Install Docker** on your system.

2. **Clone or download** this repository.

3. **Configure credentials**:
    - Update `.env` with your actual credentials:
      ```
      # Copart login credentials
      COPART_USERNAME=your_copart_username
      COPART_PASSWORD=your_copart_password

      # IAAI login credentials
      IAAI_USERNAME=your_iaai_email@example.com
      IAAI_PASSWORD=your_iaai_password
      ```
    - **Important**: Never commit the `.env` file with real credentials to version control.

## Usage

### Copart Login
```bash
./run_copart_docker.sh
```

### IAAI Login
```bash
./run_iaai_docker.sh
```

These scripts build the Docker image and run the container with environment variables loaded from `.env`.

### Manual commands
```bash
# Build the Docker image
docker build -t playwright-vnc .

# Run Copart script
docker run -it --env-file .env playwright-vnc

# Run IAAI script
docker run -it --env-file .env -e SCRIPT=iaai playwright-vnc
```

## What it does

- Launches a headless Chromium browser in a Docker container
- Sets up Xvfb for virtual display
- Starts VNC server on port 5900 (accessible locally)

### Copart Script
- Automates login to Copart with provided credentials
- Navigates to the user's wishlist and extracts lot numbers

### IAAI Script
- Automates login to IAAI with provided credentials
- Navigates to My Vehicles page and extracts stock numbers and vehicle titles

## Security Notes

- Credentials are loaded from environment variables, not hardcoded
- The `.env` file is excluded from Git commits via `.gitignore`
- For production use, consider using Docker secrets or external secret management

## Troubleshooting

- Ensure `.env` contains valid credentials
- Rebuild the image after code changes: `docker build -t playwright-vnc .`
- Check Docker logs: `docker logs <container_id>`