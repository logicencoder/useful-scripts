#!/usr/bin/env python3
"""
MEXC 100-Depth Hybrid Trading Bot
WebSocket (top 20) + REST API (full 100) every 200ms
User selects coin to monitor
"""

import asyncio
import websockets
import orjson as json
import time
import logging
import requests
import hmac
import hashlib
import os
import sys
import warnings
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import OrderedDict
import threading
from decimal import Decimal
import uuid

# FastAPI and web components
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
from pydantic import BaseModel

# Suppress warnings
warnings.filterwarnings("ignore")
os.environ['PYTHONWARNINGS'] = 'ignore'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s.%(msecs)03d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    'mexc': {
        'api_key': '',
        'api_secret': '',
        'base_url': 'https://api.mexc.com',
        'ws_url': 'wss://wbs-api.mexc.com/ws',
    },
    'trading': {
        'symbol': 'BTCUSDT',  # Will be set by user
        'rest_api_interval': 0.2,  # 200ms to avoid rate limits
        'max_depth_levels': 100,
        'ws_depth_levels': 20
    },
    'dashboard': {
        'host': '127.0.0.1',
        'port': 8010,
        'display_levels': 100
    }
}

def normalize_symbol(user_input: str) -> str:
    """Normalize symbol input - COPIED FROM YOUR WORKING CODE."""
    try:
        symbol = user_input.strip().upper()
        quote_currencies = ['USDT', 'USDC', 'BTC', 'ETH', 'BNB']
        has_quote = any(symbol.endswith(quote) for quote in quote_currencies)
        
        if not has_quote:
            symbol = symbol + 'USDT'
        
        return symbol
        
    except Exception as e:
        print(f"Error normalizing symbol: {e}")
        return user_input.upper()

def get_symbol_selection() -> str:
    """Ask user to select trading symbol."""
    print("\n" + "="*60)
    print("MEXC 100-Depth Hybrid Trading Bot")
    print("="*60)
    print("Enter the trading symbol to monitor:")
    print("Examples: btc, eth, dnx, ada (will auto-add USDT)")
    print("Or full pairs: BTCUSDT, ETHUSDT, DNXUSDT, etc.")
    print("Case insensitive - works with any caps")
    print("\n" + "="*60)
    
    while True:
        try:
            user_input = input("Enter trading symbol: ").strip()
            
            if not user_input:
                print("Please enter a trading symbol.")
                continue
            
            normalized_symbol = normalize_symbol(user_input)
            
            if len(normalized_symbol) < 6:
                print("Trading symbol too short. Please try again.")
                continue
            
            print(f"Selected symbol: {normalized_symbol}")
            return normalized_symbol
                
        except KeyboardInterrupt:
            print("\nExiting...")
            exit(1)
        except Exception as e:
            print(f"Error: {e}")

from mexc_proto_loader import load_orderbook_modules_safe

def load_generated_proto_protobuf():
    """Load protobuf modules from shared generated_proto/ via mexc_proto_loader."""
    print("📦 LOADING PROTOBUF MODULES FROM generated_proto/ ...")
    modules, ok = load_orderbook_modules_safe()
    if ok:
        print("✅ PROTOBUF MODULES LOADED!")
    else:
        print("❌ generated_proto/ not found or import failed — run mexc_proto_auto_setup.py")
    return modules, ok

def load_api_keys():
    """Load API keys from config/mexc_keys.json."""
    try:
        with open('config/mexc_keys.json', 'r') as f:
            keys = json.loads(f.read())
        
        api_key = keys.get('api_key')
        api_secret = keys.get('api_secret')
        
        if not api_key or not api_secret:
            logger.warning("⚠️ Missing keys in config/mexc_keys.json")
            return None, None
        
        logger.info("✅ API keys loaded")
        return api_key, api_secret
        
    except Exception as e:
        logger.warning(f"⚠️ No API keys: {e}")
        return None, None

@dataclass
class OrderbookLevel:
    """Single orderbook level"""
    price: Decimal
    quantity: Decimal
    source: str  # 'websocket' or 'rest'
    timestamp: float = field(default_factory=time.time)

