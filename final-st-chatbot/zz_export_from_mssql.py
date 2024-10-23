import streamlit as st
import pandas as pd
import json
from st_aggrid import AgGrid, GridOptionsBuilder
from krembot_db import ConversationDatabase

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
        SELECT id, date, previous_question, tool_answer, given_answer, Thumbs, Feedback_text
        FROM Feedback
        WHERE app_name = ?
        """
        db.cursor.execute(query, app_name)
        records = db.cursor.fetchall()
        columns = ['id', 'date', 'previous_question', 'tool_answer', 'given_answer', 'Thumbs', 'Feedback_text']
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
        SELECT id, date, conversation
        FROM [PositiveAI].[dbo].[conversations]
        WHERE app_name = ? AND user_name = ?
        """
        db.cursor.execute(query, (app_name, user_name))
        records = db.cursor.fetchall()
        columns = ['id', 'date,' 'conversation']
    return records, columns

def filter_out_system_only_conversations(records):
    """Filter out conversations that only contain system prompts."""
    filtered_records = []
    for record in records:
        # Ensure you're accessing the correct index for the conversation JSON string
        conversation_json = record[2]  # Assuming conversation JSON is in the third column (index 2)

        # Check if 'conversation_json' is a valid string before trying to parse it
        if isinstance(conversation_json, str):
            try:
                conversation = json.loads(conversation_json)

                # Check if there are any non-system messages
                non_system_messages = [msg for msg in conversation if msg.get('role') != 'system']

                if non_system_messages:  # Keep conversations with user/assistant messages
                    filtered_records.append(record)
            except json.JSONDecodeError:
                print("Skipping record with invalid JSON:", record)
        else:
            print("Skipping record with invalid conversation data:", record)
    
    return filtered_records


def filter_feedbacks_by_text(records, search_text):
    """Filter feedback records by text found in previous_question, tool_answer, or given_answer."""
    filtered_records = []
    for record in records:
        previous_question = str(record[1] or "")  # Ensure it's a string
        tool_answer = str(record[2] or "")
        given_answer = str(record[3] or "")
        feedback_text = str(record[5] or "")
        
        # Search in all columns (case-insensitive)
        if (search_text.lower() in previous_question.lower() or
            search_text.lower() in tool_answer.lower() or
            search_text.lower() in given_answer.lower() or
            search_text.lower() in feedback_text.lower()):
            filtered_records.append(record)
    
    return filtered_records


def filter_conversations_by_text(records, search_text):
    """Filter conversation records by text found in any message content."""
    filtered_records = []
    for record in records:
        # Make sure to correctly access the conversation column, not the date
        conversation_json = record[2]  # Assuming conversation is at index 2

        # Ensure 'conversation_json' is a string before attempting to parse it
        if isinstance(conversation_json, str):
            try:
                conversation = json.loads(conversation_json)

                # Search in all message contents (case-insensitive)
                for msg in conversation:
                    if search_text.lower() in msg.get('content', '').lower():
                        filtered_records.append(record)
                        break  # No need to check further once a match is found
            except json.JSONDecodeError:
                print(f"Skipping record due to invalid JSON: {conversation_json}")
        else:
            print(f"Skipping record with invalid conversation data: {record}")
    
    return filtered_records


def extract_feedback_by_thread_id(ids, records):
    # Filter records by the given thread_id
    return [record for record in records if record[0] == ids]

def extract_conversation_by_thread_id(ids):
    ids = int(ids)
    with ConversationDatabase() as db:
        query = """
        SELECT conversation
        FROM [PositiveAI].[dbo].[conversations]
        WHERE id = ?
        """
        db.cursor.execute(query, (ids,))
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

# Initialize app selection (feedbacks or conversations)
if view_option == "Feedbacks":
    app_names = get_app_names("Feedback")
else:
    app_names = get_app_names("[PositiveAI].[dbo].[conversations]")

# Fetch app names and display in a dropdown
selected_app_name = st.selectbox("Select Application Name", [''] + app_names)

