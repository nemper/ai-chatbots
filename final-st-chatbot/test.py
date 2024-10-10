import re
import os
os.environ["CLIENT_FOLDER"] = "Delfi"
os.environ["SYS_RAGBOT"] = "DELFI_SYS_RAGBOT"
os.environ["APP_ID"] = "DelfiBot"
os.environ["CHOOSE_RAG"] = "DELFI_CHOOSE_RAG"
os.environ["OPENAI_MODEL"] = "gpt-4o"
os.environ["PINECONE_HOST"] = "https://delfi-a9w1e6k.svc.aped-4627-b74a.pinecone.io"
from krembot_db import work_prompts
import streamlit as st
mprompts = work_prompts()

# Input string
input_text = """
You are a helpful assistant capable of using various tools to answer questions. Your responses should be in a structured JSON format, indicating which tool to use. The tools are: 
- Graphp: Use this tool when you are asked to recommend simmilar books based on genre, author, number of pages, price etc. or when you are asked for recommendation in general. When you find those provide brief description for them. So this is recomendation based on details and in general. Examples: „Intresuju me fantastika. Preporuči mi neke knjige“ „Koja je cena knjige Deca zla?“ „Koliko strana ima knjiga Mali princ?“ „Preporuci mi knjigu ispod 200 strana.“ „Imate li na stanju Krhotine?“  „preporuči mi 3 dramska dela“  „trnova ruzica“  „preporuči mi knjige slične ""Oladi malo"" od Sare Najt“  „Procitao sam knjigu Male Zene, mozes li da mi preporucis neke slicne.“  „Preporuci mi knjigu slicnu kao Gordost i predrasude“ „Preporuci mi knjigu kao sto je Alisa u zemlji cuda“  „Daj mi knjigu kao sto su Hajduci od Branislava Nusica“  „Predlozi mi knjigu slicnu Ostrvu pelikana“  „preporuci mi knjige istog zanra kao oladi malo“  „Preporuci mi 5 knjiga od Donata Karizija.“  „Preporuci mi knjigu ispod 200 strana.“  „Volim da citam Dostojevskog, preporuci mi neke njegove knjige.“,  „Preporuci mi neke trilere koje imate na stanju.“  „Koje knjige imate od Danila Kisa“  Provide coressponding LINK of recommended books!!!  
- Pineg: Use this tool when you are asked to recommend simmilar books based on description/content of a book or based on some kind of detail of the plot. So recommendation based on description. Example: „Preporuci mi knjigu gde zaljubljeni par nailazi na mnoge prepreke pre nego sto dodje do srecnog kraja.“ „O čemu se radi u knjizi Memoari jedne gejše?“  „Predlozi mi knjigu koja je po sadrzaju slicna kao Sa nama se zavrsava“  „Preporuci mi knjigu ciji opis je slican knjizi Atomske navike.“  „Daj mi neku knjigu koja je po radnji slicna Saptacu od Karizija.“  „Koja knjiga je slicna knjizi Avlija, po fabuli“  „Preporuci mi delo u kome se radi o zmajevima i princezama.“  „Preporuci mi knjigu slicnu onoj u kojoj se zena bacila pod voz“   Provide coressponding LINK of recommended books!!!   
- Orders: Always use this tool if the question is related to orders, their tracking, status, cancelation or if question includes order number. „Sta je sa mojom porudzbinom“, „Broj moje porudzbine je 234214“, „Koji je status moje porudzbine“, „Zelim da otkazem porudzbinu“...     
- Natop: Always use this tool if the question is related to terms (or their variations): "top list" or "most popular".     
- Korice: Use this tool when user gives you any kind of book covers, no matter how shallow or brief it is. ALWAYS PROVIDE CORRESPONDING LINK!!! Example: „Ne znam koja knjiga je u pitanju, ali imala je plave korice i siluetu zene“ „Na koricama su se nalazile papuce i fotelja“  
- Hybrid: Use this tool to provide users with quick customer support to the most common concerns and questions. FAQs can cover a variety of topics, such as technical issues, shipping cost, delivery, payment methods, delivery time frames, gifts, discounts and membership benefits, inforrmation about order cancellation and modification, complaints and returns, customer service hours, terms and conditions of use, and other relevant information.  
- Actions: If the user wants to know about current actions or about the products on a specific action.
"""

# Regex to extract tool descriptions
tool_pattern = r"- (\w+): (.+?)(?=\n-|\Z)"
tools = re.findall(tool_pattern, mprompts["choose_rag"], re.DOTALL)

# Convert to dictionary
tools_dict = {tool: description.strip() for tool, description in tools}
print(mprompts["choose_rag"])
print(tools_dict)
