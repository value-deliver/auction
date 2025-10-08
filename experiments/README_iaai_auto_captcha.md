# IAAI Auto CAPTCHA Solver

A collection of Python scripts that automatically detect and solve CAPTCHAs on the IAAI dashboard using modern solving approaches.

## Features

- **Incapsula WAF Detection**: Specifically detects Incapsula Web Application Firewall iframes (common on IAAI)
- **Enhanced CAPTCHA Detection**: Multi-stage detection including iframes, dynamic content, and text analysis
- **Checkbox CAPTCHA Support**: Automatically handles "I'm not a robot" checkboxes
- **Challenge Detection**: Detects image selection and other challenge types
- **hcaptcha-challenger Integration**: Uses the hcaptcha-challenger library for CAPTCHA analysis and detection
- **SolveCaptcha API Integration**: New dedicated script using SolveCaptcha API for automated hCaptcha solving
- **Incapsula-Specific Solving**: Handles Incapsula iframe-based CAPTCHAs with specialized logic
- **Fallback Handling**: Manual solving when automated methods are unavailable
- **Iframe Content Analysis**: Attempts to analyze CAPTCHA types within Incapsula iframes
- **Cookie Consent Handling**: Automatically handles cookie consent popups
- **Browser Automation**: Uses Playwright for reliable browser automation
- **Comprehensive Error Handling**: Graceful handling of various CAPTCHA scenarios
- **Debug Logging**: Detailed logging for troubleshooting CAPTCHA detection issues

## Prerequisites

1. **Python Environment**: Python 3.7+
2. **Environment Variables**: Set up `.env` file with credentials:
   ```
   IAAI_USERNAME=your_username
   IAAI_PASSWORD=your_password
   SOLVECAPTCHA_API_KEY=your_solvecaptcha_api_key
   ```

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Playwright Browsers**:
   ```bash
   playwright install
   ```

3. **Get SolveCaptcha API Key**:
   Sign up at [SolveCaptcha](https://solvecaptcha.com/) and get your API key

## Usage

### Option 1: hCaptcha Challenger Analysis (iaai_auto_captcha.py)

Run the analysis script:
```bash
python iaai_auto_captcha.py
```

This script uses hcaptcha-challenger for CAPTCHA analysis and provides manual solving guidance.

### Option 2: SolveCaptcha API Solver (iaai_hcaptcha_solver.py) - Recommended

Run the automated solver:
```bash
python iaai_hcaptcha_solver.py
```

This script automatically solves hCaptcha using the SolveCaptcha API service.

Both scripts will:
1. Navigate to `https://www.iaai.com/Dashboard/Default`
2. Handle cookie consent automatically
3. Detect if a CAPTCHA is present
4. Extract the hCaptcha site key
5. Attempt automated solving (Option 2) or provide analysis (Option 1)
6. Inject solution tokens when available
7. Keep the browser open for inspection

## How It Works

### SolveCaptcha API Approach (Recommended)

1. **CAPTCHA Detection**: Scans the page for hCaptcha elements using multiple selectors
2. **Site Key Extraction**: Extracts the hCaptcha site key from `data-sitekey` attributes
3. **API Submission**: Sends site key and page URL to SolveCaptcha API
4. **Polling**: Regularly checks API for solution completion
5. **Token Injection**: Injects the solved token into hidden form fields
6. **Visual Feedback**: Shows confirmation banner when CAPTCHA is solved
7. **Resolution Monitoring**: Keeps browser open for inspection

### hCaptcha Challenger Analysis

1. **CAPTCHA Detection**: Uses hcaptcha-challenger for advanced CAPTCHA analysis
2. **Type Classification**: Analyzes CAPTCHA complexity and challenge types
3. **Manual Guidance**: Provides instructions for manual solving when needed
4. **Fallback Handling**: Graceful degradation to manual methods

## Dependencies

- `playwright`: Browser automation
- `hcaptcha-challenger`: CAPTCHA analysis library
- `requests`: HTTP requests for API communication
- `selenium`: Alternative browser automation (for SolveCaptcha script)
- `webdriver-manager`: Automatic webdriver management
- `python-dotenv`: Environment variable loading

## Error Handling

The script includes comprehensive error handling for:
- Missing HCaptchaSolver library
- CAPTCHA detection failures
- Site key extraction issues
- Solving timeouts
- Network errors

## Troubleshooting

- **SolveCaptcha API key missing**: Set `SOLVECAPTCHA_API_KEY` in your `.env` file
- **hcaptcha-challenger not available**: Install with `pip install hcaptcha-challenger`
- **CAPTCHA not detected**: The script may need updates for new IAAI CAPTCHA implementations
- **Login required**: If redirected to login, manual login may be needed after CAPTCHA solving
- **API timeout**: SolveCaptcha may take up to 5 minutes for complex CAPTCHAs

## Security Note

This script is for educational and automation purposes. Ensure compliance with IAAI's terms of service and applicable laws.