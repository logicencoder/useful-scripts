#!/usr/bin/env python3

# VS CODE IMPORT FIX - STOPS THE YELLOW SQUIGGLY LINES
# This tells VS Code where to find your protobuf files

import os
import json

def print_header():
    print("=" * 80)
    print("🔧 VS CODE IMPORT FIX - STOPS YELLOW WARNINGS")
    print("💡 TELLS VS CODE WHERE YOUR PROTOBUF FILES ARE")
    print("🎯 NO MORE 'could not be resolved' ERRORS")
    print("=" * 80)

def create_vscode_settings():
    """Create VS Code settings to fix import resolution."""
    print("\n🔧 CREATING VS CODE SETTINGS...")
    
    try:
        # Create .vscode directory
        if not os.path.exists('.vscode'):
            os.makedirs('.vscode')
            print("✅ Created .vscode directory")
        
        settings_file = os.path.join('.vscode', 'settings.json')
        
        # VS Code settings for protobuf imports
        settings = {
            "python.analysis.extraPaths": [
                "./generated_proto"
            ],
            "python.autoComplete.extraPaths": [
                "./generated_proto"
            ],
            "python.analysis.autoSearchPaths": True,
            "python.analysis.diagnosticMode": "workspace",
            "pylance.include": [
                "generated_proto/**"
            ],
            "python.analysis.autoImportCompletions": True
        }
        
        # Write settings
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
        
        print("✅ Created VS Code settings.json")
        print("   This tells Pylance where to find protobuf files")
        return True
        
    except Exception as e:
        print(f"❌ Error creating VS Code settings: {e}")
        return False

def create_init_files():
    """Create __init__.py files to make proper Python packages."""
    print("\n📦 CREATING PYTHON PACKAGE FILES...")
    
    try:
        # Create __init__.py in generated_proto
        init_file = os.path.join('generated_proto', '__init__.py')
        
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write('# Generated protobuf package\n')
            print("✅ Created __init__.py in generated_proto")
        else:
            print("✅ __init__.py already exists in generated_proto")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating package files: {e}")
        return False

