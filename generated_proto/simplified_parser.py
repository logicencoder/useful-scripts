#!/usr/bin/env python3
import struct
import json
import logging
import time
import re

class SimplifiedProtobufParser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_account_update(self, binary_data):
        try:
            data_str = binary_data.decode('utf-8', errors='ignore')
            
            account_indicators = ['vcoinName', 'balanceAmount', 'frozenAmount', 'ENTRUST']
            if not any(indicator in data_str for indicator in account_indicators):
                return None
            
            coin_matches = re.findall(r'([A-Z]{2,5})', data_str)
            coin = coin_matches[0] if coin_matches else 'UNKNOWN'
            
            number_matches = re.findall(r'([0-9]+\.?[0-9]*)', data_str)
            
            if len(number_matches) >= 2:
                available_balance = number_matches[0]
                locked_balance = number_matches[1]
            else:
                available_balance = '0'
                locked_balance = '0'
            
            return {
                'vcoinName': coin,
                'balanceAmount': available_balance,
                'balanceAmountChange': '0',
                'frozenAmount': locked_balance,
                'frozenAmountChange': '0',
                'type': 'SIMPLIFIED_UPDATE',
                'time': int(time.time() * 1000)
            }
            
        except Exception as e:
            self.logger.error(f"Simplified parsing failed: {e}")
            return None
