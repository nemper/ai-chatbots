from openai import OpenAI
import streamlit as st
import os
import glob
import re
import io
import ast

from langchain_openai import ChatOpenAI
from langchain_community.graphs.networkx_graph import NetworkxEntityGraph
from langchain.chains import GraphQAChain

from myfunc.mojafunkcija import show_logo
from myfunc.embeddings import rag_tool_answer, MultiQueryDocumentRetriever, CohereReranker, PineconeRetriever, ContextRetriever, LongContextHandler
from myfunc.prompts import PromptDatabase, SQLSearchTool
from myfunc.retrievers import HybridQueryProcessor, SelfQueryPositive
from myfunc.various_tools import hyde_rag
from myfunc.varvars_dicts import work_vars

try:
    x = st.session_state.sys_ragbot
except:
    with PromptDatabase() as db:
        prompt_map = db.get_prompts_by_names(["rag_self_query", "sys_ragbot"],[os.getenv("RAG_SELF_QUERY"), os.getenv("SYS_RAGBOT")])
        st.session_state.rag_self_query = prompt_map.get("rag_self_query", "You are helpful assistant that always writes in Serbian.")
        st.session_state.sys_ragbot = "You are helpful assistant that always writes in Serbian."

    
# os.environ["LANGCHAIN_TRACING_V2"] = "true"
# os.environ["LANGCHAIN_PROJECT"] = f"RAG Test Bot"
# os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
# os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
with st.sidebar:
    global phglob
    phglob=st.empty()

st.title("RAG Test Bot")

with st.expander("Uputstvo"):
    st.caption("""
    ### Upotreba razlicitih retrievera i prompt augmentation
               
    1. Hybrid search sa podesavanjem aplha i score
    2. SelfQuery with metadata
    3. SQL search
    4. Parent retriever trazi opsirniji doc           
    5. Parent retriever expanduje retrieved data uzimajuci prethodne i naredne chunkove istog doc
    6. Graph pretrazuje Knowledge Graph           
    7. Hyde kreira hipoteticke odgovore za poboljsanje prompta          
    8. Multiquery search kreira dodatne promptove
    9. Decompositivio rasclanjuje propmt na logicne celine i dobij aodgovor za svaku.           
    10. Cohere Reranking reranks documents using Cohere API
    11. Long Context reorder reorders chunks by putting the most relevant in the beginning and end.
    12. Contextual Compression compresses chunks to relevant parts
    13. Calendly zakazuje sastanak
    14. Bez alata - cist LLM
               """)
if "rag_tool" not in st.session_state:
    st.session_state.rag_tool = " " 
if "graph_file" not in st.session_state:
    st.session_state.graph_file = " " 
if "alpha" not in st.session_state:
    st.session_state.alpha = 0.5 
if "score" not in st.session_state:
    st.session_state.score = 0.0
if "byte_data" not in st.session_state:
    st.session_state.byte_data = ""

def positive_calendly(phglob):
    with st.sidebar:
        with phglob.container():
            calendly_url = "https://calendly.com/djordje-thai/30min/?embed=true"
            iframe_html = f'<iframe src="{calendly_url}" width="320" height="820"></iframe>'
            st.components.v1.html(iframe_html, height=820)
            
    return "Do not answer to this question, just say Hvala"
    