class HybridOrderbookManager:
    """Manages 100-depth orderbook using WebSocket + REST API hybrid approach"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.lock = threading.RLock()
        
        # Separate storage for WebSocket and REST data
        self.ws_bids = OrderedDict()  # Top 20 from WebSocket
        self.ws_asks = OrderedDict()  # Top 20 from WebSocket
        self.rest_bids = OrderedDict()  # Full 100 from REST
        self.rest_asks = OrderedDict()  # Full 100 from REST
        
        # Merged orderbook (final result)
        self.merged_bids = OrderedDict()  # Final 100 levels
        self.merged_asks = OrderedDict()  # Final 100 levels
        
        # Timestamps
        self.last_ws_update = 0
        self.last_rest_update = 0
        self.update_count = 0
        
        # Callbacks
        self.callbacks = []
    
    def add_callback(self, callback):
        """Add callback for orderbook updates"""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self):
        """Notify callbacks of updates"""
        for callback in self.callbacks:
            try:
                callback(self.get_merged_orderbook())
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def update_websocket_data(self, bids: List[List[str]], asks: List[List[str]]):
        """Update top 20 levels from WebSocket"""
        try:
            with self.lock:
                # Clear and rebuild WebSocket data
                self.ws_bids.clear()
                self.ws_asks.clear()
                
                # Store WebSocket bids (top 20)
                for price_str, qty_str in bids:
                    price = Decimal(price_str)
                    quantity = Decimal(qty_str)
                    self.ws_bids[price] = OrderbookLevel(price, quantity, 'websocket')
                
                # Store WebSocket asks (top 20)
                for price_str, qty_str in asks:
                    price = Decimal(price_str)
                    quantity = Decimal(qty_str)
                    self.ws_asks[price] = OrderbookLevel(price, quantity, 'websocket')
                
                self.last_ws_update = time.time()
                self._merge_orderbooks()
                
                logger.debug(f"📡 WS Update: {len(self.ws_bids)} bids, {len(self.ws_asks)} asks")
                
        except Exception as e:
            logger.error(f"Error updating WebSocket data: {e}")
    
    def update_rest_data(self, bids: List[List[str]], asks: List[List[str]]):
        """Update full 100 levels from REST API"""
        try:
            with self.lock:
                # Clear and rebuild REST data
                self.rest_bids.clear()
                self.rest_asks.clear()
                
                # Store REST bids (full 100)
                for price_str, qty_str in bids:
                    price = Decimal(price_str)
                    quantity = Decimal(qty_str)
                    self.rest_bids[price] = OrderbookLevel(price, quantity, 'rest')
                
                # Store REST asks (full 100)
                for price_str, qty_str in asks:
                    price = Decimal(price_str)
                    quantity = Decimal(qty_str)
                    self.rest_asks[price] = OrderbookLevel(price, quantity, 'rest')
                
                self.last_rest_update = time.time()
                self._merge_orderbooks()
                
                logger.debug(f"🌐 REST Update: {len(self.rest_bids)} bids, {len(self.rest_asks)} asks")
                
        except Exception as e:
            logger.error(f"Error updating REST data: {e}")
    
    def _merge_orderbooks(self):
        """Merge WebSocket (1-20) + REST (21-100) data"""
        try:
            # Determine which data to use
            ws_fresh = (time.time() - self.last_ws_update) < 5.0  # WebSocket data fresh?
            rest_fresh = (time.time() - self.last_rest_update) < 10.0  # REST data fresh?
            
            # Merge bids (highest price first)
            self.merged_bids.clear()
            
            if ws_fresh and rest_fresh:
                # Use WebSocket for top 20, REST for 21-100
                all_bids = {}
                
                # Add REST data first (all levels)
                for price, level in self.rest_bids.items():
                    all_bids[price] = level
                
                # Override top 20 with WebSocket data (more recent)
                for price, level in self.ws_bids.items():
                    all_bids[price] = level
                
                # Sort and take top 100
                sorted_bids = sorted(all_bids.items(), key=lambda x: x[0], reverse=True)[:100]
                self.merged_bids = OrderedDict(sorted_bids)
                
            elif rest_fresh:
                # Use only REST data
                sorted_bids = sorted(self.rest_bids.items(), key=lambda x: x[0], reverse=True)[:100]
                self.merged_bids = OrderedDict(sorted_bids)
                
            elif ws_fresh:
                # Use only WebSocket data (limited to 20)
                sorted_bids = sorted(self.ws_bids.items(), key=lambda x: x[0], reverse=True)[:20]
                self.merged_bids = OrderedDict(sorted_bids)
            
            # Merge asks (lowest price first)
            self.merged_asks.clear()
            
            if ws_fresh and rest_fresh:
                # Use WebSocket for top 20, REST for 21-100
                all_asks = {}
                
                # Add REST data first (all levels)
                for price, level in self.rest_asks.items():
                    all_asks[price] = level
                
                # Override top 20 with WebSocket data (more recent)
                for price, level in self.ws_asks.items():
                    all_asks[price] = level
                
                # Sort and take top 100
                sorted_asks = sorted(all_asks.items(), key=lambda x: x[0])[:100]
                self.merged_asks = OrderedDict(sorted_asks)
                
            elif rest_fresh:
                # Use only REST data
                sorted_asks = sorted(self.rest_asks.items(), key=lambda x: x[0])[:100]
                self.merged_asks = OrderedDict(sorted_asks)
                
            elif ws_fresh:
                # Use only WebSocket data (limited to 20)
                sorted_asks = sorted(self.ws_asks.items(), key=lambda x: x[0])[:20]
                self.merged_asks = OrderedDict(sorted_asks)
            
            self.update_count += 1
            
            # Notify callbacks
            self._notify_callbacks()
            
            if self.update_count % 50 == 0:
                logger.info(f"📊 Merged orderbook #{self.update_count}: {len(self.merged_bids)} bids, {len(self.merged_asks)} asks")
            
        except Exception as e:
            logger.error(f"Error merging orderbooks: {e}")
    
    def get_merged_orderbook(self) -> Dict[str, Any]:
        """Get merged orderbook data for API/display"""
        with self.lock:
            # Calculate spread
            spread = None
            if self.merged_bids and self.merged_asks:
                best_bid = next(iter(self.merged_bids.keys()))
                best_ask = next(iter(self.merged_asks.keys()))
                spread = float(best_ask - best_bid)
            
            return {
                'symbol': self.symbol,
                'timestamp': max(self.last_ws_update, self.last_rest_update),
                'bids': [[str(price), str(level.quantity), level.source] for price, level in list(self.merged_bids.items())],
                'asks': [[str(price), str(level.quantity), level.source] for price, level in list(self.merged_asks.items())],
                'total_bid_levels': len(self.merged_bids),
                'total_ask_levels': len(self.merged_asks),
                'best_bid': str(next(iter(self.merged_bids.keys()))) if self.merged_bids else None,
                'best_ask': str(next(iter(self.merged_asks.keys()))) if self.merged_asks else None,
                'spread': spread,
                'last_ws_update': self.last_ws_update,
                'last_rest_update': self.last_rest_update,
                'update_count': self.update_count
            }
    
    def calculate_liquidity(self, side: str, usd_amount: float) -> Dict[str, Any]:
        """Calculate liquidity using merged 100-level orderbook"""
        try:
            with self.lock:
                levels = self.merged_bids if side == 'sell' else self.merged_asks
                remaining_usd = usd_amount
                total_tokens = Decimal('0')
                levels_used = 0
                
                for price, level in levels.items():
                    if remaining_usd <= 0:
                        break
                        
                    level_usd_value = float(price * level.quantity)
                    
                    if level_usd_value <= remaining_usd:
                        total_tokens += level.quantity
                        remaining_usd -= level_usd_value
                        levels_used += 1
                    else:
                        partial_tokens = Decimal(str(remaining_usd)) / price
                        total_tokens += partial_tokens
                        remaining_usd = 0
                        levels_used += 1
                
                average_price = Decimal(str(usd_amount - remaining_usd)) / total_tokens if total_tokens > 0 else 0
                
                return {
                    'total_tokens': float(total_tokens),
                    'remaining_usd': remaining_usd,
                    'levels_used': levels_used,
                    'average_price': float(average_price),
                    'fully_filled': remaining_usd == 0,
                    'available_levels': len(levels),
                    'max_possible_levels': 100
                }
                
        except Exception as e:
            logger.error(f"Error calculating liquidity: {e}")
            return {'error': str(e)}

class DirectGeneratedProtoOrderbookParser:
    """Protobuf parser for WebSocket data"""
    
    def __init__(self, protobuf_modules):
        self.protobuf_modules = protobuf_modules
    
    def parse_orderbook_update(self, binary_data):
        """Parse WebSocket protobuf message"""
        if not self.protobuf_modules:
            return None
        
        try:
            wrapper_module = self.protobuf_modules['wrapper']
            wrapper = wrapper_module.PushDataV3ApiWrapper()
            wrapper.ParseFromString(binary_data)
            
            # Check for limit depth data
            if hasattr(wrapper, 'publicLimitDepths') and wrapper.HasField('publicLimitDepths'):
                depth_data = wrapper.publicLimitDepths
                bids = []
                asks = []
                
                if hasattr(depth_data, 'bids'):
                    for bid in depth_data.bids:
                        price = bid.price if hasattr(bid, 'price') else '0'
                        quantity = bid.quantity if hasattr(bid, 'quantity') else '0'
                        bids.append([price, quantity])
                
                if hasattr(depth_data, 'asks'):
                    for ask in depth_data.asks:
                        price = ask.price if hasattr(ask, 'price') else '0'
                        quantity = ask.quantity if hasattr(ask, 'quantity') else '0'
                        asks.append([price, quantity])
                
                return {
                    'symbol': wrapper.symbol if hasattr(wrapper, 'symbol') else 'UNKNOWN',
                    'bids': bids,
                    'asks': asks,
                    'type': 'limit_depth'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Protobuf parsing error: {e}")
            return None

class RESTAPIFetcher:
    """Fetches full 100-level orderbook via REST API every 200ms"""
    
    def __init__(self, symbol: str, orderbook_manager: HybridOrderbookManager):
        self.symbol = symbol
        self.orderbook_manager = orderbook_manager
        self.running = False
        self.fetch_thread = None
        self.interval = CONFIG['trading']['rest_api_interval']
        
    def start(self):
        """Start REST API fetching thread"""
        if self.running:
            return
            
        self.running = True
        self.fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self.fetch_thread.start()
        logger.info(f"🌐 Started REST API fetcher (every {self.interval*1000}ms)")
    
    def stop(self):
        """Stop REST API fetching"""
        self.running = False
        if self.fetch_thread:
            self.fetch_thread.join(timeout=5)
        logger.info("🛑 REST API fetcher stopped")
    
    def _fetch_loop(self):
        """Main fetching loop"""
        while self.running:
            try:
                self._fetch_orderbook()
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"REST fetch error: {e}")
                time.sleep(1)
    
    def _fetch_orderbook(self):
        """Fetch 100-level orderbook from REST API"""
        try:
            url = f"{CONFIG['mexc']['base_url']}/api/v3/depth"
            params = {
                'symbol': self.symbol,
                'limit': 100
            }
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = json.loads(response.content)
            
            # Update orderbook manager
            self.orderbook_manager.update_rest_data(data['bids'], data['asks'])
            
        except Exception as e:
            logger.error(f"REST API fetch failed: {e}")

class WebSocketClient:
    """WebSocket client for top 20 levels"""
    
    def __init__(self, symbol: str, orderbook_manager: HybridOrderbookManager, protobuf_modules):
        self.symbol = symbol
        self.orderbook_manager = orderbook_manager
        self.protobuf_parser = DirectGeneratedProtoOrderbookParser(protobuf_modules)
        self.ws = None
        self.running = False
        
    async def connect_and_subscribe(self):
        """Connect to WebSocket and subscribe to top 20 levels"""
        try:
            ws_url = CONFIG['mexc']['ws_url']
            logger.info(f"🔌 Connecting to WebSocket: {ws_url}")
            
            self.ws = await websockets.connect(ws_url)
            self.running = True
            
            # Subscribe to top 20 levels only
            subscription = {
                "method": "SUBSCRIPTION",
                "params": [f"spot@public.limit.depth.v3.api.pb@{self.symbol}@20"]
            }
            
            await self.ws.send(json.dumps(subscription).decode('utf-8'))
            logger.info(f"📡 Subscribed to WebSocket: {self.symbol} @ 20 levels")
            
            # Process messages
            await self._process_messages()
            
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    async def _process_messages(self):
        """Process WebSocket messages"""
        try:
            async for message in self.ws:
                if isinstance(message, bytes):
                    # Parse protobuf
                    parsed_data = self.protobuf_parser.parse_orderbook_update(message)
                    if parsed_data and parsed_data['symbol'] in [self.symbol, 'UNKNOWN']:
                        # Update orderbook manager with top 20 levels
                        self.orderbook_manager.update_websocket_data(
                            parsed_data['bids'], 
                            parsed_data['asks']
                        )
                elif isinstance(message, str):
                    # Handle JSON control messages
                    try:
                        data = json.loads(message)
                        if data.get('code') == 0:
                            logger.debug(f"✅ WebSocket: {data.get('msg')}")
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"WebSocket message processing error: {e}")

# Global instances
orderbook_manager = None
rest_fetcher = None
websocket_client = None

# FastAPI app
app = FastAPI(title="MEXC 100-Depth Hybrid Bot", version="1.0.0")

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve dashboard"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>MEXC 100-Depth Hybrid Bot</title>
    <style>
        body { font-family: Arial, sans-serif; background: #0a0a0a; color: white; margin: 20px; }
        .header { background: #1a1a1a; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .panel { background: #1a1a1a; padding: 15px; border-radius: 10px; }
        table { width: 100%; border-collapse: collapse; font-family: monospace; font-size: 12px; }
        th, td { padding: 5px; text-align: right; border-bottom: 1px solid #333; }
        .bid { color: #00ff88; } .ask { color: #ff4444; } .ws { background: rgba(0,255,136,0.1); } .rest { background: rgba(68,68,255,0.1); }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 MEXC 100-Depth Hybrid Bot</h1>
        <p>WebSocket (top 20) + REST API (full 100) every 200ms</p>
        <div id="status">Connecting...</div>
    </div>
    
    <div class="grid">
        <div class="panel">
            <h3>📊 BIDS (BUY) - 100 Levels</h3>
            <table id="bids-table">
                <tr><th>Price</th><th>Quantity</th><th>Source</th></tr>
            </table>
        </div>
        
        <div class="panel">
            <h3>📊 ASKS (SELL) - 100 Levels</h3>
            <table id="asks-table">
                <tr><th>Price</th><th>Quantity</th><th>Source</th></tr>
            </table>
        </div>
    </div>

    <script>
        async function updateOrderbook() {
            try {
                const response = await fetch('/api/orderbook');
                const data = await response.json();
                
                document.getElementById('status').innerHTML = 
                    `Symbol: ${data.symbol} | Levels: ${data.total_bid_levels}/${data.total_ask_levels} | ` +
                    `Spread: $${data.spread ? data.spread.toFixed(8) : 'N/A'} | Updates: ${data.update_count}`;
                
                // Update bids table
                const bidsTable = document.getElementById('bids-table');
                bidsTable.innerHTML = '<tr><th>Price</th><th>Quantity</th><th>Source</th></tr>';
                data.bids.slice(0, 50).forEach(([price, qty, source]) => {
                    const row = bidsTable.insertRow();
                    row.className = `bid ${source}`;
                    row.innerHTML = `<td>${parseFloat(price).toFixed(8)}</td><td>${parseFloat(qty).toFixed(6)}</td><td>${source}</td>`;
                });
                
                // Update asks table  
                const asksTable = document.getElementById('asks-table');
                asksTable.innerHTML = '<tr><th>Price</th><th>Quantity</th><th>Source</th></tr>';
                data.asks.slice(0, 50).forEach(([price, qty, source]) => {
                    const row = asksTable.insertRow();
                    row.className = `ask ${source}`;
                    row.innerHTML = `<td>${parseFloat(price).toFixed(8)}</td><td>${parseFloat(qty).toFixed(6)}</td><td>${source}</td>`;
                });
                
            } catch (error) {
                console.error('Error updating orderbook:', error);
            }
        }
        
        // Update every 500ms
        setInterval(updateOrderbook, 500);
        updateOrderbook();
    </script>
</body>
</html>
"""

