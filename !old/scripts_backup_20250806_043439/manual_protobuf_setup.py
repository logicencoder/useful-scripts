#!/usr/bin/env python3

import os
import sys
import subprocess

def main():
    print("🔥 MEXC BALANCE MONITOR - INSTANT FIX & RUN")
    print("="*50)
    
    # FIX 1: Set the magic environment variable that solves the protobuf issue
    print("🔧 Applying protobuf compatibility fix...")
    os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'
    print("✅ Protobuf compatibility fixed!")
    
    # FIX 2: Find and run the balance monitor script
    print("🔍 Looking for balance monitor script...")
    
    script_name = 'bal_mon_mexc_V3_ok_1aaa.py'  # Your original script
    
    if os.path.exists(script_name):
        print(f"✅ Found: {script_name}")
        print("🚀 Starting balance monitor...")
        print("="*50)
        
        # Run the script with the environment fix
        env = os.environ.copy()
        env['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'
        
        subprocess.run([sys.executable, script_name], env=env)
        
    else:
        print("❌ Script not found!")
        print("📝 Available Python files:")
        for f in os.listdir('.'):
            if f.endswith('.py'):
                print(f"   - {f}")

if __name__ == "__main__":
    main()