def rag_tool_answer(prompt):
    context = " "
  
    if  st.session_state.rag_tool == "Hybrid":
        processor = HybridQueryProcessor(alpha=st.session_state.alpha, score=st.session_state.score, namespace="laguna")
        context, scores, tokens = processor.process_query_results(prompt)
        st.info("Score po chunku:")
        st.write(scores)
        
    # SelfQuery Tool Configuration
    elif  st.session_state.rag_tool == "SelfQuery":
        # Example configuration for SelfQuery
        prompt = st.session_state.rag_self_query + prompt
        context = SelfQueryPositive(prompt, namespace="selfdemo", index_name="neo-positive")
        
    # SQL Tool Configuration
    elif st.session_state.rag_tool == "SQL":
            processor = SQLSearchTool()
            context = processor.search(prompt)

    # Parent Doc Tool Configuration
    elif  st.session_state.rag_tool == "Parent Doc":
        # Define stores
        h_retriever = HybridQueryProcessor(namespace="pos-50", top_k=1)
        h_docstore = HybridQueryProcessor(namespace="pos-2650")

        # Perform a basic search hybrid
        basic_search_result, source_result, chunk = h_retriever.process_query_parent_results(prompt)
        # Perform a search filtered by source (from basic search)
        search_by_source_result = h_docstore.search_by_source(prompt, source_result)
        st.write(f"Osnovni rezultat koji sluzi da nadje prvi: {basic_search_result}")
        st.write(f"Krajnji rezultat koji se vraca: {search_by_source_result}")
        return search_by_source_result

    # Parent Chunks Tool Configuration
    elif  st.session_state.rag_tool == "Parent Chunks":
        # Define stores
        h_retriever = HybridQueryProcessor(namespace="zapisnici", top_k=1)
        # Perform a basic search hybrid
        basic_search_result, source_result, chunk = h_retriever.process_query_parent_results(prompt)
        # Perform a search filtered by source and a specific chunk range (both from basic search)
        search_by_chunk_result = h_retriever.search_by_chunk(prompt, source_result, chunk)
        st.write(f"Osnovni rezultat koji sluzi da nadje prvi: {basic_search_result}")
        st.write(f"Krajnji rezultat koji se vraca: {search_by_chunk_result}")
        return search_by_chunk_result

    # Graph Tool Configuration
    elif  st.session_state.rag_tool == "Graph":
                
        # Read the graph from the file-like object
        graph = NetworkxEntityGraph.from_gml(st.session_state.graph_file)
        chain = GraphQAChain.from_llm(ChatOpenAI(model=work_vars["names"]["openai_model"], temperature=0), graph=graph, verbose=True)
        rezultat= chain.invoke(prompt)
        context = rezultat['result']

    # Hyde Tool Configuration
    elif  st.session_state.rag_tool == "Hyde":
        # Assuming a processor for Hyde exists
        context = hyde_rag(prompt)

    # MultiQuery Tool Configuration
    elif  st.session_state.rag_tool == "MultiQuery":
        # Initialize the MQDR instance
        retriever_instance = MultiQueryDocumentRetriever(question=prompt, namespace="positive", tip="multi")
        # To get documents relevant to the original question
        context = retriever_instance.get_relevant_documents(prompt)
        output=retriever_instance.log_messages
        generated_queries = output[0].split(": ")[1]
        queries = ast.literal_eval(generated_queries)
        st.info(f"Dodatna pitanja - MultiQuery Alat:")
        for query in queries:
            st.caption(query)
    elif  st.session_state.rag_tool == "Decomposition":
        # Initialize the MQDR instance
        retriever_instance = MultiQueryDocumentRetriever(question=prompt, namespace="positive", tip="sub")
        # To get documents relevant to the original question
        context = retriever_instance.get_relevant_documents(prompt)
        output=retriever_instance.log_messages
        generated_queries = output[0].split(": ")[1]
        queries = ast.literal_eval(generated_queries)
        st.info(f"Razlozena pitanja - Decomposition Alat:")
        for query in queries:
            st.caption(query)
        

    # RAG Fusion Tool Configuration
    elif  st.session_state.rag_tool == "Cohere Reranking":
        # Retrieve documents using Pinecone
        pinecone_retriever = PineconeRetriever(prompt)
        docs = pinecone_retriever.get_relevant_documents()
        documents = [doc.page_content for doc in docs]
        # Rerank documents using Cohere
    
        cohere_reranker = CohereReranker(prompt)
        context = cohere_reranker.rerank(documents)
        
    elif  st.session_state.rag_tool == "Contextual Compression":
        # Retrieve documents using Pinecone
        pinecone_retriever = PineconeRetriever(prompt)
        docs = pinecone_retriever.get_relevant_documents()
        documents = [doc.page_content for doc in docs]
       
        # Retrieve and compressed context
        context_retriever = ContextRetriever(prompt)
        context = context_retriever.get_compressed_context()
        
    elif  st.session_state.rag_tool == "Long Context":
         # Retrieve documents using Pinecone
        pinecone_retriever = PineconeRetriever(prompt)
        docs = pinecone_retriever.get_relevant_documents()
        documents = [doc.page_content for doc in docs]
        
        # Reorder documents for long context handling
        long_context_handler = LongContextHandler()
        context = long_context_handler.reorder(documents)
        
    elif  st.session_state.rag_tool == "Calendly":
        # Scledule Calendly meeting
        context = positive_calendly(phglob)
        
    # Fallback for undefined tool
    else:
        st.write("Nedefinisani RAG alat. Nastavljam bez RAG-a.")
        
   
    return context       

def find_next_thread_id():
    existing_threads = list_saved_threads()
    max_id = 0
    for thread in existing_threads:
        match = re.search(r'thread_(\d+).txt', thread)
        if match:
            thread_id = int(match.group(1))
            if thread_id > max_id:
                max_id = thread_id
    return max_id + 1

def list_saved_threads():
    # List all files that match the pattern 'thread_*.txt'
    return glob.glob('thread_*.txt')

def load_thread_from_file(filename):
    messages = []
    
    with open(filename, 'r') as file:
        for line in file:
            # Assuming each line is in the format 'Role: Message'
            if ": " in line:
                role, content = line.split(": ", 1)
                messages.append({"role": role.lower(), "content": content.strip()})
                
    return messages