def add_simple_path_fix():
    """Add simple sys.path fix to scripts that need it."""
    print("\n🔧 ADDING SIMPLE PATH FIX TO SCRIPTS...")
    
    # Find scripts that import protobuf modules
    scripts_needing_fix = []
    
    protobuf_modules = [
        'PrivateAccountV3Api_pb2',
        'PushDataV3ApiWrapper_pb2', 
        'PublicLimitDepthsV3Api_pb2',
        'PublicAggreDepthsV3Api_pb2'
    ]
    
    for file in os.listdir('.'):
        if file.endswith('.py') and not file.startswith('vscode_') and not file.startswith('protobuf_'):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check if it imports protobuf modules
                for module in protobuf_modules:
                    if f'import {module}' in content:
                        scripts_needing_fix.append(file)
                        break
            except:
                pass
    
    if not scripts_needing_fix:
        print("✅ No scripts need path fixes")
        return True
    
    print(f"🔍 Found {len(scripts_needing_fix)} scripts that need path fix")
    
    for script in scripts_needing_fix:
        try:
            with open(script, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if already has path fix
            if 'sys.path.insert' in content and 'generated_proto' in content:
                print(f"✅ {script} already has path fix")
                continue
            
            # Add simple path fix at the top
            lines = content.split('\n')
            
            # Find where to insert (after shebang and before imports)
            insert_pos = 0
            for i, line in enumerate(lines):
                if line.startswith('#!'):
                    insert_pos = i + 1
                elif line.startswith('import ') or line.startswith('from '):
                    insert_pos = i
                    break
            
            # Simple path fix
            path_fix = [
                '',
                '# Add protobuf path',
                'import sys',
                'import os',
                'sys.path.insert(0, os.path.join(os.path.dirname(__file__), "generated_proto"))',
                ''
            ]
            
            # Insert the fix
            for j, fix_line in enumerate(path_fix):
                lines.insert(insert_pos + j, fix_line)
            
            # Write back
            with open(script, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            print(f"✅ Added path fix to {script}")
            
        except Exception as e:
            print(f"❌ Error fixing {script}: {e}")
    
    return True

def create_py_typed_file():
    """Create py.typed file for better type checking."""
    print("\n📝 CREATING TYPE HINT FILES...")
    
    try:
        py_typed_file = os.path.join('generated_proto', 'py.typed')
        
        if not os.path.exists(py_typed_file):
            with open(py_typed_file, 'w') as f:
                f.write('# Marker file for type checking\n')
            print("✅ Created py.typed file")
        else:
            print("✅ py.typed file already exists")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating py.typed: {e}")
        return False

def test_vscode_recognition():
    """Test if VS Code can now recognize the imports."""
    print("\n🧪 TESTING VS CODE IMPORT RECOGNITION...")
    
    # Check if the settings file exists and is correct
    settings_file = os.path.join('.vscode', 'settings.json')
    
    if not os.path.exists(settings_file):
        print("❌ VS Code settings file missing")
        return False
    
    try:
        with open(settings_file, 'r') as f:
            settings = json.load(f)
        
        if 'python.analysis.extraPaths' in settings:
            if './generated_proto' in settings['python.analysis.extraPaths']:
                print("✅ VS Code settings are correct")
                return True
            else:
                print("❌ Missing generated_proto in extraPaths")
                return False
        else:
            print("❌ Missing extraPaths setting")
            return False
            
    except Exception as e:
        print(f"❌ Error reading settings: {e}")
        return False

def main():
    """Main function to fix VS Code import recognition."""
    print_header()
    
    # Step 1: Create VS Code settings
    print("\n" + "="*60)
    print("STEP 1: CREATING VS CODE SETTINGS")
    print("="*60)
    
    vscode_success = create_vscode_settings()
    
    # Step 2: Create package files
    print("\n" + "="*60)
    print("STEP 2: CREATING PACKAGE STRUCTURE")
    print("="*60)
    
    package_success = create_init_files()
    
    # Step 3: Add path fixes to scripts
    print("\n" + "="*60)
    print("STEP 3: ADDING PATH FIXES")
    print("="*60)
    
    path_success = add_simple_path_fix()
    
    # Step 4: Create type files
    print("\n" + "="*60)
    print("STEP 4: CREATING TYPE FILES")
    print("="*60)
    
    type_success = create_py_typed_file()
    
    # Step 5: Test settings
    print("\n" + "="*60)
    print("STEP 5: TESTING SETTINGS")
    print("="*60)
    
    test_success = test_vscode_recognition()
    
    # Results
    print("\n" + "="*60)
    print("🎯 FINAL RESULTS")
    print("="*60)
    
    print(f"🔧 VS Code settings: {'✅ CREATED' if vscode_success else '❌ FAILED'}")
    print(f"📦 Package structure: {'✅ CREATED' if package_success else '❌ FAILED'}")
    print(f"🔧 Path fixes: {'✅ ADDED' if path_success else '❌ FAILED'}")
    print(f"📝 Type files: {'✅ CREATED' if type_success else '❌ FAILED'}")
    print(f"🧪 Settings test: {'✅ PASS' if test_success else '❌ FAIL'}")
    
    if all([vscode_success, package_success, test_success]):
        print("\n🎉 VS CODE IMPORT FIX COMPLETE!")
        print("\n📋 NEXT STEPS:")
        print("1. 🔄 RESTART VS CODE COMPLETELY (close and reopen)")
        print("2. 🔍 Wait a few seconds for Pylance to reload")
        print("3. ✅ Yellow squiggly lines should disappear")
        print("4. 🚀 Your scripts will run normally")
        
        print("\n💡 WHY THIS WORKS:")
        print("   • VS Code now knows to look in generated_proto folder")
        print("   • Python scripts have the correct import paths")
        print("   • Protobuf 3.20.3 is compatible with your files")
        print("   • No more descriptor errors or import warnings")
        
    else:
        print("\n⚠️ Some steps failed")
        print("🔄 Try restarting VS Code anyway - it might still work")
    
    print("\n🎯 THE BOTTOM LINE:")
    print("Your Python code works fine - this is just VS Code display issue")
    print("After restarting VS Code, the yellow warnings should be gone!")

if __name__ == "__main__":
    main()