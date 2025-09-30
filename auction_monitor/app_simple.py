#!/usr/bin/env python3
"""
Simplified Copart Auction Monitor Web Application
Uses polling instead of WebSocket for compatibility
"""

import os
import asyncio
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from monitor_simple import AuctionMonitor

# Initialize SocketIO first (before decorators)
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'auction-monitor-secret-key'

# Initialize SocketIO with the app
socketio.init_app(app)

# Global monitor instance
monitor = None
monitor_thread = None

# Store socketio instance for monitor to use
socketio_instance = socketio

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('status', {'message': 'Connected to auction monitor'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

@socketio.on('request_status')
def handle_request_status():
    """Send current status to client"""
    if monitor:
        emit('auction_update', {
            'is_monitoring': monitor.is_monitoring,
            'current_auction': monitor.current_auction_data,
            'last_update': monitor.last_update
        })
    else:
        emit('auction_update', {
            'is_monitoring': False,
            'current_auction': None,
            'last_update': None
        })

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index_simple.html')

@app.route('/api/status')
def get_status():
    """Get current monitoring status"""
    print("API /api/status called")  # Debug logging
    response_data = {
        'is_monitoring': monitor.is_monitoring if monitor else False,
        'current_auction': monitor.current_auction_data if monitor else None,
        'last_update': monitor.last_update if monitor else None
    }
    print(f"Returning status: {response_data}")  # Debug logging
    return jsonify(response_data)

@app.route('/api/start', methods=['POST'])
def start_monitoring():
    """Start monitoring an auction"""
    global monitor, monitor_thread
    print("API /api/start called")  # Debug logging

    # Try to get data from form or JSON
    auction_url = None
    if request.is_json:
        data = request.get_json()
        auction_url = data.get('auction_url')
    else:
        auction_url = request.form.get('auction_url')

    print(f"Auction URL: {auction_url}")  # Debug logging

    if not auction_url:
        return jsonify({'success': False, 'message': 'Auction URL is required'})

    if monitor and monitor.is_monitoring:
        return jsonify({'success': False, 'message': 'Already monitoring an auction'})

    try:
        print(f"Creating monitor for URL: {auction_url}")  # Debug logging
        # Initialize monitor with socketio instance
        global socketio_instance
        socketio_instance = socketio
        monitor = AuctionMonitor(socketio_instance)
        print("Monitor created successfully")  # Debug logging

        # Start monitoring in background thread
        print("Starting monitoring thread...")  # Debug logging
        monitor_thread = threading.Thread(target=start_monitoring_thread, args=(auction_url,))
        monitor_thread.daemon = True
        monitor_thread.start()
        print("Monitoring thread started")  # Debug logging

        return jsonify({'success': True, 'message': f'Started monitoring: {auction_url}'})

    except Exception as e:
        print(f"Error starting monitoring: {str(e)}")  # Debug logging
        import traceback
        traceback.print_exc()  # Print full traceback
        return jsonify({'success': False, 'message': f'Failed to start monitoring: {str(e)}'})

@app.route('/api/stop', methods=['POST'])
def stop_monitoring():
    """Stop monitoring"""
    global monitor, monitor_thread

    if monitor:
        monitor.stop_monitoring()
        monitor = None

    if monitor_thread:
        monitor_thread.join(timeout=5)
        monitor_thread = None

    return jsonify({'success': True, 'message': 'Stopped monitoring'})

@app.route('/api/bid', methods=['POST'])
def place_bid():
    """Place a bid on the current auction"""
    print("🔥 API /api/bid endpoint called")
    global monitor

    if not monitor:
        print("❌ No monitor instance available")
        return jsonify({'success': False, 'message': 'No monitor instance available'})

    if not monitor.is_monitoring:
        print("❌ Monitor is not currently monitoring")
        return jsonify({'success': False, 'message': 'No active auction monitoring'})

    print("✅ Monitor is active and monitoring")

    try:
        print("📨 Parsing request JSON...")
        data = request.get_json()
        print(f"📋 Request data: {data}")

        bid_amount = data.get('bid_amount')
        print(f"💰 Bid amount: {bid_amount}")

        if not bid_amount:
            print("❌ No bid amount provided")
            return jsonify({'success': False, 'message': 'Bid amount is required'})

        if bid_amount <= 0:
            print(f"❌ Invalid bid amount: {bid_amount}")
            return jsonify({'success': False, 'message': 'Bid amount must be greater than 0'})

        print(f"🚀 Placing bid for amount: ${bid_amount}")

        # Place bid asynchronously
        success = asyncio.run(monitor.place_bid(bid_amount))
        print(f"📊 Bid placement result: {success}")

        if success:
            print("✅ Bid placed successfully")
            return jsonify({'success': True, 'message': f'Bid placed: ${bid_amount}'})
        else:
            print("❌ Bid placement failed")
            return jsonify({'success': False, 'message': 'Failed to place bid'})

    except Exception as e:
        print(f"💥 Bid endpoint error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Bid failed: {str(e)}'})

@app.route('/api/find_bid_button', methods=['POST'])
def find_bid_button():
    """Run the complete bid button finder functionality"""
    print("🔍 API /api/find_bid_button endpoint called")

    try:
        print("📨 Parsing request JSON...")
        data = request.get_json()
        print(f"📋 Request data: {data}")

        auction_url = data.get('auction_url')
        print(f"🔗 Auction URL: {auction_url}")

        if not auction_url:
            print("❌ No auction URL provided")
            return jsonify({'success': False, 'message': 'Auction URL is required'})

        print(f"🚀 Running bid button finder for: {auction_url}")

        # Create a temporary monitor instance for bid button finding
        temp_monitor = AuctionMonitor(socketio_instance)

        # Run bid button finder asynchronously
        success = asyncio.run(temp_monitor.find_bid_button(auction_url))
        print(f"📊 Bid button finder result: {success}")

        if success:
            print("✅ Bid button finder completed successfully")
            return jsonify({'success': True, 'message': f'Bid button finder completed for: {auction_url}'})
        else:
            print("❌ Bid button finder failed")
            return jsonify({'success': False, 'message': 'Bid button finder failed'})

    except Exception as e:
        print(f"💥 Find bid button endpoint error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Find bid button failed: {str(e)}'})

@app.route('/api/highlight_bid_button', methods=['POST'])
def highlight_bid_button():
    """Manually highlight the bid button with blue color during active monitoring"""
    print("🔵 API /api/highlight_bid_button endpoint called")
    global monitor

    if not monitor:
        print("❌ No monitor instance available")
        return jsonify({'success': False, 'message': 'No monitor instance available'})

    if not monitor.is_monitoring:
        print("❌ Monitor is not currently monitoring")
        return jsonify({'success': False, 'message': 'No active auction monitoring'})

    try:
        print("🔵 Triggering manual bid button highlight...")

        # Run highlight asynchronously
        success = asyncio.run(monitor._highlight_bid_button_manual())
        print(f"📊 Manual highlight result: {success}")

        if success:
            print("✅ Manual bid button highlight completed successfully")
            return jsonify({'success': True, 'message': 'Bid button highlighted successfully'})
        else:
            print("❌ Manual bid button highlight failed")
            return jsonify({'success': False, 'message': 'Bid button highlight failed'})

    except Exception as e:
        print(f"💥 Highlight bid button endpoint error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Highlight failed: {str(e)}'})


def start_monitoring_thread(auction_url):
    """Start monitoring in a separate thread"""
    global monitor

    try:
        asyncio.run(monitor.start_monitoring(auction_url))
    except Exception as e:
        print(f'Monitoring error: {str(e)}')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)