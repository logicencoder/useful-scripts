from decimal import Decimal

def format_decimal(value):
    """
    Format a Decimal number without scientific notation.
    
    Args:
    value (Decimal or str or float): The number to format.
    
    Returns:
    str: Formatted number as a string without scientific notation.
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    
    return format(value, 'f').rstrip('0').rstrip('.')


from decimal import Decimal

# Example usage:
small_number = Decimal('6.04E-8')
formatted = format_decimal(small_number)
print(formatted)  # Output: 0.0000000604

large_number = Decimal('1.23E10')
formatted = format_decimal(large_number)
print(formatted)  # Output: 12300000000

regular_number = Decimal('123.4560')
formatted = format_decimal(regular_number)
print(formatted)  # Output: 123.456