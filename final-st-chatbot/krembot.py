import io
import streamlit as st
import uuid

#_ = """
import os
os.environ["CLIENT_FOLDER"] = "Denty"
os.environ["SYS_RAGBOT"] = "DENTY_REPAIRER"
os.environ["APP_ID"] = "DentyBot"
os.environ["CHOOSE_RAG"] = "GENERAL_CHOOSE_RAG"
os.environ["OPENAI_MODEL"] = "gpt-4o-2024-08-06"
os.environ["PINECONE_HOST"] = "https://neo-positive-a9w1e6k.svc.apw5-4e34-81fa.pinecone.io"
#"""

_ = """
import os
os.environ["CLIENT_FOLDER"] = "Delfi"
os.environ["SYS_RAGBOT"] = "DELFI_SYS_RAGBOT"
os.environ["APP_ID"] = "DelfiBot"
os.environ["CHOOSE_RAG"] = "DELFI_CHOOSE_RAG"
os.environ["OPENAI_MODEL"] = "gpt-4o-2024-08-06"
os.environ["PINECONE_HOST"] = "https://delfi-a9w1e6k.svc.aped-4627-b74a.pinecone.io"
"""

_ = """
import os
os.environ["CLIENT_FOLDER"] = "ECD"
os.environ["SYS_RAGBOT"] = "ECD_SYS_RAGBOT"
os.environ["APP_ID"] = "ECDBot"
os.environ["CHOOSE_RAG"] = "ECD_CHOOSE_RAG"
os.environ["OPENAI_MODEL"] = "gpt-4o-2024-08-06"
os.environ["PINECONE_HOST"] = "https://neo-positive-a9w1e6k.svc.apw5-4e34-81fa.pinecone.io"
"""
from openai import OpenAI
from os import getenv
from streamlit_mic_recorder import mic_recorder

from krembot_tools import rag_tool_answer
from krembot_db import ConversationDatabase, work_prompts
from krembot_stui import *
from krembot_funcs import *

from streamlit_feedback import streamlit_feedback

mprompts = work_prompts()

with st.expander("Promptovi"):
    st.write(mprompts)

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


