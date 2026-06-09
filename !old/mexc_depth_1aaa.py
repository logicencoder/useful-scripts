#!/usr/bin/env python3

# DUAL EXCHANGE ORDERBOOK MONITOR - MEXC + GATE.IO
# ALL-IN-ONE FILE - FASTAPI + WEBSOCKETS + EMBEDDED DASHBOARD
# PORT: 8007

import os
import sys
import time
import threading
import asyncio
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, List, Optional, Set
from collections import defaultdict

# External imports
import orjson
import websocket
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dual_orderbook.log'),
        logging.StreamHandler()
    ]
)

# Load protobuf modules for MEXC
def load_mexc_protobuf():
    try:
        if not os.path.exists('generated_proto'):
            logging.error("❌ generated_proto folder not found!")
            return None
        
        if 'generated_proto' not in sys.path:
            sys.path.insert(0, 'generated_proto')
        
        import PushDataV3ApiWrapper_pb2
        import PublicLimitDepthsV3Api_pb2
        import PublicAggreDepthsV3Api_pb2
        
        protobuf_modules = {
            'wrapper': PushDataV3ApiWrapper_pb2,
            'limit_depths': PublicLimitDepthsV3Api_pb2,
            'aggre_depths': PublicAggreDepthsV3Api_pb2
        }
        
        logging.info("✅ MEXC Protobuf modules loaded")
        return protobuf_modules
    except Exception as e:
        logging.error(f"❌ Failed to load protobuf: {e}")
        return None

# Global protobuf modules
PROTOBUF_MODULES = load_mexc_protobuf()

# Symbol normalization functions
def normalize_symbol_mexc(user_input: str) -> str:
    """Convert user input to MEXC format: BTCUSDT"""
    symbol = user_input.strip().upper().replace("_", "")
    quote_currencies = ['USDT', 'USDC', 'BTC', 'ETH', 'BNB']
    has_quote = any(symbol.endswith(quote) for quote in quote_currencies)
    if not has_quote:
        symbol = symbol + 'USDT'
    return symbol

def normalize_symbol_gateio(user_input: str) -> str:
    """Convert user input to Gate.io format: BTC_USDT"""
    symbol = user_input.strip().upper().replace("_", "")
    quote_currencies = ['USDT', 'USDC', 'BTC', 'ETH', 'BNB']
    
    for quote in quote_currencies:
        if symbol.endswith(quote):
            base = symbol[:-len(quote)]
            return f"{base}_{quote}"
    
    return f"{symbol}_USDT"

def format_price(price: str, precision: int = 5) -> str:
    """Format price with specified precision"""
    try:
        price_decimal = Decimal(price)
        scaled = price_decimal.quantize(Decimal('0.' + '0' * precision), rounding=ROUND_HALF_UP)
        return f"{scaled:f}"
    except (InvalidOperation, ValueError):
        return price

def format_quantity(qty: str, precision: int = 6) -> str:
    """Format quantity with specified precision"""
    try:
        qty_decimal = Decimal(qty)
        scaled = qty_decimal.quantize(Decimal('0.' + '0' * precision), rounding=ROUND_HALF_UP)
        return f"{scaled:f}"
    except (InvalidOperation, ValueError):
        return qty

# Orderbook Manager - Shared state
class OrderbookManager:
    def __init__(self):
        self.orderbooks = {
            'MEXC': {},
            'GATEIO': {}
        }
        self.lock = threading.Lock()
        self.websocket_clients: Set[WebSocket] = set()
        self.stats = {
            'MEXC': {'messages': 0, 'connected': False, 'last_update': None},
            'GATEIO': {'messages': 0, 'connected': False, 'last_update': None}
        }
    
    def update_orderbook(self, exchange: str, symbol: str, bids: List, asks: List):
        """Update orderbook data with additional calculations"""
        with self.lock:
            if exchange not in self.orderbooks:
                self.orderbooks[exchange] = {}
            
            # Calculate additional values for bids
            processed_bids = []
            cumulative_qty = 0
            cumulative_usd = 0
            
            for price, quantity in sorted(bids, key=lambda x: float(x[0]), reverse=True):
                price_float = float(price)
                quantity_float = float(quantity)
                total = price_float * quantity_float
                
                cumulative_qty += quantity_float
                cumulative_usd += total
                
                avg_price = cumulative_usd / cumulative_qty if cumulative_qty > 0 else 0
                
                processed_bids.append([
                    price, 
                    quantity, 
                    str(round(cumulative_qty, 6)),  # Cumulative Quantity
                    str(round(total, 2)),  # Total USD
                    str(round(cumulative_usd, 2)),  # Cumulative USD
                    str(round(avg_price, 5))  # Average Price
                ])
            
            # Calculate additional values for asks
            processed_asks = []
            cumulative_qty = 0
            cumulative_usd = 0
            
            for price, quantity in sorted(asks, key=lambda x: float(x[0])):
                price_float = float(price)
                quantity_float = float(quantity)
                total = price_float * quantity_float
                
                cumulative_qty += quantity_float
                cumulative_usd += total
                
                avg_price = cumulative_usd / cumulative_qty if cumulative_qty > 0 else 0
                
                processed_asks.append([
                    price, 
                    quantity, 
                    str(round(cumulative_qty, 6)),  # Cumulative Quantity
                    str(round(total, 2)),  # Total USD
                    str(round(cumulative_usd, 2)),  # Cumulative USD
                    str(round(avg_price, 5))  # Average Price
                ])
            
            self.orderbooks[exchange][symbol] = {
                'bids': processed_bids,
                'asks': processed_asks,
                'timestamp': int(time.time() * 1000)
            }
            
            self.stats[exchange]['messages'] += 1
            self.stats[exchange]['last_update'] = datetime.now().strftime('%H:%M:%S')
    
    def get_orderbook(self, exchange: str, symbol: str) -> Optional[Dict]:
        """Get orderbook data"""
        with self.lock:
            return self.orderbooks.get(exchange, {}).get(symbol)
    
    def get_all_orderbooks(self) -> Dict:
        """Get all orderbook data"""
        with self.lock:
            return {
                'orderbooks': self.orderbooks.copy(),
                'stats': self.stats.copy()
            }
    
    def update_connection_status(self, exchange: str, connected: bool):
        """Update connection status"""
        with self.lock:
            self.stats[exchange]['connected'] = connected
    
    async def broadcast(self, data: Dict):
        """Broadcast data to all connected WebSocket clients"""
        dead_clients = set()
        for client in self.websocket_clients.copy():
            try:
                await client.send_text(orjson.dumps(data).decode('utf-8'))
            except:
                dead_clients.add(client)
        
        self.websocket_clients -= dead_clients

