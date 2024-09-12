import streamlit as st
import pandas as pd
from krembot_db import ConversationDatabase
import json

st.set_page_config(layout="wide")

st.title("Viewer Application")
st.caption("Choose to view feedback or conversations, and select an application name.")

# Sidebar for radio button selection
view_option = st.sidebar.radio("Choose what to view", ("Feedbacks", "Conversations"))

def get_app_names(table_name):
    with ConversationDatabase() as db:
        query = f"SELECT DISTINCT app_name FROM {table_name}"
        db.cursor.execute(query)
        results = db.cursor.fetchall()
        app_names = [row[0] for row in results]
    return app_names

def get_feedback_records(app_name):
    with ConversationDatabase() as db:
        query = """
        SELECT thread_id, previous_question, tool_answer, given_answer, Thumbs, Feedback_text
        FROM Feedback
        WHERE app_name = ?
        """
        db.cursor.execute(query, app_name)
        records = db.cursor.fetchall()
        columns = ['thread_id', 'previous_question', 'tool_answer', 'given_answer', 'Thumbs', 'Feedback_text']
    return records, columns

def get_user_names(app_name):
    with ConversationDatabase() as db:
        query = """
        SELECT DISTINCT user_name
        FROM [PositiveAI].[dbo].[conversations]
        WHERE app_name = ?
        """
        db.cursor.execute(query, app_name)
        results = db.cursor.fetchall()
        user_names = [row[0] for row in results]
    return user_names

def get_conversation_records(app_name, user_name):
    with ConversationDatabase() as db:
        query = """
        SELECT thread_id, conversation
        FROM [PositiveAI].[dbo].[conversations]
        WHERE app_name = ? AND user_name = ?
        """
        db.cursor.execute(query, (app_name, user_name))
        records = db.cursor.fetchall()
        columns = ['thread_id', 'conversation']
    return records, columns

def extract_feedback_by_thread_id(thread_id, records):
    # Filter records by the given thread_id
    return [record for record in records if record[0] == thread_id]

def extract_conversation_by_thread_id(thread_id):
    with ConversationDatabase() as db:
        query = """
        SELECT conversation
        FROM [PositiveAI].[dbo].[conversations]
        WHERE thread_id = ?
        """
        db.cursor.execute(query, (thread_id,))
        result = db.cursor.fetchone()
    return result[0] if result else None

def parse_and_display_conversation(conversation_json):
    # Load the JSON-formatted string
    conversation = json.loads(conversation_json)
    
    # Filter out conversations that only have system messages
    non_system_messages = [msg for msg in conversation if msg['role'] != 'system']
    
    if not non_system_messages:
        st.write("This conversation contains only system messages, skipping...")
        return
    
    # Display the conversation messages
    for msg in non_system_messages:
        if msg['role'] == 'user':
            st.write(f"**USER:** {msg['content']}")
        elif msg['role'] == 'assistant':
            st.write(f"**ASSISTANT:** {msg['content']}")
        st.divider()  # Add a divider between conversation pairs

def filter_out_system_only_conversations(records):
    filtered_records = []
    for record in records:
        conversation_json = record[1]  # Assuming conversation is in the second column
        conversation = json.loads(conversation_json)
        
        # Check if conversation has non-system messages
        non_system_messages = [msg for msg in conversation if msg['role'] != 'system']
        
        if non_system_messages:  # Only include conversations with user/assistant messages
            filtered_records.append(record)
    
    return filtered_records

# Determine the table to fetch application names from based on the selected option
if view_option == "Feedbacks":
    app_names = get_app_names("Feedback")
else:
    app_names = get_app_names("[PositiveAI].[dbo].[conversations]")

# Fetch app names and display in a dropdown
selected_app_name = st.selectbox("Select Application Name", [''] + app_names)

if selected_app_name:
    if view_option == "Feedbacks":
        # Fetch feedback records for the selected app name
        records, columns = get_feedback_records(selected_app_name)

        if records:
            df = pd.DataFrame.from_records(records, columns=columns)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Entry field for thread_id after showing the DataFrame
            selected_thread_id = st.text_input("Enter the Thread ID to filter feedback")

            if selected_thread_id:
                # Filter feedback by the provided thread_id
                filtered_feedback = extract_feedback_by_thread_id(selected_thread_id, records)

                if filtered_feedback:
                    feedback = filtered_feedback[0]  # Assume only one record will match
                    st.write(f"**USER:** {feedback[1]}")        # previous_question
                    st.divider()
                    st.write(f"**TOOL:** {feedback[2]}")        # tool_answer
                    st.divider()
                    st.write(f"**ASSISTANT:** {feedback[3]}")   # given_answer
                else:
                    st.write(f"No feedback found for Thread ID: {selected_thread_id}")
        else:
            st.write("No feedback records found for the selected application name.")

    else:
        # Fetch user names for the selected app name
        user_names = get_user_names(selected_app_name)
        selected_user_name = st.selectbox("Select User Name", [''] + user_names)

        if selected_user_name:
            # Fetch conversation records for the selected app name and user name
            records, columns = get_conversation_records(selected_app_name, selected_user_name)

            # Filter out system-only conversations
            records = filter_out_system_only_conversations(records)

            if records:
                df = pd.DataFrame.from_records(records, columns=columns)
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Entry field for thread_id in Conversations
                selected_thread_id = st.text_input("Enter the Thread ID to extract the conversation")

                # Fetch and display conversation based on thread_id input
                if selected_thread_id:
                    conversation_text = extract_conversation_by_thread_id(selected_thread_id)

                    if conversation_text:
                        st.write(f"Conversation for Thread ID: {selected_thread_id}")
                        parse_and_display_conversation(conversation_text)
                    else:
                        st.write(f"No conversation found for Thread ID: {selected_thread_id}")
            else:
                st.write(f"No conversation records found for the selected user.")
else:
    st.write("Please select an application name to proceed.")
