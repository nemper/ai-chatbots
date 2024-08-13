import nltk
import os

# Define the target directory for NLTK data
nltk_data_dir = os.path.join(os.getcwd(), 'nltk_data')

# Create the directory if it doesn't exist
if not os.path.exists(nltk_data_dir):
    os.makedirs(nltk_data_dir)

# Download the 'punkt' tokenizer data to this directory
nltk.download('punkt', download_dir=nltk_data_dir)