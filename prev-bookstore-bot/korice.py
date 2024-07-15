# kreira opise naslovnih strana. moze da s ekoristi html fajl ili stranica

from bs4 import BeautifulSoup
import re


# Function to read and parse HTML, then extract specific links
def extract_korice_links(html_file):
    # Read HTML file
    with open(html_file, 'r', encoding='utf-8') as file:
        html_content = file.read()

    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all 'a' tags and filter by 'href' containing 'korice'
    links = soup.find_all('a', href=re.compile(r'\bkorice\b'))

    # Extract the URLs
    urls = [link['href'] for link in links if 'href' in link.attrs]

    return urls

# Example usage
import json
from openai import OpenAI

html_file_path = 'view-source_https___laguna.rs_z148_zanr_klasici_laguna.html'
korice_urls = extract_korice_links(html_file_path)
lista_knjiga = []

client = OpenAI()

for korice_url in korice_urls:
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Whats in this image? These are book covers. Extract the book name and the book author name together with the detailed description of the image in JSON with values book_author, book_name, and book_cover_description. Please give the description in the Serbian language."},
                    {"type": "image_url", "image_url": {"url": korice_url}},
                ],
            }
        ],
        max_tokens=500,
    )

    # Assuming the response JSON is correctly formatted
    book_info = json.loads(response.choices[0].message.content)
    book_info['url'] = korice_url  # Add URL to the dictionary
    lista_knjiga.append(book_info)
    print(f"Radim link {korice_url}"  )

# Convert the list of dictionaries to JSON string for output
json_output = json.dumps(lista_knjiga, ensure_ascii=False, indent=4)
with open('book_data.json', 'w', encoding='utf-8') as f:
    f.write(json_output)
    print("JSON data has been saved to 'book_data.json'")


    
