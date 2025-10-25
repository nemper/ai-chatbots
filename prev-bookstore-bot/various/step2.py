import json
import os
from concurrent.futures import ProcessPoolExecutor

# Paths to the input files
combined_file = r"C:\Users\Public\Desktop\NEMANJA\Other\combined.jsonl"
combined2_file = r"C:\Users\Public\Desktop\NEMANJA\Other\combined2.jsonl"

# Path to the output file
output_file = r"C:\Users\Public\Desktop\NEMANJA\Other\merged.jsonl"

# Read combined.jsonl into a dictionary
def read_combined_jsonl(file_path):
    combined_data = {}
    with open(file_path, 'r', encoding='utf-8-sig') as file:
        for line in file:
            try:
                data = json.loads(line)
                combined_data[data['custom_id']] = data['body']['input']
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON in {file_path}: {e}")
    return combined_data

# Process a chunk of combined2.jsonl lines
def process_chunk(lines, combined_data):
    processed_lines = []
    for line in lines:
        try:
            data = json.loads(line)
            custom_id = data['custom_id']
            if custom_id in combined_data:
                data['description'] = combined_data[custom_id]
            processed_lines.append(json.dumps(data))
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON in chunk: {e}")
    return processed_lines

# Read and process combined2.jsonl in chunks
def process_file_in_chunks(input_file, chunk_size=1000):
    with open(input_file, 'r', encoding='utf-8-sig') as file:
        lines = []
        for line in file:
            lines.append(line)
            if len(lines) >= chunk_size:
                yield lines
                lines = []
        if lines:
            yield lines

# Main function to merge the data
def main():
    combined_data = read_combined_jsonl(combined_file)

    with open(output_file, 'w', encoding='utf-8-sig') as outfile:
        with ProcessPoolExecutor() as executor:
            futures = []
            for chunk in process_file_in_chunks(combined2_file):
                futures.append(executor.submit(process_chunk, chunk, combined_data))

            for future in futures:
                for processed_line in future.result():
                    outfile.write(processed_line + '\n')

if __name__ == "__main__":
    main()

print(f"Merged data written to {output_file}")
