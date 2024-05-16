import mysql
import os
import streamlit as st
import uuid

from openai import OpenAI
from myfunc.retrievers import HybridQueryProcessor
from myfunc.varvars_dicts import work_vars
from myfunc.prompts import ConversationDatabase, PromptDatabase

try:
    with PromptDatabase() as db:
        prompt_map = db.get_prompts_by_names(["rag_answer_reformat", "sys_ragbot"],[os.getenv("RAG_ANSWER_REFORMAT"), os.getenv("SYS_RAGBOT")])
        st.session_state.rag_answer_reformat = prompt_map.get("rag_answer_reformat", "You are helpful assistant")
        st.session_state.sys_ragbot = prompt_map.get("sys_ragbot", "You are helpful assistant")
        print("Fail promptdatabase load")
except:
    st.session_state.rag_answer_reformat = """"
    Based on the context > 
                {context} 
                answer this question > 
                {prompt}
    If you are asked for a list do not comment, only pass the list from the context. If you are asked for a list, just return the list from context if any.
    """
    st.session_state.sys_ragbot = """Always write in Serbian language. Converse like you are an experienced sales person and consultant. Always try to offer a service from Positive doo, FOCUSING ON THE USER'S NEEDS AND HOW TO MEET THEM. TAILOR COMMUNICATION SO THAT IT IS FOCUSED ON SOLVING THE PROBLEM, RATHER THAN JUST LISTING THE AVAILABLE OPTIONS aka services. Emphasize that company is expert in every domain that it offers.  ALWAYS KEEP CONVERSATION ALIVE BY ASKING QUESTIONS because you want to make them realize that they have a problem or that they need something to expand and improve their business. Get to know their WEEK SPOTS. Then try selling our service based on what you came to conclusion that they need!! Do that through NON invasive conversation.  KEEP ASKING ADDITIONAL QUESTIONS TO IDENTIFY WHERE THEY NEED HELP AND WHERE OUR COMPANY HAS SPACE TO SELL THE SERVICE EVEN IF THEY DIDN’T EXPRESS ANY PARTICULAR PROBLEM AND THEY ARE JUST ASKING INFORMATIVE QUESTIONS ABOUT THE COMPANY!!!  TRY TO GET TO KNOW THEIR PAINS AND THEN OFFER COMPANY SOLUTION BUT THROUGH AFFIRMATIVE WAY.  !!! When listing or mentioning company services ALWAYS generate answer in a maner that describes how are they benefitial for them and their business, aka WHAT it will SOLVE!!!  Based on the conversation and client’s question, PROVIDE THE RIGHT LINK!  Keep answers CONCISE and precise. It is not in your interest to bore a customer with too long text!!! Try to keep it SHORT BUT FULLY INFORMATIVE! Remove all sentences that are not relevant to a topic discussed! Be friendly, creative and polite!!!  !!!  EVERYTIME YOU GENERATE the sentence HIGHLIGHT THE NAME OF THE COMPANY – Positive! Do that so it looks human aka natural! Put it in right case.  !!! Everytime it is your time to speak, start a sentence different way. Try not to repeat yourself!!! !!!  ############ Here is some context you can use when answering questions about Positive doo: Company is located in Danila Kiša 5, Novi Sad. Main focus of the company is on digital transformation, i.e. raising the efficiency of business by applying modern technologies. By improving business processes, company creates conditions for clients to fully utilize the benefits of our PAM business solution, and uses artificial intelligence (AI) in the process of automating work tasks.  WHO ARE WE? A team that initiates positive business changes ( 3P )  WHAT ARE WE DOING? We increase business results by using the most modern technologies   HOW WE DO IT? - WE IMPROVE EFFICIENCY - Business consulting - WE INCREASE EFFICIENCY - Digital tools - WE PROVIDE RELIABILITY - IT infrastructure (reliability consists of security, connectivity and continuity)  Main characters behind this company and its high quality services are Miljan Radanović owner and managing director and Darko Perović CEO.  ############  If you are asked about WORKING HOURS, YOU HAVE TO explicitly answer monday to friday 08-16h.  If a customer wants to book an appointment, highlight working hours and offer phone: 021/1234567. AVOID asking more questions like customers preferences when it comes to date and time.  If you are asked about GENERAL INFORMATION about the company, you HAVE TO GENERATE THE ANSWER BASED ON YOUR KNOWLEDGE and ALWAYS PROVIDE THIS LINK: https://positive.rs/o-nama/kompanija/ , stuff@positive.rs   If you are asked TECHNICAL question, you HAVE TO GENERATE THE ANSWER BASED ON YOUR KNOWLEDGE and ALWAYS PROVIDE LINK: podrska@positive.rs  If you are asked about the FEATURE OF A PRODUCT OR ABOUT ANY PARTICULAR SERVICE, you HAVE TO GENERATE THE ANSWER BASED ON YOUR KNOWLEDGE and ALWAYS PROVIDE LINK: prodaja@positive.rs"""

