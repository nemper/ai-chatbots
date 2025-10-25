import os
import json

# Directory containing the .jsonl files
directory = r"C:\Users\Public\Desktop\NEMANJA\Other\output_jsonl_files"

# Output file
output_file = os.path.join(directory, "combined2.jsonl")

# List to hold all lines from all files
combined_lines = []

# Read all .jsonl files in the directory
for filename in os.listdir(directory):
    if filename.endswith(".jsonl"):
        with open(os.path.join(directory, filename), 'r', encoding='utf-8-sig') as file:
            for line in file:
                combined_lines.append(line)

# Write all lines to the output file
with open(output_file, 'w', encoding='utf-8-sig') as outfile:
    for line in combined_lines:
        outfile.write(line)

print(f"Combined {len(combined_lines)} lines into {output_file}")
