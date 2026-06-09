async def handle_buy_order_placement(log_data):
    global buy_orders_placed, bought_coin, bought_quantity, INITIAL_USDT_BALANCE, bought_coin_precision, price_precision, USE_THRESHOLD_CHECKER, PRINT_MESSAGES, order_updates

    log_data = await parse_log_data(log_data)

    if 'Symbol' in log_data and 'Price' in log_data:
        symbol = log_data['Symbol']
        price = Decimal(log_data['Price'])

        bought_coin = symbol.split('USDT')[0]
        if check_ignore_list(symbol):
            return

        price_precision = max(0, -price.as_tuple().exponent)

        if symbol in symbol_ohlcv_data:
            open_price = Decimal(str(symbol_ohlcv_data[symbol]))
            logging.info(f"Symbol: {symbol}, Current Price: {price}, Open Price: {open_price}")
            
            if should_buy_based_on_threshold(price, open_price):
                buy_orders = generate_buy_orders(symbol, price)
                order_ids, buy_time_taken = await process_buy_orders(buy_orders)
                total_usdt_spent, total_coins_bought = calculate_order_totals(order_ids, buy_orders)

                bought_coin_precision = max(0, -total_coins_bought.as_tuple().exponent)
                
                if total_coins_bought > Decimal('0'):
                    average_buy_price = total_usdt_spent / total_coins_bought
                    log_buy_results(buy_time_taken, total_usdt_spent, total_coins_bought, average_buy_price)
                    
                    logging.info(f"Stored price precision: {price_precision}, Stored {bought_coin} precision: {bought_coin_precision}")

                    new_usdt_balance = get_latest_usdt_balance()
                    if new_usdt_balance != INITIAL_USDT_BALANCE:
                        logging.info(f"USDT balance changed from {INITIAL_USDT_BALANCE:.{price_precision}f} to {new_usdt_balance:.{price_precision}f}")
                        INITIAL_USDT_BALANCE = new_usdt_balance

                    sell_order_results = await place_batch_sell_orders(symbol, total_coins_bought, average_buy_price, price_precision, bought_coin_precision)
                    
                    for i, result in enumerate(sell_order_results, 1):
                        if 'orderId' in result:
                            pass
                    
                    PRINT_MESSAGES = False

                buy_orders_placed = True
            elif USE_THRESHOLD_CHECKER:
                logging.info(f"Didn't buy, price is above {PRICE_INCREASE_THRESHOLD * 100}% of open price for {symbol}")
        else:
            logging.warning(f"No open price data found for {symbol}")
    
    if buy_orders_placed:
        PRINT_MESSAGES = False