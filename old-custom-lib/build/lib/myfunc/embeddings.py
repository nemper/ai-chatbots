import ast
import cohere
import json
import logging
import os
import streamlit as st

from io import StringIO
from openai import OpenAI
from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder
from time import sleep
from tqdm.auto import tqdm
from uuid import uuid4

from langchain.chains import GraphQAChain
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.indexes.graph import NetworkxEntityGraph
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain.prompts import PromptTemplate
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.document_transformers import LongContextReorder
from langchain_community.retrievers import PineconeHybridSearchRetriever
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from mojafunkcija import st_style, pinecone_stats
from prompts import PromptDatabase, SQLSearchTool
from retrievers import HybridQueryProcessor, PineconeUtility, SelfQueryPositive, TextProcessing
from various_tools import get_structured_decision_from_model, positive_calendly, web_search_process, scrape_webpage_text, hyde_rag

if "init_prompts" not in st.session_state:
    st.session_state.init_prompts = 42
    with PromptDatabase() as db:
        prompt_map = db.get_prompts_by_names(["contextual_compression"],[os.getenv("CONTEXTUAL_COMPRESSION")])
        st.session_state.contextual_compression = prompt_map.get("contextual_compression", "You are helpful assistant").format()

st_style()
client=OpenAI()
text_processor = TextProcessing(gpt_client=client)
pinecone_utility = PineconeUtility()

class MultiQueryDocumentRetriever:
    """
    Retrieves relevant documents for complex queries by utilizing multi-query techniques
    and Pinecone's hybrid search capabilities.
    
    Attributes:
        
        question (str): Main query for document retrieval.
        namespace (str): Namespace within Pinecone where documents are stored.
        model (str): Model used for generating embeddings for the query and documents.
        temperature (int): Temperature setting for the language model, affecting creativity.
        host (str): Host URL for the Pinecone service.
    """

    def __init__(self, question, namespace="zapisnici", model="text-embedding-3-large", host="https://neo-positive-a9w1e6k.svc.apw5-4e34-81fa.pinecone.io", temperature=0):
        
        self.question = question
        self.namespace = namespace
        self.model = model
        self.host = host
        self.temperature = temperature
        self.log_messages = []
        self.logger = self._init_logger()
        self.llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=self.temperature)
        self.retriever = self._init_retriever()

    def _init_logger(self):
        """Initializes and configures the logger to store messages in an attribute."""
        class ListHandler(logging.Handler):
            def __init__(self, log_messages_list):
                super().__init__()
                self.log_messages_list = log_messages_list

            def emit(self, record):
                log_message = self.format(record)
                self.log_messages_list.append(log_message)

        log_handler = ListHandler(self.log_messages)
        log_handler.setLevel(logging.INFO)
        logger = logging.getLogger("langchain.retrievers.multi_query")
        logger.setLevel(logging.INFO)
        logger.addHandler(log_handler)
        return logger

    def _init_retriever(self):
        """Initializes the document retriever with Pinecone Hybrid Search."""
        api_key = os.environ.get("PINECONE_API_KEY_S")
        pinecone = Pinecone(api_key=api_key, host=self.host)
        index = pinecone.Index(host=self.host)
        
        embeddings = OpenAIEmbeddings(model=self.model)
        bm25_encoder = BM25Encoder()
        bm25_encoder.fit(self.question)

        pinecone_retriever = PineconeHybridSearchRetriever(
            embeddings=embeddings,
            sparse_encoder=bm25_encoder,
            index=index,
            namespace=self.namespace
        )
        our_template = """You are an AI language model assistant. Your task is to generate 4 different versions of the given user 
            question to retrieve relevant documents from a vector  database. 
            By generating multiple perspectives on the user question, your goal is to help the user overcome some of the limitations 
            of distance-based similarity search. Provide these alternative questions separated by newlines. 
            Original question: 
            {question}
        """
        our_prompt = PromptTemplate(input_variables=['question'], template=our_template)
        return MultiQueryRetriever.from_llm(retriever=pinecone_retriever, llm=self.llm, prompt=our_prompt)

    def get_relevant_documents(self, custom_question=None):
        """Retrieves documents relevant to the provided or default query."""
        if custom_question is None:
            custom_question = self.question
        
        result = self.retriever.get_relevant_documents(query=custom_question)
        
        return "\n\n".join([doc.page_content for doc in result])


