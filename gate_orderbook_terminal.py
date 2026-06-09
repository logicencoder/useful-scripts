#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import websocket
import orjson
import time
import threading
import sys

# WebSocket URL for Gate.io Spot API v4
WS_URL = "wss://api.gateio.ws/ws/v4/"

# Trading pairs to subscribe (CAN BE MORE THAN 80, WILL OPEN MULTIPLE CONNECTIONS)
PAIRS = ["XRP_USDT", "DNX_USDT"]

# Update interval: "100ms" or "1000ms"
UPDATE_INTERVAL = "100ms"

# Maximum coins per WebSocket connection
MAX_COINS_PER_CONNECTION = 80


def on_message(ws, message):
    """
    Called when a message is received from the WebSocket.
    Prints ALL orderbook updates to terminal with USD amounts calculated and CUMULATIVE totals.
    """
    try:
        data = orjson.loads(message)
        
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
            
            total_bid_amount = 0.0
            total_bid_usd = 0.0
            total_ask_amount = 0.0
            total_ask_usd = 0.0
            
            if bids:
                print(f"BIDS (Buy Orders) - Total: {len(bids)} levels:")
                cumulative_bid_amount = 0.0
                cumulative_bid_usd = 0.0
                for bid in bids:
                    price = float(bid[0])
                    amount = float(bid[1])
                    usd_value = price * amount
                    cumulative_bid_amount += amount
                    cumulative_bid_usd += usd_value
                    total_bid_amount += amount
                    total_bid_usd += usd_value
                    print(f"  Price: {bid[0]:>15} | Amount: {bid[1]:>15} | USD: ${usd_value:>15.2f} | CUM Amount: {cumulative_bid_amount:>15.4f} | CUM USD: ${cumulative_bid_usd:>15.2f}")
                print(f"  TOTAL BIDS: Amount: {total_bid_amount:>15.4f} | USD Value: ${total_bid_usd:>15.2f}")
            
            if asks:
                print(f"ASKS (Sell Orders) - Total: {len(asks)} levels:")
                cumulative_ask_amount = 0.0
                cumulative_ask_usd = 0.0
                for ask in asks:
                    price = float(ask[0])
                    amount = float(ask[1])
                    usd_value = price * amount
                    cumulative_ask_amount += amount
                    cumulative_ask_usd += usd_value
                    total_ask_amount += amount
                    total_ask_usd += usd_value
                    print(f"  Price: {ask[0]:>15} | Amount: {ask[1]:>15} | USD: ${usd_value:>15.2f} | CUM Amount: {cumulative_ask_amount:>15.4f} | CUM USD: ${cumulative_ask_usd:>15.2f}")
                print(f"  TOTAL ASKS: Amount: {total_ask_amount:>15.4f} | USD Value: ${total_ask_usd:>15.2f}")
            
            # GRAND TOTALS
            grand_total_amount = total_bid_amount + total_ask_amount
            grand_total_usd = total_bid_usd + total_ask_usd
            
            print(f"\n  *** GRAND TOTAL (BIDS + ASKS) ***")
            print(f"  Total Amount: {grand_total_amount:>15.4f} | Total USD Value: ${grand_total_usd:>15.2f}")
            
            print("-" * 80)
        
        # Check if this is a pong response
        elif data.get("channel") == "spot.pong":
            print(f"[PING-PONG] Received pong at {data.get('time')}")
        
        # Print any error messages
        elif data.get("error") is not None:
            print(f"[ERROR] {data}")
            
    except orjson.JSONDecodeError as e:
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


