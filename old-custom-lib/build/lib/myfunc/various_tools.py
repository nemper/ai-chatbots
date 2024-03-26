import streamlit as st
from openai import OpenAI
from tqdm.auto import tqdm
from langchain.text_splitter import RecursiveCharacterTextSplitter
import re
import html
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests
import openai
import sys
import datetime
from langchain.text_splitter import CharacterTextSplitter
import os
from myfunc.mojafunkcija import (
    pinecone_stats, st_style
    )
from myfunc.retrievers import (
    PineconeUtility, TextProcessing, HybridQueryProcessor, 
    SQLSearchTool, SelfQueryPositive
    )
from myfunc.various_tools import (
    MultiQueryDocumentRetriever, CohereReranker, 
    PineconeRetriever, ContextRetriever, LongContextHandler, 
    hyde_rag, get_structured_decision_from_model, web_search_process
    )
from langchain_community.retrievers import PineconeHybridSearchRetriever
from pinecone_text.sparse import BM25Encoder
from time import sleep
import json
from uuid import uuid4
from io import StringIO
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain_experimental.text_splitter import SemanticChunker

from langchain_openai import ChatOpenAI
from langchain.indexes.graph import NetworkxEntityGraph
from langchain.chains import GraphQAChain
import ast

st_style()
client=OpenAI()


# novi dugacki zapisnik
class MeetingTranscriptSummarizer:
    def __init__(self, transcript, temperature, number_of_topics):
        self.transcript = transcript
        self.temperature = temperature
        self.number_of_topics = number_of_topics

    def get_response(self, prompt, text):
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": prompt + "Use only the Serbian Language"},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content

    def summarize(self):
        introduction = self.get_response("Extract the meeting date and the participants.", self.transcript)
        topic_identification_prompt = (
            f"List up to {self.number_of_topics} main topics discussed in the transcript "
            "excluding the introductory details and explanation of the topics. "
            "All remaining topics summarize in the single topic Razno."
        )
        topics = self.get_response(topic_identification_prompt, self.transcript).split('\n')
        
        st.success("Identifikovane su teme:")
        for topic in topics:
            st.success(topic)

        summaries = []
        for topic in topics:
            summary_prompt = f"Summarize the discussion on the topic: {topic}, excluding the introductory details."
            summary = self.get_response(summary_prompt, self.transcript)
            summaries.append(f"## Tema: {topic} \n{summary}")
            st.info(f"Obradjujem temu: {topic}")
        
        conclusion = self.get_response("Generate a conclusion from the whole meeting.", self.transcript)
        full_text = (
            f"## Sastanak koordinacije AI Tima\n\n{introduction}\n\n"
            f"## Teme sastanka\n\n" + "\n".join([f"{topic}" for topic in topics]) + "\n\n"
            + "\n\n".join(summaries) 
            + f"\n\n## Zaključak\n\n{conclusion}"
        )
        return full_text
    

# analogno klasi iznad
def summarize_meeting_transcript(transcript, temp, broj_tema):
    """
    Summarize a meeting transcript by first extracting the date, participants, and topics,
    and then summarizing each topic individually while excluding the introductory information
    from the summaries.

    Parameters: 
        transcript (str): The transcript of the meeting.
    """

    def get_response(prompt, text, temp):
        """
        Generate a response from the model based on the given prompt and text.
        
        Parameters:
            prompt (str): The prompt to send to the model.
            text (str): The text to summarize or extract information from.
        """
        
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            temperature=temp,  
            messages=[
                {"role": "system", "content": prompt + "Use only the Serbian Language"},
                {"role": "user", "content": text}
            ]
        )
        
        return response.choices[0].message.content

    # Extract introductory details like date, participants, and a brief overview
    intro_prompt = "Extract the meeting date and the participants."
    introduction = get_response(intro_prompt, transcript, temp)

    # Identify the main topics in the transcript
    topic_identification_prompt = f"List up to {broj_tema} main topics discussed in the transcript excluding the introductory details and explanation of the topics. All remaining topics summarize in the single topic Razno."
    topics = get_response(topic_identification_prompt, transcript, temp).split('\n')
    
    st.success("Identifikovane su teme:")
    for topic in topics:
        st.success(topic)

    # Summarize each identified topic
    summaries = []
    for topic in topics:
        summary_prompt = f"Summarize the discussion on the topic: {topic}, excluding the introductory details."
        summary = get_response(summary_prompt, transcript, temp)
        summaries.append(f"## Tema: {topic} \n{summary}")
        st.info(f"Obradjujem temu: {topic}")
        
    # Optional: Generate a conclusion from the whole transcript
    conclusion_prompt = "Generate a conclusion from the whole meeting."
    conclusion = get_response(conclusion_prompt, transcript, temp)
    
    # Compile the full text
    full_text = (
    f"## Sastanak koordinacije AI Tima\n\n{introduction}\n\n"
    f"## Teme sastanka\n\n" + "\n".join([f"{topic}" for topic in topics]) + "\n\n"
    + "\n\n".join(summaries) 
    + f"\n\n## Zaključak\n\n{conclusion}"
    )
    return full_text


