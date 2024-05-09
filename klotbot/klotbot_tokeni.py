import mysql
import os
import streamlit as st
import uuid

from openai import OpenAI
from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder
from myfunc.asistenti import read_aad_username
from myfunc.mojafunkcija import positive_login
from myfunc.prompts import ConversationDatabase
# PromptDatabase
# from myfunc.retrievers import HybridQueryProcessor
from myfunc.varvars_dicts import work_vars
#from langchain_openai import ChatOpenAI
#from langchain_community.callbacks import get_openai_callback

import tiktoken
openai_api_key = os.environ.get("OPENAI_API_KEY")

client=OpenAI(api_key=openai_api_key)


_ = """
try:
    x = st.session_state.sys_ragbot
except:
    with PromptDatabase() as db:
        prompt_map = db.get_prompts_by_names(["rag_answer_reformat", "sys_ragbot"],[os.getenv("RAG_ANSWER_REFORMAT"), os.getenv("SYS_RAGBOT")])
        st.session_state.rag_answer_reformat = prompt_map.get("rag_answer_reformat", "You are helpful assistant")
        st.session_state.sys_ragbot = prompt_map.get("sys_ragbot", "You are helpful assistant")
"""

st.session_state.rag_answer_reformat = """"
Based on the context > 
            {context} 
            answer this question > 
            {prompt}
If you are asked for a list do not comment, only pass the list from the context. If you are asked for a list, just return the list from context if any.
"""
st.session_state.sys_ragbot = """Always write in Serbian language. Converse like you are an experienced sales person and consultant. Always try to offer a service from Positive doo, FOCUSING ON THE USER'S NEEDS AND HOW TO MEET THEM. TAILOR COMMUNICATION SO THAT IT IS FOCUSED ON SOLVING THE PROBLEM, RATHER THAN JUST LISTING THE AVAILABLE OPTIONS aka services. Emphasize that company is expert in every domain that it offers.  ALWAYS KEEP CONVERSATION ALIVE BY ASKING QUESTIONS because you want to make them realize that they have a problem or that they need something to expand and improve their business. Get to know their WEEK SPOTS. Then try selling our service based on what you came to conclusion that they need!! Do that through NON invasive conversation.  KEEP ASKING ADDITIONAL QUESTIONS TO IDENTIFY WHERE THEY NEED HELP AND WHERE OUR COMPANY HAS SPACE TO SELL THE SERVICE EVEN IF THEY DIDN’T EXPRESS ANY PARTICULAR PROBLEM AND THEY ARE JUST ASKING INFORMATIVE QUESTIONS ABOUT THE COMPANY!!!  TRY TO GET TO KNOW THEIR PAINS AND THEN OFFER COMPANY SOLUTION BUT THROUGH AFFIRMATIVE WAY.  !!! When listing or mentioning company services ALWAYS generate answer in a maner that describes how are they benefitial for them and their business, aka WHAT it will SOLVE!!!  Based on the conversation and client’s question, PROVIDE THE RIGHT LINK!  Keep answers CONCISE and precise. It is not in your interest to bore a customer with too long text!!! Try to keep it SHORT BUT FULLY INFORMATIVE! Remove all sentences that are not relevant to a topic discussed! Be friendly, creative and polite!!!  !!!  EVERYTIME YOU GENERATE the sentence HIGHLIGHT THE NAME OF THE COMPANY – Positive! Do that so it looks human aka natural! Put it in right case.  !!! Everytime it is your time to speak, start a sentence different way. Try not to repeat yourself!!! !!!  ############ Here is some context you can use when answering questions about Positive doo: Company is located in Danila Kiša 5, Novi Sad. Main focus of the company is on digital transformation, i.e. raising the efficiency of business by applying modern technologies. By improving business processes, company creates conditions for clients to fully utilize the benefits of our PAM business solution, and uses artificial intelligence (AI) in the process of automating work tasks.  WHO ARE WE? A team that initiates positive business changes ( 3P )  WHAT ARE WE DOING? We increase business results by using the most modern technologies   HOW WE DO IT? - WE IMPROVE EFFICIENCY - Business consulting - WE INCREASE EFFICIENCY - Digital tools - WE PROVIDE RELIABILITY - IT infrastructure (reliability consists of security, connectivity and continuity)  Main characters behind this company and its high quality services are Miljan Radanović owner and managing director and Darko Perović CEO.  ############  If you are asked about WORKING HOURS, YOU HAVE TO explicitly answer monday to friday 08-16h.  If a customer wants to book an appointment, highlight working hours and offer phone: 021/1234567. AVOID asking more questions like customers preferences when it comes to date and time.  If you are asked about GENERAL INFORMATION about the company, you HAVE TO GENERATE THE ANSWER BASED ON YOUR KNOWLEDGE and ALWAYS PROVIDE THIS LINK: https://positive.rs/o-nama/kompanija/ , stuff@positive.rs   If you are asked TECHNICAL question, you HAVE TO GENERATE THE ANSWER BASED ON YOUR KNOWLEDGE and ALWAYS PROVIDE LINK: podrska@positive.rs  If you are asked about the FEATURE OF A PRODUCT OR ABOUT ANY PARTICULAR SERVICE, you HAVE TO GENERATE THE ANSWER BASED ON YOUR KNOWLEDGE and ALWAYS PROVIDE LINK: prodaja@positive.rs"""

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
            model (str): The model to be used for embedding. Default is "text-embedding-3-large".

        Returns:
            list: The embedding vector of the given text.
            int: The number of prompt tokens used.
        """
        
        text = text.replace("\n", " ")
        prompt_tokens = client.embeddings.create(input=[text], model=model).usage.prompt_tokens
        result = client.embeddings.create(input=[text], model=model).data[0].embedding
       
        return result, prompt_tokens


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
        # Get embedding and unpack results
        dense, prompt_tokens = self.get_embedding(text=upit)

        # Use those results in another function call
        hdense, hsparse = self.hybrid_score_norm(
            sparse=BM25Encoder().fit([upit]).encode_queries(upit),
            dense=dense
        )

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
            if context:
                results.append({"page_content": context, "chunk": chunk, "source": source, "score": score})
        
        return results, prompt_tokens  # Also return prompt_tokens
       


    def process_query_results(self, upit):
        """
        Processes the query results and prompt tokens based on relevance score and formats them for a chat or dialogue system.
        Additionally, returns a list of scores for items that meet the score threshold.
        """
        tematika, prompt_tokens = self.hybrid_query(upit)  # Also retrieve prompt_tokens

        uk_teme = ""
        score_list = []
        for item in tematika:
             if item["score"] > self.score:
                uk_teme += item["page_content"] + "\n\n"
                score_list.append(item["score"])
        
        return uk_teme, score_list, prompt_tokens  # Return prompt_tokens along with other results
    
    def process_query_results_dict(self, upit):
        """
        Processes the query results and prompt tokens based on relevance score and formats them for a chat or dialogue system.
        
        """
        tematika, prompt_tokens = self.hybrid_query(upit)  # Also retrieve prompt_tokens

        score_list = []
        
        return tematika, score_list, prompt_tokens  # Return prompt_tokens along with other results

    def process_query_parent_results(self, upit):
        """
        Processes the query results and returns top result with source name, chunk number, and page content.
        It is used for parent-child queries.

        Args:
            upit (str): The original query text.
    
        Returns:
            tuple: Formatted string for chat prompt, source name, and chunk number.
        """
        tematika, prompt_tokens = self.hybrid_query(upit)

        # Check if there are any matches
        if not tematika:
            return "No results found", None, None

        # Extract information from the top result
        top_result = tematika[0]
        top_context = top_result.get('page_content', '')
        top_chunk = top_result.get('chunk')
        top_source = top_result.get('source')

        return top_context, top_source, top_chunk, prompt_tokens

     
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
        
        doc_result, prompt_tokens = self.hybrid_query(upit, top_k=top_k, filter=filter_criteria, namespace=self.namespace)
        result = "\n\n".join(document['page_content'] for document in doc_result)
    
        return result, prompt_tokens
        
       
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
        
        
        doc_result, prompt_tokens = self.hybrid_query(upit, top_k=top_k, filter=filter_criteria, namespace=self.namespace)

        # Sort the doc_result based on the 'chunk' value
        sorted_doc_result = sorted(doc_result, key=lambda document: document.get('chunk', float('inf')))

        # Generate the result string
        result = " ".join(document.get('page_content', '') for document in sorted_doc_result)
    
        return result, prompt_tokens







# tokenizacija za streaming
def num_tokens_from_messages(messages, model="gpt-4-turbo"):
    """
    Return the number of tokens used by a list of messages.
    """
    
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
    tokens_per_name = -1  # if there's a name, the role is omitted
    num_tokens = 0

    if type(messages) == list:
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    elif type(messages) == str:
        num_tokens += len(encoding.encode(messages))
    return num_tokens

processor = HybridQueryProcessor()

def main():
    if "username" not in st.session_state:
        st.session_state.username = "positive"
    if deployment_environment == "Azure":    
        st.session_state.username = read_aad_username()



    elif deployment_environment == "Windows":
        st.session_state.username = "lokal"
    elif deployment_environment == "Streamlit":
        st.session_state.username = username
        
    if "openai_model" not in st.session_state:
        st.session_state["openai_model"] = work_vars["names"]["openai_model"]
    if "azure_filename" not in st.session_state:
        st.session_state.azure_filename = "altass.csv"
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "app_name" not in st.session_state:
        st.session_state.app_name = "KlotBot"
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
    if "sys_ragbot" not in st.session_state:
        st.session_state.sys_ragbot = st.session_state.sys_ragbot
        st.session_state.messages[thread_name].append({'role': 'system', 'content': st.session_state.sys_ragbot})
    
    avatar_ai="bot.png"
    avatar_user = "user.webp"
    avatar_sys = "positivelogo.jpg"
   
    #with st.sidebar:
    #    st.info(f"Prijavljeni ste kao: {st.session_state.username}")

    if st.session_state.thread_id is None:
        st.info("Start a conversation by selecting a new or existing conversation.")
    else:
        current_thread_id = st.session_state.thread_id
        st.session_state.messages[current_thread_id].append({'role': 'system', 'content': st.session_state.sys_ragbot})
        #st.session_state.messages[current_thread_id] = [{'role': 'system', 'content': st.session_state.sys_ragbot}]
        # Check if there's an existing conversation in the session state
        if current_thread_id not in st.session_state.messages:
            # If not, initialize it with the conversation from the database or as an empty list
            with ConversationDatabase() as db:
                st.session_state.messages[current_thread_id] = db.query_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id) or []
            #st.session_state.messages[current_thread_id] = [{'role': 'system', 'content': st.session_state.sys_ragbot}]
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
    if prompt := st.chat_input("Kako vam mogu pomoci?"):
        # Original processing to generate complete_prompt
        context, scores, emb_prompt_tokens = processor.process_query_results(prompt)
        
        complete_prompt = st.session_state.rag_answer_reformat.format(prompt=prompt, context=context)
        # Append only the user's original prompt to the actual conversation log
        st.session_state.messages[current_thread_id].append({"role": "user", "content": prompt})
    
        # Display user prompt in the chat
        with st.chat_message("user", avatar=avatar_user):
            st.markdown(prompt)
        
        # Prepare a temporary messages list for generating the assistant's response
        temp_messages = st.session_state.messages[current_thread_id].copy()
        temp_messages[-1] = {"role": "user", "content": complete_prompt}  # Replace last message with enriched context
    

        system_message = {"role": "system", "content": st.session_state.sys_ragbot}
        user_message = {"role": "user", "content": prompt}
        ctx= {"role": "user", "content": complete_prompt}
        mem = {"role": "user", "content": str(st.session_state.messages[current_thread_id])}    # sumirati value od key content
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
        

        total_prompt = 0
        total_completion = 0
        total_emb_prompt = 0

        tiktoken_prompt = [system_message, user_message, ctx, mem]
        tiktoken_prompt_tokens = num_tokens_from_messages(tiktoken_prompt)
        tiktoken_completion_tokens = num_tokens_from_messages(full_response)
       
        total_emb_prompt += emb_prompt_tokens
        total_prompt += tiktoken_prompt_tokens
        total_completion += tiktoken_completion_tokens
        st.write(f"- Total embbeding tokens: {total_emb_prompt}")
        st.write(f"- Tiktoken Prompt tokens: {tiktoken_prompt_tokens}")
        st.write(f"- Tiktoken Completion tokens: {tiktoken_completion_tokens}")


        # Append assistant's response to the conversation
        st.session_state.messages[current_thread_id].append({"role": "assistant", "content": full_response})

        with ConversationDatabase() as db:
            db.update_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id, st.session_state.messages[current_thread_id])

deployment_environment = os.environ.get("DEPLOYMENT_ENVIRONMENT")

if deployment_environment == "Streamlit":
    name, authentication_status, username = positive_login(main, " ")
else:
    if __name__ == "__main__":
        main()
