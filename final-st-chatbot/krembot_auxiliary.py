import os
from os import getenv
from neo4j import GraphDatabase, Driver
from neo4j.graph import Node
import json
from pinecone import Pinecone
from typing import Any, List, Dict, Any
from re import finditer
import streamlit as st
from krembot_db import ConversationDatabase

# Load the configurations from JSON file located in the 'clients' folder
def load_config(client_key: str) -> None:
    """
    Loads environment variables from the client configuration JSON file 
    based on the provided client key and sets them in the os.environ.

    Args:
        client_key (str): The key of the client to load from the configuration file.
    """
    config_path = os.path.join('clients', 'client_configs.json')  # Adjust path to the 'clients' folder
    try:
        with open(config_path, 'r') as config_file:
            configs = json.load(config_file)
            
            if client_key in configs:
                for key, value in configs[client_key].items():
                    os.environ[key] = value
            else:
                print(f"Client '{client_key}' not found in the config.")
    except FileNotFoundError:
        print(f"Configuration file not found at {config_path}")


# Load only the tools from the JSON file that exist in tools_dict
def load_matching_tools(choose_rag: str) -> List[Dict[str, Any]]:
    """
    Loads tools from a JSON file and returns only those tools whose keys match
    the tool names found in tools_dict, generated from the provided text (choose_rag).

    Args:
        choose_rag (str): The input string used to match tools from the JSON file.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries representing the matching tools.
    """
    tools_dict = generate_tool_dict(choose_rag)
    config_path = os.path.join('clients', 'all_tools.json')  # Path to the JSON file in the 'clients' folder

    try:
        with open(config_path, 'r') as json_file:
            all_tools_json = json.load(json_file)  # Load the JSON content
            # Filter and load only the dictionaries whose keys exist in tools_dict
            matching_tools = []
            for tool_name in tools_dict.keys():
                if tool_name in all_tools_json:
                    # Update the description with the one in tools_dict
                    tool_dict = all_tools_json[tool_name]
                    tool_dict["function"]["parameters"]["properties"]["query"]["description"] = tools_dict[tool_name]
                    matching_tools.append(tool_dict)

            return matching_tools
    except FileNotFoundError:
        st.write(f"Configuration file not found at {config_path}")
        return []


# Generate a tool dictionary from the given text (choose_rag)
def generate_tool_dict(choose_rag: str) -> Dict[str, str]:
    """
    Generates a dictionary of tool descriptions from the provided text.

    Args:
        choose_rag (str): The input string that contains tool names and their descriptions.

    Returns:
        Dict[str, str]: A dictionary where the keys are tool names and the values are tool descriptions.
    """

    # Function to extract all main keys from all_tools.json
    def load_all_tool_keys() -> List[str]:
        """
        Loads all top-level keys (tool names) from the all_tools.json file.

        Returns:
            List[str]: A list of tool names extracted from the all_tools.json file.
        """
        json_file_path = os.path.join('clients', 'all_tools.json')
        try:
            with open(json_file_path, 'r') as json_file:
                all_tools_data = json.load(json_file)
                
                # Extract the top-level keys
                main_keys = list(all_tools_data.keys())
                
                return main_keys

        except FileNotFoundError:
            print(f"File {json_file_path} not found.")
            return []

        except json.JSONDecodeError:
            print(f"Error decoding JSON in {json_file_path}.")
            return []

    tools = load_all_tool_keys()
    # Build a regex pattern to match '- ToolName:' with exact tool names
    pattern = r'-\s*({0}):'.format("|".join(tools))

    # Find all matches of tool names in the text
    matches = list(finditer(pattern, choose_rag))

    # Initialize an empty dictionary to store tool descriptions
    tools_dict = {}

    # Loop over matches to extract descriptions
    for i, match in enumerate(matches):
        tool = match.group(1)
        start = match.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(choose_rag)
        description = choose_rag[start:end].strip()
        tools_dict[tool] = description

    for k, v in tools_dict.items():
        print(f"{k}")

    print("+++++++++")
    return tools_dict



def connect_to_neo4j() -> Driver:
    """
    Establishes a connection to the Neo4j database using credentials from environment variables.

    Returns:
        neo4j.Driver: A Neo4j driver instance for interacting with the database.
    """
    uri = getenv("NEO4J_URI")
    user = getenv("NEO4J_USER")
    password = getenv("NEO4J_PASS")
    return GraphDatabase.driver(uri, auth=(user, password))