# Function to save messages to a .txt file
def save_messages_to_file(thread_id, messages):
    # Define the filename based on the thread ID
    filename = f"thread_{thread_id}.txt"

    # Open the file in write mode
    with open(filename, 'w') as file:
        for message in messages:
            # Format each message
            formatted_message = f"{message['role'].title()}: {message['content']}\n"
            file.write(formatted_message)
    
    return filename

# app body
# Initialize session state for messages and thread ID

if "messages" not in st.session_state:
    st.session_state.messages = {}
# Set the default thread ID to a new thread when the app starts
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = find_next_thread_id()

# Initialize the message list for the current thread if not already present
current_thread_id = st.session_state["thread_id"]
if current_thread_id not in st.session_state.messages:
    st.session_state.messages[current_thread_id] = []
    st.session_state.messages[current_thread_id].append({"role": "system", "content": st.session_state.sys_ragbot})



client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = work_vars["names"]["openai_model"]

# Initialize session state for messages and thread ID
if "messages" not in st.session_state:
    st.session_state.messages = {}
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = 1

# Initialize the message list for the current thread if not already present
current_thread_id = st.session_state["thread_id"]
if current_thread_id not in st.session_state.messages:
    st.session_state.messages[current_thread_id] = []

# Display the existing messages in the current thread
for message in st.session_state.messages.get(current_thread_id, []):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle new user input
if prompt := st.chat_input("Sta biste zeleli da znate?"):
    
    # upotrebljava alat, vraca context
    context = rag_tool_answer(prompt)

    complete_prompt = f""" 
    Based on the context: 
    {context} 
    answer this question: 
    {prompt}
    """
    st.session_state.messages[current_thread_id].append({"role": "user", "content": complete_prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        st.info(f"Alat u upotrebi: {st.session_state.rag_tool}")
        st.caption(f"Prompt sa rezultatom alata: {complete_prompt}")
        
        
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        for response in client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=st.session_state.messages[current_thread_id],
            stream=True,
        ):
            full_response += (response.choices[0].delta.content or "")
            message_placeholder.markdown(full_response + "▌")
        message_placeholder.markdown(full_response)
    st.session_state.messages[current_thread_id].append({"role": "assistant", "content": full_response})



with st.sidebar:
    show_logo()
    st.caption("02.05.24")
    
    if st.button('Start New Conversation'):
        # Find the next available thread ID
        new_thread_id = find_next_thread_id()
        st.session_state["thread_id"] = new_thread_id
        st.session_state.messages[new_thread_id] = []
        st.session_state.messages[current_thread_id].append({"role": "system", "content": st.session_state.sys_ragbot})
        st.success(f'New conversation started with Thread ID: {new_thread_id}')
        

    # Dropdown to select a saved thread
    saved_threads = list_saved_threads()
    selected_thread_file = st.selectbox('Select a thread to load', [''] + saved_threads)

    # Load the selected thread
    if selected_thread_file:
        loaded_messages = load_thread_from_file(selected_thread_file)
        # Extract thread ID from the filename
        thread_id = int(selected_thread_file.split('_')[1].split('.')[0])
        st.session_state["thread_id"] = thread_id
        st.session_state.messages[thread_id] = loaded_messages

        st.success(f'Loaded conversation from {selected_thread_file}')

    # ... rest of the code to handle new messages and save the conversation ...
    # Add a button to save the conversation
    if st.button('Save Conversation'):
        messages = st.session_state.messages.get(current_thread_id, [])
        if messages:
            filename = save_messages_to_file(current_thread_id, messages)
            st.success(f'Conversation saved to {filename}')
        else:
            st.error('No messages to save.')
    
    # Dropdown to select RAG tool
    st.session_state.rag_tool = st.selectbox(
        "Odaberite RAG alat", 
        ["Bez alata", "Hybrid", "SelfQuery", "SQL", "Parent Doc", "Parent Chunks", "Graph", "Hyde", "MultiQuery", "Decomposition", "Cohere Reranking", "Contextual Compression", "Long Context", "Calendly"]
    )
    if st.session_state.rag_tool == "Graph":
        uploaded_file = st.file_uploader("Ucitajte Graph file", key="upl_graph", type="gml")
        if uploaded_file:
            st.session_state.graph_file = uploaded_file.name
            with io.open(st.session_state.graph_file, "wb") as file:
                file.write(uploaded_file.getbuffer())
           
            
            
        else:
            st.error("Ucitajte Graph file")
    if st.session_state.rag_tool == "Hybrid":
        st.session_state.alpha = st.slider("Odaberite odnos KW/Semantic (0-KW): ", 0.0, 1.0, 0.5, 0.1)
        st.session_state.score = st.slider("Odaberite minimalan score slicnosti: ", 0.0, 1.0, 0.0, 0.1)
    
    if st.session_state.rag_tool == "Hyde":
        st.info("Alat jos nije implementran")
