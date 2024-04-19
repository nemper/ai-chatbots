# in myfunc.retrievers.py
import datetime
import io
import json
import matplotlib.pyplot as plt
import networkx as nx
import openai
import os
import PyPDF2
import re
import streamlit as st
import sys
import time
import unidecode

from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder

from langchain.chains.query_constructor.base import AttributeInfo
from langchain.indexes import GraphIndexCreator
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_community.vectorstores import Pinecone as LangPine
from langchain_openai import OpenAIEmbeddings
from langchain_openai.chat_models import ChatOpenAI

from myfunc.mojafunkcija import pinecone_stats
from myfunc.varvars_dicts import work_vars


# in myfunc.retrievers.py
class HybridQueryProcessor:
    """
    A processor for executing hybrid queries using Pinecone.

    This class allows the execution of queries that combine dense and sparse vector searches,
    typically used for retrieving and ranking information based on text data.

    Attributes:
        api_key (str): The API key for Pinecone.
        environment (str): The Pinecone environment setting.
        alpha (float): The weight used to balance dense and sparse vector scores.
        score (float): The score treshold.
        index_name (str): The name of the Pinecone index to be used.
        index: The Pinecone index object.
        namespace (str): The namespace to be used for the Pinecone index.
        top_k (int): The number of results to be returned.
            
    Example usage:
    processor = HybridQueryProcessor(api_key=environ["PINECONE_API_KEY"], 
                                 environment=environ["PINECONE_API_KEY"],
                                 alpha=0.7, 
                                 score=0.35,
                                 index_name='custom_index'), 
                                 namespace=environ["NAMESPACE"],
                                 top_k = 10 # all params are optional

    result = processor.hybrid_query("some query text")    
    """

    def __init__(self, **kwargs):
        """
        Initializes the HybridQueryProcessor with optional parameters.

        The API key and environment settings are fetched from the environment variables.
        Optional parameters can be passed to override these settings.

        Args:
            **kwargs: Optional keyword arguments:
                - api_key (str): The API key for Pinecone (default fetched from environment variable).
                - environment (str): The Pinecone environment setting (default fetched from environment variable).
                - alpha (float): Weight for balancing dense and sparse scores (default 0.5).
                - score (float): Weight for balancing dense and sparse scores (default 0.05).
                - index_name (str): Name of the Pinecone index to be used (default 'positive').
                - namespace (str): The namespace to be used for the Pinecone index (default fetched from environment variable).
                - top_k (int): The number of results to be returned (default 6).
        """
        self.api_key = kwargs.get('api_key', os.getenv('PINECONE_API_KEY'))
        self.environment = kwargs.get('environment', os.getenv('PINECONE_API_KEY'))
        self.alpha = kwargs.get('alpha', 0.5)  # Default alpha is 0.5
        self.score = kwargs.get('score', 0.05)  # Default score is 0.05
        self.index_name = kwargs.get('index', 'neo-positive')  # Default index is 'positive'
        self.namespace = kwargs.get('namespace', os.getenv("NAMESPACE"))  
        self.top_k = kwargs.get('top_k', 6)  # Default top_k is 6
        self.index = None
        self.host = os.getenv("PINECONE_HOST")
        self.init_pinecone()

    def init_pinecone(self):
        """
        Initializes the Pinecone connection and index.
        """
        pinecone=Pinecone(api_key=self.api_key, host=self.host)
        self.index = pinecone.Index(host=self.host)

    def get_embedding(self, text, model="text-embedding-3-large"):
        """
        Retrieves the embedding for the given text using the specified model.

        Args:
            text (str): The text to be embedded.
            model (str): The model to be used for embedding. Default is "text-embedding-ada-002".

        Returns:
            list: The embedding vector of the given text.
        """
        client = openai
        text = text.replace("\n", " ")
        
        return client.embeddings.create(input=[text], model=model).data[0].embedding

    def hybrid_score_norm(self, dense, sparse):
        """
        Normalizes the scores from dense and sparse vectors using the alpha value.

        Args:
            dense (list): The dense vector scores.
            sparse (dict): The sparse vector scores.

        Returns:
            tuple: Normalized dense and sparse vector scores.
        """
        return ([v * self.alpha for v in dense], 
                {"indices": sparse["indices"], 
                 "values": [v * (1 - self.alpha) for v in sparse["values"]]})

    def hybrid_query(self, upit, top_k=None, filter=None, namespace=None):
        """
        Executes a hybrid query on the Pinecone index using the provided query text.

        Args:
            upit (str): The query text.
            top_k (int, optional): The number of results to be returned. If not provided, use the class's top_k value.
            filter (dict, optional): Additional filter criteria for the query.
            namespace (str, optional): The namespace to be used for the query. If not provided, use the class's namespace.

        Returns:
            list: A list of query results, each being a dictionary containing page content, chunk, and source.
        """
        hdense, hsparse = self.hybrid_score_norm(
            sparse=BM25Encoder().fit([upit]).encode_queries(upit),
            dense=self.get_embedding(upit))
    
        query_params = {
            'top_k': top_k or self.top_k,
            'vector': hdense,
            'sparse_vector': hsparse,
            'include_metadata': True,
            'namespace': namespace or self.namespace
        }

        if filter:
            query_params['filter'] = filter

        response = self.index.query(**query_params)

        matches = response.to_dict().get('matches', [])

        # Construct the results list
        results = []
        for match in matches:
            metadata = match.get('metadata', {})
            context = metadata.get('context', '')
            chunk = metadata.get('chunk')
            source = metadata.get('source')
            try:
                score = match.get('score', 0)
            except:
                score = metadata.get('score', 0)

            # Append a dictionary with page content, chunk, and source
            if context:  # Ensure that 'context' is not empty
                results.append({"page_content": context, "chunk": chunk, "source": source, "score": score})
        
        return results


    def process_query_results(self, upit):
        """
        Processes the query results based on relevance score and formats them for a chat or dialogue system.
        Additionally, returns a list of scores for items that meet the score threshold.

        Args:
            upit (str): The original query text.
        
        Returns:
            tuple: A tuple containing the formatted string for chat prompt and a list of scores.
        """
        tematika = self.hybrid_query(upit)

        uk_teme = ""  # Formatted string for chat prompt
        score_list = []  # List to hold scores that meet the threshold

        for item in tematika:
            if item["score"] > self.score:  # Score threshold
                uk_teme += item["page_content"] + "\n\n"
                score_list.append(item["score"])  # Append the score to the list

        return uk_teme, score_list

    def process_query_parent_results(self, upit):
        """
        Processes the query results and returns top result with source name, chunk number, and page content.
        It is used for parent-child queries.

        Args:
            upit (str): The original query text.
    
        Returns:
            tuple: Formatted string for chat prompt, source name, and chunk number.
        """
        tematika = self.hybrid_query(upit)

        # Check if there are any matches
        if not tematika:
            return "No results found", None, None

        # Extract information from the top result
        top_result = tematika[0]
        top_context = top_result.get('page_content', '')
        top_chunk = top_result.get('chunk')
        top_source = top_result.get('source')

        return top_context, top_source, top_chunk

     
    def search_by_source(self, upit, source_result, top_k=5, filter=None):
        """
        Perform a similarity search for documents related to `upit`, filtered by a specific `source_result`.
        
        :param upit: Query string.
        :param source_result: source to filter the search results.
        :param top_k: Number of top results to return.
        :param filter: Additional filter criteria for the query.
        :return: Concatenated page content of the search results.
        """
        filter_criteria = filter or {}
        filter_criteria['source'] = source_result
        top_k = top_k or self.top_k
        
        doc_result = self.hybrid_query(upit, top_k=top_k, filter=filter_criteria, namespace=self.namespace)
        result = "\n\n".join(document['page_content'] for document in doc_result)
    
        return result
        
       
    def search_by_chunk(self, upit, source_result, chunk, razmak=3, top_k=20, filter=None):
        """
        Perform a similarity search for documents related to `upit`, filtered by source and a specific chunk range.
        Namespace for store can be different than for the original search.
    
        :param upit: Query string.
        :param source_result: source to filter the search results.
        :param chunk: Target chunk number.
        :param razmak: Range to consider around the target chunk.
        :param top_k: Number of top results to return.
        :param filter: Additional filter criteria for the query.
        :return: Concatenated page content of the search results.
        """
        
        manji = chunk - razmak
        veci = chunk + razmak
    
        filter_criteria = filter or {}
        filter_criteria = {
            'source': source_result,
            '$and': [{'chunk': {'$gte': manji}}, {'chunk': {'$lte': veci}}]
        }
        
        
        doc_result = self.hybrid_query(upit, top_k=top_k, filter=filter_criteria, namespace=self.namespace)

        # Sort the doc_result based on the 'chunk' value
        sorted_doc_result = sorted(doc_result, key=lambda document: document.get('chunk', float('inf')))

        # Generate the result string
        result = " ".join(document.get('page_content', '') for document in sorted_doc_result)
    
        return result


