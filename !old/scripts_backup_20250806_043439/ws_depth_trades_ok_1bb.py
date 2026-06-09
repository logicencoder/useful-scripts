#!/usr/bin/env python3

import asyncio
import time
from datetime import datetime
import sys
import os
import subprocess
import json
import struct
from collections import defaultdict

# Third-party imports
import orjson
import websockets

# Global variables
current_orderbook = {'asks': [], 'bids': [], 'last_update': None, 'version': None}
recent_trades = []
ORDERBOOK_DEPTH = 20
display_mode = "live"  # "live" or "snapshot"

def install_requirements():
    """Install required packages including protobuf"""
    required_packages = ['orjson', 'websockets', 'protobuf']
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

def decode_protobuf_message_enhanced(data):
    """Enhanced protobuf decoder that better extracts orderbook data"""
    try:
        result = {
            'type': 'UNKNOWN',
            'channel': '',
            'asks': [],
            'bids': [],
            'trades': [],
            'strings': [],
            'numbers': [],
            'timestamp': None
        }
        
        # Extract readable strings
        strings = extract_strings_from_protobuf(data)
        result['strings'] = strings
        
        # Determine message type from strings
        for s in strings:
            if 'limit.depth' in s:
                result['type'] = 'ORDERBOOK'
                result['channel'] = s
            elif 'aggre.deals' in s or 'deals' in s:
                result['type'] = 'TRADES'
                result['channel'] = s
            elif 'bookTicker' in s:
                result['type'] = 'TICKER'
                result['channel'] = s
        
        # Extract numeric data (prices, quantities, timestamps)
        numbers = extract_numbers_from_protobuf(data)
        result['numbers'] = numbers
        
        # Parse orderbook data if this is an orderbook message
        if result['type'] == 'ORDERBOOK':
            asks, bids = parse_orderbook_from_numbers(numbers, strings)
            result['asks'] = asks
            result['bids'] = bids
        
        # Parse trade data if this is a trades message
        elif result['type'] == 'TRADES':
            trades = parse_trades_from_numbers(numbers, strings)
            result['trades'] = trades
        
        return result
        
    except Exception as e:
        return {
            'error': str(e),
            'type': 'ERROR',
            'size': len(data),
            'hex_preview': data[:50].hex()
        }

def extract_strings_from_protobuf(data):
    """Extract all readable strings from protobuf data"""
    strings = []
    i = 0
    
    while i < len(data):
        # Look for length-prefixed strings (protobuf wire format)
        if i + 1 < len(data):
            length = data[i]
            if 3 <= length <= 200 and i + length + 1 <= len(data):
                try:
                    string_data = data[i+1:i+1+length]
                    decoded = string_data.decode('utf-8')
                    # Check if it's printable ASCII/UTF-8
                    if all(32 <= ord(c) <= 126 or c in '\n\r\t' for c in decoded):
                        strings.append(decoded)
                    i += length + 1
                except:
                    i += 1
            else:
                i += 1
        else:
            i += 1
    
    # Also look for non-length-prefixed strings
    try:
        full_text = data.decode('utf-8', errors='ignore')
        # Extract meaningful parts
        parts = full_text.split('\x00')
        for part in parts:
            cleaned = ''.join(c for c in part if 32 <= ord(c) <= 126)
            if len(cleaned) >= 3 and any(x in cleaned for x in ['spot', 'USDT', 'public', 'depth', 'deals']):
                strings.append(cleaned)
    except:
        pass
    
    return list(set(strings))  # Remove duplicates

