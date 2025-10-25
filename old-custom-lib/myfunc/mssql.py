import json
from os import getenv
import pyodbc
import streamlit as st
from datetime import datetime

class ConversationDatabase:
    """
    A class to interact with a MSSQL database for storing and retrieving conversation data.
    """
    def __init__(self, host=None, user=None, password=None, database=None):
        self.host = host if host is not None else getenv('MSSQL_HOST')
        self.user = user if user is not None else getenv('MSSQL_USER')
        self.password = password if password is not None else getenv('MSSQL_PASS')
        self.database = database if database is not None else getenv('MSSQL_DB')
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

    def add_sql_record(
        self,
        app_name: str,
        user_name: str,
        thread_id: str,
        conversation
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
            self.cursor.execute(insert_sql, values)
            self.conn.commit()
        except Exception as e:
            print(f"Error adding token record: {e}")
            raise

    def insert_feedback(self, thread_id, app_name, previous_question, tool_answer, given_answer, thumbs, feedback_text):
        """
        Inserts feedback data into the Feedback table.
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

    def close(self):
        if self.conn:
            self.conn.close()
            print("Database connection closed.")


class PromptDatabase:
    """
    A class to interact with an MSSQL database for storing and retrieving prompt templates.
    """
    def __init__(self, host=None, user=None, password=None, database=None):
        """
        Initializes the connection details for the database, with the option to use environment variables as defaults.
        """
        self.host = host if host is not None else getenv('MSSQL_HOST')
        self.user = user if user is not None else getenv('MSSQL_USER')
        self.password = password if password is not None else getenv('MSSQL_PASS')
        self.database = database if database is not None else getenv('MSSQL_DB')
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
        SELECT PromptName, PromptString FROM PromptStrings
        WHERE PromptName IN ({','.join(['?'] * len(prompt_names))})
        """ + order_clause

        params = tuple(prompt_names) + tuple(prompt_names)
        self.cursor.execute(query, params)
        results = self.cursor.fetchall()
        dict = {}
        for result in results:
            dict[result[0]] = result[1]
        return dict

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


@st.cache_data
def work_prompts():
    default_prompt = "You are a helpful assistant that always writes in Serbian."

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
    prompt_map = {}
    for prompt_name in prompt_names:
        env_var = prompt_env_map[prompt_name]
        prompt_string = sql_results.get(env_var)
        if prompt_string is not None:
            prompt_map[prompt_name] = prompt_string
        else:
            # Use the default prompt if no result is found in the database
            prompt_map[prompt_name] = all_prompts[prompt_name]

    return prompt_map
