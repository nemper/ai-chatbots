import requests
import re
from os import getenv

def API_search_aks(order_ids):
    
    def get_current_status(order_id):
        url = f"http://www.akskurir.com/AKSVipService/TrenutniStatus/{order_id}"
        headers = {
            'x-api-key': getenv("DELFI_ORDER_API_KEY")  # Pretpostavljamo da je potrebni API ključ
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Podigni grešku ako je status kod neuspješan
        return response.json()

    def get_status_changes(order_id):
        url = f"http://www.akskurir.com/AKSVipService/Pracenje/{order_id}"
        headers = {
            'x-api-key': getenv("AKS_API_KEY")  # Pretpostavljamo da je potrebni API ključ
        }
        response = requests.get(url, headers=headers)
        print(response.json())
        response.raise_for_status()
        print()
        return response.json()

    def parse_current_status(json_data):
        status_info = {}
        if 'ErrorCode' in json_data:
            status_info['ErrorCode'] = json_data.get('ErrorCode', 'N/A')
            status_info['Status'] = json_data.get('Status', 'N/A')
        else:
            status_info['ErrorCode'] = 'N/A'
            status_info['Status'] = 'N/A'
        return status_info

    def parse_status_changes(json_data):
        status_changes = []
        if 'ErrorCode' in json_data and json_data['ErrorCode'] == 0:
            lst = json_data.get('StatusList', [])
            for status in lst:
                status_info = {
                    'Vreme': status.get('Vreme', 'N/A'),
                    'VremeInt': status.get('VremeInt', 'N/A'),
                    'Centar': status.get('Centar', 'N/A'),
                    'StatusOpis': status.get('StatusOpis', 'N/A'),
                    'NStatus': status.get('NStatus', 'N/A')
                }
                status_changes.append(status_info)
        return status_changes

    def get_multiple_orders_info(order_ids):
        orders_info = []
        for order_id in order_ids:
            try:
                # Dohvati trenutni status
                current_status_json = get_current_status(order_id)
                current_status = parse_current_status(current_status_json)
                
                # Dohvati promjene statusa
                status_changes_json = get_status_changes(order_id)
                status_changes = parse_status_changes(status_changes_json)
                
                # Sastavi informacije o narudžbi
                order_info = {
                    'order_id': order_id,
                    'current_status': current_status,
                    'status_changes': status_changes
                }
                orders_info.append(order_info)
            except requests.exceptions.RequestException as e:
                print(f"HTTP greška za narudžbu {order_id}: {e}")
                orders_info.append({'order_id': order_id, 'error': str(e)})
            except Exception as e:
                print(f"Greška za narudžbu {order_id}: {e}")
                orders_info.append({'order_id': order_id, 'error': str(e)})
        return orders_info

    # Glavna funkcija za dohvat informacija za sve narudžbe
    try:
        orders_info = get_multiple_orders_info(order_ids)
    except Exception as e:
        print(f"Greška pri dohvaćanju informacija o narudžbama: {e}")
        orders_info = "Nema narudžbi za zadane ID-eve."

    return orders_info


def order_aks(prompt):
    def extract_orders_from_string(text):
        # Definiramo regex obrazac za pronalazak cijelih brojeva sa 5 ili više cifara
        pattern = r'\b\d{5,}\b'
        orders = re.findall(pattern, text)
        return [int(order) for order in orders]

    order_ids = extract_orders_from_string(prompt)
    print(f"Pronađeni ID-evi narudžbi: {order_ids}")
    return API_search_aks(order_ids)

# Primjer korištenja:
if __name__ == "__main__":
    korisnicki_unos = "Molim provjerite status narudžbi 123456, 789012 i 345678."
    for i in range(100):
        rezultat = API_search_aks([968398 - i])