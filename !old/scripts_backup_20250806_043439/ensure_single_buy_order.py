
# ============ PROTOBUF COMPATIBILITY FIX ============
import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
print("🔧 PROTOBUF FIX APPLIED: Using pure Python implementation")
# ==================================================

async def ensure_single_buy_order(log_data):
    global buy_orders_placed, bought_coin

    with buy_order_lock:
        if not buy_orders_placed and ENABLE_BUYING:
            await handle_buy_order_placement(log_data)
            buy_orders_placed = True
            return True
    return False