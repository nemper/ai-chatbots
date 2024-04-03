import json
import nltk     # kasnije ce se paketi importovati u funkcijama
import openai
import os
import streamlit as st

from openai import AssistantEventHandler
from st_copy_to_clipboard import st_copy_to_clipboard
from streamlit_extras.stylable_container import stylable_container
from time import sleep
from typing_extensions import override

from myfunc.prompts import SQLSearchTool
from myfunc.retrievers import HybridQueryProcessor
from myfunc.various_tools import web_search_process
 
# First, we create a EventHandler class to define
# how we want to handle the events in the response stream.
def display_tool_output(output):
    # Example function to update Streamlit UI with tool output
    # Adjust based on how you intend to display or use the output
    st.write(output)
    
class EventHandler(AssistantEventHandler):    
  @override
  def on_text_created(self, text) -> None:
    print(f"\nassistant > ", end="", flush=True)
      
  @override
  def on_text_delta(self, delta, snapshot):
    print(delta.value, end="", flush=True)
      
  def on_tool_call_created(self, tool_call):
    print(f"\nassistant > {tool_call.type}\n", flush=True)
  
    def on_tool_call_delta(self, delta, snapshot):
        # Handle tool call responses here
        # Assuming 'delta' contains 'tool_call' with necessary details about the tool call completion
        # The precise structure of 'delta' would depend on the OpenAI API documentation
        
        # Check if the delta is for a tool call completion with outputs
        if delta.type == 'tool_call_completed' and delta.tool_call.outputs:
            for output in delta.tool_call.outputs:
                tool_name = output.tool_call.function.name  # Adjust based on actual structure
                arguments = json.loads(output.tool_call.function.arguments)  # Adjust based on actual structure
                
                # Handle the output based on the tool's name
                if tool_name == "web_search_process":
                    # Assuming 'arguments' contains the necessary input for the tool
                    try:
                        query = arguments["query"]
                    except KeyError:
                        query = arguments["q"]
                    result = web_search_process(query)
                    display_tool_output(result)  # Update the UI with the result

                elif tool_name == "hybrid_search_process":
                    upit = arguments["upit"]
                    result = hybrid_search_process(upit)
                    display_tool_output(result)  # Update the UI with the result

                elif tool_name == "sql_search_tool":
                    upit = arguments["upit"]
                    result = sql_search_tool(upit)
                    display_tool_output(result)  # Update the UI with the result



# st.set_page_config(page_title="Positive Chatbot", page_icon="🤖")

version = "v1.0.1 asistenti lib"

os.getenv("OPENAI_API_KEY")
assistant_id = "asst_1YAl3U9XJTOnfYUJrStFO1nH"
# assistant_id = os.getenv("ASSISTANT_ID")

client = openai.OpenAI()
# printuje se u drugoj skripti, a moze jelte da se vidi i na OpenAI Playground-u
client.beta.assistants.retrieve(assistant_id=assistant_id)

# ovde se navode svi alati koji ce se koristiti u chatbotu
# funkcije za obradu upita prebacene su iz myfunc zato da bi se lakse dodavali opcioni parametri u funkcije
def hybrid_search_process(upit: str) -> str:
        processor = HybridQueryProcessor()
        stringic = processor.process_query_results(upit)
        return stringic
    
def sql_search_tool(upit: str) -> str:
    processor = SQLSearchTool()
    stringic = processor.search(upit)
    return stringic


