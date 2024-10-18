import pytz
import re
import requests
import xml.etree.ElementTree as ET

from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_community.vectorstores import Pinecone as LangPine
from langchain_openai import OpenAIEmbeddings
from langchain_openai.chat_models import ChatOpenAI

from datetime import datetime, time
from openai import OpenAI
import os
from os import getenv
from pinecone_text.sparse import BM25Encoder
from typing import List, Dict, Any, Tuple, Union, Optional
from krembot_db import work_prompts
from krembot_auxiliary import load_matching_tools, connect_to_neo4j, connect_to_pinecone, neo4j_isinstance
from functools import lru_cache
mprompts = work_prompts()
client = OpenAI(api_key=getenv("OPENAI_API_KEY"))


all_tools = load_matching_tools(mprompts["choose_rag"])

def get_tool_response(prompt: str):
    """Function to cache external API tool responses if needed."""
    return client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Your one and only job is to determine the name of the tool that should be used to solve the user query. Do not return any other information."}, 
            {"role": "user", "content": prompt}
        ],
        tools=all_tools,
        temperature=0.0,
        tool_choice="required",
    )

def rag_tool_answer(prompt: str, x: int) -> Tuple[Any, str]:
    """
    Generates an answer using the RAG (Retrieval-Augmented Generation) tool based on the provided prompt and context.

    The function behavior varies depending on the 'APP_ID' environment variable. It utilizes different processors
    and tools to fetch and generate the appropriate response.

    Args:
        prompt (str): The input query or prompt for which an answer is to be generated.
        x (int): Additional parameter that may influence the processing logic, such as device selection.

    Returns:
        Tuple[Any, str]: A tuple containing the generated context or search results and the RAG tool used.
    """
    rag_tool = "ClientDirect"
    app_id = os.getenv("APP_ID")

    if app_id == "DentyBotR":
        processor = HybridQueryProcessor(namespace="denty-serviser", delfi_special=1)
        search_results = processor.process_query_results(upit=prompt, device=x)
        return search_results, rag_tool

    elif app_id == "DentyBotS":
        processor = HybridQueryProcessor(namespace="denty-komercijalista", delfi_special=1)
        context = processor.process_query_results(prompt)
        return context, rag_tool

    elif app_id == "ECDBot":
        processor = HybridQueryProcessor(namespace="ecd", delfi_special=1)
        return processor.process_query_results(prompt), rag_tool

    context = " "

    response = get_tool_response(prompt)
    assistant_message = response.choices[0].message
    finish_reason = response.choices[0].finish_reason

    if finish_reason == "tool_calls" or "stop":
        rag_tool = assistant_message.tool_calls[0].function.name
    else:
        rag_tool = "None chosen"

    processor_cache = {}

    def get_processor(cls, *args, **kwargs):
        key = (cls, args, tuple(sorted(kwargs.items())))
        if key not in processor_cache:
            processor_cache[key] = cls(*args, **kwargs)
        return processor_cache[key]

    # Use get_processor to cache class instances
    toplist_processor = get_processor(TopListFetcher, 'https://delfi.rs/api/pc-frontend-api/toplists')
    common_processor = get_processor(HybridQueryProcessor, namespace="delfi-podrska", delfi_special=1)
    bookstore_processor = get_processor(BookstoreSearcher)
    actions_processor = get_processor(ActionFetcher, 'https://delfi.rs/api/pc-frontend-api/actions-page')

    # Update your tool_processors dictionary
    tool_processors = {
        "Hybrid": lambda: common_processor.process_query_results(prompt),
        "Korice": lambda: SelfQueryDelfi(upit=mprompts["rag_self_query"] + prompt, namespace="korice"),
        "recomendation_based_on_attributes": lambda: graphp(prompt),
        "recomendation_based_on_description": lambda: pineg(prompt),
        "top_list": lambda: toplist_processor.decide_and_respond(prompt),
        "Orders": lambda: order_delfi(prompt),
        "Promotion": lambda: actions_processor.decide_and_respond(prompt),
        "Knjizare": lambda: bookstore_processor.return_all(),
        "Calendly": lambda: positive_calendly(prompt),
    }

    # Return the corresponding function for the chosen RAG tool
    context = tool_processors.get(rag_tool, lambda: "No tool chosen")()

    return context, rag_tool


def positive_calendly(y_no):
    calendly_url = "https://outlook.office365.com/owa/calendar/Sales@positive.rs/bookings/"
    return f"Naravno, sastanak sa nama možete zakazati na sledećem linku: <a href='{calendly_url}' target='_blank' class='custom-link'>ovde</a>"


class BookstoreSearcher:
    """
    A class to handle searching for bookstores and their working hours by either bookstore name or city.
    
    The class fetches data from an external API and caches the result to optimize repeated calls. It builds
    structured lists and dictionaries to support efficient searches and provides methods for searching
    based on input strings.
    """

    def __init__(self) -> None:
        """
        Initializes the BookstoreSearcher class.
        
        Currently, this class has no attributes that need to be initialized upon creation.
        """
        pass

    @staticmethod
    @lru_cache(maxsize=2)
    def get_bookstore_data() -> dict | None:
        """
        Fetches bookstore data from the API and caches the result.
        
        Uses the Least Recently Used (LRU) caching to store the most recent API result for optimization.
        Returns the API data if the request is successful, otherwise returns None.

        Returns:
        --------
        dict | None
            The fetched bookstore data in a dictionary format or None if the API call fails.
        """
        url = "https://delfi.rs/api/bookstores"
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json()['data']
        else:
            return None

    @classmethod
    @lru_cache(maxsize=2)
    def return_all(cls) -> str | None:
        """
        Builds and initializes the required data structures for storing bookstore and city information.
        
        This method:
        - Fetches bookstore data.
        - Extracts relevant information: bookstore names, working hours, and addresses.
        - Formats the result into a structured string of bookstores, their working hours, and addresses.

        Returns:
        --------
        str | None
            A formatted string listing all bookstores, their working hours, and addresses, or None if data is unavailable.
        """
        # Call get_bookstore_data() directly from the class using cls
        data = cls.get_bookstore_data()
        if data is None:
            return None

        a, b, c = zip(*[(bookstore['bookstoreName'], bookstore['workingHours'], bookstore['address']) for bookstore in data])
        result_string = '\n'.join(f"{name}: {hours}, {address}" for name, hours, address in zip(a, b, c))

        return result_string

    

