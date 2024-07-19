from langchain_openai import OpenAIEmbeddings
from langchain_openai.chat_models import ChatOpenAI
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_community.vectorstores import Pinecone as LangPine
import re
import csv
import os
import json
import streamlit as st
from neo4j import GraphDatabase
from openai import OpenAI
from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder
from typing import List, Dict
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@st.cache_resource
def connect_to_neo4j():
    return GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASS")))

@st.cache_resource
def connect_to_pinecone():
    pinecone_api_key = os.getenv('PINECONE_API_KEY')
    pinecone_environment = os.getenv('PINECONE_ENVIRONMENT')
    index_name = 'delfi'
    pc = Pinecone(api_key=pinecone_api_key, environment=pinecone_environment)
    return pc.Index(index_name)

def graphp(pitanje):
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

    def get_descriptions_from_pinecone(ids, api_key=os.getenv('PINECONE_API_KEY'), host="https://delfi-a9w1e6k.svc.aped-4627-b74a.pinecone.io", index_name="delfi", namespace="opisi"):
        # Initialize Pinecone
        index = connect_to_pinecone

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

    def get_question():
        while True:
            question = pitanje
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
    
    driver = connect_to_neo4j()
    while True:
        question = get_question()
        cypher_query = generate_cypher_query(question)
        
        if is_valid_cypher(cypher_query):
            book_data = run_cypher_query(driver, cypher_query)
            if not has_id_field(book_data):
                return book_data

            book_ids = [book['id'] for book in book_data]
            context = get_descriptions_from_pinecone(book_ids)
            print("ABV", context)
            combined_data = combine_data(book_data, context)
            output = " "
            for data in combined_data:
                output += "Title: {data['title']}\n\n"
                output += f"Title: {data['title']}\n"
                output += f"Category: {data['category']}\n"
                output += f"Price: {data['price']}\n"
                output += f"Quantity: {data['quantity']}\n"
                output += f"Pages: {data['pages']}\n"
                output += f"eBook: {data['eBook']}\n"
                output += f"Description: {data['description']}\n\n\n"
            return output
        else:
            return "Traženi pojam nije jasan. Molimo pokušajte ponovo."


def pineg(pitanje):
    namespace = 'opisi'
    index = connect_to_pinecone()

    def run_cypher_query(id):
        driver = connect_to_neo4j()
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

    def dense_query(query, top_k=5, filter=None, namespace=namespace):
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

    query = pitanje.strip()
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
    output = " "
    for data in combined_data:
        output += "Title: {data['title']}\n\n"
        output += f"Title: {data['title']}\n"
        output += f"Category: {data['category']}\n"
        output += f"Price: {data['price']}\n"
        output += f"Quantity: {data['quantity']}\n"
        output += f"Pages: {data['pages']}\n"
        output += f"eBook: {data['eBook']}\n"
        output += f"Description: {data['description']}\n\n\n"
    return output


def order_search(id_porudzbine):
    match = re.search(r'\d{5,}', id_porudzbine)
    if not match:
        return "No integer found in the prompt."
    
    order_number = int(match.group())

    try:
        with open('orders.csv', mode='r', encoding='utf-8-sig') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)
            for row in csv_reader:
                if int(row[0]) == order_number:
                    return ", ".join(row)
        return f"Order number {order_number} not found in the CSV file."
    except FileNotFoundError:
        return "The file 'orders.csv' does not exist."
    except Exception as e:
        return f"An error occurred: {e}"


