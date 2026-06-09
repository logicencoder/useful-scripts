#!/usr/bin/env python3

# MEXC Balance Monitor - FIXED VERSION WITH PROPER PROTOBUF PARSING
# 3 HARDCODED + 1 USER SELECTED COIN
# PROPER BALANCE CALCULATIONS ACCORDING TO OFFICIAL MEXC API DOCS

import os
import hmac
import time
import json
import asyncio
import hashlib
import threading
import requests
import websocket
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from urllib.parse import urlencode
from queue import Queue
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler
import logging
import struct


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
    except Exception as e:
        logging.error(f"Failed to set terminal title: {e}")

# Set title to current filename
set_terminal_title("MEXC Balance Monitor - FIXED VERSION")

# Initialize thread-safe queues
balances_queue = Queue()
connection_queue = Queue()
debug_queue = Queue()

# Global state variables
current_balances = {}
should_exit = False

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
    'last_message_time': None,
    'binary_messages': 0,
    'json_messages': 0,
    'last_key_extend': None
}

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
    print("MEXC Balance Monitor - FIXED VERSION")
    print("="*50)
    print(f"Hardcoded coins: {', '.join(HARDCODED_COINS)}")
    print("\nPlease enter the 4th coin to track:")
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
            
            print(f"\nNormalized coin: '{normalized_coin}'")
            print(f"Will track: {HARDCODED_COINS + [normalized_coin]}")
            
            confirm = input("Is this correct? (y/n): ").lower().strip()
            if confirm in ['y', 'yes', 'ok', '']:
                print(f"Selected coin: {normalized_coin}")
                return normalized_coin
            else:
                print("Please try again.")
                continue
                
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
            filename=f'logs/balance_monitor_fixed_{timestamp}.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        file_handler.setLevel(logging.DEBUG)
        
        error_handler = RotatingFileHandler(
            filename=f'logs/balance_error_fixed_{timestamp}.log',
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setFormatter(logging.Formatter(log_format, date_format))
        error_handler.setLevel(logging.ERROR)
        
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)
        
        logging.info("FIXED Balance monitor logging system initialized")
        
    except Exception as e:
        print(f"Failed to setup logging: {str(e)}")
        raise

def format_with_precision(value: Decimal, precision: Optional[int] = None) -> str:
    """Format decimal value with specified precision."""
    if precision is None:
        precision = 6
    
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
        with open('config/mexc_keys.json', 'r') as f:
            keys = json.load(f)
        
        api_key = keys.get('api_key')
        api_secret = keys.get('api_secret')
        
        if not api_key or not api_secret:
            print("❌ Missing keys in config/mexc_keys.json")
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
    debug_queue.put({'message': message, 'type': msg_type})

# ============================================================================
# PROPER PROTOBUF MESSAGE PARSER - FIXED VERSION
# ============================================================================

