import asyncio
import aiohttp
import struct
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import signal
import sys
import os
import argparse


# FIX PROTOBUF VERSION COMPATIBILITY ISSUE
print("🔧 FIXED PROTOBUF COMPATIBILITY - Using pure Python implementation")

# Global flag to stop the script gracefully
stop_flag = False

# Global log file handle
log_file = None

def signal_handler(sig, frame):
    global stop_flag
    print('\n🛑 STOP signal received - shutting down gracefully...')
    stop_flag = True

def setup_logging(symbol):
    """Setup log file in logs directory with timestamp and coin name"""
    global log_file
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create log filename with timestamp and symbol
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_filename = f"logs/{timestamp}_{symbol}.log"
    
    # Open log file
    log_file = open(log_filename, 'a', buffering=1)  # Line buffered
    print(f"📝 Logging to: {log_filename}")
    
    return log_filename

def log_message(message):
    """Write message to both console and log file"""
    print(message)
    if log_file:
        log_file.write(message + '\n')

def get_symbol_input():
    """Get trading symbol from user input"""
    while True:
        user_input = input("Enter coin symbol (e.g., ETH, BTC, ETHUSDT, BTCUSDT): ").strip().upper()
        
        if not user_input:
            print("Please enter a valid symbol!")
            continue
            
        # Handle different input formats
        if user_input.endswith("USDT"):
            symbol = user_input
        elif len(user_input) <= 5 and user_input.isalpha():
            symbol = user_input + "USDT"
        else:
            symbol = user_input
            
        print(f"Using symbol: {symbol}")
        return symbol

async def send_ping(websocket):
    """Send ping messages to keep connection alive"""
    global stop_flag
    while not stop_flag:
        try:
            await asyncio.sleep(25)
            if stop_flag:
                break
            ping_msg = {"method": "PING"}
            await websocket.send_json(ping_msg)
            log_message(f"🏓 Ping sent at {datetime.now().strftime('%H:%M:%S')}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            log_message(f"❌ Ping error: {e}")
            break

async def subscribe_to_symbol(websocket, symbol):
    """Subscribe to symbol trades"""
    subscription_message = {
        "method": "SUBSCRIPTION",
        "params": [f"spot@public.aggre.deals.v3.api.pb@100ms@{symbol}"]
    }
    await websocket.send_json(subscription_message)
    log_message(f"✅ Subscribed to {symbol}")
    return f"spot@public.aggre.deals.v3.api.pb@100ms@{symbol}"

def decode_varint(data, offset):
    """Decode a protobuf varint from binary data"""
    result = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        offset += 1
        if (byte & 0x80) == 0:
            break
        shift += 7
    return result, offset

def decode_string(data, offset):
    """Decode a protobuf string from binary data"""
    length, offset = decode_varint(data, offset)
    if offset + length > len(data):
        return "", offset
    string_data = data[offset:offset + length].decode('utf-8', errors='ignore')
    return string_data, offset + length

def parse_protobuf_trades(binary_data):
    """Parse MEXC protobuf trade messages manually"""
    try:
        trades = []
        offset = 0
        
        # Skip initial bytes and find trade data section
        while offset < len(binary_data) - 10:
            if binary_data[offset] == 0x0a:  # Field 1 (channel)
                # Skip channel field
                channel_len, offset = decode_varint(binary_data, offset + 1)
                offset += channel_len
            elif binary_data[offset] == 0x1a:  # Field 3 (symbol)
                # Skip symbol field
                symbol_len, offset = decode_varint(binary_data, offset + 1)
                offset += symbol_len
            elif binary_data[offset] == 0xd2 and offset + 1 < len(binary_data) and binary_data[offset + 1] == 0x13:
                # Found trade data section (field 26, wire type 2)
                offset += 2
                trades_section_len, offset = decode_varint(binary_data, offset)
                trades_end = offset + trades_section_len
                
                # Parse individual trades within this section
                while offset < trades_end and offset < len(binary_data):
                    if binary_data[offset] == 0x0a:  # Individual trade (field 1)
                        offset += 1
                        trade_len, offset = decode_varint(binary_data, offset)
                        trade_end = offset + trade_len
                        
                        trade = {}
                        
                        # Parse trade fields
                        while offset < trade_end and offset < len(binary_data):
                            field_byte = binary_data[offset]
                            
                            if field_byte == 0x0a:  # Price (field 1)
                                offset += 1
                                price, offset = decode_string(binary_data, offset)
                                trade['price'] = price
                                
                            elif field_byte == 0x12:  # Quantity (field 2)
                                offset += 1
                                quantity, offset = decode_string(binary_data, offset)
                                trade['quantity'] = quantity
                                
                            elif field_byte == 0x18:  # Trade type (field 3)
                                offset += 1
                                trade_type, offset = decode_varint(binary_data, offset)
                                trade['tradetype'] = trade_type
                                
                            elif field_byte == 0x20:  # Timestamp (field 4)
                                offset += 1
                                timestamp, offset = decode_varint(binary_data, offset)
                                trade['time'] = timestamp
                                
                            else:
                                offset += 1
                        
                        if 'price' in trade and 'quantity' in trade and 'tradetype' in trade:
                            trades.append(trade)
                    else:
                        offset += 1
                break
            else:
                offset += 1
                
        return trades
    except Exception as e:
        log_message(f"Error parsing protobuf: {e}")
        return []

async def process_message(message_type, message_data):
    """Process incoming WebSocket messages"""
    try:
        if message_type == aiohttp.WSMsgType.TEXT:
            # Handle JSON responses (subscription confirmations, pings, etc.)
            import orjson
            data = orjson.loads(message_data)
            
            if "code" in data and data["code"] == 0:
                if data.get("msg") == "PONG":
                    return
                else:
                    log_message(f"✅ Server response: {data.get('msg', 'Unknown')}")
                    return
            elif "code" in data and data["code"] != 0:
                log_message(f"❌ Server error: {data}")
                return
                
        elif message_type == aiohttp.WSMsgType.BINARY:
            # Handle protobuf trade data
            trades = parse_protobuf_trades(message_data)
            
            for trade in trades:
                try:
                    price = trade['price']
                    volume = trade['quantity']
                    trade_type = "BUY" if trade['tradetype'] == 1 else "SELL"
                    color = "\033[32m" if trade['tradetype'] == 1 else "\033[31m"
                    
                    # Calculate USDT volume
                    price_dec = Decimal(price)
                    volume_dec = Decimal(volume)
                    usdt_volume = (price_dec * volume_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    
                    # Print colored output (console only)
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - "
                          f"Price: {price}, Amount: {volume}, USDT Amount: {usdt_volume}, "
                          f"Side: {color}{trade_type}\033[0m")
                    
                    # Write to log file (without color codes)
                    if log_file:
                        log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - "
                                      f"Price: {price}, Amount: {volume}, USDT Amount: {usdt_volume}, "
                                      f"Side: {trade_type}\n")
                          
                except (KeyError, ValueError, InvalidOperation) as e:
                    log_message(f"❌ Error processing trade: {e}, trade data: {trade}")
                    
    except Exception as e:
        log_message(f"❌ Error processing message: {e}")