def extract_numbers_from_protobuf(data):
    """Extract all numeric values from protobuf data"""
    numbers = []
    
    # Extract 64-bit doubles (most prices/quantities)
    for i in range(len(data) - 7):
        try:
            # Little-endian double
            double_val = struct.unpack('<d', data[i:i+8])[0]
            if 0.00000001 < abs(double_val) < 100000000:  # Reasonable range
                numbers.append(('double', double_val, i))
        except:
            pass
    
    # Extract 32-bit floats
    for i in range(len(data) - 3):
        try:
            float_val = struct.unpack('<f', data[i:i+4])[0]
            if 0.00000001 < abs(float_val) < 100000000:
                numbers.append(('float', float_val, i))
        except:
            pass
    
    # Extract varints (timestamps, sequence numbers)
    i = 0
    while i < len(data):
        try:
            varint, consumed = decode_varint(data[i:])
            if consumed > 0 and 1000000000 < varint < 99999999999999:  # Timestamp range
                numbers.append(('varint', varint, i))
                i += consumed
            else:
                i += 1
        except:
            i += 1
    
    # Sort by position and remove duplicates
    numbers.sort(key=lambda x: x[2])
    unique_numbers = []
    seen_positions = set()
    
    for num_type, value, pos in numbers:
        if pos not in seen_positions:
            unique_numbers.append((num_type, value, pos))
            seen_positions.add(pos)
    
    return unique_numbers

def decode_varint(data):
    """Decode protobuf varint"""
    result = 0
    shift = 0
    consumed = 0
    
    for byte in data:
        consumed += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
        if shift >= 64:
            break
    else:
        return 0, 0
    
    return result, consumed

def parse_orderbook_from_numbers(numbers, strings):
    """Parse orderbook asks/bids from extracted numbers"""
    asks = []
    bids = []
    
    # Filter for price-like values (doubles and floats)
    price_qty_candidates = []
    
    for num_type, value, pos in numbers:
        if num_type in ['double', 'float'] and 0.001 < value < 1000000:
            price_qty_candidates.append((value, pos))
    
    # Sort by position in data
    price_qty_candidates.sort(key=lambda x: x[1])
    
    # Group into price/quantity pairs
    pairs = []
    for i in range(0, len(price_qty_candidates) - 1, 2):
        if i + 1 < len(price_qty_candidates):
            val1, pos1 = price_qty_candidates[i]
            val2, pos2 = price_qty_candidates[i + 1]
            
            # Heuristic: higher value is usually price, lower is quantity
            if val1 > val2 and val1 > 10:  # Price usually > 10 for major cryptos
                price, qty = val1, val2
            elif val2 > val1 and val2 > 10:
                price, qty = val2, val1
            else:
                price, qty = val1, val2  # Default order
            
            pairs.append((price, qty))
    
    # Remove duplicates and sort
    unique_pairs = list(set(pairs))
    unique_pairs.sort(key=lambda x: x[0])
    
    # Split into asks (higher prices) and bids (lower prices)
    if len(unique_pairs) >= 4:
        mid_point = len(unique_pairs) // 2
        
        # Asks: higher prices (sellers)
        asks = [(price, qty) for price, qty in unique_pairs[mid_point:]]
        asks.sort(key=lambda x: x[0])  # Lowest ask first
        
        # Bids: lower prices (buyers)  
        bids = [(price, qty) for price, qty in unique_pairs[:mid_point]]
        bids.sort(key=lambda x: x[0], reverse=True)  # Highest bid first
    
    return asks[:ORDERBOOK_DEPTH], bids[:ORDERBOOK_DEPTH]

def parse_trades_from_numbers(numbers, strings):
    """Parse trade data from extracted numbers"""
    trades = []
    
    # Look for price, quantity, timestamp combinations
    price_candidates = []
    qty_candidates = []
    timestamp_candidates = []
    
    for num_type, value, pos in numbers:
        if num_type in ['double', 'float']:
            if value > 10:  # Likely price
                price_candidates.append((value, pos))
            elif 0.001 < value < 10000:  # Likely quantity
                qty_candidates.append((value, pos))
        elif num_type == 'varint' and value > 1000000000:  # Likely timestamp
            timestamp_candidates.append((value, pos))
    
    # Try to match prices with quantities
    for price, price_pos in price_candidates:
        for qty, qty_pos in qty_candidates:
            if abs(price_pos - qty_pos) < 20:  # Close in data position
                timestamp = None
                for ts, ts_pos in timestamp_candidates:
                    if abs(ts_pos - price_pos) < 50:
                        timestamp = ts
                        break
                
                trades.append({
                    'price': price,
                    'quantity': qty, 
                    'timestamp': timestamp,
                    'side': 'unknown'
                })
    
    return trades[:10]  # Return latest 10 trades

