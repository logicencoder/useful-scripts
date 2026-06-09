#!/usr/bin/env python3

# MEXC Balance Monitor - DIRECT DP FOLDER VERSION
# NO FALLBACKS - STRAIGHT TO DP FOLDER PROTOBUF

import os
import hmac
import time
import json
import hashlib
import threading
import requests
import websocket
import subprocess
import sys
import warnings
import atexit
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from urllib.parse import urlencode
from queue import Queue
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler
import logging

# Suppress ALL warnings
warnings.filterwarnings("ignore")
os.environ['PYTHONWARNINGS'] = 'ignore'

# FIX PROTOBUF VERSION COMPATIBILITY ISSUE
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'
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
set_terminal_title("MEXC Balance Monitor - DIRECT GENERATED_PROTO VERSION")

# Initialize thread-safe queues
balances_queue = Queue()
connection_queue = Queue()
debug_queue = Queue()

# Global state variables
current_balances = {}
should_exit = False
global_monitor = None  # Store monitor instance for cleanup

# HARDCODED COINS + USER SELECTED
HARDCODED_COINS = ['ETH', 'USDT', 'USDC']
selected_coin = None

# Connection state tracking
connection_state = {
    'status': 'Disconnected',
    'connected_at': None,
    'last_ping': None,
    'reconnect_count': 0,
    'last_error': None,
    'messages_received': 0,
    'listen_key': None,
    'listen_key_full': None,
    'last_message_time': None,
    'binary_messages': 0,
    'json_messages': 0,
    'last_key_extend': None,
    'protobuf_mode': 'Unknown',
    'listen_key_created_at': None,
    'listen_key_expires_at': None
}

def cleanup_on_exit():
    """Cleanup function called on program exit."""
    global global_monitor
    if global_monitor:
        print("\n🧹 CLEANING UP ON EXIT...")
        global_monitor.cleanup_and_stop()

# Register exit cleanup
atexit.register(cleanup_on_exit)

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
        
        print("📦 IMPORTING PROTOBUF MODULES FROM GENERATED_PROTO FOLDER...")
        
        # Import the modules directly
        import PrivateAccountV3Api_pb2
        import PushDataV3ApiWrapper_pb2
        
        protobuf_modules = {
            'account': PrivateAccountV3Api_pb2,
            'wrapper': PushDataV3ApiWrapper_pb2
        }
        
        print("✅ PROTOBUF MODULES LOADED SUCCESSFULLY!")
        return protobuf_modules, True
        
    except Exception as e:
        print(f"❌ FAILED TO LOAD PROTOBUF: {e}")
        return None, False

def normalize_coin_input(user_input: str) -> str:
    """Normalize coin input to base coin symbol."""
    if not user_input:
        return ""
    
    normalized = user_input.upper().strip()
    
    suffixes_to_remove = ['USDT', 'USDC', 'BTC', 'ETH']
    for suffix in suffixes_to_remove:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
            break
    
    normalized = ''.join(c for c in normalized if c.isalpha())
    return normalized

def get_user_coin_selection() -> str:
    """Ask user to select the 4th coin to track."""
    print("\n" + "="*50)
    print("MEXC Balance Monitor - DIRECT GENERATED_PROTO VERSION")
    print("="*50)
    print(f"Hardcoded coins: {', '.join(HARDCODED_COINS)}")
    print("\nEnter the 4th coin to track:")
    print("You can enter in any format (DNX, dnx, DNXUSDT, etc.)")
    print("\n" + "="*50)
    
    while True:
        try:
            user_input = input("Enter coin symbol: ").strip()
            
            if not user_input:
                print("Please enter a coin symbol.")
                continue
            
            normalized_coin = normalize_coin_input(user_input)
            
            if not normalized_coin:
                print("Invalid coin format. Please try again.")
                continue
            
            if normalized_coin in HARDCODED_COINS:
                print(f"'{normalized_coin}' is already in hardcoded coins: {HARDCODED_COINS}")
                print("Please select a different coin.")
                continue
            
            print(f"Selected coin: {normalized_coin}")
            return normalized_coin
                
        except KeyboardInterrupt:
            print("\nExiting...")
            exit(1)
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again.")