# Global orderbook manager
orderbook_manager = OrderbookManager()

# MEXC WebSocket Connector
class MEXCWebSocketConnector:
    def __init__(self, symbols: List[str], orderbook_manager: OrderbookManager):
        self.symbols = [normalize_symbol_mexc(s) for s in symbols]
        self.orderbook_manager = orderbook_manager
        self.ws_url = "wss://wbs-api.mexc.com/ws"
        self.ws = None
        self.running = False
        self.thread = None
        
        self.protobuf_parser = self._init_protobuf_parser()
        
        logging.info(f"🔧 MEXC Connector initialized with symbols: {self.symbols}")
    
    def _init_protobuf_parser(self):
        """Initialize protobuf parser"""
        if not PROTOBUF_MODULES:
            logging.error("❌ No protobuf modules available")
            return None
        return PROTOBUF_MODULES
    
    def parse_protobuf_message(self, binary_data):
        """Parse protobuf binary message"""
        if not self.protobuf_parser:
            return None
        
        try:
            wrapper_module = self.protobuf_parser['wrapper']
            wrapper = wrapper_module.PushDataV3ApiWrapper()
            wrapper.ParseFromString(binary_data)
            
            bids = []
            asks = []
            symbol = wrapper.symbol if hasattr(wrapper, 'symbol') else 'UNKNOWN'
            
            if hasattr(wrapper, 'publicLimitDepths') and wrapper.HasField('publicLimitDepths'):
                depth_data = wrapper.publicLimitDepths
                
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
                
                return {'symbol': symbol, 'bids': bids, 'asks': asks}
            
            elif hasattr(wrapper, 'publicIncreaseDepths') and wrapper.HasField('publicIncreaseDepths'):
                depth_data = wrapper.publicIncreaseDepths
                
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
                
                return {'symbol': symbol, 'bids': bids, 'asks': asks}
            
            return None
        except Exception as e:
            logging.error(f"❌ MEXC protobuf parsing error: {e}")
            return None
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        if isinstance(message, bytes):
            parsed = self.parse_protobuf_message(message)
            if parsed:
                symbol = parsed['symbol']
                bids = sorted(parsed['bids'], key=lambda x: float(x[0]), reverse=True)[:20]
                asks = sorted(parsed['asks'], key=lambda x: float(x[0]))[:20]
                
                self.orderbook_manager.update_orderbook('MEXC', symbol, bids, asks)
                
                asyncio.run(self.orderbook_manager.broadcast({
                    'type': 'orderbook_update',
                    'exchange': 'MEXC',
                    'symbol': symbol,
                    'data': {'bids': bids, 'asks': asks}
                }))
        else:
            try:
                data = orjson.loads(message)
                if data.get('msg') == 'PONG':
                    logging.debug("🏓 MEXC PONG received")
            except:
                pass
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        logging.error(f"❌ MEXC WebSocket error: {error}")
        self.orderbook_manager.update_connection_status('MEXC', False)
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logging.info(f"🔌 MEXC WebSocket closed")
        self.orderbook_manager.update_connection_status('MEXC', False)
    
    def on_open(self, ws):
        """Handle WebSocket open"""
        logging.info(f"✅ MEXC Connected! Subscribing to {len(self.symbols)} symbols")
        self.orderbook_manager.update_connection_status('MEXC', True)
        
        params = [f"spot@public.limit.depth.v3.api.pb@{s}@20" for s in self.symbols]
        subscription = {"method": "SUBSCRIPTION", "params": params}
        ws.send(orjson.dumps(subscription).decode('utf-8'))
        
        def send_ping():
            while self.running:
                try:
                    if self.ws and self.running:
                        ping_msg = {"method": "PING", "id": int(time.time())}
                        self.ws.send(orjson.dumps(ping_msg).decode('utf-8'))
                    time.sleep(30)
                except:
                    break
        
        ping_thread = threading.Thread(target=send_ping, daemon=True)
        ping_thread.start()
    
    def start(self):
        """Start WebSocket connection"""
        if self.running:
            logging.warning("⚠️ MEXC WebSocket already running")
            return
        
        self.running = True
        
        def run_websocket():
            while self.running:
                try:
                    self.ws = websocket.WebSocketApp(
                        self.ws_url,
                        on_message=self.on_message,
                        on_error=self.on_error,
                        on_close=self.on_close,
                        on_open=self.on_open
                    )
                    self.ws.run_forever()
                except Exception as e:
                    logging.error(f"❌ MEXC WebSocket error: {e}")
                    if self.running:
                        time.sleep(5)
        
        self.thread = threading.Thread(target=run_websocket, daemon=True)
        self.thread.start()
        logging.info("🚀 MEXC WebSocket thread started")
    
    def stop(self):
        """Stop WebSocket connection"""
        logging.info("🛑 Stopping MEXC WebSocket...")
        self.running = False
        if self.ws:
            self.ws.close()
        self.orderbook_manager.update_connection_status('MEXC', False)
        logging.info("✅ MEXC WebSocket stopped")

