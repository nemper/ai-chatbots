import os
from pinecone import Pinecone
from langchain_community.vectorstores import Pinecone as LangPine
from pinecone_text.sparse import BM25Encoder
import openai
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.sql_database import SQLDatabase
from langchain.agents.agent_types import AgentType
from langchain_openai.chat_models import ChatOpenAI
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_openai import OpenAIEmbeddings
import mysql.connector
import json


def SelfQueryPositive(upit, api_key=None, environment=None, index_name='neo-positive', namespace=None, openai_api_key=None, host=None):
    """
    Executes a query against a Pinecone vector database using specified parameters or environment variables. 
    The function initializes the Pinecone and OpenAI services, sets up the vector store and metadata, 
    and performs a query using a custom retriever based on the provided input 'upit'.
    
    It is used for self-query on metadata.

    Parameters:
    upit (str): The query input for retrieving relevant documents.
    api_key (str, optional): API key for Pinecone. Defaults to PINECONE_API_KEY_POS from environment variables.
    environment (str, optional): Pinecone environment. Defaults to PINECONE_ENVIRONMENT_POS from environment variables.
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
    api_key = api_key if api_key is not None else os.getenv('PINECONE_API_KEY_POS')
    environment = environment if environment is not None else os.getenv('PINECONE_ENVIRONMENT_POS')
    # index_name is already defaulted to 'positive'
    namespace = namespace if namespace is not None else os.getenv("NAMESPACE")
    openai_api_key = openai_api_key if openai_api_key is not None else os.getenv("OPENAI_API_KEY")
    host = host if host is not None else os.getenv("PINECONE_HOST")
   
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    # prilagoditi stvanim potrebama metadata
    metadata_field_info = [
        AttributeInfo(name="person_name",
                      description="The name of the person can be in the Serbian language like Miljan, Darko, Goran or similar", type="string"),
        AttributeInfo(
            name="topic", description="The topic of the document", type="string"),
        AttributeInfo(
            name="context", description="The Content of the document", type="string"),
        AttributeInfo(
            name="source", description="The source of the document", type="string"),
    ]

    # Define document content description
    document_content_description = "Content of the document"

    # Prilagoditi stvanom nazivu namespace-a
    vectorstore = LangPine.from_existing_index(
        index_name, embeddings, "context", namespace=namespace)

    # Initialize OpenAI embeddings and LLM
    llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)
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
            result += document.metadata['person_name'] + " kaze: \n"
            result += document.page_content + "\n\n"
    except Exception as e:
        result = e
    
    return result

class SQLSearchTool:
    """
    A tool to search an SQL database using natural language queries.
    This class uses the LangChain library to create an SQL agent that
    interprets natural language and executes corresponding SQL queries.
    """

    def __init__(self, db_uri=None):
        """
        Initialize the SQLSearchTool with a database URI.

        :param db_uri: The database URI. If None, it reads from the DB_URI environment variable.
        """

        if db_uri is None:
            db_uri = os.getenv("DB_URI")
        self.db = SQLDatabase.from_uri(db_uri)

        llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)
        toolkit = SQLDatabaseToolkit(
            db=self.db, llm=llm
        )

        self.agent_executor = create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            verbose=True,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            
        )

    def search(self, query, queries = 10):
        """
        Execute a search using a natural language query.

        :param query: The natural language query.
        :param queries: The number of results to return (default 10).
        :return: The response from the agent executor.
        """


        with PromptDatabase() as db:
            prompt_map = db.get_prompts_by_names(["result1"],["SQL_SEARCH_METHOD"])
            result1 = prompt_map.get('result1', 'You are helpful assistant that always writes in Serbian.')
        formatted_query = result1.format(query=query, queries=queries)

        try:
            response = self.agent_executor.invoke({formatted_query})["output"]
        except Exception as e:
            
            response = f"Ne mogu da odgovorim na pitanje, molim vas korigujte zahtev. Opis greske je \n {e}"
        
        return response


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
    processor = HybridQueryProcessor(api_key=environ["PINECONE_API_KEY_POS"], 
                                 environment=environ["PINECONE_ENVIRONMENT_POS"],
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
        self.api_key = kwargs.get('api_key', os.getenv('PINECONE_API_KEY_POS'))
        self.environment = kwargs.get('environment', os.getenv('PINECONE_ENVIRONMENT_POS'))
        self.alpha = kwargs.get('alpha', 0.5)  # Default alpha is 0.5
        self.score = kwargs.get('score', 0.05)  # Default score is 0.05
        self.index_name = kwargs.get('index', 'neo-positive')  # Default index is 'positive'
        self.namespace = kwargs.get('namespace', os.getenv("NAMESPACE"))  
        self.top_k = kwargs.get('top_k', 6)  # Default top_k is 6
        self.index = None
        self.host = os.getenv("PINECONE_HOST")
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
            model (str): The model to be used for embedding. Default is "text-embedding-ada-002".

        Returns:
            list: The embedding vector of the given text.
        """
        client = openai
        text = text.replace("\n", " ")
        
        return client.embeddings.create(input=[text], model=model).data[0].embedding

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
        """
        Executes a hybrid query on the Pinecone index using the provided query text.

        Args:
            upit (str): The query text.
            top_k (int, optional): The number of results to be returned. If not provided, use the class's top_k value.
            filter (dict, optional): Additional filter criteria for the query.
            namespace (str, optional): The namespace to be used for the query. If not provided, use the class's namespace.

        Returns:
            list: A list of query results, each being a dictionary containing page content, chunk, and source.
        """
        hdense, hsparse = self.hybrid_score_norm(
            sparse=BM25Encoder().fit([upit]).encode_queries(upit),
            dense=self.get_embedding(upit))
    
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

        # Construct the results list
        results = []
        for match in matches:
            metadata = match.get('metadata', {})
            context = metadata.get('context', '')
            chunk = metadata.get('chunk')
            source = metadata.get('source')
            try:
                score = match.get('score', 0)
            except:
                score = metadata.get('score', 0)

            # Append a dictionary with page content, chunk, and source
            if context:  # Ensure that 'context' is not empty
                results.append({"page_content": context, "chunk": chunk, "source": source, "score": score})
        
        return results


    def process_query_results(self, upit):
        """
        Processes the query results based on relevance score and formats them for a chat or dialogue system.
        Additionally, returns a list of scores for items that meet the score threshold.

        Args:
            upit (str): The original query text.
        
        Returns:
            tuple: A tuple containing the formatted string for chat prompt and a list of scores.
        """
        tematika = self.hybrid_query(upit)

        uk_teme = ""  # Formatted string for chat prompt
        score_list = []  # List to hold scores that meet the threshold

        for item in tematika:
            if item["score"] > self.score:  # Score threshold
                uk_teme += item["page_content"] + "\n\n"
                score_list.append(item["score"])  # Append the score to the list

        return uk_teme, score_list

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