# in myfunc.retrievers.py
class ParentPositiveManager:
    """
    This class manages the functionality for performing similarity searches using Pinecone and OpenAI Embeddings.
    It provides methods for retrieving documents based on similarity to a given query (`upit`), optionally filtered by source and chunk range.
    Works both with the original and the hybrid search. 
    Search by chunk is in the same namespace. Search by source can be in a different namespace.
    
    """
    
    # popraviti: 
    # 1. standardni set metadata source, chunk, datum. Za cosine index sadrzaj je text, za hybrid search je context (ne korsiti se ovde)
   
    
    def __init__(self, api_key=None, environment=None, index_name=None, namespace=None, openai_api_key=None):
        """
        Initializes the Pinecone and OpenAI Embeddings with the provided or environment-based configuration.
        
        :param api_key: Pinecone API key.
        :param environment: Pinecone environment.
        :param index_name: Name of the Pinecone index.
        :param namespace: Namespace for document retrieval.
        :param openai_api_key: OpenAI API key.
        :param index_name: Pinecone index name.
        
        """
        self.api_key = api_key if api_key is not None else os.getenv('PINECONE_API_KEY')
        self.environment = environment if environment is not None else os.getenv('PINECONE_ENV')
        self.namespace = namespace if namespace is not None else os.getenv("NAMESPACE")
        self.openai_api_key = openai_api_key if openai_api_key is not None else os.getenv("OPENAI_API_KEY")
        self.index_name = index_name if index_name is not None else os.getenv("PINECONE_INDEX")
        self.host = os.getenv("PINECONE_HOST")
        pinecone=Pinecone(api_key=api_key, host=self.host)
        self.index = pinecone.Index(host=self.host)
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        self.docsearch = LangPine.from_existing_index(self.index_name, self.embeddings)

    def search_by_source(self, upit, source_result, top_k=5):
        """
        Perform a similarity search for documents related to `upit`, filtered by a specific `source_result`.
        
        :param upit: Query string.
        :param source_result: source to filter the search results.
        :return: Concatenated page content of the search results.
        """
        doc_result = self.docsearch.similarity_search(upit, k=top_k, filter={'source': source_result}, namespace=self.namespace)
        result = "\n\n".join(document.page_content for document in doc_result)
        
        return result

    def search_by_chunk(self, upit, source_result, chunk, razmak=3, top_k=20):
        """
        Perform a similarity search for documents related to `upit`, filtered by source and a specific chunk range.
        Namsepace for store can be different than for th eoriginal search.
        
        :param upit: Query string.
        :param source_result: source to filter the search results.
        :param chunk: Target chunk number.
        :param razmak: Range to consider around the target chunk.
        :return: Concatenated page content of the search results.
        """
        
        manji = chunk - razmak
        veci = chunk + razmak
        
        filter_criteria = {
            'source': source_result,
            '$and': [{'chunk': {'$gte': manji}}, {'chunk': {'$lte': veci}}]
        }
        doc_result = self.docsearch.similarity_search(upit, k=top_k, filter=filter_criteria, namespace=self.namespace)
        # Sort the doc_result based on the 'chunk' metadata
        sorted_doc_result = sorted(doc_result, key=lambda document: document.metadata['chunk'])
        # Generate the result string
        result = " ".join(document.page_content for document in sorted_doc_result)
        
        return result

    def basic_search(self, upit):
        """
        Perform a basic similarity search for the document most related to `upit`.
        
        :param upit: Query string.
        :return: Tuple containing the page content, source, and chunk number of the top search result.
        """
        doc_result = self.docsearch.similarity_search(upit, k=1, namespace=self.namespace)
        top_result = doc_result[0]
        
        return top_result.page_content, top_result.metadata['source'], top_result.metadata['chunk']
   

