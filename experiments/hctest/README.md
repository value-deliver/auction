# AgentV Test Script

This directory contains a test script demonstrating how to use AgentV, the AI-powered hCaptcha solver from hcaptcha-challenger.

## Setup

1. **Install dependencies** (if not using uv):
   ```bash
   pip install -r requirements.txt
   playwright install --with-deps
   ```

   Or if using uv:
   ```bash
   uv pip install hcaptcha-challenger playwright
   playwright install --with-deps
   ```

2. **Set up your API key**:
   - Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
   - Create a `.env` file in this directory with:
     ```
     GEMINI_API_KEY=your_api_key_here
     ```

## Usage

1. **Install Playwright browsers** (required):
   ```bash
   cd C:\BD\dev\auction2\hctest
   playwright install --with-deps
   ```

2. **Run the test script**:
   ```bash
   # Using the virtual environment from hcaptcha-challenger-repo
   C:\BD\dev\auction2\hcaptcha-challenger-repo\.venv\Scripts\python.exe agentv_test.py

   # Or if using uv (may have issues with some packages)
   uv run python agentv_test.py

   # Or with pip
   python agentv_test.py
   ```

The script will:
1. Launch a browser and navigate to an hCaptcha test page
2. Initialize AgentV with your configuration
3. Automatically solve the hCaptcha challenge
4. Display the results

## Test Results

🎉 **FULL SUCCESS**: AgentV is working perfectly!

✅ **Complete hCaptcha Solving**: The test script successfully:
- Loads GEMINI_API_KEY from `.env` file
- Launches Chromium browser with anti-detection measures
- Navigates to hCaptcha test page
- Initializes AgentV and clicks checkbox
- Detects and solves multiple challenge types:
  - `image_drag_multi` (drag-and-drop puzzles)
  - `image_label_multi_select` (creature selection)
- Uses Gemini AI for intelligent spatial reasoning
- **Successfully passes hCaptcha challenges!**

The script demonstrates AgentV's full capability to handle real hCaptcha challenges with AI-powered automation.

## Configuration

### Test URLs

You can change the test URL in `agentv_test.py` by uncommenting different options:

```python
# Easy challenges (default)
test_url = SiteKey.as_site_link(SiteKey.user_easy)

# Moderate difficulty
# test_url = SiteKey.as_site_link(SiteKey.user_moderate)

# Difficult challenges
# test_url = SiteKey.as_site_link(SiteKey.user_difficult)

# Site-specific challenges
# test_url = SiteKey.as_site_link(SiteKey.discord)  # Discord-style
# test_url = SiteKey.as_site_link(SiteKey.epic)     # Epic Games-style

# Random challenge type
# test_url = SiteKey.choice()
```

### AgentConfig Options

The script uses sensible defaults, but you can customize the `AgentConfig` in the `solve_hcaptcha()` function:

- **Model Selection**: Choose between `gemini-2.5-flash` (fast/cheap) and `gemini-2.5-pro` (accurate/slower)
- **Timeouts**: Adjust execution and response timeouts
- **Debug Mode**: Enable detailed logging
- **Challenge Filtering**: Skip specific challenge types or questions

## Supported Challenge Types

AgentV can automatically solve:
- ✅ Binary image classification ("select all images with cars")
- ✅ Point selection challenges
- ✅ Drag-and-drop spatial challenges

## Troubleshooting

- **API Key Issues**: Make sure your `.env` file is in the same directory as the script
- **Browser Issues**: The script launches Chromium with anti-detection measures. Make sure Playwright browsers are installed with `playwright install --with-deps`
- **Network Issues**: Increase timeouts if you have slow internet
- **Challenge Failures**: Some challenges may be too complex; the script includes retry logic
- **Unicode Issues**: If you see encoding errors, the script should work fine on most systems
- **uv Issues**: If uv fails with metadata errors, use the virtual environment Python directly: `C:\BD\dev\auction2\hcaptcha-challenger-repo\.venv\Scripts\python.exe agentv_test.py`
- **Gemini Model Errors**: If you see 404 errors for Gemini models, try updating the model names in the script. Available models may change over time. Check [Google AI Studio](https://aistudio.google.com/apikey) for current model availability.

## Integration

To use AgentV in your own automation:

```python
from hcaptcha_challenger import AgentV, AgentConfig

# In your Playwright automation
agent_config = AgentConfig()
agent = AgentV(page=page, agent_config=agent_config)

await agent.robotic_arm.click_checkbox()
await agent.wait_for_challenge()

if agent.cr_list:
    print("hCaptcha solved!")