def graphp(pitanje):
    """
    Processes a user's question, generates a Cypher query, executes it on a Neo4j database, 
    enriches the resulting data with descriptions from Pinecone, and formats the response.

    Parameters:
    pitanje (str): User's question in natural language related to the Neo4j database.

    Returns:
    list: A list of dictionaries representing enriched book data, each containing properties like 
          'title', 'category', 'author', and a description from Pinecone.
    
    The function consists of the following steps:
    1. Connects to the Neo4j database using the `connect_to_neo4j()` function.
    2. Defines a nested function `run_cypher_query()` to execute a Cypher query and clean the results.
    3. Generates a Cypher query from the user's question using the `generate_cypher_query()` function.
    4. Validates the generated Cypher query using `is_valid_cypher()`.
    5. Runs the Cypher query on the Neo4j database and retrieves book data.
    6. Enriches the retrieved book data with additional information fetched from an API.
    7. Fetches descriptions from Pinecone for the books using their 'oldProductId'.
    8. Combines book data with descriptions.
    9. Formats the final data and returns it as a formatted response.

    The function performs error handling to manage invalid Cypher queries or errors during data fetching.
    """
    driver = connect_to_neo4j()

    def run_cypher_query(driver, query):
        with driver.session() as session:
            results = session.run(query)
            cleaned_results = []
            max_characters=100000
            total_characters = 0
            max_record_length = 0
            min_record_length = float('inf')
            
            for record in results:
                cleaned_record = {}
                for key, value in record.items():
                    result_node = neo4j_isinstance(value)
                    if result_node:
                        properties = result_node
                    else:
                        # Ako je vrednost obična vrednost, samo je dodamo
                        properties = {key: value}
                    
                    for prop_key, prop_value in properties.items():
                        # Uklanjamo prefiks 'b.' ako postoji
                        new_key = prop_key.split('.')[-1]
                        cleaned_record[new_key] = prop_value
                
                record_length = sum(len(str(value)) for value in cleaned_record.values())
                if total_characters + record_length > max_characters:
                    break  # Prekida se ako dodavanje ovog zapisa prelazi maksimalan broj karaktera

                cleaned_results.append(cleaned_record)
                record_length = sum(len(str(value)) for value in cleaned_record.values())
                total_characters += record_length
                if record_length > max_record_length:
                    max_record_length = record_length
                if record_length < min_record_length:
                    min_record_length = record_length
        
        number_of_records = len(cleaned_results)
        # average_characters_per_record = total_characters / number_of_records if number_of_records > 0 else 0

        print(f"Number of records: {number_of_records}")
        print(f"Total number of characters: {total_characters}")

        return cleaned_results

    def generate_cypher_query(question):
        prompt = f"Translate the following user question into a Cypher query. Use the given structure of the database: {question}"
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.0,
            messages=[
                {
            "role": "system",
            "content": (
                "You are a helpful assistant that converts natural language questions into Cypher queries for a Neo4j database."
                "The database has 3 node types: Author, Book, Genre, and 2 relationship types: BELONGS_TO and WROTE."
                "Only Book nodes have properties: id, oldProductId, category, title, price, quantity, pages, and eBook."
                "All node and relationship names are capitalized (e.g., Author, Book, Genre, BELONGS_TO, WROTE)."
                "Genre names are also capitalized (e.g., Drama, Fantastika, Domaći pisci, Knjige za decu). Please ensure that the generated Cypher query uses these exact capitalizations."
                "Sometimes you will need to filter the data based on the category. Exsiting categories are: Knjiga, Strana knjiga, Gift, Film, Muzika, Udžbenik, Video igra, Dečija knjiga."
                "Ensure to include a condition to check that the quantity property of Book nodes is greater than 0 to ensure the books are in stock where this filter is plausable."
                "When writing the Cypher query, ensure that instead of '=' use CONTAINS, in order to return all items which contains the searched term."
                "When generating the Cypher query, ensure to handle inflected forms properly by converting all names to their nominative form. For example, if the user asks for books by 'Adrijana Čajkovskog,' the query should be generated for 'Adrijan Čajkovski,' ensuring that the search is performed using the base form of the author's name."
                "Additionally, ensure to normalize the search term by replacing non-diacritic characters with their diacritic equivalents. For instance, convert 'z' to 'ž', 's' to 'š', 'c' to 'ć' or 'č', and so on, so that the search returns accurate results even when the user omits Serbian diacritics."
                "When returning some properties of books, ensure to always return the oldProductId and the title too."
                "Ensure to limit the number of records returned to 6."
                "Hari Poter is stored as 'Harry Potter' in the database."
                "If the question contains 'top list' or 'na akciji', ignore these words and focus on the main part of the question."

                "Here is an example user question and the corresponding Cypher query: "
                "Example user question: 'Pronađi knjigu Da Vinčijev kod.' "
                "Cypher query: MATCH (b:Book) WHERE toLower(b.title) CONTAINS toLower('Da Vinčijev kod') AND b.quantity > 0 RETURN b LIMIT 6"

                "Example user question: 'O čemu se radi u knjizi Memoari jedne gejše?' "
                "Cypher query: MATCH (b:Book) WHERE toLower(b.title) CONTAINS toLower('Memoari jedne gejše') RETURN b LIMIT 6"

                "Example user question: 'Interesuje me knjiga Piramide.' "
                "Cypher query: MATCH (b:Book)-[:WROTE]-(a:Author) WHERE toLower(b.title) CONTAINS toLower('Piramide') AND b.quantity > 0 RETURN b.title AS title, b.oldProductId AS oldProductId, b.category AS category, a.name AS author LIMIT 6"
                
                "Example user question: 'Preporuci mi knjige istog žanra kao Krhotine.' "
                "Cypher query: MATCH (b:Book)-[:BELONGS_TO]->(g:Genre) WHERE toLower(b.title) CONTAINS toLower('Krhotine') WITH g MATCH (rec:Book)-[:BELONGS_TO]->(g)<-[:BELONGS_TO]-(b:Book) WHERE b.title CONTAINS 'Krhotine' AND rec.quantity > 0 MATCH (rec)-[:WROTE]-(a:Author) RETURN rec.title AS title, rec.oldProductId AS oldProductId, b.category AS category, a.name AS author, g.name AS genre LIMIT 6"

                "Example user question: 'Koja je cena za Autostoperski vodič kroz galaksiju?' "
                "Cypher query: MATCH (b:Book) WHERE toLower(b.title) CONTAINS toLower('Autostoperski vodič kroz galaksiju') AND b.quantity > 0 RETURN b.title AS title, b.oldProductId AS oldProductId, b.category AS category LIMIT 6"

                "Example user question: 'Da li imate anu karenjinu na stanju' "
                "Cypher query: MATCH (b:Book) WHERE toLower(b.title) CONTAINS toLower('Ana Karenjina') AND b.quantity > 0 RETURN b.title AS title, b.oldProductId AS oldProductId, b.category AS category LIMIT 6"

                "Example user question: 'Intresuju me fantastika. Preporuči mi neke knjige' "
                "Cypher query: MATCH (a:Author)-[:WROTE]->(b:Book)-[:BELONGS_TO]->(g:Genre {name: 'Fantastika'}) RETURN b, a.name, g.name LIMIT 6"
                
                "Example user question: 'Da li imate mobi dik na stanju, treba mi 27 komada?' "
                "Cypher query: MATCH (b:Book) WHERE toLower(b.title) CONTAINS toLower('Mobi Dik') AND b.quantity > 27 RETURN b.title AS title, b.quantity AS quantity, b.oldProductId AS oldProductId, b.category AS category LIMIT 6"
            
                "Example user question: 'preporuči mi knjige slične Oladi malo od Sare Najt' "
                "Cypher query: MATCH (b:Book)-[:WROTE]-(a:Author) WHERE toLower(b.title) CONTAINS toLower('Oladi malo') AND toLower(a.name) CONTAINS toLower('Sara Najt') WITH b MATCH (b)-[:BELONGS_TO]->(g:Genre) WITH g, b MATCH (rec:Book)-[:BELONGS_TO]->(g)<-[:BELONGS_TO]-(b) WHERE rec.quantity > 0 AND NOT toLower(rec.title) CONTAINS toLower('Oladi malo') WITH rec, COLLECT(DISTINCT g.name) AS genres MATCH (rec)-[:WROTE]-(recAuthor:Author) RETURN rec.title AS title, rec.oldProductId AS oldProductId, rec.category AS category, recAuthor.name AS author, genres AS genre LIMIT 6"
                
                "Example user question: 'daj mi preporuku za neku biografiju' "
                "Cypher query: MATCH (a:Author)-[:WROTE]->(b:Book)-[:BELONGS_TO]->(g:Genre) WHERE toLower(g.name) CONTAINS 'biografij' AND b.quantity > 0 RETURN b.title AS title, b.oldProductId AS oldProductId, b.category AS category, a.name AS author, g.name AS genre LIMIT 6"
                
                "Example user question: 'daj mi preporuku za nagradjene knjige' "
                "Cypher query: MATCH (a:Author)-[:WROTE]->(b:Book)-[:BELONGS_TO]->(g:Genre) WHERE toLower(g.name) CONTAINS 'nagrađen' AND toLower(g.name) CONTAINS 'knjig' AND b.quantity > 0 RETURN b.title AS title, b.oldProductId AS oldProductId, b.category AS category, a.name AS author, g.name AS genre LIMIT 6"
                
            )
        },
                {"role": "user", "content": prompt}
            ]
        )
        cypher_query = response.choices[0].message.content.strip()

        # Uklanjanje nepotrebnog teksta oko upita
        if '```cypher' in cypher_query:
            cypher_query = cypher_query.split('```cypher')[1].split('```')[0].strip()
        
        # Uklanjanje tačke ako je prisutna na kraju
        if cypher_query.endswith('.'):
            cypher_query = cypher_query[:-1].strip()

        return cypher_query


    def get_descriptions_from_pinecone(ids):
        # Initialize Pinecone
        # pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"), host=os.getenv("PINECONE_HOST"))
        index = connect_to_pinecone(x=0)
        # Fetch the vectors by IDs
        try:
            results = index.fetch(ids=ids, namespace="opisi")
        except Exception as e:
            print(f"Error fetching vectors: {e}")
            return {}
        descriptions = {}
        for id in ids:
            if id in results['vectors']:
                vector_data = results['vectors'][id]
                if 'metadata' in vector_data:
                    descriptions[id] = vector_data['metadata'].get('text', 'No description available')
                else:
                    descriptions[id] = 'Metadata not found in vector data.'
            else:
                descriptions[id] = 'Nemamo opis za ovaj artikal.'
        
        return descriptions
    

    def combine_data(book_data, descriptions):
        # print(f"Book Data: {book_data}")
        # print(f"Descriptions: {descriptions}")
        combined_data = []

        for book in book_data:        
            book_id = book.get('oldProductId', None)
            
            # Konvertuj book_id u string da bi se mogao porediti sa ključevima u descriptions
            book_id_str = str(book_id)

            description = descriptions.get(book_id_str, 'No description available')
            combined_entry = {**book, 'description': description}
            combined_data.append(combined_entry)
        
        # print(f"Combined Data: {combined_data}")
        return combined_data

    def is_valid_cypher(cypher_query):
        # Provera validnosti Cypher upita (osnovna provera)
        if not cypher_query or "MATCH" not in cypher_query.upper():
            return False
        return True
    
    cypher_query = generate_cypher_query(pitanje)
    print(f"Generated Cypher Query: {cypher_query}")
    
    if is_valid_cypher(cypher_query):
        try:
            book_data = run_cypher_query(driver, cypher_query)

            # print(f"Book Data: {book_data}")

            try:
                oldProductIds = [item['oldProductId'] for item in book_data]
                print(f"Old Product IDs: {oldProductIds}")
            except KeyError:
                print("Nema 'oldProductId'.")
                oldProductIds = []

            # Filtrirana lista koja će sadržati samo relevantne knjige
            filtered_book_data = []

            if not oldProductIds:
                filtered_book_data = book_data
                return filtered_book_data

            else:
                api_podaci = API_search(oldProductIds)
                # print(f"API Data: {api_podaci}")

                # Kreiranje mape id za brže pretraživanje
                products_info_map = {int(product['id']): product for product in api_podaci}

                # Iteracija kroz book_data i dodavanje relevantnih podataka
                for book in book_data:
                    old_id = book['oldProductId']
                    if old_id in products_info_map:
                        product = products_info_map[old_id]
                        # Spojite dva rečnika - podaci iz products_info_map ažuriraju book
                        book.update(products_info_map[old_id])
                        # Dodavanje knjige u filtriranu listu
                        filtered_book_data.append(book)

                    # print(f"Filtered Book Data: {filtered_book_data}")

                print("******Gotov api deo!!!")

                oldProductIds_str = [str(id) for id in oldProductIds]

                descriptionsDict = get_descriptions_from_pinecone(oldProductIds_str)
                # print("******Gotov Pinecone deo!!!")
                combined_data = combine_data(filtered_book_data, descriptionsDict)
                
                # return
                print(f"Combined Data: {combined_data}")
                return combined_data
        except Exception as e:
            print(f"Greška pri izvršavanju upita: {e}. Molimo pokušajte ponovo.")
    else:
        print("Traženi pojam nije jasan. Molimo pokušajte ponovo.")

