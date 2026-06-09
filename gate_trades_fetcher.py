import asyncio
import aiohttp
import orjson
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import os
import logging

def setup_logging(symbol):
    """Sets up basic logging to file"""
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create timestamp for filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = os.path.join(log_dir, f"{symbol.lower()}_gateio_{timestamp}.log")
    
    # Setup file logger
    file_handler = logging.FileHandler(log_filename)
    file_formatter = logging.Formatter('%(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Setup logger
    logger = logging.getLogger(symbol)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    
    return logger

async def send_ping(websocket):
    while True:
        try:
            await asyncio.sleep(25)
            await websocket.send_json({"method": "ping"})
        except Exception:
            break

async def subscribe_to_symbol(websocket, symbol):
    subscription_message = {
        "time": int(datetime.now().timestamp()),
        "channel": "spot.trades",
        "event": "subscribe",
        "payload": [symbol]
    }
    await websocket.send_json(subscription_message)
    print(f"Subscribed to {symbol}")

async def process_message(message, logger, display_symbol):
    try:
        data = orjson.loads(message)
        if "event" in data and data["event"] == "update" and "result" in data:
            trade = data["result"]
            price = trade["price"]
            volume = trade["amount"]
            is_buy = trade["side"] == "buy"
            trade_type = "BUY" if is_buy else "SELL"
            color = "\033[32m" if is_buy else "\033[31m"  # Green for buy, Red for sell
            
            # Calculate USDT volume
            price_dec = Decimal(price)
            volume_dec = Decimal(volume)
            usdt_volume = (price_dec * volume_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            # Console output (colored)
            print(f"{timestamp} - {display_symbol} - Price: {price}, Amount: {volume}, "
                  f"USDT Amount: {usdt_volume}, Side: {color}{trade_type}\033[0m")
            
            # File output (plain text, no colors)
            logger.info(f"{timestamp} - {display_symbol} - Price: {price}, Amount: {volume}, "
                       f"USDT Amount: {usdt_volume}, Side: {trade_type}")
            
    except Exception as e:
        print(f"Error processing message: {e}")

async def main():
    symbol = "DNX_USDT"  # Gate.io uses underscore instead of direct pair
    display_symbol = "DNXUSDT"  # For display/logging purposes, like MEXC format
    # symbol = "ETH_USDT"
    ws_url = "wss://api.gateio.ws/ws/v4/"
    
    # Setup logging
    logger = setup_logging(display_symbol)
    
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url, heartbeat=30) as websocket:
                    print(f"Connected to WebSocket")
                    
                    # Start ping task
                    ping_task = asyncio.create_task(send_ping(websocket))
                    
                    # Subscribe to the symbol
                    await subscribe_to_symbol(websocket, symbol)
                    
                    # Process messages
                    async for message in websocket:
                        if message.type == aiohttp.WSMsgType.TEXT:
                            await process_message(message.data, logger, display_symbol)
                        elif message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
                    
                    ping_task.cancel()
                    
        except Exception as e:
            print(f"Connection error: {e}")
            print("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript stopped by user")