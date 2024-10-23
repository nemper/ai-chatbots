import ast

def extract_unique_dicts(file_path):
    unique_dicts = []
    seen_dicts = set()

    with open(file_path, 'r') as file:
        for line in file:
            try:
                # Convert the string to a dictionary
                dictionary = ast.literal_eval(line.strip())
                
                # Remove the 'id' field to ignore it when checking for uniqueness
                dict_without_id = {k: v for k, v in dictionary.items() if k != 'id'}
                
                # Convert the dictionary (without 'id') to a frozenset of key-value pairs to make it hashable
                dict_as_tuple = frozenset(dict_without_id.items())
                
                # Check if the dictionary has been seen before
                if dict_as_tuple not in seen_dicts:
                    seen_dicts.add(dict_as_tuple)
                    unique_dicts.append(dictionary)
            
            except (ValueError, SyntaxError):
                print(f"Skipping invalid line: {line.strip()}")
    
    return unique_dicts

# Specify the path to the input file
input_file_path = 'api.txt'

# Extract unique dictionaries
unique_dicts = extract_unique_dicts(input_file_path)

# Print or save the unique dictionaries
for item in unique_dicts:
    print(item)