# in myfunc.retrievers.py
class TextProcessing:
    def __init__(self, gpt_client):
        self.client = gpt_client

    def add_self_data(self, line):
        """
        Extracts the person's name and topic from a given line of text using a GPT-4 model.

        This function sends a request to a GPT-4 model with a specific prompt that instructs the model to use JSON format
        for extracting a person's name ('person_name') and a topic from the provided text ('line'). The prompt includes instructions
        to use the Serbian language for extraction. If the model cannot decide on a name, it is instructed to return 'John Doe'.

        Parameters:
        - line (str): A line of text from which the person's name and topic are to be extracted.

        Returns:
        - tuple: A tuple containing the extracted person's name and topic. If the extraction is successful, it returns
        (person_name, topic). If the model cannot decide on a name, it returns ('John Doe', topic).

        Note:
        The function assumes that the response from the GPT-4 model is in a JSON-compatible format and that the keys
        'person_name' and 'topic' are present in the JSON object returned by the model.
        """
        response = self.client.chat.completions.create(
            model=work_vars["names"]["openai_model"],
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "result1"},
                {"role": "user", "content": line}
            ]
        )
        json_content = response.choices[0].message.content.strip()
        content_dict = json.loads(json_content)
        person_name = content_dict.get("person_name", "John Doe")
        topic = content_dict["topic"]
        
        return person_name, topic

    def format_output_text(self, prefix, question, content):
        """
        Formats the output text.
        """
        return prefix + question + content

    def get_current_date_formatted(self):
        """
        Returns the current date formatted as a string.
        """
        return datetime.datetime.now().strftime("%d.%m.%Y")

    def add_question(self, chunk_text):
        """
        Adds a question to a chunk of text to match the given statement.
        """
        result = self.client.chat.completions.create(
            model=work_vars["names"]["openai_model"],
            temperature=0,
            messages=[
                {"role": "system", "content": "result2"},
                {"role": "user", "content": chunk_text}
            ]
        )

        return result.choices[0].message.content


