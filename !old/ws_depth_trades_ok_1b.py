#!/usr/bin/env python3

import asyncio
import time
from datetime import datetime
import sys
import os
import subprocess
import json
import struct

# Third-party imports
import orjson
import websockets

# Global variables
current_orderbook = {'asks': [], 'bids': [], 'last_update': None, 'version': None}
recent_trades = []
ORDERBOOK_DEPTH = 20

def install_requirements():
    """Install required packages including protobuf"""
    required_packages = ['orjson', 'websockets', 'protobuf']
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

async def connect_websocket(symbol):
    """Connect to MEXC WebSocket with CORRECT endpoint"""
    retry_delay = 1
    max_delay = 30
    
    # CORRECT WebSocket endpoints to try
    endpoints = [
        'wss://wbs-api.mexc.com/ws',  # Main endpoint from docs
        'wss://stream.mexc.com/ws',   # Alternative stream endpoint
        'wss://api.mexc.com/ws',      # API endpoint
    ]
    
    for ws_url in endpoints:
        try:
            print(f"🔗 Trying WebSocket endpoint: {ws_url}")
            print(f"🎯 Symbol: {symbol}USDT with depth {ORDERBOOK_DEPTH}")
            
            # Try with different connection methods
            connection_methods = [
                # Method 1: Direct connection
                lambda: websockets.connect(ws_url),
                # Method 2: With headers
                lambda: websockets.connect(ws_url, extra_headers={
                    'User-Agent': 'MEXC-Python-Client/1.0'
                }),
                # Method 3: With origin
                lambda: websockets.connect(ws_url, origin='https://www.mexc.com')
            ]
            
            for i, connect_func in enumerate(connection_methods):
                try:
                    print(f"   📡 Connection method {i+1}...")
                    
                    async with connect_func() as ws:
                        print(f"✅ Connected successfully to {ws_url}!")
                        
                        # Try JSON format first (some endpoints still support it)
                        await test_json_subscription(ws, symbol)
                        
                        # If JSON fails, try protobuf format
                        await test_protobuf_subscription(ws, symbol)
                        
                        # Start message loop
                        await handle_messages(ws, symbol)
                        
                except websockets.exceptions.ConnectionClosed:
                    print(f"   ❌ Connection method {i+1} closed")
                    continue
                except Exception as e:
                    print(f"   ❌ Connection method {i+1} failed: {e}")
                    continue
                    
        except Exception as e:
            print(f"💥 Endpoint {ws_url} failed: {str(e)}")
            continue
    
    print("\n❌ ALL ENDPOINTS AND METHODS FAILED!")
    print("🚨 MEXC WebSocket API might be:")
    print("   1. Fully migrated to pure Protobuf (needs .proto files)")
    print("   2. Requiring authentication")
    print("   3. Geo-blocked")
    print("   4. Down for maintenance")
    
    print("\n💡 ALTERNATIVES:")
    print("   1. Use REST API polling")
    print("   2. Switch to Binance/OKX WebSocket")  
    print("   3. Wait for community protobuf implementation")

async def test_json_subscription(ws, symbol):
    """Test JSON format subscription"""
    try:
        print("🧪 Testing JSON format...")
        
        # Send PING
        ping_msg = {"method": "PING"}
        await ws.send(orjson.dumps(ping_msg).decode())
        
        # Wait for response with timeout
        response = await asyncio.wait_for(ws.recv(), timeout=5)
        
        # Try to parse as JSON
        try:
            data = orjson.loads(response)
            print(f"📋 JSON Response: {data}")
            
            if 'PONG' in str(data):
                print("✅ JSON format works! Subscribing...")
                
                # Subscribe to channels
                subscription = {
                    "method": "SUBSCRIPTION",
                    "params": [
                        f"spot@public.limit.depth.v3.api.pb@{symbol}USDT@{ORDERBOOK_DEPTH}",
                        f"spot@public.aggre.deals.v3.api.pb@100ms@{symbol}USDT"
                    ]
                }
                
                await ws.send(orjson.dumps(subscription).decode())
                print("📨 JSON subscription sent")
                return True
                
        except:
            print("❌ Response is not JSON, trying protobuf...")
            return False
            
    except asyncio.TimeoutError:
        print("⏰ JSON test timeout")
        return False
    except Exception as e:
        print(f"❌ JSON test failed: {e}")
        return False

async def test_protobuf_subscription(ws, symbol):
    """Test Protobuf format subscription"""
    try:
        print("🧪 Testing Protobuf format...")
        
        # Create a simple protobuf-like message
        # This is a placeholder - real implementation needs .proto files
        
        # Try sending subscription as binary
        subscription_data = create_protobuf_subscription(symbol)
        await ws.send(subscription_data)
        
        # Wait for binary response
        response = await asyncio.wait_for(ws.recv(), timeout=5)
        
        if isinstance(response, bytes):
            print(f"📋 Received binary data: {len(response)} bytes")
            # Try to decode protobuf (placeholder)
            decoded = decode_protobuf_message(response)
            print(f"📋 Decoded: {decoded}")
            return True
        else:
            print("❌ Expected binary response for protobuf")
            return False
            
    except asyncio.TimeoutError:
        print("⏰ Protobuf test timeout")
        return False
    except Exception as e:
        print(f"❌ Protobuf test failed: {e}")
        return False

