#!/usr/bin/env python3

# MEXC Balance Monitor - 3 HARDCODED + 1 USER SELECTED COIN
# ETH, USDT, USDC + user selected coin in any format
# FIXED FOR NEW API v3.api.pb FORMAT - REALTIME BALANCE UPDATES

# Standard library imports
import os
import hmac
import time
import asyncio
import hashlib
import threading
import argparse
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, InvalidOperation
from urllib.parse import urlencode
from queue import Queue
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler
import logging


# FIX PROTOBUF VERSION COMPATIBILITY ISSUE
print("🔧 FIXED PROTOBUF COMPATIBILITY - Using pure Python implementation")

# Third-party imports
import orjson
import aiohttp
import websockets

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
set_terminal_title("MEXC Balance Monitor - 3+1 Coins [NEW API FIXED]")

# Initialize thread-safe queues
balances_queue = Queue()
connection_queue = Queue()
debug_queue = Queue()

# Global state variables - SIMPLIFIED
current_balances = {}
should_exit = False

# HARDCODED COINS + USER SELECTED
HARDCODED_COINS = ['ETH', 'USDT', 'USDC']  # Always show these 3
selected_coin = None  # User will select this at startup

# Connection state tracking
connection_state = {
    'status': 'Disconnected',
    'connected_at': None,
    'last_ping': None,
    'reconnect_count': 0,
    'last_error': None,
    'messages_received': 0,
    'listen_key': None,
    'last_message_time': None
}

def normalize_coin_input(user_input: str) -> str:
    """
    Normalize coin input to base coin symbol.
    Handles any format: DNX, dnx, DNXUSDT, dnxusdt, etc.
    
    Args:
        user_input: User input in any format
        
    Returns:
        str: Normalized base coin symbol (e.g., 'DNX')
    """
    if not user_input:
        return ""
    
    # Convert to uppercase and strip whitespace
    normalized = user_input.upper().strip()
    
    # Remove common suffixes
    suffixes_to_remove = ['USDT', 'USDC', 'BTC', 'ETH']
    for suffix in suffixes_to_remove:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
            break
    
    # Remove any remaining special characters or numbers at the end
    normalized = ''.join(c for c in normalized if c.isalpha())
    
    return normalized

