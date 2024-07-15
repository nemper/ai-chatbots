import json
import pandas as pd

# Path to the uploaded JSONL file
file_path = './opis/response_data_50.jsonl'

# Initialize lists to hold custom_id and content
custom_ids = []
contents = []

# Read the JSONL file and extract custom_id and content from nested structure
with open(file_path, 'r', encoding='utf-8') as file:
    for line in file:
        data = json.loads(line.strip())
        custom_ids.append(data.get('custom_id'))
        response_body = data.get('response', {}).get('body', {})
        choices = response_body.get('choices', [])
        if choices:
            content = choices[0].get('message', {}).get('content')
        else:
            content = None
        contents.append(content)

# Create a DataFrame from the extracted data
df = pd.DataFrame({'custom_id': custom_ids, 'content': contents})

# Display the DataFrame
print(df)

# Save the DataFrame to a CSV file if needed
df.to_csv('./extracted_custom_ids_and_contents.csv', index=False)
