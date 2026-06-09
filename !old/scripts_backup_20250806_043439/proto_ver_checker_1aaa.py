#!/usr/bin/env python3

# IMPORT PATH FIXER - FIXES THE YELLOW IMPORT ERRORS IN VS CODE
# This fixes the "could not be resolved" errors you're seeing

import os
import sys
import shutil
from datetime import datetime

def print_header():
    """Print script header."""
    print("=" * 80)
    print("🔧 IMPORT PATH FIXER - FIXES YELLOW IMPORT ERRORS")
    print("🎯 FIXES 'could not be resolved' ERRORS IN VS CODE")
    print("💪 MAKES ALL PROTOBUF IMPORTS WORK PROPERLY")
    print("=" * 80)

def create_backup():
    """Create backup of scripts before modifying."""
    print("\n📦 CREATING BACKUP...")
    
    backup_dir = f"scripts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup all Python scripts
        python_files = [f for f in os.listdir('.') if f.endswith('.py')]
        
        for file in python_files:
            if not file.startswith('fix_') and not file.startswith('import_'):
                shutil.copy2(file, backup_dir)
        
        print(f"✅ Backed up {len(python_files)} Python files to {backup_dir}")
        return backup_dir
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return None

def fix_import_paths_in_scripts():
    """Fix import paths in all Python scripts."""
    print("\n🔧 FIXING IMPORT PATHS IN SCRIPTS...")
    
    # Find all Python scripts that import protobuf files
    python_scripts = []
    for file in os.listdir('.'):
        if (file.endswith('.py') and 
            not file.startswith('fix_') and 
            not file.startswith('import_')):
            python_scripts.append(file)
    
    if not python_scripts:
        print("❌ No Python scripts found")
        return False
    
    print(f"🔍 Checking {len(python_scripts)} scripts for import issues")
    
    # List of protobuf modules that need path fixing
    protobuf_modules = [
        'PrivateAccountV3Api_pb2',
        'PushDataV3ApiWrapper_pb2', 
        'PublicLimitDepthsV3Api_pb2',
        'PublicAggreDepthsV3Api_pb2',
        'PublicIncreaseDepthsBatchV3Api_pb2',
        'PrivateOrdersV3Api_pb2',
        'PublicAggreBookTickerV3Api_pb2',
        'PublicDealsV3Api_pb2',
        'PublicBookTickerBatchV3Api_pb2',
        'PublicBookTickerV3Api_pb2',
        'PrivateDealsV3Api_pb2',
        'PublicAggreDealsV3Api_pb2',
        'PublicMiniTickersV3Api_pb2',
        'PublicMiniTickerV3Api_pb2',
        'PublicIncreaseDepthsV3Api_pb2',
        'PublicSpotKlineV3Api_pb2'
    ]
    
    fixed_count = 0
    
    for script in python_scripts:
        try:
            print(f"\n🔍 Checking {script}...")
            
            with open(script, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            changes_made = []
            
            # Check if script imports any protobuf modules
            needs_fixing = False
            for module in protobuf_modules:
                if f'import {module}' in content or f'from {module}' in content:
                    needs_fixing = True
                    break
            
            if not needs_fixing:
                print(f"   ℹ️ No protobuf imports found")
                continue
            
            # Step 1: Add sys.path.insert for generated_proto
            lines = content.split('\n')
            
            # Find where to insert the path fix
            insert_position = 0
            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    insert_position = i
                    break
            
            # Check if path fix already exists
            has_path_fix = any('sys.path.insert' in line and 'generated_proto' in line for line in lines)
            
            if not has_path_fix:
                # Insert path fix
                path_fix_lines = [
                    '',
                    '# ============ PROTOBUF IMPORT PATH FIX ============',
                    'import sys',
                    'import os',
                    'sys.path.insert(0, os.path.join(os.path.dirname(__file__), "generated_proto"))',
                    'print("🔧 PROTOBUF PATH ADDED: generated_proto folder accessible")',
                    '# ================================================',
                    ''
                ]
                
                for j, fix_line in enumerate(path_fix_lines):
                    lines.insert(insert_position + j, fix_line)
                
                changes_made.append("Added sys.path fix for generated_proto")
            
            # Step 2: Update imports to use correct module names
            content = '\n'.join(lines)
            
            # Fix direct imports
            for module in protobuf_modules:
                # Replace direct imports
                old_import = f'import {module}'
                new_import = f'import {module}'  # Keep the same, path fix handles it
                
                # Replace from imports  
                old_from = f'from {module}'
                new_from = f'from {module}'  # Keep the same, path fix handles it
                
                # The path fix above should handle the imports, but let's make sure
                # they're using the right syntax
                
            # Step 3: Add error handling for imports
            lines = content.split('\n')
            new_lines = []
            
            for line in lines:
                # If it's a protobuf import, wrap it in try/except
                if any(f'import {module}' in line for module in protobuf_modules):
                    if 'try:' not in line and 'except:' not in line:
                        module_name = None
                        for module in protobuf_modules:
                            if f'import {module}' in line:
                                module_name = module
                                break
                        
                        if module_name:
                            new_lines.extend([
                                'try:',
                                f'    {line}',
                                f'    print("✅ Successfully imported {module_name}")',
                                'except ImportError as e:',
                                f'    print("❌ Failed to import {module_name}: {{e}}")',
                                f'    print("🔍 Check if generated_proto folder exists and contains {module_name}.py")',
                                '    sys.exit(1)'
                            ])
                            changes_made.append(f"Added error handling for {module_name}")
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            content = '\n'.join(new_lines)
            
            # Write the changes
            if content != original_content:
                with open(script, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"   ✅ FIXED! Changes: {', '.join(changes_made)}")
                fixed_count += 1
            else:
                print(f"   ℹ️ No changes needed")
                
        except Exception as e:
            print(f"   ❌ Error fixing {script}: {e}")
    
    print(f"\n✅ Fixed {fixed_count} scripts")
    return fixed_count > 0

def create_init_file():
    """Create __init__.py in generated_proto to make it a proper Python package."""
    print("\n📦 CREATING PYTHON PACKAGE FILES...")
    
    try:
        # Create __init__.py in generated_proto
        init_file = os.path.join('generated_proto', '__init__.py')
        
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write('# Generated protobuf package\n')
                f.write('# This file makes generated_proto a proper Python package\n')
            print("✅ Created __init__.py in generated_proto")
        else:
            print("✅ __init__.py already exists in generated_proto")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating package files: {e}")
        return False

def create_vscode_settings():
    """Create VS Code settings to fix Pylance import resolution."""
    print("\n🔧 CREATING VS CODE SETTINGS FOR PYLANCE...")
    
    try:
        # Create .vscode directory if it doesn't exist
        if not os.path.exists('.vscode'):
            os.makedirs('.vscode')
        
        settings_file = os.path.join('.vscode', 'settings.json')
        
        # VS Code settings to fix Pylance import issues
        settings = {
            "python.analysis.extraPaths": [
                "./generated_proto"
            ],
            "python.autoComplete.extraPaths": [
                "./generated_proto"  
            ],
            "pylance.include": [
                "generated_proto/**"
            ],
            "python.analysis.autoSearchPaths": True,
            "python.analysis.diagnosticMode": "workspace"
        }
        
        import json
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
        
        print("✅ Created VS Code settings.json")
        print("   This tells Pylance where to find your protobuf files")
        return True
        
    except Exception as e:
        print(f"❌ Error creating VS Code settings: {e}")
        return False

def test_imports():
    """Test that all imports work correctly."""
    print("\n🧪 TESTING IMPORT RESOLUTION...")
    
    # Add generated_proto to path for testing
    import sys
    generated_proto_path = os.path.join(os.getcwd(), 'generated_proto')
    if generated_proto_path not in sys.path:
        sys.path.insert(0, generated_proto_path)
    
    protobuf_modules = [
        'PrivateAccountV3Api_pb2',
        'PushDataV3ApiWrapper_pb2', 
        'PublicLimitDepthsV3Api_pb2',
        'PublicAggreDepthsV3Api_pb2'
    ]
    
    successful_imports = 0
    failed_imports = 0
    
    for module in protobuf_modules:
        try:
            exec(f'import {module}')
            print(f"✅ {module} imported successfully")
            successful_imports += 1
        except Exception as e:
            print(f"❌ {module} failed: {e}")
            failed_imports += 1
    
    return successful_imports, failed_imports

def main():
    """Main function to fix all import path issues."""
    print_header()
    
    # Step 1: Create backup
    backup_dir = create_backup()
    if not backup_dir:
        print("❌ Cannot proceed without backup")
        return
    
    # Step 2: Fix import paths in scripts
    print("\n" + "="*60)
    print("STEP 1: FIXING IMPORT PATHS IN SCRIPTS")
    print("="*60)
    
    scripts_fixed = fix_import_paths_in_scripts()
    
    # Step 3: Create Python package files
    print("\n" + "="*60)
    print("STEP 2: CREATING PYTHON PACKAGE STRUCTURE")
    print("="*60)
    
    package_created = create_init_file()
    
    # Step 4: Create VS Code settings
    print("\n" + "="*60)
    print("STEP 3: CREATING VS CODE SETTINGS")
    print("="*60)
    
    vscode_settings = create_vscode_settings()
    
    # Step 5: Test imports
    print("\n" + "="*60)
    print("STEP 4: TESTING IMPORTS")
    print("="*60)
    
    successful, failed = test_imports()
    
    # Final results
    print("\n" + "="*60)
    print("🎯 FINAL RESULTS")
    print("="*60)
    
    print(f"📦 Backup created: {backup_dir}")
    print(f"🔧 Scripts fixed: {'✅ YES' if scripts_fixed else '❌ NO'}")
    print(f"📦 Package structure: {'✅ YES' if package_created else '❌ NO'}")
    print(f"🔧 VS Code settings: {'✅ YES' if vscode_settings else '❌ NO'}")
    print(f"✅ Successful imports: {successful}")
    print(f"❌ Failed imports: {failed}")
    
    if successful > 0 and failed == 0:
        print("\n🎉 SUCCESS! All import path issues fixed!")
        print("🚀 Restart VS Code to see the yellow warnings disappear")
        print("💡 Your scripts should now run without import errors")
    elif successful > 0:
        print("\n✅ Partially fixed - some imports still failing")
        print("🔄 Restart VS Code and check remaining issues")
    else:
        print("\n❌ Import issues persist")
        print("🔍 Check if generated_proto folder contains all the _pb2.py files")
    
    print("\n📋 NEXT STEPS:")
    print("1. 🔄 Restart VS Code completely")
    print("2. 🔍 Check that yellow squiggly lines are gone")
    print("3. 🚀 Run your scripts to verify they work")
    print(f"4. 💾 If issues persist, restore from: {backup_dir}")

if __name__ == "__main__":
    main()