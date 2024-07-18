import openai
import os
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
from neo4j import GraphDatabase

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

def connect_to_neo4j(uri, user, password):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    return driver

def run_cypher_query(driver, query):
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
    
def generate_cypher_query(question):
    prompt = f"Translate the following user question into a Cypher query. Use the given structure of the database: {question}"
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that converts natural language questions into Cypher queries for a Neo4j database. The database has 3 node types: Author, Books, Genre, and 2 relationship types: BELONGS_TO and WROTE. Only Book nodes have properties: id, category, title, price, quantity, pages, and eBook. All node and relationship names are capitalized (e.g., Author, Book, Genre, BELONGS_TO, WROTE). Genre names are also capitalized (e.g., Drama, Fantastika). Please ensure that the generated Cypher query uses these exact capitalizations."},
            {"role": "user", "content": prompt}
        ]
    )
    cypher_query = response.choices[0].message.content.strip()

    # Uklanjanje nepotrebnog teksta oko upita
    if '```cypher' in cypher_query:
        cypher_query = cypher_query.split('```cypher')[1].split('```')[0].strip()

    return cypher_query

def get_descriptions_from_pinecone(ids, api_key, environment, index_name, namespace):
    # Initialize Pinecone
    pc = Pinecone(api_key=api_key, environment=environment)
    index = pc.Index(name=index_name)

    # Fetch the vectors by IDs
    results = index.fetch(ids=ids, namespace=namespace)
    descriptions = {}

    for id in ids:
        if id in results['vectors']:
            vector_data = results['vectors'][id]
            if 'metadata' in vector_data:
                descriptions[id] = vector_data['metadata'].get('text', 'No description available')
            else:
                descriptions[id] = 'Metadata not found in vector data.'
        else:
            descriptions[id] = 'No vector found with this ID.'
    
    return descriptions

def combine_data(book_data, descriptions):
    combined_data = []
    for book in book_data:
        book_id = book['id']
        description = descriptions.get(book_id, 'No description available')
        combined_entry = {**book, 'description': description}
        combined_data.append(combined_entry)
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

def main():
    # pinecone_index_name = "YOUR_PINECONE_INDEX_NAME"
    
    driver = connect_to_neo4j(uri, user, password)
    
    question = input("Enter your question: ")
    cypher_query = generate_cypher_query(question)
    print(f"Generated Cypher Query: {cypher_query}")
    
    book_data = run_cypher_query(driver, cypher_query)
    # print(book_data)
    
    book_ids = [book['id'] for book in book_data]
    # print(book_ids)
    descriptions = get_descriptions_from_pinecone(book_ids, pinecone_api_key, pinecone_environment, index_name, namespace)
    # print(descriptions)
    
    combined_data = combine_data(book_data, descriptions)
    display_results(combined_data)

if __name__ == "__main__":
    main()