# prepare & do embeddings iz Embeddings repoa
def prepare_embeddings(chunk_size, chunk_overlap, dokum):
    skinuto = False
    napisano = False

    file_name = "chunks.json"
    with st.form(key="my_form_prepare", clear_on_submit=False):
        
        # define delimiter
        text_delimiter = st.text_input(
            "Unesite delimiter: ",
            help="Delimiter se koristi za podelu dokumenta na delove za indeksiranje. Prazno za paragraf",
        )
        # define prefix
        text_prefix = st.text_input(
            "Unesite prefiks za tekst: ",
            help="Prefiks se dodaje na početak teksta pre podela na delove za indeksiranje",
        )
        add_schema = st.radio(
            "Da li želite da dodate Metadata (Dodaje ime i temu u metadata): ",
            ("Ne", "Da"),
            key="add_schema_doc",
            help="Dodaje u metadata ime i temu",
        )
        add_pitanje = st.radio(
            "Da li želite da dodate pitanje: ",
            ("Ne", "Da"),
            key="add_pitanje_doc",
            help="Dodaje pitanje u text",
        )
        semantic = st.radio(
            "Da li želite semantic chunking: ",
            ("Ne", "Da"),
            key="semantic",
            help="Greg Kamaradt Semantic Chunker",
        )
        st.session_state.submit_b = st.form_submit_button(
            label="Submit",
            help="Pokreće podelu dokumenta na delove za indeksiranje",
        )
        st.info(f"Chunk veličina: {chunk_size}, chunk preklapanje: {chunk_overlap}")
        if len(text_prefix) > 0:
            text_prefix = text_prefix + " "

        if dokum is not None and st.session_state.submit_b == True:
            
            data=PineconeUtility.read_uploaded_file(dokum, text_delimiter)
            # Split the document into smaller parts, the separator should be the word "Chapter"
            if semantic == "Da":
                text_splitter = SemanticChunker(OpenAIEmbeddings())
            else:
                text_splitter = CharacterTextSplitter(
                        separator=text_delimiter,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                    )

            texts = text_splitter.split_documents(data)


            # # Create the OpenAI embeddings
            st.success(f"Učitano {len(texts)} tekstova")

            # Define a custom method to convert Document to a JSON-serializable format
            output_json_list = []
            
            # Loop through the Document objects and convert them to JSON
            i = 0
            for document in texts:
                i += 1
                if add_pitanje=="Da":
                    pitanje = TextProcessing.add_question(document.page_content) + " "
                    st.info(f"Dodajem pitanje u tekst {i}")
                else:
                    pitanje = ""
      
                output_dict = {
                    "id": str(uuid4()),
                    "chunk": i,
                    "text": TextProcessing.format_output_text(text_prefix, pitanje, document.page_content),
                    "source": document.metadata.get("source", ""),
                    "date": TextProcessing.get_current_date_formatted(),
                }

                if add_schema == "Da":
                    try:
                        person_name, topic = TextProcessing.add_self_data(document.page_content)
                    except Exception as e:
                        st.write(f"An error occurred: {e}")
                        person_name, topic = "John Doe", "Any"
    
                    output_dict["person_name"] = person_name
                    output_dict["topic"] = topic
                    st.success(f"Processing {i} of {len(texts)}, {person_name}, {topic}")

                output_json_list.append(output_dict)
                

            # # Specify the file name where you want to save the JSON data
            json_string = (
                "["
                + ",\n".join(
                    json.dumps(d, ensure_ascii=False) for d in output_json_list
                )
                + "]"
            )

            # Now, json_string contains the JSON data as a string

            napisano = st.info(
                "Tekstovi su sačuvani u JSON obliku, downloadujte ih na svoj računar"
            )

    if napisano:
        file_name = os.path.splitext(dokum.name)[0]
        skinuto = st.download_button(
            "Download JSON",
            data=json_string,
            file_name=f"{file_name}.json",
            mime="application/json",
        )
    if skinuto:
        st.success(f"Tekstovi sačuvani na {file_name} su sada spremni za Embeding")