def create_protobuf_subscription(symbol):
    """Create protobuf subscription message (placeholder)"""
    # This is a PLACEHOLDER - real implementation needs:
    # 1. Download .proto files from mexcdevelop/websocket-proto
    # 2. Compile them with protoc
    # 3. Use generated Python classes
    
    # For now, create a simple binary message
    message = f"SUBSCRIPTION:{symbol}USDT:depth{ORDERBOOK_DEPTH}"
    return message.encode('utf-8')

def decode_protobuf_message(data):
    """Decode protobuf message and extract readable data"""
    try:
        # Convert hex to readable strings to find channel names
        hex_str = data.hex()
        readable_parts = []
        
        # Look for ASCII strings in the data (channels, prices, etc.)
        i = 0
        while i < len(data):
            # Look for length-prefixed strings (protobuf format)
            if i + 1 < len(data):
                length = data[i]
                if 5 <= length <= 100 and i + length + 1 <= len(data):  # Reasonable string length
                    try:
                        string_data = data[i+1:i+1+length]
                        decoded = string_data.decode('utf-8')
                        if all(32 <= ord(c) <= 126 for c in decoded):  # Printable ASCII
                            readable_parts.append(decoded)
                        i += length + 1
                    except:
                        i += 1
                else:
                    i += 1
            else:
                i += 1
        
        # Look for full channel names in hex
        hex_text = bytes.fromhex(hex_str[:200]).decode('utf-8', errors='ignore')
        
        # Also look for numeric data (prices, quantities) 
        price_qty_pairs = extract_orderbook_data(data)
        
        # Determine message type
        message_type = "UNKNOWN"
        channel_found = ""
        
        for part in readable_parts:
            if 'limit.depth' in part:
                message_type = "ORDERBOOK"
                channel_found = part
                break
            elif 'aggre.deals' in part:
                message_type = "TRADES"  
                channel_found = part
                break
            elif 'bookTicker' in part:
                message_type = "TICKER"
                channel_found = part
                break
        
        # Check hex text for channel names
        if message_type == "UNKNOWN":
            if 'limit.depth' in hex_text:
                message_type = "ORDERBOOK"
            elif 'aggre.deals' in hex_text:
                message_type = "TRADES"
            elif 'bookTicker' in hex_text:
                message_type = "TICKER"
        
        return {
            'type': message_type,
            'channel': channel_found,
            'strings': readable_parts,
            'orderbook': price_qty_pairs,
            'size': len(data)
        }
        
    except Exception as e:
        return {
            'error': str(e),
            'type': 'ERROR',
            'size': len(data)
        }

def extract_orderbook_data(data):
    """Extract orderbook price/quantity pairs from protobuf data"""
    pairs = []
    
    try:
        import struct
        
        # Look for 64-bit doubles in the data (prices and quantities)
        i = 0
        numbers = []
        
        while i <= len(data) - 8:
            try:
                # Try little-endian double
                double_val = struct.unpack('<d', data[i:i+8])[0]
                if 0.00000001 < abs(double_val) < 10000000:  # Reasonable range
                    numbers.append((double_val, i))
                i += 1
            except:
                i += 1
        
        # Sort by position and group into price/quantity pairs
        numbers.sort(key=lambda x: x[1])  # Sort by position in data
        
        # Group consecutive numbers as price/quantity pairs
        for i in range(0, len(numbers) - 1, 2):
            if i + 1 < len(numbers):
                val1 = numbers[i][0]
                val2 = numbers[i+1][0] 
                
                # Determine which is price vs quantity based on typical ranges
                if val1 > val2 and val1 > 100:  # Higher value likely price
                    price, qty = val1, val2
                elif val2 > val1 and val2 > 100:  # Higher value likely price  
                    price, qty = val2, val1
                elif val1 > 1 and val2 < 100000:  # First one price, second quantity
                    price, qty = val1, val2
                else:
                    price, qty = val1, val2
                
                pairs.append((price, qty))
        
        # Remove duplicates and sort by price
        seen = set()
        unique_pairs = []
        for price, qty in pairs:
            key = (round(price, 8), round(qty, 8))
            if key not in seen:
                seen.add(key)
                unique_pairs.append((price, qty))
        
        # Sort by price (highest first for asks)
        unique_pairs.sort(key=lambda x: x[0], reverse=True)
        
        return unique_pairs[:40]  # Return top 40 pairs
        
    except Exception as e:
        return []

