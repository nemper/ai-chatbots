import json
import pyodbc
import streamlit as st
from datetime import datetime

from os import getenv

import json
import pyodbc
import os
from typing import Any, Dict, List, Optional, Tuple

class ConversationDatabase:
    """
    A class to interact with a MSSQL database for storing and retrieving conversation data.

    This class provides methods to create tables, insert, update, query, and delete conversation records.
    It also handles logging of token usage and user feedback. The class is designed to be used as a
    context manager to ensure proper opening and closing of database connections.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None
    ) -> None:
        """
        Initializes the ConversationDatabase with database connection parameters.

        If parameters are not provided, they are fetched from environment variables:
            - 'MSSQL_HOST' for the host
            - 'MSSQL_USER' for the username
            - 'MSSQL_PASS' for the password
            - 'MSSQL_DB' for the database name

        Args:
            host (Optional[str], optional): The database server host. Defaults to environment variable 'MSSQL_HOST'.
            user (Optional[str], optional): The database username. Defaults to environment variable 'MSSQL_USER'.
            password (Optional[str], optional): The database password. Defaults to environment variable 'MSSQL_PASS'.
            database (Optional[str], optional): The database name. Defaults to environment variable 'MSSQL_DB'.
        """
        self.host: str = host if host is not None else os.getenv('MSSQL_HOST')
        self.user: str = user if user is not None else os.getenv('MSSQL_USER')
        self.password: str = password if password is not None else os.getenv('MSSQL_PASS')
        self.database: str = database if database is not None else os.getenv('MSSQL_DB')
        self.conn: Optional[pyodbc.Connection] = None
        self.cursor: Optional[pyodbc.Cursor] = None

    def __enter__(self) -> 'ConversationDatabase':
        """
        Establishes a connection to the MSSQL database and initializes a cursor.

        This method is called when entering the context of the `with` statement.

        Returns:
            ConversationDatabase: The instance of the class with an active database connection.
        
        Raises:
            Exception: If there is an error connecting to the database.
        """
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
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            raise
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any]
    ) -> None:
        """
        Closes the database cursor and connection upon exiting the context.

        This method is called when exiting the context of the `with` statement, regardless of whether
        an exception occurred.

        Args:
            exc_type (Optional[type]): The type of the exception.
            exc_val (Optional[BaseException]): The exception instance.
            exc_tb (Optional[Any]): The traceback object.

        Returns:
            None
        """
        if self.cursor is not None:
            self.cursor.close()
        if self.conn is not None:
            self.conn.close()
        if exc_type or exc_val or exc_tb:
            print(f"Exception occurred: {exc_type}, {exc_val}")

    def create_sql_table(self) -> None:
        """
        Creates the 'conversations' table in the database if it does not already exist.

        The table includes fields for id, app_name, user_name, thread_id, and conversation.
        This method ensures that the necessary table structure is in place for storing conversation data.

        Returns:
            None
        
        Raises:
            Exception: If there is an error executing the SQL statement.
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
        try:
            self.cursor.execute(check_table_sql)
            self.conn.commit()
        except Exception as e:
            print(f"Error creating table: {e}")
            raise

    def update_sql_record(
        self,
        app_name: str,
        user_name: str,
        thread_id: str,
        new_conversation: List[Dict[str, Any]]
    ) -> None:
        """
        Updates an existing conversation record with new conversation data.

        This method replaces the existing conversation data with the provided `new_conversation` for a specific
        record identified by `app_name`, `user_name`, and `thread_id`.

        Args:
            app_name (str): The name of the application.
            user_name (str): The name of the user.
            thread_id (str): The thread identifier.
            new_conversation (List[Dict[str, Any]]): The new conversation data as a list of dictionaries.

        Returns:
            None
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
        """
        new_conversation_json = json.dumps(new_conversation)
        update_sql = '''
        UPDATE conversations
        SET conversation = ?
        WHERE app_name = ? AND user_name = ? AND thread_id = ?
        '''
        try:
            self.cursor.execute(update_sql, (new_conversation_json, app_name, user_name, thread_id))
            self.conn.commit()
            affected_rows = self.cursor.rowcount
            if affected_rows == 0:
                print("No rows were updated. Please check if the record exists.")
        except pyodbc.Error as e:
            print(f"Error updating record: {e}")
            self.conn.rollback()

    def record_exists(
        self,
        app_name: str,
        user_name: str,
        thread_id: str
    ) -> bool:
        """
        Checks whether a specific conversation record exists in the database.

        Args:
            app_name (str): The name of the application.
            user_name (str): The name of the user.
            thread_id (str): The thread identifier.

        Returns:
            bool: `True` if the record exists, `False` otherwise.
        """
        check_sql = '''
        SELECT COUNT(*)
        FROM conversations
        WHERE app_name = ? AND user_name = ? AND thread_id = ?
        '''
        self.cursor.execute(check_sql, (app_name, user_name, thread_id))
        count = self.cursor.fetchone()[0]
        return count > 0

    def add_sql_record(
        self,
        app_name: str,
        user_name: str,
        thread_id: str,
        conversation: List[Dict[str, Any]]
    ) -> None:
        """
        Inserts a new conversation record into the database.

        Args:
            app_name (str): The name of the application.
            user_name (str): The name of the user.
            thread_id (str): The thread identifier.
            conversation (List[Dict[str, Any]]): The conversation data as a list of dictionaries.

        Returns:
            None
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
        """
        conversation_json = json.dumps(conversation)
        current_date = datetime.now().date()

        insert_sql = '''
        INSERT INTO conversations (app_name, date, user_name, thread_id, conversation) 
        VALUES (?, ?, ?, ?, ?)
        '''
        try:
            self.cursor.execute(insert_sql, (app_name, current_date, user_name, thread_id, conversation_json))
            self.conn.commit()
        except pyodbc.Error as e:
            print(f"Error adding record: {e}")
            self.conn.rollback()

    def update_or_insert_sql_record(
            self,
            app_name: str,
            user_name: str,
            thread_id: str,
            new_conversation: List[Dict[str, Any]]
        ) -> None:
        """
        Updates an existing conversation record or inserts a new one if it does not exist.

        Args:
            app_name (str): The name of the application.
            user_name (str): The name of the user.
            thread_id (str): The thread identifier.
            new_conversation (List[Dict[str, Any]]): The conversation data as a list of dictionaries.

        Returns:
            None
        """
        if self.record_exists(app_name, user_name, thread_id):
            self.update_sql_record(app_name, user_name, thread_id, new_conversation)
        else:
            self.add_sql_record(app_name, user_name, thread_id, new_conversation)

    def query_sql_record(
        self,
        app_name: str,
        user_name: str,
        thread_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves a conversation record from the database.

        Args:
            app_name (str): The name of the application.
            user_name (str): The name of the user.
            thread_id (str): The thread identifier.

        Returns:
            Optional[List[Dict[str, Any]]]: The conversation data as a list of dictionaries if the record exists,
                                             otherwise `None`.
        
        Raises:
            Exception: If there is an error executing the SQL statement.
        """
        query_sql = '''
        SELECT conversation FROM conversations 
        WHERE app_name = ? AND user_name = ? AND thread_id = ?
        '''
        try:
            self.cursor.execute(query_sql, (app_name, user_name, thread_id))
            result = self.cursor.fetchone()
            if result:
                return json.loads(result[0])
            else:
                return None
        except Exception as e:
            print(f"Error querying record: {e}")
            raise

    def delete_sql_record(
        self,
        app_name: str,
        user_name: str,
        thread_id: str
    ) -> None:
        """
        Deletes a specific conversation record from the database.

        Args:
            app_name (str): The name of the application.
            user_name (str): The name of the user.
            thread_id (str): The thread identifier.

        Returns:
            None
        
        Raises:
            Exception: If there is an error executing the SQL statement.
        """
        delete_sql = '''
        DELETE FROM conversations
        WHERE app_name = ? AND user_name = ? AND thread_id = ?
        '''
        try:
            self.cursor.execute(delete_sql, (app_name, user_name, thread_id))
            self.conn.commit()
        except Exception as e:
            print(f"Error deleting record: {e}")
            raise

    def list_threads(
        self,
        app_name: str,
        user_name: str
    ) -> List[str]:
        """
        Lists all unique thread IDs for a given application and user.

        Args:
            app_name (str): The name of the application.
            user_name (str): The name of the user.

        Returns:
            List[str]: A list of unique thread IDs associated with the specified application and user.
        
        Raises:
            Exception: If there is an error executing the SQL statement.
        """
        list_threads_sql = '''
        SELECT DISTINCT thread_id FROM conversations
        WHERE app_name = ? AND user_name = ?
        '''
        try:
            self.cursor.execute(list_threads_sql, (app_name, user_name))
            threads = self.cursor.fetchall()
            return [thread[0] for thread in threads]
        except Exception as e:
            print(f"Error listing threads: {e}")
            raise

    def add_token_record_openai(
        self,
        app_id: str,
        model_name: str,
        embedding_tokens: int,
        prompt_tokens: int,
        completion_tokens: int,
        stt_tokens: int,
        tts_tokens: int
    ) -> None:
        """
        Inserts a token usage record into the 'chatbot_token_log' table.

        This method logs the number of tokens used for various components such as embeddings,
        prompts, completions, speech-to-text (STT), and text-to-speech (TTS) for a specific application
        and model.

        Args:
            app_id (str): The identifier for the application.
            model_name (str): The name of the OpenAI model used.
            embedding_tokens (int): Number of tokens used for embeddings.
            prompt_tokens (int): Number of tokens used for prompts.
            completion_tokens (int): Number of tokens used for completions.
            stt_tokens (int): Number of tokens used for speech-to-text.
            tts_tokens (int): Number of tokens used for text-to-speech.

        Returns:
            None
        
        Raises:
            Exception: If there is an error executing the SQL statement.
        """
        insert_sql = """
        INSERT INTO chatbot_token_log (app_id, embedding_tokens, prompt_tokens, completion_tokens, stt_tokens, tts_tokens, model_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        values = (app_id, embedding_tokens, prompt_tokens, completion_tokens, stt_tokens, tts_tokens, model_name)
        try:
            self.cursor.execute(insert_sql, values)
            self.conn.commit()
        except Exception as e:
            print(f"Error adding token record: {e}")
            raise

    def insert_feedback(
        self,
        thread_id: str,
        app_name: str,
        previous_question: str,
        tool_answer: str,
        given_answer: str,
        thumbs: str,
        feedback_text: str
    ) -> None:
        """
        Inserts user feedback into the 'Feedback' table.

        This method logs feedback provided by the user regarding the chatbot's responses. It includes
        details such as the previous question, the tool's answer, the user's given answer, the type of
        feedback (Good/Bad), and any optional text provided by the user.

        Args:
            thread_id (str): The thread identifier associated with the conversation.
            app_name (str): The name of the application.
            previous_question (str): The previous question asked by the user.
            tool_answer (str): The answer provided by the tool.
            given_answer (str): The answer given by the user.
            thumbs (str): The type of feedback ('Good' or 'Bad').
            feedback_text (str): Optional additional feedback text provided by the user.

        Returns:
            None
        
        Raises:
            Exception: If there is an error executing the SQL statement.
        """
        current_date = datetime.now().date()
        try:
            insert_query = """
            INSERT INTO Feedback (app_name, date, previous_question, tool_answer, given_answer, Thumbs, Feedback_text, thread_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.cursor.execute(insert_query, (app_name, current_date, previous_question, tool_answer, given_answer, thumbs, feedback_text, thread_id))
            self.conn.commit()
        except Exception as e:
            print(f"Error inserting feedback into the database: {e}")
            raise

    def close(self) -> None:
        """
        Closes the database connection if it is open.

        This method ensures that both the cursor and connection to the database are properly closed,
        releasing any held resources. It is recommended to call this method when the database interactions
        are complete to prevent potential memory leaks or connection issues.

        Returns:
            None
        """
        if self.conn:
            self.conn.close()
            print("Database connection closed.")



import json
import pyodbc
import os
from typing import Any, Dict, List, Optional, Tuple, Union

class PromptDatabase:
    """
    A class to interact with an MSSQL database for storing and retrieving prompt templates.

    This class provides methods to create tables, insert, update, query, and delete prompt records.
    It also handles the retrieval of prompt details based on various criteria. The class is designed
    to be used as a context manager to ensure proper opening and closing of database connections.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None
    ) -> None:
        """
        Initializes the connection details for the database, with the option to use environment variables as defaults.

        If parameters are not provided, they are fetched from environment variables:
            - 'MSSQL_HOST' for the host
            - 'MSSQL_USER' for the username
            - 'MSSQL_PASS' for the password
            - 'MSSQL_DB' for the database name

        Args:
            host (Optional[str], optional): The database server host. Defaults to environment variable 'MSSQL_HOST'.
            user (Optional[str], optional): The database username. Defaults to environment variable 'MSSQL_USER'.
            password (Optional[str], optional): The database password. Defaults to environment variable 'MSSQL_PASS'.
            database (Optional[str], optional): The database name. Defaults to environment variable 'MSSQL_DB'.
        """
        self.host: str = host if host is not None else os.getenv('MSSQL_HOST')
        self.user: str = user if user is not None else os.getenv('MSSQL_USER')
        self.password: str = password if password is not None else os.getenv('MSSQL_PASS')
        self.database: str = database if database is not None else os.getenv('MSSQL_DB')
        self.conn: Optional[pyodbc.Connection] = None
        self.cursor: Optional[pyodbc.Cursor] = None
        
    def __enter__(self) -> 'PromptDatabase':
        """
        Establishes the database connection and returns the instance itself when entering the context.

        This method is called when entering the context of the `with` statement.

        Returns:
            PromptDatabase: The instance of the class with an active database connection.
        
        Raises:
            pyodbc.Error: If there is an error connecting to the database.
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

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any]
    ) -> None:
        """
        Closes the database connection and cursor when exiting the context.
        Handles any exceptions that occurred within the context.

        This method is called when exiting the context of the `with` statement, regardless of whether
        an exception occurred.

        Args:
            exc_type (Optional[type]): The type of the exception.
            exc_val (Optional[BaseException]): The exception instance.
            exc_tb (Optional[Any]): The traceback object.

        Returns:
            None
        """
        if self.cursor is not None:
            self.cursor.close()
            self.cursor = None
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        if exc_type or exc_val or exc_tb:
            pass

    def query_sql_prompt_strings(
        self,
        prompt_names: List[str]
    ) -> Dict[str, str]:
        """
        Fetches the existing prompt strings for a given list of prompt names, maintaining the order of prompt_names.

        This method constructs and executes a SQL query that retrieves prompt names and their corresponding
        prompt strings from the 'PromptStrings' table. It ensures that the results are ordered based on the
        sequence of prompt names provided in the input list.

        Args:
            prompt_names (List[str]): A list of prompt names for which to retrieve the prompt strings.

        Returns:
            Dict[str, str]: A dictionary mapping each prompt name to its corresponding prompt string.
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
        """
        order_clause = "ORDER BY CASE PromptName "
        for idx, name in enumerate(prompt_names):
            order_clause += f"WHEN ? THEN {idx} "
        order_clause += "END"

        query = f"""
        SELECT PromptName, PromptString FROM PromptStrings
        WHERE PromptName IN ({','.join(['?'] * len(prompt_names))})
        """ + order_clause

        params = tuple(prompt_names) + tuple(prompt_names)
        self.cursor.execute(query, params)
        results = self.cursor.fetchall()
        prompt_dict: Dict[str, str] = {}
        for result in results:
            prompt_dict[result[0]] = result[1]
        return prompt_dict

    def get_records(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None
    ) -> List[pyodbc.Row]:
        """
        Executes a SQL query and retrieves all matching records.

        Args:
            query (str): The SQL query to execute.
            params (Optional[Tuple[Any, ...]], optional): A tuple of parameters to pass with the SQL query.
                                                           Defaults to None.

        Returns:
            List[pyodbc.Row]: A list of rows resulting from the executed query. Returns an empty list if an error occurs.
        """
        try:
            if self.conn is None:
                self.__enter__()
            self.cursor.execute(query, params)
            records = self.cursor.fetchall()
            return records
        except Exception:
            return []

    def get_records_from_column(
        self,
        table: str,
        column: str
    ) -> List[Any]:
        """
        Fetches distinct records from a specified column in a specified table.

        Args:
            table (str): The name of the table to query.
            column (str): The name of the column from which to retrieve distinct records.

        Returns:
            List[Any]: A list of distinct values from the specified column. Returns an empty list if no records are found.
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
        """
        query = f"SELECT DISTINCT {column} FROM {table}"
        records = self.get_records(query)
        return [record[0] for record in records] if records else []

    def get_all_records_from_table(
        self,
        table_name: str
    ) -> Tuple[List[pyodbc.Row], List[str]]:
        """
        Fetches all records and all columns from a given table.

        Args:
            table_name (str): The name of the table from which to fetch records.

        Returns:
            Tuple[List[pyodbc.Row], List[str]]: 
                - A list of all records from the specified table.
                - A list of column names corresponding to the records.
                Returns two empty lists if an error occurs.
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
        """
        query = f"SELECT * FROM {table_name}"
        try:
            self.cursor.execute(query)
            records = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            return records, columns
        except Exception as e:
            print(f"Failed to fetch records: {e}")
            return [], []  # Return empty lists in case of an error

    def get_prompts_for_username(
        self,
        username: str
    ) -> List[pyodbc.Row]:
        """
        Fetches all prompt texts and matching variable names for a given username.

        Args:
            username (str): The username (or partial username) for which to fetch prompt texts and variable names.

        Returns:
            List[pyodbc.Row]: A list of records containing prompt details matching the specified username.
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
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

    def add_record(
        self,
        table: str,
        **fields: Any
    ) -> Optional[int]:
        """
        Inserts a new record into the specified table with the provided fields.

        Args:
            table (str): The name of the table to insert the record into.
            **fields (Any): Arbitrary keyword arguments representing column-value pairs to insert.

        Returns:
            Optional[int]: The ID of the inserted record if the table has an identity column. Returns None if insertion fails.
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
        """
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

    def add_new_record(
        self,
        username: str,
        filename: str,
        variablename: str,
        promptstring: str,
        promptname: str,
        comment: str
    ) -> str:
        """
        Adds a new prompt record to the database, handling the relationships between users, files, variables, and prompts.

        Args:
            username (str): The name of the user.
            filename (str): The name of the Python file associated with the variable.
            variablename (str): The name of the variable.
            promptstring (str): The prompt string content.
            promptname (str): The name of the prompt.
            comment (str): Additional comments or metadata for the prompt.

        Returns:
            str: A success message if the record is added successfully, otherwise an error message.
        """
        try:
            self.cursor.execute("SELECT UserID FROM Users WHERE Username = ?", (username,))
            user_result = self.cursor.fetchone()
            user_id = user_result[0] if user_result else None

            self.cursor.execute("SELECT VariableID FROM PromptVariables WHERE VariableName = ?", (variablename,))
            variable_result = self.cursor.fetchone()
            variable_id = variable_result[0] if variable_result else None

            self.cursor.execute("SELECT FileID FROM PythonFiles WHERE Filename = ?", (filename,))
            file_result = self.cursor.fetchone()
            file_id = file_result[0] if file_result else None

            if not all([user_id, variable_id, file_id]):
                return "Error: Missing UserID, VariableID, or VariableFileID."

            self.cursor.execute(
                "INSERT INTO PromptStrings (PromptString, PromptName, Comment, UserID, VariableID, VariableFileID) VALUES (?, ?, ?, ?, ?, ?)",
                (promptstring, promptname, comment, user_id, variable_id, file_id)
            )

            self.conn.commit()
            return "Record added successfully."
        except Exception as e:
            self.conn.rollback()
            return f"Failed to add the record: {e}"

    def update_record(
        self,
        table: str,
        fields: Dict[str, Any],
        condition: Tuple[str, List[Any]]
    ) -> str:
        """
        Updates records in the specified table based on a condition.

        Args:
            table (str): The name of the table to update.
            fields (Dict[str, Any]): A dictionary of column names and their new values.
            condition (Tuple[str, List[Any]]): A tuple containing the condition string and its values 
                                               (e.g., ("UserID = ?", [user_id])).

        Returns:
            str: A success message if the record is updated successfully, otherwise an error message.
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
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
        
    def delete_prompt_by_name(
        self,
        promptname: str
    ) -> str:
        """
        Deletes a prompt record from the 'PromptStrings' table by its prompt name.

        This method removes the specified prompt from the database. It also handles deletions or updates in related tables
        if necessary to maintain referential integrity.

        Args:
            promptname (str): The name of the prompt to delete.

        Returns:
            str: A success message if the prompt is deleted successfully, otherwise an error message.
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
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
    
    def update_prompt_record(
        self,
        promptname: str,
        new_promptstring: str,
        new_comment: str
    ) -> str:
        """
        Updates the PromptString and Comment fields of an existing prompt record identified by PromptName.

        Args:
            promptname (str): The name of the prompt to update.
            new_promptstring (str): The new value for the PromptString field.
            new_comment (str): The new value for the Comment field.

        Returns:
            str: A success message if the prompt record is updated successfully, otherwise an error message.
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
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

    def search_for_string_in_prompt_text(
        self,
        search_string: str
    ) -> List[Dict[str, str]]:
        """
        Lists all prompt names and prompt texts where a specific string is part of the prompt text.

        Args:
            search_string (str): The string to search for within prompt texts.

        Returns:
            List[Dict[str, str]]: A list of dictionaries, each containing 'PromptName' and 'PromptString' 
                                  for records matching the search criteria.
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
        """
        self.cursor.execute('''
        SELECT PromptName, PromptString
        FROM PromptStrings
        WHERE PromptString LIKE ?
        ''', ('%' + search_string + '%',))
        results = self.cursor.fetchall()
    
        records = [{'PromptName': row[0], 'PromptString': row[1]} for row in results]
        return records

    def get_prompt_details_by_name(
        self,
        promptname: str
    ) -> Optional[Dict[str, str]]:
        """
        Fetches the details of a prompt record identified by PromptName.

        Args:
            promptname (str): The name of the prompt to fetch details for.

        Returns:
            Optional[Dict[str, str]]: A dictionary containing 'PromptString' and 'Comment' of the prompt 
                                      if found, otherwise `None`.
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
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
                return {"PromptString": result[1], "Comment": result[2]}
            else:
                return None
        except Exception as e:
            print(f"Error occurred: {e}")
            return None

    def update_all_record(
        self,
        original_value: str,
        new_value: str,
        table: str,
        column: str
    ) -> str:
        """
        Updates a specific record identified by the original value in a given table and column.

        This method ensures that only valid tables and columns are updated to prevent SQL injection
        and maintain data integrity.

        Args:
            original_value (str): The current value to identify the record to update.
            new_value (str): The new value to set for the specified column.
            table (str): The name of the table to update.
            column (str): The name of the column to update.

        Returns:
            str: A success message if the record is updated successfully, otherwise an error message.
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
    
    def get_prompt_details_for_all(
        self,
        value: str,
        table: str,
        column: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the details of a record identified by a value in a specific table and column.

        Args:
            value (str): The value to fetch details for.
            table (str): The name of the table to fetch from.
            column (str): The name of the column to match the value against.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing the record's details if found, otherwise `None`.
        
        Raises:
            ValueError: If the specified table or column is invalid.
            pyodbc.Error: If there is an error executing the SQL statement.
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

    def close(self) -> None:
        """
        Closes the database connection and cursor, if they exist.

        This method ensures that both the cursor and connection to the database are properly closed,
        releasing any held resources. It is recommended to call this method when the database interactions
        are complete to prevent potential memory leaks or connection issues.

        Returns:
            None
        """
        if self.cursor is not None:
            self.cursor.close()
            self.cursor = None
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def query_sql_record(self, prompt_name: str) -> Optional[Dict[str, str]]:
        """
        Fetches the existing prompt text and comment for a given prompt name.

        Args:
            prompt_name (str): The name of the prompt.

        Returns:
            Optional[Dict[str, str]]: A dictionary with 'prompt_text' and 'comment' if the record exists, else None.
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

    def get_file_path_by_name(self, filename: str) -> Optional[str]:
        """
        Fetches the FilePath for a given Filename from the PythonFiles table.

        Args:
            filename (str): The name of the file to fetch the path for.

        Returns:
            Optional[str]: The FilePath of the file if found, otherwise None.
        """
        query = "SELECT FilePath FROM PythonFiles WHERE Filename = ?"
        try:
            self.cursor.execute(query, (filename,))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error occurred: {e}")
            return None

    def update_filename_and_path(
        self,
        original_filename: str,
        new_filename: str,
        new_file_path: str
    ) -> Optional[str]:
        """
        Updates the Filename and FilePath in the PythonFiles table for a given original Filename.

        Args:
            original_filename (str): The original name of the file to update.
            new_filename (str): The new name for the file.
            new_file_path (str): The new path for the file.

        Returns:
            Optional[str]: A success message if the record is updated successfully, otherwise None.
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

    def add_relationship_record(
        self,
        prompt_id: int,
        user_id: int,
        variable_id: int,
        file_id: int
    ) -> str:
        """
        Adds a new relationship record to the CentralRelationshipTable.

        Args:
            prompt_id (int): The ID of the prompt.
            user_id (int): The ID of the user.
            variable_id (int): The ID of the variable.
            file_id (int): The ID of the file.

        Returns:
            str: A success message if the record is added successfully, otherwise an error message.
        """
        query = """
        INSERT INTO CentralRelationshipTable (PromptID, UserID, VariableID, FileID)
        VALUES (?, ?, ?, ?);
        """
        try:
            self.cursor.execute(query, (prompt_id, user_id, variable_id, file_id))
            self.conn.commit()
            return "Record added successfully"
        except Exception as e:
            self.conn.rollback()
            return f"Error in add_relationship_record: {e}"

    def update_relationship_record(
        self,
        record_id: int,
        prompt_id: Optional[int] = None,
        user_id: Optional[int] = None,
        variable_id: Optional[int] = None,
        file_id: Optional[int] = None
    ) -> str:
        """
        Updates a relationship record in the CentralRelationshipTable based on provided parameters.

        Args:
            record_id (int): The ID of the relationship record to update.
            prompt_id (Optional[int], optional): The new PromptID to set. Defaults to None.
            user_id (Optional[int], optional): The new UserID to set. Defaults to None.
            variable_id (Optional[int], optional): The new VariableID to set. Defaults to None.
            file_id (Optional[int], optional): The new FileID to set. Defaults to None.

        Returns:
            str: A success message if the record is updated successfully, otherwise an error message.
        """
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

    def delete_record(
        self,
        table: str,
        condition: Tuple[str, Any]
    ) -> str:
        """
        Deletes a record from a specified table based on a condition.

        Args:
            table (str): The name of the table from which to delete the record.
            condition (Tuple[str, Any]): A tuple containing the condition string and its parameters
                                            (e.g., ("ID = ?", id_value)).

        Returns:
            str: A success message if the record is deleted successfully, otherwise an error message.
        """
        query = f"DELETE FROM {table} WHERE {condition[0]}"
        try:
            self.cursor.execute(query, condition[1])
            self.conn.commit()
            return "Record deleted successfully"
        except Exception as e:
            self.conn.rollback()
            return f"Error in delete_record: {e}"

    def get_record_by_name(
        self,
        table: str,
        name_column: str,
        value: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the entire record from a specified table based on a column name and value.

        Args:
            table (str): The table to search in.
            name_column (str): The column name to match the value against.
            value (str): The value to search for.

        Returns:
            Optional[Dict[str, Any]]: A dictionary with the record data or None if no record is found.
        """
        query = f"SELECT * FROM {table} WHERE {name_column} = ?"
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
        
    def get_relationships_by_user_id(
        self,
        user_id: int
    ) -> Union[List[Dict[str, Any]], bool]:
        """
        Fetches relationship records for a given user ID.
        
        Args:
            user_id (int): The ID of the user for whom to fetch relationship records.
        
        Returns:
            Union[List[Dict[str, Any]], bool]: 
                - A list of dictionaries containing relationship details if records are found.
                - `False` if an error occurs during the fetch.
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
        except Exception:
            return False
        
        return relationships
    
    def fetch_relationship_data(
        self,
        prompt_id: Optional[int] = None
    ) -> List[pyodbc.Row]:
        """
        Fetches relationship data from the CentralRelationshipTable, optionally filtered by PromptID.

        Args:
            prompt_id (Optional[int], optional): The PromptID to filter the relationship records. 
                                                    If None, fetches all records.

        Returns:
            List[pyodbc.Row]: A list of relationship records matching the criteria.
        """
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
    
    def get_prompts_contain_in_name(
        self,
        promptname: str
    ) -> List[Dict[str, str]]:
        """
        Fetches the details of prompt records where the PromptName contains the given string.

        Args:
            promptname (str): The string to search for in the prompt names.

        Returns:
            List[Dict[str, str]]: 
                - A list of dictionaries with 'PromptName', 'PromptString', and 'Comment' for matching records.
                - An empty list if no matching records are found.
        
        Raises:
            pyodbc.Error: If there is an error executing the SQL statement.
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
                return [
                    {
                        "PromptName": result[0],
                        "PromptString": result[1],
                        "Comment": result[2]
                    } for result in results
                ]
            else:
                return []
        except Exception as e:
            print(f"Error occurred: {e}")
            return []


@st.cache_data
def work_prompts() -> Dict[str, str]:
    """
    Retrieves and constructs a mapping of prompt names to their corresponding prompt strings.

    This function performs the following steps:
        1. Defines a default prompt string to be used as a fallback.
        2. Initializes a dictionary of prompt names mapped to the default prompt.
        3. Retrieves environment variable values corresponding to each prompt name.
        4. Uses the `PromptDatabase` class to fetch prompt strings from the database based on the environment variable values.
        5. Constructs the final `prompt_map` dictionary by:
            - Assigning the fetched prompt string if available.
            - Falling back to the default prompt if no database entry is found.

    Returns:
        Dict[str, str]: A dictionary mapping each prompt name to its corresponding prompt string.
                        If a prompt string is not found in the database, the default prompt is used.
    """
    default_prompt = "You are a helpful assistant."

    all_prompts = {
        "text_from_image": default_prompt,
        "contextual_compression": default_prompt,
        "rag_self_query": default_prompt,
        "hyde_rag": default_prompt,
        "choose_rag": default_prompt,
        "sys_ragbot": default_prompt,
        "rag_answer_reformat": default_prompt,
    }

    prompt_names = list(all_prompts.keys())

    # Build a mapping from original prompt names to environment variable values
    prompt_env_map = {name: getenv(name.upper()) for name in prompt_names}

    # Extract the environment variable values
    env_vars = list(prompt_env_map.values())
    with PromptDatabase() as db:
        # Fetch the prompt strings from the database using the environment variable values
        sql_results = db.query_sql_prompt_strings(env_vars)

    # Build the output dictionary with original prompt names as keys
    prompt_map: Dict[str, str] = {}
    for prompt_name in prompt_names:
        env_var = prompt_env_map[prompt_name]
        prompt_string = sql_results.get(env_var)
        if prompt_string is not None:
            prompt_map[prompt_name] = prompt_string
        else:
            # Use the default prompt if no result is found in the database
            prompt_map[prompt_name] = all_prompts[prompt_name]
    return prompt_map