def do_embeddings(dokum, tip, api_key, host, index_name, index):
    with st.form(key="my_form_do", clear_on_submit=False):
        err_log = ""
        # Read the texts from the .txt file
        chunks = []
        
        # Now, you can use stored_texts as your texts
        namespace = st.text_input(
            "Unesi naziv namespace-a: ",
            help="Naziv namespace-a je obavezan za kreiranje Pinecone Indeksa",
        )
        submit_b2 = st.form_submit_button(
            label="Submit", help="Pokreće kreiranje Pinecone Indeksa"
        )
        if submit_b2 and dokum and namespace:
            stringio = StringIO(dokum.getvalue().decode("utf-8"))

            # Directly load the JSON data from file content
            data = json.load(stringio)

            # Initialize lists outside the loop
            my_list = []
            my_meta = []

            # Process each JSON object in the data
            for item in data:
                # Append the text to my_list
                my_list.append(item['text'])
    
                # Append other data to my_meta
                meta_data = {key: value for key, value in item.items() if key != 'text'}
                my_meta.append(meta_data)
                
            if tip == "hybrid":
               embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
               bm25_encoder = BM25Encoder()
               # fit tf-idf values on your corpus
               bm25_encoder.fit(my_list)

               retriever = PineconeHybridSearchRetriever(
                    embeddings=embeddings,
                    sparse_encoder=bm25_encoder,
                    index=index,
               )
                           
               retriever.add_texts(texts=my_list, metadatas=my_meta, namespace=namespace)
               
            else:
                embed_model = "text-embedding-ada-002"
               
                batch_size = 100  # how many embeddings we create and insert at once
                progress_text2 = "Insertovanje u Pinecone je u toku."
                progress_bar2 = st.progress(0.0, text=progress_text2)
                ph2 = st.empty()
            
                for i in tqdm(range(0, len(data), batch_size)):
                    # find end of batch
                    i_end = min(len(data), i + batch_size)
                    meta_batch = data[i:i_end]

                    # get texts to encode
                    ids_batch = [x["id"] for x in meta_batch]
                    texts = [x["text"] for x in meta_batch]
                
                    # create embeddings (try-except added to avoid RateLimitError)
                    try:
                        res = client.embeddings.create(input=texts, model=embed_model)

                    except Exception as e:
                        done = False
                        print(e)
                        while not done:
                            sleep(5)
                            try:
                                res = client.embeddings.create(input=texts, model=embed_model)
                                done = True

                            except:
                                pass

                    embeds = [item.embedding for item in res.data]

                    # Check for [nan] embeddings
              
                    if len(embeds) > 0:
                    
                        to_upsert = list(zip(ids_batch, embeds, meta_batch))
                    else:
                        err_log += f"Greška: {meta_batch}\n"
                    # upsert to Pinecone
                    err_log += f"Upserting {len(to_upsert)} embeddings\n"
                    with open("err_log.txt", "w", encoding="utf-8") as file:
                        file.write(err_log)

                    index.upsert(vectors=to_upsert, namespace=namespace)
                    stodva = len(data)
                    if i_end > i:
                        deo = i_end
                    else:
                        deo = i
                    progress = deo / stodva
                    l = int(deo / stodva * 100)

                    ph2.text(f"Učitano je {deo} od {stodva} linkova što je {l} %")

                    progress_bar2.progress(progress, text=progress_text2)
                    

            # gives stats about index
            st.info("Napunjen Pinecone")

            st.success(f"Sačuvano u Pinecone-u")
            pinecone_stats(index, index_name)