class ParentPositiveManager:
    """
    This class manages the functionality for performing similarity searches using Pinecone and OpenAI Embeddings.
    It provides methods for retrieving documents based on similarity to a given query (`upit`), optionally filtered by source and chunk range.
    Works both with the original and the hybrid search. 
    Search by chunk is in the same namespace. Search by source can be in a different namespace.
    
    """
    
    # popraviti: 
    # 1. standardni set metadata source, chunk, datum. Za cosine index sadrzaj je text, za hybrid search je context (ne korsiti se ovde)
   
    
    def __init__(self, api_key=None, environment=None, index_name=None, namespace=None, openai_api_key=None):
        """
        Initializes the Pinecone and OpenAI Embeddings with the provided or environment-based configuration.
        
        :param api_key: Pinecone API key.
        :param environment: Pinecone environment.
        :param index_name: Name of the Pinecone index.
        :param namespace: Namespace for document retrieval.
        :param openai_api_key: OpenAI API key.
        :param index_name: Pinecone index name.
        
        """
        self.api_key = api_key if api_key is not None else os.getenv('PINECONE_API_KEY')
        self.environment = environment if environment is not None else os.getenv('PINECONE_ENV')
        self.namespace = namespace if namespace is not None else os.getenv("NAMESPACE")
        self.openai_api_key = openai_api_key if openai_api_key is not None else os.getenv("OPENAI_API_KEY")
        self.index_name = index_name if index_name is not None else os.getenv("PINECONE_INDEX")
        self.host = os.getenv("PINECONE_HOST")
        pinecone=Pinecone(api_key=api_key, host=self.host)
        self.index = pinecone.Index(host=self.host)
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        self.docsearch = LangPine.from_existing_index(self.index_name, self.embeddings)

    def search_by_source(self, upit, source_result, top_k=5):
        """
        Perform a similarity search for documents related to `upit`, filtered by a specific `source_result`.
        
        :param upit: Query string.
        :param source_result: source to filter the search results.
        :return: Concatenated page content of the search results.
        """
        doc_result = self.docsearch.similarity_search(upit, k=top_k, filter={'source': source_result}, namespace=self.namespace)
        result = "\n\n".join(document.page_content for document in doc_result)
        
        return result

    def search_by_chunk(self, upit, source_result, chunk, razmak=3, top_k=20):
        """
        Perform a similarity search for documents related to `upit`, filtered by source and a specific chunk range.
        Namsepace for store can be different than for th eoriginal search.
        
        :param upit: Query string.
        :param source_result: source to filter the search results.
        :param chunk: Target chunk number.
        :param razmak: Range to consider around the target chunk.
        :return: Concatenated page content of the search results.
        """
        
        manji = chunk - razmak
        veci = chunk + razmak
        
        filter_criteria = {
            'source': source_result,
            '$and': [{'chunk': {'$gte': manji}}, {'chunk': {'$lte': veci}}]
        }
        doc_result = self.docsearch.similarity_search(upit, k=top_k, filter=filter_criteria, namespace=self.namespace)
        # Sort the doc_result based on the 'chunk' metadata
        sorted_doc_result = sorted(doc_result, key=lambda document: document.metadata['chunk'])
        # Generate the result string
        result = " ".join(document.page_content for document in sorted_doc_result)
        
        return result

    def basic_search(self, upit):
        """
        Perform a basic similarity search for the document most related to `upit`.
        
        :param upit: Query string.
        :return: Tuple containing the page content, source, and chunk number of the top search result.
        """
        doc_result = self.docsearch.similarity_search(upit, k=1, namespace=self.namespace)
        top_result = doc_result[0]
        
        return top_result.page_content, top_result.metadata['source'], top_result.metadata['chunk']


