def color_trade_side(trade_type):
    """Colors the trade side green for buy, red for sell."""
    trade_type_str = "BUY" if trade_type == 1 else "SELL"
    color_code = "\033[32m" if trade_type == 1 else "\033[31m"  # Green for BUY, Red for SELL
    return f"{color_code}{trade_type_str}\033[0m"

def handle_logging(symbol, formatted_message):
    """Handles both console and separate file logging."""
    # Log to console using the console logger
    console_logger.info(formatted_message)

    # Log to separate file if separate_logging is True
    if separate_logging:
        if symbol not in separate_loggers:
            separate_loggers[symbol] = setup_separate_logger(symbol)
        separate_loggers[symbol].info(formatted_message)

async def on_message(symbol, message):
    try:
        data = json.loads(message)
        if data.get("c") == f"spot@public.deals.v3.api@{symbol}":
            trade_data = data["d"]["deals"][0]
            price = trade_data["p"]
            volume = trade_data["v"]
            trade_type = trade_data["S"]  # Trade type 1:buy, 2:sell
            
            price_decimal = Decimal(price)
            volume_decimal = Decimal(volume)
            
            usdt_volume = price_decimal * volume_decimal
            usdt_volume_rounded = usdt_volume.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            colored_trade_type = color_trade_side(trade_type)
            
            formatted_message = f"{symbol} - Price: {price}, Amount: {volume} {symbol.replace('USDT', '')}, USDT Amount: {usdt_volume_rounded}, Side: {colored_trade_type}"

            # Handle logging
            handle_logging(symbol, formatted_message)

            # Send data to Flask server
            send_data_to_flask(symbol, price, trade_type, usdt_volume_rounded)

    except Exception as e:
        logging.error(f"Error processing message for {symbol}: {e}")