# Gate.io WebSocket Connector
class GateIOWebSocketConnector:
    def __init__(self, symbols: List[str], orderbook_manager: OrderbookManager):
        self.symbols = [normalize_symbol_gateio(s) for s in symbols]
        self.orderbook_manager = orderbook_manager
        self.ws_url = "wss://api.gateio.ws/ws/v4/"
        self.ws = None
        self.running = False
        self.thread = None
        
        self.current_orderbooks = {}
        for symbol in self.symbols:
            self.current_orderbooks[symbol] = {'bids': [], 'asks': []}
        
        logging.info(f"🔧 Gate.io Connector initialized with symbols: {self.symbols}")
    
    def apply_orderbook_update(self, symbol: str, bids: List, asks: List):
        """Apply incremental orderbook updates"""
        try:
            for price, quantity in bids:
                price_float = float(price)
                quantity_float = float(quantity)
                
                if quantity_float == 0:
                    self.current_orderbooks[symbol]['bids'] = [
                        [p, q] for p, q in self.current_orderbooks[symbol]['bids']
                        if float(p) != price_float
                    ]
                else:
                    updated = False
                    for i, (p, q) in enumerate(self.current_orderbooks[symbol]['bids']):
                        if float(p) == price_float:
                            self.current_orderbooks[symbol]['bids'][i] = [price, quantity]
                            updated = True
                            break
                    if not updated:
                        self.current_orderbooks[symbol]['bids'].append([price, quantity])
            
            for price, quantity in asks:
                price_float = float(price)
                quantity_float = float(quantity)
                
                if quantity_float == 0:
                    self.current_orderbooks[symbol]['asks'] = [
                        [p, q] for p, q in self.current_orderbooks[symbol]['asks']
                        if float(p) != price_float
                    ]
                else:
                    updated = False
                    for i, (p, q) in enumerate(self.current_orderbooks[symbol]['asks']):
                        if float(p) == price_float:
                            self.current_orderbooks[symbol]['asks'][i] = [price, quantity]
                            updated = True
                            break
                    if not updated:
                        self.current_orderbooks[symbol]['asks'].append([price, quantity])
            
            self.current_orderbooks[symbol]['bids'] = sorted(
                self.current_orderbooks[symbol]['bids'],
                key=lambda x: float(x[0]),
                reverse=True
            )[:50]
            
            self.current_orderbooks[symbol]['asks'] = sorted(
                self.current_orderbooks[symbol]['asks'],
                key=lambda x: float(x[0])
            )[:50]
            
        except Exception as e:
            logging.error(f"❌ Gate.io orderbook update error: {e}")
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = orjson.loads(message)
            
            if data.get('event') == 'subscribe' and data.get('result', {}).get('status') == 'success':
                logging.info(f"✅ Gate.io subscription confirmed: {data.get('channel')}")
                return
            
            if data.get('event') == 'update':
                channel = data.get('channel', '')
                
                if channel.startswith('spot.order_book_update'):
                    result = data.get('result', {})
                    symbol = result.get('s', '')
                    
                    if symbol in self.current_orderbooks:
                        bids = result.get('b', [])
                        asks = result.get('a', [])
                        
                        self.apply_orderbook_update(symbol, bids, asks)
                        
                        final_bids = self.current_orderbooks[symbol]['bids'][:50]
                        final_asks = self.current_orderbooks[symbol]['asks'][:50]
                        
                        self.orderbook_manager.update_orderbook('GATEIO', symbol, final_bids, final_asks)
                        
                        asyncio.run(self.orderbook_manager.broadcast({
                            'type': 'orderbook_update',
                            'exchange': 'GATEIO',
                            'symbol': symbol,
                            'data': {'bids': final_bids, 'asks': final_asks}
                        }))
        
        except Exception as e:
            logging.error(f"❌ Gate.io message parsing error: {e}")
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        logging.error(f"❌ Gate.io WebSocket error: {error}")
        self.orderbook_manager.update_connection_status('GATEIO', False)
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logging.info(f"🔌 Gate.io WebSocket closed")
        self.orderbook_manager.update_connection_status('GATEIO', False)
    
    def on_open(self, ws):
        """Handle WebSocket open"""
        logging.info(f"✅ Gate.io Connected! Subscribing to {len(self.symbols)} symbols")
        self.orderbook_manager.update_connection_status('GATEIO', True)
        
        for symbol in self.symbols:
            subscription = {
                "time": int(time.time()),
                "channel": "spot.order_book_update",
                "event": "subscribe",
                "payload": [symbol, "100ms"]
            }
            ws.send(orjson.dumps(subscription).decode('utf-8'))
            time.sleep(0.1)
        
        def send_ping():
            while self.running:
                try:
                    if self.ws and self.running:
                        ping_msg = {
                            "time": int(time.time()),
                            "channel": "spot.ping"
                        }
                        self.ws.send(orjson.dumps(ping_msg).decode('utf-8'))
                    time.sleep(30)
                except:
                    break
        
        ping_thread = threading.Thread(target=send_ping, daemon=True)
        ping_thread.start()
    
    def start(self):
        """Start WebSocket connection"""
        if self.running:
            logging.warning("⚠️ Gate.io WebSocket already running")
            return
        
        self.running = True
        
        def run_websocket():
            while self.running:
                try:
                    self.ws = websocket.WebSocketApp(
                        self.ws_url,
                        on_message=self.on_message,
                        on_error=self.on_error,
                        on_close=self.on_close,
                        on_open=self.on_open
                    )
                    self.ws.run_forever()
                except Exception as e:
                    logging.error(f"❌ Gate.io WebSocket error: {e}")
                    if self.running:
                        time.sleep(5)
        
        self.thread = threading.Thread(target=run_websocket, daemon=True)
        self.thread.start()
        logging.info("🚀 Gate.io WebSocket thread started")
    
    def stop(self):
        """Stop WebSocket connection"""
        logging.info("🛑 Stopping Gate.io WebSocket...")
        self.running = False
        if self.ws:
            self.ws.close()
        self.orderbook_manager.update_connection_status('GATEIO', False)
        logging.info("✅ Gate.io WebSocket stopped")

# Global WebSocket connectors
mexc_connector = None
gateio_connector = None

# FastAPI Application
app = FastAPI(title="Dual Exchange Orderbook Monitor")

