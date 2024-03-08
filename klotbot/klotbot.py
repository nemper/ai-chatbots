import streamlit as st
from openai import OpenAI
from myfunc.retrievers import HybridQueryProcessor
from sql_prompt import PromptDatabase

client=OpenAI()
processor = HybridQueryProcessor() # namespace moze i iz env

with PromptDatabase() as db:
    result2 = db.query_sql_record("CHAT_TOOLS_PROMPT")
    result3 = db.query_sql_record("ALT_ASISTENT")
    
def main():
    
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "thread_id" not in st.session_state:
        st.session_state["thread_id"] = "skroznovi"
        st.session_state.messages["skroznovi"] = []
        
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = result3.get('prompt_text', 'You are helpful assistant that always writes in Sebian.')
        st.session_state.messages["skroznovi"].append({'role': 'system', 'content': st.session_state.system_prompt})
    
    for message in st.session_state.messages["skroznovi"]:
         if message["role"] != "system": 
            with st.chat_message(message["role"]):
                 st.markdown(message["content"])
    
    # Main conversation UI
    if prompt := st.chat_input("Kako vam mogu pomoci?"):
    
        # Original processing to generate complete_prompt
        context, scores = processor.process_query_results(prompt)
        complete_prompt = result2.get('prompt_text', 'You are a helpful assistant that always writes in Serbian.').format(prompt=prompt, context=context)
    
        # Append only the user's original prompt to the actual conversation log
        st.session_state.messages["skroznovi"].append({"role": "user", "content": prompt})
    
        # Display user prompt in the chat
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Prepare a temporary messages list for generating the assistant's response
        temp_messages = st.session_state.messages["skroznovi"].copy()
        temp_messages[-1] = {"role": "user", "content": complete_prompt}  # Replace last message with enriched context
    
        # Generate and display the assistant's response using the temporary messages list
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            for response in client.chat.completions.create(
                model="gpt-4-turbo-preview",
                temperature=0,
                messages=temp_messages,  # Use the temporary list with enriched context
                stream=True,
            ):
                full_response += (response.choices[0].delta.content or "")
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        
        # Append assistant's response to the conversation
        st.session_state.messages["skroznovi"].append({"role": "assistant", "content": full_response})

        

    

if __name__ == "__main__":
        main()