def SelfQueryDelfi(upit, api_key=None, environment=None, index_name='delfi', namespace='opisi', openai_api_key=None, host=None):
    """
    Executes a query against a Pinecone vector database using specified parameters or environment variables. 
    The function initializes the Pinecone and OpenAI services, sets up the vector store and metadata, 
    and performs a query using a custom retriever based on the provided input 'upit'.
    
    It is used for self-query on metadata.

    Parameters:
    upit (str): The query input for retrieving relevant documents.
    api_key (str, optional): API key for Pinecone. Defaults to PINECONE_API_KEY from environment variables.
    environment (str, optional): Pinecone environment. Defaults to PINECONE_API_KEY from environment variables.
    index_name (str, optional): Name of the Pinecone index to use. Defaults to 'positive'.
    namespace (str, optional): Namespace for Pinecone index. Defaults to NAMESPACE from environment variables.
    openai_api_key (str, optional): OpenAI API key. Defaults to OPENAI_API_KEY from environment variables.

    Returns:
    str: A string containing the concatenated results from the query, with each document's metadata and content.
         In case of an exception, it returns the exception message.

    Note:
    The function is tailored to a specific use case involving Pinecone and OpenAI services. 
    It requires proper setup of these services and relevant environment variables.
    """
    
    # Use the passed values if available, otherwise default to environment variables
    api_key = api_key if api_key is not None else os.getenv('PINECONE_API_KEY')
    environment = environment if environment is not None else os.getenv('PINECONE_API_KEY')
    # index_name is already defaulted to 'positive'
    namespace = namespace if namespace is not None else os.getenv("NAMESPACE")
    openai_api_key = openai_api_key if openai_api_key is not None else os.getenv("OPENAI_API_KEY")
    host = host if host is not None else os.getenv("PINECONE_HOST")
   
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    # prilagoditi stvanim potrebama metadata
    metadata_field_info = [
        AttributeInfo(name="authors", description="The author(s) of the document", type="string"),
        AttributeInfo(name="category", description="The category of the document", type="string"),
        AttributeInfo(name="chunk", description="The chunk number of the document", type="integer"),
        AttributeInfo(name="date", description="The date of the document", type="string"),
        AttributeInfo(name="eBook", description="Whether the document is an eBook", type="boolean"),
        AttributeInfo(name="genres", description="The genres of the document", type="string"),
        AttributeInfo(name="id", description="The unique ID of the document", type="string"),
        AttributeInfo(name="text", description="The main content of the document", type="string"),
        AttributeInfo(name="title", description="The title of the document", type="string"),
    ]

    # Define document content description
    document_content_description = "Content of the document"

    # Prilagoditi stvanom nazivu namespace-a
    vectorstore = LangPine.from_existing_index(
        index_name, embeddings, "context", namespace=namespace)

    # Initialize OpenAI embeddings and LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
    retriever = SelfQueryRetriever.from_llm(
        llm,
        vectorstore,
        document_content_description,
        metadata_field_info,
        enable_limit=True,
        verbose=True,
    )
    try:
        result = ""
        doc_result = retriever.get_relevant_documents(upit)
        for document in doc_result:
            result += "Authors: " + ", ".join(document.metadata['authors']) + "\n"
            result += "Category: " + document.metadata['category'] + "\n"
            result += "Chunk: " + str(document.metadata['chunk']) + "\n"
            result += "Date: " + document.metadata['date'] + "\n"
            result += "eBook: " + str(document.metadata['eBook']) + "\n"
            result += "Genres: " + ", ".join(document.metadata['genres']) + "\n"
            result += "ID: " + document.metadata['id'] + "\n"
            result += "Title: " + document.metadata['title'] + "\n"
            result += "Content: " + document.page_content + "\n\n"
    except Exception as e:
        result = e
    
    return result


