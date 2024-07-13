import json
from openai import OpenAI
client = OpenAI()

# upload batch file
# batch_input_file = client.files.create(
#   file=open("delfi_img_batch.jsonl", "rb"),
#   purpose="batch"
# )



# submit job
# batch_input_file_id = ############### "file-xi6VCskpxMpnwDjWa8dDGXPV"

# client.batches.create(
#     input_file_id=batch_input_file_id,
#     endpoint="/v1/chat/completions",
#     completion_window="24h",
#     metadata={
#       "description": "final delfi images job"
#     }
# )


# Check status of the batch job
# batch_job = "batch_VbTM5MQ3UokQon9HZYUXZgyf"
# status = client.batches.retrieve(batch_job)
# print(f"do sada uradjeno {status.status}: {status.request_counts.completed} of {status.request_counts.total}")


# Retrieve the file content from the API
file_id = "file-8aev1DjZ5iIVLMOCEivKiYdx"
file_response = client.files.content(file_id)

# Open the file for writing in JSONL format
jsonl_file_path = 'response_data.jsonl'

with open(jsonl_file_path, 'w', encoding='utf-8') as f:
    # Assuming each line in the response is a JSON object
    for line in file_response.text.splitlines():
        json_line = json.loads(line)
        
        custom_id = json_line.get("custom_id")
        content = json_line.get("response", {}).get("body", {}).get("choices", [])[0].get("message", {}).get("content")

# Create the simplified dictionary
        simplified_data = {
            "custom_id": custom_id,
            "content": content
        }

        # Save to a JSONL file
    jsonl_file_path = 'response_data.jsonl'
    with open(jsonl_file_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(simplified_data, ensure_ascii=False, indent=4) + '\n')

    print(f"Simplified data has been saved to '{jsonl_file_path}'")