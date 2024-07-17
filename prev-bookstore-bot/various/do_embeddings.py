from openai import OpenAI
import json
import time

client = OpenAI()
err_log = ""

# Load JSON data from a file
with open("data.json", "r", encoding="utf-8") as stringio:
    data = json.load(stringio)

# Initialize lists outside the loop
texts = [item['description'] for item in data]
metadata = [{key: value for key, value in item.items() if key != 'description'} for item in data]

embed_model = "text-embedding-3-large"
batch_size = 100  # how many embeddings we create and insert at once

all_upserts = []

for i in range(0, len(data), batch_size):
    # Find end of batch
    i_end = min(len(data), i + batch_size)
    meta_batch = data[i:i_end]
    print(i)
    # Get texts to encode
    texts_batch = texts[i:i_end]

    # Create embeddings (try-except added to avoid RateLimitError)
    try:
        res = client.embeddings.create(input=texts_batch, model=embed_model)
    except Exception as e:
        done = False
        print(e)
        while not done:
            try:
                res = client.embeddings.create(input=texts_batch, model=embed_model)
                done = True
            except Exception as e:
                print(e, texts_batch)
                pass

    # Extract embeddings from response
    embeds = [item.embedding for item in res.data]

    if len(embeds) > 0:
        # Create JSON objects for upsert with the correct structure
        to_upsert = []
        for embed, meta in zip(embeds, meta_batch):
            upsert_item = {"embedding": embed}
            upsert_item.update(meta)
            to_upsert.append(upsert_item)
        
        all_upserts.extend(to_upsert)
    else:
        err_log += f"Error: {meta_batch}\n"

# Write all upserts to file once
with open("zaupsert.json", "w", encoding="utf-8") as file:
    file.write("[")
    for i, item in enumerate(all_upserts):
        json.dump(item, file, ensure_ascii=False)
        if i < len(all_upserts) - 1:  # Don't add a comma to the last item
            file.write(",\n")
    file.write("]")