class PromptDatabase:
    """
    A class to interact with a MySQL database for storing and retrieving prompt templates.
    """
    
    def __init__(self, host=None, user=None, password=None, database=None):
        """
        Initializes the connection details for the database, with the option to use environment variables as defaults.
        """
        self.host = host if host is not None else os.getenv('DB_HOST')
        self.user = user if user is not None else os.getenv('DB_USER')
        self.password = password if password is not None else os.getenv('DB_PASSWORD')
        self.database = database if database is not None else os.getenv('DB_NAME')
        self.conn = None
        self.cursor = None
        
    def __enter__(self):
        """
        Establishes the database connection and returns the instance itself when entering the context.
        """
        self.conn = mysql.connector.connect(host=self.host, user=self.user, password=self.password, database=self.database)
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
        # Handle exception if needed, can log or re-raise exceptions based on requirements
        if exc_type or exc_val or exc_tb:
            # Optionally log or handle exception
            pass
 
        
####################### BEGIN za ostale app ####################################################   
 
    # !!!! osnovni metod za pretragu u ostalim .py    
    def get_prompts_by_names(self, variable_names, prompt_names):
        prompt_strings = self.query_sql_prompt_strings(prompt_names)
        prompt_variables = dict(zip(variable_names, prompt_strings))
        return prompt_variables


    # !!!! poziva ga osnovni metod za pretragu u ostalim .py - get_prompts_by_names 
    def query_sql_prompt_strings(self, prompt_names):
        """
        Fetches the existing prompt strings for a given list of prompt names, maintaining the order of prompt_names.
        """
        order_clause = "ORDER BY CASE PromptName "
        for idx, name in enumerate(prompt_names):
            order_clause += f"WHEN %s THEN {idx} "
        order_clause += "END"

        query = f"""
        SELECT PromptString FROM PromptStrings
        WHERE PromptName IN ({','.join(['%s'] * len(prompt_names))})
        """ + order_clause

        params = tuple(prompt_names) + tuple(prompt_names)  # prompt_names repeated for both IN and ORDER BY
        self.cursor.execute(query, params)
        results = self.cursor.fetchall()
        return [result[0] for result in results] if results else []

    
    # !!!! legacy stari poziv za ostale .py
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
        WHERE prompt_name = %s
        ''', (prompt_name,))
        result = self.cursor.fetchone()
        if result:
            return {'prompt_text': result[0], 'comment': result[1]}
        else:
            return None

####################### END za ostale app ####################################################


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
        WHERE crt.UserID = %s
        """
        try:
            # Execute the query with user_id as the parameter
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
            # Handle the error appropriately within your application context
            # For example, log the error message
            return False
        
        return relationships

    def fetch_relationship_data(self, prompt_id=None):
        # Use self.cursor to execute your query, assuming your class manages a cursor attribute
        query = """
        SELECT crt.ID, ps.PromptName, u.Username, pv.VariableName, pf.Filename
        FROM CentralRelationshipTable crt
        JOIN PromptStrings ps ON crt.PromptID = ps.PromptID
        JOIN Users u ON crt.UserID = u.UserID
        JOIN PromptVariables pv ON crt.VariableID = pv.VariableID
        JOIN PythonFiles pf ON crt.FileID = pf.FileID
        """
        
        # If a prompt_id is provided, append a WHERE clause to filter by that ID
        if prompt_id is not None:
            query += " WHERE crt.PromptID = %s"
            self.cursor.execute(query, (prompt_id,))
        else:
            self.cursor.execute(query)
        
        # Fetch all records
        records = self.cursor.fetchall()
        return records

    # opsta funkcija za prikaz polja za selectbox - koristi get_records za pripremu
    def get_records_from_column(self, table, column):
        """
        Fetch records from a specified column in a specified table.
        """
        query = f"SELECT DISTINCT {column} FROM {table}"
        records = self.get_records(query)
        return [record[0] for record in records] if records else []
    
    # za odabir za selectbox i za funkcije unosa i editovanja - osnovna funkcija
    def get_records(self, query, params=None):
        try:
            if self.conn is None or not self.conn.is_connected():
                self.__enter__()
            self.cursor.execute(query, params)
            records = self.cursor.fetchall()
            return records
        except Exception as e:
            print(f"Error occurred: {e}")
            return []
     
    def get_record_by_name(self, table, name_column, value):
        """
        Fetches the entire record from a specified table based on a column name and value.

        :param table: The table to search in.
        :param name_column: The column name to match the value against.
        :param value: The value to search for.
        :return: A dictionary with the record data or None if no record is found.
        """
        query = f"SELECT * FROM {table} WHERE {name_column} = %s"
        try:
            if self.conn is None or not self.conn.is_connected():
                self.__enter__()
            self.cursor.execute(query, (value,))
            result = self.cursor.fetchone()
            if result:
                # Constructing a dictionary from the column names and values
                columns = [desc[0] for desc in self.cursor.description]
                return dict(zip(columns, result))
            else:
                return None
        except Exception as e:
            print(f"Error occurred: {e}")
            return None


    # za prikaz cele tabele kao info prilikom unosa i editovanja koristi kasnije df
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
            return [],[]  # Return an empty DataFrame in case of an error

    def add_record(self, table, **fields):
        """
        Inserts a new record into the specified table.
    
        :param table: The name of the table to insert the record into.
        :param fields: Keyword arguments representing column names and their values to insert.
        """
        columns = ', '.join(fields.keys())
        placeholders = ', '.join(['%s'] * len(fields))
        values = tuple(fields.values())
    
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    
        try:
            self.cursor.execute(query, values)
            self.conn.commit()
            return "Uspesno dodat slog" 
        except Exception as e:
            self.conn.rollback()
            return f"Error in add_record: {e}"
    
    def update_record(self, table, fields, condition):
        """
        Updates records in the specified table based on a condition.
    
        :param table: The name of the table to update.
        :param fields: A dictionary of column names and their new values.
        :param condition: A tuple containing the condition string and its values (e.g., ("UserID = %s", [user_id])).
        """
        set_clause = ', '.join([f"{key} = %s" for key in fields.keys()])
        values = list(fields.values()) + condition[1]
    
        query = f"UPDATE {table} SET {set_clause} WHERE {condition[0]}"
    
        try:
            self.cursor.execute(query, values)
            self.conn.commit()
            return "Uspesno dodat slog"  # Returns the number of rows affected
        except Exception as e:
            self.conn.rollback()
            return f"Error in update_record: {e}"

    def add_relationship_record(self, prompt_id, user_id, variable_id, file_id):
        query = """
        INSERT INTO CentralRelationshipTable (PromptID, UserID, VariableID, FileID)
        VALUES (%s, %s, %s, %s);
        """
        try:
            self.cursor.execute(query, (prompt_id, user_id, variable_id, file_id))
            self.conn.commit()
            return  f"Uspesno dodat {self.cursor.rowcount} slog" # Return the ID of the newly inserted record
        except mysql.connector.Error as e:
            self.conn.rollback()  # Roll back the transaction on error
            return f"Error in add_relationship_record: {e}"

    def update_relationship_record(self, record_id, prompt_id=None, user_id=None, variable_id=None, file_id=None):
        updates = []
        params = []

        if prompt_id:
            updates.append("PromptID = %s")
            params.append(prompt_id)
        if user_id:
            updates.append("UserID = %s")
            params.append(user_id)
        if variable_id:
            updates.append("VariableID = %s")
            params.append(variable_id)
        if file_id:
            updates.append("FileID = %s")
            params.append(file_id)

        if not updates:
            return "No updates provided."

        query = f"UPDATE CentralRelationshipTable SET {', '.join(updates)} WHERE ID = %s;"
        params.append(record_id)

        try:
            self.cursor.execute(query, tuple(params))
            self.conn.commit()
            return "Succesful update relationship record"
        except mysql.connector.Error as e:
            self.conn.rollback()
            return f"Error in update_relationship_record: {e}"

    def delete_record(self, table, condition):
        query = f"DELETE FROM {table} WHERE {condition[0]}"
        try:
            # Directly using condition[1] which is expected to be a list or tuple of values
            self.cursor.execute(query, condition[1])
            self.conn.commit()
            return f"Record deleted"
        except Exception as e:
            self.conn.rollback()
            return f"Error in delete_record: {e}"
            

  
    # za pretragu tabel epromptova po stringu u textu
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
        WHERE PromptString LIKE %s
        ''', ('%' + search_string + '%',))
        results = self.cursor.fetchall()
    
        # Convert the results into a list of dictionaries for easier use
        records = [{'PromptName': row[0], 'PromptString': row[1]} for row in results]
        return records

