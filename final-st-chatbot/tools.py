tools = [
    {
        "type": "function",
        "function": {
            "name": "hybrid_query_processor",
            "description": "Processes hybrid queries using Pinecone to retrieve and rank information based on dense and sparse vector searches. Supports multiple namespaces for different contexts like Hybrid, FAQ, Uputstva, and Blogovi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query text to process and retrieve information for."
                    },
                    "namespace": {
                        "type": "string",
                        "enum": ["Hybrid", "FAQ", "Uputstva", "Blogovi"],
                        "description": "The namespace/context for the query. Select one of the following: Hybrid, FAQ, Uputstva, Blogovi."
                    }
                },
                "required": ["query", "namespace"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "SelfQueryDelfi",
            "description": "Executes a query against a Pinecone vector database using metadata self-querying. Supports namespaces such as 'opisi' and 'korice' for different types of document retrieval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "upit": {
                        "type": "string",
                        "description": "The query input for retrieving relevant documents and metadata."
                    },
                    "namespace": {
                        "type": "string",
                        "enum": ["opisi", "korice"],
                        "description": "Namespace to specify the document type for the query, such as 'opisi' for descriptions and 'korice' for covers."
                    }
                },
                "required": ["upit"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "graphp",
            "description": "Executes a Neo4j Cypher query based on a user's natural language question, retrieves data from the database, and combines it with additional metadata from Pinecone and an external API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pitanje": {
                        "type": "string",
                        "description": "The user's question, which is translated into a Cypher query to fetch data from the Neo4j database."
                    }
                },
                "required": ["pitanje"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pineg",
            "description": "Retrieves book-related information based on a user query, fetching data from Pinecone and Neo4j, and combining it with additional metadata from an external API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pitanje": {
                        "type": "string",
                        "description": "The user's question, which is used to search Pinecone and Neo4j for book information."
                    }
                },
                "required": ["pitanje"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "order_delfi",
            "description": "Extracts order numbers from a user prompt and retrieves order details using an external API. Returns relevant order data if valid order numbers are provided.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The user's input containing order numbers (5 or more digit integers)."
                    }
                },
                "required": ["prompt"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dentyWF",
            "description": "Selects the appropriate dental tool based on a user's query, and provides relevant information about the selected tool from a Pinecone index. Returns a response based on the device metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The user's query which helps in selecting the most appropriate dental tool."
                    }
                },
                "required": ["prompt"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "intelisale",
            "description": "Retrieves customer data based on a user query and generates a detailed report with financial and activity information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User's query, which contains customer information in a form such as 'Customer x', 'Company y', or 'klijent z'. The query will be parsed to extract the customer name in the format 'Customer x'."
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        }
    }
]
