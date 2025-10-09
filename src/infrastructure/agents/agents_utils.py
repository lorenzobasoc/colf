from google.genai import types

def build_string_content(prompt):
    return types.Content(role="user", parts=[types.Part(text=prompt)])

def read_prompt_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()