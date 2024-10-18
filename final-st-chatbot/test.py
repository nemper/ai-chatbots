from datetime import datetime

data = [
    {
        'order_id': '9007968398',
        'current_status': {'ErrorCode': 0, 'Status': 'N/A'},
        'status_changes': [
            {'Vreme': '/Date(1727683730000)/', 'VremeInt': 560081330, 'Centar': 'Beograd', 'StatusOpis': 'Kreiranje VIP Naloga', 'NStatus': 90},
            {'Vreme': '/Date(1727695366000)/', 'VremeInt': 560092966, 'Centar': 'Beograd', 'StatusOpis': 'Preuzimanje Posiljke', 'NStatus': 100},
            {'Vreme': '/Date(1727726823000)/', 'VremeInt': 560124423, 'Centar': 'Centralni Magacin 1', 'StatusOpis': 'Ulazak Na Sortirnu Traku', 'NStatus': 120},
            {'Vreme': '/Date(1727726837000)/', 'VremeInt': 560124437, 'Centar': 'Cacak', 'StatusOpis': 'Utovar U Linijski Kamion', 'NStatus': 130},
            {'Vreme': '/Date(1727766571000)/', 'VremeInt': 560164171, 'Centar': 'Cacak', 'StatusOpis': 'Posiljka Na Isporuci', 'NStatus': 140},
            {'Vreme': '/Date(1727793771000)/', 'VremeInt': 560191371, 'Centar': 'Cacak', 'StatusOpis': 'Posiljka Isporucena', 'NStatus': 160},
            {'Vreme': '/Date(1727800685000)/', 'VremeInt': 560198285, 'Centar': 'Cacak', 'StatusOpis': 'Posiljka Isporucena', 'NStatus': 161}
        ]
    }
]

# Convert '/Date(...)' to a timestamp
def extract_timestamp(date_string):
    timestamp = int(date_string[6:-2]) / 1000  # Extract and convert milliseconds to seconds
    return datetime.fromtimestamp(timestamp)

# Sort the status changes by timestamp
sorted_status_changes = sorted(data[0]['status_changes'], key=lambda x: extract_timestamp(x['Vreme']))

# Get the last (most recent) status description
most_recent_status = sorted_status_changes[-1]['StatusOpis']

# Print the result
print(most_recent_status)
