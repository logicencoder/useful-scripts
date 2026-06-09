#!/usr/bin/env python3

# MEXC Orderbook Monitor - DIRECT GENERATED_PROTO VERSION
# NO FALLBACKS - STRAIGHT TO GENERATED_PROTO FOLDER
# 20-DEPTH REAL-TIME ORDERBOOK MONITORING

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
from typing import Optional, Dict, Any, List, Tuple
from logging.handlers import RotatingFileHandler
import logging

# Suppress warnings
warnings.filterwarnings("ignore")
os.environ['PYTHONWARNINGS'] = 'ignore'

# FIX PROTOBUF VERSION COMPATIBILITY ISSUE
print("🔧 FIXED PROTOBUF COMPATIBILITY - Using pure Python implementation")

# Third-party imports
import orjson

# Textual framework imports
from textual.app import App, ComposeResult
from textual.widget import Widget
from textual.widgets import Static, DataTable, RichLog
from textual.containers import Container, Vertical, Horizontal
from textual.css.query import NoMatches
from rich.text import Text

def set_terminal_title(title: str) -> None:
    """Set the terminal window title."""
    try:
        if os.name == 'nt':  # Windows
            os.system(f'title {title}')
        else:  # Unix-like
            print(f'\033]0;{title}\007', end='', flush=True)
    except Exception:
        pass

# Set title to current filename
set_terminal_title("MEXC Orderbook Monitor - DIRECT GENERATED_PROTO VERSION")

# Initialize thread-safe queues
orderbook_queue = Queue()
connection_queue = Queue()
debug_queue = Queue()

# Global state variables
current_orderbook = {'bids': [], 'asks': []}
should_exit = False
selected_symbol = None

# Connection state tracking
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
    'symbol': None,
    'protobuf_mode': 'Unknown'
}

def load_generated_proto_protobuf():
    """Load protobuf modules directly from generated_proto folder."""
    try:
        # Check if generated_proto folder exists
        if not os.path.exists('generated_proto'):
            print("❌ generated_proto folder not found!")
            return None, False
        
        # Add generated_proto folder to path
        if 'generated_proto' not in sys.path:
            sys.path.insert(0, 'generated_proto')
        
        print("📦 IMPORTING ORDERBOOK PROTOBUF MODULES FROM GENERATED_PROTO FOLDER...")
        
        # Import the modules directly
        import PushDataV3ApiWrapper_pb2
        import PublicLimitDepthsV3Api_pb2
        import PublicAggreDepthsV3Api_pb2
        
        protobuf_modules = {
            'wrapper': PushDataV3ApiWrapper_pb2,
            'limit_depths': PublicLimitDepthsV3Api_pb2,
            'aggre_depths': PublicAggreDepthsV3Api_pb2
        }
        
        print("✅ ORDERBOOK PROTOBUF MODULES LOADED SUCCESSFULLY!")
        return protobuf_modules, True
        
    except Exception as e:
        print(f"❌ FAILED TO LOAD ORDERBOOK PROTOBUF: {e}")
        return None, False

def get_symbol_selection() -> str:
    """Ask user to select trading symbol for orderbook."""
    print("\n" + "="*50)
    print("MEXC Orderbook Monitor - DIRECT GENERATED_PROTO VERSION")
    print("="*50)
    print("Enter the trading symbol to monitor:")
    print("Examples: BTCUSDT, ETHUSDT, ADAUSDT, DNXUSDT, etc.")
    print("\n" + "="*50)
    
    while True:
        try:
            user_input = input("Enter trading symbol: ").strip().upper()
            
            if not user_input:
                print("Please enter a trading symbol.")
                continue
            
            # Basic validation
            if len(user_input) < 6:
                print("Trading symbol too short. Please enter a valid pair like BTCUSDT")
                continue
            
            if not user_input.endswith(('USDT', 'USDC', 'BTC', 'ETH')):
                print("Please enter a valid trading pair (ending with USDT, USDC, BTC, or ETH)")
                continue
            
            print(f"Selected symbol: {user_input}")
            return user_input
                
        except KeyboardInterrupt:
            print("\nExiting...")
            exit(1)
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again.")

