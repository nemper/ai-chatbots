import os
from os import getenv
from neo4j import GraphDatabase, Driver
from neo4j.graph import Node
import json
from pinecone import Pinecone
from typing import Any
from re import finditer

# Load the configurations from JSON file located in the 'clients' folder
def load_config(client_key):
    config_path = os.path.join('clients', 'client_configs.json')  # Adjust path to the 'clients' folder
    try:
        with open(config_path, 'r') as config_file:
            configs = json.load(config_file)
            
            if client_key in configs:
                for key, value in configs[client_key].items():
                    os.environ[key] = value
                    print(os.environ[key])
            else:
                print(f"Client '{client_key}' not found in the config.")
    except FileNotFoundError:
        print(f"Configuration file not found at {config_path}")

# Load only the tools from the JSON file that exist in tools_dict
def load_matching_tools(choose_rag):
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
        print(f"Configuration file not found at {config_path}")
        return []


json_file_path = os.path.join('clients', 'all_tools.json')
def generate_tool_dict(choose_rag):
    # Function to extract all main keys from all_tools.json
    def load_all_tool_keys():
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


#               OLD METHOD

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