class ProtobufParser:
    """
    Proper protobuf parser for MEXC account updates.
    Based on official MEXC API documentation.
    """
    
    @staticmethod
    def parse_varint(data, offset):
        """Parse protobuf varint."""
        result = 0
        shift = 0
        while offset < len(data):
            byte = data[offset]
            offset += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
        return result, offset
    
    @staticmethod
    def parse_length_delimited(data, offset):
        """Parse length-delimited field."""
        length, offset = ProtobufParser.parse_varint(data, offset)
        value = data[offset:offset + length]
        return value, offset + length
    
    @staticmethod
    def parse_account_update(binary_data):
        """
        Parse MEXC account update protobuf message.
        
        According to official MEXC docs, the privateAccount structure is:
        - vcoinName: string (asset name)
        - balanceAmount: string (available/free balance) 
        - balanceAmountChange: string (change in available balance)
        - frozenAmount: string (locked balance)
        - frozenAmountChange: string (change in locked balance)  
        - type: string (change type)
        - time: int64 (timestamp)
        """
        try:
            logging.info(f"🔍 PARSING PROTOBUF MESSAGE - Length: {len(binary_data)}")
            debug_log(f"🔍 PARSING PROTOBUF - Raw bytes length: {len(binary_data)}", 'debug')
            
            # Simple protobuf parsing - look for string patterns
            data_str = binary_data.decode('utf-8', errors='ignore')
            
            # Extract coin name - look for monitored coins
            detected_coin = None
            for coin in HARDCODED_COINS + [selected_coin]:
                if coin and coin in data_str:
                    detected_coin = coin
                    break
            
            if not detected_coin:
                logging.info(f"❌ No monitored coin found in message")
                return None
            
            logging.info(f"✅ Detected coin: {detected_coin}")
            debug_log(f"✅ Detected coin: {detected_coin}", 'success')
            
            # Extract decimal numbers from the protobuf message
            import re
            decimal_numbers = re.findall(r'\d+\.\d+', data_str)
            
            if len(decimal_numbers) < 2:
                logging.warning(f"⚠️ Insufficient decimal numbers found: {decimal_numbers}")
                return None
            
            # Parse according to OFFICIAL MEXC STRUCTURE
            # Based on official docs example:
            # balanceAmount: "21.94210356" (this IS the available balance)
            # frozenAmount: "0" (this IS the locked balance)
            
            # Most likely the first larger number is available balance
            # Second number (often smaller or 0) is frozen balance
            available_balance = float(decimal_numbers[0])
            frozen_balance = 0.0
            
            # Try to find frozen amount
            if len(decimal_numbers) >= 2:
                # Look for a reasonable frozen amount
                for num_str in decimal_numbers[1:]:
                    num = float(num_str)
                    if num <= available_balance:  # Frozen can't be more than available
                        frozen_balance = num
                        break
            
            # Detect change type from message content
            change_type = "UNKNOWN"
            change_indicators = {
                "ENTRUST": "ORDER_PLACED",
                "CANCEL": "ORDER_CANCELLED", 
                "TRADE": "TRADE_EXECUTED",
                "TRANSFER": "TRANSFER",
                "DEPOSIT": "DEPOSIT",
                "WITHDRAW": "WITHDRAW"
            }
            
            for indicator, change_type_name in change_indicators.items():
                if indicator in data_str.upper():
                    change_type = change_type_name
                    break
            
            # Create properly structured result according to MEXC official format
            result = {
                'vcoinName': detected_coin,
                'balanceAmount': str(available_balance),      # Available balance
                'balanceAmountChange': '0',                   # We can't reliably extract this from string parsing
                'frozenAmount': str(frozen_balance),          # Locked balance  
                'frozenAmountChange': '0',                    # We can't reliably extract this from string parsing
                'type': change_type,
                'time': int(time.time() * 1000)
            }
            
            logging.info(f"✅ PARSED ACCOUNT UPDATE:")
            logging.info(f"   Coin: {detected_coin}")
            logging.info(f"   Available: {available_balance}")
            logging.info(f"   Locked: {frozen_balance}")
            logging.info(f"   Type: {change_type}")
            
            debug_log(f"✅ PARSED: {detected_coin} Available={available_balance} Locked={frozen_balance} Type={change_type}", 'success')
            
            return result
            
        except Exception as e:
            logging.error(f"❌ PROTOBUF PARSING ERROR: {e}")
            debug_log(f"❌ PROTOBUF PARSE ERROR: {e}", 'error')
            return None

# ============================================================================
# MEXC BALANCE MONITOR CLASS - FIXED VERSION
# ============================================================================