def pineg(pitanje):
    """
    Processes a user's question, performs a dense vector search in Pinecone, fetches relevant data from an API and Neo4j, 
    combines the results, and displays them in a structured format.

    Parameters:
    pitanje (str): User's question in natural language.

    Returns:
    list: A list of combined results, each containing information from the API, Pinecone, and Neo4j database.
    
    The function consists of the following steps:
    1. Connects to the Pinecone index using `connect_to_pinecone(x=0)` and to the Neo4j database using `connect_to_neo4j()`.
    2. Defines a nested function `run_cypher_query()` to execute a Cypher query on Neo4j to retrieve book data including 
       authors and genres.
    3. Uses `get_embedding()` to create embeddings for a given text and `dense_query()` to perform a similarity search in Pinecone.
    4. Searches Pinecone using `search_pinecone()` for the initial query and `search_pinecone_second_set()` for secondary searches.
    5. Combines book data retrieved from Neo4j and API data using `combine_data()`.
    6. Displays the final combined data in a user-friendly format using `display_results()`.
    
    The function performs error handling to avoid processing duplicate entries, limits the number of API calls to a maximum 
    of three, and returns a list of combined results with enriched book information.
    """
    index = connect_to_pinecone(x=0)
    driver = connect_to_neo4j()

    def run_cypher_query(id):
        query = f"MATCH (b:Book)-[:WROTE]-(a:Author), (b)-[:BELONGS_TO]-(g:Genre) WHERE b.oldProductId = {id} AND b.quantity > 0 RETURN b, a.name AS author, g.name AS genre"
        with driver.session() as session:
            result = session.run(query)
            book_data = []
            for record in result:
                book_node = record['b']
                existing_book = next((book for book in book_data if book['id'] == book_node['id']), None)
                if existing_book:
                    # Proveri da li su 'author' i 'genre' liste, ako nisu, konvertuj ih
                    if not isinstance(existing_book['author'], list):
                        existing_book['author'] = [existing_book['author']]
                    if not isinstance(existing_book['genre'], list):
                        existing_book['genre'] = [existing_book['genre']]

                    # Ako postoji, dodaj autora i žanr u postojeće liste ako nisu već tamo
                    if record['author'] not in existing_book['author']:
                        existing_book['author'].append(record['author'])
                    if record['genre'] not in existing_book['genre']:
                        existing_book['genre'].append(record['genre'])
                else:
                    # Ako ne postoji, dodaj novi zapis sa autorom i žanrom kao liste
                    book_data.append({
                        'id': book_node['id'],
                        'oldProductId': book_node['oldProductId'],
                        'title': book_node['title'],
                        'author': record['author'],
                        'category': book_node['category'],
                        'genre': record['genre'],
                        'price': book_node['price'],
                        'quantity': book_node['quantity'],
                        'pages': book_node['pages'],
                        'eBook': book_node['eBook']
                })
            # print(f"Book Data: {book_data}")
            return book_data

    def get_embedding(text, model="text-embedding-3-large"):
        response = client.embeddings.create(
            input=[text],
            model=model
        ).data[0].embedding
        # print(f"Embedding Response: {response}")
        
        return response

    def dense_query(query, top_k, filter, namespace="opisi"):
        # Get embedding for the query
        dense = get_embedding(text=query)
        # print(f"Dense: {dense}")

        query_params = {
            'top_k': top_k,
            'vector': dense,
            'include_metadata': True,
            'filter': filter,
            'namespace': namespace
        }

        response = index.query(**query_params)

        matches = response.to_dict().get('matches', [])
        # print(f"Matches: {matches}")
        matches.sort(key=lambda x: x['score'], reverse=True)

        return matches

    def search_pinecone(query: str) -> List[Dict]:
        # Dobij embedding za query
        query_embedding = dense_query(query, top_k=4, filter=None)
        # print(f"Results: {query_embedding}")

        # Ekstraktuj id i text iz metapodataka rezultata
        matches = []
        for match in query_embedding:
            metadata = match['metadata']
            matches.append({
                'id': metadata['id'],
                'sec_id': int(metadata['sec_id']),
                'text': metadata['text'],
                'authors': metadata['authors'],
                'title': metadata['title']
            })
        
        return matches

    def search_pinecone_second_set(title: str, authors: str ) -> List[Dict]:
        # Dobij embedding za query
        query = "Nađi knjigu"
        filter = {"title" : {"$eq" : title}, "authors" : {"$in" : authors}}
        query_embedding_2 = dense_query(query, top_k=5, filter=filter)
        # print(f"Results: {query_embedding}")

        # Ekstraktuj id i text iz metapodataka rezultata
        matches = []
        for match in query_embedding_2:
            metadata = match['metadata']
            matches.append({
                'id': metadata['id'],
                'sec_id': int(metadata['sec_id']),
                'text': metadata['text'],
                'authors': metadata['authors'],
                'title': metadata['title']
            })
        
        # print(f"Matches: {matches}")
        return matches

    def combine_data(api_data, book_data, description):
        combined_data = []
        for book in book_data:
            # Pronađi odgovarajući unos u api_data na osnovu oldProductId
            matching_api_entry = next((item for item in api_data if str(item['id']) == str(book['oldProductId'])), None)
            
            if matching_api_entry:
                # Uzmemo samo potrebna polja iz book_data
                selected_book_data = {
                    'title': book.get('title'),
                    'author': book.get('author', []),
                    'category': book.get('category'),
                    'genre': book.get('genre', []),
                    'pages': book.get('pages'),
                    'eBook': book.get('eBook')
                }
                combined_entry = {
                    **selected_book_data,  # Dodaj samo potrebna polja iz book_data
                    **matching_api_entry,  # Dodaj sve podatke iz api_data
                    'description': description  # Dodaj opis
                }
            
            combined_data.append(combined_entry)

        return combined_data

    def display_results(combined_data):
        x = ""
        for data in combined_data:
            print(f"Data iz display_results: {data}")
            if "title" in data:
                print(f"Naziv: {data['title']}")
                x += f"Naslov: {data['title']}\n"
            if "author" in data:
                x += f"Autor: {data['author']}\n"
            if "category" in data:
                x += f"Kategorija: {data['category']}\n"
            if "genre" in data:
                x += f"Žanr: {(data['genre'])}\n"
            if "puna cena" in data:
                x += f"Cena: {data['puna cena']}\n"
            if "lager" in data:
                x += f"Dostupnost: {data['lager']}\n"
            if "pages" in data:
                x += f"Broj stranica: {data['pages']}\n"
            if "eBook" in data:
                x += f"eBook: {data['eBook']}\n"
            if "description" in data:
                x += f"Opis: {data['description']}\n"
            if "url" in data:
                x += f"Link: {data['url']}\n"
            if 'cena sa redovnim popustom' in data:
                x += f"Cena sa redovnim popustom: {data['cena sa redovnim popustom']}\n"
            if 'cena sa redovnim popustom na količinu' in data:
                x += f"Cena sa redovnim popustom na količinu: {data['cena sa redovnim popustom na količinu']}\n"
            if 'limit za količinski popust' in data:
                x += f"Limit za količinski popust: {data['limit za količinski popust']}\n"
            if 'cena sa premium popustom' in data:
                x += f"Cena sa premium popustom: {data['cena sa premium popustom']}\n"
            if 'cena sa premium popustom na količinu' in data:
                x += f"Cena sa premium popustom na količinu: {data['cena sa premium popustom na količinu']}\n"
            if 'limit za količinski premium popust' in data:
                x += f"Limit za količinski premium popust: {data['limit za količinski premium popust']}\n"
            x += "\n\n"

        return x

    search_results = search_pinecone(pitanje)
    print(f"Search Results: {search_results}")

    combined_results = []
    duplicate_filter = []
    counter = 0

    for result in search_results:
        print(f"Result: {result}")
        if result['sec_id'] in duplicate_filter:
            print(f"Duplicate Filter: {duplicate_filter}")
            continue
        else:
            if counter < 3:
                api_data = API_search([result['sec_id']])
                # print(f"API Data: {api_data}")
                if api_data:
                    counter += 1
                    print(f"Counter: {counter}")
                else:
                    print(f"API Data is empty for sec_id: {result['sec_id']}")
                    title = result['title']
                    authors = result['authors']
                    search_results_2 = search_pinecone_second_set(title, authors)
                    for result_2 in search_results_2:
                        if result_2['sec_id'] in duplicate_filter:
                            continue
                        else:
                            api_data = API_search([result_2['sec_id']])
                            # print(f"API Data 2: {api_data}")
                            if api_data:
                                counter += 1
                                # print(f"Counter 2: {counter}")
                                data = run_cypher_query(result_2['sec_id'])
                                # print(f"Data: {data}")

                                combined_data = combine_data(api_data, data, result_2['text'])
                                # print(f"Combined Data: {combined_data}")
                                duplicate_filter.append(result_2['sec_id'])
                                
                                combined_results.append(combined_data)
                            
                                # display_results(combined_data)
                                break

                    continue # Preskoči ako je api_data prazan

                data = run_cypher_query(result['sec_id'])
                # print(f"Data: {data}")

                combined_data = combine_data(api_data, data, result['text'])
                # print(f"Combined Data: {combined_data}")
                duplicate_filter.append(result['sec_id'])
                # print(f"Duplicate Filter: {duplicate_filter}")
                
                combined_results.extend(combined_data)
                # print(f"Combined Results: {combined_results}")
                
                
                # return display_results(combined_data)
            else:
                break
    display_results(combined_data)
    # print(f"Combined Results: {combined_results}")
    # print(f"Display Results: {display_results(combined_results)}")
    return combined_results