class HybridQueryProcessor:
    """
    A processor for executing hybrid queries using Pinecone.

    This class allows the execution of queries that combine dense and sparse vector searches,
    typically used for retrieving and ranking information based on text data.

    Attributes:
        api_key (str): The API key for Pinecone.
        environment (str): The Pinecone environment setting.
        alpha (float): The weight used to balance dense and sparse vector scores.
        score (float): The score treshold.
        index_name (str): The name of the Pinecone index to be used.
        index: The Pinecone index object.
        namespace (str): The namespace to be used for the Pinecone index.
        top_k (int): The number of results to be returned.
            
    Example usage:
    processor = HybridQueryProcessor(api_key=environ["PINECONE_API_KEY"], 
                                 environment=environ["PINECONE_API_KEY"],
                                 alpha=0.7, 
                                 score=0.35,
                                 index_name='custom_index'), 
                                 namespace=environ["NAMESPACE"],
                                 top_k = 10 # all params are optional

    result = processor.hybrid_query("some query text")    
    """

    def __init__(self, **kwargs):
        """
        Initializes the HybridQueryProcessor with optional parameters.

        The API key and environment settings are fetched from the environment variables.
        Optional parameters can be passed to override these settings.

        Args:
            **kwargs: Optional keyword arguments:
                - api_key (str): The API key for Pinecone (default fetched from environment variable).
                - environment (str): The Pinecone environment setting (default fetched from environment variable).
                - alpha (float): Weight for balancing dense and sparse scores (default 0.5).
                - score (float): Weight for balancing dense and sparse scores (default 0.05).
                - index_name (str): Name of the Pinecone index to be used (default 'positive').
                - namespace (str): The namespace to be used for the Pinecone index (default fetched from environment variable).
                - top_k (int): The number of results to be returned (default 6).
        """
        self.api_key = kwargs.get('api_key', os.getenv('PINECONE_API_KEY'))
        self.environment = kwargs.get('environment', os.getenv('PINECONE_API_KEY'))
        self.alpha = kwargs.get('alpha', 0.5)  # Default alpha is 0.5
        self.score = kwargs.get('score', 0.05)  # Default score is 0.05
        self.index_name = kwargs.get('index', 'neo-positive')  # Default index is 'positive'
        self.namespace = kwargs.get('namespace', os.getenv("NAMESPACE"))  
        self.top_k = kwargs.get('top_k', 6)  # Default top_k is 6
        self.index = None
        self.host = os.getenv("PINECONE_HOST")
        self.check_namespace = True if self.namespace in ["brosureiuputstva", "servis"] else False
        self.init_pinecone()

    def init_pinecone(self):
        """
        Initializes the Pinecone connection and index.
        """
        pinecone=Pinecone(api_key=self.api_key, host=self.host)
        self.index = pinecone.Index(host=self.host)

    def hybrid_score_norm(self, dense, sparse):
        """
        Normalizes the scores from dense and sparse vectors using the alpha value.

        Args:
            dense (list): The dense vector scores.
            sparse (dict): The sparse vector scores.

        Returns:
            tuple: Normalized dense and sparse vector scores.
        """
        return ([v * self.alpha for v in dense], 
                {"indices": sparse["indices"], 
                 "values": [v * (1 - self.alpha) for v in sparse["values"]]})
    
    def hybrid_query(self, upit, top_k=None, filter=None, namespace=None):
        # Get embedding and unpack results
        dense = self.get_embedding(text=upit)

        # Use those results in another function call
        hdense, hsparse = self.hybrid_score_norm(
            sparse=BM25Encoder().fit([upit]).encode_queries(upit),
            dense=dense
        )

        query_params = {
            'top_k': top_k or self.top_k,
            'vector': hdense,
            'sparse_vector': hsparse,
            'include_metadata': True,
            'namespace': namespace or self.namespace
        }

        if filter:
            query_params['filter'] = filter

        response = self.index.query(**query_params)

        matches = response.to_dict().get('matches', [])

        results = []
        for match in matches:
            metadata = match.get('metadata', {})
            context = metadata.get('context', '')
            chunk = metadata.get('chunk')
            source = metadata.get('source')
            if self.check_namespace:
                filename = metadata.get('filename')
                url = metadata.get('url')
            try:
                score = match.get('score', 0)
            except:
                score = metadata.get('score', 0)
            if context:
                results.append({"page_content": context, "chunk": chunk, "source": source, "score": score})
                if self.check_namespace:
                    results[-1]["filename"] = filename
                    results[-1]["url"] = url
        
        return results
       
    def process_query_results(self, upit, dict=False):
        """
        Processes the query results and prompt tokens based on relevance score and formats them for a chat or dialogue system.
        Additionally, returns a list of scores for items that meet the score threshold.
        """
        tematika = self.hybrid_query(upit)
        if not dict:
            uk_teme = ""
            score_list = []
            for item in tematika:
                if item["score"] > self.score:
                    uk_teme += item["page_content"] + "\n\n"
                    score_list.append(item["score"])
                    if self.check_namespace:
                        uk_teme += f"Filename: {item['filename']}\n"
                        uk_teme += f"URL: {item['url']}\n\n"
            
            return uk_teme, score_list
        else:
            return tematika, []
        
    def get_embedding(self, text, model="text-embedding-3-large"):

        """
        Retrieves the embedding for the given text using the specified model.

        Args:
            text (str): The text to be embedded.
            model (str): The model to be used for embedding. Default is "text-embedding-3-large".

        Returns:
            list: The embedding vector of the given text.
            int: The number of prompt tokens used.
        """
        
        text = text.replace("\n", " ")
        result = client.embeddings.create(input=[text], model=model).data[0].embedding
       
        return result
    