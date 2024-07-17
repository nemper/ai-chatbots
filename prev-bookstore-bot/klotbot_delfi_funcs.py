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
        

class PromptDatabase:
    """
    A class to interact with an MSSQL database for storing and retrieving prompt templates.
    """
    def __init__(self, host=None, user=None, password=None, database=None):
        """
        Initializes the connection details for the database, with the option to use environment variables as defaults.
        """
        self.host = host if host is not None else os.getenv('MSSQL_HOST')
        self.user = user if user is not None else os.getenv('MSSQL_USER')
        self.password = password if password is not None else os.getenv('MSSQL_PASS')
        self.database = database if database is not None else os.getenv('MSSQL_NAME')
        self.conn = None
        self.cursor = None
        
    def __enter__(self):
        """
        Establishes the database connection and returns the instance itself when entering the context.
        """
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
        """
        Closes the database connection and cursor when exiting the context.
        Handles any exceptions that occurred within the context.
        """
        if self.cursor is not None:
            self.cursor.close()
        if self.conn is not None:
            self.conn.close()
        if exc_type or exc_val or exc_tb:
            pass

    def query_sql_prompt_strings(self, prompt_names):
        """
        Fetches the existing prompt strings for a given list of prompt names, maintaining the order of prompt_names.
        """
        order_clause = "ORDER BY CASE PromptName "
        for idx, name in enumerate(prompt_names):
            order_clause += f"WHEN ? THEN {idx} "
        order_clause += "END"

        query = f"""
        SELECT PromptString FROM PromptStrings
        WHERE PromptName IN ({','.join(['?'] * len(prompt_names))})
        """ + order_clause

        params = tuple(prompt_names) + tuple(prompt_names)  # prompt_names repeated for both IN and ORDER BY
        self.cursor.execute(query, params)
        results = self.cursor.fetchall()
        return [result[0] for result in results] if results else []

    def get_records(self, query, params=None):
        try:
            if self.conn is None:
                self.__enter__()
            self.cursor.execute(query, params)
            records = self.cursor.fetchall()
            return records
        except Exception as e:
            return []

    def get_records_from_column(self, table, column):
        """
        Fetch records from a specified column in a specified table.
        """
        query = f"SELECT DISTINCT {column} FROM {table}"
        records = self.get_records(query)
        return [record[0] for record in records] if records else []

    def get_prompts_by_names(self, variable_names, prompt_names):
        prompt_strings = self.query_sql_prompt_strings(prompt_names)
        prompt_variables = dict(zip(variable_names, prompt_strings))
        return prompt_variables

    def get_all_records_from_table(self, table_name):
        """
        Fetch all records and all columns for a given table.
        :param table_name: The name of the table from which to fetch records.
        :return: A pandas DataFrame with all records and columns from the specified table.
        """
        query = f"SELECT * FROM {table_name}"
        try:
            self.cursor.execute(query)
            records = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            return records, columns
        except Exception as e:
            print(f"Failed to fetch records: {e}")
            return [], []  # Return an empty DataFrame in case of an error

    def get_prompts_for_username(self, username):
        """
        Fetch all prompt texts and matching variable names for a given username.
        :param username: The username (or partial username) for which to fetch prompt texts and variable names.
        :return: A pandas DataFrame with the prompt texts and matching variable names.
        """
        query = """
        SELECT ps.PromptName, ps.PromptString, pv.VariableName, pf.Filename, pf.FilePath, u.Username 
        FROM PromptStrings ps
        JOIN PromptVariables pv ON ps.VariableID = pv.VariableID
        JOIN PythonFiles pf ON ps.VariableFileID = pf.FileID
        JOIN Users u ON ps.UserID = u.UserID
        WHERE u.Username LIKE ?
        """
        params = (f"%{username}%",)
        records = self.get_records(query, params)
        return records

    def add_record(self, table, **fields):
        columns = ', '.join(fields.keys())
        placeholders = ', '.join(['?'] * len(fields))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        try:
            self.cursor.execute(query, tuple(fields.values()))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            print(f"Error in add_record: {e}")
            return None

    def add_new_record(self, username, filename, variablename, promptstring, promptname, comment):
        """
        Adds a new record to the database, handling the relationships between users, files, variables, and prompts.
        """
        try:
            # Fetch UserID based on username
            self.cursor.execute("SELECT UserID FROM Users WHERE Username = ?", (username,))
            user_result = self.cursor.fetchone()
            user_id = user_result[0] if user_result else None

            # Fetch VariableID based on variablename
            self.cursor.execute("SELECT VariableID FROM PromptVariables WHERE VariableName = ?", (variablename,))
            variable_result = self.cursor.fetchone()
            variable_id = variable_result[0] if variable_result else None

            # Fetch FileID based on filename
            self.cursor.execute("SELECT FileID FROM PythonFiles WHERE Filename = ?", (filename,))
            file_result = self.cursor.fetchone()
            file_id = file_result[0] if file_result else None

            # Ensure all IDs are found
            if not all([user_id, variable_id, file_id]):
                return "Error: Missing UserID, VariableID, or VariableFileID."

            # Correctly include FileID in the insertion command
            self.cursor.execute(
                "INSERT INTO PromptStrings (PromptString, PromptName, Comment, UserID, VariableID, VariableFileID) VALUES (?, ?, ?, ?, ?, ?)",
                (promptstring, promptname, comment, user_id, variable_id, file_id)
            )

            self.conn.commit()
            return "Record added successfully."
        except Exception as e:
            self.conn.rollback()
            return f"Failed to add the record: {e}"

    def update_record(self, table, fields, condition):
        """
        Updates records in the specified table based on a condition.
    
        :param table: The name of the table to update.
        :param fields: A dictionary of column names and their new values.
        :param condition: A tuple containing the condition string and its values (e.g., ("UserID = ?", [user_id])).
        """
        set_clause = ', '.join([f"{key} = ?" for key in fields.keys()])
        values = list(fields.values()) + condition[1]
    
        query = f"UPDATE {table} SET {set_clause} WHERE {condition[0]}"
    
        try:
            self.cursor.execute(query, values)
            self.conn.commit()
            return "Record updated successfully"
        except Exception as e:
            self.conn.rollback()
            return f"Error in update_record: {e}"
        
    def delete_prompt_by_name(self, promptname):
        """
        Delete a prompt record from PromptStrings by promptname.
        This method also handles deletions or updates in related tables if necessary.
        """
        delete_query = "DELETE FROM PromptStrings WHERE PromptName = ?"
        try:
            if self.conn is None:
                self.__enter__()
            self.cursor.execute(delete_query, (promptname,))
            self.conn.commit()
            return f"Prompt '{promptname}' deleted successfully."
        except Exception as e:
            self.conn.rollback()
            return f"Error deleting prompt '{promptname}': {e}"
    
    def update_prompt_record(self, promptname, new_promptstring, new_comment):
        """
        Updates the PromptString and Comment fields of an existing prompt record identified by PromptName.
    
        :param promptname: The name of the prompt to update.
        :param new_promptstring: The new value for the PromptString field.
        :param new_comment: The new value for the Comment field.
        """
        try:
            if self.conn is None:
                self.__enter__()
        
            sql_update_query = """
            UPDATE PromptStrings 
            SET PromptString = ?, Comment = ? 
            WHERE PromptName = ?
            """
        
            self.cursor.execute(sql_update_query, (new_promptstring, new_comment, promptname))
            self.conn.commit()
            return "Prompt record updated successfully."
        
        except Exception as e:
            self.conn.rollback()
            return f"Error occurred while updating the prompt record: {e}"

    def search_for_string_in_prompt_text(self, search_string):
        """
        Lists all prompt_name and prompt_text where a specific string is part of the prompt_text.

        Parameters:
        - search_string: The string to search for within prompt_text.

        Returns:
        - A list of dictionaries, each containing 'prompt_name' and 'prompt_text' for records matching the search criteria.
        """
        self.cursor.execute('''
        SELECT PromptName, PromptString
        FROM PromptStrings
        WHERE PromptString LIKE ?
        ''', ('%' + search_string + '%',))
        results = self.cursor.fetchall()
    
        records = [{'PromptName': row[0], 'PromptString': row[1]} for row in results]
        return records

    def get_prompt_details_by_name(self, promptname):
        """
        Fetches the details of a prompt record identified by PromptName.
    
        :param promptname: The name of the prompt to fetch details for.
        :return: A dictionary with the details of the prompt record, or None if not found.
        """
        query = """
        SELECT PromptName, PromptString, Comment
        FROM PromptStrings
        WHERE PromptName = ?
        """
        try:
            self.cursor.execute(query, (promptname,))
            result = self.cursor.fetchone()
            if result:
                return {"PromptString": result[0], "Comment": result[1]}
            else:
                return None
        except Exception as e:
            print(f"Error occurred: {e}")
            return None

    def update_all_record(self, original_value, new_value, table, column):
        """
        Updates a specific record identified by the original value in a given table and column.
    
        :param original_value: The current value to identify the record to update.
        :param new_value: The new value to set for the specified column.
        :param table: The table to update.
        :param column: The column to update.
        """
        try:
            valid_tables = ['Users', 'PromptVariables', 'PythonFiles']
            valid_columns = ['Username', 'VariableName', 'Filename', 'FilePath']
        
            if table not in valid_tables or column not in valid_columns:
                return "Invalid table or column name."
        
            sql_update_query = f"""
            UPDATE {table}
            SET {column} = ?
            WHERE {column} = ?
            """
    
            self.cursor.execute(sql_update_query, (new_value, original_value))
            self.conn.commit()
            return f"Record updated successfully in {table}."
    
        except Exception as e:
            self.conn.rollback()
            return f"Error occurred while updating the record: {e}"

    def get_prompt_details_for_all(self, value, table, column):
        """
        Fetches the details of a record identified by a value in a specific table and column.

        :param value: The value to fetch details for.
        :param table: The table to fetch from.
        :param column: The column to match the value against.
        :return: A dictionary with the details of the record, or None if not found.
        """
        valid_tables = ['Users', 'PromptVariables', 'PythonFiles']
        valid_columns = ['Username', 'VariableName', 'Filename', 'FilePath']
    
        if table not in valid_tables or column not in valid_columns:
            print("Invalid table or column name.")
            return None

        query = f"SELECT * FROM {table} WHERE {column} = ?"
    
        try:
            self.cursor.execute(query, (value,))
            result = self.cursor.fetchone()
            if result:
                columns = [desc[0] for desc in self.cursor.description]
                return dict(zip(columns, result))
            else:
                return None
        except Exception as e:
            print(f"Error occurred: {e}")
            return None

    def close(self):
        """
        Closes the database connection and cursor, if they exist.
        """
        if self.cursor is not None:
            self.cursor.close()
            self.cursor = None
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def query_sql_record(self, prompt_name):
        """
        Fetches the existing prompt text and comment for a given prompt name.

        Parameters:
        - prompt_name: The name of the prompt.

        Returns:
        - A dictionary with 'prompt_text' and 'comment' if record exists, else None.
        """
        self.cursor.execute('''
        SELECT prompt_text, comment FROM prompts
        WHERE prompt_name = ?
        ''', (prompt_name,))
        result = self.cursor.fetchone()
        if result:
            return {'prompt_text': result[0], 'comment': result[1]}
        else:
            return None

    def get_file_path_by_name(self, filename):
        """
        Fetches the FilePath for a given Filename from the PythonFiles table.

        :param filename: The name of the file to fetch the path for.
        :return: The FilePath of the file if found, otherwise None.
        """
        query = "SELECT FilePath FROM PythonFiles WHERE Filename = ?"
        try:
            self.cursor.execute(query, (filename,))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error occurred: {e}")
            return None

    def update_filename_and_path(self, original_filename, new_filename, new_file_path):
        """
        Updates the Filename and FilePath in the PythonFiles table for a given original Filename.

        :param original_filename: The original name of the file to update.
        :param new_filename: The new name for the file.
        :param new_file_path: The new path for the file.
        :return: A success message or an error message.
        """
        query = "UPDATE PythonFiles SET Filename = ?, FilePath = ? WHERE Filename = ?"
        try:
            self.cursor.execute(query, (new_filename, new_file_path, original_filename))
            self.conn.commit()
            return "File record updated successfully."
        except Exception as e:
            self.conn.rollback()
            print(f"Error occurred: {e}")
            return None

    def add_relationship_record(self, prompt_id, user_id, variable_id, file_id):
        query = """
        INSERT INTO CentralRelationshipTable (PromptID, UserID, VariableID, FileID)
        VALUES (?, ?, ?, ?);
        """
        try:
            self.cursor.execute(query, (prompt_id, user_id, variable_id, file_id))
            self.conn.commit()
            return f"Record added successfully"
        except Exception as e:
            self.conn.rollback()
            return f"Error in add_relationship_record: {e}"

    def update_relationship_record(self, record_id, prompt_id=None, user_id=None, variable_id=None, file_id=None):
        updates = []
        params = []

        if prompt_id:
            updates.append("PromptID = ?")
            params.append(prompt_id)
        if user_id:
            updates.append("UserID = ?")
            params.append(user_id)
        if variable_id:
            updates.append("VariableID = ?")
            params.append(variable_id)
        if file_id:
            updates.append("FileID = ?")
            params.append(file_id)

        if not updates:
            return "No updates provided."

        query = f"UPDATE CentralRelationshipTable SET {', '.join(updates)} WHERE ID = ?;"
        params.append(record_id)

        try:
            self.cursor.execute(query, tuple(params))
            self.conn.commit()
            return "Record updated successfully"
        except Exception as e:
            self.conn.rollback()
            return f"Error in update_relationship_record: {e}"

    def delete_record(self, table, condition):
        query = f"DELETE FROM {table} WHERE {condition[0]}"
        try:
            self.cursor.execute(query, condition[1])
            self.conn.commit()
            return f"Record deleted successfully"
        except Exception as e:
            self.conn.rollback()
            return f"Error in delete_record: {e}"

    def get_record_by_name(self, table, name_column, value):
        """
        Fetches the entire record from a specified table based on a column name and value.

        :param table: The table to search in.
        :param name_column: The column name to match the value against.
        :param value: The value to search for.
        :return: A dictionary with the record data or None if no record is found.
        """
        query = f"SELECT * FROM {table} WHERE {name_column} = ?"
        try:
            if self.conn is None:
                self.__enter__()
            self.cursor.execute(query, (value,))
            result = self.cursor.fetchone()
            if result:
                columns = [desc[0] for desc in self.cursor.description]
                return dict(zip(columns, result))
            else:
                return None
        except Exception as e:
            print(f"Error occurred: {e}")
            return None
        
    def get_relationships_by_user_id(self, user_id):
        """
        Fetches relationship records for a given user ID.
        
        Parameters:
        - user_id: The ID of the user for whom to fetch relationship records.
        
        Returns:
        - A list of dictionaries containing relationship details.
        """
        relationships = []
        query = """
        SELECT crt.ID, ps.PromptName, u.Username, pv.VariableName, pf.Filename
        FROM CentralRelationshipTable crt
        JOIN PromptStrings ps ON crt.PromptID = ps.PromptID
        JOIN Users u ON crt.UserID = u.UserID
        JOIN PromptVariables pv ON crt.VariableID = pv.VariableID
        JOIN PythonFiles pf ON crt.FileID = pf.FileID
        WHERE crt.UserID = ?
        """
        try:
            self.cursor.execute(query, (user_id,))
            records = self.cursor.fetchall()
            
            if records:
                for record in records:
                    relationship = {
                        'ID': record[0],
                        'PromptName': record[1],
                        'Username': record[2],
                        'VariableName': record[3],
                        'Filename': record[4]
                    }
                    relationships.append(relationship)
        except Exception as e:
            return False
        
        return relationships
    
    def fetch_relationship_data(self, prompt_id=None):
        query = """
        SELECT crt.ID, ps.PromptName, u.Username, pv.VariableName, pf.Filename
        FROM CentralRelationshipTable crt
        JOIN PromptStrings ps ON crt.PromptID = ps.PromptID
        JOIN Users u ON crt.UserID = u.UserID
        JOIN PromptVariables pv ON crt.VariableID = pv.VariableID
        JOIN PythonFiles pf ON crt.FileID = pf.FileID
        """
        
        if prompt_id is not None:
            query += " WHERE crt.PromptID = ?"
            self.cursor.execute(query, (prompt_id,))
        else:
            self.cursor.execute(query)
        
        records = self.cursor.fetchall()
        return records
    
    def get_prompts_contain_in_name(self, promptname):
        """
        Fetches the details of prompt records where the PromptName contains the given string.

        :param promptname: The string to search for in the prompt names.
        :return: A list of dictionaries with the details of the matching prompt records, or an empty list if none are found.
        """
        query = """
        SELECT PromptName, PromptString, Comment
        FROM PromptStrings
        WHERE PromptName LIKE ?
        """
        try:
            self.cursor.execute(query, ('%' + promptname + '%',))
            results = self.cursor.fetchall()
            if results:
                return [{"PromptName": result[0], "PromptString": result[1], "Comment": result[2]} for result in results]
            else:
                return []
        except Exception as e:
            print(f"Error occurred: {e}")
            return []

