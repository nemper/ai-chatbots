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
from myfunc.varvars_dicts import work_vars
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
    llm = ChatOpenAI(model=work_vars["names"]["openai_model"], temperature=0)
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
    

# in myfunc.prompts.py
class ConversationDatabase2:
    """
    A class to interact with a MSSQL database for storing and retrieving conversation data.
    """
    def __init__(self, host=None, user=None, password=None, database=None):
        self.host = host if host is not None else os.getenv('MYSQL_HOST')
        self.user = user if user is not None else os.getenv('MYSQL_USER')
        self.password = password if password is not None else os.getenv('MYSQL_PASS')
        self.database = database if database is not None else os.getenv('MYSQL_NAME')
        self.conn = None
        self.cursor = None

    def __enter__(self):
        self.conn = pyodbc.connect(
            driver='{ODBC Driver 18 for SQL Server}',
            server=self.host,
            database=self.database,
            uid=self.user,
            pwd=self.password,
            TrustServerCertificate='yes'
        )
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor is not None:
            self.cursor.close()
        if self.conn is not None:
            self.conn.close()
        if exc_type or exc_val or exc_tb:
            pass
    
    def create_sql_table(self):
        """
        Creates a table for storing conversations if it doesn't already exist.
        """
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
        print(f"Executing SQL: {check_table_sql}")
        self.cursor.execute(check_table_sql)
        self.conn.commit()
    
    def create_token_log_table(self):
        """
        Creates a table for storing token logs if it doesn't already exist.
        """
        check_table_sql = '''
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='chatbot_token_log' AND xtype='U')
        CREATE TABLE chatbot_token_log (
            id INT IDENTITY(1,1) PRIMARY KEY,
            app_id VARCHAR(255) NOT NULL,
            embedding_tokens INT NOT NULL,
            prompt_tokens INT NOT NULL,
            completion_tokens INT NOT NULL,
            stt_tokens INT NOT NULL,
            tts_tokens INT NOT NULL,
            model_name VARCHAR(255) NOT NULL,
            timestamp DATETIME DEFAULT GETDATE()
        )
        '''
        print(f"Executing SQL: {check_table_sql}")
        self.cursor.execute(check_table_sql)
        self.conn.commit()

    def add_sql_record(self, app_name, user_name, thread_id, conversation):
        """
        Adds a new record to the conversations table.
        
        Parameters:
        - app_name: The name of the application.
        - user_name: The name of the user.
        - thread_id: The thread identifier.
        - conversation: The conversation data as a list of dictionaries.
        """
        conversation_json = json.dumps(conversation)
        insert_sql = '''
        INSERT INTO conversations (app_name, user_name, thread_id, conversation) 
        VALUES (?, ?, ?, ?)
        '''
        print(f"Executing SQL: {insert_sql} with params: {(app_name, user_name, thread_id, conversation_json)}")
        self.cursor.execute(insert_sql, (app_name, user_name, thread_id, conversation_json))
        self.conn.commit()
    
    def query_sql_record(self, app_name, user_name, thread_id):
        """
        Modified to return the conversation record.
        """
        query_sql = '''
        SELECT conversation FROM conversations 
        WHERE app_name = ? AND user_name = ? AND thread_id = ?
        '''
        print(f"Executing SQL: {query_sql} with params: {(app_name, user_name, thread_id)}")
        self.cursor.execute(query_sql, (app_name, user_name, thread_id))
        result = self.cursor.fetchone()
        if result:
            return json.loads(result[0])
        else:
            return None
    
    def delete_sql_record(self, app_name, user_name, thread_id):
        """
        Deletes a conversation record based on app name, user name, and thread id.
        
        Parameters:
        - app_name: The name of the application.
        - user_name: The name of the user.
        - thread_id: The thread identifier.
        """
        delete_sql = '''
        DELETE FROM conversations
        WHERE app_name = ? AND user_name = ? AND thread_id = ?
        '''
        print(f"Executing SQL: {delete_sql} with params: {(app_name, user_name, thread_id)}")
        self.cursor.execute(delete_sql, (app_name, user_name, thread_id))
        self.conn.commit()
    
    def list_threads(self, app_name, user_name):
        """
        Lists all thread IDs for a given app name and user name.
    
        Parameters:
        - app_name: The name of the application.
        - user_name: The name of the user.

        Returns:
        - A list of thread IDs associated with the given app name and user name.
        """
        list_threads_sql = '''
        SELECT DISTINCT thread_id FROM conversations
        WHERE app_name = ? AND user_name = ?
        '''
        print(f"Executing SQL: {list_threads_sql} with params: {(app_name, user_name)}")
        self.cursor.execute(list_threads_sql, (app_name, user_name))
        threads = self.cursor.fetchall()
        return [thread[0] for thread in threads]  # Adjust based on your schema if needed
  
    def update_sql_record(self, app_name, user_name, thread_id, new_conversation):
        """
        Replaces the existing conversation data with new conversation data for a specific record in the conversations table.

        Parameters:
        - app_name: The name of the application.
        - user_name: The name of the user.
        - thread_id: The thread identifier.
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
        print(f"Executing SQL: {update_sql} with params: {(new_conversation_json, app_name, user_name, thread_id)}")
        self.cursor.execute(update_sql, (new_conversation_json, app_name, user_name, thread_id))
        self.conn.commit()

    def close(self):
        """
        Closes the database connection.
        """
        self.conn.close()

    def add_token_record_openai(self, app_id, model_name, embedding_tokens, prompt_tokens, completion_tokens, stt_tokens, tts_tokens):
        """
        Adds a new record to the database with the provided details.
        """
        insert_sql = """
        INSERT INTO chatbot_token_log (app_id, embedding_tokens, prompt_tokens, completion_tokens, stt_tokens, tts_tokens, model_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        values = (app_id, embedding_tokens, prompt_tokens, completion_tokens, stt_tokens, tts_tokens, model_name)
        print(f"Executing SQL: {insert_sql} with params: {values}")
        self.cursor.execute(insert_sql, values)
        self.conn.commit()
    
    def extract_token_sums_between_dates(self, start_date, end_date):
        """
        Extracts the summed token values between two given dates from the chatbot_token_log table.
        
        Parameters:
        - start_date: The start date in 'YYYY-MM-DD HH:MM:SS' format.
        - end_date: The end date in 'YYYY-MM-DD HH:MM:SS' format.

        Returns:
        - A dictionary containing the summed values for each token type.
        """
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
        