CATEGORY_DEVICE_MAPPING = {
    "CAD/CAM Systems": [
        "CEREC AC",
        "CEREC AF",
        "CEREC AI",
        "CEREC MC",
        "CEREC MC XL",
        "CEREC NETWORK",
        "CEREC OMNICAM",
        "CEREC PRIMEMILL",
        "CEREC PRIMESCAN",
        "CEREC SPEEDFIRE",
        "CEREC PRIMEPRINT",
        "CEREC PRIMESCAN",
        "CEREC OMNICAM",
        "CEREC SPEEDFIRE",
        "PRIMEPRINT",
        "PRIMEPRINT PPU",
        "INEOS BLUE",
        "INLAB MC",
        "INLAB PC",
        "INLAB PROFIRE",
        "INFIRE HTC",
        "CEREC PRIMEPRINT",
        "PRIMESCAN",
        "PRIMESCAN AC"
    ],
    "Imaging Systems": [
        "GALILEOS",
        "GALILEOS COMFORT",
        "GALILEOS GAX5",
        "GALILEOS X-RAY UNIT",
        "FACESCAN",
        "PERIOSCAN",
        "SIDEXIS 4",
        "SIDEXIS XG",
        "XIOS",
        "SIM INTEGO",
        "SIMULATION UNIT",
        "ORTHOPHOS XG",
        "ORTHOPHOS E",
        "ORTHOPHOS S",
        "ORTHOPHOS SL",
        "ORTHOPHOS XG",
        "XIOS"
    ],
    "Dental Units": [
        "HELIODENT",
        "HELIODENT DS",
        "HELIODENT PLUS",
        "HELIODENT VARIO",
        "C2",
        "C5",
        "C8",
        "CEREC MC",
        "CEREC MC XL",
        "INLAB MC",
        "INLAB MC X5",
        "INLAB MC XL",
        "INLAB PC",
        "INLAB PROFIRE",
        "SIROTORQUE L",
        "T1 CLASSIC",
        "T1 ENERGO",
        "T1 HIGHSPEED",
        "T1 LINE",
        "T1 TURBINE",
        "T2 ENERGO",
        "T2 HIGHSPEED",
        "T2 LINE",
        "T2 REVO",
        "T3 HIGHSPEED",
        "T3 LINE",
        "T3 RACER",
        "T3 TURBINE",
        "T4 LINE",
        "T4 RACER",
        "TURBINE",
        "TURBINES SIROBOOST",
        "TURBINES T1 CONTROL",
        "VARIO DG",
        "AXANO",
        "AXEOS",
        "C2",
        "C5",
        "C8",
        "M1",
        "MM2-SINTER",
        "HEAT-DUO",
        "MOTORCAST COMPACT",
        "MULTIMAT",
        "ORTHOPHOS E",
        "ORTHOPHOS S",
        "ORTHOPHOS SL",
        "ORTHOPHOS XG",
        "VARIO DG"
    ],
    "Lasers": [
        "FONALASER",
        "SIROLASER",
        "SIROLASER XTEND",
        "SIROENDO",
        "SIROCAM",
        "SIROLUX",
        "SIROPURE",
        "FONALASER"
    ],
    "Intraoral Scanners": [
        "INLAB MC",
        "INLAB MC X5",
        "INLAB MC XL",
        "PRIMESCAN AC",
        "SIM INTEGO",
        "INTEGO",
        "PRIMESCAN",
        "PRIMESCAN AC",
        "CEREC PRIMESCAN"
    ],
    "Dental Instruments and Tools": [
        "AE SENSOR",
        "APOLLO DI",
        "AXANO",
        "AXEOS",
        "CARL",
        "PAUL",
        "CEILING MODEL",
        "CERCON",
        "ENDO",
        "HEAT-DUO",
        "LEDLIGHT",
        "LEDVIEW",
        "M1",
        "MAILLEFER",
        "MIDWEST",
        "MM2-SINTER",
        "MOTORCAST COMPACT",
        "MULTIMAT",
        "PROFEEL",
        "PROFIRE",
        "SIMULATION UNIT",
        "SINIUS",
        "SIROCAM",
        "SIROENDO",
        "SIROLUX",
        "SIROPURE",
        "SIROTORQUE L",
        "SIUCOM",
        "SIVISION",
        "TEMPERATURE TABLE",
        "TENEO",
        "TULSA",
        "VARIO DG",
        "TURBINES SIROBOOST",
        "TURBINES T1 CONTROL"
    ],
    "Other Equipment/Accessories": [
        "INTRAORAL PRODUCTS",
        "DAC UNIVERSAL",
        "VARIO DG",
        "TENEO"
    ],
    "Hybrid or Multi-Category Devices": [
        "CEREC AC, CEREC OMNICAM",
        "CEREC AC, INEOS BLUE",
        "CEREC AC, INLAB MC",
        "CEREC AF, CEREC AI",
        "CEREC MC, CEREC AC, CEREC SPEEDFIRE, INLAB MC, CEREC PRIMEPRINT, CEREC PRIMESCAN, CEREC OMNICAM",
        "CEREC MC, CEREC PRIMEMILL, CEREC AC, CEREC OMNICAM, PRIMESCAN, INLAB MC, CEREC SPEEDFIRE, PRIMEPRINT",
        "CEREC MC, INLAB MC",
        "CEREC PRIMESCAN, CEREC OMNICAM",
        "ENDO, VDW, TULSA, MAILLEFER, MIDWEST",
        "HELIODENT, LEDVIEW",
        "SIROLASER, FONALASER",
        "SIROLUX, HELIODENT",
        "SIROLUX, LEDVIEW, HELIODENT",
        "T1 CLASSIC, T1 LINE, T2 LINE, T3 LINE, T4 LINE",
        "T1 ENERGO, T2 ENERGO",
        "T1 HIGHSPEED, T2 HIGHSPEED, T3 HIGHSPEED",
        "T1 LINE, T2 LINE, T3 LINE",
        "T1 TURBINE, T2, TURBINE, T3 TURBINE",
        "T3 RACER, T4 RACER",
        "TENEO, SINIUS, INTEGO",
        "ORTHOPHOS S, ORTHOPHOS SL",
        "ORTHOPHOS SL, ORTHOPHOS S",
        "ORTHOPHOS XG, GALILEOS",
        "ORTHOPHOS XG, GALILEOS, XIOS",
        "SIUCOM, SIVISION"
    ]
}


# Sidebar for selections
st.sidebar.header("Select Device Category and Device")

# Category selection
categories = list(CATEGORY_DEVICE_MAPPING.keys())
selected_category = st.sidebar.selectbox("Select a Category", categories)

# Device selection based on selected category
devices = CATEGORY_DEVICE_MAPPING[selected_category]
selected_device = st.sidebar.selectbox("Select a Device", devices)


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
        if getenv("APP_ID") == "DentyBot":
            x = selected_device
            if not x:
                st.error("Niste izabrali uređaj.")
            else:
                result, tool = rag_tool_answer(st.session_state.prompt, selected_device)
        else:
            result, tool = rag_tool_answer(st.session_state.prompt, 1)
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
            temp_full_prompt = {"role": "user", "content": [{"type": "text", "text": f"""
                Answer the following question from the user:
                {st.session_state.prompt}
                Using the following context, which comes directly from our database:
                {result}
                All the provided context is relevant and trustworthy, so make sure to base your answer strictly on the information above.
                Always provide corresponding links from established knowledge base and do NOT generate or suggest any links that do not exist within it. 
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
                cc_messages = [msg for msg in st.session_state.messages[current_thread_id] if msg.get("role") != "tool"][:-1]
                cc_messages.append(temp_full_prompt)
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
