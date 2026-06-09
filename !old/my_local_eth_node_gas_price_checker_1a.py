import asyncio
import json
from web3 import Web3
from datetime import datetime
from typing import Dict, Any
from colorama import init, Fore, Style

# Initialize colorama
init()

class EthereumMonitor:
    def __init__(self, node_url: str = "http://192.168.1.103:8545"):
        self.w3 = Web3(Web3.HTTPProvider(node_url))
        print(f"Connected to node: {self.w3.is_connected()}")
        
    async def get_network_stats(self) -> Dict[str, Any]:
        """Get current network statistics"""
        block = self.w3.eth.block_number
        gas_price = self.w3.eth.gas_price
        base_fee = self.w3.eth.get_block('latest').baseFeePerGas
        
        # Get latest block details
        latest_block = self.w3.eth.get_block('latest', True)
        block_txs = len(latest_block.transactions)
        
        # Get pending transactions
        txpool = self.w3.geth.txpool.status()
        pending = int(txpool['pending'], 16)
        queued = int(txpool['queued'], 16)
        
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "block_number": block,
            "gas_price_gwei": self.w3.from_wei(gas_price, 'gwei'),
            "base_fee_gwei": self.w3.from_wei(base_fee, 'gwei'),
            "txs_in_last_block": block_txs,
            "pending_txs": pending,
            "queued_txs": queued
        }
    
    def print_stats(self, stats: Dict[str, Any]):
        """Print network statistics with colors"""
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
    monitor = EthereumMonitor()
    try:
        while True:
            stats = await monitor.get_network_stats()
            monitor.print_stats(stats)
            await asyncio.sleep(1)  # Update every second
    except KeyboardInterrupt:
        print("\nMonitoring stopped")

if __name__ == "__main__":
    asyncio.run(main())