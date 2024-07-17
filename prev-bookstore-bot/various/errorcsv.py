import csv
import requests

# Function to check URL
def check_url(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return "Success"
        else:
            return f"Failed with status code {response.status_code}"
    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}"

# Read the input CSV file
input_csv_path = 'input.csv'
output_csv_path = 'output.csv'

with open(input_csv_path, 'r') as input_csv_file:
    reader = csv.DictReader(input_csv_file)
    rows = list(reader)
i=0
# Check each URL and add the result to the rows
for row in rows:
    i+=1
    row['Status'] = check_url(row['url'])
    print(row['url'], i, row['Status'])

# Write the updated rows to the output CSV file
with open(output_csv_path, 'w', newline='') as output_csv_file:
    fieldnames = reader.fieldnames + ['Status']
    writer = csv.DictWriter(output_csv_file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Output saved to {output_csv_path}")