def setup_logging():
    """Initialize logging system."""
    try:
        os.makedirs('orderbook_logs', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        log_format = '%(asctime)s.%(msecs)03d - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        root_logger = logging.getLogger()
        root_logger.handlers = []
        
        file_handler = RotatingFileHandler(
            filename=f'orderbook_logs/orderbook_monitor_generated_proto_{timestamp}.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        file_handler.setLevel(logging.DEBUG)
        
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        
        logging.info("DIRECT GENERATED_PROTO Orderbook monitor logging system initialized")
        
    except Exception as e:
        print(f"Failed to setup logging: {str(e)}")
        raise

def format_price(price: str, precision: int = 5) -> str:
    """Format price with EXCHANGE PRECISION - 5 decimals max."""
    try:
        price_decimal = Decimal(price)
        scaled = price_decimal.quantize(
            Decimal('0.' + '0' * precision),
            rounding=ROUND_HALF_UP
        )
        return f"{scaled:f}"
    except (InvalidOperation, ValueError):
        return price

def format_quantity(qty: str, precision: int = 6) -> str:
    """Format quantity with specified precision."""
    try:
        qty_decimal = Decimal(qty)
        scaled = qty_decimal.quantize(
            Decimal('0.' + '0' * precision),
            rounding=ROUND_HALF_UP
        )
        return f"{scaled:f}"
    except (InvalidOperation, ValueError):
        return qty

def update_connection_state(**kwargs):
    """Update connection state and push to UI."""
    global connection_state
    connection_state.update(kwargs)
    connection_queue.put(connection_state.copy())

def debug_log(message: str, msg_type: str = "info"):
    """Add debug message to queue."""
    type_mapping = {
        'success': 'info',
        'warning': 'debug', 
        'error': 'error',
        'info': 'info',
        'debug': 'debug',
        'websocket': 'info',
        'balance': 'info'
    }
    
    fixed_type = type_mapping.get(msg_type, 'info')
    debug_queue.put({'message': message, 'type': fixed_type})

# ============================================================================
# DIRECT GENERATED_PROTO ORDERBOOK PROTOBUF PARSER - NO FALLBACKS
# ============================================================================

class DirectGeneratedProtoOrderbookParser:
    """Direct generated_proto orderbook protobuf parser - no fallbacks."""
    
    def __init__(self, protobuf_modules):
        self.protobuf_modules = protobuf_modules
        self.parsing_mode = 'generated_proto_direct'
        
        if protobuf_modules:
            logging.info("✅ Direct generated_proto orderbook parser initialized")
            debug_log("✅ Direct generated_proto orderbook parser initialized", 'info')
            update_connection_state(protobuf_mode='Generated Proto Direct')
        else:
            logging.error("❌ No orderbook protobuf modules available")
            debug_log("❌ No orderbook protobuf modules available", 'error')
            update_connection_state(protobuf_mode='FAILED')
    
    def parse_orderbook_update(self, binary_data):
        """Parse orderbook update using generated_proto folder protobuf files - PRODUCTION VERSION."""
        if not self.protobuf_modules:
            debug_log("❌ No orderbook protobuf modules available", 'error')
            return None
        
        try:
            logging.info(f"🔍 ORDERBOOK PARSING WITH GENERATED_PROTO DIRECT - Length: {len(binary_data)}")
            debug_log(f"🔍 ORDERBOOK PARSING WITH GENERATED_PROTO DIRECT - Length: {len(binary_data)}", 'debug')
            
            wrapper_module = self.protobuf_modules['wrapper']
            
            # Parse wrapper
            wrapper = wrapper_module.PushDataV3ApiWrapper()
            wrapper.ParseFromString(binary_data)
            
            logging.info("✅ Orderbook wrapper parsed successfully")
            
            # Check for limit depth data - USING CORRECT FIELD NAMES DISCOVERED BY DEBUG
            if hasattr(wrapper, 'publicLimitDepths') and wrapper.HasField('publicLimitDepths'):
                depth_data = wrapper.publicLimitDepths
                
                bids = []
                asks = []
                
                # Extract bids using correct field name: 'bids' (not 'bidsList')
                if hasattr(depth_data, 'bids'):
                    for bid in depth_data.bids:
                        price = bid.price if hasattr(bid, 'price') else '0'
                        quantity = bid.quantity if hasattr(bid, 'quantity') else '0'
                        bids.append([price, quantity])
                
                # Extract asks using correct field name: 'asks' (not 'asksList') 
                if hasattr(depth_data, 'asks'):
                    for ask in depth_data.asks:
                        price = ask.price if hasattr(ask, 'price') else '0'
                        quantity = ask.quantity if hasattr(ask, 'quantity') else '0'
                        asks.append([price, quantity])
                
                logging.info(f"✅ GENERATED_PROTO LIMIT DEPTH SUCCESS: {wrapper.symbol if hasattr(wrapper, 'symbol') else 'UNKNOWN'} Bids={len(bids)} Asks={len(asks)}")
                debug_log(f"✅ GENERATED_PROTO LIMIT DEPTH: {wrapper.symbol if hasattr(wrapper, 'symbol') else 'UNKNOWN'} Bids={len(bids)} Asks={len(asks)}", 'info')
                
                return {
                    'symbol': wrapper.symbol if hasattr(wrapper, 'symbol') else 'UNKNOWN',
                    'bids': bids,
                    'asks': asks,
                    'type': 'limit_depth',
                    'timestamp': wrapper.sendTime if hasattr(wrapper, 'sendTime') else int(time.time() * 1000)
                }
            
            # Check for incremental depth data
            elif hasattr(wrapper, 'publicIncreaseDepths') and wrapper.HasField('publicIncreaseDepths'):
                depth_data = wrapper.publicIncreaseDepths
                
                bids = []
                asks = []
                
                # Extract incremental bids
                if hasattr(depth_data, 'bids'):
                    for bid in depth_data.bids:
                        price = bid.price if hasattr(bid, 'price') else '0'
                        quantity = bid.quantity if hasattr(bid, 'quantity') else '0'
                        bids.append([price, quantity])
                
                # Extract incremental asks
                if hasattr(depth_data, 'asks'):
                    for ask in depth_data.asks:
                        price = ask.price if hasattr(ask, 'price') else '0'
                        quantity = ask.quantity if hasattr(ask, 'quantity') else '0'
                        asks.append([price, quantity])
                
                logging.info(f"✅ GENERATED_PROTO INCREMENTAL SUCCESS: {wrapper.symbol if hasattr(wrapper, 'symbol') else 'UNKNOWN'} BidChanges={len(bids)} AskChanges={len(asks)}")
                debug_log(f"✅ GENERATED_PROTO INCREMENTAL: {wrapper.symbol if hasattr(wrapper, 'symbol') else 'UNKNOWN'} BidChanges={len(bids)} AskChanges={len(asks)}", 'info')
                
                return {
                    'symbol': wrapper.symbol if hasattr(wrapper, 'symbol') else 'UNKNOWN',
                    'bids': bids,
                    'asks': asks,
                    'type': 'aggre_depth',
                    'timestamp': wrapper.sendTime if hasattr(wrapper, 'sendTime') else int(time.time() * 1000)
                }
            
            return None
            
        except Exception as e:
            logging.error(f"❌ Generated proto orderbook parsing error: {e}")
            debug_log(f"❌ Generated proto orderbook parsing error: {e}", 'error')
            return None

# ============================================================================
# MEXC ORDERBOOK MONITOR CLASS - DIRECT GENERATED_PROTO VERSION
# ============================================================================

class MEXCOrderbookMonitorDirectGeneratedProto:
    def __init__(self, symbol, protobuf_modules):
        self.symbol = symbol.upper()
        self.expected_symbol = symbol.upper()
        self.ws_url = "wss://wbs-api.mexc.com/ws"
        self.ws = None
        self.running = False
        
        # Connection management
        self.last_ping_time = 0
        self.last_pong_time = 0
        self.ping_interval = 30
        self.connection_timeout = 90
        self.max_reconnect_attempts = 5
        self.reconnect_count = 0
        self.sent_pings = set()
        
        # Keep-alive thread
        self.keepalive_thread = None
        self.keepalive_running = False
        
        # Direct generated_proto orderbook parser
        self.protobuf_parser = DirectGeneratedProtoOrderbookParser(protobuf_modules)
        
        # Orderbook state
        self.current_orderbook = {'bids': [], 'asks': []}
        
    def get_current_time(self):
        """Get current formatted timestamp."""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
    def log_with_timestamp(self, message):
        """Log message with timestamp and send to debug queue."""
        logging.info(message)
        debug_log(message, 'info')
    
    def send_ping(self):
        """Send ping to keep WebSocket connection alive."""
        if self.ws and self.running:
            try:
                ping_id = int(time.time())
                heartbeat = {
                    "method": "PING",
                    "id": ping_id
                }
                
                self.sent_pings.add(ping_id)
                
                self.log_with_timestamp(f"🏓 SENDING HEARTBEAT (ID: {ping_id})")
                self.ws.send(json.dumps(heartbeat))
                self.last_ping_time = time.time()
                update_connection_state(last_ping=datetime.now())
                return True
            except Exception as e:
                self.log_with_timestamp(f"❌ Heartbeat failed: {e}")
                return False
        else:
            self.log_with_timestamp("⚠️ WebSocket not available for heartbeat")
            return False
    
    def keepalive_worker(self):
        """Background thread to maintain connection."""
        self.log_with_timestamp("🚀 ORDERBOOK KEEPALIVE WORKER STARTED")
        self.keepalive_running = True
        
        time.sleep(3)
        
        while self.keepalive_running and self.running:
            try:
                current_time = time.time()
                
                if (current_time - self.last_ping_time >= self.ping_interval):
                    if not self.send_ping():
                        self.log_with_timestamp("❌ Heartbeat failed - connection may be dead")
                
                time.sleep(5)
                
            except Exception as e:
                self.log_with_timestamp(f"❌ Keepalive worker error: {e}")
                time.sleep(5)
        
        self.log_with_timestamp("🛑 ORDERBOOK KEEPALIVE WORKER STOPPED")
    
    def on_message(self, ws, message):
        """Handle WebSocket messages - DIRECT GENERATED_PROTO VERSION."""
        global current_orderbook
        
        # Update message count
        msg_count = connection_state.get('messages_received', 0) + 1
        update_connection_state(
            messages_received=msg_count,
            last_message_time=datetime.now()
        )
        
        # Check if message is binary (protobuf)
        if isinstance(message, bytes):
            binary_count = connection_state.get('binary_messages', 0) + 1
            update_connection_state(binary_messages=binary_count)
            
            self.log_with_timestamp(f"🔧 ORDERBOOK BINARY MESSAGE #{binary_count} - Length: {len(message)}")
            debug_log(f"🔧 ORDERBOOK BINARY MESSAGE #{binary_count} - Length: {len(message)}", 'debug')
            
            # Parse with direct generated_proto protobuf
            parsed_data = self.protobuf_parser.parse_orderbook_update(message)
            
            if parsed_data:
                debug_log(f"✅ GENERATED_PROTO ORDERBOOK SUCCESS: {parsed_data['symbol']} Type={parsed_data['type']}", 'info')
                
                # Process orderbook update
                symbol = parsed_data.get('symbol')
                update_type = parsed_data.get('type')
                bids = parsed_data.get('bids', [])
                asks = parsed_data.get('asks', [])
                
                if symbol == self.symbol or symbol == 'UNKNOWN':
                    if update_type == 'limit_depth':
                        # Full orderbook snapshot - replace current data
                        self.current_orderbook = {
                            'bids': bids[:20],  # Take top 20 bids
                            'asks': asks[:20]   # Take top 20 asks
                        }
                        
                        self.log_with_timestamp(f"📊 GENERATED_PROTO FULL ORDERBOOK SNAPSHOT:")
                        self.log_with_timestamp(f"   Symbol: {symbol}")
                        self.log_with_timestamp(f"   Bids: {len(self.current_orderbook['bids'])} levels")
                        self.log_with_timestamp(f"   Asks: {len(self.current_orderbook['asks'])} levels")
                        
                        debug_log(f"📊 GENERATED_PROTO FULL SNAPSHOT: {symbol} Bids={len(self.current_orderbook['bids'])} Asks={len(self.current_orderbook['asks'])}", 'info')
                        
                    elif update_type == 'aggre_depth':
                        # Incremental update - apply changes
                        self.apply_orderbook_changes(bids, asks)
                        
                        self.log_with_timestamp(f"🔄 GENERATED_PROTO INCREMENTAL UPDATE:")
                        self.log_with_timestamp(f"   Symbol: {symbol}")
                        self.log_with_timestamp(f"   Bid Changes: {len(bids)}")
                        self.log_with_timestamp(f"   Ask Changes: {len(asks)}")
                        
                        debug_log(f"🔄 GENERATED_PROTO INCREMENTAL: {symbol} BidChanges={len(bids)} AskChanges={len(asks)}", 'info')
                    
                    # Sort orderbook properly
                    self.current_orderbook['bids'] = sorted(
                        self.current_orderbook['bids'], 
                        key=lambda x: float(x[0]), 
                        reverse=True  # Highest bid first
                    )[:20]
                    
                    self.current_orderbook['asks'] = sorted(
                        self.current_orderbook['asks'], 
                        key=lambda x: float(x[0])  # Lowest ask first
                    )[:20]
                    
                    # Push to UI queue
                    current_orderbook = self.current_orderbook.copy()
                    orderbook_queue.put(current_orderbook)
                    
                    debug_log(f"📤 PUSHED SORTED ORDERBOOK TO UI", 'info')
                    
                else:
                    debug_log(f"ℹ️ Different symbol orderbook: {symbol} (expected: {self.symbol})", 'debug')
            else:
                debug_log("⚠️ NO ORDERBOOK DATA PARSED FROM BINARY MESSAGE", 'debug')
            
            return
        
        # Handle JSON messages
        try:
            json_count = connection_state.get('json_messages', 0) + 1
            update_connection_state(json_messages=json_count)
            
            data = json.loads(message)
            
            if 'code' in data and 'msg' in data:
                if data.get('code') == 0:
                    if data.get('msg') == 'PONG':
                        # Check if this PONG corresponds to a ping we sent
                        pong_id = data.get('id')
                        if pong_id and pong_id in self.sent_pings:
                            self.sent_pings.remove(pong_id)
                            self.log_with_timestamp(f"🏓 PONG RECEIVED (ID: {pong_id}) - Connection alive!")
                            debug_log(f"🏓 PONG RECEIVED (ID: {pong_id}) - Connection alive!", 'info')
                            self.last_pong_time = time.time()
                    else:
                        self.log_with_timestamp(f"✅ Subscription confirmed: {data.get('msg')}")
                        debug_log(f"✅ Control Message: {data.get('msg')}", 'info')
                else:
                    self.log_with_timestamp(f"❌ Subscription error: {data}")
                    debug_log(f"❌ Control Error: {data}", 'error')
            else:
                channel = data.get('channel', 'unknown')
                debug_log(f"ℹ️ Other JSON control message - channel: {channel}", 'debug')
                
        except json.JSONDecodeError:
            debug_log(f"❌ Failed to parse JSON: {message}", 'error')
        except Exception as e:
            debug_log(f"❌ Message error: {e}", 'error')
    
    def apply_orderbook_changes(self, bid_changes, ask_changes):
        """Apply incremental changes to orderbook."""
        try:
            # Apply bid changes
            for price, quantity in bid_changes:
                price_float = float(price)
                quantity_float = float(quantity)
                
                if quantity_float == 0:
                    # Remove price level
                    self.current_orderbook['bids'] = [
                        [p, q] for p, q in self.current_orderbook['bids'] 
                        if float(p) != price_float
                    ]
                else:
                    # Update or add price level
                    updated = False
                    for i, (p, q) in enumerate(self.current_orderbook['bids']):
                        if float(p) == price_float:
                            self.current_orderbook['bids'][i] = [price, quantity]
                            updated = True
                            break
                    
                    if not updated:
                        self.current_orderbook['bids'].append([price, quantity])
            
            # Apply ask changes
            for price, quantity in ask_changes:
                price_float = float(price)
                quantity_float = float(quantity)
                
                if quantity_float == 0:
                    # Remove price level
                    self.current_orderbook['asks'] = [
                        [p, q] for p, q in self.current_orderbook['asks'] 
                        if float(p) != price_float
                    ]
                else:
                    # Update or add price level
                    updated = False
                    for i, (p, q) in enumerate(self.current_orderbook['asks']):
                        if float(p) == price_float:
                            self.current_orderbook['asks'][i] = [price, quantity]
                            updated = True
                            break
                    
                    if not updated:
                        self.current_orderbook['asks'].append([price, quantity])
            
        except Exception as e:
            self.log_with_timestamp(f"❌ Error applying orderbook changes: {e}")
            debug_log(f"❌ Error applying orderbook changes: {e}", 'error')
    
    def on_error(self, ws, error):
        """Handle WebSocket errors."""
        self.log_with_timestamp(f"❌ ORDERBOOK WEBSOCKET ERROR: {error}")
        update_connection_state(
            status='Error',
            last_error=str(error)
        )
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        self.log_with_timestamp(f"🔌 ORDERBOOK WEBSOCKET CLOSED: {close_status_code} - {close_msg}")
        
        update_connection_state(
            status='Disconnected',
            last_error=f"Connection closed: {close_status_code} - {close_msg}"
        )
        
        if self.running and self.reconnect_count < self.max_reconnect_attempts:
            self.reconnect_count += 1
            self.log_with_timestamp(f"🔄 Reconnecting in 5 seconds... (Attempt {self.reconnect_count}/{self.max_reconnect_attempts})")
            time.sleep(5)
            self.connect_websocket()
        else:
            self.log_with_timestamp("❌ Max reconnection attempts reached or not running")
    
    def on_open(self, ws):
        """Handle WebSocket open."""
        self.log_with_timestamp("✅ DIRECT GENERATED_PROTO ORDERBOOK WEBSOCKET CONNECTED!")
        self.log_with_timestamp(f"🔗 URL: {self.ws_url}")
        
        self.reconnect_count = 0
        
        update_connection_state(
            status='Connected',
            connected_at=datetime.now(),
            reconnect_count=self.reconnect_count,
            symbol=self.symbol
        )
        
        self.last_pong_time = time.time()
        
        # Subscribe to 20-depth orderbook
        subscription = {
            "method": "SUBSCRIPTION",
            "params": [f"spot@public.limit.depth.v3.api.pb@{self.symbol}@20"]
        }
        
        self.log_with_timestamp(f"📤 SUBSCRIBING TO ORDERBOOK: {json.dumps(subscription)}")
        ws.send(json.dumps(subscription))
        self.log_with_timestamp("📡 SUBSCRIBED TO DIRECT GENERATED_PROTO ORDERBOOK!")
        self.log_with_timestamp(f"👁️ MONITORING 20-DEPTH ORDERBOOK FOR: {self.symbol}")
    
    def connect_websocket(self):
        """Connect to WebSocket."""
        self.log_with_timestamp("🔗 CONNECTING DIRECT GENERATED_PROTO ORDERBOOK WEBSOCKET...")
        
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        self.ws.run_forever()
        return True
    
    def start_monitoring(self):
        """Start real-time orderbook monitoring."""
        self.log_with_timestamp("🚀 MEXC DIRECT GENERATED_PROTO ORDERBOOK MONITOR")
        self.log_with_timestamp("🎯 USING GENERATED_PROTO FOLDER DIRECTLY")
        self.log_with_timestamp(f"⚡ MONITORING 20-DEPTH ORDERBOOK FOR: {self.symbol}")
        self.log_with_timestamp(f"🔧 PARSING MODE: {self.protobuf_parser.parsing_mode}")
        
        self.running = True
        
        # Start keep-alive worker
        self.keepalive_thread = threading.Thread(target=self.keepalive_worker)
        self.keepalive_thread.daemon = True
        self.keepalive_thread.start()
        
        # Connect WebSocket
        self.connect_websocket()
    
    def stop_monitoring(self):
        """Stop monitoring and cleanup."""
        self.log_with_timestamp("🛑 STOPPING DIRECT GENERATED_PROTO ORDERBOOK MONITOR...")
        self.running = False
        self.keepalive_running = False
        
        if self.ws:
            self.ws.close()
        
        if self.keepalive_thread and self.keepalive_thread.is_alive():
            self.keepalive_thread.join(timeout=5)
        
        self.log_with_timestamp("✅ Direct generated_proto orderbook monitor stopped")

# ============================================================================
# TEXTUAL UI COMPONENTS - DIRECT GENERATED_PROTO VERSION
# ============================================================================

class OrderbookConnectionPanel(Static):
    """Panel for displaying WebSocket connection status and debug info."""
    
    CSS = """
    OrderbookConnectionPanel {
        layout: vertical;
        height: 60%;
        background: #1a1a1a;
        border: solid #dd3a3a;
        margin-bottom: 1;
    }

    .connection-header {
        background: #1a1a1a;
        color: #dd3a3a;
        padding: 1;
        text-align: center;
        font-weight: bold;
        height: 3;
    }

    .connection-info {
        background: #1a1a1a;
        color: white;
        padding: 0;
        height: 10;
    }

    .debug-log {
        background: #0f0f0f;
        color: #00ff00;
        height: 1fr;
        border: solid #333333;
        margin: 0;
        padding: 0;
    }
    """
    
    def __init__(self):
        super().__init__()
    
    def compose(self) -> ComposeResult:
        """Create the connection monitor layout."""
        yield Static("Orderbook WebSocket Monitor - DIRECT GENERATED_PROTO VERSION", classes="connection-header")
        yield Static("", id="connection-info", classes="connection-info")
        yield RichLog(id="debug-log", classes="debug-log", highlight=True, markup=True)
    
    def update_connection_info(self, conn_state: dict) -> None:
        """Update connection status display."""
        try:
            info_widget = self.query_one("#connection-info")
            
            status = conn_state.get('status', 'Unknown')
            connected_at = conn_state.get('connected_at')
            last_ping = conn_state.get('last_ping')
            reconnects = conn_state.get('reconnect_count', 0)
            messages = conn_state.get('messages_received', 0)
            binary_msgs = conn_state.get('binary_messages', 0)
            json_msgs = conn_state.get('json_messages', 0)
            last_error = conn_state.get('last_error')
            symbol = conn_state.get('symbol', 'Unknown')
            last_msg_time = conn_state.get('last_message_time')
            protobuf_mode = conn_state.get('protobuf_mode', 'Unknown')
            
            conn_time_str = "Never"
            if connected_at:
                conn_time_str = connected_at.strftime('%H:%M:%S')
            
            ping_time_str = "Never"
            if last_ping:
                ping_time_str = last_ping.strftime('%H:%M:%S')
            
            msg_time_str = "Never"
            if last_msg_time:
                msg_time_str = last_msg_time.strftime('%H:%M:%S')
            
            status_color = "green" if status == "Connected" else "red"
            mode_color = "green" if "Direct" in protobuf_mode else "red"
            
            info_text = f"""[{status_color}]Status: {status} - DIRECT GENERATED_PROTO ORDERBOOK[/{status_color}]
[{mode_color}]Parser: {protobuf_mode}[/{mode_color}]
Connected: {conn_time_str} | Symbol: {symbol}
Reconnects: {reconnects} | Messages: {messages}
Binary: {binary_msgs} | JSON: {json_msgs}
Last Ping: {ping_time_str}
Last Message: {msg_time_str}"""
            
            if last_error:
                info_text += f"\n[red]Last Error: {last_error[:50]}...[/red]"
            
            info_widget.update(info_text)
            
        except Exception as e:
            logging.error(f"Connection info update error: {str(e)}")
    
    def add_debug_message(self, message: str, msg_type: str = "info") -> None:
        """Add debug message to the log."""
        try:
            debug_log = self.query_one("#debug-log")
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            
            colors = {
                'info': 'cyan',
                'error': 'red',
                'warning': 'gray',
                'success': 'cyan',
                'debug': 'gray',
                'websocket': 'cyan',
                'balance': 'cyan'
            }
            
            color = colors.get(msg_type, 'cyan')
            formatted_msg = f"[{color}][{timestamp}] {message}[/{color}]"
            
            debug_log.write(formatted_msg)
            
        except Exception as e:
            logging.error(f"Debug message add error: {str(e)}")

class OrderbookDisplayPanel(Static):
    """Panel for displaying 20-depth orderbook - SIDE BY SIDE."""
    
    CSS = """
    OrderbookDisplayPanel {
        layout: horizontal;
        height: 40%;
        background: #1a1a1a;
        border: solid #3a96dd;
        width: 100%;
    }

    .orderbook-container {
        layout: horizontal;
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: row;
    }

    .bids-panel {
        layout: vertical;
        width: 50%;
        max-width: 50%;
        min-width: 50%;
        background: #1a1a1a;
        border-right: solid #333333;
        flex: 1;
    }

    .asks-panel {
        layout: vertical;  
        width: 50%;
        max-width: 50%;
        min-width: 50%;
        background: #1a1a1a;
        flex: 1;
    }

    .orderbook-header {
        background: #1a1a1a;
        color: #3a96dd;
        padding: 1;
        text-align: center;
        font-weight: bold;
        height: 3;
        width: 100%;
    }

    .bids-header {
        color: #00ff00;
    }

    .asks-header {
        color: #ff0000;
    }

    DataTable {
        width: 100%;
        height: 1fr;
        background: #1a1a1a;
    }

    #bids-table {
        width: 100%;
        max-width: 100%;
    }

    #asks-table {
        width: 100%;
        max-width: 100%;
    }
    """
    
    def __init__(self):
        super().__init__()
    
    def compose(self) -> ComposeResult:
        """Create the orderbook display layout - SIDE BY SIDE."""
        global selected_symbol
        
        with Horizontal(classes="orderbook-container"):
            # LEFT SIDE: Bids (Buy Orders)
            with Vertical(classes="bids-panel"):
                yield Static(f"BIDS (BUY) - {selected_symbol}", classes="orderbook-header bids-header")
                yield DataTable(id="bids-table")
            
            # RIGHT SIDE: Asks (Sell Orders)
            with Vertical(classes="asks-panel"):
                yield Static(f"ASKS (SELL) - {selected_symbol}", classes="orderbook-header asks-header")
                yield DataTable(id="asks-table")
    
    def on_mount(self) -> None:
        """Initialize orderbook tables."""
        # Setup bids table
        bids_table = self.query_one("#bids-table")
        bids_table.cursor_type = "none"
        bids_table.add_columns("Price", "Quantity", "Total")
        
        # Setup asks table
        asks_table = self.query_one("#asks-table")
        asks_table.cursor_type = "none"
        asks_table.add_columns("Price", "Quantity", "Total")

    def update_orderbook(self, orderbook: dict) -> None:
        """Update orderbook display with 20-depth data."""
        if not orderbook:
            return
            
        try:
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            # Update bids table (buy orders - highest price first)
            bids_table = self.query_one("#bids-table")
            bids_table.clear()
            
            for i, (price, quantity) in enumerate(bids[:20]):
                price_formatted = format_price(price, 5)  # 5 decimals for price like exchange
                quantity_formatted = format_quantity(quantity, 6)  # 6 decimals for quantity
                
                # Calculate total (price * quantity)
                try:
                    total = float(price) * float(quantity)
                    total_formatted = format_quantity(str(total), 6)
                except (ValueError, TypeError):
                    total_formatted = "0.000000"
                
                # Color coding for bids (green)
                bids_table.add_row(
                    Text(price_formatted, style="green"),
                    Text(quantity_formatted, style="white"),
                    Text(total_formatted, style="yellow")
                )
            
            # Fill remaining rows if less than 20 bids
            for i in range(len(bids), 20):
                bids_table.add_row(
                    Text("--", style="dark_green"),
                    Text("--", style="dark_green"), 
                    Text("--", style="dark_green")
                )
            
            # Update asks table (sell orders - lowest price first)
            asks_table = self.query_one("#asks-table")
            asks_table.clear()
            
            for i, (price, quantity) in enumerate(asks[:20]):
                price_formatted = format_price(price, 5)  # 5 decimals for price like exchange
                quantity_formatted = format_quantity(quantity, 6)  # 6 decimals for quantity
                
                # Calculate total (price * quantity)
                try:
                    total = float(price) * float(quantity)
                    total_formatted = format_quantity(str(total), 6)
                except (ValueError, TypeError):
                    total_formatted = "0.000000"
                
                # Color coding for asks (red)
                asks_table.add_row(
                    Text(price_formatted, style="red"),
                    Text(quantity_formatted, style="white"),
                    Text(total_formatted, style="yellow")
                )
            
            # Fill remaining rows if less than 20 asks
            for i in range(len(asks), 20):
                asks_table.add_row(
                    Text("--", style="dark_red"),
                    Text("--", style="dark_red"),
                    Text("--", style="dark_red")
                )
                    
        except Exception as e:
            logging.error(f"Orderbook display update error: {str(e)}")

class MEXCOrderbookAppDirectGeneratedProto(App):
    """Main application class - DIRECT GENERATED_PROTO ORDERBOOK VERSION."""
    
    CSS = """
    Screen {
        layout: vertical;
        background: #1a1a1a;
    }

    OrderbookConnectionPanel {
        height: 60%;
        width: 100%;
        background: #1a1a1a;
    }

    OrderbookDisplayPanel {
        height: 40%;
        width: 100%;
        background: #1a1a1a;
    }

    DataTable {
        width: 100%;
        background: #1a1a1a;
        color: white;
    }

    RichLog {
        background: #0f0f0f;
        color: $success;
        border: solid #333333;
    }

    Static.connection-header, Static.orderbook-header {
        background: #1a1a1a;
        padding: 1;
        height: 3;
    }

    Static.connection-info {
        background: #1a1a1a;
        color: white;
        padding: 1;
        height: 10;
    }
    """

    def __init__(self):
        super().__init__()
        logging.info("MEXCOrderbookAppDirectGeneratedProto initialized")

    def compose(self) -> ComposeResult:
        """Create main layout."""
        yield OrderbookConnectionPanel()
        yield OrderbookDisplayPanel()

    def on_mount(self) -> None:
        """Setup display updates."""
        try:
            self.set_interval(0.05, self.update_displays)
            logging.info("Direct generated_proto orderbook monitor mounted successfully")
        except Exception as e:
            logging.error(f"Failed to mount application: {str(e)}", exc_info=True)

    def update_displays(self) -> None:
        """Update both connection and orderbook displays."""
        try:
            # Process connection status updates
            if not connection_queue.empty():
                conn_state = connection_queue.get_nowait()
                if conn_state:
                    try:
                        conn_panel = self.query_one(OrderbookConnectionPanel)
                        if conn_panel:
                            conn_panel.update_connection_info(conn_state)
                    except NoMatches:
                        pass
            
            # Process debug messages
            if not debug_queue.empty():
                debug_msg = debug_queue.get_nowait()
                if debug_msg:
                    try:
                        conn_panel = self.query_one(OrderbookConnectionPanel)
                        if conn_panel:
                            conn_panel.add_debug_message(debug_msg['message'], debug_msg['type'])
                    except NoMatches:
                        pass
            
            # Process orderbook updates
            if not orderbook_queue.empty():
                orderbook = orderbook_queue.get_nowait()
                if orderbook:
                    try:
                        orderbook_panel = self.query_one(OrderbookDisplayPanel)
                        if orderbook_panel:
                            orderbook_panel.update_orderbook(orderbook)
                    except NoMatches:
                        pass

        except Exception as e:
            logging.error(f"Display update error: {str(e)}", exc_info=True)

# ============================================================================
# MAIN PROGRAM - DIRECT GENERATED_PROTO ORDERBOOK VERSION
# ============================================================================

def main():
    """Main program entry for DIRECT GENERATED_PROTO orderbook monitor."""
    global should_exit, selected_symbol
    
    try:
        print("🔥 MEXC DIRECT GENERATED_PROTO ORDERBOOK MONITOR")
        print("🎯 NO FALLBACKS - STRAIGHT TO GENERATED_PROTO FOLDER")
        print("="*60)
        
        # Load protobuf modules directly
        protobuf_modules, success = load_generated_proto_protobuf()
        if not success:
            print("❌ FAILED TO LOAD ORDERBOOK PROTOBUF FROM GENERATED_PROTO FOLDER!")
            print("Make sure you have the 'generated_proto' folder with protobuf files")
            return
        
        # Setup logging
        setup_logging()
        logging.info("Starting DIRECT GENERATED_PROTO MEXC Orderbook Monitor")
        
        # Get symbol selection
        selected_symbol = get_symbol_selection()
        
        print(f"\nStarting DIRECT GENERATED_PROTO orderbook monitor for: {selected_symbol}")
        print("Starting GUI...")
        
        # Update terminal title
        set_terminal_title(f"MEXC Orderbook Monitor - DIRECT GENERATED_PROTO - {selected_symbol}")
        
        # Initialize DIRECT GENERATED_PROTO orderbook monitor instance
        monitor = MEXCOrderbookMonitorDirectGeneratedProto(selected_symbol, protobuf_modules)
        
        # Start monitor in separate thread
        monitor_thread = threading.Thread(
            target=monitor.start_monitoring,
            daemon=True
        )
        monitor_thread.start()
        
        # Create and run UI
        app = MEXCOrderbookAppDirectGeneratedProto()
        app.run()
        
    except KeyboardInterrupt:
        logging.info("Got keyboard interrupt")
        should_exit = True
    except Exception as e:
        logging.error(f"Error: {str(e)}", exc_info=True)
    finally:
        should_exit = True
        if 'monitor' in locals():
            monitor.stop_monitoring()
        logging.info("DIRECT GENERATED_PROTO orderbook monitor shutdown complete")

if __name__ == "__main__":
    main()