import streamlit as st
@st.cache_data
def work_prompts():
    default_prompt = "You are a helpful assistant that always writes in Serbian."

    all_prompts = {
        # asistenti.py
        "text_from_image": default_prompt ,
        "text_from_audio": default_prompt ,

        # embeddings.py
        "contextual_compression": default_prompt ,
        "rag_self_query": default_prompt ,
        
        # various_tools.py
        "hyde_rag": default_prompt ,
        "choose_rag": default_prompt ,

        # klotbot
        "sys_ragbot": default_prompt,
        "rag_answer_reformat": default_prompt,

        # upitnik
        "gap_ba_expert" : default_prompt,
        "gap_dt_consultant" : default_prompt,
        "gap_service_suggestion" : default_prompt,
        "gap_write_report" : default_prompt,

        # zapisnik
        "summary_end": default_prompt,
        "summary_begin": default_prompt,
        "intro_summary": default_prompt,
        "topic_list_summary": default_prompt,
        "date_participants_summary": default_prompt,
        "topic_summary": default_prompt,
        "conclusion_summary": default_prompt,

        # pravnik
        "new_law_email": default_prompt,
        
        # blogger
        "sys_blogger": default_prompt,
        
        }

    prompt_names = list(all_prompts.keys())

    with PromptDatabase() as db:
        env_vars = [os.getenv(name.upper()) for name in prompt_names]
        prompt_map = db.get_prompts_by_names(prompt_names, env_vars)

        for name in prompt_names:
            all_prompts[name] = prompt_map.get(name, default_prompt)
    
    return all_prompts

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
    
    