class TopListFetcher:
    def __init__(self, api_url):
        """
        Inicijalizuje instancu klase sa zadatim URL-om API-ja.

        Args:
            api_url (str): URL API-ja odakle će se preuzimati podaci.
        """
        self.api_url = api_url
        self.today = datetime.now()
        self.unique_actions = set()

    def fetch_data(self):
        """
        Preuzima podatke sa API-ja.

        Returns:
            dict: Sirovi podaci preuzeti sa API-ja u JSON formatu.
            None: Vraća None ako dođe do greške prilikom preuzimanja podataka.
        """
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Greška pri povezivanju sa API-jem: {e}")
            data = None
        return data

    def get_first_items(self):
        """
        Pribavlja i prikazuje prve proizvode iz API-ja "toplists".

        Ova funkcija šalje GET zahtev ka API-ju i vraća najviše šest artikala iz sekcija
        sadržanih u odgovoru. Za svaki artikal prikazuje sledeće informacije:
        - Naslov
        - Autor(i)
        - Žanr(ovi)
        - eBook
        - Link ka stranici artikla

        Parameters:
        -----------
        self : object
            Referenca na instancu klase (ako je metoda deo klase).

        Returns: 
        --------
        list of dict
            Lista rečnika, gde svaki rečnik sadrži sledeće ključeve:
            - 'title': Naslov artikla (str)
            - 'authors': Lista autora (list of str)
            - 'genres': Lista žanrova (list of str)
            - 'eBook': Informacija o dostupnosti u eBook formatu (bool)
            - 'url': Link ka stranici artikla (str)
        """
        # URL API-ja koji koristite
        api_url = "https://delfi.rs/api/pc-frontend-api/toplists"

        try:
            # Slanje GET zahteva prema API-ju
            response = requests.get(api_url)
            response.raise_for_status()  # Provera uspešnosti zahteva

            print("Konekcija sa API-jem uspešno ostvarena!")
            
            # Parsiranje odgovora iz JSON formata
            data = response.json()

            items = []  # Lista za skladištenje rečnika artikala
            item_count = 0  # Brojač za artikle
            
            for item in data.get('data', {}).get('sections', []):
                # print("Iteriramo kroz sekciju:", item)  # Dodato za proveru
                for product in item.get('content', {}).get('products', []):
                    # print("Pronađen proizvod u kategoriji:", category)
                    title = product.get('title', 'Nema naslova')
                    authors = [author.get('authorName', 'Nepoznat autor') for author in product.get('authors', [])]
                    genres = [genre.get('genreName', 'Nepoznat žanr') for genre in product.get('genres', [])]
                    eBook = product.get('eBook')
                    category = product['category'].lower().replace(' ', '_')
                    oldProductId = product.get('oldProductId', 'Nepoznat ID')
                    url = f"https://delfi.rs/{category}/{oldProductId}"
                    # opis = product.get('description')
                    
                    # Kreiranje rečnika za artikal
                    item_dict = {
                        'title': title,
                        'authors': authors,
                        'genres': genres,
                        'eBook': eBook,
                        'url': url
                    }

                    # Dodavanje rečnika u listu
                    items.append(item_dict)

                    item_count += 1
                    if item_count >= 6:
                        break

                if item_count >= 6:
                    break

            return items
        
        except requests.exceptions.RequestException as e:
            print(f"Došlo je do greške prilikom povezivanja sa API-jem: {e}")
            return []

    def get_items_by_category(self, category):
        """
        Pribavlja i vraća listu proizvoda iz određene kategorije sa API-ja "toplists".

        Ova funkcija šalje GET zahtev ka API-ju i vraća sve artikle koji pripadaju zadatoj kategoriji. 
        Za svaki artikal vraća sledeće informacije:
        - Naslov
        - Autor(i)
        - Žanr(ovi)
        - eBook
        - Link ka stranici artikla

        Parameters:
        -----------
        self : object
            Referenca na instancu klase (ako je metoda deo klase).
        
        category : str
            Ime kategorije za koju se pretražuju artikli (npr. "knjige").
            Naziv kategorije nije osetljiv na velika i mala slova.

        Returns:
        --------
        list of dict
            Lista rečnika, gde svaki rečnik sadrži sledeće ključeve:
            - 'title': Naslov artikla (str)
            - 'authors': Lista autora (list of str)
            - 'genres': Lista žanrova (list of str)
            - 'eBook': Informacija o dostupnosti u eBook formatu (bool)
            - 'url': Link ka stranici artikla (str)
        
        Raises:
        -------
        requests.exceptions.RequestException
            Ako dođe do greške prilikom slanja zahteva ka API-ju.
        """
        api_url = "https://delfi.rs/api/pc-frontend-api/toplists"
        category_name_lower = category.lower()
        try:
            # Slanje GET zahteva prema API-ju
            response = requests.get(api_url)
            response.raise_for_status()  # Provera uspešnosti zahteva

            print("Konekcija sa API-jem uspešno ostvarena!")
            
            # Parsiranje odgovora iz JSON formata
            data = response.json()

            items = []  # Lista za skladištenje rečnika artikala
            
            for item in data.get('data', {}).get('sections', []):
                # print("Iteriramo kroz sekciju:", item)  # Dodato za proveru
                for product in item.get('content', {}).get('products', []):
                    # print("Proizvod:", product)  # Dodato za proveru
                    if product.get('category').lower() == category_name_lower:
                        # print("Pronađen proizvod u kategoriji:", category)
                        title = product.get('title', 'Nema naslova')
                        authors = [author.get('authorName', 'Nepoznat autor') for author in product.get('authors', [])]
                        genres = [genre.get('genreName', 'Nepoznat žanr') for genre in product.get('genres', [])]
                        eBook = product.get('eBook')
                        category = product['category'].lower().replace(' ', '_')
                        oldProductId = product.get('oldProductId', 'Nepoznat ID')
                        url = f"https://delfi.rs/{category}/{oldProductId}"
                        # opis = product.get('description')
                        
                        # Kreiranje rečnika za artikal
                        item_dict = {
                            'title': title,
                            'authors': authors,
                            'genres': genres,
                            'eBook': eBook,
                            'url': url
                        }

                        # Dodavanje rečnika u listu
                        items.append(item_dict)

            return items
        
        except requests.exceptions.RequestException as e:
            print(f"Došlo je do greške prilikom povezivanja sa API-jem: {e}")
            return []

    def get_items_by_genre(self, genre):
        """
        Pribavlja i vraća listu proizvoda iz određene kategorije sa API-ja "toplists".

        Ova funkcija šalje GET zahtev ka API-ju i vraća sve artikle koji pripadaju zadatoj kategoriji. 
        Za svaki artikal vraća sledeće informacije:
        - Naslov
        - Autor(i)
        - Žanr(ovi)
        - eBook
        - Link ka stranici artikla

        Parameters:
        -----------
        self : object
            Referenca na instancu klase (ako je metoda deo klase).
        
        genre : str
            Ime žanra za koju se pretražuju artikli (npr. "drama").
            Naziv žanra nije osetljiv na velika i mala slova.

        Returns:
        --------
        list of dict
            Lista rečnika, gde svaki rečnik sadrži sledeće ključeve:
            - 'title': Naslov artikla (str)
            - 'authors': Lista autora (list of str)
            - 'genres': Lista žanrova (list of str)
            - 'eBook': Informacija o dostupnosti u eBook formatu (bool)
            - 'url': Link ka stranici artikla (str)
        
        Raises:
        -------
        requests.exceptions.RequestException
            Ako dođe do greške prilikom slanja zahteva ka API-ju.
        """

        api_url = "https://delfi.rs/api/pc-frontend-api/toplists"
        genre_name_lower = genre.lower()
        try:
            # Slanje GET zahteva prema API-ju
            response = requests.get(api_url)
            response.raise_for_status()  # Provera uspešnosti zahteva

            print("Konekcija sa API-jem uspešno ostvarena!")
            
            # Parsiranje odgovora iz JSON formata
            data = response.json()

            items = []  # Lista za skladištenje rečnika artikala
            
            for item in data.get('data', {}).get('sections', []):
                # print("Iteriramo kroz sekciju:", item)  # Dodato za proveru
                for product in item.get('content', {}).get('products', []):
                    # Lista žanrova
                    genres = [genre.get('genreName', 'Nepoznat žanr').lower() for genre in product.get('genres', [])]
                
                    # Provera da li bilo koji žanr odgovara zadatom
                    if any(genre_name_lower in g for g in genres):
                        title = product.get('title', 'Nema naslova')
                        authors = [author.get('authorName', 'Nepoznat autor') for author in product.get('authors', [])]
                        genres = [genre.get('genreName', 'Nepoznat žanr') for genre in product.get('genres', [])]
                        eBook = product.get('eBook')
                        category = product['category'].lower().replace(' ', '_')
                        oldProductId = product.get('oldProductId', 'Nepoznat ID')
                        url = f"https://delfi.rs/{category}/{oldProductId}"
                        # opis = product.get('description')

                        # Kreiranje rečnika za artikal
                        item_dict = {
                            'title': title,
                            'authors': authors,
                            'genres': genres,
                            'eBook': eBook,
                            'url': url
                        }

                        # Dodavanje rečnika u listu
                        items.append(item_dict)

            return items
        
        except requests.exceptions.RequestException as e:
            print(f"Došlo je do greške prilikom povezivanja sa API-jem: {e}")
            return []
        
    def get_items_by_author(self, author):
        """
        Pribavlja i vraća listu proizvoda iz određene kategorije sa API-ja "toplists".

        Ova funkcija šalje GET zahtev ka API-ju i vraća sve artikle koji pripadaju zadatoj kategoriji. 
        Za svaki artikal vraća sledeće informacije:
        - Naslov
        - Autor(i)
        - Žanr(ovi)
        - eBook
        - Link ka stranici artikla

        Parameters:
        -----------
        self : object
            Referenca na instancu klase (ako je metoda deo klase).
        
        author : str
            Ime autora za kog se pretražuju artikli (npr. "Ivo Andrić").
            Ime autora nije osetljiv na velika i mala slova.

        Returns:
        --------
        list of dict
            Lista rečnika, gde svaki rečnik sadrži sledeće ključeve:
            - 'title': Naslov artikla (str)
            - 'authors': Lista autora (list of str)
            - 'genres': Lista žanrova (list of str)
            - 'eBook': Informacija o dostupnosti u eBook formatu (bool)
            - 'url': Link ka stranici artikla (str)
        
        Raises:
        -------
        requests.exceptions.RequestException
            Ako dođe do greške prilikom slanja zahteva ka API-ju.
        """
        api_url = "https://delfi.rs/api/pc-frontend-api/toplists"
        author_name_lower = author.lower()
        try:
            # Slanje GET zahteva prema API-ju
            response = requests.get(api_url)
            response.raise_for_status()  # Provera uspešnosti zahteva

            print("Konekcija sa API-jem uspešno ostvarena!")
            
            # Parsiranje odgovora iz JSON formata
            data = response.json()

            items = []  # Lista za skladištenje rečnika artikala
            
            for item in data.get('data', {}).get('sections', []):
                # print("Iteriramo kroz sekciju:", item)  # Dodato za proveru
                for product in item.get('content', {}).get('products', []):
                    # Lista žanrova
                    authors = [author.get('authorName', 'Nepoznat autor').lower() for author in product.get('authors', [])]
                
                    # Provera da li bilo koji žanr odgovara zadatom
                    if author_name_lower in authors:
                        title = product.get('title', 'Nema naslova')
                        authors = [author.get('authorName', 'Nepoznat autor') for author in product.get('authors', [])]
                        genres = [genre.get('genreName', 'Nepoznat žanr') for genre in product.get('genres', [])]
                        eBook = product.get('eBook')
                        category = product['category'].lower().replace(' ', '_')
                        oldProductId = product.get('oldProductId', 'Nepoznat ID')
                        url = f"https://delfi.rs/{category}/{oldProductId}"
                        # opis = product.get('description')
                        
                        # Kreiranje rečnika za artikal
                        item_dict = {
                            'title': title,
                            'authors': authors,
                            'genres': genres,
                            'eBook': eBook,
                            'url': url
                        }

                        # Dodavanje rečnika u listu
                        items.append(item_dict)
            return items
        
        except requests.exceptions.RequestException as e:
            print(f"Došlo je do greške prilikom povezivanja sa API-jem: {e}")
            return []

    def decide_and_respond(self, question):
        """
        Funkcija koja koristi LLM da odluči koja metoda će se koristiti na osnovu pitanja korisnika.
        """

        tools = [
        {
            "type": "function",
            "function": {
                "name": "getFistItems",
                "description": "",
                "parameters": {
                    "type": "object",
                    "properties": {
                    "query": {
                        "type": "string",
                        "description": "If the user asks for most popular products."
                    }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                },
                "strict": True
            }
        },
        {
            "type": "function",
            "function": {
                "name": "fetchTopListByCategory",
                "description": "",
                "parameters": {
                    "type": "object",
                    "properties": {
                    "query": {
                        "type": "string",
                        "description": "If the user asks about products by category."
                    }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                },
                "strict": True
            }
        },
        {
            "type": "function",
            "function": {
                "name": "fetchTopListByGenre",
                "description": "",
                "parameters": {
                    "type": "object",
                    "properties": {
                    "query": {
                        "type": "string",
                        "description": "If the user asks about products by genre."
                    }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                },
                "strict": True
            }
        },
        {
            "type": "function",
            "function": {
                "name": "fetchTopListByAuthor",
                "description": "",
                "parameters": {
                    "type": "object",
                    "properties": {
                    "query": {
                        "type": "string",
                        "description": "If the user asks about products by the author."
                    }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }
        ]

        response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Your one and only job is to determine the name of the tool that should be used to solve the user query. Do not return any other information."
 
                            "Here is an example: "
                            "Example user question: 'koje knjige su na akciji Nauci kroz igru' "
                            "Tool to use: 'books'"
 
                            "Here is an example: "
                            "Example user question: 'koji naslovi domacih izdavaca su na akciji' "
                            "Tool to use: 'books'"
                        )
                    },
                    {"role": "user", "content": question}
                ],
                tools=tools,
                temperature=0.0,
                tool_choice="required",
            )
        assistant_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if finish_reason == "tool_calls" or "stop":
            decision = assistant_message.tool_calls[0].function.name
        else:
            decision = "Warning: No function was called"

        print(f"Odluka: {decision}")

        if decision == 'getFistItems':
            # Korisnik pita za popularne knjige
            return self.get_first_items()
        
        elif decision == 'fetchTopListByCategory':
            # Korisnik pita za knjige po kategoriji
            prompt_for_category = f"The user question: {question}"
            category_name_response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant. The user is asking about products for a specific category."
                            "You need to extract the specific category name from the question based on this list: knjiga, film, muzika, strana knjiga, gift, udžbenik, video igra."
                            "Return only the name of the category in order to the function can filter the data for that category. ensure to handle inflected forms properly by converting all names to their nominative form."
                        
                        )
                    },
                    {"role": "user", "content": prompt_for_category}
                ]
            )
            category_name = category_name_response.choices[0].message.content.strip()
            print(f"naziv kategorije: ", category_name)
            answer = self.get_items_by_category(category_name)
            if not answer:
                answer = graphp(question)
            return answer

        elif decision == 'fetchTopListByGenre':
            # Korisnik pita za knjige po žanru
            prompt_for_genre = f"The user question: {question}"
            genre_name_response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant. The user is asking about products for a specific genre."
                            "You need to extract the specific genre name from the question, ensuring to handle inflected forms by converting them to their nominative form."
                            "Normalize the search term by replacing non-diacritic characters with their diacritic equivalents. For instance, convert 'z' to 'ž', 's' to 'š', 'c' to 'ć' or 'č', and so on, so that the search returns accurate results even when diacritics are omitted."
                            "Additionally, ensure that the genre contains the base form of the word. For example, if the user asks for 'autobiografije,' the search should be conducted using 'autobiografij' to account for both singular and plural forms."
                            
                            "Here is an example: "
                            "Example user question: 'koje E-knjige su na top listi' "
                            "Search with: 'e-knjig'"

                            "Example user question: 'daj knjige iz oblasti popularne psihologije' "
                            "Search with: 'popularna psihologij'"

                            "Example user question: 'daj mi preporuku za neke nagradjene knjige' "
                            "Search with: 'nagrađen'"

                            "Example user question: 'preporuci mi neke knjige za decu' "
                            "Search with: 'knjige za decu'"

                            "Return only the name of the genre in order to the function can filter the data for that genre."
                        )
                    },
                    {"role": "user", "content": prompt_for_genre}
                ]
            )
            genre_name = genre_name_response.choices[0].message.content.strip()
            print(f"naziv žanra: ", genre_name)
            answer = self.get_items_by_genre(genre_name)
            if not answer:
                answer = graphp(question)
            return answer

        elif decision == 'fetchTopListByAuthor':
            # Korisnik pita za knjige po autoru
            prompt_for_author = f"The user question: {question}"
            author_name_response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.0,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. The user is asking about products for a specific author. You need to extract the author name from the question. Return only the author name in order to the function can filter the data for that author."},
                    {"role": "user", "content": prompt_for_author}
                ]
            )    
            author_name = author_name_response.choices[0].message.content.strip()
            print(f"naziv autora: ", author_name)
            answer = self.get_items_by_author(author_name)
            if not answer:
                answer = graphp(question)
            return answer

        else:
            return {"error": "Nije moguće odlučiti šta korisnik želi."}


