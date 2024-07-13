import json
from openai import OpenAI
client = OpenAI()

# lista = client.batches.list(limit=10)
# for list in lista:
#     print(f"{list.status}, {list.request_counts.completed} of {list.request_counts.total} {list.metadata['description']}, batch: {list.id}, input: {list.input_file_id}, output: {list.output_file_id}")
    
#out_file = "resized.jsonl"
# out_file = "batch_50.jsonl"
# out_file = "delfi_drugi.jsonl"
# out_file = "delfi_treci.jsonl"
# out_file = "delfi_cetvrti.jsonl"

# # upload batch file
# batch_input_file = client.files.create(
#   file=open(out_file, "rb"),
#   purpose="batch"
# )



# submit job
#batch_input_file_id = "file-MYG8CPN1clawFC6fyxmEYQ6T"
#batch_input_file_id = "file-ZUjFvy99X3ICUOh1ue1Cz35Z"
#batch_input_file_id = "file-5o8SaKhdVgA1kU1NRwlHTOw2"
# batch_input_file_id = "file-3baC7bZygRoxvfXb2dh7yn91"

# client.batches.create(
#     input_file_id=batch_input_file_id,
#     endpoint="/v1/chat/completions",
#     completion_window="24h",
#     metadata={
#       "description": "final delfi images job4"
#     }
# )


# # # Check status of the batch job
# batch_job = "batch_VbTM5MQ3UokQon9HZYUXZgyf"
# status = client.batches.retrieve(batch_job)
# print(f"do sada uradjeno {status.status}: {status.request_counts.completed} of {status.request_counts.total}")
# batch_job = "batch_trkqSnrSAVchcxeAtaMfdurX"
# status = client.batches.retrieve(batch_job)
# print(f"do sada uradjeno {status.status}: {status.request_counts.completed} of {status.request_counts.total}")
# batch_job = "batch_KMwqJQ6xIjzCPGHENw7OuX3A"
# status = client.batches.retrieve(batch_job)
# print(f"do sada uradjeno {status.status}: {status.request_counts.completed} of {status.request_counts.total}")
# batch_job = "batch_YXJmqN5ebNxsNB2yNIlopNVw"
# status = client.batches.retrieve(batch_job)
# print(f"do sada uradjeno {status.status}: {status.request_counts.completed} of {status.request_counts.total}")


# Retrieve the file content from the API job 2
file_id = "file-coMsj2mJL0iCuUzCR9RsqyfI"
jsonl_file_path = 'response_data_resized.jsonl'
file_response = client.files.content(file_id)
with open(jsonl_file_path, 'w', encoding='utf-8') as f:
    for line in file_response.text.splitlines():
        json_line = json.loads(line)
        f.write(json.dumps(json_line, ensure_ascii=False) + '\n')
print(f"File content has been saved to '{jsonl_file_path}'")


# # Retrieve the file content from the API job 2
# file_id = "file-KywRConlOwtE9eW9p4N9IYiw"
# jsonl_file_path = 'error_drugi.jsonl'
# file_response = client.files.content(file_id)
# with open(jsonl_file_path, 'w', encoding='utf-8') as f:
#     for line in file_response.text.splitlines():
#         json_line = json.loads(line)
#         f.write(json.dumps(json_line, ensure_ascii=False) + '\n')
# print(f"File content has been saved to '{jsonl_file_path}'")

# # Retrieve the file content from the API job 3
# file_id = "file-1gJefnBRHK3P5jdCNc9yt1tQ"
# jsonl_file_path = 'response_data_drugi.jsonl'
# file_response = client.files.content(file_id)
# with open(jsonl_file_path, 'w', encoding='utf-8') as f:
#     for line in file_response.text.splitlines():
#         json_line = json.loads(line)
#         f.write(json.dumps(json_line, ensure_ascii=False) + '\n')
# print(f"File content has been saved to '{jsonl_file_path}'")

# # Retrieve the file content from the API job 4
# file_id = "file-kp6T2XgcOiOpqeCDuuzxJCKF"
# jsonl_file_path = 'response_data_treci.jsonl'
# file_response = client.files.content(file_id)
# with open(jsonl_file_path, 'w', encoding='utf-8') as f:
#     for line in file_response.text.splitlines():
#         json_line = json.loads(line)
#         f.write(json.dumps(json_line, ensure_ascii=False) + '\n')
# print(f"File content has been saved to '{jsonl_file_path}'")

# # Retrieve the file content from the API job 2
# file_id = "file-neN7trOOKrLQUpJORs2K7SVT"
# jsonl_file_path = 'error_treci.jsonl'
# file_response = client.files.content(file_id)
# with open(jsonl_file_path, 'w', encoding='utf-8') as f:
#     for line in file_response.text.splitlines():
#         json_line = json.loads(line)
#         f.write(json.dumps(json_line, ensure_ascii=False) + '\n')
# print(f"File content has been saved to '{jsonl_file_path}'")

# # Retrieve the file content from the API job 3
# file_id = "file-qHo2OGKS4fiPo3rnt24Q9DZW"
# jsonl_file_path = 'response_data_cetvrti.jsonl'
# file_response = client.files.content(file_id)
# with open(jsonl_file_path, 'w', encoding='utf-8') as f:
#     for line in file_response.text.splitlines():
#         json_line = json.loads(line)
#         f.write(json.dumps(json_line, ensure_ascii=False) + '\n')
# print(f"File content has been saved to '{jsonl_file_path}'")

# # Retrieve the file content from the API job 4
# file_id = "file-OqAOezkeF7mkAfVOjLuLFmee"
# jsonl_file_path = 'error_cetvrti.jsonl'
# file_response = client.files.content(file_id)
# with open(jsonl_file_path, 'w', encoding='utf-8') as f:
#     for line in file_response.text.splitlines():
#         json_line = json.loads(line)
#         f.write(json.dumps(json_line, ensure_ascii=False) + '\n')
# print(f"File content has been saved to '{jsonl_file_path}'")