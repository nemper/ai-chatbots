import os
import requests
import xml.etree.ElementTree as ET

def API_search(matching_sec_ids):
    # Function to call the API for a specific product_id
    def get_product_info(token, product_id):
        url = "https://www.delfi.rs/api/products"  # Replace with your actual API endpoint
        params = {
            "token": token,
            "product_id": product_id
        }
        response = requests.get(url, params=params)
        print(f"API response for product_id {product_id}: {response.content}")  # Debugging line
        return response.content

    # Function to parse the XML response and extract required fields
    def parse_product_info(xml_data):
        product_info = {}
        try:
            root = ET.fromstring(xml_data)
            product_node = root.find(".//product")
            if product_node is not None:
                product_info['na_stanju'] = product_node.findtext('na_stanju')
                product_info['cena'] = product_node.findtext('cena')
                product_info['lager'] = product_node.findtext('lager')
            else:
                print("Product node not found in XML data")  # Debugging line
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")  # Debugging line
        return product_info

    # Main function to get info for a list of product IDs
    def get_multiple_products_info(token, product_ids):
        products_info = []
        for product_id in product_ids:
            xml_data = get_product_info(token, product_id)
            product_info = parse_product_info(xml_data)
            if product_info:  # Only add if product info is found
                products_info.append(product_info)
            else:
                products_info.append({
                    'product_id': product_id,
                    'na_stanju': 'N/A',
                    'cena': 'N/A',
                    'lager': 'N/A'
                })
        return products_info

    # Replace with your actual token and product IDs
    token = os.getenv("DELFI_API_KEY")
    product_ids = matching_sec_ids

    # Get the info for multiple products
    products_info = get_multiple_products_info(token, product_ids)
    print(f"Products Info: {products_info}")
    
    # Print the results
    if not any(info for info in products_info if info['na_stanju'] != 'N/A'):
        return "No products found"
    
    output = ""
    for info in products_info:
        output += f"Product ID: {info.get('product_id', 'N/A')}\n"
        output += f"Na stanju: {info.get('na_stanju', 'N/A')}\n"
        output += f"Cena: {info.get('cena', 'N/A')}\n"
        output += f"Lager: {info.get('lager', 'N/A')}\n\n"
    
    return output

# Example input to the function
matching_sec_ids = [77626, 69471, 150516]
print(API_search(matching_sec_ids))
