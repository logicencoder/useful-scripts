#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import websocket
import json
import time
import threading
import sys

# WebSocket URL for Gate.io Spot API v4
WS_URL = "wss://api.gateio.ws/ws/v4/"

# Trading pairs to subscribe
PAIRS = ["ETH_USDT", "ADA_USDT"]

# Update interval: "100ms" or "1000ms"
UPDATE_INTERVAL = "100ms"


def on_message(ws, message):
    """
    Called when a message is received from the WebSocket.
    Prints the orderbook updates to terminal.
    """
    try:
        data = json.loads(message)
        
        # Check if this is a successful subscription response
        if data.get("event") == "subscribe" and data.get("result", {}).get("status") == "success":
            print(f"[SUCCESS] Subscribed to channel: {data.get('channel')}")
            print(f"[SUCCESS] Payload: {data.get('result')}")
            print("-" * 80)
            return
        
        # Check if this is an orderbook update
        if data.get("channel") == "spot.order_book_update" and data.get("event") == "update":
            result = data.get("result", {})
            currency_pair = result.get("s", "UNKNOWN")
            timestamp = result.get("t", 0)
            update_id = result.get("u", 0)
            bids = result.get("b", [])
            asks = result.get("a", [])
            
            print(f"\n[ORDERBOOK UPDATE] {currency_pair}")
            print(f"Time: {timestamp} | Update ID: {update_id}")
            
            if bids:
                print("BIDS (Buy Orders):")
                for bid in bids[:5]:  # Show top 5 bids
                    print(f"  Price: {bid[0]:>15} | Amount: {bid[1]:>15}")
            
            if asks:
                print("ASKS (Sell Orders):")
                for ask in asks[:5]:  # Show top 5 asks
                    print(f"  Price: {ask[0]:>15} | Amount: {ask[1]:>15}")
            
            print("-" * 80)
        
        # Check if this is a pong response
        elif data.get("channel") == "spot.pong":
            print(f"[PING-PONG] Received pong at {data.get('time')}")
        
        # Print any error messages
        elif data.get("error") is not None:
            print(f"[ERROR] {data}")
            
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON: {e}")
        print(f"[ERROR] Raw message: {message}")
    except Exception as e:
        print(f"[ERROR] Exception in on_message: {e}")


def on_error(ws, error):
    """
    Called when a WebSocket error occurs.
    """
    print(f"[WEBSOCKET ERROR] {error}")


def on_close(ws, close_status_code, close_msg):
    """
    Called when the WebSocket connection is closed.
    """
    print(f"[CONNECTION CLOSED] Status: {close_status_code}, Message: {close_msg}")


def on_open(ws):
    """
    Called when the WebSocket connection is opened.
    Subscribes to orderbook updates for each trading pair.
    """
    print("[CONNECTION OPENED] WebSocket connected successfully!")
    print(f"[SUBSCRIBING] to pairs: {', '.join(PAIRS)}")
    print(f"[UPDATE INTERVAL] {UPDATE_INTERVAL}")
    print("=" * 80)
    
    # Subscribe to orderbook updates for each pair
    for pair in PAIRS:
        subscribe_message = {
            "time": int(time.time()),
            "channel": "spot.order_book_update",
            "event": "subscribe",
            "payload": [pair, UPDATE_INTERVAL]
        }
        
        try:
            ws.send(json.dumps(subscribe_message))
            print(f"[SENT] Subscribe request for {pair}")
        except Exception as e:
            print(f"[ERROR] Failed to send subscribe message for {pair}: {e}")
    
    print("=" * 80)
    
    # Start a thread to send periodic ping messages to keep connection alive
    def send_ping():
        while True:
            try:
                time.sleep(10)  # Send ping every 10 seconds
                ping_message = {
                    "time": int(time.time()),
                    "channel": "spot.ping"
                }
                ws.send(json.dumps(ping_message))
            except Exception as e:
                print(f"[ERROR] Failed to send ping: {e}")
                break
    
    ping_thread = threading.Thread(target=send_ping, daemon=True)
    ping_thread.start()


def main():
    """
    Main function to start the WebSocket connection.
    """
    print("\n" + "=" * 80)
    print("GATE.IO ORDERBOOK WEBSOCKET CLIENT")
    print("=" * 80)
    print(f"Trading Pairs: {', '.join(PAIRS)}")
    print(f"Update Interval: {UPDATE_INTERVAL}")
    print(f"WebSocket URL: {WS_URL}")
    print("=" * 80 + "\n")
    
    # Enable WebSocket debug output (optional, set to False to disable)
    # websocket.enableTrace(True)
    
    # Create WebSocket connection
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Run forever with automatic reconnection
    # ping_interval: send protocol-level ping every 20 seconds
    # ping_timeout: wait 10 seconds for pong response before considering connection dead
    try:
        ws.run_forever(ping_interval=20, ping_timeout=10)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Shutting down...")
        ws.close()
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()