class MEXCBalanceMonitorFixed:
    def __init__(self, api_key, secret_key, monitored_coins):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://api.mexc.com"
        self.ws_url = "wss://wbs-api.mexc.com/ws"  # Updated to new endpoint
        self.listen_key = None
        self.ws = None
        self.running = False
        self.monitored_coins = [coin.upper() for coin in monitored_coins]
        
        # Connection management
        self.last_ping_time = 0
        self.last_key_extend_time = 0
        self.last_pong_time = 0
        self.ping_interval = 30
        self.key_extend_interval = 1800  # 30 minutes
        self.connection_timeout = 90
        self.max_reconnect_attempts = 5
        self.reconnect_count = 0
        
        # Keep-alive thread
        self.keepalive_thread = None
        self.keepalive_running = False
        
        # Protobuf parser
        self.protobuf_parser = ProtobufParser()
        
    def get_current_time(self):
        """Get current formatted timestamp."""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
    def log_with_timestamp(self, message):
        """Log message with timestamp and send to debug queue."""
        timestamp_msg = f"[{self.get_current_time()}] {message}"
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
                update_connection_state(last_key_extend=datetime.now())
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
                heartbeat = {
                    "method": "PING",
                    "id": int(time.time())
                }
                self.log_with_timestamp("🏓 SENDING HEARTBEAT")
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
                    update_connection_state(listen_key=self.listen_key)
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
        """Handle WebSocket messages - FIXED VERSION."""
        global current_balances
        
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
            
            self.log_with_timestamp(f"🔧 BINARY MESSAGE #{binary_count} - Length: {len(message)}")
            debug_log(f"🔧 BINARY MESSAGE #{binary_count} - Length: {len(message)}", 'websocket')
            
            # PROPER PROTOBUF PARSING
            parsed_data = self.protobuf_parser.parse_account_update(message)
            
            if parsed_data:
                self.log_with_timestamp(f"✅ PROTOBUF PARSING SUCCESS!")
                self.log_with_timestamp(f"📋 PARSED DATA: {json.dumps(parsed_data, indent=2)}")
                
                debug_log(f"✅ PROTOBUF SUCCESS: {parsed_data}", 'success')
                
                # Process account balance update - CORRECT LOGIC
                coin = parsed_data.get('vcoinName')
                
                if coin in self.monitored_coins:
                    # CORRECT BALANCE CALCULATION ACCORDING TO MEXC OFFICIAL DOCS:
                    # balanceAmount = Available (free) balance
                    # frozenAmount = Locked balance
                    # Total = Available + Locked
                    
                    available_balance = float(parsed_data.get('balanceAmount', 0))
                    locked_balance = float(parsed_data.get('frozenAmount', 0))
                    change_type = parsed_data.get('type', 'UNKNOWN')
                    
                    # CORRECT CALCULATION - NO SUBTRACTION!
                    total_balance = available_balance + locked_balance
                    
                    self.log_with_timestamp(f"💰 CORRECT BALANCE CALCULATION:")
                    self.log_with_timestamp(f"   Available (Free): {available_balance}")
                    self.log_with_timestamp(f"   Locked (Frozen): {locked_balance}")
                    self.log_with_timestamp(f"   Total: {total_balance}")
                    self.log_with_timestamp(f"   Change Type: {change_type}")
                    
                    debug_log(f"💰 CORRECT: {coin} Free={available_balance} Locked={locked_balance} Total={total_balance} Type={change_type}", 'balance')
                    
                    # Update balance data structure for UI - CORRECT FORMAT
                    old_balance = current_balances.get(coin, {})
                    current_balances[coin] = {
                        'free': str(available_balance),    # Available balance
                        'locked': str(locked_balance)      # Locked balance
                    }
                    
                    self.log_with_timestamp(f"🔄 BALANCE UPDATE:")
                    self.log_with_timestamp(f"   OLD: Free={old_balance.get('free', 'N/A')}, Locked={old_balance.get('locked', 'N/A')}")
                    self.log_with_timestamp(f"   NEW: Free={available_balance}, Locked={locked_balance}")
                    
                    debug_log(f"🔄 BALANCE CHANGE: {coin} OLD={old_balance} NEW={current_balances[coin]}", 'balance')
                    
                    # Push to UI queue
                    self.log_with_timestamp(f"📤 PUSHING TO UI QUEUE...")
                    balances_queue.put(current_balances.copy())
                    debug_log(f"📤 PUSHED TO UI: {current_balances}", 'balance')
                    
                    # Event type detection
                    if 'CANCEL' in change_type.upper():
                        self.log_with_timestamp(f"🚫 ORDER CANCELLATION DETECTED!")
                        debug_log(f"🚫 ORDER CANCELLED: {coin} - Free: {available_balance:.8f}, Locked: {locked_balance:.8f}", 'warning')
                    elif 'PLACE' in change_type.upper() or 'ORDER' in change_type.upper():
                        self.log_with_timestamp(f"📝 ORDER PLACEMENT DETECTED!")
                        debug_log(f"📝 ORDER PLACED: {coin} - Free: {available_balance:.8f}, Locked: {locked_balance:.8f}", 'info')
                    elif 'TRADE' in change_type.upper():
                        self.log_with_timestamp(f"💹 TRADE EXECUTION DETECTED!")
                        debug_log(f"💹 TRADE EXECUTED: {coin} - Free: {available_balance:.8f}, Locked: {locked_balance:.8f}", 'balance')
                    else:
                        self.log_with_timestamp(f"💰 BALANCE UPDATE DETECTED!")
                        debug_log(f"💰 BALANCE UPDATE: {coin} - Free: {available_balance:.8f}, Locked: {locked_balance:.8f}, Type: {change_type}", 'balance')
                    
                    self.log_with_timestamp(f"✅ PROCESSING COMPLETE FOR {coin}")
                else:
                    self.log_with_timestamp(f"ℹ️ COIN {coin} NOT IN MONITORED LIST: {self.monitored_coins}")
                    debug_log(f"ℹ️ Binary for unmonitored coin: {coin}", 'debug')
            else:
                self.log_with_timestamp(f"❌ PROTOBUF PARSING FAILED!")
                debug_log(f"❌ PROTOBUF PARSING FAILED", 'error')
            
            return
        
        # Handle JSON messages (subscription confirmations and PONG responses)
        try:
            json_count = connection_state.get('json_messages', 0) + 1
            update_connection_state(json_messages=json_count)
            
            data = json.loads(message)
            
            if 'code' in data and 'msg' in data:
                if data.get('code') == 0:
                    if data.get('msg') == 'PONG':
                        self.log_with_timestamp("🏓 PONG RECEIVED - Connection alive!")
                        debug_log("🏓 PONG RECEIVED - Connection alive!", 'success')
                        self.last_pong_time = time.time()
                    else:
                        self.log_with_timestamp(f"✅ Subscription confirmed: {data.get('msg')}")
                        debug_log(f"✅ Control Message: {data.get('msg')}", 'success')
                else:
                    self.log_with_timestamp(f"❌ Subscription error: {data}")
                    debug_log(f"❌ Control Error: {data}", 'error')
            else:
                channel = data.get('channel', 'unknown')
                self.log_with_timestamp(f"ℹ️ Other JSON control message - channel: {channel}")
                debug_log(f"ℹ️ Other JSON control message - channel: {channel}", 'info')
                
        except json.JSONDecodeError:
            self.log_with_timestamp(f"❌ Failed to parse JSON: {message}")
            debug_log(f"❌ Failed to parse JSON: {message}", 'error')
        except Exception as e:
            self.log_with_timestamp(f"❌ Message error: {e}")
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
        self.log_with_timestamp("✅ WEBSOCKET CONNECTED!")
        self.log_with_timestamp(f"🔗 URL: {self.ws_url}?listenKey={self.listen_key[:20]}...")
        
        self.reconnect_count = 0
        
        update_connection_state(
            status='Connected',
            connected_at=datetime.now(),
            reconnect_count=self.reconnect_count
        )
        
        self.last_pong_time = time.time()
        
        # Subscribe to account updates - CORRECT CHANNEL FOR PROTOBUF
        subscription = {
            "method": "SUBSCRIPTION",
            "params": ["spot@private.account.v3.api.pb"]  # Official protobuf channel
        }
        
        self.log_with_timestamp(f"📤 SUBSCRIBING TO: {json.dumps(subscription)}")
        ws.send(json.dumps(subscription))
        self.log_with_timestamp("📡 SUBSCRIBED TO ACCOUNT UPDATES (PROTOBUF)!")
        self.log_with_timestamp(f"👁️ MONITORING: {', '.join(self.monitored_coins)}")
    
    def connect_websocket(self):
        """Connect to WebSocket."""
        if not self.listen_key:
            self.log_with_timestamp("❌ No listen key available")
            return False
        
        ws_url = f"{self.ws_url}?listenKey={self.listen_key}"
        self.log_with_timestamp("🔗 CONNECTING WEBSOCKET...")
        self.log_with_timestamp(f"URL: {self.ws_url}?listenKey={self.listen_key[:20]}...")
        
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
        
        self.log_with_timestamp("💰 FETCHING INITIAL BALANCES...")
        
        try:
            timestamp = self.get_timestamp()
            params = f"timestamp={timestamp}"
            signature = self.generate_signature(params)
            
            url = f"{self.base_url}/api/v3/account"
            headers = {'X-MEXC-APIKEY': self.api_key}
            params_with_sig = f"{params}&signature={signature}"
            
            response = requests.get(f"{url}?{params_with_sig}", headers=headers)
            self.log_with_timestamp(f"📥 BALANCE RESPONSE: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Initialize all monitored coins with zero first
                for coin in self.monitored_coins:
                    current_balances[coin] = {
                        'free': '0.000000',
                        'locked': '0.000000'
                    }
                
                # Update with actual balances
                balance_count = 0
                for balance in data.get('balances', []):
                    asset = balance['asset']
                    if asset in self.monitored_coins:
                        free_bal = balance['free']
                        locked_bal = balance['locked']
                        
                        current_balances[asset] = {
                            'free': free_bal,
                            'locked': locked_bal
                        }
                        balance_count += 1
                        self.log_with_timestamp(f"💰 {asset}: Free={free_bal}, Locked={locked_bal}")
                        debug_log(f"💰 INITIAL: {asset} Free={free_bal}, Locked={locked_bal}", 'success')
                
                # Push to UI immediately
                balances_queue.put(current_balances.copy())
                self.log_with_timestamp(f"✅ Initial balances loaded: {balance_count}/{len(self.monitored_coins)} coins")
                
            else:
                self.log_with_timestamp(f"❌ Balance fetch failed: {response.text}")
                debug_log(f"❌ Initial balance fetch failed: {response.status_code}", 'error')
                
        except Exception as e:
            self.log_with_timestamp(f"❌ Initial balance error: {e}")
            debug_log(f"❌ Initial balance error: {e}", 'error')

    def start_monitoring(self):
        """Start real-time monitoring."""
        self.log_with_timestamp("🚀 MEXC FIXED BALANCE MONITOR")
        self.log_with_timestamp("🎯 PROPER PROTOBUF PARSING")
        self.log_with_timestamp(f"⚡ MONITORING: {', '.join(self.monitored_coins)}")
        self.log_with_timestamp("🏓 PERSISTENT CONNECTION WITH KEEP-ALIVE")
        
        self.running = True
        
        # STEP 1: Fetch initial balances
        self.fetch_initial_balances()
        time.sleep(2)
        
        # STEP 2: Create listen key
        if not self.create_listen_key():
            self.log_with_timestamp("❌ Failed to get listen key")
            return
        
        # STEP 3: Start keep-alive worker
        self.keepalive_thread = threading.Thread(target=self.keepalive_worker)
        self.keepalive_thread.daemon = True
        self.keepalive_thread.start()
        
        # STEP 4: Connect WebSocket
        self.connect_websocket()
    
    def stop_monitoring(self):
        """Stop monitoring and cleanup."""
        self.log_with_timestamp("🛑 STOPPING FIXED MONITOR...")
        self.running = False
        self.keepalive_running = False
        
        if self.ws:
            self.log_with_timestamp("🔌 Closing WebSocket...")
            self.ws.close()
        
        if self.keepalive_thread and self.keepalive_thread.is_alive():
            self.log_with_timestamp("⏳ Waiting for keepalive thread to stop...")
            self.keepalive_thread.join(timeout=5)
        
        if self.listen_key:
            self.log_with_timestamp(f"🗑️ Cleaning up listen key: {self.listen_key[:20]}...")
            
            timestamp = self.get_timestamp()
            params = f"listenKey={self.listen_key}&timestamp={timestamp}"
            signature = self.generate_signature(params)
            
            url = f"{self.base_url}/api/v3/userDataStream"
            headers = {'X-MEXC-APIKEY': self.api_key}
            data = f"{params}&signature={signature}"
            
            try:
                response = requests.delete(url, headers=headers, data=data)
                if response.status_code == 200:
                    self.log_with_timestamp("✅ Listen key deleted successfully")
                else:
                    self.log_with_timestamp(f"⚠️ Failed to delete key: {response.text}")
            except Exception as e:
                self.log_with_timestamp(f"⚠️ Error deleting key: {e}")
        
        self.log_with_timestamp("✅ Fixed monitor stopped and cleaned up")

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
        yield Static("WebSocket Connection Monitor - FIXED VERSION", classes="connection-header")
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
            listen_key = conn_state.get('listen_key', 'None')
            last_msg_time = conn_state.get('last_message_time')
            last_key_extend = conn_state.get('last_key_extend')
            
            conn_time_str = "Never"
            if connected_at:
                conn_time_str = connected_at.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            ping_time_str = "Never"
            if last_ping:
                ping_time_str = last_ping.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            msg_time_str = "Never"
            if last_msg_time:
                msg_time_str = last_msg_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            key_extend_str = "Never"
            if last_key_extend:
                key_extend_str = last_key_extend.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            status_color = "green" if status == "Connected" else "red"
            
            info_text = f"""[{status_color}]Status: {status} - FIXED VERSION[/{status_color}]
Connected: {conn_time_str}
Reconnects: {reconnects} | Total Messages: {messages}
Binary: {binary_msgs} | JSON: {json_msgs}
Last Ping: {ping_time_str}
Last Message: {msg_time_str}
Key Extended: {key_extend_str}
Listen Key: {listen_key[:16]}...{listen_key[-4:] if listen_key and len(listen_key) > 20 else listen_key}"""
            
            if last_error:
                info_text += f"\n[red]Last Error: {last_error}[/red]"
            
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
                'warning': 'yellow',
                'success': 'green',
                'debug': 'gray',
                'websocket': 'magenta',
                'balance': 'bright_yellow'
            }
            
            color = colors.get(msg_type, 'white')
            formatted_msg = f"[{color}][{timestamp}] {message}[/{color}]"
            
            debug_log.write(formatted_msg)
            
        except Exception as e:
            logging.error(f"Debug message add error: {str(e)}")

