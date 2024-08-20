import streamlit as st
import pandas as pd
from krembot_db import ConversationDatabase

st.set_page_config(layout="wide")

st.title("Feedback Viewer")
st.caption("Choose an application name to view feedback records")

def get_app_names():
    with ConversationDatabase() as db:
        query = "SELECT DISTINCT app_name FROM Feedback"
        db.cursor.execute(query)
        results = db.cursor.fetchall()
        app_names = [row[0] for row in results]
    return app_names

def get_feedback_records(app_name):
    with ConversationDatabase() as db:
        query = """
        SELECT thread_id, app_name, previous_question, tool_answer, given_answer, Thumbs, Feedback_text
        FROM Feedback
        WHERE app_name = ?
        """
        db.cursor.execute(query, app_name)
        records = db.cursor.fetchall()
        columns = ['thread_id', 'app_name', 'previous_question', 'tool_answer', 'given_answer', 'Thumbs', 'Feedback_text']
    return records, columns

# Fetch app names and display in a dropdown
app_names = get_app_names()
selected_app_name = st.selectbox("Select Application Name", [''] + app_names)

if selected_app_name:
    # Fetch feedback records for the selected app name
    records, columns = get_feedback_records(selected_app_name)
    
    if records:
        df = pd.DataFrame.from_records(records, columns=columns)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Button to export data to CSV
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Export to CSV",
            data=csv,
            file_name=f'feedback_{selected_app_name}.csv',
            mime='text/csv',
        )
    else:
        st.write("No feedback records found for the selected application name.")
