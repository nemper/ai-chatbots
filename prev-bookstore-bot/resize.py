import csv
import requests
from PIL import Image
from io import BytesIO

# Function to download and resize image
def download_and_resize_image(url, max_size_mb=19):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses
        
        img = Image.open(BytesIO(response.content))
        img_format = img.format  # Save the original format for later
        
        # Check the initial size
        initial_size_mb = len(response.content) / (1024 * 1024)
        
        if initial_size_mb > max_size_mb:
            # Calculate the new size maintaining the aspect ratio
            width, height = img.size
            aspect_ratio = height / width
            
            # Decrease the size to be under the max_size_mb
            while initial_size_mb > max_size_mb:
                width = int(width * 0.9)
                height = int(height * 0.9)
                img = img.resize((width, height), Image.ANTIALIAS)
                
                # Recheck the size
                buffer = BytesIO()
                img.save(buffer, format=img_format)
                initial_size_mb = len(buffer.getvalue()) / (1024 * 1024)
        
        return img, None
    
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {str(e)}"
    except Exception as e:
        return None, f"Error: {str(e)}"

# Read the input CSV file
input_csv_path = 'resize.csv'
output_csv_path = 'resized.csv'
image_save_path = './images/'

with open(input_csv_path, 'r') as input_csv_file:
    reader = csv.DictReader(input_csv_file)
    rows = list(reader)

# Process each URL and add the result to the rows
for row in rows:
    url = row['url']
    image, error = download_and_resize_image(url)
    print(row['url'])
    if image:
        image_name = f"{row['Nav Id']}.jpg"
        image_path = f"{image_save_path}{image_name}"
        image.save(image_path, format='JPEG')
        row['Status'] = "Success"
    else:
        row['Status'] = error

# Write the updated rows to the output CSV file
with open(output_csv_path, 'w', newline='') as output_csv_file:
    fieldnames = reader.fieldnames + ['Status']
    writer = csv.DictWriter(output_csv_file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Images saved and output saved to {output_csv_path}")