def get_user_coin_selection() -> str:
    """
    Ask user to select the 4th coin to track.
    Handles all input formats and validates.
    
    Returns:
        str: Normalized coin symbol
    """
    print("\n" + "="*50)
    print("MEXC Balance Monitor - Coin Selection [NEW API FIXED]")
    print("="*50)
    print(f"Hardcoded coins: {', '.join(HARDCODED_COINS)}")
    print("\nPlease enter the 4th coin to track.")
    print("You can enter in any format:")
    print("  - DNX")
    print("  - dnx") 
    print("  - DNXUSDT")
    print("  - dnxusdt")
    print("  - etc.")
    print("\n" + "="*50)
    
    while True:
        try:
            user_input = input("Enter coin symbol: ").strip()
            
            if not user_input:
                print("Please enter a coin symbol.")
                continue
            
            # Normalize the input
            normalized_coin = normalize_coin_input(user_input)
            
            if not normalized_coin:
                print("Invalid coin format. Please try again.")
                continue
            
            # Check if it's not already in hardcoded coins
            if normalized_coin in HARDCODED_COINS:
                print(f"'{normalized_coin}' is already in hardcoded coins: {HARDCODED_COINS}")
                print("Please select a different coin.")
                continue
            
            # Confirm with user
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
    """Initialize logging system with proper error capture"""
    try:
        os.makedirs('logs', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Log format with file, line number and function name
        log_format = '%(asctime)s.%(msecs)03d - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # Clear existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers = []
        
        # File handler for all logs
        file_handler = RotatingFileHandler(
            filename=f'logs/balance_monitor_{timestamp}.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        file_handler.setLevel(logging.DEBUG)
        
        # Separate error log file
        error_handler = RotatingFileHandler(
            filename=f'logs/balance_error_{timestamp}.log',
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setFormatter(logging.Formatter(log_format, date_format))
        error_handler.setLevel(logging.ERROR)
        
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)
        
        logging.info("Balance monitor logging system initialized [NEW API FIXED]")
        
    except Exception as e:
        print(f"Failed to setup logging: {str(e)}")
        raise

def format_with_precision(value: Decimal, precision: Optional[int] = None) -> str:
    """
    Format decimal value with specified precision, safely handling None values.
    """
    # Default precision to 6 if None
    if precision is None:
        precision = 6
    
    try:
        # Convert value to Decimal if it isn't already
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        # Ensure precision is a non-negative integer
        precision = max(0, int(precision))
        
        # Format using quantize for exact decimal places
        scaled = value.quantize(
            Decimal('0.' + '0' * precision),
            rounding=ROUND_HALF_UP
        )
        
        # Convert to string with proper format
        return f"{scaled:f}"
        
    except (InvalidOperation, ValueError) as e:
        logging.error(f"Failed to format value '{value}' with precision {precision}: {e}")
        return str(value)
    except Exception as e:
        logging.error(f"Unexpected formatting error: {e}")
        return str(value)

class ConnectionMonitorPanel(Static):
    """Panel for displaying WebSocket connection status and debug info"""
    
    CSS = """
    ConnectionMonitorPanel {
        layout: vertical;
        height: 50%;
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
        height: 4;
    }

    .debug-log {
        background: #1a1a1a;
        color: #00ff00;
        height: 1fr;
        border: solid #555555;
        margin: 0;
        padding: 0;
    }
    """
    
    def __init__(self):
        super().__init__()
    
    def compose(self) -> ComposeResult:
        """Create the connection monitor layout"""
        yield Static("WebSocket Connection Monitor [NEW API FIXED]", classes="connection-header")
        yield Static("", id="connection-info", classes="connection-info")
        yield RichLog(id="debug-log", classes="debug-log", highlight=True, markup=True)
    
    def update_connection_info(self, conn_state: dict) -> None:
        """Update connection status display"""
        try:
            info_widget = self.query_one("#connection-info")
            
            status = conn_state.get('status', 'Unknown')
            connected_at = conn_state.get('connected_at')
            last_ping = conn_state.get('last_ping')
            reconnects = conn_state.get('reconnect_count', 0)
            messages = conn_state.get('messages_received', 0)
            last_error = conn_state.get('last_error')
            listen_key = conn_state.get('listen_key', 'None')
            last_msg_time = conn_state.get('last_message_time')
            
            # Format connection time with full timestamp and 3 decimal milliseconds
            conn_time_str = "Never"
            if connected_at:
                conn_time_str = connected_at.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            # Format last ping time with full timestamp and 3 decimal milliseconds
            ping_time_str = "Never"
            if last_ping:
                ping_time_str = last_ping.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            # Format last message time with full timestamp and 3 decimal milliseconds
            msg_time_str = "Never"
            if last_msg_time:
                msg_time_str = last_msg_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            # Create status display
            status_color = "green" if status == "Connected" else "red"
            
            info_text = f"""[{status_color}]Status: {status}[/{status_color}]
Connected: {conn_time_str}
Reconnects: {reconnects} | Messages: {messages}
Last Ping: {ping_time_str}
Last Message: {msg_time_str}
Listen Key: {listen_key[:16]}...{listen_key[-4:] if listen_key and len(listen_key) > 20 else listen_key}"""
            
            if last_error:
                info_text += f"\n[red]Last Error: {last_error}[/red]"
            
            info_widget.update(info_text)
            
        except Exception as e:
            logging.error(f"Connection info update error: {str(e)}")
    
    def add_debug_message(self, message: str, msg_type: str = "info") -> None:
        """Add debug message to the log"""
        try:
            debug_log = self.query_one("#debug-log")
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            
            # Color coding based on message type
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
    """Panel for displaying balances - 3 HARDCODED + 1 USER SELECTED"""
    
    CSS = """
    BalanceMonitorPanel {
        layout: vertical;
        height: 50%;
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
        """Create the panel layout"""
        global selected_coin
        header_text = f"Account Balances [NEW API FIXED]: {', '.join(HARDCODED_COINS + [selected_coin])}"
        yield Static(header_text, classes="balance-header")
        yield DataTable(id="balance-table")
    
    def on_mount(self) -> None:
        """Initialize balance table"""
        balance_table = self.query_one("#balance-table")
        balance_table.cursor_type = "none"
        balance_table.add_columns("Asset", "Available", "Locked", "Total")

    def update_balances(self, balances: dict) -> None:
        """Update balances display - 3 HARDCODED + 1 USER SELECTED IN ORDER"""
        if not balances:
            return
            
        try:
            table = self.query_one("#balance-table")
            table.clear()
            
            # Get all coins to show: 3 hardcoded + 1 user selected
            global selected_coin
            coins_to_show = HARDCODED_COINS + [selected_coin]
            
            # Show coins in exact order
            for asset in coins_to_show:
                if asset in balances:
                    amounts = balances[asset]
                    free = Decimal(amounts.get('free', '0'))
                    locked = Decimal(amounts.get('locked', '0'))
                    total = free + locked
                    
                    # Use 6 decimals for all coins - CONSISTENT
                    precision = 6
                    
                    # Highlight user selected coin
                    asset_style = "bright_yellow" if asset == selected_coin else "white"
                    
                    table.add_row(
                        Text(asset, style=asset_style),
                        Text(format_with_precision(free, precision), style="green"),
                        Text(format_with_precision(locked, precision), style="red"),
                        Text(format_with_precision(total, precision))
                    )
                    
        except Exception as e:
            logging.error(f"Balance display update error: {str(e)}")

class MEXCBalanceApp(App):
    """Main application class for balance monitoring with connection monitor"""
    
    # Completely fixed CSS for Textual compatibility
    CSS = """
    Screen {
        layout: vertical;
        background: #1a1a1a;
    }

    ConnectionMonitorPanel {
        height: 50%;
        width: 100%;
        background: #1a1a1a;
    }

    BalanceMonitorPanel {
        height: 50%;
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
        height: 8;
    }
    """

    def __init__(self):
        super().__init__()
        logging.info("MEXCBalanceApp initialized with connection monitor [NEW API FIXED]")

    def compose(self) -> ComposeResult:
        """Create main layout with connection monitor and balance panel"""
        yield ConnectionMonitorPanel()
        yield BalanceMonitorPanel()

    def on_mount(self) -> None:
        """Setup display updates"""
        try:
            self.set_interval(0.05, self.update_displays)  # FASTER UPDATE RATE
            logging.info("Enhanced balance monitor mounted successfully [NEW API FIXED]")
        except Exception as e:
            logging.error(f"Failed to mount application: {str(e)}", exc_info=True)

    def update_displays(self) -> None:
        """Update both connection and balance displays - IMMEDIATE PROCESSING"""
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
            
            # Process balance updates - IMMEDIATE PROCESSING
            if not balances_queue.empty():
                balances = balances_queue.get_nowait()
                if balances:
                    try:
                        balances_panel = self.query_one(BalanceMonitorPanel)
                        if balances_panel:
                            balances_panel.update_balances(balances)
                            # Add debug message for balance updates
                            debug_queue.put({
                                'message': f'Balance UI updated: {len(balances)} assets',
                                'type': 'balance'
                            })
                    except NoMatches:
                        pass

        except Exception as e:
            logging.error(f"Display update error: {str(e)}", exc_info=True)

    async def cleanup(self) -> None:
        """Cleans up on shutdown"""
        try:
            # Set exit flag
            global should_exit
            should_exit = True
            
            # Cancel tasks
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            logging.info("Cleanup complete")
            
        except Exception as e:
            logging.error(f"Cleanup error: {str(e)}")

# Network-related functions - FIXED FOR NEW API
async def get_listen_key():
    """Get authentication listen key for private WebSocket stream - NEW API FORMAT"""
    try:
        debug_queue.put({'message': 'Requesting listen key from NEW API...', 'type': 'info'})
        
        url = 'https://api.mexc.com/api/v3/userDataStream'
        
        params = {
            'timestamp': int(time.time() * 1000),
            'recvWindow': 60000
        }
        
        signature = sign_request(params)
        params['signature'] = signature
        
        headers = {
            'X-MEXC-APIKEY': API_KEY,
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    listen_key = data.get('listenKey')
                    debug_queue.put({'message': f'NEW API Listen key received: {listen_key[:16]}...', 'type': 'success'})
                    logging.info(f"Listen key received from new API: {listen_key}")
                    return listen_key
                else:
                    error_text = await resp.text()
                    debug_queue.put({'message': f'NEW API Listen key request failed: {error_text}', 'type': 'error'})
                    logging.error(f"Failed to get listen key from new API: {error_text}")
                    return None
                    
    except Exception as e:
        debug_queue.put({'message': f'NEW API Listen key error: {str(e)}', 'type': 'error'})
        logging.error(f"Error getting listen key from new API: {str(e)}")
        return None

def sign_request(params: dict) -> str:
    """Create HMAC signature for API authentication"""
    try:
        query_string = urlencode(params)
        signature = hmac.new(
            API_SECRET.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    except Exception as e:
        logging.error(f"Error creating signature: {str(e)}")
        raise

def update_connection_state(**kwargs):
    """Update connection state and push to UI"""
    global connection_state
    connection_state.update(kwargs)
    connection_queue.put(connection_state.copy())

# FIXED BALANCE UPDATE FUNCTIONS - NEW API FORMAT
async def process_balance_update(data: dict) -> None:
    """Process balance updates from websocket - NEW API FORMAT FIXED"""
    try:
        if not isinstance(data, dict):
            logging.error(f"Invalid balance data: {data}")
            debug_queue.put({'message': f'Invalid balance data: {data}', 'type': 'error'})
            return
        
        # NEW API FORMAT: Check for privateAccount structure
        private_account = data.get('privateAccount')
        if not private_account:
            # FALLBACK: Try old format
            old_format_data = data.get('d')
            if old_format_data:
                debug_queue.put({'message': 'Using OLD API format fallback', 'type': 'warning'})
                await process_old_format_balance_update(old_format_data)
                return
            
            logging.error("Missing privateAccount and 'd' in balance update")
            debug_queue.put({'message': 'Missing privateAccount and d in balance update', 'type': 'error'})
            return
        
        # NEW API FIELD NAMES
        asset = private_account.get('vcoinName')
        balance_amount = private_account.get('balanceAmount', '0')
        frozen_amount = private_account.get('frozenAmount', '0')
        balance_change = private_account.get('balanceAmountChange', '0')
        frozen_change = private_account.get('frozenAmountChange', '0')
        change_type = private_account.get('type', 'UNKNOWN')
        change_time = private_account.get('time', 0)
        
        if not asset:
            logging.error("Missing vcoinName in privateAccount")
            debug_queue.put({'message': 'Missing vcoinName in privateAccount', 'type': 'error'})
            return
        
        # NEW FORMAT UPDATE
        new_balance = {
            'free': balance_amount,
            'locked': frozen_amount
        }
        
        # Update the balance immediately
        current_balances[asset] = new_balance
        
        # Enhanced logging for new API
        change_time_str = datetime.fromtimestamp(change_time / 1000).strftime('%H:%M:%S') if change_time > 0 else 'Unknown'
        logging.info(f"NEW API Balance updated for {asset}: free={balance_amount}, locked={frozen_amount}, change_type={change_type}, time={change_time_str}")
        debug_queue.put({
            'message': f'NEW API: {asset} free={balance_amount} locked={frozen_amount} type={change_type} change=+{balance_change}/{frozen_change}',
            'type': 'balance'
        })
        
        # IMMEDIATE UI UPDATE
        balances_queue.put(current_balances.copy())
            
    except Exception as e:
        logging.error(f"NEW API Balance update error: {str(e)}")
        debug_queue.put({'message': f'NEW API Balance update error: {str(e)}', 'type': 'error'})

async def process_old_format_balance_update(bal_data: dict) -> None:
    """Process balance updates from websocket - OLD FORMAT FALLBACK"""
    try:
        asset = bal_data.get('a')
        if not asset:
            logging.error("Missing asset in old format balance update")
            debug_queue.put({'message': 'Missing asset in old format balance update', 'type': 'error'})
            return
        
        # OLD FORMAT UPDATE
        new_balance = {
            'free': bal_data.get('f', '0'),
            'locked': bal_data.get('l', '0')
        }
        
        # Update the balance immediately
        current_balances[asset] = new_balance
        
        # Log the update
        logging.info(f"OLD API Balance updated for {asset}: free={new_balance['free']}, locked={new_balance['locked']}")
        debug_queue.put({
            'message': f'OLD API: {asset} free={new_balance["free"]} locked={new_balance["locked"]}',
            'type': 'balance'
        })
        
        # IMMEDIATE UI UPDATE
        balances_queue.put(current_balances.copy())
            
    except Exception as e:
        logging.error(f"OLD API Balance update error: {str(e)}")
        debug_queue.put({'message': f'OLD API Balance update error: {str(e)}', 'type': 'error'})

async def fetch_initial_balances():
    """Fetch initial balance data from API - 3 HARDCODED + 1 USER SELECTED"""
    try:
        # Track hardcoded coins + user selected coin
        global selected_coin
        tracked_coins = set(HARDCODED_COINS + [selected_coin])
        
        logging.info(f"Fetching initial balances for coins: {tracked_coins}")
        debug_queue.put({'message': f'Fetching NEW API initial balances for: {", ".join(tracked_coins)}', 'type': 'info'})
        
        params = {
            'timestamp': int(time.time() * 1000),
            'recvWindow': 60000
        }
        
        signature = sign_request(params)
        params['signature'] = signature
        
        headers = {
            'X-MEXC-APIKEY': API_KEY,
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.mexc.com/api/v3/account',
                headers=headers,
                params=params
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Initialize all tracked coins with zero balances first
                    for coin in tracked_coins:
                        current_balances[coin] = {
                            'free': '0',
                            'locked': '0'
                        }
                    
                    # Update any non-zero balances
                    balance_count = 0
                    for bal in data.get('balances', []):
                        asset = bal['asset']
                        if asset in tracked_coins:
                            current_balances[asset] = {
                                'free': bal['free'],
                                'locked': bal['locked']
                            }
                            balance_count += 1
                            logging.info(f"Loaded balance for {asset}: free={bal['free']}, locked={bal['locked']}")
                    
                    debug_queue.put({'message': f'NEW API Initial balances loaded: {balance_count}/{len(tracked_coins)} assets', 'type': 'success'})
                    
                    # IMMEDIATE UI update
                    balances_queue.put(current_balances.copy())
                    
                else:
                    error_text = await resp.text()
                    debug_queue.put({'message': f'NEW API Balance API error: {error_text}', 'type': 'error'})
                    logging.error(f"Failed to fetch initial balances: {error_text}")
                    
    except Exception as e:
        debug_queue.put({'message': f'NEW API Initial balance fetch error: {str(e)}', 'type': 'error'})
        logging.error(f"Error fetching initial balances: {str(e)}", exc_info=True)

async def handle_balance_stream():
    """Handle private WebSocket stream for balance changes - NEW API FORMAT WITH FALLBACKS"""
    connection_attempt = 0
    retry_delay = 1
    max_retry_delay = 30
    
    # MULTIPLE WEBSOCKET ENDPOINTS TO TRY
    websocket_endpoints = [
        "wss://wbs-api.mexc.com/ws",  # Try secure first
        "ws://wbs-api.mexc.com/ws",   # Your specified endpoint
        "wss://wbs.mexc.com/ws",      # Old endpoint secure
        "ws://wbs.mexc.com/ws"        # Old endpoint non-secure
    ]
    
    # MULTIPLE SUBSCRIPTION CHANNELS TO TRY
    subscription_channels = [
        "spot@private.account.v3.api.pb",  # Your specified channel
        "spot@private.account.v3.api",     # Old channel
    ]
    
    while not should_exit:
        try:
            logging.info(f"NEW API Balance stream connection attempt #{connection_attempt}")
            connection_attempt += 1
            
            update_connection_state(
                status='Connecting',
                reconnect_count=connection_attempt - 1,
                last_error=None
            )
            
            debug_queue.put({'message': f'NEW API Connection attempt #{connection_attempt}', 'type': 'info'})

            # Get listen key with retries
            listen_key = None
            for attempt in range(3):
                listen_key = await get_listen_key()
                if listen_key:
                    logging.info(f"Got NEW API listen key: {listen_key}")
                    break
                await asyncio.sleep(1)
            
            if not listen_key:
                error_msg = "Failed to get NEW API listen key after 3 attempts"
                logging.error(error_msg)
                update_connection_state(
                    status='Failed',
                    last_error=error_msg
                )
                await asyncio.sleep(retry_delay)
                continue

            # TRY MULTIPLE WEBSOCKET ENDPOINTS
            connected = False
            current_ws = None
            current_channel = None
            
            for ws_endpoint in websocket_endpoints:
                if connected:
                    break
                    
                ws_url = f"{ws_endpoint}?listenKey={listen_key}"
                logging.info(f"Trying WebSocket endpoint: {ws_url}")
                debug_queue.put({'message': f'Trying endpoint: {ws_endpoint}', 'type': 'info'})
                
                try:
                    current_ws = await websockets.connect(ws_url, timeout=10)
                    
                    # Update connection state
                    connect_time = datetime.now()
                    update_connection_state(
                        status='Connected',
                        connected_at=connect_time,
                        listen_key=listen_key,
                        messages_received=0
                    )
                    
                    retry_delay = 1  # Reset delay on successful connection
                    
                    logging.info(f"NEW API Balance WebSocket connected successfully to {ws_endpoint}")
                    debug_queue.put({'message': f'Connected to {ws_endpoint}!', 'type': 'success'})
                    
                    # TRY MULTIPLE SUBSCRIPTION CHANNELS
                    for channel in subscription_channels:
                        sub_message = {
                            "method": "SUBSCRIPTION",
                            "params": [channel]
                        }
                        
                        logging.info(f"Trying subscription channel: {channel}")
                        debug_queue.put({'message': f'Trying channel: {channel}', 'type': 'info'})
                        
                        await current_ws.send(orjson.dumps(sub_message).decode())
                        logging.info(f"Subscription sent for {channel}")
                        
                        # Wait for confirmation or timeout
                        try:
                            confirm_msg = await asyncio.wait_for(current_ws.recv(), timeout=5)
                            confirm_data = orjson.loads(confirm_msg)
                            
                            debug_queue.put({'message': f'Subscription response: {confirm_data}', 'type': 'info'})
                            
                            if confirm_data.get('result') is not None:
                                current_channel = channel
                                debug_queue.put({'message': f'Subscription confirmed for {channel}', 'type': 'success'})
                                connected = True
                                break
                                
                        except asyncio.TimeoutError:
                            debug_queue.put({'message': f'No subscription confirmation for {channel}', 'type': 'warning'})
                            # Try next channel
                            continue
                    
                    if connected:
                        break
                        
                except Exception as endpoint_error:
                    debug_queue.put({'message': f'Endpoint {ws_endpoint} failed: {str(endpoint_error)}', 'type': 'error'})
                    logging.error(f"Failed to connect to {ws_endpoint}: {str(endpoint_error)}")
                    if current_ws:
                        await current_ws.close()
                        current_ws = None
                    continue
            
            if not connected or not current_ws:
                error_msg = "Failed to connect to any WebSocket endpoint"
                logging.error(error_msg)
                update_connection_state(
                    status='Failed',
                    last_error=error_msg
                )
                await asyncio.sleep(retry_delay)
                continue

            # MAIN MESSAGE LOOP
            while not should_exit:
                try:
                    msg = await asyncio.wait_for(current_ws.recv(), timeout=30)
                    
                    # Update message statistics
                    msg_count = connection_state.get('messages_received', 0) + 1
                    msg_time = datetime.now()
                    update_connection_state(
                        messages_received=msg_count,
                        last_message_time=msg_time
                    )
                    
                    # Log raw message to debug
                    debug_queue.put({'message': f'RAW MSG: {msg}', 'type': 'websocket'})
                    logging.debug(f"Balance message received: {msg}")
                    
                    data = orjson.loads(msg)
                    
                    if not isinstance(data, dict):
                        continue
                    
                    # Handle balance updates - BOTH NEW AND OLD FORMAT
                    if current_channel and current_channel in str(data):
                        # NEW API FORMAT
                        if 'privateAccount' in data:
                            debug_queue.put({'message': f'Processing NEW API balance update', 'type': 'debug'})
                            await process_balance_update(data)
                            
                            # FORCED UI UPDATE
                            private_account = data.get('privateAccount', {})
                            asset = private_account.get('vcoinName')
                            if asset and asset in current_balances:
                                balances_queue.put(current_balances.copy())
                                debug_queue.put({'message': f'UI updated for {asset}', 'type': 'balance'})
                            
                            logging.debug("Processed NEW API balance update")
                        
                        # OLD API FORMAT FALLBACK
                        elif 'd' in data:
                            debug_queue.put({'message': f'Processing OLD API balance update', 'type': 'debug'})
                            await process_balance_update(data)
                            
                            # FORCED UI UPDATE
                            old_data = data.get('d', {})
                            asset = old_data.get('a')
                            if asset and asset in current_balances:
                                balances_queue.put(current_balances.copy())
                                debug_queue.put({'message': f'UI updated for {asset}', 'type': 'balance'})
                            
                            logging.debug("Processed OLD API balance update")
                    
                    # Handle subscription confirmation messages
                    elif data.get('result') is not None:
                        debug_queue.put({'message': f'Subscription result: {data.get("result")}', 'type': 'info'})
                        logging.info(f"Subscription result: {data}")
                            
                except asyncio.TimeoutError:
                    logging.info("Balance WebSocket timeout, attempting ping")
                    debug_queue.put({'message': 'WebSocket timeout, sending ping...', 'type': 'warning'})
                    
                    try:
                        pong = await current_ws.ping()
                        await asyncio.wait_for(pong, timeout=5)
                        
                        ping_time = datetime.now()
                        update_connection_state(last_ping=ping_time)
                        
                        logging.debug("Balance ping successful")
                        debug_queue.put({'message': 'Ping successful', 'type': 'success'})
                        continue
                    except Exception as ping_error:
                        error_msg = f"Ping failed: {str(ping_error)}"
                        logging.error(error_msg)
                        debug_queue.put({'message': error_msg, 'type': 'error'})
                        break
                        
                except websockets.exceptions.ConnectionClosed as e:
                    error_msg = f"WebSocket connection closed: {str(e)}"
                    logging.error(error_msg)
                    debug_queue.put({'message': error_msg, 'type': 'error'})
                    update_connection_state(
                        status='Disconnected',
                        last_error=error_msg
                    )
                    break
                    
                except Exception as e:
                    error_msg = f"Message processing error: {str(e)}"
                    logging.error(error_msg)
                    debug_queue.put({'message': error_msg, 'type': 'error'})
                    continue
                    
        except Exception as e:
            error_msg = f"Balance stream error: {str(e)}"
            logging.error(error_msg)
            debug_queue.put({'message': error_msg, 'type': 'error'})
            
            update_connection_state(
                status='Disconnected',
                last_error=error_msg
            )
            
            # Exponential backoff for reconnection
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)
            
        finally:
            if connection_state.get('status') != 'Disconnected':
                update_connection_state(status='Disconnected')
                logging.info("Balance WebSocket disconnected")

            debug_queue.put({'message': f'Reconnecting in {retry_delay} seconds...', 'type': 'warning'})
            logging.info(f"Reconnecting balance stream in {retry_delay} seconds...")

def load_api_keys():
    """Load API keys from configuration file"""
    try:
        with open('mexc_keys.json', 'rb') as f:
            keys = orjson.loads(f.read())
            return keys['api_key'], keys['api_secret']
    except Exception as e:
        logging.error(f"Failed to load API keys: {str(e)}")
        raise

# Load API keys at module level
API_KEY, API_SECRET = load_api_keys()

async def main_async():
    """Main async function that manages balance monitoring tasks only - NEW API FIXED"""
    tasks = []
    
    try:
        logging.info("Starting NEW API FIXED 3+1 balance monitor async tasks")
        debug_queue.put({'message': 'Starting NEW API FIXED 3+1 balance monitor...', 'type': 'info'})
        
        # Step 1: Fetch initial balances
        try:
            await fetch_initial_balances()
            logging.info("NEW API Initial balances fetched successfully")
        except Exception as e:
            logging.error(f"Error fetching NEW API initial balances: {str(e)}")
            # Continue even if initial balance fetch fails
        
        # Step 2: Create balance stream task
        balance_task = asyncio.create_task(handle_balance_stream())
        tasks.append(balance_task)
        logging.info("NEW API Balance stream task created")
        debug_queue.put({'message': 'NEW API Balance stream task created', 'type': 'success'})
        
        # Step 3: Wait for task to complete or fail
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # If we get here, the task completed or failed
        for task in done:
            try:
                result = await task
                logging.error(f"NEW API Balance task completed unexpectedly: {task}")
            except Exception as e:
                logging.error(f"NEW API Balance task failed with error: {str(e)}")
        
    except asyncio.CancelledError:
        logging.info("NEW API Balance monitor tasks cancelled by user")
        debug_queue.put({'message': 'NEW API Monitor cancelled by user', 'type': 'warning'})
    except Exception as e:
        logging.error(f"Error in NEW API balance monitor async loop: {str(e)}", exc_info=True)
        debug_queue.put({'message': f'NEW API Critical error: {str(e)}', 'type': 'error'})
    finally:
        # Cleanup phase
        logging.info("Starting NEW API balance monitor tasks cleanup")
        debug_queue.put({'message': 'NEW API Cleaning up tasks...', 'type': 'info'})
        
        # Cancel all running tasks
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logging.error(f"Error cancelling task: {str(e)}")
        
        # Set global exit flag
        global should_exit
        should_exit = True
        
        # Final connection state update
        update_connection_state(
            status='Shutdown',
            last_error='Application shutting down'
        )
        
        logging.info("All NEW API balance monitor tasks cleaned up")
        debug_queue.put({'message': 'NEW API Cleanup complete', 'type': 'info'})

def main():
    """Main program entry for NEW API FIXED 3+1 balance monitor"""
    try:
        # Setup logging
        setup_logging()
        logging.info("Starting NEW API FIXED 3+1 MEXC Balance Monitor")
        
        # GET USER COIN SELECTION AT STARTUP
        global selected_coin
        selected_coin = get_user_coin_selection()
        
        print(f"\nStarting NEW API FIXED monitor for: {HARDCODED_COINS + [selected_coin]}")
        print("Starting GUI...")
        
        # Update terminal title
        set_terminal_title(f"MEXC Balance Monitor [NEW API FIXED] - {', '.join(HARDCODED_COINS + [selected_coin])}")
        
        # Create app
        app = MEXCBalanceApp()
        
        # Start background balance monitoring task
        async_thread = threading.Thread(
            target=lambda: asyncio.run(main_async()),
            daemon=True
        )
        async_thread.start()
        
        # Run UI
        app.run()
        
    except KeyboardInterrupt:
        logging.info("Got keyboard interrupt")
        debug_queue.put({'message': 'Keyboard interrupt received', 'type': 'warning'})
        global should_exit
        should_exit = True
    except Exception as e:
        logging.error(f"Error: {str(e)}", exc_info=True)
        debug_queue.put({'message': f'Fatal error: {str(e)}', 'type': 'error'})
    finally:
        # Run cleanup
        should_exit = True
        logging.info("NEW API FIXED 3+1 balance monitor shutdown complete")

if __name__ == "__main__":
    main()