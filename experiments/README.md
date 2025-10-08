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

      # CAPTCHA solving (optional)
      TWOCAPTCHA_API_KEY=your_2captcha_api_key_here
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

## CAPTCHA Solving (IAAI)

The IAAI script includes automatic CAPTCHA detection and solving capabilities:

### Setup CAPTCHA Solving:
1. Sign up for a CAPTCHA solving service like [2Captcha](https://2captcha.com/)
2. Add your API key to `.env`:
   ```
   TWOCAPTCHA_API_KEY=your_api_key_here
   ```
3. Install additional dependency (optional, for full API integration):
   ```bash
   pip install requests
   ```

### How it works:
- Automatically detects when a CAPTCHA appears after login
- Captures the CAPTCHA image and task description
- Sends to 2Captcha service for solving
- Applies the solution automatically

### Supported CAPTCHA Types:
- Image selection CAPTCHAs (like "select all bats" or "select all forest images")
- Grid-based CAPTCHAs
- Coordinate-based CAPTCHAs

### Cost:
- 2Captcha charges approximately $0.001-0.005 per CAPTCHA
- Prices vary by difficulty and type

### Alternative CAPTCHA Services:
- **2Captcha**: Most popular, supports all CAPTCHA types (~$0.001-0.005 per solve)
- **Anti-Captcha**: Good alternative with similar pricing
- **CapSolver**: Advanced AI-powered solving
- **DeathByCaptcha**: Established service with good success rates

### Implementation Details:
The script includes a complete CAPTCHA solving framework:

1. **Detection**: Automatically detects various CAPTCHA types using CSS selectors and text analysis
2. **Screenshot Capture**: Takes screenshots of CAPTCHA challenges
3. **API Integration**: Framework for 2Captcha API (commented implementation provided)
4. **Solution Application**: Parses solutions and clicks appropriate images
5. **Fallback**: Keeps browser open for manual solving if automated solving fails

### Current Implementation Status:
- ✅ CAPTCHA detection and screenshot capture
- ✅ Framework for API integration
- ✅ Solution parsing and image clicking logic
- ⚠️ Full API integration requires `requests` library and uncommenting the API code

### Fallback:
If CAPTCHA solving fails or no API key is provided, the browser remains open for manual solving.

## Anti-Detection Measures

The IAAI script includes several anti-detection measures to avoid triggering security checks:

### Browser Fingerprinting:
- Realistic user agent string with proper Chrome headers
- Standard viewport size (1366x768)
- Proper locale and timezone settings
- Geolocation spoofing (New York coordinates)
- Comprehensive HTTP headers including Sec-Fetch-* headers
- Desktop-specific settings (no touch, not mobile)

### Human-like Behavior:
- Character-by-character typing with random delays (100-400ms)
- Realistic mouse movements with curved paths
- Random scrolling and hovering behaviors
- Variable pause times between actions
- Occasional interaction with non-essential elements

### Timing Randomization:
- Random delays between 0.5-12 seconds for different actions
- Extended pauses before form submission (5-12 seconds)
- Multiple checkpoint waits for dynamic content

### Usage Patterns:
- Sometimes checks "Remember Me" checkbox
- Varies interaction patterns between runs
- Multiple attempts with increasing delays

## Incapsula WAF Protection

IAAI uses **Incapsula (Imperva)** Web Application Firewall with advanced bot detection. If you encounter Incapsula blocks:

### Detection Indicators:
- Page shows: "Request unsuccessful. Incapsula incident ID: ..."
- iframe with `/_Incapsula_Resource` URL
- Incident ID in URL parameters
- "ROBOTS NOINDEX, NOFOLLOW" meta tag

### Causes of Incapsula Blocks:
- **High-frequency requests** from same IP
- **Suspicious behavioral patterns**
- **Inconsistent browser fingerprinting**
- **IP reputation issues**
- **Session analysis anomalies**

### Mitigation Strategies:
1. **Reduce login frequency** (wait hours between attempts)
2. **Use residential proxies** or different IP addresses
3. **Implement longer delays** between sessions
4. **Use consistent browser fingerprints**
5. **Avoid peak hours** when bot detection is stricter

### Script Response:
When Incapsula blocks are detected, the script will:
- Display clear warning messages
- Keep browser open for inspection
- Provide specific remediation steps
- Wait longer (10 minutes) for manual intervention

These measures help avoid detection as automated traffic while maintaining reasonable execution speed.

## Security Notes

- Credentials are loaded from environment variables, not hardcoded
- The `.env` file is excluded from Git commits via `.gitignore`
- For production use, consider using Docker secrets or external secret management

## Troubleshooting

- Ensure `.env` contains valid credentials
- Rebuild the image after code changes: `docker build -t playwright-vnc .`
- Check Docker logs: `docker logs <container_id>`