async def maintain_connection(symbol):
    """Maintain a single persistent WebSocket connection"""
    global stop_flag
    ws_url = "ws://wbs-api.mexc.com/ws"
    ping_task = None
    
    log_message(f"🔗 Connecting to MEXC WebSocket...")
    
    try:
        # Create session with very long timeouts to avoid disconnections
        timeout = aiohttp.ClientTimeout(
            total=None,           # No total timeout
            sock_read=300,        # 5 minutes read timeout
            sock_connect=30       # 30 seconds connect timeout
        )
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.ws_connect(
                ws_url,
                heartbeat=60,         # Longer heartbeat
                receive_timeout=None, # No receive timeout
                compress=15           # Enable compression
            ) as websocket:
                
                log_message(f"✅ Connected to WebSocket!")
                log_message(f"📡 Starting persistent connection for {symbol}")
                log_message(f"⏰ Connection established at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Start ping task
                ping_task = asyncio.create_task(send_ping(websocket))
                
                # Subscribe to the symbol
                await subscribe_to_symbol(websocket, symbol)
                
                # Main message processing loop
                while not stop_flag:
                    try:
                        # Use a timeout to check stop_flag periodically
                        message = await asyncio.wait_for(websocket.receive(), timeout=1.0)
                        
                        if message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            log_message(f"❌ WebSocket closed or error: {message.type}")
                            if not stop_flag:
                                raise ConnectionError("WebSocket connection lost")
                            break
                        
                        await process_message(message.type, message.data)
                        
                    except asyncio.TimeoutError:
                        # Timeout is expected - just check if we should stop
                        continue
                    except Exception as e:
                        if not stop_flag:
                            log_message(f"❌ Error in message loop: {e}")
                            raise
                        break
    
    except Exception as e:
        if not stop_flag:
            log_message(f"❌ Connection error: {e}")
            raise
    
    finally:
        # Cleanup
        log_message(f"🧹 Cleaning up connection...")
        if ping_task and not ping_task.done():
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass
        log_message(f"✅ Connection cleanup completed")

async def main():
    """Main function - maintains ONE persistent connection"""
    global stop_flag, log_file
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='MEXC Real-time Trade Logger')
    parser.add_argument('--coin', type=str, help='Coin symbol (e.g., ETH, BTC, DNXUSDT)')
    args = parser.parse_args()
    
    # Get symbol from argument or user input
    if args.coin:
        user_input = args.coin.strip().upper()
        if user_input.endswith("USDT"):
            symbol = user_input
        elif len(user_input) <= 5 and user_input.isalpha():
            symbol = user_input + "USDT"
        else:
            symbol = user_input
        print(f"Using symbol from argument: {symbol}")
    else:
        symbol = get_symbol_input()
    
    # Setup logging
    log_filename = setup_logging(symbol)
    
    log_message(f"\n🚀 Starting SINGLE persistent connection for {symbol}...")
    log_message(f"📋 This script will maintain ONE connection and NOT create multiple listen keys")
    log_message(f"🛑 Press Ctrl+C to stop gracefully\n")
    
    try:
        # Run with limited retries and longer delays
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts and not stop_flag:
            attempt += 1
            
            try:
                log_message(f"🔄 Connection attempt {attempt}/{max_attempts}")
                await maintain_connection(symbol)
                
                # If we get here, connection ended gracefully
                if stop_flag:
                    break
                
            except Exception as e:
                log_message(f"❌ Connection attempt {attempt} failed: {e}")
                
                if attempt < max_attempts and not stop_flag:
                    delay = 30 * attempt  # 30s, 60s, 90s delays
                    log_message(f"⏳ Waiting {delay} seconds before retry...")
                    
                    # Wait with periodic stop_flag checks
                    for _ in range(delay):
                        if stop_flag:
                            break
                        await asyncio.sleep(1)
        
        if attempt >= max_attempts:
            log_message(f"❌ Max connection attempts ({max_attempts}) reached. Stopping.")
            
    except KeyboardInterrupt:
        log_message(f"\n🛑 Keyboard interrupt received")
    
    finally:
        stop_flag = True
        log_message(f"✅ Script terminated gracefully")
        
        # Close log file
        if log_file:
            log_file.close()

if __name__ == "__main__":
    asyncio.run(main())
    # asyncio.run(main())