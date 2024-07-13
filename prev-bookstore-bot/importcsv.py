import csv
import json

# Function to read URLs and Nav IDs from a CSV file
def read_csv_file(csv_file):
    urls = []
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            urls.append({
                "id": row["Nav Id"].strip(),
                "url": row["Slika"].strip()
            })
    return urls

# Example usage

#csv_file_path = 'prvih_50.csv'  # Path to your CSV file
#csv_file_path = 'delfidrugi.csv'  # Path to your CSV file
#csv_file_path = 'delfitreci.csv'  # Path to your CSV file
csv_file_path = 'delficetvrti.csv'  # Path to your CSV file

korice_data = read_csv_file(csv_file_path)

# Create a batch JSON list
batch_list = []

for data in korice_data:
    korice_url = data["url"]
    nav_id = data["id"]
    
    batch_item = {
        "custom_id": nav_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": "You are an expert in describing images. You always describe images in the Serbian language."}
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What's in this image? These are book covers. Extract the book name and the book author name together with the detailed description of the image in JSON with values book_author, book_name, and book_cover_description."},
                        {"type": "image_url", "image_url": {"url": korice_url}}
                    ]
                }
            ],
            "max_tokens": 300
        }
    }
    
    batch_list.append(batch_item)

# Convert the batch list to JSON string for output
#out_file = "batch_50.jsonl"
#out_file = "delfi_drugi.jsonl"
#out_file = "delfi_treci.jsonl"
out_file = "delfi_cetvrti.jsonl"

with open(out_file, 'w', encoding='utf-8') as f:
    for item in batch_list:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')

print(f"Batch JSONL data has been saved to {out_file}")