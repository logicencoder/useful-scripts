#!/bin/bash

echo "🔧 FIXING PROTOBUF VERSION MISMATCH!"
echo "===================================="

# Downgrade protobuf to work with your protoc 3.12
echo "⬇️ Downgrading protobuf to 3.20.3 (compatible with protoc 3.12)..."
pip install --force-reinstall protobuf==3.20.3

echo ""
echo "✅ DONE! Now run:"
echo "python mexc_protodepth_tui_single.py"