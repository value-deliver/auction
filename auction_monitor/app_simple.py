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

def start_monitoring_thread(auction_url):
    """Start monitoring in a separate thread"""
    global monitor

    try:
        asyncio.run(monitor.start_monitoring(auction_url))
    except Exception as e:
        print(f'Monitoring error: {str(e)}')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)