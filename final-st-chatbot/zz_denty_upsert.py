import os
from typing import List, Dict
from pinecone.grpc import PineconeGRPC as Pinecone  # Ensure you're using the correct client

def connect_to_pinecone():
    pinecone_api_key = os.getenv('PINECONE_API_KEY')
    pinecone_host = "https://neo-positive-a9w1e6k.svc.apw5-4e34-81fa.pinecone.io"
    return Pinecone(api_key=pinecone_api_key, host=pinecone_host).Index(host=pinecone_host)

def list_all_ids(index: Pinecone, namespace: str) -> List[str]:
    """
    Retrieve all vector IDs from the specified namespace using the new list method.

    Args:
        index (Pinecone.Index): The Pinecone index object.
        namespace (str): The namespace to retrieve IDs from.

    Returns:
        List[str]: A list of all vector IDs.
    """
    all_ids = []
    try:
        for ids in index.list(namespace=namespace):
            all_ids.extend(ids)
            print(f"Fetched {len(all_ids)} IDs so far...")
    except Exception as e:
        print(f"An error occurred while listing IDs: {e}")
        raise e
    print(f"Total IDs fetched: {len(all_ids)}")
    return all_ids

def batch_generator(lst: List[str], batch_size: int):
    """
    Yield successive batches from the list.

    Args:
        lst (List[str]): The list to divide into batches.
        batch_size (int): The size of each batch.

    Yields:
        List[str]: A batch of vector IDs.
    """
    for i in range(0, len(lst), batch_size):
        yield lst[i:i + batch_size]

def update_metadata(index: Pinecone, namespace: str, vector_id: str, vector: List[float], metadata: Dict):
    """
    Upsert a single vector with updated metadata.

    Args:
        index (Pinecone.Index): The Pinecone index object.
        namespace (str): The namespace of the vector.
        vector_id (str): The ID of the vector.
        vector (List[float]): The vector values.
        metadata (Dict): The updated metadata.
    """
    try:
        index.upsert(
            vectors=[
                {
                    "id": vector_id,
                    "values": vector,
                    "metadata": metadata
                }
            ],
            namespace=namespace
        )
    except Exception as e:
        print(f"Failed to upsert vector ID {vector_id}: {e}")
        raise e

def main():
    # Connect to Pinecone
    index = connect_to_pinecone()
    print("Connected to Pinecone index successfully.")

    # Define your namespace
    namespace = "denty-serviser"

    # List all vector IDs in the namespace using the new list method
    all_ids = list_all_ids(index, namespace)

    # Process in batches
    for id_batch in batch_generator(all_ids, batch_size=100):
        # Fetch vectors with values and metadata
        try:
            fetch_response = index.fetch(ids=id_batch, namespace=namespace)
            vectors = fetch_response.get('vectors', {})
        except Exception as e:
            print(f"Failed to fetch vectors for batch: {e}")
            continue  # Skip this batch and continue with the next

        vectors_to_upsert = []

        for vec_id, vec_data in vectors.items():
            metadata = vec_data.get('metadata', {})
            # Assuming 'values' are returned by default
            vector = vec_data.get('values', [])
            if 'text' in metadata:
                # Rename 'text' to 'context'
                metadata['context'] = metadata.pop('text')
                
                # Prepare the upsert data
                vectors_to_upsert.append({
                    "id": vec_id,
                    "values": vector,
                    "metadata": metadata
                })

        if vectors_to_upsert:
            try:
                # Upsert the updated vectors
                index.upsert(vectors=vectors_to_upsert, namespace=namespace)
                print(f"Upserted {len(vectors_to_upsert)} vectors in this batch.")
            except Exception as e:
                print(f"Failed to upsert batch: {e}")
                continue  # Skip this batch and continue with the next
        else:
            print("No vectors to upsert in this batch.")

    print("Metadata update process completed successfully.")

if __name__ == "__main__":
    main()