# in myfunc.retrievers.py
class PineconeUtility:
    def __init__(self):
        # Nothing to initialize
        x = 1

    def obrisi_index(self):
        # Method for handling Pinecone index deletion
        index_name = st.selectbox("Odaberite index", ["neo-positive", "embedings1"], help="Unesite ime indeksa", key="opcije"
    )
        if index_name is not None and index_name!=" " and index_name !="" :
            col1, col2 = st.columns(2)
            if index_name=="embedings1":
            
                pinecone=Pinecone(api_key=os.environ.get("PINECONE_API_KEY_STARI"), host="https://embedings1-b1b39e1.svc.us-west1-gcp.pinecone.io") #embedings1 (thai, free)
                index = pinecone.Index(host="https://embedings1-b1b39e1.svc.us-west1-gcp.pinecone.io") #embedings1
            elif index_name=="neo-positive":
                
                pinecone=Pinecone(api_key=os.environ.get("PINECONE_API_KEY_S"), host="https://neo-positive-a9w1e6k.svc.apw5-4e34-81fa.pinecone.io") #neo-positive (thai, serverless, 3072)
                index = pinecone.Index(host="https://neo-positive-a9w1e6k.svc.apw5-4e34-81fa.pinecone.io") #neo-positive
            else:
                st.error("Index ne postoji")
                st.stop()
            with col2:
                pinecone_stats(index, index_name)
        
            with col1:
                with st.form(key="util", clear_on_submit=True):
                    st.subheader("Uklanjanje namespace-a iz Pinecone Indeksa")
                    namespace = st.text_input(
                        "Unesite namespace : ",
                        help="Unesite namespace koji želite da obrišete (prazno za sve)",
                    )
                    moj_filter = st.text_input(
                        "Unesite filter za source (prazno za sve) : ",
                        help="Unesite filter za source (prazno za sve) : ",
                    )
                    nastavak = st.radio(
                        f"Da li ukloniti namespace {namespace} iz indeksa {index_name}",
                        ("Da", "Ne"),
                        help="Da li ukloniti namespace iz indeksa?",
                    )

                    submit_button = st.form_submit_button(
                        label="Submit",
                        help="Pokreće uklanjanje namespace-a iz indeksa",
                    )
                    if submit_button:
                        if not nastavak == "Da":
                            placeholder = st.empty()
                            with placeholder.container():
                                st.write("Izlazim iz programa")
                                time.sleep(2)
                                placeholder.empty()
                            sys.exit()
                        else:
                            with st.spinner("Sačekajte trenutak..."):
                            
                                # ukoliko zelimo da izbrisemo samo nekle recorde bazirano na meta data
                                try:
                                    if not moj_filter == "":
                                        index.delete(
                                            filter={"person_name": {"$in": [moj_filter]}},
                                            namespace=namespace,
                                        )
                                    #elif not namespace == "":
                                    else:
                                        index.delete(delete_all=True, namespace=namespace)
                                    # else:
                                    #     index.delete(delete_all=True)
                                except Exception as e:
                                    match = re.search(r'"message":"(.*?)"', str(e))

                                    if match:
                                        # Prints the extracted message
                                        st.error(f"Proverite ime indeksa koji ste uneli: {match.group(1)}")
                                    sys.exit()

                    
                                st.success("Uspešno obrisano")

    def create_node(self, id, label):
        # Method for creating a graph node
        ascii_label = unidecode.unidecode(label)  # Convert label to ASCII
        return f'  node [\n    id {id}\n    label "{ascii_label}"\n  ]\n'

    def create_edge(self, source, target, relation):
        # Method for creating a graph edge
        ascii_relation = unidecode.unidecode(relation)  # Convert relation to ASCII
        return f'  edge [\n    source {source}\n    target {target}\n    relation "{ascii_relation}"\n  ]\n'

    def create_graph_structure(self, data):
        # Method for creating the overall graph structure
        graph = "graph [\n  directed 1\n"
        nodes = {}
        edges = []
        graph_structure = "graph [\n  directed 1\n"
        node_id = 0
        for item in data:
        # Check and add the first element of the tuple as a node
            if item[0] not in nodes:
                nodes[item[0]] = node_id
                graph_structure += self.create_node(node_id, item[0])
                node_id += 1
        
            # Check and add the second element of the tuple as a node
            if item[1] not in nodes:
                nodes[item[1]] = node_id
                graph_structure += self.create_node(node_id, item[1])
                node_id += 1

            # Create an edge based on the relation (item[2])
            graph_structure += self.create_edge(nodes[item[0]], nodes[item[1]], item[2])

    # Close the graph structure
        graph_structure += "]"
        return graph_structure


    def create_graph(self, dokum):
        # Method for handling the graph creation process
        skinuto = False
        napisano = False
        slika_grafa = False
        if "skinuto" not in st.session_state:
            st.session_state.skinuto = False
        
        if st.session_state.skinuto == False:
            with st.spinner("Kreiram Graf, molim vas sacekajte..."):
                buffer = io.BytesIO()
                # Write data to the buffer
                buffer.write(dokum.getbuffer())
                # Get the byte data from the buffer
                byte_data = buffer.getvalue()
                all_text = byte_data.decode('utf-8')
                    
                # initialize graph engine
                index_creator = GraphIndexCreator(llm=ChatOpenAI(temperature=0, model=work_vars["names"]["openai_model"]))
                text = "\n".join(all_text.split("\n\n"))
            
                # create graph
                graph = index_creator.from_text(text)
                prikaz = graph.get_triples()
                with st.expander("Graf:"):
                    st.write(prikaz)
                # Don't forget to close the buffer when done
                buffer.close() 
                # save graph, with the same name different extension
                file_name = os.path.splitext(dokum.name)[0]
            
                graph_structure = self.create_graph_structure(prikaz)
                napisano = st.info(
                        f"Tekst je sačuvan u gml obliku kao {file_name}.gml, downloadujte ga na svoj računar"
                )
            
                skinut = st.download_button(
                    "Download GML",
                    data=graph_structure,
                    file_name=f"{file_name}.gml",
                    mime='ascii',
                )
                
                st.session_state.skinuto = True
                st.success(f"Graf je sačuvan kao {file_name}.gml")
                    
            # Load the GML file
        
        if st.session_state.skinuto:
            st.markdown("**Kada downloadujete graph file, učitajte GRAF ako zelite graficki prikaz**")
            slika_grafa = st.file_uploader(
                "Izaberite GRAF dokument", key="upload_graf", type=["gml"]
            )      
                
            if slika_grafa is not None:
                with io.open(slika_grafa.name, "wb") as file:
                        file.write(slika_grafa.getbuffer())
                
                G = nx.read_gml(slika_grafa.name)
                nx.draw(G, with_labels=True, node_size=200, font_size=5)
                st.pyplot(plt)  # Display the plot in Streamlit

    def read_uploaded_file(self, dokum, text_delimiter="space"):
        # Method for reading and processing the uploaded file
        with io.open(dokum.name, "wb") as file:
            file.write(dokum.getbuffer())

            
            if text_delimiter == "":
                text_delimiter = "\n\n"

            if ".pdf" in dokum.name:
                pdf_reader = PyPDF2.PdfReader(dokum)
                num_pages = len(pdf_reader.pages)
                text_content = ""

                for page in range(num_pages):
                    page_obj = pdf_reader.pages[page]
                    text_content += page_obj.extract_text()
                text_content = text_content.replace("•", "")
                text_content = re.sub(r"(?<=\b\w) (?=\w\b)", "", text_content)
                with io.open("temp.txt", "w", encoding="utf-8") as f:
                    f.write(text_content)

                loader = UnstructuredFileLoader("temp.txt", encoding="utf-8")
            else:
                # Creating a file loader object
                loader = UnstructuredFileLoader(dokum.name, encoding="utf-8")
            data = loader.load()
        return data


