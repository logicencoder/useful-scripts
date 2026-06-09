# ONLY LIQUIDITY POLL CHECKER

import asyncio
import time
from datetime import datetime
from decimal import Decimal
import warnings
import os
from web3 import Web3
from colorama import init, Fore, Style, Back

# Initialize colorama
init()

# Suppress all warnings
warnings.filterwarnings("ignore")
os.environ['PYTHONWARNINGS'] = 'ignore'

# Core Constants
TOKEN_ADDRESS = "0x9928a8600d14ac22c0be1e8d58909834d7ceaf13".lower()
POOL_ADDRESS = "0xa29d18f6a73f6f65c9f0eeae2dd0563d6f615c0f".lower()
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2".lower()
TOKEN_DECIMALS = 9
WETH_DECIMALS = 18

def format_timestamp():
    """Format current timestamp with milliseconds"""
    now = datetime.now()
    return now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

def format_amount(amount: int, decimals: int) -> Decimal:
    """Format raw amount with proper decimals"""
    return Decimal(str(amount)) / Decimal(str(10 ** decimals))

async def get_pool_info(w3: Web3) -> dict:
    """Get current pool balances for token and WETH"""
    try:
        balance_abi = [{
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        }]
        
        # Create contract instances
        weth_contract = w3.eth.contract(
            address=Web3.to_checksum_address(WETH_ADDRESS), 
            abi=balance_abi
        )
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(TOKEN_ADDRESS), 
            abi=balance_abi
        )
        
        # Get balances
        weth_balance = await asyncio.to_thread(
            weth_contract.functions.balanceOf(
                Web3.to_checksum_address(POOL_ADDRESS)
            ).call
        )
        
        token_balance = await asyncio.to_thread(
            token_contract.functions.balanceOf(
                Web3.to_checksum_address(POOL_ADDRESS)
            ).call
        )
        
        return {
            'eth_balance': format_amount(weth_balance, WETH_DECIMALS),
            'token_balance': format_amount(token_balance, TOKEN_DECIMALS)
        }
        
    except Exception as e:
        print(f"Error getting pool info: {str(e)}")
        return {
            'eth_balance': Decimal('0'),
            'token_balance': Decimal('0')
        }

def select_provider():
    """Select Ethereum node provider"""
    print(f"\n{Back.BLUE}{Fore.WHITE} Select Ethereum Node Provider: {Style.RESET_ALL}")
    print("1. Primary Node (192.168.1.103)")
    print("2. Backup Node (localhost)")
    print("3. Custom IP")
    print("4. Infura")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-4): ").strip()
            if choice == "1":
                return "http://192.168.1.103:8545"
            elif choice == "2":
                return "http://localhost:8545"
            elif choice == "3":
                ip = input("\nEnter custom IP address (format: xxx.xxx.xxx.xxx): ").strip()
                return f"http://{ip}:8545"
            elif choice == "4":
                api_key = input("\nEnter your Infura API key: ").strip()
                return f"https://mainnet.infura.io/v3/{api_key}"
            else:
                print(f"{Back.RED}{Fore.WHITE}Enter 1, 2, 3, or 4{Style.RESET_ALL}")
        except ValueError:
            print(f"{Back.RED}{Fore.WHITE}Invalid input{Style.RESET_ALL}")

async def monitor_pool_liquidity(provider_url, update_interval=5):
    """Monitor pool liquidity at regular intervals"""
    print(f"\n{Back.GREEN}{Fore.BLACK} Starting Pool Liquidity Monitor {Style.RESET_ALL}")
    print(f"Provider: {provider_url}")
    print(f"Update Interval: {update_interval} seconds")
    print("Press Ctrl+C to stop monitoring\n")
    
    w3 = Web3(Web3.HTTPProvider(provider_url))
    
    # Check connection
    if not w3.is_connected():
        print(f"{Back.RED}{Fore.WHITE}Error: Cannot connect to the provider{Style.RESET_ALL}")
        return
    
    try:
        # Initial fetch
        pool_info = await get_pool_info(w3)
        timestamp = format_timestamp()
        print(f"{timestamp} Pool Liquidity: {Fore.CYAN}{pool_info['eth_balance']:.4f}{Style.RESET_ALL} WETH / {Fore.YELLOW}{pool_info['token_balance']:,.8f}{Style.RESET_ALL} 0xDNX")
        
        # Setup continuous monitoring
        while True:
            await asyncio.sleep(update_interval)
            
            # Get current pool info
            pool_info = await get_pool_info(w3)
            timestamp = format_timestamp()
            
            # Display pool liquidity with colored output
            print(f"{timestamp} Pool Liquidity: {Fore.CYAN}{pool_info['eth_balance']:.4f}{Style.RESET_ALL} WETH / {Fore.YELLOW}{pool_info['token_balance']:,.8f}{Style.RESET_ALL} 0xDNX")
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped")
    except Exception as e:
        print(f"\n{Back.RED}{Fore.WHITE}Error: {str(e)}{Style.RESET_ALL}")

async def main():
    """Main entry point"""
    try:
        print(f"\n{Back.BLUE}{Fore.WHITE} 0xDNX Pool Liquidity Monitor {Style.RESET_ALL}")
        provider_url = select_provider()
        
        # Get update interval
        update_interval = 5  # Default to 5 seconds
        try:
            interval_input = input(f"\nEnter update interval in seconds (default: {update_interval}): ").strip()
            if interval_input:
                update_interval = int(interval_input)
                if update_interval < 1:
                    update_interval = 1
                    print("Setting minimum interval to 1 second")
        except ValueError:
            print("Invalid input, using default 5 seconds")
        
        # Start monitoring
        await monitor_pool_liquidity(provider_url, update_interval)
        
    except KeyboardInterrupt:
        print("\nProgram terminated")
    except Exception as e:
        print(f"\n{Back.RED}{Fore.WHITE}Fatal error: {str(e)}{Style.RESET_ALL}")

# Program entry point
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated")
    except Exception as e:
        print(f"\n{Back.RED}{Fore.WHITE}Fatal error: {str(e)}{Style.RESET_ALL}")