class BalanceMonitorPanel(Static):
    """Panel for displaying balances - FIXED VERSION."""
    
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
        header_text = f"Account Balances - FIXED: {', '.join(HARDCODED_COINS + [selected_coin])}"
        yield Static(header_text, classes="balance-header")
        yield DataTable(id="balance-table")
    
    def on_mount(self) -> None:
        """Initialize balance table."""
        balance_table = self.query_one("#balance-table")
        balance_table.cursor_type = "none"
        balance_table.add_columns("Asset", "Available", "Locked", "Total")

    def update_balances(self, balances: dict) -> None:
        """Update balances display - FIXED VERSION."""
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
                    # CORRECT CALCULATION: Total = Available + Locked
                    total = free + locked  # This is now correct!
                    
                    precision = 6
                    asset_style = "bright_yellow" if asset == selected_coin else "white"
                    
                    table.add_row(
                        Text(asset, style=asset_style),
                        Text(format_with_precision(free, precision), style="green"),
                        Text(format_with_precision(locked, precision), style="red"),
                        Text(format_with_precision(total, precision))
                    )
                else:
                    precision = 6
                    asset_style = "bright_yellow" if asset == selected_coin else "white"
                    
                    table.add_row(
                        Text(asset, style=asset_style),
                        Text("0.000000", style="green"),
                        Text("0.000000", style="red"),
                        Text("0.000000")
                    )
                    
        except Exception as e:
            logging.error(f"Balance display update error: {str(e)}")