# Define a function to scrape a given URL
def scrape(url: str):
    global headers, sajt, err_log, tiktoken_len, vrsta
    # Send a GET request to the URL
    res = requests.get(url, headers=headers)

    # Check the response status code
    if res.status_code != 200:
        # If the status code is not 200 (OK), write the status code and return None
        err_log += f"{res.status_code} for {url}\n"
        return None

    # If the status code is 200, initialize BeautifulSoup with the response text
    soup = BeautifulSoup(res.text, "html.parser")
    # soup = BeautifulSoup(res.text, 'lxml')

    # Find all links to local pages on the website
    local_links = []
    for link in soup.find_all("a", href=True):
        if (
            link["href"].startswith(sajt)
            or link["href"].startswith("/")
            or link["href"].startswith("./")
        ):
            href = link["href"]
            base_url, extension = os.path.splitext(href)
            if not extension and not "mailto" in href and not "tel" in href:
          
                local_links.append(urljoin(sajt, href))

                # Find the main content using CSS selectors
                try:
                    # main_content_list = soup.select('body main')
                    main_content_list = soup.select(vrsta)

                    # Check if 'main_content_list' is not empty
                    if main_content_list:
                        main_content = main_content_list[0]

                        # Extract the plaintext of the main content
                        main_content_text = main_content.get_text()

                        # Remove all HTML tags
                        main_content_text = re.sub(r"<[^>]+>", "", main_content_text)

                        # Remove extra white space
                        main_content_text = " ".join(main_content_text.split())

                        # Replace HTML entities with their corresponding characters
                        main_content_text = html.unescape(main_content_text)

                    else:
                        # Handle the case when 'main_content_list' is empty
                        main_content_text = "error"
                        err_log += f"Error in page structure, use body instead\n"
                        st.error(err_log)
                        sys.exit()
                except Exception as e:
                    err_log += f"Error while discovering page content\n"
                    return None

    # return as json
    return {"url": url, "text": main_content_text}, local_links