def API_search_2(order_ids: List[str]) -> Union[List[Dict[str, Any]], str]:
    """
    Retrieves and processes information for a list of order IDs.

    This function fetches detailed information for each order ID by making API requests to an external service.
    It parses the JSON responses to extract relevant order details such as ID, type, status, delivery service,
    delivery time, payment type, package status, and order item type. Additionally, it collects tracking codes
    and performs an auxiliary search if tracking codes are available.

    Args:
        order_ids (List[str]): A list of order IDs for which information is to be retrieved.

    Returns:
        List[Dict[str, Any]] or str: A list of dictionaries containing the extracted order information. If an error
                                     occurs during the retrieval process, it returns an error message indicating that
                                     no orders were found for the given IDs.
    """
    def get_order_info(order_id):
        url = f"http://185.22.145.64:3003/api/order-info/{order_id}"
        headers = {
            'x-api-key': getenv("DELFI_ORDER_API_KEY")
        }
        return requests.get(url, headers=headers).json()
    tc = []
    # Function to parse the JSON response and extract required fields
    def parse_order_info(json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses the JSON data for a single order and extracts relevant order information.

        Args:
            json_data (Dict[str, Any]): The JSON data received from the order information API.

        Returns:
            Dict[str, Any]: A dictionary containing extracted order details such as:
                - id (str): The unique identifier of the order.
                - type (str): The type of the order.
                - status (str): The current status of the order.
                - delivery_service (str): The delivery service used for the order.
                - delivery_time (str): The estimated delivery time.
                - payment_type (str): The type of payment used.
                - package_status (str): The status of the package.
                - order_item_type (str): The type of items in the order.
        """
        order_info = {}
        if 'orderData' in json_data:
            data = json_data['orderData']
            # Extract required fields from the order info
            order_info['id'] = data.get('id', 'N/A')
            order_info['type'] = data.get('type', 'N/A')
            order_info['status'] = data.get('status', 'N/A')
            order_info['delivery_service'] = data.get('delivery_service', 'N/A')
            order_info['delivery_time'] = data.get('delivery_time', 'N/A')
            order_info['payment_type'] = data.get('payment_detail', {}).get('payment_type', 'N/A')
            tc.append(data.get('tracking_codes', None))
            # Extract package info if available
            packages = data.get('packages', [])
            if packages:
                package_status = packages[0].get('status', 'N/A')
                order_info['package_status'] = package_status

            # Extract order items info if available
            order_items = data.get('order_items', [])
            if order_items:
                item_type = order_items[0].get('type', 'N/A')
                order_info['order_item_type'] = item_type

        return order_info

    # Main function to get info for a list of order IDs
    def get_multiple_orders_info(order_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieves and processes information for multiple order IDs.

        Args:
            order_ids (List[str]): A list of order IDs for which information is to be retrieved.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each containing details of an order, including:
                - id (str): The unique identifier of the order.
                - type (str): The type of the order.
                - status (str): The current status of the order.
                - delivery_service (str): The delivery service used for the order.
                - delivery_time (str): The estimated delivery time.
                - payment_type (str): The type of payment used.
                - package_status (str): The status of the package.
                - order_item_type (str): The type of items in the order.
            If an error occurs during retrieval, the list may contain an error message string.
        """
        orders_info = []
        for order_id in order_ids:
            json_data = get_order_info(order_id)
            order_info = parse_order_info(json_data)
            if order_info:
                orders_info.append(order_info)
        return orders_info

    # Retrieve order information for all provided order IDs
    try:
        orders_info = get_multiple_orders_info(order_ids)
    except Exception as e:
        print(f"Error retrieving order information: {e}")
        orders_info = "No orders found for the given IDs."
    tc = [x for x in tc if x is not None]
    if len(tc) > 0:
        if "," in tc[0]:
            tc = tc[0].split(",")
            for i in range(len(tc)):
                print(tc[i])
                orders_info.append(API_search_aks([tc[i]]))
        else:
            orders_info.append(API_search_aks(tc))
    final_output = orders_message(orders_info)
    return f"Prosledi samo naredni tekst: {final_output}" 


def orders_message(orders_info: Union[List[Dict[str, Any]], str]) -> str:
    """
    Maps the values of the order details to a human-readable message.
    """
    def check_if_working_hours():
        belgrade_timezone = pytz.timezone('Europe/Belgrade')
        current_time = datetime.now(belgrade_timezone)

        start_time = time(9, 0)
        end_time = time(16, 45)

        if start_time <= current_time.time() <= end_time:
            return True
        else:
            return False


    def aks_odgovori(orders_dict):
        def extract_timestamp(date_string):
            timestamp = int(date_string[6:-2]) / 1000  # Extract and convert milliseconds to seconds
            return datetime.fromtimestamp(timestamp)

        # Sort the status changes by timestamp
        sorted_status_changes = sorted(orders_dict[0]['status_changes'], key=lambda x: extract_timestamp(x['Vreme']))

        # Get the last (most recent) status description
        most_recent_status = sorted_status_changes[-1]['StatusOpis']
        print(111111111111, most_recent_status)
        reply2 = ""
        if most_recent_status == "Kreiranje VIP Naloga":
            reply2 = """
            Vaša porudžbina je spakovana i spremna za slanje. 
            """
        elif most_recent_status == "Preuzimanje Posiljke":
            reply2 = """
            Vaša porudžbina je poslata i biće isporučena u skladu sa rokom za dostavu. 
            """
        elif most_recent_status == "Ulazak Na Sortirnu Traku":
            reply2 = """
            Vaša porudžbina je poslata i biće isporučena u skladu sa rokom za dostavu. 
            """
        elif most_recent_status in ["Utovar U Linijski Kamion", "Izlaz iz Magacina"]:
            reply2 = """
            Vaša porudžbina je poslata i biće isporučena u skladu sa rokom za dostavu.
            """
        elif most_recent_status == "Posiljka Na Isporuci":
            reply2 = """
            Vaša porudžbina je poslata i prema podacima koje smo dobili od kurirske službe, nalazi se na isporuci. 
            """
        elif most_recent_status in ["Otkaz isporuke", "Vraceno u magacin"]:
            reply2 = """
            Vaša porudžbina je poslata, ali prema podacima koje smo dobili od kurirske službe, isporuka je otkazana. 
            Prosledićemo urgenciju za isporuku, molimo Vas da proverite da li su podaci sa potvrde o porudžbini ispravni kako bi kurir kontaktirao sa Vama - 
            u ovim situacijama moramo imati povratnu informaciju o prepisci kako bismo poslali urgenciju kurirskoj službi.
            """
        elif most_recent_status == "Unet povrat":
            reply2 = """
            Vaša porudžbina je poslata, ali prema podacima koje smo dobili od kurirske službe, nije bila moguća isporuka, usled čega je paket vraćen pošiljaocu. 
            Ukoliko želite, možemo ponovo poslati porudžbinu, samo je potrebno da nam pošaljete mejl na na imejl-adresu podrska@delfi.rs. 
            """
        else:
            "Posiljka je isporucena!"
        return reply2

    reply = ""
    orders_info2 = orders_info[0]
    if orders_info2["status"] in ["finished", "paymentCompleted"] and orders_info2["package_status"] == "INVITATION_SENT":
        reply = aks_odgovori(orders_info[1])

    elif orders_info2["status"] == "finished" and orders_info2["payment_type"] == "ADMINISTRATIVE _BAN":
        reply = """
        Vaša porudžbina je uspešno kreirana i trenutno se nalazi u fazi obrade.
        Kako bi porudžbina bila poslata, potrebno je da pošaljete popunjen formular, koji je poslat u okviru potvrde porudžbine, na adresu Kralja Petra 45, V sprat.
        Molimo Vas da kontaktirate sa nama u vezi sa svim dodatnim pitanjima na broj telefona:  011/7155-042. Radno vreme našeg korisničkog servisa: ponedeljak-petak (8-17 sati)
        """

    elif orders_info2["status"] == "finished":
        reply = """
        Vaša porudžbina je uspešno kreirana i trenutno se nalazi u fazi obrade. Isporuka će biti realizovana u skladu sa Uslovima korišćenja. 

        Očekivani rok isporuke je 2-5 radnih dana. 
        """
    elif orders_info2["status"] in ["readyForOnlinePayment", "waitingForFinalOnlinePaymentStatus"]:
        reply = """
        Vaša porudžbina se trenutno nalazi u procesu kreiranja.
        Ukoliko Vam u narednih 30 minuta ne stigne potvrda o kupovini na imejl adresu koju ste ostavili prilikom kreiranja porudžbine molimo Vas da nas kontaktirate slanjem upita na podrska@delfi.rs 
        ili pozivom na broj telefona našeg korisničkog servisa 011/7155-042. Radno vreme našeg korisničkog servisa: ponedeljak-petak (8-17 sati).
        """
    elif orders_info2["status"] == "ebookSuccessfullyAdded":
        reply = """
        Vaša porudžbina je uspešno kreirana i kupljene naslove možete pronaći u sekciji Moje knjige na Vašem nalogu u okviru EDEN Books aplikacije.

        Ukoliko Vam je potrebna dodatna asistencija molim Vas da nam pošaljete upit na mail podrska@delfi.rs.
        """
    elif orders_info2["status"] == "canceled":
        reply = """
        Vaša porudžbina nije uspešno realizovana.
        Molimo Vas da nam pošaljete potvrdu o uplati na imejl adresu podrska@delfi.rs ukoliko su sredstva povučena sa Vašeg računa, a da bismo rešili situaciju u najkraćem mogućem roku.
        """
    elif orders_info2["status"] == "paymentCompleted" and orders_info2["delivery_service"] == "DHL":
        reply = """
        Vaša porudžbina je poslata kurirskom službom DHL i isporuka će biti realizovana u skladu sa Uslovima korišćenja. 

        Očekivani rok isporuke je 2-5 radnih dana. Ukoliko želite, možete pratiti svoju porudžbinu na linku dhl.com. Kod za praćenje je poslati kod koji je upisan u administraciji u okviru porudžbine.
        """

    elif orders_info2["status"] == "manuallyCanceled":
        if check_if_working_hours():
            reply = """
            Hvala na poslatom upitu. Slobodan operater će odgovoriti u najkraćem mogućem roku.
            """
        else:
            reply = """
            Hvala na poslatom upitu. Vaša porudžbina je označena kao otkazana.
            Molimo Vas da nam ostavite imejl adresu i/ili kontakt telefon ukoliko se razlikuju u odnosu na podatke iz porudžbine kako bi naš operater kontaktirao sa Vama u najkraćem mogućem roku.
            """
    elif orders_info2["status"] == "returned":
        reply = """
        Vaša porudžbina je vraćena u našu knjižaru usled neuspešne isporuke.
        Ona je otkazana pošto nismo dobili povratnu informaciju da li želite da se pošalje ponovo. Molimo Vas da ponovite porudžbinu kako bismo je obradili i poslali.
        """
    else:
        reply = """
        Nepredviđena greška. Molimo Vas da nas kontaktirate slanjem upita na podrska@delfi.rs 
        ili pozivom na broj telefona našeg korisničkog servisa 011/7155-042. Radno vreme našeg korisničkog servisa: ponedeljak-petak (8-17 sati).
        """
    return reply


def order_delfi(prompt: str) -> str:
    def extract_orders_from_string(text: str) -> List[int]:
        """
        Extracts all integer order IDs consisting of five or more digits from the provided text.

        Args:
            text (str): The input string containing potential order IDs.

        Returns:
            List[int]: A list of extracted order IDs as integers.
        """
        # Define a regular expression pattern to match 5 or more digit integers
        pattern = r'\b\d{5,}\b'
        
        # Use re.findall to extract all matching patterns
        orders = re.findall(pattern, text)
        
        # Convert the matched strings to integers
        return [int(order) for order in orders]

    order_ids = extract_orders_from_string(prompt)
    if len(order_ids) > 0:
        return API_search_2(order_ids)
    else:
        return "Morate uneti tačan broj porudžbine/a."


def API_search(matching_sec_ids: List[int]) -> List[Dict[str, Any]]:
    def get_product_info(token, product_id):
        return requests.get(url="https://www.delfi.rs/api/products", params={"token": token, "product_id": product_id}).content

    # Function to parse the XML response and extract required fields
    def parse_product_info(xml_data):
        product_info = {}
        quantity_discount2_flag = False
        try:
            root = ET.fromstring(xml_data)
            product_node = root.find(".//product")
            if product_node is not None:
                # cena = product_node.findtext('cena')
                lager = product_node.findtext('lager')
                url = product_node.findtext('url')
                id = product_node.findtext('ID')
                navid = product_node.findtext('ID_nav')

                action_node = product_node.find('action')
                if action_node is not None:
                    print(f"Action node found!")  # Debugging line
                    type = action_node.find('type').text
                    if type == "fixedPrice" or type == "fixedDiscount":
                        title = action_node.find('title').text
                        end_at = action_node.find('endAt').text
                        price_regular_standard = float(action_node.find('priceRegularStandard').text)
                        price_regular_premium = float(action_node.find('priceRegularPremium').text)
                        price_quantity_standard = float(action_node.find('priceQuantityStandard').text)
                        price_quantity_premium = float(action_node.find('priceQuantityPremium').text)

                        if price_regular_standard == price_regular_premium == price_quantity_standard == price_quantity_premium:
                            akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'akcijska cena': price_regular_standard
                        }
                        elif price_regular_standard == price_regular_premium and price_quantity_standard == price_quantity_premium:
                            akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'akcijska cena': price_regular_standard,
                            'akcijska cena sa količinskim popustom': price_quantity_standard
                        }
                        elif price_regular_standard == price_quantity_standard and price_regular_premium == price_quantity_premium:
                            akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'akcijska cena': price_regular_standard,
                            'akcijska premium cena': price_regular_premium
                        }
                        elif price_regular_standard == price_regular_premium == price_quantity_standard != price_quantity_premium:
                            akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'akcijska cena': price_regular_standard,
                            'akcijska premium cena sa količinskim popustom': price_quantity_premium
                        }
                        elif price_regular_standard == price_quantity_standard and price_regular_premium != price_regular_standard and price_quantity_premium != price_quantity_standard and price_regular_premium != price_quantity_premium:
                            akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'akcijska cena': price_regular_standard,
                            'akcijska premium cena': price_regular_premium,
                            'akcijska premium cena sa količinskim popustom': price_quantity_premium
                        }
                        else:
                            akcija = {
                                'naziv akcije': title,
                                'kraj akcije': end_at,
                                'cena sa redovnim popustom': price_regular_standard,
                                'cena sa premium popustom': price_regular_premium,
                                'cena sa redovnim količinskim popustom': price_quantity_standard,
                                'cena sa premium količinskim popustom': price_quantity_premium
                            }
                    elif type == "exponentialDiscount":
                        title = action_node.find('title').text
                        end_at = action_node.find('endAt').text
                        eksponencijalni_procenti = action_node.find('levelPercentages').text
                        eksponencijalne_cene = action_node.find('levelPrices').text

                        akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'eksponencijalni procenti': eksponencijalni_procenti,
                            'eksponencijalne cene': eksponencijalne_cene
                        }
                    elif type == "quantityDiscount2":
                        quantity_discount2_flag = True
                        title = action_node.find('title').text
                        end_at = action_node.find('endAt').text
                        price_quantity_standard_d2 = float(action_node.find('priceQuantityStandard').text)
                        price_quantity_premium_d2 = float(action_node.find('priceQuantityPremium').text)
                        quantity_discount_limit = int(action_node.find('quantityDiscount2Limit').text)

                        akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'cena sa redovnim količinskim popustom': price_quantity_standard_d2,
                            'cena sa premium količinskim popustom': price_quantity_premium_d2,
                            'limit za količinski popust': quantity_discount_limit
                        }
                else:
                    print("Action node not found, taking regular price")  # Debugging line
                    # Pristupanje priceList elementu
                price_list = product_node.find('priceList')
                if price_list is not None:
                    collection_price = float(price_list.find('collectionFullPrice').text)
                    full_price = float(price_list.find('fullPrice').text)
                    eBook_price = float(price_list.find('eBookPrice').text)
                    regular_discount_price = float(price_list.find('regularDiscountPrice').text)
                    quantity_discount_price = float(price_list.find('quantityDiscountPrice').text)
                    quantity_discount_limit = int(price_list.find('quantityDiscountLimit').text)
                    premium_discount_price = float(price_list.find('regularDiscountPremiumPrice').text)
                    premium_quantity_discount_price = float(price_list.find('quantityDiscountPremiumPrice').text)
                    premium_quantity_discount_limit = int(price_list.find('quantityDiscountPremiumLimit').text)

                    if regular_discount_price == premium_discount_price == quantity_discount_price == premium_quantity_discount_price:
                        cene = {
                            'akcijska cena': regular_discount_price
                        }
                    elif regular_discount_price == premium_discount_price and quantity_discount_price == premium_quantity_discount_price:
                        cene = {
                            'cena sa popustom': regular_discount_price,
                            'cena sa količinskim popustom': quantity_discount_price
                        }
                    elif regular_discount_price == quantity_discount_price and premium_discount_price == premium_quantity_discount_price:
                        cene = {
                            'cena sa redovnim popustom': regular_discount_price,
                            'cena sa premium popustom': premium_discount_price
                        }
                    elif regular_discount_price == premium_discount_price == quantity_discount_price != premium_quantity_discount_price:
                        cene = {
                            'cena sa popustom': regular_discount_price,
                            'cena sa premium količinskim popustom': premium_quantity_discount_price
                        }
                    elif regular_discount_price == quantity_discount_price and premium_discount_price != regular_discount_price and premium_quantity_discount_price != quantity_discount_price and premium_discount_price != premium_quantity_discount_price:
                        cene = {
                            'cena sa redovnim popustom': regular_discount_price,
                            'cena sa premium popustom': premium_discount_price,
                            'cena sa premium količinskim popustom': premium_quantity_discount_price
                        }
                    else:
                        cene = {
                        'cena sa redovnim popustom': regular_discount_price,
                        'cena sa redovnim popustom na količinu': quantity_discount_price,
                        'cena sa premium popustom': premium_discount_price,
                        'cena sa premium popustom na količinu': premium_quantity_discount_price,
                        }
                    
                    if quantity_discount_limit == quantity_discount_limit:
                        limit = {
                            'limit za količinski popust': quantity_discount_limit
                        }
                    else:
                        limit = {
                            'limit za redovan količinski popust': quantity_discount_limit,
                            'limit za premium količinski popust': premium_quantity_discount_limit
                        }
                
                    pojedinacne_cene_za_quantity_discount2 = {
                        'cena sa redovnim popustom': regular_discount_price,
                        'cena sa premium popustom': premium_discount_price
                    }

                # if lager and int(lager) > 0:
                if int(lager) > 0:
                    product_info = {
                        'puna cena': full_price,
                        'eBook cena': eBook_price,
                        'cena kolekcije': collection_price,
                        'lager': lager,
                        'url': url,
                        'id': id,
                        # 'navid': navid
                    }
                    if action_node is None:
                        product_info.update(cene)
                        product_info.update(limit)
                    elif quantity_discount2_flag:
                        product_info.update(pojedinacne_cene_za_quantity_discount2)
                        product_info.update(akcija)
                    else:
                        product_info.update(akcija)
                else:
                    print(f"Skipping product with lager {lager}")  # Debugging line
            else:
                print("Product node not found in XML data")  # Debugging line
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")  # Debugging line
        return product_info

    # Main function to get info for a list of product IDs
    def get_multiple_products_info(token, product_ids):
        products_info = []
        for product_id in product_ids:
            # print(f"Product ID: {product_id}")
            xml_data = get_product_info(token, product_id)
            # print(f"XML data for product_id {product_id}: {xml_data}")  # Debugging line
            product_info = parse_product_info(xml_data)
            if product_info:
                products_info.append(product_info)
        return products_info

    # Replace with your actual token and product IDs
    token = os.getenv("DELFI_API_KEY")
    product_ids = matching_sec_ids

    try:
        products_info = get_multiple_products_info(token, product_ids)
    except:
        products_info = "No products found for the given IDs."
    # print(f"API Info: {products_info}")
    # output = "Data returned from API for each searched id: \n"
    # for info in products_info:
    #     output += str(info) + "\n"
    return products_info

