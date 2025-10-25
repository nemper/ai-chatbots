import json
import os
import zipfile

# Path to the input JSONL file
input_jsonl_file_path = "C:\\Users\\djordje\\PyApps\\laguna\\final_delfi.jsonl"
output_directory = "./final_out"
zip_file_path = "output_jsonl_files.zip"

# Create the output directory if it doesn't exist
os.makedirs(output_directory, exist_ok=True)

# Function to write a list of JSON objects to a JSONL file
def write_jsonl(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as outfile:
        for item in data:
            json.dump(item, outfile)
            outfile.write('\n')

# Read the JSONL file and split it into separate JSONL files
batch_size = 10000  # Define a batch size to split the files
batch = []
file_count = 1

with open(input_jsonl_file_path, 'r', encoding='utf-8') as infile:
    for i, line in enumerate(infile):
        batch.append(json.loads(line.strip()))
        if (i + 1) % batch_size == 0:
            output_file_path = os.path.join(output_directory, f"batch_{file_count}.jsonl")
            write_jsonl(output_file_path, batch)
            batch = []
            file_count += 1

    # Write any remaining items in the batch
    if batch:
        output_file_path = os.path.join(output_directory, f"batch_{file_count}.jsonl")
        write_jsonl(output_file_path, batch)

# Create a zip file containing all the JSONL files
with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, _, files in os.walk(output_directory):
        for file in files:
            zipf.write(os.path.join(root, file), arcname=file)

print(f"All JSONL files have been saved in {zip_file_path}")
