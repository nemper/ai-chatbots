import openai
import os
from openai import OpenAI
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from neo4j import GraphDatabase
from pinecone import Pinecone
from typing import List, Dict

# OpenAI API ključ
openai.gpt_api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI()

# Neo4j detalji
uri = "neo4j+ssc://d6013ca1.databases.neo4j.io"
user = "neo4j"
password = "2uosfTECcWia2FGlqa9k3Xqehm3-6X96NJCc1FrjZ3A"

# Define your Pinecone API key and environment
pinecone_api_key = os.getenv('PINECONE_API_KEY')
pinecone_environment = os.getenv('PINECONE_ENVIRONMENT')
index_name = 'delfi'
namespace = 'opisi'

# Initialize Pinecone
pc = Pinecone(api_key=pinecone_api_key, environment=pinecone_environment)
index = pc.Index(index_name)

def connect_to_neo4j(uri, user, password):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    return driver

def run_cypher_query(id):
    driver = connect_to_neo4j(uri, user, password)
    query = f"MATCH (b:Book) WHERE b.id = '{id}' RETURN b"
    with driver.session() as session:
        result = session.run(query)
        book_data = []
        for record in result:
            book_node = record['b']
            book_data.append({
                'id': book_node['id'],
                'title': book_node['title'],
                'category': book_node['category'],
                'price': book_node['price'],
                'quantity': book_node['quantity'],
                'pages': book_node['pages'],
                'eBook': book_node['eBook']
            })
        return book_data

def get_embedding(text, model="text-embedding-3-large"):
    response = client.embeddings.create(
        input=[text],
        model=model
    ).data[0].embedding
    # print(f"Embedding Response: {response}")
    
    return response

def dense_query(query, top_k=5, filter=None, namespace="opisi"):
    # Get embedding for the query
    dense = get_embedding(text=query)
    # print(f"Dense: {dense}")

    query_params = {
        'top_k': top_k,
        'vector': dense,
        'include_metadata': True,
        'namespace': namespace
    }

    response = index.query(**query_params)
    # print(f"Response: {response}")

    matches = response.to_dict().get('matches', [])
    # print(f"Matches: {matches}")

    return matches

def search_pinecone(query: str, top_k: int = 5) -> List[Dict]:
    # Dobij embedding za query
    query_embedding = dense_query(query)
    # print(f"Results: {query_embedding}")

    # Ekstraktuj id i text iz metapodataka rezultata
    matches = []
    for match in query_embedding:
        metadata = match['metadata']
        matches.append({
            'id': metadata['id'],
            'text': metadata['text']
        })
    
    # print(f"Matches: {matches}")
    return matches

def combine_data(book_data, descriptions):
    combined_data = []
    for book in book_data:
        combined_entry = {**book, 'description': descriptions}
        combined_data.append(combined_entry)
        print(f"Combined Entry: {combined_entry}")
    return combined_data

def display_results(combined_data):
    for data in combined_data:
        print(f"Title: {data['title']}")
        print(f"Category: {data['category']}")
        print(f"Price: {data['price']}")
        print(f"Quantity: {data['quantity']}")
        print(f"Pages: {data['pages']}")
        print(f"eBook: {data['eBook']}")
        print(f"Description: {data['description']}")
        print("\n")

def get_question():
    while True:
        question = input("Enter your search content: ")
        if question.strip():
            return question
        else:
            print("Pitanje ne može biti prazno. Molimo pokušajte ponovo.")

def main():
    query = get_question()
    search_results = search_pinecone(query)

    combined_results = []

    for result in search_results:
        
        additional_data = run_cypher_query(result['id'])
        
        # Korak 3: Kombinovanje podataka
        combined_data = combine_data(additional_data, result['text'])
        
        combined_results.append(combined_data)
    
    # return combined_results
    # driver = connect_to_neo4j(uri, user, password)
    
    # query = input("Enter your search content: ")

    # results = search_pinecone(query)
    # print(f"The type of the variable 'query' is: {type(results)}")
    # ids, descriptions = zip(*results)
    
    # if not ids:
    #     print("No matching books found.")
    #     return
    
    # ids_str = ', '.join([f"'{id}'" for id in ids])
    # cypher_query = f"MATCH (b:Book) WHERE b.id IN [{ids_str}] RETURN b"
    # book_data = run_cypher_query(driver, cypher_query)
    
    # combined_data = combine_data(book_data, descriptions)
        display_results(combined_data)

if __name__ == "__main__":
    main()