def neo4j_isinstance(value: Any) -> dict:
    if isinstance(value, Node):
    # Ako je vrednost Node objekat, pristupamo properties atributima
        return {k: v for k, v in value._properties.items()}


def connect_to_pinecone(x: int) -> Any:
    """
    Connects to a Pinecone index based on the provided parameter.

    Args:
        x (int): Determines which Pinecone host to connect to. If x is 0, connects to the primary host;
                 otherwise, connects to the secondary host.

    Returns:
        Any: An instance of Pinecone Index connected to the specified host.
    """
    pinecone_api_key = getenv('PINECONE_API_KEY')
    pinecone_host = (
        "https://delfi-a9w1e6k.svc.aped-4627-b74a.pinecone.io"
        if x == 0
        else "https://neo-positive-a9w1e6k.svc.apw5-4e34-81fa.pinecone.io"
    )
    pinecone_client = Pinecone(api_key=pinecone_api_key, host=pinecone_host)
    return pinecone_client.Index(host=pinecone_host)


def handle_feedback() -> None:
    """
    Processes and stores user feedback within the Streamlit application.

    This function retrieves feedback data from the Streamlit session state, structures it into a predefined
    format, and stores it in the database using the `ConversationDatabase` context manager. The feedback
    includes details such as the previous question, the tool's answer, the user's given answer, the type
    of feedback (Good/Bad), and any optional text provided by the user.

    Upon successful storage, a success toast message is displayed. If an error occurs during the storage
    process, an error message is shown to the user.

    Returns:
        None

    Raises:
        None: All exceptions are handled internally and do not propagate.
    """
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


# NOT USED CURERNTLY, wait for stui to be functional again
def reset_memory(sys_ragbot) -> None:
    """
    Resets the conversation memory for the current thread within the Streamlit session.

    This function clears the message history by resetting the `messages` dictionary for the current
    `thread_id` in the session state to its initial state, which contains only the system prompt.
    Additionally, it clears any filtered messages stored in the session state.

    This is useful for starting a new conversation thread or clearing the existing context to ensure
    that subsequent interactions are not influenced by previous exchanges.

    Returns:
        None

    Raises:
        None: The function performs operations on the session state without raising exceptions.
    """
    st.session_state.messages[st.session_state.thread_id] = [{'role': 'system', 'content': sys_ragbot}]
    st.session_state.filtered_messages = ""


def initialize_session_state(defaults):
    for key, value in defaults.items():
        if key not in st.session_state:
            if callable(value):
                # ako se dodeljuje npr. funkcija
                st.session_state[key] = value()
            else:
                st.session_state[key] = value

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


#               OLD METHODS

# def get_structured_decision_from_model(user_query: str) -> str:
#     """
#     Determines the appropriate tool to handle a user's query using the OpenAI model.
#
#     This function sends the user's query to the OpenAI API with a specific system prompt to obtain a structured
#     decision in JSON format. It parses the JSON response to extract the selected tool.
#
#     Args:
#         user_query (str): The user's input query for which a structured decision is to be made.
#
#     Returns:
#         str: The name of the tool determined by the model to handle the user's query. If the 'tool' key is not present,
#              it returns the first value from the JSON response.
#     """
#     client = OpenAI()
#     response = client.chat.completions.create(
#         model=getenv("OPENAI_MODEL"),
#         temperature=0,
#         response_format={"type": "json_object"},
#         messages=[
#         {"role": "system", "content": mprompts["choose_rag"]},
#         {"role": "user", "content": f"Please provide the response in JSON format: {user_query}"}],
#         )
#     json_string = response.choices[0].message.content
#     # Parse the JSON string into a Python dictionary
#     data_dict = json.loads(json_string)
#     # Access the 'tool' value
#     return data_dict['tool'] if 'tool' in data_dict else list(data_dict.values())[0]


# def main_wrap_for_st() -> None:
#     """
#     Wraps the main application logic with OpenAI error handling for the Streamlit application.

#     This function serves as a wrapper that executes the main application function (`main`) within the
#     `check_openai_errors` context. It ensures that any OpenAI-related errors encountered during the
#     execution of the main function are gracefully handled and appropriate warning messages are
#     displayed to the user using Streamlit's `st.warning`.

#     This abstraction allows for cleaner main application code by centralizing error handling related
#     to OpenAI API interactions.

#     Returns:
#         None

#     Raises:
#         None: All exceptions are handled within the `check_openai_errors` function and do not propagate.
#     """
#     check_openai_errors(main)