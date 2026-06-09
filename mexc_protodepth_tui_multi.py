#!/usr/bin/env python3

# MEXC Multi-Symbol Orderbook Monitor - ALL FEATURES PRESERVED
# 20-DEPTH REAL-TIME ORDERBOOK WITH LISTEN KEY + API KEYS
# REFACTORED BUT COMPLETE

import os
import time
import json
import threading
import websocket
import sys
import warnings
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from queue import Queue
from typing import Optional, Dict, Any, List
from logging.handlers import RotatingFileHandler
import logging

warnings.filterwarnings("ignore")
os.environ['PYTHONWARNINGS'] = 'ignore'

import orjson
from textual.app import App, ComposeResult
from textual.widget import Widget
from textual.widgets import Static, DataTable, RichLog
from textual.containers import Container, Vertical, Horizontal
from textual.css.query import NoMatches
from rich.text import Text

def set_terminal_title(title: str) -> None:
    try:
        if os.name == 'nt':
            os.system(f'title {title}')
        else:
            print(f'\033]0;{title}\007', end='', flush=True)
    except:
        pass

set_terminal_title("MEXC Multi-Symbol Orderbook Monitor")

# Thread-safe queues
orderbook_queue = Queue()
connection_queue = Queue()
debug_queue = Queue()

# Global state
current_orderbooks = {}  # {symbol: {'bids': [], 'asks': []}}
should_exit = False
selected_symbols = []
active_symbol_index = 0

# Connection state
connection_state = {
    'status': 'Disconnected',
    'connected_at': None,
    'last_ping': None,
    'reconnect_count': 0,
    'last_error': None,
    'messages_received': 0,
    'last_message_time': None,
    'binary_messages': 0,
    'json_messages': 0,
    'symbols': [],
    'active_symbol': None,
    'protobuf_mode': 'Unknown',
    'listen_key': None,
    'listen_key_full': None,
    'last_key_extend': None,
    'listen_key_created_at': None,
    'listen_key_expires_at': None
}

from mexc_proto_loader import load_orderbook_modules_safe

def load_generated_proto_protobuf():
    print("📦 Loading protobuf modules from generated_proto/ ...")
    modules, ok = load_orderbook_modules_safe()
    if ok:
        print("✅ Protobuf modules loaded!")
    else:
        print("❌ generated_proto/ not found or import failed — run mexc_proto_auto_setup.py")
    return modules, ok

def normalize_symbol(user_input: str) -> str:
    symbol = user_input.strip().upper()
    quote_currencies = ['USDT', 'USDC', 'BTC', 'ETH', 'BNB']
    has_quote = any(symbol.endswith(quote) for quote in quote_currencies)
    if not has_quote:
        symbol = symbol + 'USDT'
    
    logging.info(f"🔄 Normalized '{user_input}' -> '{symbol}'")
    return symbol

def get_symbol_selection() -> List[str]:
    print("\n" + "="*50)
    print("MEXC Multi-Symbol Orderbook Monitor")
    print("="*50)
    print("Enter trading symbols (comma-separated):")
    print("Examples: btc,eth,bnb OR BTCUSDT,ETHUSDT")
    print("Or type 'top10' for popular coins")
    print("\n" + "="*50)
    
    while True:
        try:
            user_input = input("Enter symbols: ").strip()
            
            if not user_input:
                print("Please enter symbols.")
                continue
            
            if user_input.lower() == 'top10':
                logging.info("📋 User selected TOP10 preset")
                symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT']
                logging.info(f"📋 TOP10 symbols: {', '.join(symbols)}")
            else:
                symbols = [s.strip() for s in user_input.split(',')]
                logging.info(f"📋 User entered: {symbols}")
            
            normalized = [normalize_symbol(s) for s in symbols if s.strip()]
            
            if not normalized:
                print("No valid symbols.")
                continue
            
            logging.info(f"✅ Final normalized symbols: {', '.join(normalized)}")
            print(f"Selected {len(normalized)} symbols: {', '.join(normalized)}")
            return normalized
                
        except KeyboardInterrupt:
            print("\nExiting...")
            exit(1)
        except Exception as e:
            logging.error(f"Symbol selection error: {e}")
            print(f"Error: {e}")

