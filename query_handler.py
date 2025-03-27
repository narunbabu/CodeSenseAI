# query_handler.py
import json
import uuid
import time # Import time
import re   # Import re
from datetime import datetime
from utils import extract_json, load_json # Import load_json

class QueryHandler:
    def __init__(self, project_manager, clients_mapping):
        self.project_manager = project_manager
        self.clients_mapping = clients_mapping
        # Assuming openai_client is accessible or passed if needed as default
        # from project_config import openai_client # Or get default from mapping

    def process_query(self, input_query, client_type):
        pm = self.project_manager
        # Load the combined summary data
        # Use load_json utility for consistency and error handling
        combined = load_json(pm.combined_json_path)
        if not combined:
            # Handle error: Summary file not found or invalid
            print(f"Error: Could not load summary file from {pm.combined_json_path}")
            # Optionally raise an exception or return an indicator of failure
            return None # Indicate failure

        project_summary = combined.get("project_summary", "No project summary available.")
        file_summaries_str = ""
        # Ensure files exist and iterate safely
        for path, data in combined.get("files", {}).items():
            # Check if data is a dictionary and has 'concise_summary'
            if isinstance(data, dict):
                 concise_summary = data.get('concise_summary', 'No concise summary available.')
                 file_summaries_str += f"\nFile path: {path}\nConcise Summary: {concise_summary}\n"
            else:
                 # Log unexpected data format
                 print(f"Warning: Unexpected data format for file '{path}' in summary.")
                 file_summaries_str += f"\nFile path: {path}\nConcise Summary: Error loading summary.\n"


        # Construct the prompt exactly as requested
        prompt = f"""This is user query: {input_query}
Project summary: {project_summary}
File summaries: {file_summaries_str}
Select the files that are most relevant to the query and provide instructions for modifications.
Respond ONLY in JSON format, starting with [ and ending with ], following this structure exactly:
[{{"file_path": "relative/path/to/file.ext", "concise_summary": "Brief explanation of how this file relates to the user query.", "instructions_to_modify": "Specific, actionable instructions for how the code in this file should be changed to meet the user query."}}, ...]
Ensure the output is valid JSON. Do not include any other text, explanations, or markdown formatting outside the JSON structure.
"""

        # Get the selected client, handle potential missing client_type
        # Use a default client (e.g., openai_client) if the type is invalid or not found
        client = self.clients_mapping.get(client_type)
        if not client:
             print(f"Warning: Client type '{client_type}' not found in mapping. Using default.")
             # Attempt to get a default client, e.g., 'openai'
             client = self.clients_mapping.get("openai")
             if not client:
                 # Major configuration issue if default is also missing
                 raise ValueError("Default LLM client 'openai' not found in configuration.")

        start_time = time.time()
        try:
            response = client.get_response(prompt)
        except Exception as e:
            print(f"Error calling LLM client {client_type}: {e}")
            # Handle LLM call error, maybe return None or raise
            return None
        elapsed = time.time() - start_time

        # Clean up the response (optional, depends on client behavior)
        # response_clean = re.sub(r'<thought>.*?</thought>', '', response, flags=re.DOTALL) # Keep if needed

        # Extract JSON using the utility function
        # Pass the raw response directly if cleaning is not reliable
        file_recommendations = extract_json(response)

        # Validate the extracted structure (basic check)
        if not isinstance(file_recommendations, list):
             print(f"Warning: LLM response was not parsed as a list. Raw response:\n{response}")
             # Attempt to wrap if it looks like a single dict meant to be a list
             if isinstance(file_recommendations, dict) and "file_path" in file_recommendations:
                 file_recommendations = [file_recommendations]
             else:
                 # Store raw response as error message or keep raw
                 file_recommendations = [{"error": "Failed to parse valid JSON list from LLM response."}]


        query_id = str(uuid.uuid4())
        query_entry = {
            "id": query_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "input_query": input_query,
            "client_type": client_type, # Store the client used
            "response": file_recommendations, # Store the parsed JSON (or error structure)
            "raw_response": response, # Store the original LLM response
            "response_time": elapsed
        }

        try:
            history = pm.load_query_history()
            history.append(query_entry)
            pm.save_query_history(history)
        except Exception as e:
            print(f"Error saving query history: {e}")
            # Handle history saving error, maybe log and return ID anyway?
            return query_id # Return ID even if saving failed, as query was processed

        return query_id