# in myfunc.retrievers.py
def SelfQueryPositive(upit, api_key=None, environment=None, index_name='neo-positive', namespace=None, openai_api_key=None, host=None):
    """
    Executes a query against a Pinecone vector database using specified parameters or environment variables. 
    The function initializes the Pinecone and OpenAI services, sets up the vector store and metadata, 
    and performs a query using a custom retriever based on the provided input 'upit'.
    
    It is used for self-query on metadata.

    Parameters:
    upit (str): The query input for retrieving relevant documents.
    api_key (str, optional): API key for Pinecone. Defaults to PINECONE_API_KEY from environment variables.
    environment (str, optional): Pinecone environment. Defaults to PINECONE_API_KEY from environment variables.
    index_name (str, optional): Name of the Pinecone index to use. Defaults to 'positive'.
    namespace (str, optional): Namespace for Pinecone index. Defaults to NAMESPACE from environment variables.
    openai_api_key (str, optional): OpenAI API key. Defaults to OPENAI_API_KEY from environment variables.

    Returns:
    str: A string containing the concatenated results from the query, with each document's metadata and content.
         In case of an exception, it returns the exception message.

    Note:
    The function is tailored to a specific use case involving Pinecone and OpenAI services. 
    It requires proper setup of these services and relevant environment variables.
    """
    
    # Use the passed values if available, otherwise default to environment variables
    api_key = api_key if api_key is not None else os.getenv('PINECONE_API_KEY')
    environment = environment if environment is not None else os.getenv('PINECONE_API_KEY')
    # index_name is already defaulted to 'positive'
    namespace = namespace if namespace is not None else os.getenv("NAMESPACE")
    openai_api_key = openai_api_key if openai_api_key is not None else os.getenv("OPENAI_API_KEY")
    host = host if host is not None else os.getenv("PINECONE_HOST")
   
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    # prilagoditi stvanim potrebama metadata
    metadata_field_info = [
        AttributeInfo(name="person_name",
                      description="The name of the person can be in the Serbian language like Miljan, Darko, Goran or similar", type="string"),
        AttributeInfo(
            name="topic", description="The topic of the document", type="string"),
        AttributeInfo(
            name="context", description="The Content of the document", type="string"),
        AttributeInfo(
            name="source", description="The source of the document", type="string"),
    ]

    # Define document content description
    document_content_description = "Content of the document"

    # Prilagoditi stvanom nazivu namespace-a
    vectorstore = LangPine.from_existing_index(
        index_name, embeddings, "context", namespace=namespace)

    # Initialize OpenAI embeddings and LLM
    llm = ChatOpenAI(model=work_vars["names"]["openai_model"], temperature=0)
    retriever = SelfQueryRetriever.from_llm(
        llm,
        vectorstore,
        document_content_description,
        metadata_field_info,
        enable_limit=True,
        verbose=True,
    )
    try:
        result = ""
        doc_result = retriever.get_relevant_documents(upit)
        for document in doc_result:
            result += document.metadata['person_name'] + " kaze: \n"
            result += document.page_content + "\n\n"
    except Exception as e:
        result = e
    
    return result