def setup_logging():
    try:
        os.makedirs('orderbook_logs', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        log_format = '%(asctime)s.%(msecs)03d - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        root_logger = logging.getLogger()
        root_logger.handlers = []
        
        # File handler with detailed logging
        file_handler = RotatingFileHandler(
            filename=f'orderbook_logs/multi_orderbook_{timestamp}.log',
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler for immediate feedback
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        console_handler.setLevel(logging.INFO)
        
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        logging.info("="*80)
        logging.info("MULTI-SYMBOL ORDERBOOK MONITOR LOGGING INITIALIZED")
        logging.info(f"Log file: orderbook_logs/multi_orderbook_{timestamp}.log")
        logging.info("="*80)
        
        print(f"\n✅ LOGGING INITIALIZED: orderbook_logs/multi_orderbook_{timestamp}.log\n")
        
    except Exception as e:
        print(f"❌ FAILED TO SETUP LOGGING: {str(e)}")
        raise

def format_price(price: str, precision: int = 5) -> str:
    try:
        price_decimal = Decimal(price)
        scaled = price_decimal.quantize(Decimal('0.' + '0' * precision), rounding=ROUND_HALF_UP)
        return f"{scaled:f}"
    except (InvalidOperation, ValueError):
        return price

def format_quantity(qty: str, precision: int = 6) -> str:
    try:
        qty_decimal = Decimal(qty)
        scaled = qty_decimal.quantize(Decimal('0.' + '0' * precision), rounding=ROUND_HALF_UP)
        return f"{scaled:f}"
    except (InvalidOperation, ValueError):
        return qty

def update_connection_state(**kwargs):
    global connection_state
    connection_state.update(kwargs)
    connection_queue.put(connection_state.copy())

def debug_log(message: str, msg_type: str = "info"):
    type_mapping = {'success': 'info', 'warning': 'debug', 'error': 'error', 'info': 'info', 'debug': 'debug', 'websocket': 'info', 'balance': 'info'}
    fixed_type = type_mapping.get(msg_type, 'info')
    debug_queue.put({'message': message, 'type': fixed_type})

class DirectGeneratedProtoOrderbookParser:
    def __init__(self, protobuf_modules):
        self.protobuf_modules = protobuf_modules
        self.parsing_mode = 'generated_proto_direct'
        
        if protobuf_modules:
            logging.info("✅ Direct generated_proto orderbook parser initialized")
            debug_log("✅ Parser initialized", 'info')
            update_connection_state(protobuf_mode='Generated Proto Direct')
        else:
            logging.error("❌ No protobuf modules available")
            debug_log("❌ No protobuf modules", 'error')
            update_connection_state(protobuf_mode='FAILED')
    
    def parse_orderbook_update(self, binary_data):
        if not self.protobuf_modules:
            return None
        
        try:
            wrapper_module = self.protobuf_modules['wrapper']
            wrapper = wrapper_module.PushDataV3ApiWrapper()
            wrapper.ParseFromString(binary_data)
            
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
                
                symbol = wrapper.symbol if hasattr(wrapper, 'symbol') else 'UNKNOWN'
                
                return {
                    'symbol': symbol,
                    'bids': bids,
                    'asks': asks,
                    'type': 'limit_depth',
                    'timestamp': wrapper.sendTime if hasattr(wrapper, 'sendTime') else int(time.time() * 1000)
                }
            
            elif hasattr(wrapper, 'publicIncreaseDepths') and wrapper.HasField('publicIncreaseDepths'):
                depth_data = wrapper.publicIncreaseDepths
                
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
                
                symbol = wrapper.symbol if hasattr(wrapper, 'symbol') else 'UNKNOWN'
                
                return {
                    'symbol': symbol,
                    'bids': bids,
                    'asks': asks,
                    'type': 'aggre_depth',
                    'timestamp': wrapper.sendTime if hasattr(wrapper, 'sendTime') else int(time.time() * 1000)
                }
            
            return None
            
        except Exception as e:
            logging.error(f"❌ Protobuf parsing error: {e}")
            return None

class MEXCMultiSymbolOrderbookMonitor:
    def __init__(self, symbols, protobuf_modules):
        self.symbols = [s.upper() for s in symbols]
        self.base_url = "https://api.mexc.com"
        self.ws_url = "wss://wbs-api.mexc.com/ws"
        self.listen_key = None
        self.ws = None
        self.running = False
        
        self.last_ping_time = 0
        self.last_pong_time = 0
        self.last_key_extend_time = 0
        self.ping_interval = 30
        self.key_extend_interval = 1800
        self.reconnect_count = 0
        self.sent_pings = set()
        
        self.keepalive_thread = None
        self.keepalive_running = False
        
        self.protobuf_parser = DirectGeneratedProtoOrderbookParser(protobuf_modules)
        
        self.current_orderbooks = {}
        for symbol in self.symbols:
            self.current_orderbooks[symbol] = {'bids': [], 'asks': []}
        
        self.api_key = None
        self.api_secret = None
        self.load_api_keys()
        
    def load_api_keys(self):
        try:
            with open('config/mexc_keys.json', 'r') as f:
                keys = json.load(f)
            
            self.api_key = keys.get('api_key')
            self.api_secret = keys.get('api_secret')
            
            if not self.api_key or not self.api_secret:
                self.log_with_timestamp("⚠️ No API keys - public mode only")
                return False
            
            self.log_with_timestamp("✅ API keys loaded")
            return True
            
        except FileNotFoundError:
            self.log_with_timestamp("⚠️ config/mexc_keys.json not found - public mode")
            return False
        except Exception as e:
            self.log_with_timestamp(f"⚠️ Key load error: {e}")
            return False
    
    def generate_signature(self, params_string):
        if not self.api_secret:
            return ""
        
        import hmac
        import hashlib
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            params_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def get_timestamp(self):
        return int(time.time() * 1000)
    
    def create_listen_key(self):
        if not self.api_key:
            return False
            
        self.log_with_timestamp("🔑 Creating listen key...")
        
        try:
            import requests
            
            timestamp = self.get_timestamp()
            params = f"timestamp={timestamp}"
            signature = self.generate_signature(params)
            
            url = f"{self.base_url}/api/v3/userDataStream"
            headers = {'X-MEXC-APIKEY': self.api_key}
            data = f"{params}&signature={signature}"
            
            response = requests.post(url, headers=headers, data=data)
            
            if response.status_code == 200:
                result = response.json()
                if 'listenKey' in result:
                    self.listen_key = result['listenKey']
                    self.log_with_timestamp(f"✅ Listen key created")
                    self.last_key_extend_time = time.time()
                    
                    created_at = datetime.now()
                    expire_time = created_at.replace(hour=23, minute=59, second=59, microsecond=0)
                    
                    update_connection_state(
                        listen_key=self.listen_key[:20] + "...",
                        listen_key_full=self.listen_key,
                        listen_key_created_at=created_at,
                        listen_key_expires_at=expire_time
                    )
                    return True
            
            return False
        except Exception as e:
            self.log_with_timestamp(f"❌ Create key error: {e}")
            return False
    
    def extend_listen_key(self):
        if not self.listen_key or not self.api_key:
            return False
            
        try:
            import requests
            
            timestamp = self.get_timestamp()
            params = f"listenKey={self.listen_key}&timestamp={timestamp}"
            signature = self.generate_signature(params)
            
            url = f"{self.base_url}/api/v3/userDataStream"
            headers = {'X-MEXC-APIKEY': self.api_key}
            data = f"{params}&signature={signature}"
            
            response = requests.put(url, headers=headers, data=data)
            
            if response.status_code == 200:
                self.log_with_timestamp("✅ Listen key extended")
                self.last_key_extend_time = time.time()
                
                expire_time = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
                update_connection_state(
                    last_key_extend=datetime.now(),
                    listen_key_expires_at=expire_time
                )
                return True
            
            return False
        except Exception as e:
            self.log_with_timestamp(f"❌ Extend key error: {e}")
            return False
    
    def delete_listen_key(self):
        if not self.listen_key or not self.api_key:
            return True
            
        try:
            import requests
            
            timestamp = self.get_timestamp()
            params = f"listenKey={self.listen_key}&timestamp={timestamp}"
            signature = self.generate_signature(params)
            
            url = f"{self.base_url}/api/v3/userDataStream"
            headers = {'X-MEXC-APIKEY': self.api_key}
            data = f"{params}&signature={signature}"
            
            response = requests.delete(url, headers=headers, data=data)
            
            if response.status_code == 200:
                self.log_with_timestamp("✅ Listen key deleted")
                return True
            
            return False
        except Exception as e:
            self.log_with_timestamp(f"❌ Delete key error: {e}")
            return False
        
    def log_with_timestamp(self, message):
        logging.info(message)
        debug_log(message, 'info')
    
    def send_ping(self):
        if self.ws and self.running:
            try:
                ping_id = int(time.time())
                heartbeat = {"method": "PING", "id": ping_id}
                
                self.sent_pings.add(ping_id)
                self.ws.send(json.dumps(heartbeat))
                self.last_ping_time = time.time()
                update_connection_state(last_ping=datetime.now())
                return True
            except Exception as e:
                return False
        return False
    
    def keepalive_worker(self):
        self.log_with_timestamp("🚀 Keepalive worker started")
        self.keepalive_running = True
        
        time.sleep(3)
        
        while self.keepalive_running and self.running:
            try:
                current_time = time.time()
                
                if (current_time - self.last_ping_time >= self.ping_interval):
                    self.send_ping()
                
                if current_time - self.last_key_extend_time >= self.key_extend_interval:
                    self.extend_listen_key()
                
                time.sleep(5)
                
            except Exception as e:
                time.sleep(5)
        
        self.log_with_timestamp("🛑 Keepalive worker stopped")
    
    def on_message(self, ws, message):
        global current_orderbooks
        
        msg_count = connection_state.get('messages_received', 0) + 1
        update_connection_state(
            messages_received=msg_count,
            last_message_time=datetime.now()
        )
        
        if isinstance(message, bytes):
            binary_count = connection_state.get('binary_messages', 0) + 1
            update_connection_state(binary_messages=binary_count)
            
            logging.debug(f"📦 Binary message #{binary_count}, size: {len(message)} bytes")
            
            parsed_data = self.protobuf_parser.parse_orderbook_update(message)
            
            if parsed_data:
                symbol = parsed_data.get('symbol')
                update_type = parsed_data.get('type')
                bids = parsed_data.get('bids', [])
                asks = parsed_data.get('asks', [])
                
                logging.info(f"✅ Parsed {symbol}: type={update_type}, bids={len(bids)}, asks={len(asks)}")
                
                if symbol in self.current_orderbooks:
                    if update_type == 'limit_depth':
                        self.current_orderbooks[symbol] = {
                            'bids': bids[:20],
                            'asks': asks[:20]
                        }
                        logging.info(f"📊 Full snapshot for {symbol}: {len(bids)} bids, {len(asks)} asks")
                    elif update_type == 'aggre_depth':
                        self.apply_orderbook_changes(symbol, bids, asks)
                        logging.info(f"🔄 Incremental update for {symbol}: {len(bids)} bid changes, {len(asks)} ask changes")
                    
                    # Sort orderbook
                    self.current_orderbooks[symbol]['bids'] = sorted(
                        self.current_orderbooks[symbol]['bids'], 
                        key=lambda x: float(x[0]), 
                        reverse=True
                    )[:20]
                    
                    self.current_orderbooks[symbol]['asks'] = sorted(
                        self.current_orderbooks[symbol]['asks'], 
                        key=lambda x: float(x[0])
                    )[:20]
                    
                    # Push to UI
                    current_orderbooks = self.current_orderbooks.copy()
                    orderbook_queue.put({'symbol': symbol, 'data': self.current_orderbooks[symbol]})
                else:
                    logging.warning(f"⚠️ Received data for unexpected symbol: {symbol} (not in monitored list)")
            else:
                logging.warning(f"⚠️ Failed to parse binary message #{binary_count}")
            
            return
        
        try:
            json_count = connection_state.get('json_messages', 0) + 1
            update_connection_state(json_messages=json_count)
            
            data = json.loads(message)
            logging.debug(f"📄 JSON message #{json_count}: {data}")
            
            if 'code' in data and 'msg' in data:
                if data.get('code') == 0:
                    if data.get('msg') == 'PONG':
                        pong_id = data.get('id')
                        if pong_id and pong_id in self.sent_pings:
                            self.sent_pings.remove(pong_id)
                            self.last_pong_time = time.time()
                            logging.info(f"🏓 PONG received (ID: {pong_id})")
                            debug_log(f"🏓 PONG", 'info')
                    else:
                        logging.info(f"✅ Subscription confirmed: {data.get('msg')}")
                        debug_log(f"✅ {data.get('msg')}", 'info')
                else:
                    logging.error(f"❌ Error response: {data}")
                    debug_log(f"❌ {data}", 'error')
                
        except Exception as e:
            logging.error(f"❌ Message handling error: {e}")
            pass
    
    def apply_orderbook_changes(self, symbol, bid_changes, ask_changes):
        try:
            for price, quantity in bid_changes:
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
            
            for price, quantity in ask_changes:
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
            
        except Exception as e:
            pass
    
    def on_error(self, ws, error):
        self.log_with_timestamp(f"❌ WebSocket error: {error}")
        update_connection_state(status='Error', last_error=str(error))
    
    def on_close(self, ws, close_status_code, close_msg):
        self.log_with_timestamp(f"🔌 WebSocket closed")
        update_connection_state(status='Disconnected')
    
    def on_open(self, ws):
        self.log_with_timestamp(f"✅ Connected! Monitoring {len(self.symbols)} symbols")
        self.log_with_timestamp(f"📋 SYMBOL LIST: {', '.join(self.symbols)}")
        self.reconnect_count = 0
        
        update_connection_state(
            status='Connected',
            connected_at=datetime.now(),
            reconnect_count=self.reconnect_count,
            symbols=self.symbols
        )
        
        self.last_pong_time = time.time()
        
        # Subscribe to all symbols
        params = [f"spot@public.limit.depth.v3.api.pb@{s}@20" for s in self.symbols]
        subscription = {"method": "SUBSCRIPTION", "params": params}
        
        self.log_with_timestamp(f"📡 Subscribing to {len(self.symbols)} symbols")
        self.log_with_timestamp(f"📤 SUBSCRIPTION PARAMS: {json.dumps(params, indent=2)}")
        ws.send(json.dumps(subscription))
    
    def connect_websocket(self):
        if self.listen_key:
            ws_url = f"{self.ws_url}?listenKey={self.listen_key}"
        else:
            ws_url = self.ws_url
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        self.ws.run_forever()
        return True
    
    def start_monitoring(self):
        self.log_with_timestamp(f"🚀 Starting multi-symbol monitor: {', '.join(self.symbols)}")
        
        self.running = True
        
        if self.api_key:
            self.create_listen_key()
        
        self.keepalive_thread = threading.Thread(target=self.keepalive_worker)
        self.keepalive_thread.daemon = True
        self.keepalive_thread.start()
        
        self.connect_websocket()
    
    def stop_monitoring(self):
        self.log_with_timestamp("🛑 Stopping monitor...")
        self.running = False
        self.keepalive_running = False
        
        if self.ws:
            self.ws.close()
        
        if self.keepalive_thread and self.keepalive_thread.is_alive():
            self.keepalive_thread.join(timeout=5)
        
        if self.listen_key:
            self.delete_listen_key()
        
        self.log_with_timestamp("✅ Monitor stopped")

class OrderbookConnectionPanel(Static):
    CSS = """
    OrderbookConnectionPanel {
        layout: vertical;
        height: 30%;
        background: #1a1a1a;
        border: solid #dd3a3a;
        margin-bottom: 1;
    }
    Container { height: 4; layout: vertical; }
    .connection-header { background: #1a1a1a; color: #dd3a3a; padding: 0; text-align: center; font-weight: bold; height: 1; }
    .connection-info { background: #1a1a1a; color: white; padding: 0; height: 3; }
    .debug-log { background: #0f0f0f; color: #00ff00; height: 8; border: solid #333333; margin: 0; padding: 0; overflow: auto; }
    """
    
    def compose(self):
        with Container():
            yield Static("Multi-Symbol Orderbook Monitor", classes="connection-header")
            yield Static("", id="connection-info", classes="connection-info")
        yield RichLog(id="debug-log", classes="debug-log", highlight=True, markup=True, auto_scroll=True, wrap=True)
    
    def update_connection_info(self, conn_state: dict):
        try:
            info_widget = self.query_one("#connection-info")
            
            status = conn_state.get('status', 'Unknown')
            messages = conn_state.get('messages_received', 0)
            binary_msgs = conn_state.get('binary_messages', 0)
            json_msgs = conn_state.get('json_messages', 0)
            symbols = conn_state.get('symbols', [])
            active = conn_state.get('active_symbol', 'None')
            
            status_color = "green" if status == "Connected" else "red"
            
            info_text = f"""[{status_color}]Status: {status}[/{status_color}] | Msgs: {messages} (B:{binary_msgs}/J:{json_msgs})
Symbols: {len(symbols)} | Active: {active}
Monitoring: {', '.join(symbols[:8])}{' +' + str(len(symbols)-8) + ' more' if len(symbols) > 8 else ''}"""
            
            info_widget.update(info_text)
            
        except:
            pass
    
    def add_debug_message(self, message: str, msg_type: str = "info"):
        try:
            debug_log_widget = self.query_one("#debug-log")
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            
            colors = {'info': 'cyan', 'error': 'red', 'warning': 'gray', 'success': 'cyan', 'debug': 'gray'}
            color = colors.get(msg_type, 'cyan')
            formatted_msg = f"[{color}][{timestamp}] {message}[/{color}]"
            
            debug_log_widget.write(formatted_msg)
            
        except:
            pass

class OrderbookDisplayPanel(Static):
    CSS = """
    OrderbookDisplayPanel {
        layout: horizontal;
        height: 70%;
        background: #1a1a1a;
        border: solid #3a96dd;
        width: 100%;
    }
    .orderbook-container { layout: horizontal; width: 100%; height: 100%; }
    .bids-panel { layout: vertical; width: 50%; background: #1a1a1a; border-right: solid #333333; }
    .asks-panel { layout: vertical; width: 50%; background: #1a1a1a; }
    .orderbook-header { background: #1a1a1a; color: #3a96dd; padding: 0; text-align: center; font-weight: bold; height: 1; }
    .bids-header { color: #00ff00; }
    .asks-header { color: #ff0000; }
    DataTable { width: 100%; height: 1fr; background: #1a1a1a; }
    """
    
    def compose(self):
        global selected_symbols, active_symbol_index
        active_symbol = selected_symbols[active_symbol_index] if selected_symbols else "NONE"
        
        with Horizontal(classes="orderbook-container"):
            with Vertical(classes="bids-panel"):
                yield Static(f"BIDS (BUY) - {active_symbol}", id="bids-header", classes="orderbook-header bids-header")
                yield DataTable(id="bids-table")
            
            with Vertical(classes="asks-panel"):
                yield Static(f"ASKS (SELL) - {active_symbol}", id="asks-header", classes="orderbook-header asks-header")
                yield DataTable(id="asks-table")
    
    def on_mount(self):
        bids_table = self.query_one("#bids-table")
        bids_table.cursor_type = "none"
        bids_table.add_columns("Price", "Quantity", "Total", "Cum.Qty", "Cum.USD", "Avg.Price")
        
        asks_table = self.query_one("#asks-table")
        asks_table.cursor_type = "none"
        asks_table.add_columns("Price", "Quantity", "Total", "Cum.Qty", "Cum.USD", "Avg.Price")

    def update_symbol_header(self, symbol):
        try:
            self.query_one("#bids-header").update(f"BIDS (BUY) - {symbol}")
            self.query_one("#asks-header").update(f"ASKS (SELL) - {symbol}")
        except:
            pass

    def update_orderbook(self, symbol, orderbook):
        global active_symbol_index, selected_symbols
        
        # Only update if this is the active symbol
        if selected_symbols and symbol != selected_symbols[active_symbol_index]:
            return
            
        if not orderbook:
            return
            
        try:
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            # Update bids table
            bids_table = self.query_one("#bids-table")
            bids_table.clear()
            
            cumulative_bid_qty = 0.0
            cumulative_bid_usd = 0.0
            
            for i, (price, quantity) in enumerate(bids[:20]):
                price_formatted = format_price(price, 5)
                quantity_formatted = format_quantity(quantity, 6)
                
                try:
                    price_float = float(price)
                    quantity_float = float(quantity)
                    total = price_float * quantity_float
                    total_formatted = format_quantity(str(total), 6)
                    
                    cumulative_bid_qty += quantity_float
                    cumulative_bid_usd += total
                    
                    cum_qty_formatted = format_quantity(str(cumulative_bid_qty), 6)
                    cum_usd_formatted = format_quantity(str(cumulative_bid_usd), 6)
                    
                    if cumulative_bid_qty > 0:
                        avg_price = cumulative_bid_usd / cumulative_bid_qty
                        avg_price_formatted = format_price(str(avg_price), 5)
                    else:
                        avg_price_formatted = "0.00000"
                    
                except (ValueError, TypeError):
                    total_formatted = "0.000000"
                    cum_qty_formatted = "0.000000"
                    cum_usd_formatted = "0.000000"
                    avg_price_formatted = "0.00000"
                
                bids_table.add_row(
                    Text(price_formatted, style="green"),
                    Text(quantity_formatted, style="white"),
                    Text(total_formatted, style="yellow"),
                    Text(cum_qty_formatted, style="cyan"),
                    Text(cum_usd_formatted, style="magenta"),
                    Text(avg_price_formatted, style="bright_blue")
                )
            
            for i in range(len(bids), 20):
                bids_table.add_row(
                    Text("--", style="dark_green"),
                    Text("--", style="dark_green"), 
                    Text("--", style="dark_green"),
                    Text("--", style="dark_green"),
                    Text("--", style="dark_green"),
                    Text("--", style="dark_green")
                )
            
            # Update asks table
            asks_table = self.query_one("#asks-table")
            asks_table.clear()
            
            cumulative_ask_qty = 0.0
            cumulative_ask_usd = 0.0
            
            for i, (price, quantity) in enumerate(asks[:20]):
                price_formatted = format_price(price, 5)
                quantity_formatted = format_quantity(quantity, 6)
                
                try:
                    price_float = float(price)
                    quantity_float = float(quantity)
                    total = price_float * quantity_float
                    total_formatted = format_quantity(str(total), 6)
                    
                    cumulative_ask_qty += quantity_float
                    cumulative_ask_usd += total
                    
                    cum_qty_formatted = format_quantity(str(cumulative_ask_qty), 6)
                    cum_usd_formatted = format_quantity(str(cumulative_ask_usd), 6)
                    
                    if cumulative_ask_qty > 0:
                        avg_price = cumulative_ask_usd / cumulative_ask_qty
                        avg_price_formatted = format_price(str(avg_price), 5)
                    else:
                        avg_price_formatted = "0.00000"
                    
                except (ValueError, TypeError):
                    total_formatted = "0.000000"
                    cum_qty_formatted = "0.000000"
                    cum_usd_formatted = "0.000000"
                    avg_price_formatted = "0.00000"
                
                asks_table.add_row(
                    Text(price_formatted, style="red"),
                    Text(quantity_formatted, style="white"),
                    Text(total_formatted, style="yellow"),
                    Text(cum_qty_formatted, style="cyan"),
                    Text(cum_usd_formatted, style="magenta"),
                    Text(avg_price_formatted, style="bright_blue")
                )
            
            for i in range(len(asks), 20):
                asks_table.add_row(
                    Text("--", style="dark_red"),
                    Text("--", style="dark_red"),
                    Text("--", style="dark_red"),
                    Text("--", style="dark_red"),
                    Text("--", style="dark_red"),
                    Text("--", style="dark_red")
                )
                    
        except Exception as e:
            logging.error(f"Orderbook display error: {str(e)}")

class MEXCMultiOrderbookApp(App):
    CSS = """
        Screen { layout: vertical; background: #1a1a1a; }
        OrderbookConnectionPanel { height: 30%; width: 100%; }
        OrderbookDisplayPanel { height: 70%; width: 100%; }
        DataTable { width: 100%; background: #1a1a1a; color: white; }
        RichLog { background: #0f0f0f; color: $success; border: solid #333333; overflow: auto; }
        """
    
    BINDINGS = [
        ("n", "next_symbol", "Next Symbol"),
        ("p", "prev_symbol", "Prev Symbol"),
        ("q", "quit", "Quit")
    ]

    def __init__(self):
        super().__init__()
        logging.info("Multi-orderbook app initialized")

    def compose(self):
        yield OrderbookConnectionPanel()
        yield OrderbookDisplayPanel()

    def on_mount(self):
        try:
            self.set_interval(0.05, self.update_displays)
            logging.info("Multi-orderbook monitor mounted")
        except Exception as e:
            logging.error(f"Mount failed: {str(e)}", exc_info=True)

    def update_displays(self):
        try:
            if not connection_queue.empty():
                conn_state = connection_queue.get_nowait()
                if conn_state:
                    try:
                        conn_panel = self.query_one(OrderbookConnectionPanel)
                        if conn_panel:
                            conn_panel.update_connection_info(conn_state)
                    except NoMatches:
                        pass
            
            if not debug_queue.empty():
                debug_msg = debug_queue.get_nowait()
                if debug_msg:
                    try:
                        conn_panel = self.query_one(OrderbookConnectionPanel)
                        if conn_panel:
                            conn_panel.add_debug_message(debug_msg['message'], debug_msg['type'])
                    except NoMatches:
                        pass
            
            if not orderbook_queue.empty():
                update = orderbook_queue.get_nowait()
                if update:
                    try:
                        orderbook_panel = self.query_one(OrderbookDisplayPanel)
                        if orderbook_panel:
                            orderbook_panel.update_orderbook(update['symbol'], update['data'])
                    except NoMatches:
                        pass

        except Exception as e:
            logging.error(f"Display update error: {str(e)}", exc_info=True)
    
    def action_next_symbol(self):
        global active_symbol_index, selected_symbols, current_orderbooks
        if selected_symbols:
            active_symbol_index = (active_symbol_index + 1) % len(selected_symbols)
            symbol = selected_symbols[active_symbol_index]
            
            try:
                orderbook_panel = self.query_one(OrderbookDisplayPanel)
                orderbook_panel.update_symbol_header(symbol)
                
                if symbol in current_orderbooks:
                    orderbook_panel.update_orderbook(symbol, current_orderbooks[symbol])
                
                update_connection_state(active_symbol=symbol)
                debug_log(f"➡️ Switched to {symbol}", 'info')
            except:
                pass
    
    def action_prev_symbol(self):
        global active_symbol_index, selected_symbols, current_orderbooks
        if selected_symbols:
            active_symbol_index = (active_symbol_index - 1) % len(selected_symbols)
            symbol = selected_symbols[active_symbol_index]
            
            try:
                orderbook_panel = self.query_one(OrderbookDisplayPanel)
                orderbook_panel.update_symbol_header(symbol)
                
                if symbol in current_orderbooks:
                    orderbook_panel.update_orderbook(symbol, current_orderbooks[symbol])
                
                update_connection_state(active_symbol=symbol)
                debug_log(f"⬅️ Switched to {symbol}", 'info')
            except:
                pass

def main():
    global should_exit, selected_symbols, active_symbol_index
    
    try:
        print("🔥 MEXC MULTI-SYMBOL ORDERBOOK MONITOR")
        print("✅ ALL FEATURES: Listen key + API keys + Cumulative + Weighted avg")
        print("="*75)
        
        protobuf_modules, success = load_generated_proto_protobuf()
        if not success:
            print("❌ Failed to load protobuf!")
            return
        
        setup_logging()
        logging.info("Starting multi-symbol orderbook monitor")
        
        selected_symbols = get_symbol_selection()
        active_symbol_index = 0
        
        print(f"\n🎯 Monitoring {len(selected_symbols)} symbols")
        print("📊 Press 'n' for next, 'p' for previous, 'q' to quit\n")
        
        set_terminal_title(f"MEXC Multi-Symbol Monitor - {len(selected_symbols)} symbols")
        
        monitor = MEXCMultiSymbolOrderbookMonitor(selected_symbols, protobuf_modules)
        
        monitor_thread = threading.Thread(target=monitor.start_monitoring, daemon=True)
        monitor_thread.start()
        
        app = MEXCMultiOrderbookApp()
        app.run()
        
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt")
        should_exit = True
    except Exception as e:
        logging.error(f"Error: {str(e)}", exc_info=True)
    finally:
        should_exit = True
        if 'monitor' in locals():
            monitor.stop_monitoring()
        logging.info("Monitor shutdown complete")

if __name__ == "__main__":
    main()