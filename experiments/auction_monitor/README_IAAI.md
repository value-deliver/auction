# IAAI AuctionNow Monitor

This is a real-time monitoring system for IAAI's AuctionNow bidding interface, providing the same interface and listening mechanism as the Copart monitor but adapted for IAAI's AuctionNow page.

## Features

- **Real-time monitoring** of IAAI AuctionNow auctions
- **WebSocket-based updates** for live auction data
- **Bid button detection and highlighting** for visual feedback
- **Manual bid placement** through the web interface
- **MutationObserver** for detecting DOM changes in real-time
- **Network monitoring** for auction API calls

## Architecture

The system consists of:

1. **`iaai_monitor.py`** - IAAI-specific AuctionMonitor class that handles Playwright automation and real-time monitoring
2. **`iaai_app.py`** - Flask application with SocketIO for the web interface
3. **`templates/index_iaai.html`** - Web interface adapted for IAAI AuctionNow
4. **`run_iaai_monitor.sh`** - Setup and run script

## Setup

1. **Install dependencies:**
   ```bash
   cd experiments/auction_monitor
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Run the monitor:**
   ```bash
   ./run_iaai_monitor.sh
   ```

   Or manually:
   ```bash
   python iaai_app.py
   ```

3. **Access the interface:**
   Open http://localhost:5001 in your browser

## Usage

### Starting Monitoring

1. Use `auction_recaptcha.py` to login to IAAI and navigate to an active auction
2. Copy the AuctionNow URL (e.g., `/AuctionNow` or full URL)
3. Paste it in the "Auction URL" field
4. Click "Start" to begin monitoring

### Interface Features

- **Auction URL**: Enter the IAAI AuctionNow page URL
- **Bid Amount**: Enter the amount you want to bid
- **Place Bid**: Triggers bid button highlighting (doesn't actually place bid)
- **Bid Button**: Highlights the bid button on the auction page
- **Real Plus Button**: Highlights and clicks the plus button to increase bid

### Real-time Updates

The monitor provides real-time updates for:
- Current auction item
- Current bid amount
- Time remaining
- Auction status
- Active bidders count

### Bid Button Highlighting

- **Blue highlight**: Manual bid button highlighting
- **Red highlight**: Plus button highlighting and clicking
- Highlights automatically reset after 3 seconds

## Technical Details

### IAAI AuctionNow Page Structure

The monitor is designed to work with IAAI's AuctionNow bidding interface, which includes:

- Main auction events container: `#auctionEvents`
- Navigation elements with auction controls
- Dynamic bidding interface
- Real-time auction data updates

### Monitoring Mechanism

1. **Page Navigation**: Navigates to the provided AuctionNow URL
2. **Element Detection**: Waits for AuctionNow-specific elements to load
3. **MutationObserver**: Monitors DOM changes for real-time updates
4. **Network Monitoring**: Captures WebSocket and API calls
5. **Data Extraction**: Parses auction data from the page

### WebSocket Communication

- Real-time updates sent via SocketIO
- Bid change notifications
- Status updates
- Error handling with fallback to polling

## API Endpoints

- `GET /api/status` - Get current monitoring status
- `POST /api/start` - Start monitoring an auction
- `POST /api/stop` - Stop monitoring
- `POST /api/bid` - Trigger bid button highlighting
- `POST /api/highlight_bid_button` - Highlight bid button
- `POST /api/highlight_plus_button` - Highlight plus button

## Differences from Copart Monitor

- **Page Structure**: Adapted for IAAI's AuctionNow interface vs Copart's iframe-based system
- **Selectors**: IAAI-specific CSS selectors for bid buttons and auction data
- **Navigation**: Direct page navigation instead of iframe handling
- **Data Extraction**: Tailored for IAAI's auction data format

## Troubleshooting

### Common Issues

1. **Page not loading**: Ensure you're logged into IAAI first using `auction_recaptcha.py`
2. **No auction data**: Check that you're on an active AuctionNow page
3. **WebSocket connection failed**: Falls back to polling mode
4. **Bid button not found**: Auction may not be live or selectors need updating

### Debug Information

- Check browser console for JavaScript errors
- Monitor terminal output for Python logging
- Screenshot saved as `debug_auction_page.png` on navigation issues

## Development

### Adding New Features

1. Update `IAAIAuctionMonitor` class in `iaai_monitor.py`
2. Add new API endpoints in `iaai_app.py`
3. Update the web interface in `templates/index_iaai.html`
4. Test with real IAAI AuctionNow pages

### Selector Updates

If IAAI changes their page structure:
1. Inspect the AuctionNow page to find new selectors
2. Update the selector arrays in `iaai_monitor.py`
3. Test bid button detection and highlighting

## Security Notes

- This tool is for educational and research purposes
- Always comply with IAAI's terms of service
- Do not use for automated bidding without permission
- Monitor your usage to avoid rate limiting