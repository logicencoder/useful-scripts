#!/usr/bin/env python3
"""
SYSTEM DIAGNOSTIC SCRIPT - CHECK ONLY, NO CHANGES!
Run this on both WSL2 and server to compare environments
"""

import os
import sys
import platform
import subprocess
import importlib
import traceback
from pathlib import Path

print("🔍 SYSTEM DIAGNOSTIC SCRIPT - CHECK ONLY MODE")
print("=" * 60)
print("This script will NOT change anything, only check!")
print("=" * 60)

def run_command(cmd):
    """Run command and return output safely"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), -1

def check_file_exists(filepath):
    """Check if file exists and get info"""
    try:
        path = Path(filepath)
        if path.exists():
            if path.is_file():
                size = path.stat().st_size
                return f"EXISTS (file, {size} bytes)"
            elif path.is_dir():
                try:
                    contents = list(path.iterdir())
                    return f"EXISTS (directory, {len(contents)} items)"
                except:
                    return "EXISTS (directory, cannot list)"
            else:
                return "EXISTS (other type)"
        else:
            return "NOT FOUND"
    except Exception as e:
        return f"ERROR: {e}"

def check_import(module_name):
    """Try to import a module and get version if possible"""
    try:
        module = importlib.import_module(module_name)
        version = "unknown"
        
        # Try different ways to get version
        if hasattr(module, '__version__'):
            version = module.__version__
        elif hasattr(module, 'version'):
            version = module.version
        elif hasattr(module, 'VERSION'):
            version = module.VERSION
            
        return f"✅ IMPORTED (version: {version})"
    except ImportError as e:
        return f"❌ IMPORT FAILED: {e}"
    except Exception as e:
        return f"❌ ERROR: {e}"

# ==============================================================================
# 1. SYSTEM INFORMATION
# ==============================================================================
print("\n1️⃣ SYSTEM INFORMATION")
print("-" * 30)

print(f"Platform: {platform.platform()}")
print(f"System: {platform.system()}")
print(f"Release: {platform.release()}")
print(f"Architecture: {platform.architecture()}")
print(f"Machine: {platform.machine()}")
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")

# Check if running in WSL
wsl_check = check_file_exists("/proc/version")
if "EXISTS" in wsl_check:
    try:
        with open("/proc/version", "r") as f:
            version_info = f.read().strip()
            if "microsoft" in version_info.lower() or "wsl" in version_info.lower():
                print("🐧 Running in WSL: YES")
            else:
                print("🐧 Running in WSL: NO (native Linux)")
    except:
        print("🐧 Running in WSL: UNKNOWN")
else:
    print("🐧 Running in WSL: NO (not Linux)")

# ==============================================================================
# 2. PYTHON PACKAGE VERSIONS
# ==============================================================================
print("\n2️⃣ PYTHON PACKAGE VERSIONS")
print("-" * 30)

packages_to_check = [
    'protobuf',
    'google.protobuf', 
    'orjson',
    'textual',
    'rich',
    'websocket',
    'websocket-client',
    'requests',
    'logging'
]

for package in packages_to_check:
    result = check_import(package)
    print(f"{package:20}: {result}")

# Special protobuf version check
try:
    import google.protobuf
    print(f"google.protobuf.__version__: {google.protobuf.__version__}")
except:
    print("google.protobuf.__version__: CANNOT ACCESS")

# ==============================================================================
# 3. ENVIRONMENT VARIABLES
# ==============================================================================
print("\n3️⃣ ENVIRONMENT VARIABLES")
print("-" * 30)

env_vars_to_check = [
    'PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION',
    'PYTHONPATH',
    'PATH',
    'PYTHONWARNINGS',
    'VIRTUAL_ENV',
    'CONDA_DEFAULT_ENV'
]

for env_var in env_vars_to_check:
    value = os.environ.get(env_var, "NOT SET")
    print(f"{env_var}: {value}")

# ==============================================================================
# 4. COMMAND LINE TOOLS
# ==============================================================================
print("\n4️⃣ COMMAND LINE TOOLS")
print("-" * 30)

commands_to_check = [
    'python3 --version',
    'pip3 --version',
    'protoc --version',
    'which python3',
    'which pip3', 
    'which protoc'
]

for cmd in commands_to_check:
    stdout, stderr, returncode = run_command(cmd)
    status = "✅ OK" if returncode == 0 else "❌ FAILED"
    print(f"{cmd:20}: {status}")
    if stdout:
        print(f"    Output: {stdout}")
    if stderr and returncode != 0:
        print(f"    Error: {stderr}")

# ==============================================================================
# 5. PIP PACKAGE DETAILS
# ==============================================================================
print("\n5️⃣ PIP PACKAGE DETAILS")
print("-" * 30)

pip_packages = ['protobuf', 'orjson', 'textual', 'rich', 'websocket-client', 'requests']

for package in pip_packages:
    stdout, stderr, returncode = run_command(f"pip3 show {package}")
    if returncode == 0 and stdout:
        lines = stdout.split('\n')
        for line in lines:
            if line.startswith(('Name:', 'Version:', 'Location:')):
                print(f"  {package}: {line}")
    else:
        print(f"  {package}: NOT INSTALLED or ERROR")

# ==============================================================================
# 6. FILE SYSTEM CHECKS
# ==============================================================================
print("\n6️⃣ FILE SYSTEM CHECKS")  
print("-" * 30)

current_dir = os.getcwd()
print(f"Current directory: {current_dir}")

files_to_check = [
    'generated_proto',
    'generated_proto/PushDataV3ApiWrapper_pb2.py',
    'generated_proto/PublicLimitDepthsV3Api_pb2.py', 
    'generated_proto/PublicAggreDepthsV3Api_pb2.py',
    'config/mexc_keys.json',
    'orderbook_logs'
]

for filepath in files_to_check:
    status = check_file_exists(filepath)
    print(f"{filepath:40}: {status}")

# Check generated_proto contents in detail
if os.path.exists('generated_proto'):
    print("\ngenerated_proto folder contents:")
    try:
        for item in os.listdir('generated_proto'):
            item_path = os.path.join('generated_proto', item)
            if os.path.isfile(item_path):
                size = os.path.getsize(item_path)
                print(f"  {item:30}: {size} bytes")
            else:
                print(f"  {item:30}: (directory)")
    except Exception as e:
        print(f"  ERROR listing contents: {e}")

# ==============================================================================
# 7. PROTOBUF IMPORT TEST
# ==============================================================================
print("\n7️⃣ PROTOBUF IMPORT TEST")
print("-" * 30)

# Test without setting environment variable first
print("Testing WITHOUT environment variable:")
try:
    # Add generated_proto to path temporarily  
    if 'generated_proto' not in sys.path:
        sys.path.insert(0, 'generated_proto')
    
    import PushDataV3ApiWrapper_pb2
    print("  ✅ PushDataV3ApiWrapper_pb2: SUCCESS")
except Exception as e:
    print(f"  ❌ PushDataV3ApiWrapper_pb2: FAILED - {e}")

try:
    import PublicLimitDepthsV3Api_pb2
    print("  ✅ PublicLimitDepthsV3Api_pb2: SUCCESS") 
except Exception as e:
    print(f"  ❌ PublicLimitDepthsV3Api_pb2: FAILED - {e}")

try:
    import PublicAggreDepthsV3Api_pb2
    print("  ✅ PublicAggreDepthsV3Api_pb2: SUCCESS")
except Exception as e:
    print(f"  ❌ PublicAggreDepthsV3Api_pb2: FAILED - {e}")

# Test WITH environment variable
print("\nTesting WITH PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python:")
old_env = os.environ.get('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION')
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

try:
    # Clear import cache
    if 'PushDataV3ApiWrapper_pb2' in sys.modules:
        del sys.modules['PushDataV3ApiWrapper_pb2']
    if 'PublicLimitDepthsV3Api_pb2' in sys.modules:
        del sys.modules['PublicLimitDepthsV3Api_pb2']  
    if 'PublicAggreDepthsV3Api_pb2' in sys.modules:
        del sys.modules['PublicAggreDepthsV3Api_pb2']
    
    import PushDataV3ApiWrapper_pb2
    print("  ✅ PushDataV3ApiWrapper_pb2: SUCCESS")
except Exception as e:
    print(f"  ❌ PushDataV3ApiWrapper_pb2: FAILED - {e}")

try:
    import PublicLimitDepthsV3Api_pb2
    print("  ✅ PublicLimitDepthsV3Api_pb2: SUCCESS")
except Exception as e:
    print(f"  ❌ PublicLimitDepthsV3Api_pb2: FAILED - {e}")

try:
    import PublicAggreDepthsV3Api_pb2  
    print("  ✅ PublicAggreDepthsV3Api_pb2: SUCCESS")
except Exception as e:
    print(f"  ❌ PublicAggreDepthsV3Api_pb2: FAILED - {e}")

# Restore environment variable
if old_env is None:
    os.environ.pop('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', None)
else:
    os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = old_env

# ==============================================================================
# 8. PROTOBUF FILE INSPECTION
# ==============================================================================
print("\n8️⃣ PROTOBUF FILE INSPECTION")
print("-" * 30)

pb2_files = [
    'generated_proto/PushDataV3ApiWrapper_pb2.py',
    'generated_proto/PublicLimitDepthsV3Api_pb2.py',
    'generated_proto/PublicAggreDepthsV3Api_pb2.py'
]

for pb2_file in pb2_files:
    if os.path.exists(pb2_file):
        print(f"\n{pb2_file}:")
        try:
            with open(pb2_file, 'r') as f:
                lines = f.readlines()
                print(f"  Lines: {len(lines)}")
                
                # Look for key indicators
                for i, line in enumerate(lines[:20]):  # Check first 20 lines
                    line = line.strip()
                    if 'DESCRIPTOR' in line or 'protoc' in line or '_pb2' in line:
                        print(f"  Line {i+1}: {line}")
                        
        except Exception as e:
            print(f"  ERROR reading file: {e}")
    else:
        print(f"\n{pb2_file}: NOT FOUND")

# ==============================================================================
# SUMMARY
# ==============================================================================
print("\n" + "=" * 60)
print("🏁 DIAGNOSTIC COMPLETE")
print("=" * 60)
print("Copy this entire output and compare between WSL2 and server!")
print("Look for differences in:")
print("- Python/protobuf versions")  
print("- Environment variables")
print("- File existence and sizes")
print("- Import test results")
print("=" * 60)
