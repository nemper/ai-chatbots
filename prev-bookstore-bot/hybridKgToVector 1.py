import sys
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
        data = []
        for record in result:
            for key in record.keys():
                node = record[key]
                if key == 'b':
                    data.append({
                        'id': node['id'],
                        'title': node['title'],
                        'category': node['category'],
                        'price': node['price'],
                        'quantity': node['quantity'],
                        'pages': node['pages'],
                        'eBook': node['eBook']
                    })
                elif key == 'a':
                    data.append({
                        'name': node['name']
                    })
                elif key == 'g':
                    data.append({
                        'name': node['name']
                    })
        # print(f"Data: {data}")
        return data
    
def generate_cypher_query(question):
    prompt = f"Translate the following user question into a Cypher query. Use the given structure of the database: {question}"
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
        "role": "system",
        "content": (
            "You are a helpful assistant that converts natural language questions into Cypher queries for a Neo4j database."
            "The database has 3 node types: Author, Books, Genre, and 2 relationship types: BELONGS_TO and WROTE."
            "Only Book nodes have properties: id, category, title, price, quantity, pages, and eBook."
            "All node and relationship names are capitalized (e.g., Author, Book, Genre, BELONGS_TO, WROTE)."
            "Genre names are also capitalized (e.g., Drama, Fantastika). Please ensure that the generated Cypher query uses these exact capitalizations."
            "Limit the returned results to 5 records."
            "Here is an example user question and the corresponding Cypher query: "
            "Example user question: 'Pronađi knjigu Da Vinčijev kod.' "
            "Cypher query: MATCH (b:Book) WHERE toLower(b.title) = toLower('Da Vinčijev kod') RETURN b LIMIT 5."
        )
    },
            {"role": "user", "content": prompt}
        ]
    )
    cypher_query = response.choices[0].message.content.strip()
    # print(f"Generated Not Cleaned Cypher Query: {cypher_query}")

    # Uklanjanje nepotrebnog teksta oko upita
    if '```cypher' in cypher_query:
        cypher_query = cypher_query.split('```cypher')[1].split('```')[0].strip()
    
    # Uklanjanje tačke ako je prisutna na kraju
    if cypher_query.endswith('.'):
        cypher_query = cypher_query[:-1].strip()

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

def get_question():
    while True:
        question = input("Enter your question: ")
        if question.strip():
            return question
        else:
            print("Pitanje ne može biti prazno. Molimo pokušajte ponovo.")

def is_valid_cypher(cypher_query):
    # Provera validnosti Cypher upita (osnovna provera)
    if not cypher_query or "MATCH" not in cypher_query.upper():
        # print("Cypher upit nije validan.")
        return False
    # print("Cypher upit je validan.")
    return True

def has_id_field(data):
    # Provera da li vraćeni podaci sadrže 'id' polje
    return all('id' in item for item in data)

def formulate_answer_with_llm(question, graph_data):
    input_text = f"Pitanje: '{question}'\nPodaci iz grafa: {graph_data}\nMolimo formulišite odgovor na osnovu ovih podataka."
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that formulates answers based on given data. You have been provided with a user question and data returned from a graph database. Please formulate an answer based on these inputs."},
            {"role": "user", "content": input_text}
        ]
    )
    return response.choices[0].message.content.strip()

def main():  
    driver = connect_to_neo4j(uri, user, password)
    
    while True:
        question = get_question()
        cypher_query = generate_cypher_query(question)
        print(f"Generated Cypher Query: {cypher_query}")
        
        if is_valid_cypher(cypher_query):
            try:
                book_data = run_cypher_query(driver, cypher_query)
                # print(f"Book Data: {book_data}")
                # print(has_id_field(book_data))

                if not has_id_field(book_data):
                    # print("Vraćeni podaci ne sadrže 'id' polje.")
                    answer = formulate_answer_with_llm(question, book_data)
                    print(answer)
                    sys.exit()

                book_ids = [book['id'] for book in book_data]
                descriptions = get_descriptions_from_pinecone(book_ids, pinecone_api_key, pinecone_environment, index_name, namespace)
                combined_data = combine_data(book_data, descriptions)
                display_results(combined_data)
                return
            except Exception as e:
                print(f"Greška pri izvršavanju upita: {e}. Molimo pokušajte ponovo.")
        else:
            print("Traženi pojam nije jasan. Molimo pokušajte ponovo.")

if __name__ == "__main__":
    main()