###### !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ############
################# treba za razne manipulacije sa CentralrelationshipTable #######################
    
    # pomocna funkcija za zatvaranje konekcije
    def close(self):
        """
        Closes the database connection and cursor, if they exist.
        """
        if self.cursor is not None:
            self.cursor.close()
            self.cursor = None  # Reset cursor to None to avoid re-closing a closed cursor
        if self.conn is not None and self.conn.is_connected():
            self.conn.close()
            self.conn = None  # Reset connection to None for safety
   


class ConversationDatabase:
    """
    A class to interact with a MySQL database for storing and retrieving conversation data.
    """
    
    def __init__(self, host=None, user=None, password=None, database=None):
        """
        Initializes the connection details for the database, with the option to use environment variables as defaults.
        """
        self.host = host if host is not None else os.getenv('DB_HOST')
        self.user = user if user is not None else os.getenv('DB_USER')
        self.password = password if password is not None else os.getenv('DB_PASSWORD')
        self.database = database if database is not None else os.getenv('DB_NAME')
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """
        Establishes the database connection and returns the instance itself when entering the context.
        """
        self.conn = mysql.connector.connect(host=self.host, user=self.user, password=self.password, database=self.database)
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
        # Handle exception if needed, can log or re-raise exceptions based on requirements
        if exc_type or exc_val or exc_tb:
            # Optionally log or handle exception
            pass
    
    
    def create_sql_table(self):
        """
        Creates a table for storing conversations if it doesn't already exist.
        """
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            app_name VARCHAR(255) NOT NULL,
            user_name VARCHAR(255) NOT NULL,
            thread_id VARCHAR(255) NOT NULL,
            conversation LONGTEXT NOT NULL
        )
        ''')
        # print("Table created if new.")
    
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
        self.cursor.execute('''
        INSERT INTO conversations (app_name, user_name, thread_id, conversation) 
        VALUES (%s, %s, %s, %s)
        ''', (app_name, user_name, thread_id, conversation_json))
        self.conn.commit()
        # print("New record added.")
    
    def query_sql_record(self, app_name, user_name, thread_id):
        """
        Modified to return the conversation record.
        """
        self.cursor.execute('''
        SELECT conversation FROM conversations 
        WHERE app_name = %s AND user_name = %s AND thread_id = %s
        ''', (app_name, user_name, thread_id))
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
        WHERE app_name = %s AND user_name = %s AND thread_id = %s
        '''
        self.cursor.execute(delete_sql, (app_name, user_name, thread_id))
        self.conn.commit()
        # print("Conversation thread deleted.")
    
    def list_threads(self, app_name, user_name):
        """
        Lists all thread IDs for a given app name and user name.
    
        Parameters:
        - app_name: The name of the application.
        - user_name: The name of the user.

        Returns:
        - A list of thread IDs associated with the given app name and user name.
        """
        self.cursor.execute('''
        SELECT DISTINCT thread_id FROM conversations
        WHERE app_name = %s AND user_name = %s
        ''', (app_name, user_name))
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
        self.cursor.execute('''
        UPDATE conversations
        SET conversation = %s
        WHERE app_name = %s AND user_name = %s AND thread_id = %s
        ''', (new_conversation_json, app_name, user_name, thread_id))
        self.conn.commit()
        # print("Record updated with new conversation.")

    def close(self):
        """
        Closes the database connection.
        """
        self.conn.close()