# Define a function to scrape a given URL
def main_scraper(chunk_size, chunk_overlap):
    skinuto = False
    napisano = False
    file_name = "chunks.json"
    with st.form(key="my_form_scrape", clear_on_submit=False):
        global res, err_log, headers, sajt, source, vrsta
        st.subheader("Pinecone Scraping")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }

        # Set the domain URL

        # with st.form(key="my_form", clear_on_submit=False):
        sajt = st.text_input("Unesite sajt : ")
        # prefix moze da se definise i dinamicki
        text_prefix = st.text_input(
            "Unesite prefiks za tekst: ",
            help="Prefiks se dodaje na početak teksta pre podela na delove za indeksiranje",
        )
        vrsta = st.radio(
            "Unesite vrstu (default je body main): ", ("body main", "body")
        )
        # add_schema = st.radio(
        #     "Da li želite da dodate Schema Data (može značajno produžiti vreme potrebno za kreiranje): ",
        #     ("Da", "Ne"),
        #     help="Schema Data se dodaje na početak teksta",
        #     key="add_schema_web",
        # )
        # chunk_size, chunk_overlap = def_chunk()
        submit_button = st.form_submit_button(label="Submit")
        st.info(f"Chunk veličina: {chunk_size}, chunk preklapanje: {chunk_overlap}")
        if len(text_prefix) > 0:
            text_prefix = text_prefix + " "
        if submit_button and not sajt == "":
            res = requests.get(sajt, headers=headers)
            err_log = ""

            # Read OpenAI API key from file
            openai.api_key = os.environ.get("OPENAI_API_KEY")

            # # Retrieving API keys from files
            # PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")

            # # Setting the environment for Pinecone API
            # PINECONE_API_ENV = os.environ.get("PINECONE_API_ENV")

            # pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_API_ENV)

            # Initialize BeautifulSoup with the response text
            soup = BeautifulSoup(res.text, "html.parser")
            # soup = BeautifulSoup(res.text, 'html5lib')

            # Define a function to scrape a given URL

            links = [sajt]
            scraped = set()
            data = []
            i = 0
            placeholder = st.empty()

            with st.spinner(f"Scraping "):
                while True:
                    # while i < 2:
                    i += 1
                    if len(links) == 0:
                        st.success("URL lista je kompletirana")
                        break
                    url = links[0]

                    # st.write(f'{url}, ">>", {i}')
                    placeholder.text(f"Obrađujem link broj {i}")
                    try:
                        res = scrape(url)
                        err_log += f" OK scraping {url}: {i}\n"
                    except Exception as e:
                        err_log += f"An error occurred while scraping {url}: page can not be scraped.\n"

                    scraped.add(url)

                    if res is not None:
                        page_content, local_links = res
                        data.append(page_content)
                        # add new links to links list
                        links.extend(local_links)
                        # remove duplicates
                        links = list(set(links))
                    # remove links already scraped
                    links = [link for link in links if link not in scraped]

                # Initialize RecursiveCharacterTextSplitter
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size, chunk_overlap=chunk_overlap
                )
            chunks = []

            progress_text = "Podaci za Embeding se trenutno kreiraju. Molimo sačekajte."

            progress_bar = st.progress(0.0, text=progress_text)
            ph = st.empty()
            progress_barl = st.progress(0.0, text=progress_text)
            ph2 = st.empty()
            ph3 = st.empty()
            # Iterate over data records
            with st.spinner(f"Kreiranje podataka za Embeding"):
                for idx, record in enumerate(tqdm(data)):
                    # Split the text into chunks using the text splitter
                    texts = text_splitter.split_text(record["text"])

                    sto = len(data)
                    odsto = idx + 1
                    procenat = odsto / sto

                    k = int(odsto / sto * 100)
                    progress_bar.progress(procenat, text=progress_text)
                    ph.text(f"Učitano {odsto} od {sto} linkova što je {k} % ")
                    # Create a list of chunks for each text

                    # ovde moze da se doda dinamicko dadavanje prefixa
                    for il in range(len(texts)):
                        stol = len(texts)
                        odstol = il + 1
                        procenatl = odstol / stol

                        kl = int(odstol / stol * 100)
                        progress_barl.progress(procenatl, text=progress_text)
                        ph2.text(f"Učitano {odstol} od {stol} chunkova što je {kl} % ")

                        chunks.append(
                            {
                                "id": str(uuid4()),
                                "text": f"{text_prefix}  {texts[il]}",
                                "source": record["url"],
                                "date": datetime.datetime.now().strftime("%d.%m.%Y")
                            }
                        )

                    # Generate JSON strings for each chunk and join them with newline characters
                    json_strings = [
                        json.dumps(chunk, ensure_ascii=False) for chunk in chunks
                    ]
                    json_string = ",\n".join(json_strings)

                    # Add "[" at the beginning and "]" at the end of the entire JSON string
                    json_string = "[" + json_string + "]"
                    # Assuming 'chunks' is your list of dictionaries

                    # Now, json_string contains the JSON data as a string

                    napisano = st.info(
                        "Tekstovi su sačuvani u JSON obliku, downloadujte ih na svoj računar"
                    )

                    # Specify the file name where you want to save the JSON data

    parsed_url = urlparse(sajt)
    # Get the netloc (which includes the website name)
    website_name = parsed_url.netloc
    # Remove any potential "www." prefix
    if website_name.startswith("www."):
        website_name = website_name[4:]
    parts = website_name.split(".")
    if len(parts) > 1:
        website_name = parts[0]

    if napisano:
        skinuto = st.download_button(
            "Download JSON",
            data=json_string,
            file_name=f"{website_name}.json",
            mime="application/json",
        )
    if skinuto:
        st.success(f"Tekstovi sačuvani na {file_name} su sada spremni za Embeding")




