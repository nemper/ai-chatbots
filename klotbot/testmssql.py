from myfunc.prompts import ConversationDatabase2

mssql_database = "PositiveAI"
mssql_host = "pendulum.positive.rs, 12001"
mssql_username = "razvoj"
mssql_password = r"ILmg0t'E4zi\6O>U7i<o"


with ConversationDatabase2(host=mssql_host, user=mssql_username, password=mssql_password, database=mssql_database) as db:
    db.create_sql_table()
    db.create_token_log_table()
    print("Tables created if they didn't exist.")

# Testing delete_sql_record
with ConversationDatabase2(host=mssql_host, user=mssql_username, password=mssql_password, database=mssql_database) as db:
    db.delete_sql_record('app_name', 'user_name', 'thread_id')
    print("Record deleted.")

# Testing list_threads
with ConversationDatabase2(host=mssql_host, user=mssql_username, password=mssql_password, database=mssql_database) as db:
    threads = db.list_threads('app_name', 'user_name')
    print(f"Threads: {threads}")

# Testing update_sql_record
with ConversationDatabase2(host=mssql_host, user=mssql_username, password=mssql_password, database=mssql_database) as db:
    db.update_sql_record('app_name', 'user_name', 'thread_id', [{'message': 'Updated message'}])
    updated_conversation = db.query_sql_record('app_name', 'user_name', 'thread_id')
    print(f"Updated Conversation: {updated_conversation}")

# Testing add_token_record_openai
with ConversationDatabase2(host=mssql_host, user=mssql_username, password=mssql_password, database=mssql_database) as db:
    db.add_token_record_openai('app_id', 'model_name', 10, 20, 30, 40, 50)
    print("Token record added.")

# Testing extract_token_sums_between_dates
with ConversationDatabase2(host=mssql_host, user=mssql_username, password=mssql_password, database=mssql_database) as db:
    start_date = '2024-01-01 00:00:00'
    end_date = '2024-12-31 23:59:59'
    token_sums = db.extract_token_sums_between_dates(start_date, end_date)
    print(f"Token Sums: {token_sums}")