import json
import datetime

class TextProcessing:
    def __init__(self, gpt_client):
        self.client = gpt_client

    def add_self_data(self, line):
        """
        Extracts the person's name and topic from a given line of text using a GPT-4 model.
        """
        response = self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "result1"},
                {"role": "user", "content": line}
            ]
        )
        json_content = response.choices[0].message.content.strip()
        content_dict = json.loads(json_content)
        person_name = content_dict.get("person_name", "John Doe")
        topic = content_dict["topic"]
        
        return person_name, topic

    def format_output_text(self, prefix, question, content):
        """
        Formats the output text.
        """
        return prefix + question + content

    def get_current_date_formatted(self):
        """
        Returns the current date formatted as a string.
        """
        return datetime.datetime.now().strftime("%d.%m.%Y")

    def add_question(self, chunk_text):
        """
        Adds a question to a chunk of text to match the given statement.
        """
        result = self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            temperature=0,
            messages=[
                {"role": "system", "content": "result2"},
                {"role": "user", "content": chunk_text}
            ]
        )

        return result.choices[0].message.content


import streamlit as st
from pinecone import Pinecone
import sys
import os
import time
from myfunc.mojafunkcija import pinecone_stats
from langchain.indexes import GraphIndexCreator
from langchain_openai import ChatOpenAI
import networkx as nx
import matplotlib.pyplot as plt
# from langchain.indexes.graph import NetworkxEntityGraph
# from langchain.chains import GraphQAChain
import PyPDF2
import io
import re
from langchain_community.document_loaders import UnstructuredFileLoader
import unidecode

