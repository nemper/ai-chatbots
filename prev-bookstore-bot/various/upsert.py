import os
import json
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pinecone.grpc import PineconeGRPC as Pinecone

# Pinecone API key, host, and index details
api_key = os.getenv("PINECONE_API_KEY")  # Ensure your API key is set in the environment variables
host = "https://delfi-a9w1e6k.svc.aped-4627-b74a.pinecone.io"  # Replace with your Pinecone host
index_name = "delfi"
namespace = "korice"

# Path to the cleaned JSONL file
cleaned_file = r"C:\Users\Public\Desktop\NEMANJA\Other\cleaned.jsonl"

# Initialize Pinecone client
pc = Pinecone(api_key=api_key)
index = pc.Index(index_name)

def read_jsonl_file_in_chunks(file_path, batch_size=100):
    """Read data from JSONL file in chunks."""
    with open(file_path, 'r', encoding='utf-8-sig') as file:
        lines = []
        for line in file:
            lines.append(line)
            if len(lines) >= batch_size:
                yield lines
                lines = []
        if lines:
            yield lines

def process_chunk(api_key, host, index_name, namespace, lines):
    """Process a chunk of lines and prepare data for upserting."""
    pc = Pinecone(api_key=api_key, host=host)
    index = pc.Index(index_name)

    vectors = []
    for line in lines:
        try:
            data = json.loads(line)
            vector = {
                "id": str(uuid.uuid4()),
                "values": data["content"],
                "metadata": {key: value for key, value in data.items() if key != "content"}
            }
            # Add the "date" metadata
            vector["metadata"]["date"] = 20240716
            vectors.append(vector)
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError: {e} for line: {line}")
    
    index.upsert(vectors=vectors, namespace=namespace)
    return len(vectors)

def upsert_data(file_path, batch_size=100):
    """Upsert data in parallel."""
    with ProcessPoolExecutor() as executor:
        futures = []
        chunk_counter = 0
        for chunk in read_jsonl_file_in_chunks(file_path, batch_size):
            chunk_counter += 1
            print(f"Submitting chunk {chunk_counter} with {len(chunk)} vectors")
            futures.append(executor.submit(process_chunk, api_key, host, index_name, namespace, chunk))
        
        for future in as_completed(futures):
            try:
                result = future.result(timeout=300)  # Timeout after 5 minutes
                print(f"Upserted {result} vectors")
            except Exception as e:
                print(f"Exception: {e}")

if __name__ == "__main__":
    try:
        print("Starting data upsert...")
        upsert_data(cleaned_file)
        print("Data upserted successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