@app.get("/api/orderbook")
async def get_orderbook():
    """Get merged 100-level orderbook"""
    global orderbook_manager
    
    if not orderbook_manager:
        raise HTTPException(status_code=503, detail="Orderbook not initialized")
    
    return orderbook_manager.get_merged_orderbook()

@app.get("/api/liquidity/{side}")
async def calculate_liquidity(side: str, usd_amount: float):
    """Calculate liquidity using 100 levels"""
    global orderbook_manager
    
    if not orderbook_manager:
        raise HTTPException(status_code=503, detail="Orderbook not initialized")
    
    if side not in ['buy', 'sell']:
        raise HTTPException(status_code=400, detail="Side must be 'buy' or 'sell'")
    
    result = orderbook_manager.calculate_liquidity(side, usd_amount)
    if 'error' in result:
        raise HTTPException(status_code=503, detail=result['error'])
    
    return result

# Application startup
async def start_application():
    """Start all components"""
    global orderbook_manager, rest_fetcher, websocket_client
    
    try:
        # Get user symbol selection
        symbol = get_symbol_selection()
        CONFIG['trading']['symbol'] = symbol
        
        # Load protobuf modules
        protobuf_modules, success = load_generated_proto_protobuf()
        if not success:
            logger.error("❌ Failed to load protobuf modules")
            return False
        
        # Load API keys
        api_key, api_secret = load_api_keys()
        CONFIG['mexc']['api_key'] = api_key or ''
        CONFIG['mexc']['api_secret'] = api_secret or ''
        
        # Initialize hybrid orderbook manager
        orderbook_manager = HybridOrderbookManager(symbol)
        logger.info(f"✅ Initialized hybrid orderbook manager for {symbol}")
        
        # Start REST API fetcher (every 200ms for full 100 levels)
        rest_fetcher = RESTAPIFetcher(symbol, orderbook_manager)
        rest_fetcher.start()
        
        # Start WebSocket client (top 20 levels)
        websocket_client = WebSocketClient(symbol, orderbook_manager, protobuf_modules)
        asyncio.create_task(websocket_client.connect_and_subscribe())
        
        logger.info("✅ All components started successfully")
        logger.info(f"🎯 Monitoring {symbol} with 100-depth hybrid approach")
        logger.info(f"📡 WebSocket: Top 20 levels (real-time)")
        logger.info(f"🌐 REST API: Full 100 levels (every 200ms)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        return False

async def main():
    """Main entry point"""
    logger.info("🚀 Starting MEXC 100-Depth Hybrid Bot")
    
    # Start application components
    success = await start_application()
    if not success:
        logger.error("❌ Failed to start application")
        return
    
    # Start FastAPI server
    logger.info(f"🌐 Starting dashboard on http://127.0.0.1:8010")
    
    config = uvicorn.Config(
        app=app,
        host=CONFIG['dashboard']['host'],
        port=CONFIG['dashboard']['port'],
        log_level="info",
        access_log=False
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    """
    MEXC 100-Depth Hybrid Trading Bot
    
    FEATURES:
    ✅ User selects coin to monitor
    ✅ WebSocket: Top 20 levels (real-time updates)  
    ✅ REST API: Full 100 levels (every 200ms to avoid rate limits)
    ✅ Merged orderbook: WebSocket 1-20 + REST 21-100
    ✅ Dashboard shows source (WebSocket/REST) for each level
    ✅ 100-level liquidity analysis
    ✅ Rate limit safe (5 req/sec vs 50 req/sec limit)
    
    RATE LIMITS:
    - MEXC: ~500 requests per 10 seconds
    - This bot: 5 requests per second (200ms interval)
    - Safe margin: 10x under the limit
    
    RUN:
    1. Make sure generated_proto/ folder exists
    2. python mexc_100depth_hybrid_bot.py
    3. Choose your coin (btc, eth, dnx, etc.)
    4. Open http://127.0.0.1:8010
    """
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
        if rest_fetcher:
            rest_fetcher.stop()
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")