import json
import os

# Path to the uploaded JSONL file
file_path = "C:\\Users\\djordje\\Downloads\\batch_PRbU1bw1wqMp91yWDCf1Xy2N_output.jsonl"

# Path to the output JSONL file
output_file_path = './extracted_custom_ids_and_contents.jsonl'

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

# Create the list of dictionaries to save in JSONL format
data_to_save = [{'custom_id': custom_id, 'content': content} for custom_id, content in zip(custom_ids, contents)]

# Write to the output JSONL file
with open(output_file_path, 'a', encoding='utf-8') as outfile:
    for item in data_to_save:
        json.dump(item, outfile)
        outfile.write('\n')

print(f'Data saved to {output_file_path}')
