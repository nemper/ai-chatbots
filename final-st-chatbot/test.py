from os import getenv

import requests
def API_search_2(order_ids):
    """
    Retrieves and processes information for a list of order IDs.

    This function fetches detailed information for each order ID by making API requests to an external service.
    It parses the JSON responses to extract relevant order details such as ID, type, status, delivery service,
    delivery time, payment type, package status, and order item type. Additionally, it collects tracking codes
    and performs an auxiliary search if tracking codes are available.

    Args:
        order_ids (List[str]): A list of order IDs for which information is to be retrieved.

    Returns:
        List[Dict[str, Any]] or str: A list of dictionaries containing the extracted order information. If an error
                                     occurs during the retrieval process, it returns an error message indicating that
                                     no orders were found for the given IDs.
    """
    def get_order_info(order_id):
        url = f"http://185.22.145.64:3003/api/order-info/{order_id}"
        headers = {
            'x-api-key': getenv("DELFI_ORDER_API_KEY")
        }
        return requests.get(url, headers=headers).json()
    tc = []
    # Function to parse the JSON response and extract required fields
    def parse_order_info(json_data):
        """
        Parses the JSON data for a single order and extracts relevant order information.

        Args:
            json_data (Dict[str, Any]): The JSON data received from the order information API.

        Returns:
            Dict[str, Any]: A dictionary containing extracted order details such as:
                - id (str): The unique identifier of the order.
                - type (str): The type of the order.
                - status (str): The current status of the order.
                - delivery_service (str): The delivery service used for the order.
                - delivery_time (str): The estimated delivery time.
                - payment_type (str): The type of payment used.
                - package_status (str): The status of the package.
                - order_item_type (str): The type of items in the order.
        """
        order_info = {}
        if 'orderData' in json_data:
            data = json_data['orderData']
            f = str(data)
            if "shipped" in f:
                print(1111)
            # Extract required fields from the order info
            order_info['id'] = data.get('id', 'N/A')
            order_info['type'] = data.get('type', 'N/A')
            order_info['status'] = data.get('status', 'N/A')
            order_info['delivery_service'] = data.get('delivery_service', 'N/A')
            order_info['delivery_time'] = data.get('delivery_time', 'N/A')
            order_info['payment_type'] = data.get('payment_detail', {}).get('payment_type', 'N/A')
            tc.append(data.get('tracking_codes', None))
            # Extract package info if available
            packages = data.get('packages', [])
            if packages:
                package_status = packages[0].get('status', 'N/A')
                order_info['package_status'] = package_status

            # Extract order items info if available
            order_items = data.get('order_items', [])
            if order_items:
                item_type = order_items[0].get('type', 'N/A')
                order_info['order_item_type'] = item_type

        return order_info

    # Main function to get info for a list of order IDs
    def get_multiple_orders_info(order_ids):
        """
        Retrieves and processes information for multiple order IDs.

        Args:
            order_ids (List[str]): A list of order IDs for which information is to be retrieved.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each containing details of an order, including:
                - id (str): The unique identifier of the order.
                - type (str): The type of the order.
                - status (str): The current status of the order.
                - delivery_service (str): The delivery service used for the order.
                - delivery_time (str): The estimated delivery time.
                - payment_type (str): The type of payment used.
                - package_status (str): The status of the package.
                - order_item_type (str): The type of items in the order.
            If an error occurs during retrieval, the list may contain an error message string.
        """
        orders_info = []
        for order_id in order_ids:
            json_data = get_order_info(order_id)
            order_info = parse_order_info(json_data)
            if order_info:
                orders_info.append(order_info)
        return orders_info
    
    orders_info = get_multiple_orders_info(order_ids)

    return orders_info


numbers = list(range(975496, 976496))

o = API_search_2(numbers)

