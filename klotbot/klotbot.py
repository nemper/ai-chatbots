import streamlit as st
from openai import OpenAI
from myfunc.retrievers import HybridQueryProcessor
from sql_prompt import PromptDatabase

client=OpenAI()
processor = HybridQueryProcessor() # namespace moze i iz env

with PromptDatabase() as db:
    prompt_map = db.get_prompts_by_names(["result2", "result3"],["CHAT_TOOLS_PROMPT", "ALT_ASISTENT"])
    result2 = prompt_map.get("result2", "You are helpful assistant")
    result3 = prompt_map.get("result3", "You are helpful assistant")
    
def main():
    
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "thread_id" not in st.session_state:
        st.session_state["thread_id"] = "skroznovi"
        st.session_state.messages["skroznovi"] = []
        
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = result3
        st.session_state.messages["skroznovi"].append({'role': 'system', 'content': st.session_state.system_prompt})
    
    avatar_ai="bot.png" 
    avatar_user = "user.webp"
   
    for message in st.session_state.messages["skroznovi"]:
         
         if message["role"] == "assistant": 
            with st.chat_message(message["role"], avatar=avatar_ai):
                 st.markdown(message["content"])
         elif message["role"] == "user":         
            with st.chat_message(message["role"], avatar=avatar_user):
                 st.markdown(message["content"])
    # Main conversation UI
    if prompt := st.chat_input("Kako vam mogu pomoci?"):
    
        # Original processing to generate complete_prompt
        context, scores = processor.process_query_results(prompt)
        complete_prompt = result2.format(prompt=prompt, context=context)
    
        # Append only the user's original prompt to the actual conversation log
        st.session_state.messages["skroznovi"].append({"role": "user", "content": prompt})
    
        # Display user prompt in the chat
        with st.chat_message("user", avatar=avatar_user):
            st.markdown(prompt)
        
        # Prepare a temporary messages list for generating the assistant's response
        temp_messages = st.session_state.messages["skroznovi"].copy()
        temp_messages[-1] = {"role": "user", "content": complete_prompt}  # Replace last message with enriched context
    
        # Generate and display the assistant's response using the temporary messages list
        with st.chat_message("assistant", avatar=avatar_ai):
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