class PineconeRetriever:
    """Handles document retrieval using Pinecone's hybrid search capabilities.
    
    Attributes:
        query (str): The search query for retrieving documents.
        namespace (str): The namespace within Pinecone where the documents are stored.
        model (str): The model used for generating embeddings for the query and documents.
    """
    def __init__(self, query, namespace="zapisnici", model="text-embedding-3-large", host="https://neo-positive-a9w1e6k.svc.apw5-4e34-81fa.pinecone.io"):
            self.query = query
            self.namespace = namespace
            self.model = model
            self.host = host  # Ensure the host attribute is correctly set here
            self.pinecone = self._init_pinecone(host)  # Pass the host to the Pinecone initialization
            self.index = self.pinecone.Index(host=self.host)  # Use the host attribute here
            self.embeddings = OpenAIEmbeddings(model=self.model)
            self.bm25_encoder = BM25Encoder()
            self.bm25_encoder.fit(self.query)
            self.retriever = PineconeHybridSearchRetriever(
                embeddings=self.embeddings,
                sparse_encoder=self.bm25_encoder,
                index=self.index,
                namespace=self.namespace
            )

    def _init_pinecone(self, host):
        """Initializes the Pinecone service with the API key and host.
        
        Args:
            host (str): The host URL for the Pinecone service.
        """
        api_key = os.environ.get("PINECONE_API_KEY_S")
        return Pinecone(api_key=api_key, host=host)


    def get_relevant_documents(self):
        """Retrieves documents relevant to the query from Pinecone."""
        return self.retriever.get_relevant_documents(self.query)


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
            print("B", dokum)
            print("B", type(dokum))
            data=pinecone_utility.read_uploaded_file(dokum, text_delimiter)
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
                    pitanje = text_processor.add_question(document.page_content) + " "
                    st.info(f"Dodajem pitanje u tekst {i}")
                else:
                    pitanje = ""
      
                output_dict = {
                    "id": str(uuid4()),
                    "chunk": i,
                    "text": text_processor.format_output_text(text_prefix, pitanje, document.page_content),
                    "source": document.metadata.get("source", ""),
                    "date": text_processor.get_current_date_formatted(),
                }

                if add_schema == "Da":
                    try:
                        person_name, topic = text_processor.add_self_data(document.page_content)
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


class CohereReranker:
    """Reranks documents based on relevance to the query using Cohere's rerank model.

    Attributes:
        query (str): The search query for reranking documents.
    """
    def __init__(self, query):
        self.query = query
        self.client = cohere.Client(os.getenv("COHERE_API_KEY"))

    def rerank(self, documents):
        """Reranks the given documents based on their relevance to the query.

        Args:
            documents (list): A list of document texts to be reranked.

        Returns:
            str: A string containing the top reranked documents concatenated together.
        """
        results = self.client.rerank(query=self.query, documents=documents, top_n=3, model="rerank-multilingual-v2.0")
        return "\n\n".join([result.document['text'] for result in results])


class LongContextHandler:
    """Reorders documents to prioritize more relevant content for long contexts.

    This class does not require initialization parameters.
    """
    def reorder(self, documents):
        """Reorders the given documents based on their relevance and context.

        Args:
            documents (list): A list of document texts to be reordered.

        Returns:
            str: A string containing the reordered documents concatenated together.
        """
        reordering = LongContextReorder()
        reordered_docs = reordering.transform_documents(documents)
        return "\n\n".join(reordered_docs)


class ContextRetriever:
    """Retrieves and compresses documents to only include the most relevant parts.
    
    Attributes:
        documents (list): A list of documents to be compressed.
        model (str): The model used for compression.
    """
    
    def __init__(self, documents, model="gpt-4-turbo-preview"):
        self.documents = documents
        self.model = model
        
        response_schemas = [
            ResponseSchema(name="compressed_text", description="The compressed text of the document"),
        ]
        
        output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
        format_instructions = output_parser.get_format_instructions()
        
        self.prompt = PromptTemplate(
            template=st.session_state.contextual_compression,
            input_variables=["documents"],
            partial_variables={"format_instructions": format_instructions},
        )
        self.llm = ChatOpenAI(model=self.model, temperature=0)
        # ovo bar je kako je bilo u primeru
        self.chain = self.prompt | self.llm | output_parser

    def get_compressed_context(self):
        """Compresses the provided documents to include only the most relevant parts."""
        # combine documents into a single string
        compressed_output = self.chain.invoke({"documents": "\n\n".join(self.documents)})

        # just in case...
        if isinstance(compressed_output, dict) and 'compressed_text' in compressed_output:
            return compressed_output['compressed_text']
        else:
            return "Error: Unexpected structure of compressed_output"
        

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
