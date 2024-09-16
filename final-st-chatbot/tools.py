tools = [
    {
        "type": "function",
        "function": {
            "name": "hybrid_query_processor",
            "description": "Use this tool to provide users with quick customer support to the most common concerns and questions. FAQs can cover a variety of topics, such as technical issues, shipping cost, delivery, payment methods, delivery time frames, gifts, discounts and membership benefits, inforrmation about order cancellation and modification, complaints and returns, customer service hours, terms and conditions of use, and other relevant information.",
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
            "description": "Executes a query against a Pinecone vector database using metadata self-querying. Supports namespaces such as 'opisi' and 'korice' for different types of document retrieval. Use this tool when user gives you any kind of book covers OR content (summary) description, no matter how shallow or brief it is. ALWAYS PROVIDE CORRESPONDING LINK!!! Example: „Ne znam koja knjiga je u pitanju, ali imala je plave korice i siluetu zene“ „Knjiga u kojoj se zena baca pod voz“ ",
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
            "description": "Use this tool when you are asked to recommend simmilar books based on genre, author, number of pages, price etc. and when you find those provide brief description for them. So this is recomendation based on details. Examples: „Intresuju me fantastika. Preporuči mi neke knjige“ „Koja je cena knjige Deca zla?“ „Koliko strana ima knjiga Mali princ?“ „Preporuci mi knjigu ispod 200 strana.“ „Imate li na stanju Krhotine?“  „preporuči mi 3 dramska dela“  „trnova ruzica“  „preporuci mi knjige istog zanra kao oladi malo“  „Preporuci mi 5 knjiga od Donata Karizija.“  „Preporuci mi knjigu ispod 200 strana.“  „Volim da citam Dostojevskog, preporuci mi neke njegove knjige.“,  „Preporuci mi neke trilere koje imate na stanju.“  „Koje knjige imate od Danila Kisa“  Provide coressponding LINK of recommended books!!!",
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
            "description": "Use this tool when you get description of a book or some kind of details of the plot and a question to recommend simmilar books based on that. So recommendation based on description. Example: „Preporuci mi knjigu gde zaljubljeni par nailazi na mnoge prepreke pre nego sto dodje do srecnog kraja.“ „Procitao sam knjigu Male Zene, mozes li da mi preporucis neke slicne.“ „O čemu se radi u knjizi Memoari jedne gejše?“  „Preporuci mi delo u kome se radi o zmajevima i princezama.“  „Preporuci mi knjigu slicnu onoj u kojoj se zena bacila pod voz“   „preporuči mi knjige slične ""Oladi malo"" od Sare Najt“  Provide coressponding LINK of recommended books!!!  ",
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
            "description": "Always use this tool if the question is related to orders, their tracking, status, cancelation or if question includes order number. „Sta je sa mojom porudzbinom“, „Broj moje porudzbine je 234214“, „Koji je status moje porudzbine“, „Zelim da otkazem porudzbinu“...  ",
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
    }
]


_ = """

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

"""
