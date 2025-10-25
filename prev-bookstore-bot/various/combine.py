import json
import pandas as pd

# Paths to the input files
csv_file_path = "C:\\Users\\djordje\\PyApps\\laguna\\datasource\\Delfi_slike_noimg_143465.csv"
jsonl_file_path = "./extracted_custom_ids_and_contents.jsonl"
output_jsonl_file_path = "./final_delfi.jsonl"

# Read the CSV file into a DataFrame
csv_df = pd.read_csv(csv_file_path)

# Convert the DataFrame to a dictionary for easy lookup
nav_id_to_slika = dict(zip(csv_df['Nav Id'], csv_df['Slika']))

# Process the JSONL file in chunks to handle large files efficiently
chunk_size = 10000  # Define a chunk size to process

# Open the output file in append mode
with open(output_jsonl_file_path, 'w', encoding='utf-8') as outfile:
    # Read and process the JSONL file in chunks
    with open(jsonl_file_path, 'r', encoding='utf-8') as infile:
        buffer = []
        for i, line in enumerate(infile):
            data = json.loads(line.strip())
            custom_id = data.get('custom_id')
            if custom_id in nav_id_to_slika:
                data['slika'] = nav_id_to_slika[custom_id]
            buffer.append(data)

            # Write the buffer to the output file in chunks
            if (i + 1) % chunk_size == 0:
                for item in buffer:
                    json.dump(item, outfile)
                    outfile.write('\n')
                buffer = []  # Clear the buffer

            # Print progress to the console
            print(f"Processed {i + 1} records", end='\r')

        # Write any remaining items in the buffer
        if buffer:
            for item in buffer:
                json.dump(item, outfile)
                outfile.write('\n')

print(f'Updated data saved to {output_jsonl_file_path}')
