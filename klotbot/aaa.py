import os
from pinecone import Index

class HybridQueryProcessor:
    def __init__(self):
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("Pinecone API key is not set")
        self.index = Index("your_index_name", api_key=api_key)