def setup_logging():
    """Initialize logging system."""
    try:
        os.makedirs('logs', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        log_format = '%(asctime)s.%(msecs)03d - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        root_logger = logging.getLogger()
        root_logger.handlers = []
        
        file_handler = RotatingFileHandler(
            filename=f'logs/balance_monitor_generated_proto_{timestamp}.log',
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        file_handler.setLevel(logging.DEBUG)
        
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        
        logging.info("DIRECT GENERATED_PROTO Balance monitor logging system initialized")
        
    except Exception as e:
        print(f"Failed to setup logging: {str(e)}")
        raise

def format_with_precision(value: Decimal, precision: Optional[int] = None) -> str:
    """Format decimal value with specified precision."""
    if precision is None:
        precision = 8
    
    try:
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        precision = max(0, int(precision))
        
        scaled = value.quantize(
            Decimal('0.' + '0' * precision),
            rounding=ROUND_HALF_UP
        )
        
        return f"{scaled:f}"
        
    except (InvalidOperation, ValueError) as e:
        logging.error(f"Failed to format value '{value}' with precision {precision}: {e}")
        return str(value)
    except Exception as e:
        logging.error(f"Unexpected formatting error: {e}")
        return str(value)

def load_api_keys():
    """Load API keys from configuration file."""
    try:
        with open('mexc_keys.json', 'r') as f:
            keys = json.load(f)
        
        api_key = keys.get('api_key')
        api_secret = keys.get('api_secret')
        
        if not api_key or not api_secret:
            print("❌ Missing keys in mexc_keys.json")
            return None, None
        
        return api_key, api_secret
        
    except Exception as e:
        print(f"❌ Error loading keys: {e}")
        return None, None

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
# DIRECT GENERATED_PROTO FOLDER PROTOBUF PARSER - NO FALLBACKS
# ============================================================================

class DirectGeneratedProtoProtobufParser:
    """Direct generated_proto folder protobuf parser - no fallbacks."""
    
    def __init__(self, protobuf_modules):
        self.protobuf_modules = protobuf_modules
        self.parsing_mode = 'generated_proto_direct'
        
        if protobuf_modules:
            logging.info("✅ Direct generated_proto protobuf parser initialized")
            debug_log("✅ Direct generated_proto protobuf parser initialized", 'info')
            update_connection_state(protobuf_mode='Generated Proto Direct')
        else:
            logging.error("❌ No protobuf modules available")
            debug_log("❌ No protobuf modules available", 'error')
            update_connection_state(protobuf_mode='FAILED')
    
    def parse_account_update(self, binary_data):
        """Parse account update using generated_proto folder protobuf files."""
        if not self.protobuf_modules:
            debug_log("❌ No protobuf modules available", 'error')
            return None
        
        try:
            logging.info(f"🔍 PARSING WITH GENERATED_PROTO DIRECT - Length: {len(binary_data)}")
            debug_log(f"🔍 PARSING WITH GENERATED_PROTO DIRECT - Length: {len(binary_data)}", 'debug')
            
            wrapper_module = self.protobuf_modules['wrapper']
            account_module = self.protobuf_modules['account']
            
            # Try wrapper first
            try:
                wrapper = wrapper_module.PushDataV3ApiWrapper()
                wrapper.ParseFromString(binary_data)
                
                logging.info("✅ Wrapper parsed successfully")
                
                if hasattr(wrapper, 'privateAccount') and wrapper.HasField('privateAccount'):
                    account_data = wrapper.privateAccount
                    
                    coin = account_data.vcoinName if hasattr(account_data, 'vcoinName') else 'UNKNOWN'
                    balance_amount = account_data.balanceAmount if hasattr(account_data, 'balanceAmount') else '0'
                    balance_change = account_data.balanceAmountChange if hasattr(account_data, 'balanceAmountChange') else '0'
                    frozen_amount = account_data.frozenAmount if hasattr(account_data, 'frozenAmount') else '0'
                    frozen_change = account_data.frozenAmountChange if hasattr(account_data, 'frozenAmountChange') else '0'
                    change_type = account_data.type if hasattr(account_data, 'type') else 'UNKNOWN'
                    timestamp = account_data.time if hasattr(account_data, 'time') else int(time.time() * 1000)
                    
                    logging.info(f"✅ GENERATED_PROTO WRAPPER SUCCESS: {coin} Available={balance_amount} Locked={frozen_amount}")
                    debug_log(f"✅ GENERATED_PROTO WRAPPER: {coin} Available={balance_amount} Locked={frozen_amount} Type={change_type}", 'info')
                    
                    return {
                        'vcoinName': coin,
                        'balanceAmount': balance_amount,
                        'balanceAmountChange': balance_change,
                        'frozenAmount': frozen_amount,
                        'frozenAmountChange': frozen_change,
                        'type': change_type,
                        'time': timestamp
                    }
            except Exception as e:
                logging.debug(f"Wrapper parsing failed: {e}")
            
            # Try direct account parsing
            try:
                account = account_module.PrivateAccountV3Api()
                account.ParseFromString(binary_data)
                
                coin = account.vcoinName if hasattr(account, 'vcoinName') else 'UNKNOWN'
                balance_amount = account.balanceAmount if hasattr(account, 'balanceAmount') else '0'
                balance_change = account.balanceAmountChange if hasattr(account, 'balanceAmountChange') else '0'
                frozen_amount = account.frozenAmount if hasattr(account, 'frozenAmount') else '0'
                frozen_change = account.frozenAmountChange if hasattr(account, 'frozenAmountChange') else '0'
                change_type = account.type if hasattr(account, 'type') else 'UNKNOWN'
                timestamp = account.time if hasattr(account, 'time') else int(time.time() * 1000)
                
                logging.info(f"✅ GENERATED_PROTO DIRECT SUCCESS: {coin} Available={balance_amount} Locked={frozen_amount}")
                debug_log(f"✅ GENERATED_PROTO DIRECT: {coin} Available={balance_amount} Locked={frozen_amount} Type={change_type}", 'info')
                
                return {
                    'vcoinName': coin,
                    'balanceAmount': balance_amount,
                    'balanceAmountChange': balance_change,
                    'frozenAmount': frozen_amount,
                    'frozenAmountChange': frozen_change,
                    'type': change_type,
                    'time': timestamp
                }
            except Exception as e:
                logging.debug(f"Direct account parsing failed: {e}")
            
            return None
            
        except Exception as e:
            logging.error(f"❌ Generated proto protobuf parsing error: {e}")
            debug_log(f"❌ Generated proto protobuf parsing error: {e}", 'error')
            return None

# ============================================================================
# MEXC BALANCE MONITOR CLASS - DIRECT GENERATED_PROTO FOLDER VERSION
# ============================================================================

class MEXCBalanceMonitorDirectGeneratedProto:
    def __init__(self, api_key, secret_key, monitored_coins, protobuf_modules):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://api.mexc.com"
        self.ws_url = "wss://wbs-api.mexc.com/ws"
        self.listen_key = None
        self.ws = None
        self.running = False
        self.monitored_coins = [coin.upper() for coin in monitored_coins]
        
        # Connection management
        self.last_ping_time = 0
        self.last_key_extend_time = 0
        self.last_pong_time = 0
        self.ping_interval = 30
        self.key_extend_interval = 1800
        self.connection_timeout = 90
        self.max_reconnect_attempts = 5
        self.reconnect_count = 0
        
        # Track ping IDs to prevent duplicate PONG messages
        self.sent_pings = set()
        
        # Keep-alive thread
        self.keepalive_thread = None
        self.keepalive_running = False
        
        # Direct generated_proto protobuf parser
        self.protobuf_parser = DirectGeneratedProtoProtobufParser(protobuf_modules)
        
        # Balance tracking
        self.previous_balances = {}
    
    def get_current_time(self):
        """Get current formatted timestamp."""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
    def log_with_timestamp(self, message):
        """Log message with timestamp and send to debug queue."""
        logging.info(message)
        debug_log(message, 'info')
        
    def generate_signature(self, params_string):
        """Generate HMAC SHA256 signature for API requests."""
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            params_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        self.log_with_timestamp(f"🔐 SIGNATURE: {signature}")
        return signature
    
    def get_timestamp(self):
        """Get current timestamp in milliseconds."""
        timestamp = int(time.time() * 1000)
        self.log_with_timestamp(f"⏰ TIMESTAMP: {timestamp}")
        return timestamp
    
    def delete_listen_key(self):
        """Delete listen key from MEXC."""
        if not self.listen_key:
            return True
            
        self.log_with_timestamp(f"🗑️ DELETING LISTEN KEY: {self.listen_key[:20]}...")
        
        try:
            timestamp = self.get_timestamp()
            params = f"listenKey={self.listen_key}&timestamp={timestamp}"
            signature = self.generate_signature(params)
            
            url = f"{self.base_url}/api/v3/userDataStream"
            headers = {'X-MEXC-APIKEY': self.api_key}
            data = f"{params}&signature={signature}"
            
            response = requests.delete(url, headers=headers, data=data)
            self.log_with_timestamp(f"📥 DELETE RESPONSE: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                self.log_with_timestamp("✅ Listen key deleted successfully")
                return True
            else:
                self.log_with_timestamp(f"⚠️ Failed to delete key: {response.text}")
                return False
        except Exception as e:
            self.log_with_timestamp(f"❌ Delete key error: {e}")
            return False
    
    def extend_listen_key(self):
        """Extend listen key validity."""
        if not self.listen_key:
            self.log_with_timestamp("❌ No listen key to extend")
            return False
            
        self.log_with_timestamp(f"🔄 EXTENDING LISTEN KEY: {self.listen_key[:20]}...")
        
        timestamp = self.get_timestamp()
        params = f"listenKey={self.listen_key}&timestamp={timestamp}"
        signature = self.generate_signature(params)
        
        url = f"{self.base_url}/api/v3/userDataStream"
        headers = {'X-MEXC-APIKEY': self.api_key}
        data = f"{params}&signature={signature}"
        
        try:
            response = requests.put(url, headers=headers, data=data)
            self.log_with_timestamp(f"📥 EXTEND RESPONSE: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                self.log_with_timestamp("✅ Listen key extended successfully")
                self.last_key_extend_time = time.time()
                
                expire_time = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
                update_connection_state(
                    last_key_extend=datetime.now(),
                    listen_key_expires_at=expire_time
                )
                return True
            else:
                self.log_with_timestamp(f"❌ Failed to extend key: {response.text}")
                return False
        except Exception as e:
            self.log_with_timestamp(f"❌ Extend key error: {e}")
            return False
    
    def send_ping(self):
        """Send ping to keep WebSocket connection alive."""
        if self.ws and self.running:
            try:
                ping_id = int(time.time())
                heartbeat = {
                    "method": "PING",
                    "id": ping_id
                }
                
                # Track this ping ID
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
        """Background thread to maintain connection and key."""
        self.log_with_timestamp("🚀 KEEPALIVE WORKER STARTED")
        self.keepalive_running = True
        
        time.sleep(3)
        
        while self.keepalive_running and self.running:
            try:
                current_time = time.time()
                
                if (current_time - self.last_ping_time >= self.ping_interval):
                    if not self.send_ping():
                        self.log_with_timestamp("❌ Heartbeat failed - connection may be dead")
                
                if current_time - self.last_key_extend_time >= self.key_extend_interval:
                    if not self.extend_listen_key():
                        self.log_with_timestamp("❌ Key extension failed - may need to reconnect")
                
                time.sleep(5)
                
            except Exception as e:
                self.log_with_timestamp(f"❌ Keepalive worker error: {e}")
                time.sleep(5)
        
        self.log_with_timestamp("🛑 KEEPALIVE WORKER STOPPED")
    
    def create_listen_key(self):
        """Create listen key."""
        self.log_with_timestamp("🔑 CREATING LISTEN KEY...")
        
        timestamp = self.get_timestamp()
        params = f"timestamp={timestamp}"
        signature = self.generate_signature(params)
        
        url = f"{self.base_url}/api/v3/userDataStream"
        headers = {'X-MEXC-APIKEY': self.api_key}
        data = f"{params}&signature={signature}"
        
        try:
            response = requests.post(url, headers=headers, data=data)
            self.log_with_timestamp(f"📥 CREATE RESPONSE: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if 'listenKey' in result:
                    self.listen_key = result['listenKey']
                    self.log_with_timestamp(f"✅ Created key: {self.listen_key[:20]}...")
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
                else:
                    self.log_with_timestamp(f"❌ No listenKey in response: {response.text}")
                    return False
            else:
                self.log_with_timestamp(f"❌ Create failed: {response.text}")
                return False
        except Exception as e:
            self.log_with_timestamp(f"❌ Create error: {e}")
            return False
    
    def on_message(self, ws, message):
        """Handle WebSocket messages - DIRECT GENERATED_PROTO VERSION."""
        global current_balances
        
        msg_count = connection_state.get('messages_received', 0) + 1
        update_connection_state(
            messages_received=msg_count,
            last_message_time=datetime.now()
        )
        
        if isinstance(message, bytes):
            binary_count = connection_state.get('binary_messages', 0) + 1
            update_connection_state(binary_messages=binary_count)
            
            self.log_with_timestamp(f"🔧 BINARY MESSAGE #{binary_count} - Length: {len(message)}")
            debug_log(f"🔧 BINARY MESSAGE #{binary_count} - Length: {len(message)}", 'debug')
            
            # Parse with direct generated_proto protobuf
            parsed_data = self.protobuf_parser.parse_account_update(message)
            
            if parsed_data:
                debug_log(f"✅ GENERATED_PROTO PARSE SUCCESS: {parsed_data}", 'info')
                
                coin = parsed_data.get('vcoinName')
                
                if coin in self.monitored_coins:
                    try:
                        available_balance = float(parsed_data.get('balanceAmount', 0))
                        locked_balance = float(parsed_data.get('frozenAmount', 0))
                        available_change = float(parsed_data.get('balanceAmountChange', 0))
                        locked_change = float(parsed_data.get('frozenAmountChange', 0))
                        operation_type = parsed_data.get('type', 'UNKNOWN')
                        
                        total_balance = available_balance + locked_balance
                        
                        self.log_with_timestamp(f"💰 GENERATED_PROTO BALANCE UPDATE:")
                        self.log_with_timestamp(f"   {coin} Available: {available_balance:.8f} (Δ{available_change:+.8f})")
                        self.log_with_timestamp(f"   {coin} Locked: {locked_balance:.8f} (Δ{locked_change:+.8f})")
                        self.log_with_timestamp(f"   {coin} Total: {total_balance:.8f}")
                        self.log_with_timestamp(f"   Operation: {operation_type}")
                        
                        debug_log(f"💰 GENERATED_PROTO UPDATE: {coin} Available={available_balance:.8f} Locked={locked_balance:.8f} Total={total_balance:.8f} Op={operation_type}", 'info')
                        
                        current_balances[coin] = {
                            'free': f"{available_balance:.8f}",
                            'locked': f"{locked_balance:.8f}"
                        }
                        
                        balances_queue.put(current_balances.copy())
                        debug_log(f"📤 PUSHED TO UI: {coin} balances updated", 'info')
                        
                    except ValueError as e:
                        self.log_with_timestamp(f"❌ Error converting balance values: {e}")
                        debug_log(f"❌ Balance conversion error: {e}", 'error')
                else:
                    debug_log(f"ℹ️ Binary message for unmonitored coin: {coin}", 'debug')
            
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
                            self.sent_pings.remove(pong_id)  # Remove from tracking
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
                debug_log(f"ℹ️ Other JSON message - channel: {channel}", 'debug')
                
        except json.JSONDecodeError:
            debug_log(f"❌ Failed to parse JSON: {message}", 'error')
        except Exception as e:
            debug_log(f"❌ Message error: {e}", 'error')
    
    def on_error(self, ws, error):
        """Handle WebSocket errors."""
        self.log_with_timestamp(f"❌ WEBSOCKET ERROR: {error}")
        update_connection_state(
            status='Error',
            last_error=str(error)
        )
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        self.log_with_timestamp(f"🔌 WEBSOCKET CLOSED: {close_status_code} - {close_msg}")
        
        update_connection_state(
            status='Disconnected',
            last_error=f"Connection closed: {close_status_code} - {close_msg}"
        )
        
        if self.running and self.reconnect_count < self.max_reconnect_attempts:
            self.reconnect_count += 1
            self.log_with_timestamp(f"🔄 Reconnecting in 5 seconds... (Attempt {self.reconnect_count}/{self.max_reconnect_attempts})")
            time.sleep(5)
            
            if not self.extend_listen_key():
                self.log_with_timestamp("⚠️ Listen key invalid, creating new one...")
                if not self.create_listen_key():
                    self.log_with_timestamp("❌ Failed to create new listen key")
                    return
            
            self.connect_websocket()
        else:
            self.log_with_timestamp("❌ Max reconnection attempts reached or not running")
    
    def on_open(self, ws):
        """Handle WebSocket open."""
        self.log_with_timestamp("✅ DIRECT GENERATED_PROTO WEBSOCKET CONNECTED!")
        self.log_with_timestamp(f"🔗 URL: {self.ws_url}?listenKey={self.listen_key[:20]}...")
        
        self.reconnect_count = 0
        
        update_connection_state(
            status='Connected',
            connected_at=datetime.now(),
            reconnect_count=self.reconnect_count
        )
        
        self.last_pong_time = time.time()
        
        subscription = {
            "method": "SUBSCRIPTION",
            "params": ["spot@private.account.v3.api.pb"]
        }
        
        self.log_with_timestamp(f"📤 SUBSCRIBING TO: {json.dumps(subscription)}")
        ws.send(json.dumps(subscription))
        self.log_with_timestamp("📡 SUBSCRIBED TO ACCOUNT UPDATES!")
        self.log_with_timestamp(f"👁️ MONITORING: {', '.join(self.monitored_coins)}")
    
    def connect_websocket(self):
        """Connect to WebSocket."""
        if not self.listen_key:
            self.log_with_timestamp("❌ No listen key available")
            return False
        
        ws_url = f"{self.ws_url}?listenKey={self.listen_key}"
        self.log_with_timestamp("🔗 CONNECTING WEBSOCKET...")
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        self.ws.run_forever()
        return True
    
    def fetch_initial_balances(self):
        """Fetch initial balances via REST API."""
        global current_balances
        
        self.log_with_timestamp("💰 FETCHING INITIAL BALANCES VIA REST API...")
        
        try:
            timestamp = self.get_timestamp()
            params = f"timestamp={timestamp}"
            signature = self.generate_signature(params)
            
            url = f"{self.base_url}/api/v3/account"
            headers = {'X-MEXC-APIKEY': self.api_key}
            params_with_sig = f"{params}&signature={signature}"
            
            full_url = f"{url}?{params_with_sig}"
            self.log_with_timestamp(f"🌐 REQUESTING: {url}")
            
            response = requests.get(full_url, headers=headers, timeout=10)
            self.log_with_timestamp(f"📥 BALANCE RESPONSE: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.log_with_timestamp(f"📊 RECEIVED BALANCE DATA")
                
                # Initialize all monitored coins with zero balance first
                for coin in self.monitored_coins:
                    current_balances[coin] = {
                        'free': '0.00000000',
                        'locked': '0.00000000'
                    }
                
                balance_count = 0
                total_assets = len(data.get('balances', []))
                self.log_with_timestamp(f"📊 PROCESSING {total_assets} ASSETS FROM API...")
                
                for balance in data.get('balances', []):
                    asset = balance['asset']
                    free_bal = balance['free']
                    locked_bal = balance['locked']
                    
                    # Only update if it's a monitored coin
                    if asset in self.monitored_coins:
                        current_balances[asset] = {
                            'free': free_bal,
                            'locked': locked_bal
                        }
                        balance_count += 1
                        self.log_with_timestamp(f"💰 {asset}: Free={free_bal}, Locked={locked_bal}")
                        debug_log(f"💰 INITIAL: {asset} Free={free_bal}, Locked={locked_bal}", 'info')
                
                # Push to UI
                balances_queue.put(current_balances.copy())
                self.log_with_timestamp(f"✅ Initial balances loaded: {balance_count}/{len(self.monitored_coins)} coins")
                debug_log(f"✅ Initial balances: {balance_count} of {len(self.monitored_coins)} coins loaded", 'info')
                
            else:
                self.log_with_timestamp(f"❌ Balance fetch failed: {response.status_code}")
                self.log_with_timestamp(f"❌ Response: {response.text}")
                debug_log(f"❌ Initial balance fetch failed: {response.status_code} - {response.text}", 'error')
                
                # Set all balances to zero if API fails
                for coin in self.monitored_coins:
                    current_balances[coin] = {
                        'free': '0.00000000',
                        'locked': '0.00000000'
                    }
                balances_queue.put(current_balances.copy())
                
        except Exception as e:
            self.log_with_timestamp(f"❌ Initial balance error: {e}")
            debug_log(f"❌ Initial balance error: {e}", 'error')

    def start_monitoring(self):
        """Start real-time monitoring."""
        self.log_with_timestamp("🚀 MEXC DIRECT GENERATED_PROTO BALANCE MONITOR")
        self.log_with_timestamp("🎯 USING GENERATED_PROTO FOLDER PROTOBUF FILES DIRECTLY")
        self.log_with_timestamp(f"⚡ MONITORING: {', '.join(self.monitored_coins)}")
        self.log_with_timestamp(f"🔧 PARSING MODE: {self.protobuf_parser.parsing_mode}")
        
        self.running = True
        
        # Fetch initial balances first
        self.fetch_initial_balances()
        time.sleep(2)
        
        # Create listen key
        if not self.create_listen_key():
            self.log_with_timestamp("❌ Failed to get listen key")
            return
        
        # Start keepalive thread
        self.keepalive_thread = threading.Thread(target=self.keepalive_worker)
        self.keepalive_thread.daemon = True
        self.keepalive_thread.start()
        
        # Connect to WebSocket
        self.connect_websocket()
    
    def cleanup_and_stop(self):
        """Cleanup and stop."""
        self.log_with_timestamp("🛑 STOPPING DIRECT GENERATED_PROTO MONITOR...")
        self.running = False
        self.keepalive_running = False
        
        if self.ws:
            self.log_with_timestamp("🔌 Closing WebSocket...")
            self.ws.close()
        
        if self.keepalive_thread and self.keepalive_thread.is_alive():
            self.log_with_timestamp("⏳ Waiting for keepalive thread to stop...")
            self.keepalive_thread.join(timeout=5)
        
        if self.listen_key:
            self.delete_listen_key()
        
        self.log_with_timestamp("✅ Direct generated_proto monitor stopped and cleaned up")

# ============================================================================
# TEXTUAL UI COMPONENTS - SAME AS BEFORE
# ============================================================================

class ConnectionMonitorPanel(Static):
    """Panel for displaying WebSocket connection status and debug info."""
    
    CSS = """
    ConnectionMonitorPanel {
        layout: vertical;
        height: 70%;
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
        height: 12;
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
        yield Static("WebSocket Connection Monitor - DIRECT GENERATED_PROTO VERSION", classes="connection-header")
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
            listen_key_full = conn_state.get('listen_key_full', 'None')
            listen_key_created = conn_state.get('listen_key_created_at')
            listen_key_expires = conn_state.get('listen_key_expires_at')
            last_msg_time = conn_state.get('last_message_time')
            last_key_extend = conn_state.get('last_key_extend')
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
            
            key_extend_str = "Never"
            if last_key_extend:
                key_extend_str = last_key_extend.strftime('%H:%M:%S')
            
            key_created_str = "Unknown"
            if listen_key_created:
                key_created_str = listen_key_created.strftime('%H:%M:%S')
            
            key_expires_str = "Unknown"
            if listen_key_expires:
                key_expires_str = listen_key_expires.strftime('%H:%M:%S')
            
            status_color = "green" if status == "Connected" else "red"
            mode_color = "green" if "Direct" in protobuf_mode else "red"
            
            display_key = "None"
            if listen_key_full:
                display_key = f"{listen_key_full[:12]}...{listen_key_full[-8:]}"
            
            info_text = f"""[{status_color}]Status: {status} - DIRECT GENERATED_PROTO[/{status_color}]
[{mode_color}]Parser: {protobuf_mode}[/{mode_color}]
Connected: {conn_time_str} | Reconnects: {reconnects}
Messages: {messages} (Binary: {binary_msgs}, JSON: {json_msgs})
Last Ping: {ping_time_str} | Last Message: {msg_time_str}
Key Extended: {key_extend_str}
🔑 Listen Key: {display_key}
🕐 Created: {key_created_str} | Expires: {key_expires_str}"""
            
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

class BalanceMonitorPanel(Static):
    """Panel for displaying balances."""
    
    CSS = """
    BalanceMonitorPanel {
        layout: vertical;
        height: 30%;
        background: #1a1a1a;
        border: solid #3a96dd;
    }

    DataTable {
        width: 100%;
        height: 1fr;
        background: #1a1a1a;
    }

    .balance-header {
        background: #1a1a1a;
        color: #3a96dd;
        padding: 1;
        text-align: center;
        font-weight: bold;
        height: 3;
    }
    """
    
    def __init__(self):
        super().__init__()
    
    def compose(self) -> ComposeResult:
        """Create the panel layout."""
        global selected_coin
        header_text = f"Account Balances - DIRECT GENERATED_PROTO: {', '.join(HARDCODED_COINS + [selected_coin])}"
        yield Static(header_text, classes="balance-header")
        yield DataTable(id="balance-table")
    
    def on_mount(self) -> None:
        """Initialize balance table."""
        balance_table = self.query_one("#balance-table")
        balance_table.cursor_type = "none"
        balance_table.add_columns("Asset", "Available", "Locked", "Total")

    def update_balances(self, balances: dict) -> None:
        """Update balances display."""
        if not balances:
            return
            
        try:
            table = self.query_one("#balance-table")
            table.clear()
            
            global selected_coin
            coins_to_show = HARDCODED_COINS + [selected_coin]
            
            for asset in coins_to_show:
                if asset in balances:
                    amounts = balances[asset]
                    free = Decimal(amounts.get('free', '0'))
                    locked = Decimal(amounts.get('locked', '0'))
                    total = free + locked
                    
                    precision = 8
                    asset_style = "bright_yellow" if asset == selected_coin else "white"
                    
                    table.add_row(
                        Text(asset, style=asset_style),
                        Text(format_with_precision(free, precision), style="green"),
                        Text(format_with_precision(locked, precision), style="red"),
                        Text(format_with_precision(total, precision))
                    )
                else:
                    precision = 8
                    asset_style = "bright_yellow" if asset == selected_coin else "white"
                    
                    table.add_row(
                        Text(asset, style=asset_style),
                        Text("0.00000000", style="green"),
                        Text("0.00000000", style="red"),
                        Text("0.00000000")
                    )
                    
        except Exception as e:
            logging.error(f"Balance display update error: {str(e)}")

class MEXCBalanceAppDirectGeneratedProto(App):
    """Main application class - DIRECT GENERATED_PROTO VERSION."""
    
    CSS = """
    Screen {
        layout: vertical;
        background: #1a1a1a;
    }

    ConnectionMonitorPanel {
        height: 70%;
        width: 100%;
        background: #1a1a1a;
    }

    BalanceMonitorPanel {
        height: 30%;
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

    Static.connection-header, Static.balance-header {
        background: #1a1a1a;
        padding: 1;
        height: 3;
    }

    Static.connection-info {
        background: #1a1a1a;
        color: white;
        padding: 1;
        height: 12;
    }
    """

    def __init__(self):
        super().__init__()
        logging.info("MEXCBalanceAppDirectGeneratedProto initialized")

    def compose(self) -> ComposeResult:
        """Create main layout."""
        yield ConnectionMonitorPanel()
        yield BalanceMonitorPanel()

    def on_mount(self) -> None:
        """Setup display updates."""
        try:
            self.set_interval(0.05, self.update_displays)
            logging.info("Direct generated_proto balance monitor mounted successfully")
        except Exception as e:
            logging.error(f"Failed to mount application: {str(e)}", exc_info=True)

    def update_displays(self) -> None:
        """Update both connection and balance displays."""
        try:
            if not connection_queue.empty():
                conn_state = connection_queue.get_nowait()
                if conn_state:
                    try:
                        conn_panel = self.query_one(ConnectionMonitorPanel)
                        if conn_panel:
                            conn_panel.update_connection_info(conn_state)
                    except NoMatches:
                        pass
            
            if not debug_queue.empty():
                debug_msg = debug_queue.get_nowait()
                if debug_msg:
                    try:
                        conn_panel = self.query_one(ConnectionMonitorPanel)
                        if conn_panel:
                            conn_panel.add_debug_message(debug_msg['message'], debug_msg['type'])
                    except NoMatches:
                        pass
            
            if not balances_queue.empty():
                balances = balances_queue.get_nowait()
                if balances:
                    try:
                        balances_panel = self.query_one(BalanceMonitorPanel)
                        if balances_panel:
                            balances_panel.update_balances(balances)
                    except NoMatches:
                        pass

        except Exception as e:
            logging.error(f"Display update error: {str(e)}", exc_info=True)

# ============================================================================
# MAIN PROGRAM - DIRECT GENERATED_PROTO FOLDER VERSION
# ============================================================================

def main():
    """Main program entry for DIRECT GENERATED_PROTO FOLDER balance monitor."""
    global should_exit, selected_coin, global_monitor
    
    try:
        print("🔥 MEXC DIRECT GENERATED_PROTO FOLDER BALANCE MONITOR")
        print("🎯 NO FALLBACKS - STRAIGHT TO GENERATED_PROTO FOLDER")
        print("="*60)
        
        # Load protobuf modules directly
        protobuf_modules, success = load_generated_proto_protobuf()
        if not success:
            print("❌ FAILED TO LOAD PROTOBUF FROM GENERATED_PROTO FOLDER!")
            print("Make sure you have the 'generated_proto' folder with protobuf files")
            return
        
        setup_logging()
        logging.info("Starting DIRECT GENERATED_PROTO FOLDER MEXC Balance Monitor")
        
        selected_coin = get_user_coin_selection()
        
        print(f"\nStarting DIRECT GENERATED_PROTO monitor for: {HARDCODED_COINS + [selected_coin]}")
        print("Starting GUI...")
        
        set_terminal_title(f"MEXC Balance Monitor - DIRECT GENERATED_PROTO - {', '.join(HARDCODED_COINS + [selected_coin])}")
        
        api_key, api_secret = load_api_keys()
        if not api_key or not api_secret:
            print("❌ Failed to load API keys. Please check mexc_keys.json")
            return
        
        # Store monitor instance globally for cleanup
        global_monitor = MEXCBalanceMonitorDirectGeneratedProto(
            api_key=api_key,
            secret_key=api_secret,
            monitored_coins=HARDCODED_COINS + [selected_coin],
            protobuf_modules=protobuf_modules
        )
        
        monitor_thread = threading.Thread(
            target=global_monitor.start_monitoring,
            daemon=True
        )
        monitor_thread.start()
        
        app = MEXCBalanceAppDirectGeneratedProto()
        app.run()
        
    except KeyboardInterrupt:
        logging.info("Got keyboard interrupt")
        should_exit = True
    except Exception as e:
        logging.error(f"Error: {str(e)}", exc_info=True)
    finally:
        should_exit = True
        if global_monitor:
            global_monitor.cleanup_and_stop()
        logging.info("DIRECT GENERATED_PROTO balance monitor shutdown complete")

if __name__ == "__main__":
    main()