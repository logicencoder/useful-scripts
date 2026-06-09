import requests
import json

def send_to_flask(data, client_info, flask_port=6000, enable_logging=False):
    """
    Send data with client info to a Flask server.
    
    :param data: Dictionary containing the data to be sent
    :param client_info: String containing client information
    :param flask_port: Port number for the Flask server (default: 6000)
    :param enable_logging: Boolean to enable/disable logging (default: False)
    :return: None
    """
    try:
        # Add client_info to the data
        data['client_info'] = client_info

        # Construct the Flask endpoint URL
        flask_endpoint = f'http://localhost:{flask_port}/send_data'

        # Send POST request to Flask
        response = requests.post(flask_endpoint, json=data)

        if response.status_code == 200:
            if enable_logging:
                print(f"Data sent to Flask successfully: {data}")
        else:
            if enable_logging:
                print(f"Failed to send data to Flask. Status code: {response.status_code}, Response: {response.text}")

    except requests.RequestException as e:
        if enable_logging:
            print(f"Error sending data to Flask: {e}")

# Example usage:
# client_info = "KUCOIN"
# data = {"some_key": "some_value"}
# send_to_flask(data, client_info, enable_logging=True)