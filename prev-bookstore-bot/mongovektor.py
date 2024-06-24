
from pymongo import MongoClient
from openai import OpenAI
import dns.resolver

# na mom kompu je bilo potrebno dodati ovaj deo koda da bi mogao da se konektujem na bazu
dns.resolver.default_resolver=dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers=['8.8.8.8']

# Set the Stable API version when creating a new clients
uri = "mongodb+srv://djordjethai:ItR5s9U2wV2sTMpW@cluster0.shhkwnk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri)
db = client['vektordb']
collection = db['vektor']
openaiclient=OpenAI()

# query the database
query=input("pitaj: ")
query_vector=openaiclient.embeddings.create(input=query, model="text-embedding-ada-002")
qv = query_vector.data[0].embedding

# pipeline: $vectorSearch search params, $project what to return
pipeline = [
{
    '$vectorSearch': {
      'index': 'vector_index', 
      'path': 'embeddings', 
      'queryVector': qv,
      'numCandidates': 100, 
      'limit': 5
    }
  }, {
    '$project': {
      '_id': 0, 
      'text': 1,
      'source': 1
    }
  }
]

result = client["vektordb"]["vektor"].aggregate(pipeline)
answer = ""
for i in result:
    answer += i.get('text') + "\n"

# ask LLM to summarize the results
if answer !="":
  response = openaiclient.chat.completions.create(
              model="gpt-4o",
              temperature=0,
              messages=[{"role": "user", "content": f"""Please summarize this: {answer}"""}])

  odgovor = response.choices[0].message.content
  print(odgovor)