def display_orderbook_table(asks, bids, symbol):
    """Display orderbook in the requested table format"""
    print("\n" + "="*80)
    print(f"                     {symbol} ORDERBOOK")
    print("="*80)
    
    # Header
    print(f"{'ASKS (SELL)':<40} {'BIDS (BUY)':<40}")
    print(f"{'Price':<12} {'Amount':<12} {'Total':<15} {'Price':<12} {'Amount':<12} {'Total':<15}")
    print("-" * 80)
    
    # Calculate totals
    ask_total = 0
    bid_total = 0
    
    max_rows = max(len(asks), len(bids))
    
    for i in range(max_rows):
        ask_line = ""
        bid_line = ""
        
        # Ask side (red)
        if i < len(asks):
            price, qty = asks[i]
            ask_total += qty
            ask_line = f"{price:<12.5f} {qty:<12.2f} {ask_total:<15.2f}"
        else:
            ask_line = " " * 39
        
        # Bid side (green)  
        if i < len(bids):
            price, qty = bids[i]
            bid_total += qty
            bid_line = f"{price:<12.5f} {qty:<12.2f} {bid_total:<15.2f}"
        else:
            bid_line = " " * 39
        
        print(f"{ask_line} {bid_line}")
    
    print("="*80)
    
    # Show spread if we have both asks and bids
    if asks and bids:
        spread = asks[0][0] - bids[0][0]  # Best ask - best bid
        spread_pct = (spread / bids[0][0]) * 100
        print(f"Spread: {spread:.5f} ({spread_pct:.3f}%)")
        print(f"Best Ask: {asks[0][0]:.5f} | Best Bid: {bids[0][0]:.5f}")

def display_trades_table(trades, symbol):
    """Display recent trades"""
    if not trades:
        return
    
    print(f"\n{symbol} RECENT TRADES")
    print("-" * 50)
    print(f"{'Price':<12} {'Quantity':<12} {'Time':<15} {'Side':<8}")
    print("-" * 50)
    
    for trade in trades:
        timestamp_str = ""
        if trade.get('timestamp'):
            try:
                dt = datetime.fromtimestamp(trade['timestamp'] / 1000)
                timestamp_str = dt.strftime('%H:%M:%S')
            except:
                timestamp_str = str(trade['timestamp'])[:8]
        
        print(f"{trade['price']:<12.5f} {trade['quantity']:<12.5f} {timestamp_str:<15} {trade['side']:<8}")

async def connect_websocket(symbol):
    """Connect to MEXC WebSocket with enhanced decoding"""
    ws_url = 'wss://wbs-api.mexc.com/ws'
    
    try:
        print(f"🔗 Connecting to: {ws_url}")
        print(f"🎯 Symbol: {symbol}USDT with depth {ORDERBOOK_DEPTH}")
        
        async with websockets.connect(ws_url) as ws:
            print("✅ Connected successfully!")
            
            # Send PING
            ping_msg = {"method": "PING"}
            await ws.send(orjson.dumps(ping_msg).decode())
            
            # Wait for PONG
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = orjson.loads(response)
            print(f"📋 Server response: {data}")
            
            if 'PONG' in str(data):
                print("✅ JSON format confirmed! Subscribing...")
                
                # Subscribe to orderbook and trades
                subscription = {
                    "method": "SUBSCRIPTION",
                    "params": [
                        f"spot@public.limit.depth.v3.api.pb@{symbol}USDT@{ORDERBOOK_DEPTH}",
                        f"spot@public.aggre.deals.v3.api.pb@100ms@{symbol}USDT"
                    ]
                }
                
                await ws.send(orjson.dumps(subscription).decode())
                print("📨 Subscription sent")
                
                # Handle messages
                await handle_messages_enhanced(ws, symbol)
    
    except Exception as e:
        print(f"❌ Connection failed: {e}")

