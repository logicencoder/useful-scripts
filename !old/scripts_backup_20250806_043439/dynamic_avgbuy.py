from decimal import Decimal

def get_formatted_avg_buy_price(average_buy_price: Decimal, market_price: str) -> str:
    """
    Format the average buy price with a dynamic number of decimal places
    based on the market price.

    :param average_buy_price: The average buy price as a Decimal
    :param market_price: The market price as a string
    :return: Formatted string of the average buy price with appropriate decimal places
    """
    price = Decimal(market_price)
    
    if price < Decimal('0.01'):
        decimals = 8
    elif price < Decimal('0.1'):
        decimals = 7
    elif price < Decimal('1'):
        decimals = 6
    elif price < Decimal('10'):
        decimals = 5
    elif price < Decimal('100'):
        decimals = 4
    elif price < Decimal('1000'):
        decimals = 3
    else:
        decimals = 2

    return f"{average_buy_price:.{decimals}f}"

    
    # Assuming you have the average buy price and market price
average_buy_price = Decimal('1.23456789')  # Your calculated average buy price
market_price = data['data']['lastPrice']  # Market price from your websocket data

formatted_avg_buy_price = get_formatted_avg_buy_price(average_buy_price, market_price)

logging.info(f"Average Buy Price: {formatted_avg_buy_price}")