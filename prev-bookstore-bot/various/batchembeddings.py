import json

#file_path = './opis/response_data_50.jsonl'
#file_path = './opis/response_data_drugi.jsonl' 
#file_path = './opis/response_data_treci.jsonl'  
#file_path = './opis/response_data_cetvrti.jsonl' 
file_path = './opis/response_data_resized.jsonl' 

# Create a batch JSON list
batch_list = []
with open(file_path, 'r', encoding="utf-8") as file:
    for line in file:
        data = json.loads(line.strip())
        nav_id = data.get('custom_id')
        response_body = data.get('response', {}).get('body', {})
        choices = response_body.get('choices', [])
        if choices:
            tekst = choices[0].get('message', {}).get('content')
        else:
            tekst = None
        
        batch_item = {
            "custom_id": nav_id,
            "method": "POST",
            "url": "/v1/embeddings",
            "body": {
                "model": "text-embedding-3-large",
                "input": tekst,
                "encoding_format": "float"
            }
        }
        
        batch_list.append(batch_item)

# Convert the batch list to JSON string for output
#out_file = "./zabatchembeddings/emb1.jsonl"
#out_file = "./zabatchembeddings/emb2.jsonl"
#out_file = "./zabatchembeddings/emb3.jsonl"
#out_file = "./zabatchembeddings/emb4.jsonl"
out_file = "./zabatchembeddings/emb5.jsonl"


with open(out_file, 'w', encoding='utf-8') as f:
    for item in batch_list:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')

print(f"Batch JSONL data has been saved to {out_file}")