# Embedded HTML Dashboard
HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dual Exchange Orderbook Monitor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Courier New', monospace; }
        .orderbook-row { font-size: 0.75rem; }
        .status-indicator { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
        .status-connected { background-color: #10b981; }
        .status-disconnected { background-color: #ef4444; }
        table { table-layout: fixed; width: 100%; }
        th, td { padding: 2px 4px; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .bid-price { color: #10b981; }
        .ask-price { color: #ef4444; }
        .quantity { color: #ffffff; }
        .avg-price { color: #60a5fa; }
        .total-usd { color: #fbbf24; }
        .cum-qty { color: #a78bfa; }
        .cum-usd { color: #34d399; }
        .profit { color: #10b981; }
        .loss { color: #ef4444; }
        
        /* Mobile responsive styles */
        @media (max-width: 768px) {
            .orderbook-row { font-size: 0.6rem; }
            th, td { padding: 1px 2px; }
        }
    </style>
</head>
<body class="bg-gray-900 text-white">
    <div class="container mx-auto p-2 sm:p-4">
        <!-- Header -->
        <div class="bg-gray-800 border border-gray-700 rounded-lg p-2 sm:p-4 mb-4">
            <h1 class="text-xl sm:text-2xl font-bold text-center mb-2 sm:mb-4">🚀 DUAL EXCHANGE ORDERBOOK MONITOR</h1>
            
            <!-- Control Buttons -->
            <div class="flex justify-center gap-2 sm:gap-4 mb-2 sm:mb-4">
                <button id="startBtn" class="bg-green-600 hover:bg-green-700 px-3 sm:px-6 py-1 sm:py-2 rounded font-bold text-xs sm:text-base">
                    ▶ START WS
                </button>
                <button id="stopBtn" class="bg-red-600 hover:bg-red-700 px-3 sm:px-6 py-1 sm:py-2 rounded font-bold text-xs sm:text-base">
                    ⏹ STOP WS
                </button>
            </div>
            
            <!-- Connection Status -->
            <div class="flex justify-center gap-4 sm:gap-8 mb-2 sm:mb-4 text-xs sm:text-sm">
                <div class="flex items-center gap-2">
                    <span class="status-indicator" id="mexcStatus"></span>
                    <span>MEXC: <span id="mexcStatusText">Disconnected</span></span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="status-indicator" id="gateioStatus"></span>
                    <span>Gate.io: <span id="gateioStatusText">Disconnected</span></span>
                </div>
            </div>
            
            <!-- Symbol Manager -->
            <div class="bg-gray-700 border border-gray-600 rounded p-2 sm:p-4 mb-2 sm:mb-4">
                <h3 class="font-bold mb-2 text-sm sm:text-base">📋 SYMBOL MANAGER</h3>
                <div class="flex flex-wrap gap-2 sm:gap-4 mb-2 sm:mb-3" id="symbolCheckboxes"></div>
                <div class="flex gap-2">
                    <input type="text" id="symbolInput" placeholder="Enter symbol (e.g., ADA)" 
                           class="bg-gray-800 border border-gray-600 rounded px-2 sm:px-3 py-1 flex-1 text-xs sm:text-sm">
                    <button id="addSymbolBtn" class="bg-blue-600 hover:bg-blue-700 px-2 sm:px-4 py-1 rounded text-xs sm:text-sm">
                        ➕ Add
                    </button>
                    <button id="removeSymbolBtn" class="bg-red-600 hover:bg-red-700 px-2 sm:px-4 py-1 rounded text-xs sm:text-sm">
                        ➖ Remove
                    </button>
                </div>
            </div>
            
            <!-- Active Symbol Display -->
            <div class="flex justify-center items-center gap-2 sm:gap-4 mb-2 sm:mb-4">
                <button id="prevSymbolBtn" class="bg-gray-700 hover:bg-gray-600 px-2 sm:px-4 py-1 sm:py-2 rounded text-xs sm:text-sm">
                    ◀ Prev
                </button>
                <div class="text-lg sm:text-xl font-bold">
                    Active: <span id="activeSymbol" class="text-yellow-400">NONE</span>
                </div>
                <button id="nextSymbolBtn" class="bg-gray-700 hover:bg-gray-600 px-2 sm:px-4 py-1 sm:py-2 rounded text-xs sm:text-sm">
                    Next ▶
                </button>
            </div>
            
            <!-- Stats -->
            <div class="flex justify-center gap-4 sm:gap-8 text-xs sm:text-sm">
                <span>MEXC Msgs: <span id="mexcMsgs" class="text-green-400">0</span></span>
                <span>Gate.io Msgs: <span id="gateioMsgs" class="text-green-400">0</span></span>
                <span>Last Update: <span id="lastUpdate" class="text-blue-400">--:--:--</span></span>
            </div>
        </div>
        
        <!-- Orderbook Display - Stacked Layout -->
        <div class="space-y-4">
            <!-- MEXC Orderbook -->
            <div class="bg-gray-800 border border-gray-700 rounded-lg p-2 sm:p-4">
                <h2 class="text-lg sm:text-xl font-bold text-center mb-2 sm:mb-4 text-yellow-400">MEXC ORDERBOOK (20 DEPTH)</h2>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-2">
                    <!-- MEXC Bids -->
                    <div>
                        <h3 class="font-bold text-green-400 text-center mb-2 text-sm sm:text-base">BIDS (BUY)</h3>
                        <div class="overflow-x-auto">
                            <table class="w-full min-w-full">
                                <thead>
                                    <tr class="text-xs border-b border-gray-600">
                                        <th class="w-1/6">Price</th>
                                        <th class="w-1/6">Quantity</th>
                                        <th class="w-1/6">Cum.Qty</th>
                                        <th class="w-1/6">Total.USD</th>
                                        <th class="w-1/6">Cum.USD</th>
                                        <th class="w-1/6">Avg Price</th>
                                    </tr>
                                </thead>
                                <tbody id="mexcBidsTable" class="orderbook-row"></tbody>
                            </table>
                        </div>
                    </div>
                    <!-- MEXC Asks -->
                    <div>
                        <h3 class="font-bold text-red-400 text-center mb-2 text-sm sm:text-base">ASKS (SELL)</h3>
                        <div class="overflow-x-auto">
                            <table class="w-full min-w-full">
                                <thead>
                                    <tr class="text-xs border-b border-gray-600">
                                        <th class="w-1/6">Price</th>
                                        <th class="w-1/6">Quantity</th>
                                        <th class="w-1/6">Cum.Qty</th>
                                        <th class="w-1/6">Total.USD</th>
                                        <th class="w-1/6">Cum.USD</th>
                                        <th class="w-1/6">Avg Price</th>
                                    </tr>
                                </thead>
                                <tbody id="mexcAsksTable" class="orderbook-row"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Gate.io Orderbook -->
            <div class="bg-gray-800 border border-gray-700 rounded-lg p-2 sm:p-4">
                <h2 class="text-lg sm:text-xl font-bold text-center mb-2 sm:mb-4 text-yellow-400">GATE.IO ORDERBOOK (50 DEPTH)</h2>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-2">
                    <!-- Gate.io Bids -->
                    <div>
                        <h3 class="font-bold text-green-400 text-center mb-2 text-sm sm:text-base">BIDS (BUY)</h3>
                        <div class="overflow-x-auto">
                            <table class="w-full min-w-full">
                                <thead>
                                    <tr class="text-xs border-b border-gray-600">
                                        <th class="w-1/6">Price</th>
                                        <th class="w-1/6">Quantity</th>
                                        <th class="w-1/6">Cum.Qty</th>
                                        <th class="w-1/6">Total.USD</th>
                                        <th class="w-1/6">Cum.USD</th>
                                        <th class="w-1/6">Avg Price</th>
                                    </tr>
                                </thead>
                                <tbody id="gateioBidsTable" class="orderbook-row"></tbody>
                            </table>
                        </div>
                    </div>
                    <!-- Gate.io Asks -->
                    <div>
                        <h3 class="font-bold text-red-400 text-center mb-2 text-sm sm:text-base">ASKS (SELL)</h3>
                        <div class="overflow-x-auto">
                            <table class="w-full min-w-full">
                                <thead>
                                    <tr class="text-xs border-b border-gray-600">
                                        <th class="w-1/6">Price</th>
                                        <th class="w-1/6">Quantity</th>
                                        <th class="w-1/6">Cum.Qty</th>
                                        <th class="w-1/6">Total.USD</th>
                                        <th class="w-1/6">Cum.USD</th>
                                        <th class="w-1/6">Avg Price</th>
                                    </tr>
                                </thead>
                                <tbody id="gateioAsksTable" class="orderbook-row"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Arbitrage Calculator -->
            <div class="bg-gray-800 border border-gray-700 rounded-lg p-2 sm:p-4">
                <h2 class="text-lg sm:text-xl font-bold text-center mb-2 sm:mb-4 text-yellow-400">💰 ARBITRAGE CALCULATOR</h2>
                <div class="overflow-x-auto">
                    <table class="w-full min-w-full">
                        <thead>
                            <tr class="text-xs border-b border-gray-600">
                                <th class="w-1/5">Amount (USD)</th>
                                <th class="w-1/5">Buy From</th>
                                <th class="w-1/5">Sell To</th>
                                <th class="w-1/5">Profit/Loss (USD)</th>
                                <th class="w-1/5">Profit/Loss (%)</th>
                            </tr>
                        </thead>
                        <tbody id="arbitrageTable" class="orderbook-row">
                            <tr>
                                <td class="text-center" colspan="5">Waiting for orderbook data...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        // WebSocket connection
        let ws = null;
        
        // State
        let symbols = ['DNXUSDT', 'ETHUSDT', 'SOLUSDT', 'BTCUSDT'];
        let enabledSymbols = new Set(symbols);
        let activeSymbolIndex = 0;
        let currentOrderbooks = {
            'MEXC': {},
            'GATEIO': {}
        };
        
        // Initialize
        function init() {
            renderSymbolCheckboxes();
            updateActiveSymbol();
            connectWebSocket();
            
            // Event listeners
            document.getElementById('startBtn').addEventListener('click', startWebSockets);
            document.getElementById('stopBtn').addEventListener('click', stopWebSockets);
            document.getElementById('addSymbolBtn').addEventListener('click', addSymbol);
            document.getElementById('removeSymbolBtn').addEventListener('click', removeSymbol);
            document.getElementById('prevSymbolBtn').addEventListener('click', prevSymbol);
            document.getElementById('nextSymbolBtn').addEventListener('click', nextSymbol);
        }
        
        // Render symbol checkboxes
        function renderSymbolCheckboxes() {
            const container = document.getElementById('symbolCheckboxes');
            container.innerHTML = '';
            
            symbols.forEach(symbol => {
                const label = document.createElement('label');
                label.className = 'flex items-center gap-2 cursor-pointer';
                
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = enabledSymbols.has(symbol);
                checkbox.className = 'w-4 h-4';
                checkbox.addEventListener('change', (e) => {
                    if (e.target.checked) {
                        enabledSymbols.add(symbol);
                    } else {
                        enabledSymbols.delete(symbol);
                    }
                });
                
                const span = document.createElement('span');
                span.textContent = symbol;
                
                label.appendChild(checkbox);
                label.appendChild(span);
                container.appendChild(label);
            });
        }
        
        // Add symbol
        function addSymbol() {
            const input = document.getElementById('symbolInput');
            const symbol = input.value.trim().toUpperCase();
            
            if (!symbol) return;
            
            const normalizedSymbol = normalizeSymbol(symbol);
            
            if (!symbols.includes(normalizedSymbol)) {
                symbols.push(normalizedSymbol);
                enabledSymbols.add(normalizedSymbol);
                renderSymbolCheckboxes();
                input.value = '';
            }
        }
        
        // Remove symbol
        function removeSymbol() {
            const selectedSymbols = Array.from(document.querySelectorAll('#symbolCheckboxes input:checked'))
                .map(cb => cb.nextElementSibling.textContent);
            
            selectedSymbols.forEach(symbol => {
                const index = symbols.indexOf(symbol);
                if (index > -1) {
                    symbols.splice(index, 1);
                    enabledSymbols.delete(symbol);
                }
            });
            
            if (activeSymbolIndex >= symbols.length) {
                activeSymbolIndex = Math.max(0, symbols.length - 1);
            }
            
            renderSymbolCheckboxes();
            updateActiveSymbol();
        }
        
        // Normalize symbol
        function normalizeSymbol(symbol) {
            symbol = symbol.replace('_', '');
            const quotes = ['USDT', 'USDC', 'BTC', 'ETH', 'BNB'];
            
            for (const quote of quotes) {
                if (symbol.endsWith(quote)) {
                    return symbol;
                }
            }
            
            return symbol + 'USDT';
        }
        
        // Navigate symbols
        function prevSymbol() {
            if (symbols.length === 0) return;
            activeSymbolIndex = (activeSymbolIndex - 1 + symbols.length) % symbols.length;
            updateActiveSymbol();
        }
        
        function nextSymbol() {
            if (symbols.length === 0) return;
            activeSymbolIndex = (activeSymbolIndex + 1) % symbols.length;
            updateActiveSymbol();
        }
        
        // Update active symbol display
        function updateActiveSymbol() {
            const activeSymbol = symbols[activeSymbolIndex] || 'NONE';
            document.getElementById('activeSymbol').textContent = activeSymbol;
            
            // Update orderbook tables for active symbol
            updateOrderbookDisplay('MEXC', activeSymbol);
            updateOrderbookDisplay('GATEIO', activeSymbol);
            
            // Update arbitrage calculator
            updateArbitrageCalculator(activeSymbol);
        }
        
        // Connect WebSocket
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/orderbook`);
            
            ws.onopen = () => {
                console.log('✅ WebSocket connected');
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'orderbook_update') {
                    handleOrderbookUpdate(data);
                } else if (data.type === 'stats') {
                    updateStats(data);
                }
            };
            
            ws.onclose = () => {
                console.log('🔌 WebSocket disconnected, reconnecting...');
                setTimeout(connectWebSocket, 3000);
            };
            
            ws.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
            };
        }
        
        // Handle orderbook update
        function handleOrderbookUpdate(data) {
            const { exchange, symbol, data: orderbookData } = data;
            
            if (!currentOrderbooks[exchange]) {
                currentOrderbooks[exchange] = {};
            }
            
            currentOrderbooks[exchange][symbol] = orderbookData;
            
            // Update display if this is the active symbol
            const activeSymbol = symbols[activeSymbolIndex];
            if (symbol === activeSymbol || 
                (exchange === 'GATEIO' && symbol === convertToGateioFormat(activeSymbol))) {
                updateOrderbookDisplay(exchange, symbol);
                updateArbitrageCalculator(activeSymbol);
            }
            
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
        }
        
        // Update stats
        function updateStats(data) {
            const { stats } = data;
            
            // MEXC status
            if (stats.MEXC) {
                const mexcStatus = document.getElementById('mexcStatus');
                const mexcStatusText = document.getElementById('mexcStatusText');
                
                if (stats.MEXC.connected) {
                    mexcStatus.classList.add('status-connected');
                    mexcStatus.classList.remove('status-disconnected');
                    mexcStatusText.textContent = 'Connected';
                } else {
                    mexcStatus.classList.add('status-disconnected');
                    mexcStatus.classList.remove('status-connected');
                    mexcStatusText.textContent = 'Disconnected';
                }
                
                document.getElementById('mexcMsgs').textContent = stats.MEXC.messages;
            }
            
            // Gate.io status
            if (stats.GATEIO) {
                const gateioStatus = document.getElementById('gateioStatus');
                const gateioStatusText = document.getElementById('gateioStatusText');
                
                if (stats.GATEIO.connected) {
                    gateioStatus.classList.add('status-connected');
                    gateioStatus.classList.remove('status-disconnected');
                    gateioStatusText.textContent = 'Connected';
                } else {
                    gateioStatus.classList.add('status-disconnected');
                    gateioStatus.classList.remove('status-connected');
                    gateioStatusText.textContent = 'Disconnected';
                }
                
                document.getElementById('gateioMsgs').textContent = stats.GATEIO.messages;
            }
        }
        
        // Convert to Gate.io format
        function convertToGateioFormat(symbol) {
            const quotes = ['USDT', 'USDC', 'BTC', 'ETH', 'BNB'];
            
            for (const quote of quotes) {
                if (symbol.endsWith(quote)) {
                    const base = symbol.substring(0, symbol.length - quote.length);
                    return `${base}_${quote}`;
                }
            }
            
            return symbol;
        }
        
        // Update orderbook display
        function updateOrderbookDisplay(exchange, symbol) {
            const orderbook = currentOrderbooks[exchange]?.[symbol];
            
            if (!orderbook) {
                clearOrderbookDisplay(exchange);
                return;
            }
            
            const bids = orderbook.bids || [];
            const asks = orderbook.asks || [];
            
            const maxRows = exchange === 'MEXC' ? 20 : 50;
            
            // Update bids
            const bidsTableId = exchange === 'MEXC' ? 'mexcBidsTable' : 'gateioBidsTable';
            const bidsTable = document.getElementById(bidsTableId);
            bidsTable.innerHTML = '';
            
            let cumulativeQty = 0;
            let cumulativeUsd = 0;
            
            for (let i = 0; i < maxRows; i++) {
                const row = document.createElement('tr');
                
                if (i < bids.length) {
                    const [price, quantity, cumQty, totalUsd, cumUsd, avgPrice] = bids[i];
                    const priceFloat = parseFloat(price);
                    const quantityFloat = parseFloat(quantity);
                    
                    // Calculate total for this level
                    const total = priceFloat * quantityFloat;
                    
                    // Update cumulative values
                    cumulativeQty += quantityFloat;
                    cumulativeUsd += total;
                    
                    row.innerHTML = `
                        <td class="bid-price">${parseFloat(price).toFixed(5)}</td>
                        <td class="quantity">${parseFloat(quantity).toFixed(6)}</td>
                        <td class="cum-qty">${parseFloat(cumQty).toFixed(6)}</td>
                        <td class="total-usd">${parseFloat(totalUsd).toFixed(2)}</td>
                        <td class="cum-usd">${parseFloat(cumUsd).toFixed(2)}</td>
                        <td class="avg-price">${parseFloat(avgPrice).toFixed(5)}</td>
                    `;
                } else {
                    row.innerHTML = `
                        <td class="text-gray-600">--</td>
                        <td class="text-gray-600">--</td>
                        <td class="text-gray-600">--</td>
                        <td class="text-gray-600">--</td>
                        <td class="text-gray-600">--</td>
                        <td class="text-gray-600">--</td>
                    `;
                }
                
                bidsTable.appendChild(row);
            }
            
            // Update asks
            const asksTableId = exchange === 'MEXC' ? 'mexcAsksTable' : 'gateioAsksTable';
            const asksTable = document.getElementById(asksTableId);
            asksTable.innerHTML = '';
            
            cumulativeQty = 0;
            cumulativeUsd = 0;
            
            for (let i = 0; i < maxRows; i++) {
                const row = document.createElement('tr');
                
                if (i < asks.length) {
                    const [price, quantity, cumQty, totalUsd, cumUsd, avgPrice] = asks[i];
                    const priceFloat = parseFloat(price);
                    const quantityFloat = parseFloat(quantity);
                    
                    // Calculate total for this level
                    const total = priceFloat * quantityFloat;
                    
                    // Update cumulative values
                    cumulativeQty += quantityFloat;
                    cumulativeUsd += total;
                    
                    row.innerHTML = `
                        <td class="ask-price">${parseFloat(price).toFixed(5)}</td>
                        <td class="quantity">${parseFloat(quantity).toFixed(6)}</td>
                        <td class="cum-qty">${parseFloat(cumQty).toFixed(6)}</td>
                        <td class="total-usd">${parseFloat(totalUsd).toFixed(2)}</td>
                        <td class="cum-usd">${parseFloat(cumUsd).toFixed(2)}</td>
                        <td class="avg-price">${parseFloat(avgPrice).toFixed(5)}</td>
                    `;
                } else {
                    row.innerHTML = `
                        <td class="text-gray-600">--</td>
                        <td class="text-gray-600">--</td>
                        <td class="text-gray-600">--</td>
                        <td class="text-gray-600">--</td>
                        <td class="text-gray-600">--</td>
                        <td class="text-gray-600">--</td>
                    `;
                }
                
                asksTable.appendChild(row);
            }
        }
        
        // Update arbitrage calculator
        function updateArbitrageCalculator(symbol) {
            const mexcOrderbook = currentOrderbooks['MEXC']?.[symbol];
            const gateioOrderbook = currentOrderbooks['GATEIO']?.[convertToGateioFormat(symbol)];
            
            const arbitrageTable = document.getElementById('arbitrageTable');
            arbitrageTable.innerHTML = '';
            
            if (!mexcOrderbook || !gateioOrderbook) {
                arbitrageTable.innerHTML = '<tr><td class="text-center" colspan="5">Waiting for orderbook data...</td></tr>';
                return;
            }
            
            const amounts = [50, 100, 150, 200];
            
            amounts.forEach(amount => {
                // Calculate arbitrage opportunities
                const mexcBestBid = mexcOrderbook.bids[0] ? parseFloat(mexcOrderbook.bids[0][0]) : 0;
                const mexcBestAsk = mexcOrderbook.asks[0] ? parseFloat(mexcOrderbook.asks[0][0]) : 0;
                const gateioBestBid = gateioOrderbook.bids[0] ? parseFloat(gateioOrderbook.bids[0][0]) : 0;
                const gateioBestAsk = gateioOrderbook.asks[0] ? parseFloat(gateioOrderbook.asks[0][0]) : 0;
                
                // Scenario 1: Buy from MEXC, Sell to Gate.io
                const coinsFromMexc = amount / mexcBestAsk;
                const usdFromGateio = coinsFromMexc * gateioBestBid;
                const profit1 = usdFromGateio - amount;
                const profitPercent1 = (profit1 / amount) * 100;
                
                // Scenario 2: Buy from Gate.io, Sell to MEXC
                const coinsFromGateio = amount / gateioBestAsk;
                const usdFromMexc = coinsFromGateio * mexcBestBid;
                const profit2 = usdFromMexc - amount;
                const profitPercent2 = (profit2 / amount) * 100;
                
                // Determine best opportunity
                let bestBuyFrom, bestSellTo, bestProfit, bestProfitPercent;
                
                if (profit1 > profit2) {
                    bestBuyFrom = 'MEXC';
                    bestSellTo = 'Gate.io';
                    bestProfit = profit1;
                    bestProfitPercent = profitPercent1;
                } else {
                    bestBuyFrom = 'Gate.io';
                    bestSellTo = 'MEXC';
                    bestProfit = profit2;
                    bestProfitPercent = profitPercent2;
                }
                
                const profitClass = bestProfit > 0 ? 'profit' : 'loss';
                const profitSign = bestProfit > 0 ? '+' : '';
                
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td class="text-center">$${amount}</td>
                    <td class="text-center">${bestBuyFrom}</td>
                    <td class="text-center">${bestSellTo}</td>
                    <td class="${profitClass} text-center">${profitSign}$${bestProfit.toFixed(2)}</td>
                    <td class="${profitClass} text-center">${profitSign}${bestProfitPercent.toFixed(2)}%</td>
                `;
                arbitrageTable.appendChild(row);
            });
        }
        
        // Clear orderbook display
        function clearOrderbookDisplay(exchange) {
            const maxRows = exchange === 'MEXC' ? 20 : 50;
            
            const bidsTableId = exchange === 'MEXC' ? 'mexcBidsTable' : 'gateioBidsTable';
            const asksTableId = exchange === 'MEXC' ? 'mexcAsksTable' : 'gateioAsksTable';
            
            const bidsTable = document.getElementById(bidsTableId);
            const asksTable = document.getElementById(asksTableId);
            
            bidsTable.innerHTML = '';
            asksTable.innerHTML = '';
            
            for (let i = 0; i < maxRows; i++) {
                const bidRow = document.createElement('tr');
                bidRow.innerHTML = `
                    <td class="text-gray-600">--</td>
                    <td class="text-gray-600">--</td>
                    <td class="text-gray-600">--</td>
                    <td class="text-gray-600">--</td>
                    <td class="text-gray-600">--</td>
                    <td class="text-gray-600">--</td>
                `;
                bidsTable.appendChild(bidRow);
                
                const askRow = document.createElement('tr');
                askRow.innerHTML = `
                    <td class="text-gray-600">--</td>
                    <td class="text-gray-600">--</td>
                    <td class="text-gray-600">--</td>
                    <td class="text-gray-600">--</td>
                    <td class="text-gray-600">--</td>
                    <td class="text-gray-600">--</td>
                `;
                asksTable.appendChild(askRow);
            }
        }
        
        // Start WebSockets
        async function startWebSockets() {
            const symbolsToStart = Array.from(enabledSymbols);
            
            if (symbolsToStart.length === 0) {
                alert('Please enable at least one symbol!');
                return;
            }
            
            try {
                const response = await fetch('/api/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbols: symbolsToStart })
                });
                
                const result = await response.json();
                console.log('✅ WebSockets started:', result);
            } catch (error) {
                console.error('❌ Failed to start WebSockets:', error);
            }
        }
        
        // Stop WebSockets
        async function stopWebSockets() {
            try {
                const response = await fetch('/api/stop', {
                    method: 'POST'
                });
                
                const result = await response.json();
                console.log('🛑 WebSockets stopped:', result);
            } catch (error) {
                console.error('❌ Failed to stop WebSockets:', error);
            }
        }
        
        // Initialize on page load
        window.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the embedded HTML dashboard"""
    return HTML_DASHBOARD

@app.websocket("/ws/orderbook")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time orderbook updates"""
    await websocket.accept()
    orderbook_manager.websocket_clients.add(websocket)
    
    logging.info(f"✅ WebSocket client connected. Total clients: {len(orderbook_manager.websocket_clients)}")
    
    try:
        # Send initial stats
        await websocket.send_text(orjson.dumps({
            'type': 'stats',
            'stats': orderbook_manager.stats
        }).decode('utf-8'))
        
        # Keep connection alive and send periodic stats
        while True:
            await asyncio.sleep(1)
            await websocket.send_text(orjson.dumps({
                'type': 'stats',
                'stats': orderbook_manager.stats
            }).decode('utf-8'))
            
    except WebSocketDisconnect:
        orderbook_manager.websocket_clients.discard(websocket)
        logging.info(f"🔌 WebSocket client disconnected. Total clients: {len(orderbook_manager.websocket_clients)}")
    except Exception as e:
        logging.error(f"❌ WebSocket error: {e}")
        orderbook_manager.websocket_clients.discard(websocket)

@app.post("/api/start")
async def start_websockets(request: Dict):
    """Start MEXC and Gate.io WebSocket connections"""
    global mexc_connector, gateio_connector
    
    symbols = request.get('symbols', [])
    
    if not symbols:
        return {'status': 'error', 'message': 'No symbols provided'}
    
    logging.info(f"🚀 Starting WebSockets for symbols: {symbols}")
    
    # Stop existing connections if any
    if mexc_connector:
        mexc_connector.stop()
    if gateio_connector:
        gateio_connector.stop()
    
    # Wait a bit for clean shutdown
    await asyncio.sleep(1)
    
    # Start new connections
    mexc_connector = MEXCWebSocketConnector(symbols, orderbook_manager)
    gateio_connector = GateIOWebSocketConnector(symbols, orderbook_manager)
    
    mexc_connector.start()
    gateio_connector.start()
    
    return {
        'status': 'success',
        'message': f'Started monitoring {len(symbols)} symbols',
        'symbols': symbols
    }

@app.post("/api/stop")
async def stop_websockets():
    """Stop MEXC and Gate.io WebSocket connections"""
    global mexc_connector, gateio_connector
    
    logging.info("🛑 Stopping WebSockets...")
    
    if mexc_connector:
        mexc_connector.stop()
    if gateio_connector:
        gateio_connector.stop()
    
    return {
        'status': 'success',
        'message': 'WebSockets stopped'
    }

@app.get("/api/orderbook/{exchange}/{symbol}")
async def get_orderbook(exchange: str, symbol: str):
    """Get orderbook data for a specific exchange and symbol"""
    orderbook = orderbook_manager.get_orderbook(exchange.upper(), symbol.upper())
    
    if not orderbook:
        return {'error': 'Orderbook not found'}
    
    return {
        'exchange': exchange,
        'symbol': symbol,
        'orderbook': orderbook
    }

@app.get("/api/status")
async def get_status():
    """Get connection status and stats"""
    return {
        'status': 'ok',
        'stats': orderbook_manager.stats,
        'orderbooks': list(orderbook_manager.orderbooks.keys())
    }

if __name__ == "__main__":
    logging.info("="*80)
    logging.info("🚀 DUAL EXCHANGE ORDERBOOK MONITOR STARTING")
    logging.info("="*80)
    logging.info(f"📡 Server will run on http://localhost:8007")
    logging.info(f"📊 MEXC: 20 depth | Gate.io: 50 depth")
    logging.info(f"💎 Default symbols: DNX, ETH, SOL, BTC")
    logging.info("="*80)
    
    if not PROTOBUF_MODULES:
        logging.error("❌ Cannot start: Protobuf modules not loaded!")
        logging.error("❌ Make sure 'generated_proto/' folder exists with MEXC protobuf files!")
        sys.exit(1)
    
    print("\n" + "="*80)
    print("🚀 DUAL EXCHANGE ORDERBOOK MONITOR")
    print("="*80)
    print("✅ MEXC: 20 depth (Protobuf)")
    print("✅ Gate.io: 50 depth (JSON)")
    print("💎 Default symbols: DNX, ETH, SOL, BTC")
    print(f"📡 Dashboard: http://localhost:8007")
    print("="*80 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8007, log_level="info")