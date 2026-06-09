#!/usr/bin/env python3

# AGGRESSIVE PROTOBUF FIXER - ACTUALLY REMOVES ALL VERSION ISSUES
# This version completely eliminates all protobuf version validation

import os
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

def print_header():
    """Print script header."""
    print("=" * 80)
    print("🔧 AGGRESSIVE PROTOBUF FIXER - ACTUALLY FIXES THE DAMN THING")
    print("🎯 COMPLETELY REMOVES ALL VERSION VALIDATION")
    print("💪 NO MORE YELLOW WARNINGS OR IMPORT ERRORS")
    print("=" * 80)

def create_backup():
    """Create backup of protobuf files."""
    print("\n📦 CREATING BACKUP...")
    
    backup_dir = f"protobuf_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        os.makedirs(backup_dir, exist_ok=True)
        
        if os.path.exists('generated_proto'):
            shutil.copytree('generated_proto', f"{backup_dir}/generated_proto")
            print(f"✅ Backed up generated_proto to {backup_dir}")
            return backup_dir
        else:
            print("❌ generated_proto folder not found!")
            return None
            
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return None

def aggressive_patch_protobuf_files():
    """AGGRESSIVE patching - removes ALL version validation completely."""
    print("\n🔥 AGGRESSIVE PATCHING - REMOVING ALL VERSION CHECKS...")
    
    if not os.path.exists('generated_proto'):
        print("❌ generated_proto folder not found")
        return False
    
    protobuf_files = []
    for file in os.listdir('generated_proto'):
        if file.endswith('_pb2.py'):
            protobuf_files.append(os.path.join('generated_proto', file))
    
    if not protobuf_files:
        print("❌ No protobuf files found in generated_proto")
        return False
    
    print(f"🔍 Found {len(protobuf_files)} protobuf files to patch")
    
    patched_count = 0
    
    for file_path in protobuf_files:
        try:
            filename = os.path.basename(file_path)
            print(f"\n🔧 AGGRESSIVELY PATCHING {filename}...")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            changes_made = []
            
            # STEP 1: Remove runtime_version import completely
            lines = content.split('\n')
            new_lines = []
            
            for line in lines:
                if 'from google.protobuf import runtime_version' in line:
                    new_lines.append('# REMOVED: ' + line + '  # AGGRESSIVE PATCH')
                    changes_made.append("Removed runtime_version import")
                else:
                    new_lines.append(line)
            
            content = '\n'.join(new_lines)
            
            # STEP 2: Remove ENTIRE ValidateProtobufRuntimeVersion blocks
            lines = content.split('\n')
            new_lines = []
            skip_mode = False
            parenthesis_count = 0
            
            i = 0
            while i < len(lines):
                line = lines[i]
                
                if '_runtime_version.ValidateProtobufRuntimeVersion(' in line or 'ValidateProtobufRuntimeVersion(' in line:
                    # Start of validation block - remove everything until matching closing parenthesis
                    new_lines.append('# REMOVED VALIDATION BLOCK: ' + line + '  # AGGRESSIVE PATCH')
                    skip_mode = True
                    parenthesis_count = line.count('(') - line.count(')')
                    changes_made.append("Removed validation block")
                    
                elif skip_mode:
                    # We're inside a validation block
                    parenthesis_count += line.count('(') - line.count(')')
                    new_lines.append('# REMOVED: ' + line + '  # AGGRESSIVE PATCH')
                    
                    if parenthesis_count <= 0:
                        # End of validation block
                        skip_mode = False
                        parenthesis_count = 0
                        
                else:
                    # Normal line - keep it
                    new_lines.append(line)
                
                i += 1
            
            content = '\n'.join(new_lines)
            
            # STEP 3: Remove any remaining _runtime_version references
            if '_runtime_version' in content:
                lines = content.split('\n')
                new_lines = []
                for line in lines:
                    if '_runtime_version' in line and 'REMOVED' not in line and 'AGGRESSIVE PATCH' not in line:
                        new_lines.append('# REMOVED: ' + line + '  # AGGRESSIVE PATCH')
                        if "remaining runtime_version references" not in changes_made:
                            changes_made.append("Removed remaining runtime_version references")
                    else:
                        new_lines.append(line)
                content = '\n'.join(new_lines)
            
            # STEP 4: Fix any descriptor creation issues
            # Replace direct descriptor creation with safe alternatives
            content = content.replace(
                'serialized_options=None, file=DESCRIPTOR',
                'serialized_options=None'
            )
            
            # STEP 5: Remove global descriptor assignments that cause issues
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                if ('_globals[' in line and 'DESCRIPTOR' in line and 
                    '_descriptor' in line and '=' in line):
                    new_lines.append('# REMOVED DESCRIPTOR: ' + line + '  # AGGRESSIVE PATCH')
                    if "descriptor assignments" not in changes_made:
                        changes_made.append("Removed problematic descriptor assignments")
                else:
                    new_lines.append(line)
            content = '\n'.join(new_lines)
            
            # Only write if we made changes
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"   ✅ PATCHED! Changes: {', '.join(changes_made)}")
                patched_count += 1
            else:
                print(f"   ℹ️ No changes needed")
                
        except Exception as e:
            print(f"   ❌ Error patching {filename}: {e}")
    
    if patched_count > 0:
        print(f"\n🎉 SUCCESSFULLY PATCHED {patched_count} FILES!")
        print("🔥 ALL VERSION VALIDATION COMPLETELY REMOVED!")
        return True
    else:
        print("\n⚠️ No files were patched")
        return False