def rag_tool_answer(prompt, phglob):
    context = " "
    st.session_state.rag_tool = get_structured_decision_from_model(prompt)

    if  st.session_state.rag_tool == "Hybrid":
        processor = HybridQueryProcessor(alpha=st.session_state.alpha, score=st.session_state.score, namespace="zapisnici")
        context, scores = processor.process_query_results(prompt)
        st.info("Score po chunku:")
        st.write(scores)
        
    # SelfQuery Tool Configuration
    elif  st.session_state.rag_tool == "SelfQuery":
        # Example configuration for SelfQuery
        uvod = st.session_state.self_query
        prompt = uvod + prompt
        context = SelfQueryPositive(prompt, namespace="selfdemo", index_name="neo-positive")
        
    # SQL Tool Configuration
    elif st.session_state.rag_tool == "SQL":
            processor = SQLSearchTool()
            try:
                context = processor.search(prompt)
            except Exception as e :
                st.error(f"Ne mogu da ispunim zahtev {e}")
    elif st.session_state.rag_tool == "WebSearchProcess":
         context = web_search_process(prompt)
         
    # Parent Doc Tool Configuration
    elif  st.session_state.rag_tool == "ParentDoc":
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
    elif  st.session_state.rag_tool == "ParentChunks":
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
        chain = GraphQAChain.from_llm(ChatOpenAI(model="gpt-4-turbo-preview", temperature=0), graph=graph, verbose=True)
        rezultat= chain.invoke(prompt)
        context = rezultat['result']

    # Hyde Tool Configuration
    elif  st.session_state.rag_tool == "Hyde":
        # Assuming a processor for Hyde exists
        context = hyde_rag(prompt)

    # MultiQuery Tool Configuration
    elif  st.session_state.rag_tool == "MultiQuery":
        # Initialize the MQDR instance
        retriever_instance = MultiQueryDocumentRetriever(prompt)
        # To get documents relevant to the original question
        context = retriever_instance.get_relevant_documents(prompt)
        output=retriever_instance.log_messages
        generated_queries = output[0].split(": ")[1]
        queries = ast.literal_eval(generated_queries)
        st.info(f"Dodatna pitanja - MultiQuery Alat:")
        for query in queries:
            st.caption(query)


    # RAG Fusion Tool Configuration
    elif  st.session_state.rag_tool == "CohereReranking":
        # Retrieve documents using Pinecone
        pinecone_retriever = PineconeRetriever(prompt)
        docs = pinecone_retriever.get_relevant_documents()
        documents = [doc.page_content for doc in docs]
        
        # Rerank documents using Cohere
        cohere_reranker = CohereReranker(prompt)
        context = cohere_reranker.rerank(documents)
        
    elif  st.session_state.rag_tool == "ContextualCompression":
        # Retrieve documents using Pinecone
        pinecone_retriever = PineconeRetriever(prompt)
        docs = pinecone_retriever.get_relevant_documents()
        documents = [doc.page_content for doc in docs]
       
        # Retrieve and compressed context
        context_retriever = ContextRetriever(documents)
        context = context_retriever.get_compressed_context()
        
    elif  st.session_state.rag_tool == "LongContext":
         # Retrieve documents using Pinecone
        pinecone_retriever = PineconeRetriever(prompt)
        docs = pinecone_retriever.get_relevant_documents()
        documents = [doc.page_content for doc in docs]
        
        # Reorder documents for long context handling
        long_context_handler = LongContextHandler()
        context = long_context_handler.reorder(documents)

    elif  st.session_state.rag_tool == "Calendly":
        # Schedule Calendly meeting
        context = positive_calendly(phglob)

    elif st.session_state.rag_tool == "UploadedDoc":
        # Read text from the uploaded document
        try:
            context = "Text from the document: " + st.session_state.uploaded_doc[0].page_content
        except:
            context = "No text found in the document. Please check if the document is in the correct format."

    elif st.session_state.rag_tool == "WebScrap":
        try:
            context = "Text from the webpage: " + scrape_webpage_text(st.session_state.url_to_scrap)
        except:
            context = "No text found in the webpage. Please check if the URL is correct."
            
    return context


def scrape_webpage_text(url):
    """
    Fetches the content of a webpage by URL and returns the textual content,
    excluding HTML tags and script content.

    Args:
    - url (str): The URL of the webpage to scrape.

    Returns:
    - str: The textual content of the webpage.
    """
    try:
        # Send a GET request to the webpage
        response = requests.get(url)
        # Raise an exception if the request was unsuccessful
        response.raise_for_status()
        
        # Parse the content of the request with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()
        
        # Get text from the parsed content
        text = soup.get_text()
        
        # Clean up the text by collapsing whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    except requests.RequestException as e:
        return f"An error occurred: {e}"


def positive_calendly(phglob):
    with st.sidebar:
        with phglob.container():
            calendly_url = "https://calendly.com/djordje-thai/30min/?embed=true"
            iframe_html = f'<iframe src="{calendly_url}" width="320" height="820"></iframe>'
            st.components.v1.html(iframe_html, height=820)
            
    return "Do not answer to this question, just say Hvala"
