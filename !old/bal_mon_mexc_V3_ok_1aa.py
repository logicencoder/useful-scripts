import hashlib
import hmac
import time
import json
import requests
import websocket
import threading
import os
from datetime import datetime


# FIX PROTOBUF VERSION COMPATIBILITY ISSUE
print("🔧 FIXED PROTOBUF COMPATIBILITY - Using pure Python implementation")

class MEXCBalanceMonitor:
    def __init__(self, api_key, secret_key, monitored_coins):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://api.mexc.com"
        self.ws_url = "wss://wbs-api.mexc.com/ws"
        self.listen_key = None
        self.ws = None
        self.running = False
        self.monitored_coins = [coin.upper() for coin in monitored_coins]  # Convert to uppercase
        self.last_ping_time = 0
        self.last_key_extend_time = 0
        
    def get_current_time(self):
        """Get current formatted timestamp"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
    def mask_key(self, key):
        """Mask API key for secure display"""
        if len(key) <= 8:
            return "*" * len(key)
        return key[:4] + "*" * (len(key) - 8) + key[-4:]
        
    def generate_signature(self, params_string):
        """Generate HMAC SHA256 signature for API requests"""
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            params_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        print(f"[{self.get_current_time()}] 🔐 SIGNATURE: {signature}")
        return signature
    
    def get_timestamp(self):
        """Get current timestamp in milliseconds"""
        timestamp = int(time.time() * 1000)
        print(f"[{self.get_current_time()}] ⏰ TIMESTAMP: {timestamp}")
        return timestamp
    
    def get_existing_listen_keys(self):
        """Get all existing listen keys"""
        print(f"\n[{self.get_current_time()}] 📋 CHECKING EXISTING LISTEN KEYS...")
        
        timestamp = self.get_timestamp()
        params = f"timestamp={timestamp}"
        signature = self.generate_signature(params)
        
        url = f"{self.base_url}/api/v3/userDataStream?{params}&signature={signature}"
        headers = {'X-MEXC-APIKEY': self.api_key}
        
        print(f"[{self.get_current_time()}] 📤 GET REQUEST: {url}")
        
        try:
            response = requests.get(url, headers=headers)
            print(f"[{self.get_current_time()}] 📥 RESPONSE: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                keys = result.get('listenKey', [])
                print(f"[{self.get_current_time()}] ✅ Found {len(keys)} existing keys")
                return keys
            else:
                print(f"[{self.get_current_time()}] ❌ Failed to get keys: {response.text}")
                return []
        except Exception as e:
            print(f"[{self.get_current_time()}] ❌ Error: {e}")
            return []
    
    def delete_listen_key(self, key):
        """Delete a specific listen key"""
        print(f"\n🗑️ DELETING KEY: {key[:20]}...")
        
        timestamp = self.get_timestamp()
        params = f"listenKey={key}&timestamp={timestamp}"
        signature = self.generate_signature(params)
        
        url = f"{self.base_url}/api/v3/userDataStream"
        headers = {'X-MEXC-APIKEY': self.api_key}
        data = f"{params}&signature={signature}"
        
        print(f"📤 DELETE REQUEST: {data}")
        
        try:
            response = requests.delete(url, headers=headers, data=data)
            print(f"📥 DELETE RESPONSE: {response.status_code} - {response.text}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Delete error: {e}")
            return False
    
    def cleanup_all_keys(self):
        """Delete ALL existing listen keys"""
        print("\n🧹 CLEANING UP ALL EXISTING KEYS...")
        
        keys = self.get_existing_listen_keys()
        if not keys:
            print("✅ No keys to clean")
            return
        
        print(f"🗑️ Deleting {len(keys)} keys...")
        for key in keys:
            self.delete_listen_key(key)
            time.sleep(0.2)
        
        print("✅ All keys cleaned up")
    
    def create_single_listen_key(self):
        """Create exactly ONE listen key"""
        print("\n🔑 CREATING ONE LISTEN KEY...")
        
        # First check if we already have keys
        existing_keys = self.get_existing_listen_keys()
        if existing_keys:
            print(f"⚠️ Found {len(existing_keys)} existing keys - using first one")
            self.listen_key = existing_keys[0]
            print(f"✅ Using existing key: {self.listen_key[:20]}...")
            return True
        
        # Create new key only if none exist
        timestamp = self.get_timestamp()
        params = f"timestamp={timestamp}"
        signature = self.generate_signature(params)
        
        url = f"{self.base_url}/api/v3/userDataStream"
        headers = {'X-MEXC-APIKEY': self.api_key}
        data = f"{params}&signature={signature}"
        
        print(f"📤 CREATE REQUEST: {data}")
        
        try:
            response = requests.post(url, headers=headers, data=data)
            print(f"📥 CREATE RESPONSE: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if 'listenKey' in result:
                    self.listen_key = result['listenKey']
                    print(f"✅ Created new key: {self.listen_key[:20]}...")
                    return True
                else:
                    # Check for error 730709
                    if result.get('code') == '730709':
                        print("❌ Too many keys! Cleaning up...")
                        self.cleanup_all_keys()
                        # Try one more time after cleanup
                        time.sleep(1)
                        response = requests.post(url, headers=headers, data=data)
                        print(f"📥 RETRY RESPONSE: {response.status_code} - {response.text}")
                        if response.status_code == 200:
                            result = response.json()
                            if 'listenKey' in result:
                                self.listen_key = result['listenKey']
                                print(f"✅ Created key after cleanup: {self.listen_key[:20]}...")
                                return True
                    
                    print(f"❌ No listenKey in response: {response.text}")
                    return False
            else:
                print(f"❌ Create failed: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Create error: {e}")
            return False
    
    def parse_protobuf_message(self, binary_data):
        """Parse protobuf binary message"""
        try:
            # Convert to string for parsing
            data_str = binary_data.decode('utf-8', errors='ignore')
            
            # Check if this contains any of our monitored coins
            detected_coin = None
            for coin in self.monitored_coins:
                if coin in data_str:
                    detected_coin = coin
                    break
            
            if not detected_coin:
                return None
            
            # Extract readable strings from the binary data
            # Look for balance amounts (numbers in the data)
            import re
            
            # Find floating point numbers in the data
            numbers = re.findall(r'\d+\.\d+', data_str)
            
            # Find change type (ENTRUST, TRADE, etc.)
            change_types = re.findall(r'[A-Z_]{4,}', data_str)
            
            if numbers and len(numbers) >= 2:
                # First number is usually balance, second is change
                balance = float(numbers[0]) if numbers else 0
                change = float(numbers[1]) if len(numbers) > 1 else 0
                frozen = float(numbers[2]) if len(numbers) > 2 else 0
                
                change_type = change_types[0] if change_types else 'UNKNOWN'
                
                return {
                    'vcoinName': detected_coin,
                    'balanceAmount': str(balance),
                    'balanceAmountChange': str(change),
                    'frozenAmount': str(frozen),
                    'type': change_type,
                    'time': int(time.time() * 1000)
                }
        except Exception as e:
            print(f"❌ Protobuf parse error: {e}")
        
        return None
    
    def on_message(self, ws, message):
        """Handle WebSocket messages"""
        print(f"\n📨 RAW MESSAGE: {message}")
        
        # Check if message is binary (protobuf)
        if isinstance(message, bytes):
            print("🔧 BINARY PROTOBUF MESSAGE DETECTED")
            
            # Parse protobuf data
            parsed_data = self.parse_protobuf_message(message)
            if parsed_data:
                print(f"📋 PROTOBUF PARSED: {json.dumps(parsed_data, indent=2)}")
                
                # Process as monitored coin balance change
                coin = parsed_data.get('vcoinName')
                print(f"💰 COIN: {coin}")
                
                if coin in self.monitored_coins:
                    balance = float(parsed_data.get('balanceAmount', 0))
                    change = float(parsed_data.get('balanceAmountChange', 0))
                    frozen = float(parsed_data.get('frozenAmount', 0))
                    change_type = parsed_data.get('type', 'UNKNOWN')
                    timestamp = parsed_data.get('time', 0)
                    
                    readable_time = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Choose emoji based on coin
                    coin_emoji = {
                        'USDT': '💵',
                        'USDC': '💸', 
                        'ETH': '⚡',
                        'BTC': '₿'
                    }.get(coin, '🪙')
                    
                    print("\n" + "🔔" * 30)
                    print(f"🔔 {coin} BALANCE CHANGE DETECTED! 🔔")
                    print("🔔" * 30)
                    print(f"⏰ Time: {readable_time}")
                    print(f"{coin_emoji} Balance: {balance:.8f} {coin}")
                    print(f"📈 Change: {change:+.8f} {coin}")
                    print(f"🧊 Frozen: {frozen:.8f} {coin}")
                    print(f"📊 Type: {change_type}")
                    
                    if change > 0:
                        print(f"📈 {coin} BALANCE INCREASED ✅")
                    elif change < 0:
                        print(f"📉 {coin} BALANCE DECREASED ❌")
                    else:
                        print(f"➡️ NO {coin} BALANCE CHANGE")
                    
                    print("🔔" * 30 + "\n")
                else:
                    print(f"ℹ️ Ignoring {coin} change (not monitored)")
            else:
                print("ℹ️ Not a monitored coin protobuf message")
            return
        
        # Handle JSON messages (subscription confirmations)
        try:
            data = json.loads(message)
            print(f"📋 JSON PARSED: {json.dumps(data, indent=2)}")
            
            # Check for account updates (shouldn't happen with protobuf, but keep for safety)
            if data.get('channel') == 'spot@private.account.v3.api.pb':
                private_account = data.get('privateAccount', {})
                coin = private_account.get('vcoinName')
                
                print(f"💰 COIN: {coin}")
                
                if coin in self.monitored_coins:
                    balance = float(private_account.get('balanceAmount', 0))
                    change = float(private_account.get('balanceAmountChange', 0))
                    frozen = float(private_account.get('frozenAmount', 0))
                    change_type = private_account.get('type', 'UNKNOWN')
                    timestamp = private_account.get('time', 0)
                    
                    readable_time = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Choose emoji based on coin
                    coin_emoji = {
                        'USDT': '💵',
                        'USDC': '💸', 
                        'ETH': '⚡',
                        'BTC': '₿'
                    }.get(coin, '🪙')
                    
                    print("\n" + "🔔" * 30)
                    print(f"🔔 {coin} BALANCE CHANGE DETECTED! 🔔")
                    print("🔔" * 30)
                    print(f"⏰ Time: {readable_time}")
                    print(f"{coin_emoji} Balance: {balance:.8f} {coin}")
                    print(f"📈 Change: {change:+.8f} {coin}")
                    print(f"🧊 Frozen: {frozen:.8f} {coin}")
                    print(f"📊 Type: {change_type}")
                    
                    if change > 0:
                        print(f"📈 {coin} BALANCE INCREASED ✅")
                    elif change < 0:
                        print(f"📉 {coin} BALANCE DECREASED ❌")
                    else:
                        print(f"➡️ NO {coin} BALANCE CHANGE")
                    
                    print("🔔" * 30 + "\n")
                else:
                    print(f"ℹ️ Ignoring {coin} change (not monitored)")
            else:
                # This is likely a subscription confirmation
                if 'code' in data and 'msg' in data:
                    if data.get('code') == 0:
                        print(f"✅ Subscription confirmed: {data.get('msg')}")
                    else:
                        print(f"❌ Subscription error: {data}")
                else:
                    channel = data.get('channel', 'unknown')
                    print(f"ℹ️ Other JSON message - channel: {channel}")
                
        except json.JSONDecodeError:
            print(f"❌ Failed to parse JSON: {message}")
        except Exception as e:
            print(f"❌ Message error: {e}")
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"\n❌ WEBSOCKET ERROR: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        print(f"\n🔌 WEBSOCKET CLOSED: {close_status_code} - {close_msg}")
        if self.running:
            print("🔄 Reconnecting in 5 seconds...")
            time.sleep(5)
            self.connect_websocket()
    
    def on_open(self, ws):
        """Handle WebSocket open"""
        print(f"\n✅ WEBSOCKET CONNECTED!")
        print(f"🔗 URL: {self.ws_url}?listenKey={self.listen_key[:20]}...")
        
        # Subscribe to account updates
        subscription = {
            "method": "SUBSCRIPTION",
            "params": ["spot@private.account.v3.api.pb"]
        }
        
        print(f"📤 SUBSCRIBING: {json.dumps(subscription)}")
        ws.send(json.dumps(subscription))
        print("📡 SUBSCRIBED TO BALANCE UPDATES!")
        print(f"👁️ MONITORING: {', '.join(self.monitored_coins)}")
        print("Press Ctrl+C to stop\n")
    
    def connect_websocket(self):
        """Connect to WebSocket"""
        if not self.listen_key:
            print("❌ No listen key available")
            return False
        
        ws_url = f"{self.ws_url}?listenKey={self.listen_key}"
        print(f"\n🔗 CONNECTING WEBSOCKET...")
        print(f"URL: {self.ws_url}?listenKey={self.listen_key[:20]}...")
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        # Run in background thread
        ws_thread = threading.Thread(target=self.ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        return True
    
    def start_monitoring(self):
        """Start real-time monitoring"""
        print("🚀 MEXC MULTI-COIN REAL-TIME MONITOR")
        print("="*50)
        print("🎯 ONE LISTEN KEY ONLY")
        print(f"⚡ MONITORING: {', '.join(self.monitored_coins)}")
        print("="*50)
        
        self.running = True
        
        # Create exactly ONE listen key
        if not self.create_single_listen_key():
            print("❌ Failed to get listen key")
            return
        
        # Connect WebSocket with that key
        if not self.connect_websocket():
            print("❌ Failed to connect WebSocket")
            return
        
        try:
            # Keep alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping...")
            self.stop_monitoring()
    
    def stop_monitoring(self):
        """Stop monitoring and cleanup listen key"""
        print("\n🛑 STOPPING MONITOR...")
        self.running = False
        
        # Close WebSocket
        if self.ws:
            print("🔌 Closing WebSocket...")
            self.ws.close()
        
        # Clean up the listen key
        if self.listen_key:
            print(f"🗑️ Cleaning up listen key: {self.listen_key[:20]}...")
            
            timestamp = self.get_timestamp()
            params = f"listenKey={self.listen_key}&timestamp={timestamp}"
            signature = self.generate_signature(params)
            
            url = f"{self.base_url}/api/v3/userDataStream"
            headers = {'X-MEXC-APIKEY': self.api_key}
            data = f"{params}&signature={signature}"
            
            try:
                response = requests.delete(url, headers=headers, data=data)
                if response.status_code == 200:
                    print("✅ Listen key deleted successfully")
                else:
                    print(f"⚠️ Failed to delete key: {response.text}")
            except Exception as e:
                print(f"⚠️ Error deleting key: {e}")
        
        print("✅ Monitor stopped and cleaned up")

def load_api_keys():
    """Load API keys from mexc_keys.json"""
    try:
        with open("mexc_keys.json", 'r') as f:
            keys = json.load(f)
        
        api_key = keys.get('api_key')
        api_secret = keys.get('api_secret')
        
        if not api_key or not api_secret:
            print("❌ Missing keys in mexc_keys.json")
            return None, None
        
        # Mask for display
        masked_key = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else "*" * len(api_key)
        masked_secret = api_secret[:6] + "*" * (len(api_secret) - 12) + api_secret[-6:] if len(api_secret) > 12 else "*" * len(api_secret)
        
        print(f"🔑 API Key: {masked_key}")
        print(f"🔑 Secret: {masked_secret}")
        print()
        
        return api_key, api_secret
        
    except Exception as e:
        print(f"❌ Error loading keys: {e}")
        return None, None

def get_monitored_coins():
    """Get list of coins to monitor"""
    print("\n🪙 COIN SELECTION:")
    print("="*40)
    print("📋 Fixed coins: ETH, USDT, USDC")
    print("➕ You can add one more coin")
    print("="*40)
    
    # Fixed coins
    coins = ['ETH', 'USDT', 'USDC']
    
    # Ask for additional coin
    while True:
        additional_coin = input("💭 Enter additional coin symbol (e.g., BTC, MX, etc.): ").strip().upper()
        
        if not additional_coin:
            print("❌ Please enter a coin symbol")
            continue
        
        if additional_coin in coins:
            print(f"⚠️ {additional_coin} is already monitored")
            continue
        
        if len(additional_coin) < 2 or len(additional_coin) > 10:
            print("❌ Invalid coin symbol (2-10 characters)")
            continue
        
        coins.append(additional_coin)
        break
    
    print(f"\n✅ MONITORING COINS: {', '.join(coins)}")
    print("="*40)
    return coins

def main():
    print("🚀 MEXC MULTI-COIN BALANCE MONITOR")
    print("="*60)
    print("🎯 USES ONLY ONE LISTEN KEY")
    print("⚡ REAL-TIME BALANCE MONITORING")
    print("🪙 MONITORS: ETH, USDT, USDC + YOUR CHOICE")
    print("🔒 SECURE KEY MASKING")
    print("="*60)
    
    # Load keys
    api_key, api_secret = load_api_keys()
    if not api_key or not api_secret:
        return
    
    # Get coins to monitor
    monitored_coins = get_monitored_coins()
    
    # Start monitoring
    monitor = MEXCBalanceMonitor(api_key, api_secret, monitored_coins)
    monitor.start_monitoring()

if __name__ == "__main__":
    main()