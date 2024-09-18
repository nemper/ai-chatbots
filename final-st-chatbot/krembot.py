import io
import streamlit as st
import uuid
_ = """
import os
os.environ["CLIENT_FOLDER"] = "Delfi"
os.environ["SYS_RAGBOT"] = "DELFI_SYS_RAGBOT"
os.environ["APP_ID"] = "DelfiBot"
os.environ["CHOOSE_RAG"] = "DELFI_CHOOSE_RAG"
os.environ["OPENAI_MODEL"] = "gpt-4o-2024-08-06"
os.environ["PINECONE_HOST"] = "https://delfi-a9w1e6k.svc.aped-4627-b74a.pinecone.io"
"""

#_ = """
import os
os.environ["CLIENT_FOLDER"] = "ECD"
os.environ["SYS_RAGBOT"] = "ECD_SYS_RAGBOT"
os.environ["APP_ID"] = "ECDBot"
os.environ["CHOOSE_RAG"] = "ECD_CHOOSE_RAG"
os.environ["OPENAI_MODEL"] = "gpt-4o-2024-08-06"
os.environ["PINECONE_HOST"] = "https://neo-positive-a9w1e6k.svc.apw5-4e34-81fa.pinecone.io"
#"""
from openai import OpenAI
from os import getenv
from streamlit_mic_recorder import mic_recorder

from krembot_tools import rag_tool_answer
from krembot_db import ConversationDatabase, work_prompts
from krembot_stui import *
from krembot_funcs import *

from streamlit_feedback import streamlit_feedback

mprompts = work_prompts()

#with st.expander("Promptovi"):
#    st.write(mprompts)

default_values = {
    "_last_speech_to_text_transcript_id": 0,
    "_last_speech_to_text_transcript": None,
    "success": False,
    "toggle_state": False,
    "button_clicks": False,
    "prompt": '',
    "vrsta": False,
    "messages": {},
    "image_ai": None,
    "thread_id": str(uuid.uuid4()),
    "filtered_messages": "",
    "selected_question": None,
    "username": "positive",
    "app_name": getenv("APP_ID"),
    # "app_name": "Krembot",
    "feedback": {},
    "fb_k": {},
}

initialize_session_state(default_values)

if st.session_state.thread_id not in st.session_state.messages:
    st.session_state.messages[st.session_state.thread_id] = [{'role': 'system', 'content': mprompts["sys_ragbot"]}]

client = OpenAI(api_key=getenv("OPENAI_API_KEY"))
file_reader = FileReader()

# custom_streamlit_style()
# apply_background_image(avatar_bg)

def handle_feedback():
    feedback = st.session_state.get("fb_k", {})
    # print("Feedback received:", feedback)
    feedback_text = feedback.get('text', '')
    feedback_data = {
        "previous_question": st.session_state.get("previous_question", ""),
        "tool_answer": st.session_state.get("tool_answer", ""),
        "given_answer": st.session_state.get("given_answer", ""),
        "feedback_type": "Good" if feedback.get('score') == "👍" else "Bad",
        "optional_text": feedback_text
    }
    st.session_state.feedback = feedback_data

    # Store feedback data in the database
    try:
        with ConversationDatabase() as db:
            db.insert_feedback(
                thread_id=st.session_state.thread_id,
                app_name=st.session_state.app_name,
                previous_question=feedback_data["previous_question"],
                tool_answer=feedback_data["tool_answer"],
                given_answer=feedback_data["given_answer"],
                thumbs=feedback_data["feedback_type"],
                feedback_text=feedback_data["optional_text"]
            )
        st.toast("✔️ Feedback received and stored in the database!")
    except Exception as e:
        st.error(f"Error storing feedback: {e}")


import tiktoken

def num_tokens_from_messages(messages, model_name):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")  # Fallback encoding
    num_tokens = 0
    for message in messages:
        # Every message follows <im_start>{role/name}\n{content}<im_end>\n
        num_tokens += 4  # Tokens for <im_start>{role/name}\n{content}<im_end>\n
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
    num_tokens += 2  # Add tokens for priming
    return num_tokens


