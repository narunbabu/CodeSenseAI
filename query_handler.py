# query_handler.py
import json
import uuid
import time # Import time
import re   # Import re
from datetime import datetime
from utils import extract_json, load_json # Import load_json
from constants import NEW_PROJECT_CREATION_PROMPT


class QueryHandler:
    def __init__(self, project_manager, clients_mapping):
        self.project_manager = project_manager
        self.clients_mapping = clients_mapping
        # Assuming openai_client is accessible or passed if needed as default
        # from project_config import openai_client # Or get default from mapping

    def process_query(self, input_query, client_type):
        pm = self.project_manager
        prompt = ""
        is_new_project_query = False

        # Check if the project is effectively empty (no summary or empty summary)
        if not pm.has_summary():
            is_new_project_query = True
            print("Processing query for a new/empty project.")

            prompt = NEW_PROJECT_CREATION_PROMPT.format(input_query=input_query)
        else:
            # Load the existing combined summary data
            combined = load_json(pm.combined_json_path)
            if not combined:
                # Handle error: Summary file exists but couldn't be loaded or is invalid
                print(f"Error: Could not load or parse summary file from {pm.combined_json_path}")
                # Fallback to treating as new project? Or return error? Let's return error.
                # Alternatively, could try to proceed without context, similar to new project.
                # For now, treat load failure as critical.
                # flash("Error loading project summary. Cannot process query.", "error") # Cannot flash from here
                return None # Indicate failure

            project_summary = combined.get("project_summary", "No project summary available.")
            file_summaries_str = ""
            # Ensure files exist and iterate safely
            files_data = combined.get("files", {})
            if not files_data:
                 print("Warning: Summary exists but contains no file entries. Treating as new project query.")
                 is_new_project_query = True
                 prompt = f"""This is a request possibly to add files to an existing but empty project, or modify project settings. The user query is: {input_query}
Project summary: {project_summary}
There are currently no files with summaries in the project.
Generate the necessary file(s) or instructions based on the query. If creating files, provide complete content.
Respond ONLY in JSON format, starting with [ and ending with ], following this structure exactly:
[{{"file_path": "relative/path/to/new_file.ext", 
"concise_summary": "Purpose of the file and what is its functionality. This will be used to understand the nature of this file for further queries.", 
"instructions_to_modify": "Instructions to code writer on how to write the code, it's functionality how it will serve/depend on other files of project. Note: Do not give code here"}}, ...]
Ensure the output is valid JSON. Do not include any other text, explanations, or markdown formatting outside the JSON structure. Ensure 'file_path' uses forward slashes '/' and is relative to the project root.
Your response here:
"""
            else:
                 for path, data in files_data.items():
                     # Check if data is a dictionary and has 'concise_summary'
                     if isinstance(data, dict):
                          concise_summary = data.get('concise_summary', 'No concise summary available.')
                          file_summaries_str += f"\nFile path: {path}\nConcise Summary: {concise_summary}\n"
                     else:
                          # Log unexpected data format
                          print(f"Warning: Unexpected data format for file '{path}' in summary.")
                          file_summaries_str += f"\nFile path: {path}\nConcise Summary: Error loading summary.\n"

                 # Construct the standard prompt for existing projects with summaries
                 prompt = f"""This is user query: {input_query}
Project summary: {project_summary}
File summaries: {file_summaries_str}
Select the files that are most relevant to the query and provide instructions for modifications. If the query requires creating a new file, provide the path and the complete code/content for the new file in 'instructions_to_modify'.
Respond ONLY in JSON format, starting with [ and ending with ], following this structure exactly:
[{{"file_path": "relative/path/to/file.ext", "concise_summary": "Brief explanation of how this file relates to the user query, or the purpose of a new file.", "instructions_to_modify": "Specific, actionable instructions for how the code in this file should be changed, OR the complete code/content for a new file."}}, ...]
Ensure the output is valid JSON. Do not include any other text, explanations, or markdown formatting outside the JSON structure. Ensure 'file_path' uses forward slashes '/' and is relative to the project root.
"""

        # --- Common Logic: Call LLM and Process Response ---

        # Get the selected client, handle potential missing client_type
        client = self.clients_mapping.get(client_type)
        if not client:
             print(f"Warning: Client type '{client_type}' not found in mapping. Using default (openai).")
             client = self.clients_mapping.get("openai")
             if not client:
                 # Major configuration issue if default is also missing
                 print("CRITICAL ERROR: Default LLM client 'openai' not found in configuration.")
                 # flash("Configuration error: Default LLM client not found.", "error") # Cannot flash
                 return None # Indicate critical failure

        print(f"--- Sending Prompt to {client_type} ---")
        print(prompt) # Optional: Log the prompt being sent
        print("--- End Prompt ---")

        start_time = time.time()
        try:
            response = client.get_response(prompt)
            print(f"--- Raw Response from {client_type} ---")
            print(response) # Optional: Log the raw response
            # save to a temperary local file to see how it has come
            temp_store_file_path = "ra_response_qh.txt"
            # load 
            try: # Added try-except for robustness during file write
                with open(temp_store_file_path, "w", encoding="utf-8") as file:
                    file.write(response)

                # print the response has been saved at path
                print(f"Saved LLM response details to {temp_store_file_path}")
            except Exception as e:
                print(f"Error loading LLM response details to {temp_store_file_path}: {e}")


            print("--- End Raw Response ---")
        except Exception as e:
            print(f"Error calling LLM client {client_type}: {e}")
            # Handle LLM call error, maybe return None or raise
            return None
        elapsed = time.time() - start_time
        print(f"LLM response received in {elapsed:.2f} seconds.")

        # Clean up the response (optional, depends on client behavior)
        # response_clean = re.sub(r'<thought>.*?</thought>', '', response, flags=re.DOTALL) # Keep if needed

        # Extract JSON using the utility function
        # Pass the raw response directly if cleaning is not reliable
        file_recommendations = extract_json(response)
        temp_store_file_path =  "file_recommendations.json"
        # load 
        try: # Added try-except for robustness during file write
            with open(temp_store_file_path, "w", encoding="utf-8") as file:
                json.dump(file_recommendations, file, indent=4) # Added indent

            # print the response has been saved at path
            print(f"Saved LLM response details to {temp_store_file_path}")
        except Exception as e:
            print(f"Error loading LLM response details to {temp_store_file_path}: {e}")

        # Validate the extracted structure (basic check)
        if not isinstance(file_recommendations, dict):
             print(f"Warning: LLM response was not parsed as a dict. Raw response:\n{response}")
             # Attempt to wrap if it looks like a single dict meant to be a list
             if isinstance(file_recommendations, list) and "file_path" in file_recommendations:
                 print("Attempting to wrap single list response into a dict.")
                 file_recommendations = file_recommendations[0]
             else:
                 # Store raw response as error message or keep raw
                 # Create a placeholder error entry
                 file_recommendations = {"error": "Failed to parse valid JSON list from LLM response. See raw_response.", "file_path": None, "instructions_to_modify": None}


        query_id = str(uuid.uuid4())
        query_entry = {
            "id": query_id,
            "timestamp": datetime.now().isoformat(), # Use ISO format for consistency
            "input_query": input_query,
            "client_type": client_type, # Store the client used
            "response": file_recommendations, # Store the parsed JSON (or error structure)
            "raw_response": response, # Store the original LLM response
            "response_time": elapsed,
            "is_new_project_query": is_new_project_query # Flag if it was treated as a new project query
        }

        try:
            history = pm.load_query_history()
            history.insert(0, query_entry) # Add new query to the beginning
            pm.save_query_history(history)
        except Exception as e:
            print(f"Error saving query history: {e}")
            # Handle history saving error, maybe log and return ID anyway?
            return query_id # Return ID even if saving failed, as query was processed

        return query_id
