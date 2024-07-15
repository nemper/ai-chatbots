import json
import pandas as pd
import os

# Path to the uploaded JSONL file
#file_path = "C:\\Users\\djordje\\Downloads\\batch_PRbU1bw1wqMp91yWDCf1Xy2N_output.jsonl"
file_path = "C:\\Users\\djordje\\Downloads\\batch_mYjqcolWG7mEAZfFrs02lCvq_output.jsonl"
#file_path = "C:\\Users\\djordje\\Downloads\\batch_JxuA79CmvYwNQk7tk0BBpgQQ_output.jsonl"

# Initialize lists to hold custom_id and content
custom_ids = []
contents = []

# Read the JSONL file and extract custom_id and content from nested structure
with open(file_path, 'r', encoding='utf-8') as file:
    for line in file:
        data = json.loads(line.strip())
        custom_ids.append(data.get('custom_id'))
        response_body = data.get('response', {}).get('body', {})
        choices = response_body.get('data', [])
        
        if choices:
            content = choices[0].get('embedding', [])
        else:
            content = None
        contents.append(content)
        

# Create a DataFrame from the extracted data
df = pd.DataFrame({'custom_id': custom_ids, 'content': contents})

# # Path to the CSV file
csv_file_path = './slike_vektori.csv'
# print(df)
# Check if the file exists
if os.path.isfile(csv_file_path):
    # Append to the existing file
    df.to_csv(csv_file_path, mode='a', header=False, index=False)
else:
    # Write a new file
    df.to_csv(csv_file_path, index=False)