def build_messages_for_api(current_thread_id, max_tokens=120000):
    messages = []
    user_messages = [msg for msg in st.session_state.messages[current_thread_id] if msg['role'] == 'user']
    assistant_messages = [msg for msg in st.session_state.messages[current_thread_id] if msg['role'] == 'assistant']
    
    model_name = getenv("OPENAI_MODEL")
    
    # Always include the system prompt
    system_prompt = {'role': 'system', 'content': mprompts["sys_ragbot"]}
    messages = [system_prompt]
    
    # Build the full conversation history
    conversation = []
    for idx in range(len(user_messages)):
        # Add the user message without tool output
        conversation.append(user_messages[idx].copy())
        
        # Add the assistant message (if exists)
        if idx < len(assistant_messages):
            conversation.append(assistant_messages[idx])

    _ = """
    for idx in range(len(user_messages)):
        # User message with tool output
        user_msg = user_messages[idx].copy()
        if idx < len(tool_outputs):
            tool_output = tool_outputs[idx]['tool_output']
            user_msg['content'] += f"\n\n[Tool Output]:\n{tool_output}"
        conversation.append(user_msg)
        
        # Assistant message (if exists)
        if idx < len(assistant_messages):
            assistant_msg = assistant_messages[idx]
            conversation.append(assistant_msg)
    """
    # Combine system prompt and conversation
    messages.extend(conversation)
    
    total_tokens = num_tokens_from_messages(messages, model_name)
    
    # Remove messages from the front (after system prompt) until total_tokens <= max_tokens
    while total_tokens > max_tokens and len(messages) > 1:  # Always keep at least the system prompt
        messages.pop(1)  # Remove the message right after the system prompt
        total_tokens = num_tokens_from_messages(messages, model_name)
    
    return messages


def check_if_for_tool(prompt, conversation):
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.0,
          messages=[
            {"role": "system", "content": """You are a helpful assistant that determines if the user question is related to the previous question in the conversation.
             Answer question based on the meaning of the context provided in the user's question:
             - If the latest question is related return: 1
             - If it is not return: 0
             """},
            {"role": "user", "content": f"Previous conversation: {conversation}, \n\n Current question: {prompt}"},
        ]
    )

    return response.choices[0].message.content.strip()

def reset_memory():
    st.session_state.messages[st.session_state.thread_id] = [{'role': 'system', 'content': mprompts["sys_ragbot"]}]
    st.session_state.filtered_messages = ""

