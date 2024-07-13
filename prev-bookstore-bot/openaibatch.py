import json
from openai import OpenAI
client = OpenAI()


# #out_file = "batch_50.jsonl"
# #out_file = "delfi_drugi.jsonl"
# #out_file = "delfi_treci.jsonl"
# out_file = "delfi_cetvrti.jsonl"

# # upload batch file
# batch_input_file = client.files.create(
#   file=open(out_file, "rb"),
#   purpose="batch"
# )



# # submit job
# #batch_input_file_id = "file-MYG8CPN1clawFC6fyxmEYQ6T"
# #batch_input_file_id = "file-ZUjFvy99X3ICUOh1ue1Cz35Z"
# batch_input_file_id = "file-5o8SaKhdVgA1kU1NRwlHTOw2"

# client.batches.create(
#     input_file_id=batch_input_file_id,
#     endpoint="/v1/chat/completions",
#     completion_window="24h",
#     metadata={
#       "description": "final delfi images job4"
#     }
# )


# # Check status of the batch job
# batch_job = "batch_VbTM5MQ3UokQon9HZYUXZgyf"
# status = client.batches.retrieve(batch_job)
# print(f"do sada uradjeno {status.status}: {status.request_counts.completed} of {status.request_counts.total}")


# Retrieve the file content from the API - UNETI PRAVE ID !!!!!!!!!!!!!!!!!
#file_id = "file-8aev1DjZ5iIVLMOCEivKiYdx"
file_id = "file-8aev1DjZ5iIVLMOCEivKiYdx"
#file_id = "file-8aev1DjZ5iIVLMOCEivKiYdx"
#file_id = "file-8aev1DjZ5iIVLMOCEivKiYdx"

file_response = client.files.content(file_id)

# Open the file for writing in JSONL format
#jsonl_file_path = 'response_data_prvi.jsonl'
jsonl_file_path = 'response_data_drugi.jsonl'
#jsonl_file_path = 'response_data_treci.jsonl'
#jsonl_file_path = 'response_data_cetvrti.jsonl'

with open(jsonl_file_path, 'w', encoding='utf-8') as f:
    # Assuming each line in the response is a JSON object
    for line in file_response.text.splitlines():
        json_line = json.loads(line)
        f.write(json.dumps(json_line, ensure_ascii=False) + '\n')

print(f"File content has been saved to '{jsonl_file_path}'")