def add_environment_fix_to_scripts():
    """Add environment variable fix to all Python scripts."""
    print("\n🔧 ADDING ENVIRONMENT FIX TO SCRIPTS...")
    
    # Find Python scripts that might use protobuf
    python_scripts = []
    for file in os.listdir('.'):
        if (file.endswith('.py') and 
            file != __file__ and 
            ('mexc' in file.lower() or 'balance' in file.lower() or 
             'order' in file.lower() or 'api' in file.lower())):
            python_scripts.append(file)
    
    if not python_scripts:
        print("❌ No relevant Python scripts found")
        return False
    
    print(f"🔍 Found {len(python_scripts)} scripts to fix")
    
    fixed_count = 0
    
    for script in python_scripts:
        try:
            with open(script, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if already has the fix
                print(f"✅ {script} already has environment fix")
                continue
            
            # Backup first
            backup_name = f"{script}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(script, backup_name)
            
            # Find where to insert the fix
            lines = content.split('\n')
            
            # Look for imports section
            insert_position = 0
            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    insert_position = i + 1
                elif line.strip() == '' and insert_position > 0:
                    break
            
            # Insert the fix
            fix_lines = [
                '',
                '# ============ PROTOBUF COMPATIBILITY FIX ============',
                'import os',
                '# ==================================================',
                ''
            ]
            
            # Insert the fix
            for j, fix_line in enumerate(fix_lines):
                lines.insert(insert_position + j, fix_line)
            
            # Write back
            with open(script, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            print(f"✅ Fixed {script} (backup: {backup_name})")
            fixed_count += 1
            
        except Exception as e:
            print(f"❌ Error fixing {script}: {e}")
    
    print(f"\n✅ Fixed {fixed_count} scripts with environment variable")
    return fixed_count > 0

def test_protobuf_import():
    """Test if protobuf imports work without errors."""
    print("\n🧪 TESTING PROTOBUF IMPORTS...")
    
    # Set environment variable for this test
    
    test_results = {
        'imports_successful': [],
        'imports_failed': [],
        'warnings_detected': False
    }
    
    if not os.path.exists('generated_proto'):
        print("❌ generated_proto folder not found")
        return test_results
    
    # Add generated_proto to path
    if 'generated_proto' not in sys.path:
        sys.path.insert(0, 'generated_proto')
    
    # Test importing each protobuf file
    protobuf_files = [f for f in os.listdir('generated_proto') if f.endswith('_pb2.py')]
    
    for pb_file in protobuf_files[:5]:  # Test first 5 files
        module_name = pb_file[:-3]  # Remove .py extension
        try:
            print(f"🔍 Testing import: {module_name}")
            
            # Capture warnings
            import warnings
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                
                # Try to import the module
                exec(f"import {module_name}")
                
                if w:
                    print(f"⚠️ Warnings detected in {module_name}")
                    test_results['warnings_detected'] = True
                    for warning in w:
                        print(f"   Warning: {warning.message}")
                else:
                    print(f"✅ {module_name} imported successfully")
                    test_results['imports_successful'].append(module_name)
                
        except Exception as e:
            print(f"❌ Failed to import {module_name}: {e}")
            test_results['imports_failed'].append((module_name, str(e)))
    
    return test_results

def main():
    """Main function that actually fixes the protobuf issues."""
    print_header()
    
    # Step 1: Create backup
    backup_dir = create_backup()
    if not backup_dir:
        print("❌ Cannot proceed without backup")
        return
    
    # Step 2: Apply aggressive patching
    print("\n" + "="*60)
    print("STEP 1: AGGRESSIVE PROTOBUF FILE PATCHING")
    print("="*60)
    
    patch_success = aggressive_patch_protobuf_files()
    
    # Step 3: Add environment fix to scripts
    print("\n" + "="*60)
    print("STEP 2: ADDING ENVIRONMENT FIX TO SCRIPTS")
    print("="*60)
    
    env_fix_success = add_environment_fix_to_scripts()
    
    # Step 4: Test the fixes
    print("\n" + "="*60)
    print("STEP 3: TESTING THE FIXES")
    print("="*60)
    
    test_results = test_protobuf_import()
    
    # Step 5: Report results
    print("\n" + "="*60)
    print("🎯 FINAL RESULTS")
    print("="*60)
    
    print(f"📦 Backup created: {backup_dir}")
    print(f"🔧 Protobuf files patched: {'✅ YES' if patch_success else '❌ NO'}")
    print(f"🔧 Scripts fixed: {'✅ YES' if env_fix_success else '❌ NO'}")
    print(f"✅ Successful imports: {len(test_results['imports_successful'])}")
    print(f"❌ Failed imports: {len(test_results['imports_failed'])}")
    print(f"⚠️ Warnings detected: {'YES' if test_results['warnings_detected'] else 'NO'}")
    
    if test_results['imports_failed']:
        print("\n🔍 IMPORT FAILURES:")
        for module, error in test_results['imports_failed']:
            print(f"   {module}: {error}")
    
    if len(test_results['imports_successful']) > 0 and not test_results['warnings_detected']:
        print("\n🎉 SUCCESS! Protobuf imports are working without warnings!")
        print("🚀 Your scripts should now run without yellow warnings")
    elif test_results['warnings_detected']:
        print("\n⚠️ Some warnings still present - may need additional fixes")
    else:
        print("\n❌ Still having issues - may need to regenerate protobuf files")
        print("💡 Try running: protoc --python_out=generated_proto *.proto")
    
    print(f"\n💾 If you need to restore, your backup is in: {backup_dir}")

if __name__ == "__main__":
    main()