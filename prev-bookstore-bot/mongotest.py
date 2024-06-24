
from pymongo import MongoClient
from openai import OpenAI
import dns.resolver
import json

# na mom kompu je bilo potrebno dodati ovaj deo koda da bi mogao da se konektujem na bazu
dns.resolver.default_resolver=dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers=['8.8.8.8']

system_prompt = """You are a MongoDB query generator. I will provide you with a plain language description of a query, and you will convert it into a MongoDB query in JSON format. My database has the following fields: text, source, and date. Please ensure the output is properly formatted JSON.

Examples:
Plain language: Find all documents where the text contains the word "operacija".
MongoDB query:

{
  "text": { "$regex": "operacija"}
}
Plain language: Get all documents from the source "news".
MongoDB query:

{
  "source": "news"
}
Plain language: Retrieve all documents dated before January 1, 2022.
MongoDB query:

{
  "date": { "$lt": "2022-01-01" }
}

Plain language: Find documents where the text contains "operacija" and the source is "news".
MongoDB query:

{
  "$and": [
    { "text": { "$regex": "operacija" },
    { "source": "news" }
  ]
}
Plain language: Find documents where the text contains "operacija" and the date is after January 1, 2022.
MongoDB query:

{
  "$and": [
    { "text": { "$regex": "operacija", "$options": "i" } },
    { "date": { "$gt": "2022-01-01" } }
  ]
}"""


# Set the Stable API version when creating a new clients
uri = "mongodb+srv://djordjethai:ItR5s9U2wV2sTMpW@cluster0.shhkwnk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri)
db = client['vektordb']
collection = db['vektor']
openaiclient=OpenAI()

# query the database
query=input("pitaj: ")
prep_response = openaiclient.chat.completions.create(
              model="gpt-4o",
              temperature=0,
              messages=[{"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"""Please translate this query to MongoDB language: {query}. Give response in JSON format only"""}],
              response_format={"type": "json_object"} )

odgovor = prep_response.choices[0].message.content
#print(odgovor)
answer = ""
query_json = json.loads(odgovor)
fields = query_json.keys()
mydoc = collection.find(query_json).limit(3)

for document in mydoc:
    for field in fields:
        if field in document:
            answer += f"{field}: {document[field]}\n"

# Print the answer
#print(answer)
if answer !="":
  response = openaiclient.chat.completions.create(
              model="gpt-4o",
              temperature=0,
              messages=[{"role": "user", "content": f"""Answer the question {query} using this context: {answer}"""}])

  odgovor = response.choices[0].message.content
  print(odgovor)