def main(): 
    # Inicijalizacija session state-a
    default_session_states = {
        "file_id_list": [],
        "openai_model": "gpt-4-turbo-preview",
        "messages": [],
        "thread_id": None,
        "is_deleted": False,
        "cancel_run": None,
        }
    
    for key, value in default_session_states.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if st.session_state.thread_id is None:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id

    
    assistant = client.beta.assistants.retrieve(assistant_id=assistant_id)
    if st.session_state.thread_id:
        thread = client.beta.threads.retrieve(thread_id=st.session_state.thread_id)

    # ako se desi error run ce po default-u trajati 10 min pre no sto se prekine -- ovo je da ne moramo da cekamo
    try:
        run = client.beta.threads.runs.cancel(thread_id=st.session_state.thread_id, run_id=st.session_state.cancel_run)
    except:
        pass
    run = None
    

    # pitalica
    if prompt := st.chat_input(placeholder=f"Postavite pitanje                                ({version})"):
        if st.session_state.thread_id is not None:
            #client.beta.threads.messages.create(thread_id=st.session_state.thread_id, role="user", content=prompt) 
            res_box = st.empty()
            report = []
            stream = client.beta.threads.create_and_run(
                assistant_id=assistant.id,
                thread=thread.id,
                tools=tools,
                #{"messages": [{"role": "user", "content": prompt}]},
                stream=True)
            for event in stream:
                if event.data.object == "thread.message.delta":
                    for content in event.data.delta.content:
                        if content.type == "text":
                            report.append(content.text.value)
                            result = "".join(report).strip()
                            res_box.markdown(f"*{result}*")

    _ = """
    if prompt := st.chat_input(placeholder=f"Postavite pitanje                                ({version})"):
        if st.session_state.thread_id is not None:
            client.beta.threads.messages.create(thread_id=st.session_state.thread_id, role="user", content=prompt) 

            # run = client.beta.threads.runs.create_and_stream(thread_id=st.session_state.thread_id, assistant_id=assistant.id)
            with client.beta.threads.runs.create_and_stream(
                thread_id=thread.id,
                assistant_id=assistant.id,
                instructions="You are a helpful assistant",
                event_handler=EventHandler(),
                ) as stream:
                stream.until_done()

        else:
            st.warning("Molimo Vas da izaberete postojeci ili da kreirate novi chat.")
    """

    # fixirana poruka za spinner
    with stylable_container(
                    key="bottom_content",
                    css_styles="""
                        {
                            position: fixed;
                            bottom: 150px;
                        }
                        """,
                    ):
        # obrada upita        
        with st.spinner("🤖 Chatbot razmislja..."):
            if run is not None:
                while True:
                
                    sleep(0.3)
                    run_status = client.beta.threads.runs.retrieve(thread_id=st.session_state.thread_id, run_id=run.id)

                    if run_status.status == 'completed':
                        break
                    # ako se poziva neka funkcija
                    elif run_status.status == 'requires_action':
                        tools_outputs = []

                        for tool_call in run_status.required_action.submit_tool_outputs.tool_calls:
                            if tool_call.function.name == "web_search_process":
                                arguments = json.loads(tool_call.function.arguments)
                                try:
                                    output = web_search_process(arguments["query"])
                                except:
                                    output = web_search_process(arguments["q"])

                                tool_output = {"tool_call_id":tool_call.id, "output": json.dumps(output)}
                                tools_outputs.append(tool_output)
                           
                            elif tool_call.function.name == "hybrid_search_process":
                                arguments = json.loads(tool_call.function.arguments)
                                output = hybrid_search_process(arguments["upit"])
                                tool_output = {"tool_call_id":tool_call.id, "output": json.dumps(output)}
                                tools_outputs.append(tool_output)
                            elif tool_call.function.name == "sql_search_tool":
                                arguments = json.loads(tool_call.function.arguments)
                                output = sql_search_tool(arguments["upit"])
                                tool_output = {"tool_call_id":tool_call.id, "output": json.dumps(output)}
                                tools_outputs.append(tool_output)
                                
                        if run_status.required_action.type == 'submit_tool_outputs':
                            client.beta.threads.runs.submit_tool_outputs(thread_id=st.session_state.thread_id, run_id=run.id, tool_outputs=tools_outputs)

                        sleep(0.3)
    try:
        # kreiranje ispisa pitanja/odgovora     
        messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id) 
        for msg in reversed(messages.data): 
            role = msg.role
            content = msg.content[0].text.value 
            messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id) 
            
            if role == 'user':
                st.markdown(f"<div style='background-color:lightblue; padding:10px; margin:5px; border-radius:5px;'><span style='color:blue'>👤 {role.capitalize()}:</span> {content}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background-color:lightgray; padding:10px; margin:5px; border-radius:5px;'><span style='color:red'>🤖 {role.capitalize()}:</span> {content}</div>", unsafe_allow_html=True)
                # copy to clipboard dugme (za svaki odgovor)
                st_copy_to_clipboard(content)
        
    except:
        pass
    
    
if __name__ == "__main__":
    main()