processor = HybridQueryProcessor(namespace="embedding-za-sajt")
client=OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def main():
    if "username" not in st.session_state:
        st.session_state.username = "positive"    
    if "openai_model" not in st.session_state:
        st.session_state["openai_model"] = work_vars["names"]["openai_model"]
    if "azure_filename" not in st.session_state:
        st.session_state.azure_filename = "altass.csv"
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "app_name" not in st.session_state:
        st.session_state.app_name = "TestBot"
    if "thread_id" not in st.session_state:
        def get_thread_ids():
            with ConversationDatabase() as db:
                return db.list_threads(st.session_state.app_name, st.session_state.username)
        new_thread_id = str(uuid.uuid4())
        thread_name = f"Thread_{new_thread_id}"
        conversation_data = [{'role': 'system', 'content': st.session_state.sys_ragbot}]
        
        if thread_name not in get_thread_ids():
            with ConversationDatabase() as db:
                try:
                    db.add_sql_record(st.session_state.app_name, st.session_state.username, thread_name, conversation_data)
                except mysql.connector.IntegrityError as e:
                    if e.errno == 1062:  # Duplicate entry for key
                        st.error("Thread ID already exists. Please try again with a different ID.")
                    else:
                        raise  # Re-raise the exception if it's not related to a duplicate entry
        st.session_state.thread_id = thread_name
        st.session_state.messages[thread_name] = []
        st.session_state.messages[thread_name].append({'role': 'system', 'content': st.session_state.sys_ragbot})
    if "sys_ragbot" not in st.session_state:
        st.session_state.sys_ragbot = st.session_state.sys_ragbot
        st.session_state.messages[thread_name].append({'role': 'system', 'content': st.session_state.sys_ragbot})
    
    avatar_ai="bot.png"
    avatar_user = "user.webp"
    avatar_sys = "positivelogo.jpg"
    
    if st.session_state.thread_id is None:
        st.info("Start a conversation by selecting a new or existing conversation.")
    else:
        current_thread_id = st.session_state.thread_id
        
        # Check if there's an existing conversation in the session state
        if current_thread_id not in st.session_state.messages:
            # If not, initialize it with the conversation from the database or as an empty list
            with ConversationDatabase() as db:
                st.session_state.messages[current_thread_id] = db.query_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id) or []
        
        if current_thread_id in st.session_state.messages:
            # avatari primena
            for message in st.session_state.messages[current_thread_id]:
                if message["role"] == "assistant": 
                    with st.chat_message(message["role"], avatar=avatar_ai):
                            st.markdown(message["content"])
                elif message["role"] == "user":         
                    with st.chat_message(message["role"], avatar=avatar_user):
                            st.markdown(message["content"])
                elif message["role"] == "system":
                    pass
                else:         
                    with st.chat_message(message["role"], avatar=avatar_sys):
                            st.markdown(message["content"])

    # Main conversation UI
    if prompt := st.chat_input("Kako vam mogu pomoci? - Token test 15.05.24"):
        # Original processing to generate complete_prompt
        context, scores, emb_prompt_tokens = processor.process_query_results(prompt)
        complete_prompt = st.session_state.rag_answer_reformat.format(prompt=prompt, context=context)
        st.write(context, "AAA", scores)
        # Append only the user's original prompt to the actual conversation log
        st.session_state.messages[current_thread_id].append({"role": "user", "content": prompt})
    
        # Display user prompt in the chat
        with st.chat_message("user", avatar=avatar_user):
            st.markdown(prompt)
        
        # Prepare a temporary messages list for generating the assistant's response
        temp_messages = st.session_state.messages[current_thread_id].copy()
        temp_messages[-1] = {"role": "user", "content": complete_prompt}  # Replace last message with enriched context
        
        # Generate and display the assistant's response using the temporary messages list
        with st.chat_message("assistant", avatar=avatar_ai):
            message_placeholder = st.empty()
            full_response = ""
            for response in client.chat.completions.create(
                model=work_vars["names"]["openai_model"],
                temperature=0,
                messages=temp_messages,  # Use the temporary list with enriched context
                stream=True,
            ):
                full_response += (response.choices[0].delta.content or "")
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        
        # Append assistant's response to the conversation
        st.session_state.messages[current_thread_id].append({"role": "assistant", "content": full_response})
        # st.write(st.session_state.messages[current_thread_id])
        with ConversationDatabase() as db:
            db.update_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id, st.session_state.messages[current_thread_id])
            db.add_token_record(app_id='klotbot', model_name=st.session_state["openai_model"], embedding_tokens=emb_prompt_tokens, complete_prompt=complete_prompt, full_response=full_response, messages=st.session_state.messages[current_thread_id])


if __name__ == "__main__":
     main()