if selected_app_name:
    if view_option == "Feedbacks":
        # Text input for filtering feedbacks
        search_text = st.text_input("Enter text to filter by:")

        # Fetch feedback records for the selected app name
        records, columns = get_feedback_records(selected_app_name)

        if records:
            # Apply text filter
            if search_text:
                records = filter_feedbacks_by_text(records, search_text)

            # Convert records to DataFrame for display in AgGrid
            df = pd.DataFrame.from_records(records, columns=columns)

            # Configure AgGrid for single-row selection
            gb = GridOptionsBuilder.from_dataframe(df)
            gb.configure_selection('single')  # Single row selection
            grid_options = gb.build()

            # Display interactive grid
            grid_response = AgGrid(df, gridOptions=grid_options, update_mode='SELECTION_CHANGED')

            # Access the selected rows (as a DataFrame)
            selected_rows = pd.DataFrame(grid_response['selected_rows'])

            # Ensure selected_rows is not empty and check its content
            if not selected_rows.empty:
                # Get the first selected row using iloc
                selected_row = selected_rows.iloc[0]

                # Extract values from the selected row
                selected_id = selected_row['id']

                # Filter feedback by the selected thread_id
                filtered_feedback = extract_feedback_by_thread_id(selected_id, records)

                if filtered_feedback:
                    feedback = filtered_feedback[0]
                    st.write(f"**USER:** {feedback[2]}")        # previous_question
                    st.divider()
                    st.write(f"**TOOL:** {feedback[3]}")        # tool_answer
                    st.divider()
                    st.write(f"**ASSISTANT:** {feedback[4]}")   # given_answer
                    st.divider()
                    st.write(f"**FEEDBACK:** {feedback[6]}")    # feedback text
                else:
                    st.write(f"No feedback found for Thread ID: {selected_id}")
        else:
            st.write("No feedback records found for the selected application name.")

    else:
        # Fetch user names for the selected app name
        user_names = get_user_names(selected_app_name)
        selected_user_name = st.selectbox("Select User Name", [''] + user_names)

        if selected_user_name:
            # Text input for filtering conversations
            search_text = st.text_input("Enter text to filter by:")

            # Fetch conversation records for the selected app name and user name
            records, columns = get_conversation_records(selected_app_name, selected_user_name)

            # Ensure 'columns' matches the data returned by 'records'
            columns = ['id', 'date', 'conversation']  # Make sure this matches the structure

            # Filter out conversations that contain only system prompts
            filtered_records = filter_out_system_only_conversations(records)

            # Apply text filter
            if search_text:
                filtered_records = filter_conversations_by_text(filtered_records, search_text)

            if filtered_records:
                # Convert filtered records to DataFrame for display in AgGrid
                df = pd.DataFrame.from_records(filtered_records, columns=columns)

                # Configure AgGrid for single-row selection
                gb = GridOptionsBuilder.from_dataframe(df)
                gb.configure_selection('single')  # Single row selection
                grid_options = gb.build()

                # Display interactive grid
                grid_response = AgGrid(df, gridOptions=grid_options, update_mode='SELECTION_CHANGED')

                # Access the selected rows (as a DataFrame)
                selected_rows = pd.DataFrame(grid_response['selected_rows'])

                # Ensure selected_rows is not empty
                if not selected_rows.empty:
                    # Get the first selected row using iloc
                    selected_row = selected_rows.iloc[0]

                    # Extract values from the selected row
                    selected_id = selected_row['id']

                    # Fetch and display conversation based on thread_id input
                    conversation_text = extract_conversation_by_thread_id(selected_id)

                    if conversation_text:
                        st.header(f"Conversation: {selected_id}")
                        parse_and_display_conversation(conversation_text)
                    else:
                        st.write(f"No conversation found for Thread ID: {selected_id}")
            else:
                st.write(f"No conversation records found for the selected user.")
else:
    st.write("Please select an application name to proceed.")
