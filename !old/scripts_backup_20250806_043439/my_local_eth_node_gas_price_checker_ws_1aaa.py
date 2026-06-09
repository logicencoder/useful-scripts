import asyncio
import json
from web3 import Web3
from datetime import datetime
from typing import Dict, Any
from colorama import init, Fore, Style
import websockets

# Initialize colorama
init()

async def get_network_stats(websocket) -> Dict[str, Any]:
    """
    Get all network stats using WebSocket connection
    
    Args:
        websocket: Active WebSocket connection
    Returns:
        Dictionary with network stats
    """
    # Get block number
    block_request = {
        "jsonrpc": "2.0",
        "method": "eth_blockNumber",
        "params": [],
        "id": 1
    }
    await websocket.send(json.dumps(block_request))
    block_response = await websocket.recv()
    block = int(json.loads(block_response)['result'], 16)

    # Get gas price
    gas_request = {
        "jsonrpc": "2.0",
        "method": "eth_gasPrice",
        "params": [],
        "id": 2
    }
    await websocket.send(json.dumps(gas_request))
    gas_response = await websocket.recv()
    gas_price = int(json.loads(gas_response)['result'], 16)

    # Get latest block
    latest_block_request = {
        "jsonrpc": "2.0",
        "method": "eth_getBlockByNumber",
        "params": ["latest", True],
        "id": 3
    }
    await websocket.send(json.dumps(latest_block_request))
    block_response = await websocket.recv()
    latest_block = json.loads(block_response)['result']
    
    base_fee = int(latest_block['baseFeePerGas'], 16)
    block_txs = len(latest_block['transactions'])

    # Get txpool status
    txpool_request = {
        "jsonrpc": "2.0",
        "method": "txpool_status",
        "params": [],
        "id": 4
    }
    await websocket.send(json.dumps(txpool_request))
    txpool_response = await websocket.recv()
    txpool = json.loads(txpool_response)['result']

    # Convert values
    w3 = Web3()  # For unit conversion only
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "block_number": block,
        "gas_price_gwei": w3.from_wei(gas_price, 'gwei'),
        "base_fee_gwei": w3.from_wei(base_fee, 'gwei'),
        "txs_in_last_block": block_txs,
        "pending_txs": int(txpool['pending'], 16),
        "queued_txs": int(txpool['queued'], 16)
    }

def print_stats(stats: Dict[str, Any]):
    """
    Print network statistics with colors
    """
    print("\033[2J\033[H")  # Clear screen
    print(f"{Fore.CYAN}=== Ethereum Network Monitor ==={Style.RESET_ALL}")
    print(f"Time: {stats['timestamp']}")
    print(f"\n{Fore.YELLOW}Block Height:{Style.RESET_ALL} {stats['block_number']:,}")
    print(f"{Fore.GREEN}Gas Price:{Style.RESET_ALL} {stats['gas_price_gwei']:.2f} Gwei")
    print(f"{Fore.GREEN}Base Fee:{Style.RESET_ALL} {stats['base_fee_gwei']:.2f} Gwei")
    print(f"\n{Fore.BLUE}Transactions:{Style.RESET_ALL}")
    print(f"  Last Block: {stats['txs_in_last_block']:,}")
    print(f"  Pending: {stats['pending_txs']:,}")
    print(f"  Queued: {stats['queued_txs']:,}")
    print("\nPress Ctrl+C to exit")

async def main():
    """
    Main function to run the monitor
    """
    ws_url = "ws://192.168.1.103:8546"
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"Connected to WebSocket node at {ws_url}")
            
            while True:
                try:
                    stats = await get_network_stats(websocket)
                    print_stats(stats)
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"{Fore.RED}Error getting stats: {e}{Style.RESET_ALL}")
                    await asyncio.sleep(5)
                    
    except KeyboardInterrupt:
        print("\nMonitoring stopped")
    except Exception as e:
        print(f"{Fore.RED}WebSocket connection failed: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(main())