class PineconeUtility:
    def __init__(self):
        # Nothing to initialize
        x = 1

    def obrisi_index(self):
        # Method for handling Pinecone index deletion
        index_name = st.selectbox("Odaberite index", ["neo-positive", "embedings1"], help="Unesite ime indeksa", key="opcije"
    )
        if index_name is not None and index_name!=" " and index_name !="" :
            col1, col2 = st.columns(2)
            if index_name=="embedings1":
            
                pinecone=Pinecone(api_key=os.environ.get("PINECONE_API_KEY_STARI"), host="https://embedings1-b1b39e1.svc.us-west1-gcp.pinecone.io") #embedings1 (thai, free)
                index = pinecone.Index(host="https://embedings1-b1b39e1.svc.us-west1-gcp.pinecone.io") #embedings1
            elif index_name=="neo-positive":
                
                pinecone=Pinecone(api_key=os.environ.get("PINECONE_API_KEY_S"), host="https://neo-positive-a9w1e6k.svc.apw5-4e34-81fa.pinecone.io") #neo-positive (thai, serverless, 3072)
                index = pinecone.Index(host="https://neo-positive-a9w1e6k.svc.apw5-4e34-81fa.pinecone.io") #neo-positive
            else:
                st.error("Index ne postoji")
                st.stop()
            with col2:
                pinecone_stats(index, index_name)
        
            with col1:
                with st.form(key="util", clear_on_submit=True):
                    st.subheader("Uklanjanje namespace-a iz Pinecone Indeksa")
                    namespace = st.text_input(
                        "Unesite namespace : ",
                        help="Unesite namespace koji želite da obrišete (prazno za sve)",
                    )
                    moj_filter = st.text_input(
                        "Unesite filter za source (prazno za sve) : ",
                        help="Unesite filter za source (prazno za sve) : ",
                    )
                    nastavak = st.radio(
                        f"Da li ukloniti namespace {namespace} iz indeksa {index_name}",
                        ("Da", "Ne"),
                        help="Da li ukloniti namespace iz indeksa?",
                    )

                    submit_button = st.form_submit_button(
                        label="Submit",
                        help="Pokreće uklanjanje namespace-a iz indeksa",
                    )
                    if submit_button:
                        if not nastavak == "Da":
                            placeholder = st.empty()
                            with placeholder.container():
                                st.write("Izlazim iz programa")
                                time.sleep(2)
                                placeholder.empty()
                            sys.exit()
                        else:
                            with st.spinner("Sačekajte trenutak..."):
                            
                                # ukoliko zelimo da izbrisemo samo nekle recorde bazirano na meta data
                                try:
                                    if not moj_filter == "":
                                        index.delete(
                                            filter={"person_name": {"$in": [moj_filter]}},
                                            namespace=namespace,
                                        )
                                    #elif not namespace == "":
                                    else:
                                        index.delete(delete_all=True, namespace=namespace)
                                    # else:
                                    #     index.delete(delete_all=True)
                                except Exception as e:
                                    match = re.search(r'"message":"(.*?)"', str(e))

                                    if match:
                                        # Prints the extracted message
                                        st.error(f"Proverite ime indeksa koji ste uneli: {match.group(1)}")
                                    sys.exit()

                    
                                st.success("Uspešno obrisano")

    def create_node(self, id, label):
        # Method for creating a graph node
        ascii_label = unidecode.unidecode(label)  # Convert label to ASCII
        return f'  node [\n    id {id}\n    label "{ascii_label}"\n  ]\n'

    def create_edge(self, source, target, relation):
        # Method for creating a graph edge
        ascii_relation = unidecode.unidecode(relation)  # Convert relation to ASCII
        return f'  edge [\n    source {source}\n    target {target}\n    relation "{ascii_relation}"\n  ]\n'

    def create_graph_structure(self, data):
        # Method for creating the overall graph structure
        graph = "graph [\n  directed 1\n"
        nodes = {}
        edges = []
        graph_structure = "graph [\n  directed 1\n"
        node_id = 0
        for item in data:
        # Check and add the first element of the tuple as a node
            if item[0] not in nodes:
                nodes[item[0]] = node_id
                graph_structure += self.create_node(node_id, item[0])
                node_id += 1
        
            # Check and add the second element of the tuple as a node
            if item[1] not in nodes:
                nodes[item[1]] = node_id
                graph_structure += self.create_node(node_id, item[1])
                node_id += 1

            # Create an edge based on the relation (item[2])
            graph_structure += self.create_edge(nodes[item[0]], nodes[item[1]], item[2])

    # Close the graph structure
        graph_structure += "]"
        return graph_structure


    def create_graph(self, dokum):
        # Method for handling the graph creation process
        skinuto = False
        napisano = False
        slika_grafa = False
        if "skinuto" not in st.session_state:
            st.session_state.skinuto = False
        
        if st.session_state.skinuto == False:
            with st.spinner("Kreiram Graf, molim vas sacekajte..."):
                buffer = io.BytesIO()
                # Write data to the buffer
                buffer.write(dokum.getbuffer())
                # Get the byte data from the buffer
                byte_data = buffer.getvalue()
                all_text = byte_data.decode('utf-8')
                    
                # initialize graph engine
                index_creator = GraphIndexCreator(llm=ChatOpenAI(temperature=0, model="gpt-4-turbo-preview"))
                text = "\n".join(all_text.split("\n\n"))
            
                # create graph
                graph = index_creator.from_text(text)
                prikaz = graph.get_triples()
                with st.expander("Graf:"):
                    st.write(prikaz)
                # Don't forget to close the buffer when done
                buffer.close() 
                # save graph, with the same name different extension
                file_name = os.path.splitext(dokum.name)[0]
            
                graph_structure = self.create_graph_structure(prikaz)
                napisano = st.info(
                        f"Tekst je sačuvan u gml obliku kao {file_name}.gml, downloadujte ga na svoj računar"
                )
            
                skinut = st.download_button(
                    "Download GML",
                    data=graph_structure,
                    file_name=f"{file_name}.gml",
                    mime='ascii',
                )
                
                st.session_state.skinuto = True
                st.success(f"Graf je sačuvan kao {file_name}.gml")
                    
            # Load the GML file
        
        
        if st.session_state.skinuto:
            st.markdown("**Kada downloadujete graph file, učitajte GRAF ako zelite graficki prikaz**")
            slika_grafa = st.file_uploader(
                "Izaberite GRAF dokument", key="upload_graf", type=["gml"]
            )      
                
            if slika_grafa is not None:
                with io.open(slika_grafa.name, "wb") as file:
                        file.write(slika_grafa.getbuffer())
                
                G = nx.read_gml(slika_grafa.name)
                nx.draw(G, with_labels=True, node_size=200, font_size=5)
                st.pyplot(plt)  # Display the plot in Streamlit

    def read_uploaded_file(self, dokum, text_delimiter="space"):
        # Method for reading and processing the uploaded file
        with io.open(dokum.name, "wb") as file:
            file.write(dokum.getbuffer())

            
            if text_delimiter == "":
                text_delimiter = "\n\n"

            if ".pdf" in dokum.name:
                pdf_reader = PyPDF2.PdfReader(dokum)
                num_pages = len(pdf_reader.pages)
                text_content = ""

                for page in range(num_pages):
                    page_obj = pdf_reader.pages[page]
                    text_content += page_obj.extract_text()
                text_content = text_content.replace("•", "")
                text_content = re.sub(r"(?<=\b\w) (?=\w\b)", "", text_content)
                with io.open("temp.txt", "w", encoding="utf-8") as f:
                    f.write(text_content)

                loader = UnstructuredFileLoader("temp.txt", encoding="utf-8")
            else:
                # Creating a file loader object
                loader = UnstructuredFileLoader(dokum.name, encoding="utf-8")
            data = loader.load()
        return data
    