def main():
    if 'tool_outputs' not in st.session_state:
        st.session_state.tool_outputs = []

    current_thread_id = st.session_state.thread_id
    
    if "thread_id" not in st.session_state:
        def get_thread_ids():
            with ConversationDatabase() as db:
                return db.list_threads(st.session_state.app_name, st.session_state.username)
        new_thread_id = str(uuid.uuid4())
        thread_name = f"Thread_{new_thread_id}"
        conversation_data = [{'role': 'system', 'content': mprompts["sys_ragbot"]}]
        if thread_name not in get_thread_ids():
            with ConversationDatabase() as db:
                db.add_sql_record(st.session_state.app_name, st.session_state.username, thread_name, conversation_data)
        st.session_state.thread_id = thread_name
        st.session_state.messages[thread_name] = []
    try:
        if "Thread_" in st.session_state.thread_id:
            contains_system_role = any(message.get('role') == 'system' for message in st.session_state.messages[thread_name])
            if not contains_system_role:
                st.session_state.messages[thread_name].append({'role': 'system', 'content': mprompts["sys_ragbot"]})
    except:
        pass
    
    if st.session_state.thread_id is None:
        st.info("Start a conversation by selecting a new or existing conversation.")
    else:
        current_thread_id = st.session_state.thread_id

        with ConversationDatabase() as db:
            db.update_or_insert_sql_record(
                st.session_state.app_name,
                st.session_state.username,
                current_thread_id,
                st.session_state.messages[current_thread_id]
            )

        try:
            if "Thread_" in st.session_state.thread_id:
                contains_system_role = any(message.get('role') == 'system' for message in st.session_state.messages[thread_name])
                if not contains_system_role:
                    st.session_state.messages[thread_name].append({'role': 'system', 'content': mprompts["sys_ragbot"]})
        except:
            pass
       
        # Check if there's an existing conversation in the session state
        if current_thread_id not in st.session_state.messages:
            # If not, initialize it with the conversation from the database or as an empty list
            with ConversationDatabase() as db:
                st.session_state.messages[current_thread_id] = db.query_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id) or []
        if current_thread_id in st.session_state.messages:
            # avatari primena
            if current_thread_id in st.session_state.messages:
                for message in st.session_state.messages[current_thread_id]:
                    if message["role"] == "assistant": 
                        with st.chat_message("assistant", avatar=avatar_ai):
                            st.markdown(message["content"])
                    elif message["role"] == "user":         
                        with st.chat_message("user", avatar=avatar_user):
                            st.markdown(message["content"])
                    elif message["role"] == "system":
                        pass  # Do not display system messages  
    # Opcije
    col1, col2, col3 = st.columns(3)
    with col1:
    # Use the fixed container and apply the horizontal layout
        with st_fixed_container(mode="fixed", position="bottom", border=False, margin='10px'):
            with st.popover("Više opcija", help = "Snimanje pitanja, Slušanje odgovora, Priloži sliku"):
                # prica
                audio = mic_recorder(
                    key='my_recorder',
                    callback=callback,
                    start_prompt="🎤 Počni snimanje pitanja",
                    stop_prompt="⏹ Završi snimanje i pošalji ",
                    just_once=False,
                    use_container_width=False,
                    format="webm",
                )
                #predlozi
                st.session_state.toggle_state = st.toggle('✎ Predlozi pitanja/odgovora', key='toggle_button_predlog', help = "Predlažze sledeće pitanje")
                # govor
                st.session_state.button_clicks = st.toggle('🔈 Slušaj odgovor', key='toggle_button', help = "Glasovni odgovor asistenta")
                # slika
                st.session_state.image_ai, st.session_state.vrsta = file_reader.read_files()

    # main conversation prompt            
    st.session_state.prompt = st.chat_input("Kako vam mogu pomoći?")

    if st.session_state.selected_question != None:
        st.session_state.prompt = st.session_state['selected_question']
        st.session_state['selected_question'] = None
        
    if st.session_state.prompt is None:
        # snimljeno pitanje
        if audio is not None:
            id = audio['id']
            if id > st.session_state._last_speech_to_text_transcript_id:
                st.session_state._last_speech_to_text_transcript_id = id
                audio_bio = io.BytesIO(audio['bytes'])
                audio_bio.name = 'audio.webm'
                st.session_state.success = False
                err = 0
                while not st.session_state.success and err < 3:
                    try:
                        transcript = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_bio,
                            language="sr"
                        )
                    except Exception as e:
                        st.error(f"Neočekivana Greška : {str(e)} pokušajte malo kasnije.")
                        err += 1
                        
                    else:
                        st.session_state.success = True
                        st.session_state.prompt = transcript.text

    # Main conversation answer
    if st.session_state.prompt:
        jj = [msg for msg in st.session_state.messages[current_thread_id] if msg.get("role") not in ["tool", "system"]][:-1]
        print(f"\n\n\nJJ: {jj}")
        if len(jj) < 2:
            hh = 1
        else:
            hh = check_if_for_tool(st.session_state.prompt, jj)
        hh = 1
        if hh in ["0", 0]:
            result, tool = hh, "NoTool"
        else:
            result, tool = rag_tool_answer(st.session_state.prompt)
        print(f"\n\n\nHH: {hh}")
        # After getting the tool output
        st.session_state.tool_outputs.append({
            'user_message': st.session_state.prompt,
            'tool_output': result
        })

        st.session_state.tool_answer = result
        with st.expander("Expand"):
            st.write("Alat koji je koriscen: ", tool)
            st.divider()
            st.write("Odgovor iz alata: \n", result)
            st.divider()
            st.write("Istorija konverzacije: \n", st.session_state.messages[current_thread_id])
        
        if result=="CALENDLY":
            full_prompt=""
            full_response=""
            temp_full_prompt = {"role": "user", "content": [{"type": "text", "text": st.session_state.prompt}]}

        elif st.session_state.image_ai:
            if st.session_state.vrsta:
                full_prompt = st.session_state.prompt + st.session_state.image_ai
                temp_full_prompt = {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
            
                    ]
                }
                st.session_state.messages[current_thread_id].append(
                    {"role": "user", "content": st.session_state.prompt}
                )
                with st.chat_message("user", avatar=avatar_user):
                    st.markdown(st.session_state.prompt)
        else:
            if result == hh:
                temp_full_prompt = {"role": "user", "content": [{"type": "text", "text": st.session_state.prompt}]}
            else:
                temp_full_prompt = {"role": "user", "content": [{"type": "text", "text": f"""
                    Answer the following question from the user:
                    {st.session_state.prompt}{st.session_state.prompt}
                    Using the following context, which comes directly from our database:
                    {result}
                    All the provided context is relevant and trustworthy, so make sure to base your answer strictly on the information above.
                    Always write in Serbian.
                    """}]}
                    #If you cannot find the relevant information within the context, clearly state that the information is not currently available, but do not invent or guess.
            # print(f"temp_full_prompt: {temp_full_prompt}")
    
            # Append only the user's original prompt to the actual conversation log
            st.session_state.messages[current_thread_id].append({"role": "user", "content": st.session_state.prompt})

            # Display user prompt in the chat
            with st.chat_message("user", avatar=avatar_user):
                st.markdown(st.session_state.prompt)

        
        # mislim da sve ovo ide samo ako nije kalendly
        if result!="CALENDLY":    
        # Generate and display the assistant's response using the temporary messages list
            with st.chat_message("tool", avatar=avatar_ai):
                st.markdown(str(tool))

            with st.chat_message("assistant", avatar=avatar_ai):
                # cc_messages = [msg for msg in st.session_state.messages[current_thread_id] if msg.get("role") != "tool"][:-1] + [temp_full_prompt]
                cc_messages = [msg for msg in st.session_state.messages[current_thread_id] if msg.get("role") not in ["tool", "system"]][:-1]
                cc_messages.append(temp_full_prompt)
                # cc_messages = build_messages_for_api(current_thread_id)
                print(f"\n\n\ncc_messages: {cc_messages}")
                message_placeholder = st.empty()
                full_response = ""
                for response in client.chat.completions.create(
                    model=getenv("OPENAI_MODEL"),
                    temperature=0.0,
                    messages=cc_messages,
                    stream=True,
                    stream_options={"include_usage":True},
                    ):
                    try:
                        full_response += (response.choices[0].delta.content or "")
                        message_placeholder.markdown(full_response + "▌")
                    except Exception as e:
                            pass
            

            message_placeholder.markdown(full_response)
            copy_to_clipboard(full_response)
            # Append assistant's response to the conversation
            st.session_state.messages[current_thread_id].append({"role": "tool", "content": str(tool)})
            st.session_state.messages[current_thread_id].append({"role": "assistant", "content": full_response})
            st.session_state.filtered_messages = ""
            # da pise i tool
            filtered_data = [entry for entry in st.session_state.messages[current_thread_id] if entry['role'] in ["user", "assistant", "tool"]]
            for item in filtered_data:  # lista za download conversation
                st.session_state.filtered_messages += (f"{item['role']}: {item['content']}\n")  
    
            # Save the previous question and given answer for feedback purposes
            st.session_state.previous_question = st.session_state.prompt
            st.session_state.given_answer = full_response

            # Display thumbs feedback after the assistant's response
            with st.form('form'):
                streamlit_feedback(feedback_type="thumbs",
                                    optional_text_label="[Optional] Please provide an explanation", 
                                    align="flex-start", 
                                    key='fb_k')
                st.form_submit_button('Save feedback', on_click=handle_feedback)

            # ako su oba async, ako ne onda redovno
            if st.session_state.button_clicks and st.session_state.toggle_state:
                process_request(client, temp_full_prompt, full_response, getenv("OPENAI_API_KEY"))
            else:
                if st.session_state.button_clicks: # ako treba samo da cita odgovore
                    play_audio_from_stream_s(full_response)
        
                if st.session_state.toggle_state:  # ako treba samo da prikaze podpitanja
                    predlozeni_odgovori(temp_full_prompt)
    
            if st.session_state.vrsta:
                st.info(f"Dokument je učitan ({st.session_state.vrsta}) - uklonite ga iz uploadera kada ne želite više da pričate o njegovom sadržaju.")


    with col2:
        with st_fixed_container(mode="fixed", position="bottom", border=False, margin='10px'):          
            st.download_button(
                "⤓ Preuzmi", 
                st.session_state.filtered_messages, 
                file_name="istorija.txt", 
                help = "Čuvanje istorije ovog razgovora"
                )
    with col3:
        with st_fixed_container(mode="fixed", position="bottom", border=False, margin='10px'):          
            st.button("🗑 Obriši", on_click=reset_memory)


def main_wrap_for_st():
    check_openai_errors(main)
 
if __name__ == "__main__":
    main()
