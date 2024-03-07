import mysql.connector
import os

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
    
    def create_sql_table(self):
        """
        Creates a table for storing conversations if it doesn't already exist.
        """
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            prompt_name VARCHAR(255) NOT NULL UNIQUE,
            comment VARCHAR(255) NOT NULL,
            prompt_text LONGTEXT NOT NULL
        );
        ''')
        # print("Table created if new.")
    
    def add_sql_record(self, prompt_name, comment, prompt_text):
        """
        Attempts to add a new record to the prompts table.
    
        Parameters:
        - prompt_name: The name of the prompt.
        - comment: Comment about the prompt.
        - prompt_text: The prompt text.
    
        If the prompt_name is not unique, insertion will fail.
        """
        try:
            self.cursor.execute('''
            INSERT INTO prompts (prompt_name, comment, prompt_text) 
            VALUES (%s, %s, %s)
            ''', (prompt_name, comment, prompt_text))
            self.conn.commit()
            return(True)
        except Exception as e:
            return(False)
            # Optionally, roll back the transaction if needed
            # self.conn.rollback()

    
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

    def query_multiple_sql_records(self, prompt_names):
        """
        Fetches the existing prompt texts a list of prompt names.

        Parameters:
        - prompt_names: The list of the name of the prompt.

        Returns:
        - A dictionary with all 'prompt_text' for rows of prompt_names if rows exists, else None.
        """
        placeholder = ','.join(['%s'] * len(prompt_names))
        self.cursor.execute(f'''
        SELECT prompt_name, prompt_text FROM prompts
        WHERE prompt_name IN ({placeholder})
        ''', prompt_names)
        rows = self.cursor.fetchall()
        if rows:
            return {name: text for name, text in rows}
        else:
            return None
            
    def delete_sql_record(self, prompt_name):
        """
        Deletes a conversation record based on app name, user name, and thread id.
        
        Parameters:
        - app_name: The name of the application.
        - user_name: The name of the user.
        - thread_id: The thread identifier.
        """
        delete_sql = '''
        DELETE FROM prompts
        WHERE prompt_name = %s
        '''
        self.cursor.execute(delete_sql, (prompt_name))
        self.conn.commit()
        # print("Conversation thread deleted.")
    
    def list_threads(self):
        """
        Lists all thread IDs for a given app name and user name.
    
        Parameters:
        - prompt_name: The name of the prompt.
        - comment: Comment.
        - prompt_text : Prompt text

        Returns:
        - Prompt record data.
        """
        self.cursor.execute('''
        SELECT DISTINCT prompt_name FROM prompts
        
        ''', )  # Correct tuple notation for a single element
        threads = self.cursor.fetchall()
        return [thread[0] for thread in threads]  # Adjust based on your schema if needed
  
    def update_sql_record(self, prompt_name, prompt_text, comment):
        """
        Updates the existing record with new prompt text and comment.

        Parameters:
        - prompt_name: The name of the prompt.
        - prompt_text: New text of the prompt.
        - comment: New comment.
        """
        self.cursor.execute('''
        UPDATE prompts
        SET prompt_text = %s, comment = %s
        WHERE prompt_name = %s 
        ''', (prompt_text, comment, prompt_name))
        self.conn.commit()
        
    def fetch_filter_records(self, comment=None):
        """
        Fetches records from the database, optionally filtered by comment.
    
        Parameters:
        - comment: Optional. The content of the comment field to filter records by.
    
        Returns:
        - A list of dictionaries, where each dictionary represents a record.
        """
        query = "SELECT comment, prompt_name, prompt_text FROM prompts"
        params = ()
        if comment:
            query += " WHERE comment = %s"
            params = (comment,)
        self.cursor.execute(query, params)
        columns = [col[0] for col in self.cursor.description]
        records = [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        return records

    def get_distinct_comments(self):
        """
        Fetches all distinct comments from the database.
    
        Returns:
            A list of distinct comments.
        """
        self.cursor.execute('SELECT DISTINCT comment FROM prompts')
        return [comment[0] for comment in self.cursor.fetchall()]
    
    def search_for_string_in_prompt_text(self, search_string):
        """
        Lists all prompt_name and prompt_text where a specific string is part of the prompt_text.

        Parameters:
        - search_string: The string to search for within prompt_text.

        Returns:
        - A list of dictionaries, each containing 'prompt_name' and 'prompt_text' for records matching the search criteria.
        """
        self.cursor.execute('''
        SELECT prompt_name, prompt_text
        FROM prompts
        WHERE prompt_text LIKE %s
        ''', ('%' + search_string + '%',))
        results = self.cursor.fetchall()
    
        # Convert the results into a list of dictionaries for easier use
        records = [{'prompt_name': row[0], 'prompt_text': row[1]} for row in results]
        return records


    def close(self):
        """
        Closes the database connection.
        """
        self.conn.close()
