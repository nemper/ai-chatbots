import requests

def get_bookstore_data():
    """
    Fetches bookstore data from the API and caches the result.
    Returns the API data if the request is successful, otherwise returns None.
    """
    url = "https://delfi.rs/api/bookstores"
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()['data']
    else:
        return None

def extract_bookstore_names(data):
    """
    Extracts bookstore names from the API data.
    
    Parameters:
    -----------
    data: list of dicts
        The list containing bookstore data dictionaries.
        
    Returns:
    --------
    list of str
        A list of bookstore names.
    """
    if data is None:
        return []
    
    return [bookstore['bookstoreName'] for bookstore in data]

# Fetch data from the API
bookstore_data = get_bookstore_data()

# Extract bookstore names
bookstore_names = extract_bookstore_names(bookstore_data)

# Print the names of the bookstores
print(bookstore_names)