def create_on_open(pairs_chunk, connection_id):
    """
    Creates an on_open callback function for a specific set of pairs.
    
    Args:
        pairs_chunk: List of trading pairs for this connection
        connection_id: ID number of this connection
    
    Returns:
        on_open function
    """
    def on_open(ws):
        print(f"[CONNECTION {connection_id} OPENED] WebSocket connected successfully!")
        print(f"[CONNECTION {connection_id}] Subscribing to {len(pairs_chunk)} pairs: {', '.join(pairs_chunk)}")
        print(f"[CONNECTION {connection_id}] Update interval: {UPDATE_INTERVAL}")
        print("=" * 80)
        
        # Subscribe to orderbook updates for each pair in this chunk
        for pair in pairs_chunk:
            subscribe_message = {
                "time": int(time.time()),
                "channel": "spot.order_book_update",
                "event": "subscribe",
                "payload": [pair, UPDATE_INTERVAL]
            }
            
            try:
                ws.send(orjson.dumps(subscribe_message).decode('utf-8'))
                print(f"[CONNECTION {connection_id}] Subscribed to {pair}")
            except Exception as e:
                print(f"[CONNECTION {connection_id} ERROR] Failed to subscribe to {pair}: {e}")
        
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
                    ws.send(orjson.dumps(ping_message).decode('utf-8'))
                except Exception as e:
                    print(f"[CONNECTION {connection_id} ERROR] Failed to send ping: {e}")
                    break
        
        ping_thread = threading.Thread(target=send_ping, daemon=True)
        ping_thread.start()
    
    return on_open


def split_pairs_into_chunks(pairs, chunk_size):
    """
    Split list of pairs into chunks of maximum size.
    
    Args:
        pairs: List of trading pairs
        chunk_size: Maximum size of each chunk
    
    Returns:
        List of chunks
    """
    chunks = []
    for i in range(0, len(pairs), chunk_size):
        chunks.append(pairs[i:i + chunk_size])
    return chunks


def create_websocket_connection(pairs_chunk, connection_id):
    """
    Create and run a single WebSocket connection for a chunk of pairs.
    
    Args:
        pairs_chunk: List of trading pairs for this connection
        connection_id: ID number of this connection
    """
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=create_on_open(pairs_chunk, connection_id),
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Run forever with automatic reconnection
    ws.run_forever(ping_interval=20, ping_timeout=10)


def main():
    """
    Main function to start WebSocket connections.
    Opens multiple connections if there are more than MAX_COINS_PER_CONNECTION pairs.
    """
    print("\n" + "=" * 80)
    print("GATE.IO ORDERBOOK WEBSOCKET CLIENT - MULTI-CONNECTION")
    print("=" * 80)
    print(f"Total Trading Pairs: {len(PAIRS)}")
    print(f"Pairs: {', '.join(PAIRS)}")
    print(f"Update Interval: {UPDATE_INTERVAL}")
    print(f"Max Coins Per Connection: {MAX_COINS_PER_CONNECTION}")
    print(f"WebSocket URL: {WS_URL}")
    print("=" * 80)
    
    # Split pairs into chunks of MAX_COINS_PER_CONNECTION
    pairs_chunks = split_pairs_into_chunks(PAIRS, MAX_COINS_PER_CONNECTION)
    num_connections = len(pairs_chunks)
    
    print(f"\n[INFO] Total pairs: {len(PAIRS)}")
    print(f"[INFO] Max pairs per connection: {MAX_COINS_PER_CONNECTION}")
    print(f"[INFO] Number of WebSocket connections needed: {num_connections}")
    print("=" * 80 + "\n")
    
    # Create threads for each WebSocket connection
    threads = []
    
    for i, pairs_chunk in enumerate(pairs_chunks, start=1):
        print(f"[INFO] Starting connection {i} with {len(pairs_chunk)} pairs...")
        thread = threading.Thread(
            target=create_websocket_connection,
            args=(pairs_chunk, i),
            daemon=True
        )
        thread.start()
        threads.append(thread)
        time.sleep(0.5)  # Small delay between connection starts
    
    print(f"\n[INFO] All {num_connections} connections started!")
    print("=" * 80 + "\n")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Shutting down all connections...")
        sys.exit(0)


if __name__ == "__main__":
    main()