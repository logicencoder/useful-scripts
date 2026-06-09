import hashlib
import hmac
import time
import json
import requests
import os


# FIX PROTOBUF VERSION COMPATIBILITY ISSUE
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'
print("🔧 FIXED PROTOBUF COMPATIBILITY - Using pure Python implementation")

class MEXCKeyChecker:
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://api.mexc.com"
        
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
        return signature
    
    def get_timestamp(self):
        """Get current timestamp in milliseconds"""
        return int(time.time() * 1000)
    
    def get_valid_listen_keys(self):
        """Get all valid listen keys"""
        print("\n🔍 CHECKING ACTIVE LISTEN KEYS...")
        print("="*60)
        
        timestamp = self.get_timestamp()
        params = f"timestamp={timestamp}"
        signature = self.generate_signature(params)
        
        url = f"{self.base_url}/api/v3/userDataStream?{params}&signature={signature}"
        headers = {
            'X-MEXC-APIKEY': self.api_key
        }
        
        print(f"📤 REQUEST:")
        print(f"   URL: {url}")
        print(f"   API Key: {self.mask_key(self.api_key)}")
        print()
        
        try:
            response = requests.get(url, headers=headers)
            
            print(f"📥 RESPONSE:")
            print(f"   Status: {response.status_code}")
            print(f"   Raw: {response.text}")
            print()
            
            if response.status_code == 200:
                result = response.json()
                listen_keys = result.get('listenKey', [])
                
                print(f"✅ SUCCESS!")
                print(f"📊 ACTIVE LISTEN KEYS: {len(listen_keys)}/60 (max)")
                print(f"🆓 AVAILABLE SLOTS: {60 - len(listen_keys)}")
                print()
                
                if listen_keys:
                    print("📝 YOUR ACTIVE KEYS:")
                    for i, key in enumerate(listen_keys, 1):
                        print(f"   {i:2d}. {key}")
                else:
                    print("✨ No active listen keys found")
                
                print("="*60)
                return listen_keys
            else:
                print(f"❌ Failed to get listen keys: {response.status_code} - {response.text}")
                print("="*60)
                return []
        except Exception as e:
            print(f"❌ Error: {e}")
            print("="*60)
            return []
    
    def close_listen_key(self, listen_key):
        """Close a specific listen key"""
        timestamp = self.get_timestamp()
        params = f"listenKey={listen_key}&timestamp={timestamp}"
        signature = self.generate_signature(params)
        
        url = f"{self.base_url}/api/v3/userDataStream"
        headers = {
            'X-MEXC-APIKEY': self.api_key
        }
        data = f"{params}&signature={signature}"
        
        try:
            response = requests.delete(url, headers=headers, data=data)
            if response.status_code == 200:
                return True
            else:
                print(f"❌ Failed to close key {listen_key[:20]}...: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error closing key: {e}")
            return False
    
    def cleanup_all_keys(self):
        """Close ALL listen keys"""
        keys = self.get_valid_listen_keys()
        
        if not keys:
            print("✅ No keys to clean up")
            return True
        
        print(f"\n🗑️ CLEANING UP {len(keys)} KEYS...")
        print("="*60)
        
        success_count = 0
        for i, key in enumerate(keys, 1):
            print(f"🗑️ Closing key {i}/{len(keys)}: {key[:20]}...")
            if self.close_listen_key(key):
                success_count += 1
                print(f"   ✅ Closed")
            else:
                print(f"   ❌ Failed")
            time.sleep(0.3)  # Small delay
        
        print()
        print(f"✅ Cleanup complete: {success_count}/{len(keys)} keys closed")
        print("="*60)
        return success_count == len(keys)

def load_api_keys():
    """Load API keys from mexc_keys.json file"""
    keys_file = "mexc_keys.json"
    
    if not os.path.exists(keys_file):
        print(f"❌ ERROR: {keys_file} file not found!")
        return None, None
    
    try:
        with open(keys_file, 'r') as f:
            keys = json.load(f)
        
        api_key = keys.get('api_key')
        api_secret = keys.get('api_secret')
        
        if not api_key or not api_secret:
            print("❌ ERROR: api_key or api_secret missing")
            return None, None
        
        return api_key, api_secret
        
    except Exception as e:
        print(f"❌ ERROR loading keys: {e}")
        return None, None

def main():
    print("🔍 MEXC LISTEN KEY CHECKER")
    print("="*50)
    print("📊 Check how many listen keys you have active")
    print("🗑️ Option to clean up all keys")
    print("="*50)
    
    # Load API keys
    api_key, api_secret = load_api_keys()
    if not api_key or not api_secret:
        return
    
    checker = MEXCKeyChecker(api_key, api_secret)
    
    # Check current keys
    keys = checker.get_valid_listen_keys()
    
    # Ask if user wants to clean up
    if keys:
        print()
        while True:
            choice = input("❓ Do you want to CLEAN UP ALL these keys? (y/n): ").strip().lower()
            if choice in ['y', 'yes']:
                checker.cleanup_all_keys()
                break
            elif choice in ['n', 'no']:
                print("✅ Keeping existing keys")
                break
            else:
                print("Please enter 'y' or 'n'")

if __name__ == "__main__":
    main()