def API_search_aks(order_ids: List[str]) -> List[Dict[str, Any]]:
    
    def get_order_status(order_id: int) -> Dict[str, Any]:
        url = f"http://www.akskurir.com/AKSVipService/Pracenje/{order_id}"
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for failed requests
        return response.json()

    def parse_order_status(json_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Parses the JSON data of an order's status and extracts relevant information.

        Args:
            json_data (Dict[str, Any]): The JSON data received from the order tracking API.

        Returns:
            Tuple[Dict[str, Any], List[Dict[str, Any]]]: 
                - A dictionary containing the error code and current status of the order.
                - A list of dictionaries detailing each status change, including:
                    - 'Vreme' (str): The timestamp of the status change.
                    - 'VremeInt' (str): An internal timestamp or identifier.
                    - 'Centar' (str): The center or location associated with the status.
                    - 'StatusOpis' (str): A description of the status.
                    - 'NStatus' (str): A numerical or coded representation of the status.
        """
        status_info = {}
        status_changes = []
        
        if 'ErrorCode' in json_data and json_data['ErrorCode'] == 0:
            status_info['ErrorCode'] = json_data.get('ErrorCode', 'N/A')
            status_info['Status'] = json_data.get('Status', 'N/A')
            
            lst = json_data.get('StatusList', [])
            for status in lst:
                status_change = {
                    'Vreme': status.get('Vreme', 'N/A'),
                    'VremeInt': status.get('VremeInt', 'N/A'),
                    'Centar': status.get('Centar', 'N/A'),
                    'StatusOpis': status.get('StatusOpis', 'N/A'),
                    'NStatus': status.get('NStatus', 'N/A')
                }
                status_changes.append(status_change)
        else:
            status_info['ErrorCode'] = json_data.get('ErrorCode', 'N/A')
            status_info['Status'] = json_data.get('Status', 'N/A')

        return status_info, status_changes

    def get_multiple_orders_info(order_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Retrieves and processes information for multiple order IDs.

        Args:
            order_ids (List[int]): A list of order IDs for which information is to be retrieved.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each containing:
                - 'order_id' (int): The unique identifier of the order.
                - 'current_status' (Dict[str, Any]): The current status information of the order, including:
                    - 'ErrorCode' (Any): The error code returned by the API (if any).
                    - 'Status' (Any): The current status of the order.
                - 'status_changes' (List[Dict[str, Any]]): A list of status change records, each containing:
                    - 'Vreme' (str): The timestamp of the status change.
                    - 'VremeInt' (str): An internal timestamp or identifier.
                    - 'Centar' (str): The center or location associated with the status.
                    - 'StatusOpis' (str): A description of the status.
                    - 'NStatus' (str): A numerical or coded representation of the status.
                - 'error' (str, optional): An error message if the order information could not be retrieved.
        """
        orders_info = []
        for order_id in order_ids:
            try:
                # Fetch order status
                order_status_json = get_order_status(order_id)
                current_status, status_changes = parse_order_status(order_status_json)
                
                # Assemble order information
                order_info = {
                    'order_id': order_id,
                    'current_status': current_status,
                    'status_changes': status_changes
                }
                orders_info.append(order_info)
            except requests.exceptions.RequestException as e:
                print(f"HTTP error for order {order_id}: {e}")
                orders_info.append({'order_id': order_id, 'error': str(e)})
            except Exception as e:
                print(f"Error for order {order_id}: {e}")
                orders_info.append({'order_id': order_id, 'error': str(e)})
        return orders_info

    # Main function to retrieve information for all orders
    try:
        orders_info = get_multiple_orders_info(order_ids)
    except Exception as e:
        print(f"Error retrieving order information: {e}")
        orders_info = "No orders found for the given IDs."

    return orders_info


def SelfQueryDelfi(
    upit: str,
    api_key: Optional[str] = None,
    environment: Optional[str] = None,
    index_name: str = 'delfi',
    namespace: str = 'opisi',
    openai_api_key: Optional[str] = None,
    host: Optional[str] = None
    ) -> str:
    """
    Performs a self-query on the Delfi vector store to retrieve relevant documents based on the user's query.

    This function initializes the necessary embeddings and vector store, sets up the retriever with OpenAI's ChatGPT model,
    and retrieves relevant documents that match the user's input query. It then formats the retrieved documents and their
    metadata into a single result string.

    Args:
        upit (str): The user's input query for which relevant documents are to be retrieved.
        api_key (Optional[str], optional): The API key for Pinecone. Defaults to the 'PINECONE_API_KEY' environment variable.
        environment (Optional[str], optional): The environment setting for Pinecone. Defaults to the 'PINECONE_API_KEY' environment variable.
        index_name (str, optional): The name of the Pinecone index to use. Defaults to 'delfi'.
        namespace (str, optional): The namespace within the Pinecone index to query. Defaults to 'opisi'.
        openai_api_key (Optional[str], optional): The API key for OpenAI. Defaults to the 'OPENAI_API_KEY' environment variable.
        host (Optional[str], optional): The host URL for Pinecone. Defaults to the 'PINECONE_HOST' environment variable.

    Returns:
        str: A formatted string containing the details of the retrieved documents, including metadata such as
             section ID, category, custom ID, date, image URL, authors, title, cover description, and the content.
             If an error occurs, returns the error message as a string.
    """
    
    # Use the passed values if available, otherwise default to environment variables
    api_key = api_key if api_key is not None else getenv('PINECONE_API_KEY')
    environment = environment if environment is not None else getenv('PINECONE_API_KEY')
    # index_name is already defaulted to 'positive'
    namespace = namespace if namespace is not None else getenv("NAMESPACE")
    openai_api_key = openai_api_key if openai_api_key is not None else getenv("OPENAI_API_KEY")
    host = host if host is not None else getenv("PINECONE_HOST")
   
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    # prilagoditi stvanim potrebama metadata
    metadata_field_info = [
        AttributeInfo(name="authors", description="The author(s) of the document", type="string"),
        AttributeInfo(name="category", description="The category of the document", type="string"),
        AttributeInfo(name="chunk", description="The chunk number of the document", type="integer"),
        AttributeInfo(name="date", description="The date of the document", type="string"),
        AttributeInfo(name="eBook", description="Whether the document is an eBook", type="boolean"),
        AttributeInfo(name="genres", description="The genres of the document", type="string"),
        AttributeInfo(name="id", description="The unique ID of the document", type="string"),
        AttributeInfo(name="text", description="The main content of the document", type="string"),
        AttributeInfo(name="title", description="The title of the document", type="string"),
        AttributeInfo(name="sec_id", description="The ID for the url generation", type="string"),
    ]

    # Define document content description
    document_content_description = "Content of the document"

    # Prilagoditi stvanom nazivu namespace-a
    text_key = "text" if namespace == "opisi" else "description"
    vectorstore = LangPine.from_existing_index(
        index_name=index_name, embedding=embeddings, text_key=text_key, namespace=namespace)

    # Initialize OpenAI embeddings and LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
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
        for doc in doc_result:
            print("DOC: ", doc)
            metadata = doc.metadata
            print("METADATA: ", metadata)
            result += (
                (f"Sec_id: {str(metadata['sec_id'])}\n" if 'sec_id' in metadata else "") +
                (f"Category: {str(metadata['category'])}\n" if 'category' in metadata else "") +
                (f"Custom ID: {str(metadata['custom_id'])}\n" if 'custom_id' in metadata else "") +
                (f"Date: {str(int(metadata['date']))}\n" if 'date' in metadata else "") +
                (f"Image URL: {str(metadata['slika'])}\n" if 'slika' in metadata else "") +
                (f"Authors: {str(metadata.get('book_author', 'Unknown'))}\n" if 'book_author' in metadata else "") +
                (f"Title: {str(metadata.get('book_name', 'Untitled'))}\n" if 'book_name' in metadata else "") +
                (f"Cover Description: {str(metadata.get('book_cover_description', 'No description'))}\n" if 'book_cover_description' in metadata else "") +
                (f"Content: {str(doc.page_content)}\n\n" if doc.page_content else "")
            )
            print("RESULT", result)
        return result.strip()

    except Exception as e:
        print(e)
        return str(e)


class HybridQueryProcessor:
    """
    A processor for executing hybrid queries using Pinecone.

    This class allows the execution of queries that combine dense and sparse vector searches,
    typically used for retrieving and ranking information based on text data.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initializes the HybridQueryProcessor with optional parameters.

        The API key and environment settings are fetched from the environment variables.
        Optional parameters can be passed to override these settings.

        Args:
            **kwargs: Optional keyword arguments:
                - api_key (str): The API key for Pinecone (default fetched from environment variable).
                - environment (str): The Pinecone environment setting (default fetched from environment variable).
                - alpha (float): Weight for balancing dense and sparse scores (default 0.5).
                - score (float): Score threshold for filtering results (default 0.05).
                - index_name (str): Name of the Pinecone index to be used (default 'neo-positive').
                - namespace (str): The namespace to be used for the Pinecone index (default fetched from environment variable).
                - top_k (int): The number of results to be returned (default 5).
                - delfi_special (Any): Additional parameter for special configurations.
        """
        self.api_key = kwargs.get('api_key', getenv('PINECONE_API_KEY'))
        self.environment = kwargs.get('environment', getenv('PINECONE_API_KEY'))
        self.alpha = kwargs.get('alpha', 0.5)  # Default alpha is 0.5
        self.score = kwargs.get('score', 0.05)  # Default score is 0.05
        self.index_name = kwargs.get('index', 'neo-positive')  # Default index is 'positive'
        self.namespace = kwargs.get('namespace', getenv("NAMESPACE"))  
        self.top_k = kwargs.get('top_k', 5)  # Default top_k is 5
        self.delfi_special = kwargs.get('delfi_special')
        self.index = connect_to_pinecone(self.delfi_special)
        self.host = getenv("PINECONE_HOST")

    def get_embedding(self, text: str, model: str = "text-embedding-3-large") -> List[float]:
        """
        Retrieves the embedding for the given text using the specified model.

        Args:
            text (str): The text to be embedded.
            model (str): The model to be used for embedding. Default is "text-embedding-3-large".

        Returns:
            List[float]: The embedding vector of the given text.
        """
        
        text = text.replace("\n", " ")
        result = client.embeddings.create(input=[text], model=model).data[0].embedding
       
        return result
    
    def hybrid_score_norm(self, dense: List[float], sparse: Dict[str, Any]) -> Tuple[List[float], Dict[str, List[float]]]:
        """
        Normalizes the scores from dense and sparse vectors using the alpha value.

        Args:
            dense (List[float]): The dense vector scores.
            sparse (Dict[str, Any]): The sparse vector scores.

        Returns:
            Tuple[List[float], Dict[str, List[float]]]: 
                - Normalized dense vector scores.
                - Normalized sparse vector scores with updated values.
        """
        return ([v * self.alpha for v in dense], 
                {"indices": sparse["indices"], 
                 "values": [v * (1 - self.alpha) for v in sparse["values"]]})
    
    def hybrid_query(
        self,
        upit: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
        ) -> List[Dict[str, Any]]:
        """
        Executes a hybrid query combining both dense (embedding-based) and sparse (BM25-based) search approaches
        to retrieve the most relevant results. The query leverages embeddings for semantic understanding and
        BM25 for keyword matching, normalizing their scores for a hybrid result.

        Args:
            upit (str): The input query string for which to search and retrieve results.
            top_k (Optional[int], optional): The maximum number of top results to return. If not specified, uses the default value defined in `self.top_k`.
            filter (Optional[Dict[str, Any]], optional): An optional filter to apply to the search results. It should be a dictionary that defines criteria for filtering the results.
            namespace (Optional[str], optional): The namespace within which to search for results. Defaults to `self.namespace` if not provided.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries where each dictionary represents a search result. Each result includes metadata such as:
                - 'context': The relevant text snippet related to the query.
                - 'chunk': The specific chunk of the document where the match was found.
                - 'source': The source of the document or data (could be `None` based on certain conditions).
                - 'url': The URL of the document if available.
                - 'page': The page number if applicable.
                - 'score': The relevance score of the match (default is 0 if not present).

        Raises:
            Exception: If any error occurs during processing, the exception is caught and logged but not re-raised.

        Note:
            - The hybrid query combines both semantic and lexical retrieval methods.
            - Results are only added if the 'context' field exists in the result metadata.
            - When running under the environment variable `APP_ID="ECDBot"`, the 'source' field is conditionally modified for non-first results.
        """
        # Get embedding and unpack results
        dense = self.get_embedding(text=upit)

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
        
        for idx, match in enumerate(matches):
            try:
                metadata = match.get('metadata', {})

                # Create the result entry with all metadata fields
                result_entry = metadata.copy()

                # Ensure mandatory fields exist with default values if they are not in metadata
                result_entry.setdefault('context', None)
                result_entry.setdefault('chunk', None)
                result_entry.setdefault('source', None)
                result_entry.setdefault('url', None)
                result_entry.setdefault('page', None)
                result_entry.setdefault('score', match.get('score', 0))

                if idx != 0 and getenv("APP_ID") == "ECDBot":
                    result_entry['source'] = None  # or omit this line to exclude 'source' entirely

                # Only add to results if 'context' exists
                if result_entry['context']:
                    results.append(result_entry)
            except Exception as e:
                # Log or handle the exception if needed
                print(f"An error occurred: {e}")
                pass
        
        return results
       
    def process_query_results(
        self,
        upit: str,
        dict: bool = False,
        device: Optional[Any] = None
        ) -> Any:
        """
        Processes the query results and prompt tokens based on relevance score and formats them for a chat or dialogue system.
        Additionally, returns a list of scores for items that meet the score threshold.

        Args:
            upit (str): The input query string to process.
            dict (bool, optional): Determines the format of the returned results. If `True`, returns a list of dictionaries containing raw results.
                                   If `False`, returns a formatted string of relevant metadata. Defaults to `False`.
            device (Optional[Any], optional): An optional device parameter to filter results, applicable when `APP_ID` is "DentyBot". Defaults to `None`.

        Returns:
            Any: 
                - If `dict` is `False`, returns a formatted string containing metadata of relevant documents.
                - If `dict` is `True`, returns a list of dictionaries with raw search results.
        """
        if getenv("APP_ID") == "DentyBot":
            filter = {'device': {'$in': [device]}}
            tematika = self.hybrid_query(upit=upit, filter=filter)
        else:
            tematika = self.hybrid_query(upit=upit)
        if not dict:
            uk_teme = ""
            
            for item in tematika:
                if item["score"] > self.score:
                    # Build the metadata string from all relevant fields
                    metadata_str = "\n".join(f"{key}: {value}" for key, value in item.items() if value != None)
                    # Append the formatted metadata string to uk_teme
                    uk_teme += metadata_str + "\n\n"
            
            return uk_teme
        else:
            return tematika


from datetime import datetime

class ActionFetcher:
    def __init__(self, api_url):
        """
        Inicijalizuje instancu klase sa zadatim URL-om API-ja.

        Args:
            api_url (str): URL API-ja odakle će se preuzimati podaci.
        """
        self.api_url = api_url
        self.today = datetime.now()
        self.unique_actions = set()

    def fetch_data(self):
        """
        Preuzima podatke sa API-ja.

        Returns:
            dict: Sirovi podaci preuzeti sa API-ja u JSON formatu.
            None: Vraća None ako dođe do greške prilikom preuzimanja podataka.
        """
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Greška pri povezivanju sa API-jem: {e}")
            data = None
        return data

    def fetch_actions(self, data):
        """
        Procesira podatke o akcijama i izdvaja unikatne aktuelne akcije.

        Args:
            data (dict): JSON podaci preuzeti sa API-ja, koji sadrže sekcije i akcije.

        Returns:
            None: Podaci se interno dodaju u `self.unique_actions`.
        """
        if data:
            for section in data.get('data', {}).get('sections', []):
                products = section.get('content', {}).get('products', [])
                for product in products:
                    for action in product.get('actions', []):
                        end_at = action.get('endAt')
                        if end_at:
                            try:
                                end_date = datetime.fromisoformat(end_at.replace('Z', ''))
                            except ValueError:
                                continue
                            if end_date > self.today:
                                action_type = action.get('actionType')
                                action_title = action.get('actionTitle')
                                action_description = action.get('raw', {}).get('description', 'Nema opisa')
                                end_date_str = end_date.strftime('%d.%m.%Y. %H:%M:%S')
                                self.unique_actions.add((action_type, action_title, action_description, end_date_str))

    def get_all_actions(self):
        """
        Vraća listu unikatnih akcija sa opisima i krajnjim datumima.

        Returns:
            list: Lista akcija gde svaka akcija sadrži naslov, opis i krajnji datum.
            Svaki element liste je rečnik sa ključevima:
                - 'action_title' (str): Naslov akcije.
                - 'action_description' (str): Opis akcije.
                - 'end_date' (str): Krajnji datum akcije u formatu 'dd.mm.yyyy. HH:MM:SS'.
        """
        actions = []
        for action in self.unique_actions:
            actions.append({
                'action_title': action[0],
                'action_description': action[1],
                'end_date': action[2]
            })
        return actions

    def fetch_books_for_action(self, action_name):
        """
        Procesira podatke o knjigama za zadatu akciju i vraća listu knjiga sa svim relevantnim podacima.

        Args:
            action_name (str): Naziv akcije za koju treba pronaći knjige.

        Returns:
            list: Lista rečnika gde svaki rečnik sadrži informacije o knjizi.

        Napomena:
            Ako je pronađeno više od 9 knjiga koje odgovaraju akciji, metoda će vratiti prvih 9 knjiga.
        """
        
        books = []
        data = self.fetch_data()
        if data:
            action_name_lower = action_name.lower()
            for section in data.get('data', {}).get('sections', []):
                products = section.get('content', {}).get('products', [])
                for product in products:
                    # Proveravamo samo akcije pre nego što obrađujemo proizvode
                    relevant_action = None
                    for action in product.get('actions', []):
                        if action_name_lower in action.get('actionTitle', '').lower():
                            relevant_action = action
                            break  # Pronašli smo relevantnu akciju, nema potrebe da tražimo dalje
                    
                    # Ako smo našli akciju, onda nastavljamo sa obradom proizvoda
                    if relevant_action:
                        # Extract common book data
                        title = product.get('title', 'Nema naslova')
                        description = product.get('description', 'Nema opisa')
                        authors = [author.get('authorName', 'Nepoznat autor') for author in product.get('authors', [])]
                        genres = [genre.get('genreName', 'Nepoznat žanr') for genre in product.get('genres', [])]
                        eBook = product.get('eBook', False)
                        category = product['category'].lower().replace(' ', '_')
                        oldProductId = product.get('oldProductId', 'Nepoznat ID')
                        url = f"https://delfi.rs/{category}/{oldProductId}"
                        collection_price = product.get('collectionFullPrice', 'N/A')
                        price_list = product.get('priceList', {})
                        full_price = price_list.get('fullPrice', 'N/A')
                        ebook_price = price_list.get('eBookPrice', 'N/A')
                        regular_discount_price = price_list.get('regularDiscountPrice', 'N/A')
                        premium_discount_price = price_list.get('regularDiscountPremiumPrice', 'N/A')

                        # Extract action data
                        action_type = relevant_action.get('actionType', 'N/A')
                        end_at = relevant_action.get('endAt')
                        action_title = relevant_action.get('actionTitle', 'N/A')
                        action_description = relevant_action.get('actionDescription', 'N/A')
                        # print(f"action_title: {action_title}")

                        # Create the base data dictionary
                        book_data = {
                            'title': title,
                            'authors': authors,
                            'genres': genres,
                            'eBook': eBook,
                            'url': url,
                            'description': description,
                            'actionType': action_type,
                            'actionTitle': action_title,
                            'endAt':end_at,
                            'actionDescription': action_description,
                            'collectionFullPrice': collection_price,
                            'fullPrice': full_price,
                            'eBookPrice': ebook_price,
                        }

                        # Depending on the action type, add extra data
                        if action_type == 'fixedDiscount':
                            price_regular_standard = action.get('priceRegularStandard', 'N/A')
                            price_regular_premium = action.get('priceRegularPremium', 'N/A')
                            price_quantity_standard = action.get('priceQuantityStandard', 'N/A')
                            price_quantity_premium = action.get('priceQuantityPremium', 'N/A')
                            if price_regular_standard == price_regular_premium == price_quantity_standard == price_quantity_premium:
                                book_data.update({
                                    'akcijska cena': price_regular_standard
                                })
                            elif price_regular_standard == price_regular_premium and price_quantity_standard == price_quantity_premium:
                                book_data.update({
                                    'akcijska cena': price_regular_standard,
                                    'akcijska cena sa količinskim popustom': price_quantity_standard,
                                })
                            elif price_regular_standard == price_quantity_standard and price_regular_premium == price_quantity_premium:
                                book_data.update({
                                    'akcijska cena': price_regular_standard,
                                    'akcijska premium cena': price_regular_premium
                                })
                            elif price_regular_standard == price_regular_premium == price_quantity_standard != price_quantity_premium:
                                book_data.update({
                                    'akcijska cena': price_regular_standard,
                                    'akcijska premium cena sa količinskim popustom': price_quantity_premium
                                })
                            elif price_regular_standard == price_quantity_standard and price_regular_premium != price_regular_standard and price_quantity_premium != price_quantity_standard and price_regular_premium != price_quantity_premium:
                                book_data.update({
                                    'akcijska cena': price_regular_standard,
                                    'akcijska premium cena': price_regular_premium,
                                    'akcijska premium cena sa količinskim popustom': price_quantity_premium
                                })
                            else:
                                book_data.update({
                                    'akcijska cena': price_regular_standard,
                                    'akcijska premium cena': price_regular_premium,
                                    'akcijska cena sa količinskim popustom': price_quantity_standard,
                                    'akcijska premium cena sa količinskim popustom': price_quantity_premium,
                                })
                        elif action_type == 'fixedPrice':
                            price_regular_standard = action.get('priceRegularStandard', 'N/A')
                            price_regular_premium = action.get('priceRegularPremium', 'N/A')
                            price_quantity_standard = action.get('priceQuantityStandard', 'N/A')
                            price_quantity_premium = action.get('priceQuantityPremium', 'N/A')
                            fixed_price = action.get('raw', {}).get('fixedPrice', 'N/A')
                            fixed_price_limit = action.get('raw', {}).get('fixedPriceCount', 'N/A')
                            book_data.update({
                                'fiksna cena': fixed_price,
                                'potrebna količina za ostvarivanje akcije': fixed_price_limit
                            })
                            if price_regular_standard == price_regular_premium == price_quantity_standard == price_quantity_premium:
                                book_data.update({
                                    'akcijska cena': price_regular_standard
                                })
                            elif price_regular_standard == price_regular_premium and price_quantity_standard == price_quantity_premium:
                                book_data.update({
                                    'akcijska cena': price_regular_standard,
                                    'akcijska cena sa količinskim popustom': price_quantity_standard,
                                })
                            elif price_regular_standard == price_quantity_standard and price_regular_premium == price_quantity_premium:
                                book_data.update({
                                    'akcijska cena': price_regular_standard,
                                    'akcijska premium cena': price_regular_premium
                                })
                            elif price_regular_standard == price_regular_premium == price_quantity_standard != price_quantity_premium:
                                book_data.update({
                                    'akcijska cena': price_regular_standard,
                                    'akcijska premium cena sa količinskim popustom': price_quantity_premium
                                })
                            elif price_regular_standard == price_quantity_standard and price_regular_premium != price_regular_standard and price_quantity_premium != price_quantity_standard and price_regular_premium != price_quantity_premium:
                                book_data.update({
                                    'akcijska cena': price_regular_standard,
                                    'akcijska premium cena': price_regular_premium,
                                    'akcijska premium cena sa količinskim popustom': price_quantity_premium
                                })
                            else:
                                book_data.update({
                                    'akcijska cena': price_regular_standard,
                                    'akcijska premium cena': price_regular_premium,
                                    'akcijska cena sa količinskim popustom': price_quantity_standard,
                                    'akcijska premium cena sa količinskim popustom': price_quantity_premium,
                                })
                        elif action_type == 'exponentialDiscount':
                            levels = action.get('levels', [])
                            level_list = []
                            for level in levels:
                                level_percentage = level.get('levelPercentage', 'N/A')
                                level_price = level.get('levelPrice', 'N/A')
                                level_list.append({
                                    'procenat': level_percentage,
                                    'akcijska cena': level_price,
                                })
                            book_data.update({
                                'stepenasti popust': level_list
                            })
                        elif action_type == 'quantityDiscount2':
                            price_quantity_standard = relevant_action.get('priceQuantityStandard', 'N/A')
                            price_quantity_premium = relevant_action.get('priceQuantityPremium', 'N/A')
                            quantity_discount2_limit = relevant_action.get('quantityDiscount2Limit', 'N/A')
                            if regular_discount_price == premium_discount_price and price_quantity_standard == price_quantity_premium:
                                book_data.update({
                                    'cena sa popustom': regular_discount_price,
                                    'akcijska cena sa količiniskim popustom': price_quantity_standard,
                                    'limit za količinski popust': quantity_discount2_limit,
                                })
                            else:
                                book_data.update({
                                    'cena sa redovnim popustom': regular_discount_price,
                                    'cena sa premium popustom': premium_discount_price,
                                    'akcijska cena sa količiniskim popustom': price_quantity_standard,
                                    'akcijska premium cena sa količiniskim popustom': price_quantity_premium,
                                    'limit za količinski popust': quantity_discount2_limit,
                                })

                        # Add the book data to the list
                        books.append(book_data)

                        if len(books) >= 9:
                            return books
        return books

    def decide_and_respond(self, question):
        """
        Odlučuje koju funkciju pozvati na osnovu korisnikovog pitanja, koristeći LLM (Language Model).

        Args:
            question (str): Pitanje korisnika koje može biti vezano za aktuelne akcije ili proizvode na određenoj akciji.

        Returns:
            list: Ako korisnik pita za aktuelne akcije, vraća listu svih trenutno dostupnih akcija.
            list: Ako korisnik pita za proizvode na određenoj akciji, vraća listu knjiga koje su deo te akcije.
            dict: Ako dođe do greške u odlučivanju, vraća rečnik sa ključem "error" i opisom greške.
        
        Raises:
            KeyError: Ako ne postoji odgovarajući API ključ ili ako dođe do greške prilikom pristupa API-ju.
            ValueError: Ako LLM ne može da odluči između akcija i knjiga na osnovu korisničkog pitanja.
        
        Proces:
            - Prvo koristi LLM da odluči da li korisnik pita o aktuelnim akcijama ili knjigama na specifičnoj akciji.
            - Ako je odgovor 'actions', vraća sve trenutno dostupne akcije.
            - Ako je odgovor 'books', iz korisnikovog pitanja se izvlači naziv akcije i vraćaju se knjige za tu akciju.
            - Ako odluka nije jasna, vraća se poruka o grešci.
        """

        tools = [
        {
            "type": "function",
            "function": {
                "name": "Books",
                "description": "",
                "parameters": {
                    "type": "object",
                    "properties": {
                    "query": {
                        "type": "string",
                        "description": "If the user asks about products on some of the actions"
                    }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                },
                "strict": True
            }
        },
        {
            "type": "function",
            "function": {
                "name": "Actions",
                "description": "",
                "parameters": {
                    "type": "object",
                    "properties": {
                    "query": {
                        "type": "string",
                        "description": "If the user asks about current actions in the store."
                    }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }
        ]
         
        response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "Your one and only job is to determine the name of the tool that should be used to solve the user query. Do not return any other information."},
                        {"role": "user", "content": question}],
                tools=tools,
                temperature=0.0,
                tool_choice="required",
            )
        assistant_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        
        if finish_reason == "tool_calls" or "stop":
            decision = assistant_message.tool_calls[0].function.name
        else:
            decision = "Warning: No function was called"

        if decision == 'Actions':
            # Korisnik pita za aktuelne akcije
            data = self.fetch_data()
            self.fetch_actions(data)
            return self.get_all_actions()

        elif decision == 'Books':
            # Korisnik pita za knjige iz specifične akcije
            action_name_response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant. The user is asking about books for one of the current promotion."
                            "You need to extract the specific promotion name from the question, ensuring to handle inflected forms by converting them to their nominative form."
                            "Ensure that the name contains the base form of the word. For example, if the user asks for 'autobiografije,' the search should be conducted using 'autobiografij' to account for both singular and plural forms."
                            "Normalize the search term by replacing non-diacritic characters with their diacritic equivalents. For instance, convert 'z' to 'ž', 's' to 'š', 'c' to 'ć' or 'č', and so on, so that the search returns accurate results even when diacritics are not omitted."
                            "Return only the name of the promotion in order to the function filter the data for books on that specific promotion."
 
                            "Here is an example: "
                            "Example user question: 'koje knjige su na akciji Nauci kroz igru' "
                            "nauči kroz igr"
 
                            "Here is an example: "
                            "Example user question: 'koje knjige su na akciji Nauci kroz igru' "
                            "domaći izdavači"
                        )
                    },])
            action_name = action_name_response.choices[0].message.content.strip()
            print(f"naziv akcije: ", action_name)
            return self.fetch_books_for_action(action_name)

        else:
            return {"error": "Nije moguće odlučiti šta korisnik želi."}