async def handle_messages_enhanced(ws, symbol):
    """Enhanced message handler with better display"""
    global current_orderbook, recent_trades
    
    last_orderbook_display = 0
    last_trades_display = 0
    
    try:
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=30)
            current_time = time.time()
            
            if isinstance(msg, bytes):
                # Decode protobuf message
                decoded = decode_protobuf_message_enhanced(msg)
                
                # Process orderbook data
                if decoded['type'] == 'ORDERBOOK' and (decoded['asks'] or decoded['bids']):
                    current_orderbook['asks'] = decoded['asks']
                    current_orderbook['bids'] = decoded['bids']
                    current_orderbook['last_update'] = current_time
                    
                    # Display orderbook every 2 seconds or if significant change
                    if current_time - last_orderbook_display > 2:
                        # Clear screen for live updates
                        if display_mode == "live":
                            os.system('clear' if os.name == 'posix' else 'cls')
                        
                        display_orderbook_table(decoded['asks'], decoded['bids'], symbol)
                        last_orderbook_display = current_time
                
                # Process trade data
                elif decoded['type'] == 'TRADES' and decoded['trades']:
                    recent_trades.extend(decoded['trades'])
                    recent_trades = recent_trades[-20:]  # Keep last 20 trades
                    
                    # Display trades every 5 seconds
                    if current_time - last_trades_display > 5:
                        display_trades_table(decoded['trades'], symbol)
                        last_trades_display = current_time
                
                # Debug info (optional)
                if decoded['type'] == 'UNKNOWN':
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"\n📦 [{timestamp}] Unknown message: {len(msg)} bytes")
                    if decoded.get('strings'):
                        print(f"   Strings: {decoded['strings'][:3]}")
                    if decoded.get('numbers'):
                        print(f"   Numbers: {len(decoded['numbers'])} found")
            
            else:
                # Handle JSON messages
                try:
                    data = orjson.loads(msg)
                    print(f"📄 JSON: {data}")
                except:
                    print(f"📄 Text: {msg}")
    
    except asyncio.TimeoutError:
        print("⏰ Message timeout")
    except websockets.exceptions.ConnectionClosed:
        print("🔌 Connection closed")
    except KeyboardInterrupt:
        print("\n👋 Stopping...")
        raise
    except Exception as e:
        print(f"❌ Message handling error: {e}")

async def main():
    """Main function"""
    global display_mode
    
    print("\n" + "="*80)
    print("🚀 ENHANCED MEXC WEBSOCKET - BETTER PROTOBUF DECODING")
    print("="*80)
    print("🔥 This version provides better orderbook display!")
    print("📊 Shows asks/bids in table format with totals")
    print("💱 Displays recent trades")
    print("=" * 80 + "\n")
    
    # Install requirements
    try:
        install_requirements()
    except Exception as e:
        print(f"❌ Failed to install requirements: {e}")
    
    # Get symbol from user
    symbol = input("Enter trading pair symbol (e.g., BTC, ETH): ").upper().strip()
    if not symbol:
        symbol = "ETH"
        print("No symbol entered, using ETH as default")
    
    # Ask for display mode
    mode = input("Display mode - (l)ive updates or (s)napshot updates? [l]: ").lower().strip()
    if mode.startswith('s'):
        display_mode = "snapshot"
        print("📸 Snapshot mode selected")
    else:
        display_mode = "live" 
        print("📺 Live mode selected (clears screen)")
    
    print(f"\n🎯 Starting WebSocket for {symbol}USDT...")
    print("⌨️  Press Ctrl+C to exit\n")
    
    try:
        await connect_websocket(symbol)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n💥 Fatal error: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n💥 Fatal error: {str(e)}")
        sys.exit(1)