from langchain_openai import OpenAIEmbeddings
from langchain_openai.chat_models import ChatOpenAI
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_community.vectorstores import Pinecone as LangPine
import re
import csv
import os
import json
import pyodbc
from neo4j import GraphDatabase
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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
    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL"), temperature=0.0)
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


def graph_search(pitanje):
    prompt = (
        "Preformuliši sledeće korisničko pitanje tako da bude jasno i razumljivo, uzimajući u obzir sledeće:\n"
        "1. Imamo 3 vrste nodova: Author, Book, Genre.\n"
        "2. Knjige imaju propertije: id, category, title, price, quantity, pages, eBook.\n"
        "3. Nazivi nodova uvek počinju velikim slovom. Posebno je važno da žanrovi budu pravilno napisani (npr. Fantastika, Drama, Religija i mitologija).\n"
        "4. Važno je razlikovati kategoriju od žanra. Kategorije su (npr. Knjiga, Film, Muzika, Udžbenik).\n"
        "5. Naslovi knjiga su često u različitim padežima, pa je potrebno prepoznati pravu reč.\n\n"
        "6. Korisnička pitanja mogu biti zbunjujuća, i važno je da prepoznamo da li se odnose na autora, knjigu ili žanr, i da ih ispravno formulišemo.\n\n"
        "Primeri:\n"
        "Pitanje: 'Interesuju me naslovi pisca Piramida.'\n"
        "Preformulisano pitanje: 'Interesuju me drugi naslovi autora knjige \"Piramide\".'\n\n"
        "Pitanje: 'Koji su autori napisali knjige u žanru drama?'\n"
        "Preformulisano pitanje: 'Koji su autori napisali knjige koje spadaju u žanr Drama?'\n\n"
        f"Pitanje: {pitanje}\n\n"
        "Preformulisano pitanje:"
    )
    
    try:
        response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that always writes in Serbian."},
            {"role": "user", "content": prompt}
        ]
    )

        preformulisano_pitanje = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Došlo je do greške: {e}")

    # Neo4j detalji

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASS")

    # Kreiranje Neo4j sesije
    driver = GraphDatabase.driver(uri, auth=(user, password))

    def translate_question_to_cypher(question):
        prompt = f"Translate the following user question into a Cypher query. Use the given structure of the database: {question}"
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": """You are a helpful assistant that converts natural language questions into Cypher queries for a Neo4j database. 
                 The database has 3 node types: Author, Books, Genre, and 2 relationship types: BELONGS_TO and WROTE. 
                 Only Book nodes have properties: id, category, title, price, quantity, pages, and eBook. All node and relationship names are capitalized (e.g., Author, Book, Genre, BELONGS_TO, WROTE). 
                 Genre names are also capitalized (e.g., Drama, Fantastika). Please ensure that the generated Cypher query uses these exact capitalizations."""},
                {"role": "user", "content": prompt}
            ]
        )
        cypher_query = response.choices[0].message.content.strip()

        # Uklanjanje nepotrebnog teksta oko upita
        if '```cypher' in cypher_query:
            cypher_query = cypher_query.split('```cypher')[1].split('```')[0].strip()

        return cypher_query

    def execute_cypher_query(cypher_query):
        with driver.session() as session:
            result = session.run(cypher_query)
            return [record.data() for record in result]
        

    result = execute_cypher_query(translate_question_to_cypher(preformulisano_pitanje))
    return json.dumps(result, ensure_ascii=False, indent=2)
 
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
    


class ConversationDatabase:
    """
    A class to interact with a MSSQL database for storing and retrieving conversation data.
    """
    def __init__(self, host=None, user=None, password=None, database=None):
        self.host = host if host is not None else os.getenv('MSSQL_HOST')
        self.user = user if user is not None else os.getenv('MSSQL_USER')
        self.password = password if password is not None else os.getenv('MSSQL_PASS')
        self.database = database if database is not None else os.getenv('MSSQL_DB')
        self.conn = None
        self.cursor = None

    def __enter__(self):
        try:
            self.conn = pyodbc.connect(
                driver='{ODBC Driver 18 for SQL Server}',
                server=self.host,
                database=self.database,
                uid=self.user,
                pwd=self.password,
                TrustServerCertificate='yes'
            )
            self.cursor = self.conn.cursor()
            print("Database connection established.")
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor is not None:
            self.cursor.close()
        if self.conn is not None:
            self.conn.close()
        if exc_type or exc_val or exc_tb:
            print(f"Exception occurred: {exc_type}, {exc_val}")
            pass

    def create_sql_table(self):
        check_table_sql = '''
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='conversations' AND xtype='U')
        CREATE TABLE conversations (
            id INT IDENTITY(1,1) PRIMARY KEY,
            app_name VARCHAR(255) NOT NULL,
            user_name VARCHAR(255) NOT NULL,
            thread_id VARCHAR(255) NOT NULL,
            conversation NVARCHAR(MAX) NOT NULL
        )
        '''
        try:
            print(f"Executing SQL: {check_table_sql}")
            self.cursor.execute(check_table_sql)
            self.conn.commit()
        except Exception as e:
            print(f"Error creating table: {e}")
            raise

    def update_sql_record(self, app_name, user_name, thread_id, new_conversation):
        """
        Replaces the existing conversation data with new conversation data for a specific record in the conversations table.

        Parameters:
        - app_name: The name of the application.
        - user_name: The name of the user.
        - thread_id: The thread identifier (string).
        - new_conversation: The new conversation data to replace as a list of dictionaries.
        """

        # Convert the new conversation to JSON format
        new_conversation_json = json.dumps(new_conversation)

        # Update the record with the new conversation
        update_sql = '''
        UPDATE conversations
        SET conversation = ?
        WHERE app_name = ? AND user_name = ? AND thread_id = ?
        '''
        try:
            print(f"Executing SQL: {update_sql} with params: {(new_conversation_json, app_name, user_name, thread_id)}")
            self.cursor.execute(update_sql, (new_conversation_json, app_name, user_name, thread_id))
            self.conn.commit()
            print("Update successful.")
            affected_rows = self.cursor.rowcount
            print(f"Number of affected rows: {affected_rows}")
            if affected_rows == 0:
                print("No rows were updated. Please check if the record exists.")
        except pyodbc.Error as e:
            print(f"Error updating record: {e}")
            self.conn.rollback()

    def record_exists(self, app_name, user_name, thread_id):
        """
        Checks if a record exists in the conversations table.

        Parameters:
        - app_name: The name of the application.
        - user_name: The name of the user.
        - thread_id: The thread identifier (string).

        Returns:
        - Boolean indicating if the record exists.
        """
        check_sql = '''
        SELECT COUNT(*)
        FROM conversations
        WHERE app_name = ? AND user_name = ? AND thread_id = ?
        '''
        self.cursor.execute(check_sql, (app_name, user_name, thread_id))
        count = self.cursor.fetchone()[0]
        return count > 0

    def add_sql_record(self, app_name, user_name, thread_id, conversation):
        """
        Adds a new record to the conversations table.

        Parameters:
        - app_name: The name of the application.
        - user_name: The name of the user.
        - thread_id: The thread identifier (string).
        - conversation: The conversation data as a list of dictionaries.
        """

        conversation_json = json.dumps(conversation)
        insert_sql = '''
        INSERT INTO conversations (app_name, user_name, thread_id, conversation) 
        VALUES (?, ?, ?, ?)
        '''
        try:
            print(f"Executing SQL: {insert_sql} with params: {(app_name, user_name, thread_id, conversation_json)}")
            self.cursor.execute(insert_sql, (app_name, user_name, thread_id, conversation_json))
            self.conn.commit()
            print("Insert successful.")
        except pyodbc.Error as e:
            print(f"Error adding record: {e}")
            self.conn.rollback()

    def update_or_insert_sql_record(self, app_name, user_name, thread_id, new_conversation):
        if self.record_exists(app_name, user_name, thread_id):
            self.update_sql_record(app_name, user_name, thread_id, new_conversation)
        else:
            self.add_sql_record(app_name, user_name, thread_id, new_conversation)


    def query_sql_record(self, app_name, user_name, thread_id):
        query_sql = '''
        SELECT conversation FROM conversations 
        WHERE app_name = ? AND user_name = ? AND thread_id = ?
        '''
        try:
            print(f"Executing SQL: {query_sql} with params: {(app_name, user_name, thread_id)}")
            self.cursor.execute(query_sql, (app_name, user_name, thread_id))
            result = self.cursor.fetchone()
            if result:
                return json.loads(result[0])
            else:
                return None
        except Exception as e:
            print(f"Error querying record: {e}")
            raise

    def delete_sql_record(self, app_name, user_name, thread_id):
        delete_sql = '''
        DELETE FROM conversations
        WHERE app_name = ? AND user_name = ? AND thread_id = ?
        '''
        try:
            print(f"Executing SQL: {delete_sql} with params: {(app_name, user_name, thread_id)}")
            self.cursor.execute(delete_sql, (app_name, user_name, thread_id))
            self.conn.commit()
        except Exception as e:
            print(f"Error deleting record: {e}")
            raise

    def list_threads(self, app_name, user_name):
        list_threads_sql = '''
        SELECT DISTINCT thread_id FROM conversations
        WHERE app_name = ? AND user_name = ?
        '''
        try:
            print(f"Executing SQL: {list_threads_sql} with params: {(app_name, user_name)}")
            self.cursor.execute(list_threads_sql, (app_name, user_name))
            threads = self.cursor.fetchall()
            return [thread[0] for thread in threads]
        except Exception as e:
            print(f"Error listing threads: {e}")
            raise

    def add_token_record_openai(self, app_id, model_name, embedding_tokens, prompt_tokens, completion_tokens, stt_tokens, tts_tokens):
        insert_sql = """
        INSERT INTO chatbot_token_log (app_id, embedding_tokens, prompt_tokens, completion_tokens, stt_tokens, tts_tokens, model_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        values = (app_id, embedding_tokens, prompt_tokens, completion_tokens, stt_tokens, tts_tokens, model_name)
        try:
            print(f"Executing SQL: {insert_sql} with params: {values}")
            self.cursor.execute(insert_sql, values)
            self.conn.commit()
        except Exception as e:
            print(f"Error adding token record: {e}")
            raise

    def extract_token_sums_between_dates(self, start_date, end_date):
        query_sql = """
        SELECT 
            SUM(embedding_tokens) as total_embedding_tokens, 
            SUM(prompt_tokens) as total_prompt_tokens, 
            SUM(completion_tokens) as total_completion_tokens, 
            SUM(stt_tokens) as total_stt_tokens, 
            SUM(tts_tokens) as total_tts_tokens 
        FROM chatbot_token_log 
        WHERE timestamp BETWEEN ? AND ?
        """
        try:
            print(f"Executing SQL: {query_sql} with params: {(start_date, end_date)}")
            self.cursor.execute(query_sql, (start_date, end_date))
            result = self.cursor.fetchone()
            if result:
                return {
                    "total_embedding_tokens": int(result[0]),
                    "total_prompt_tokens": int(result[1]),
                    "total_completion_tokens": int(result[2]),
                    "total_stt_tokens": int(result[3]),
                    "total_tts_tokens": int(result[4]),
                }
            else:
                return None
        except Exception as e:
            print(f"Error extracting token sums: {e}")
            raise

    def close(self):
        if self.conn:
            self.conn.close()
            print("Database connection closed.")

        

from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder
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
        self.check_namespace = True if self.namespace in ["brosureiuputstva", "servis", "casopis"] else False
        self.init_pinecone()

    def init_pinecone(self):
        """
        Initializes the Pinecone connection and index.
        """
        pinecone=Pinecone(api_key=self.api_key, host=self.host)
        self.index = pinecone.Index(host=self.host)

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

    def process_query_parent_results(self, upit):
        """
        Processes the query results and returns top result with source name, chunk number, and page content.
        It is used for parent-child queries.

        Args:
            upit (str): The original query text.
    
        Returns:
            tuple: Formatted string for chat prompt, source name, and chunk number.
        """
        tematika = self.hybrid_query(upit)

        # Check if there are any matches
        if not tematika:
            return "No results found", None, None

        # Extract information from the top result
        top_result = tematika[0]
        top_context = top_result.get('page_content', '')
        top_chunk = top_result.get('chunk')
        top_source = top_result.get('source')

        return top_context, top_source, top_chunk

     
    def search_by_source(self, upit, source_result, top_k=5, filter=None):
        """
        Perform a similarity search for documents related to `upit`, filtered by a specific `source_result`.
        
        :param upit: Query string.
        :param source_result: source to filter the search results.
        :param top_k: Number of top results to return.
        :param filter: Additional filter criteria for the query.
        :return: Concatenated page content of the search results.
        """
        filter_criteria = filter or {}
        filter_criteria['source'] = source_result
        top_k = top_k or self.top_k
        
        doc_result = self.hybrid_query(upit, top_k=top_k, filter=filter_criteria, namespace=self.namespace)
        result = "\n\n".join(document['page_content'] for document in doc_result)
    
        return result
        
       
    def search_by_chunk(self, upit, source_result, chunk, razmak=3, top_k=20, filter=None):
        """
        Perform a similarity search for documents related to `upit`, filtered by source and a specific chunk range.
        Namespace for store can be different than for the original search.
    
        :param upit: Query string.
        :param source_result: source to filter the search results.
        :param chunk: Target chunk number.
        :param razmak: Range to consider around the target chunk.
        :param top_k: Number of top results to return.
        :param filter: Additional filter criteria for the query.
        :return: Concatenated page content of the search results.
        """
        
        manji = chunk - razmak
        veci = chunk + razmak
    
        filter_criteria = filter or {}
        filter_criteria = {
            'source': source_result,
            '$and': [{'chunk': {'$gte': manji}}, {'chunk': {'$lte': veci}}]
        }
        
        
        doc_result = self.hybrid_query(upit, top_k=top_k, filter=filter_criteria, namespace=self.namespace)

        # Sort the doc_result based on the 'chunk' value
        sorted_doc_result = sorted(doc_result, key=lambda document: document.get('chunk', float('inf')))

        # Generate the result string
        result = " ".join(document.get('page_content', '') for document in sorted_doc_result)
    
        return result
    