async def handle_messages(ws, symbol):
    """Handle incoming messages"""
    try:
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=30)
            
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            
            if isinstance(msg, bytes):
                print(f"\n📦 BINARY MESSAGE @ {timestamp}")
                print(f"📊 Size: {len(msg)} bytes")
                
                # Decode protobuf data
                decoded = decode_protobuf_message(msg)
                
                # Identify message type from strings
                message_type = "UNKNOWN"
                if any('limit.depth' in s for s in decoded.get('strings', [])):
                    message_type = "ORDERBOOK"
                elif any('deals' in s for s in decoded.get('strings', [])):
                    message_type = "TRADES"
                elif any('bookTicker' in s for s in decoded.get('strings', [])):
                    message_type = "TICKER"
                
                print(f"📋 Type: {message_type}")
                print(f"📋 Channels: {decoded.get('strings', [])}")
                
                if decoded.get('numbers'):
                    print(f"💰 Prices/Quantities: {decoded['numbers'][:10]}")  # Show top 10
                    
                    if message_type == "ORDERBOOK" and len(decoded['numbers']) >= 4:
                        # Try to identify ask/bid structure
                        numbers = [float(x) for x in decoded['numbers']]
                        numbers.sort(reverse=True)  # Highest prices first (asks)
                        
                        print(f"\n📊 ORDERBOOK ANALYSIS:")
                        print(f"   💰 Highest prices (likely ASKS):")
                        for i, price in enumerate(numbers[:5]):
                            print(f"      {i+1}. {price:.8f}")
                        
                        print(f"   💵 Lower prices (likely BIDS):")
                        for i, price in enumerate(numbers[-5:]):
                            print(f"      {i+1}. {price:.8f}")
                
                if 'error' in decoded:
                    print(f"❌ Decode error: {decoded['error']}")
                
            else:
                print(f"\n📄 TEXT MESSAGE @ {timestamp}")
                try:
                    data = orjson.loads(msg)
                    print(f"📋 JSON: {data}")
                    
                    # Process market data if available
                    if 'channel' in data:
                        await process_market_data(data, symbol)
                        
                except:
                    print(f"📋 Raw: {msg}")
            
            print("=" * 70)
            
    except asyncio.TimeoutError:
        print("⏰ Message timeout")
    except websockets.exceptions.ConnectionClosed:
        print("🔌 Connection closed")
    except Exception as e:
        print(f"❌ Message handling error: {e}")

async def process_market_data(data, symbol):
    """Process market data from WebSocket"""
    try:
        channel = data.get('channel', '')
        
        if 'depth' in channel or 'limit' in channel:
            print(f"📊 ORDERBOOK DATA for {symbol}")
            
            # Handle different data structures
            if 'publiclimitdepths' in data:
                depths = data['publiclimitdepths']
                asks = depths.get('asksList', [])
                bids = depths.get('bidsList', [])
                
                if asks and bids:
                    print(f"💰 Best Ask: {asks[0]['price']} @ {asks[0]['quantity']}")
                    print(f"💵 Best Bid: {bids[0]['price']} @ {bids[0]['quantity']}")
                    
        elif 'deals' in channel or 'trade' in channel:
            print(f"💱 TRADE DATA for {symbol}")
            
            if 'publicdeals' in data:
                deals = data['publicdeals']
                deals_list = deals.get('dealsList', [])
                
                for deal in deals_list:
                    price = deal.get('price', 'N/A')
                    quantity = deal.get('quantity', 'N/A')
                    trade_type = deal.get('tradetype', 0)
                    side = "🟢 BUY" if trade_type == 1 else "🔴 SELL"
                    
                    print(f"   {side} {price} @ {quantity}")
                    
    except Exception as e:
        print(f"❌ Error processing market data: {e}")

async def main():
    """Main function"""
    print("\n" + "="*75)
    print("🚀 MEXC WEBSOCKET - MULTI-ENDPOINT TESTING")
    print("="*75)
    print("⚠️  MEXC switched to Protobuf on Aug 4, 2025!")
    print("🧪 This script tests JSON + Protobuf formats")
    print("🔍 Tries multiple endpoints and connection methods")
    print("=" * 75 + "\n")
    
    # Install requirements
    try:
        install_requirements()
    except Exception as e:
        print(f"❌ Failed to install requirements: {e}")
        print("📥 Please install manually: pip install websockets orjson protobuf")
    
    # Get symbol from user
    symbol = input("Enter trading pair symbol (e.g., BTC, ETH): ").upper().strip()
    if not symbol:
        symbol = "BTC"
        print("No symbol entered, using BTC as default")
    
    print(f"\n🎯 Testing WebSocket connection for {symbol}USDT...")
    print(f"📊 Orderbook depth: {ORDERBOOK_DEPTH} levels")
    print("⌨️  Press Ctrl+C to exit\n")
    
    try:
        await connect_websocket(symbol)
    except KeyboardInterrupt:
        print("\n👋 Testing stopped")
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