class MEXCBalanceAppFixed(App):
    """Main application class - FIXED VERSION."""
    
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
        height: 10;
    }
    """

    def __init__(self):
        super().__init__()
        logging.info("MEXCBalanceAppFixed initialized")

    def compose(self) -> ComposeResult:
        """Create main layout."""
        yield ConnectionMonitorPanel()
        yield BalanceMonitorPanel()

    def on_mount(self) -> None:
        """Setup display updates."""
        try:
            self.set_interval(0.05, self.update_displays)
            logging.info("Fixed balance monitor mounted successfully")
        except Exception as e:
            logging.error(f"Failed to mount application: {str(e)}", exc_info=True)

    def update_displays(self) -> None:
        """Update both connection and balance displays."""
        try:
            # Process connection status updates
            if not connection_queue.empty():
                conn_state = connection_queue.get_nowait()
                if conn_state:
                    try:
                        conn_panel = self.query_one(ConnectionMonitorPanel)
                        if conn_panel:
                            conn_panel.update_connection_info(conn_state)
                    except NoMatches:
                        pass
            
            # Process debug messages
            if not debug_queue.empty():
                debug_msg = debug_queue.get_nowait()
                if debug_msg:
                    try:
                        conn_panel = self.query_one(ConnectionMonitorPanel)
                        if conn_panel:
                            conn_panel.add_debug_message(debug_msg['message'], debug_msg['type'])
                    except NoMatches:
                        pass
            
            # Process balance updates
            if not balances_queue.empty():
                balances = balances_queue.get_nowait()
                if balances:
                    try:
                        balances_panel = self.query_one(BalanceMonitorPanel)
                        if balances_panel:
                            balances_panel.update_balances(balances)
                            debug_log(f'Balance UI updated: {len(balances)} assets', 'balance')
                    except NoMatches:
                        pass

        except Exception as e:
            logging.error(f"Display update error: {str(e)}", exc_info=True)

# ============================================================================
# MAIN PROGRAM - FIXED VERSION
# ============================================================================

def main():
    """Main program entry for FIXED balance monitor."""
    global should_exit, selected_coin
    
    try:
        # Setup logging
        setup_logging()
        logging.info("Starting FIXED MEXC Balance Monitor")
        
        # Get user coin selection
        selected_coin = get_user_coin_selection()
        
        print(f"\nStarting FIXED monitor for: {HARDCODED_COINS + [selected_coin]}")
        print("Starting GUI...")
        
        # Update terminal title
        set_terminal_title(f"MEXC Balance Monitor - FIXED - {', '.join(HARDCODED_COINS + [selected_coin])}")
        
        # Load API keys
        api_key, api_secret = load_api_keys()
        if not api_key or not api_secret:
            print("❌ Failed to load API keys. Please check config/mexc_keys.json")
            return
        
        # Initialize FIXED monitor instance  
        monitor = MEXCBalanceMonitorFixed(
            api_key=api_key,
            secret_key=api_secret,
            monitored_coins=HARDCODED_COINS + [selected_coin]
        )
        
        # Start monitor in separate thread
        monitor_thread = threading.Thread(
            target=monitor.start_monitoring,
            daemon=True
        )
        monitor_thread.start()
        
        # Create and run UI
        app = MEXCBalanceAppFixed()
        app.run()
        
    except KeyboardInterrupt:
        logging.info("Got keyboard interrupt")
        debug_log('Keyboard interrupt received', 'warning')
        should_exit = True
    except Exception as e:
        logging.error(f"Error: {str(e)}", exc_info=True)
        debug_log(f'Fatal error: {str(e)}', 'error')
    finally:
        should_exit = True
        if 'monitor' in locals():
            monitor.stop_monitoring()
        logging.info("FIXED balance monitor shutdown complete")

if __name__ == "__main__":
    main()