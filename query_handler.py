# query_handler.py
import json
import uuid
import time # Import time
import re   # Import re
from datetime import datetime
from utils import extract_json, load_json, save_json # Import load_json
from constants import NEW_PROJECT_CREATION_PROMPT


class QueryHandler:
    def __init__(self, project_manager, clients_mapping):
        self.project_manager = project_manager
        self.clients_mapping = clients_mapping
        # Assuming openai_client is accessible or passed if needed as default
        # from project_config import openai_client # Or get default from mapping

#     def process_query(self, input_query, client_type):
#         pm = self.project_manager
#         prompt = ""
#         is_new_project_query = False
#         trigger_code_generation = False # Flag to signal code generation step

#         # Check if the project is effectively empty (no summary or empty summary)
#         if not pm.has_summary():
#             is_new_project_query = True
#             print("Processing query for a new/empty project.")
#             # Use the specific prompt for generating the project structure definition
#             prompt = NEW_PROJECT_CREATION_PROMPT.format(input_query=input_query)
#             # The expected response is the JSON structure resembling combined_code_summary.json
#         else:
#             # --- Existing Project Logic (remains largely the same) ---
#             combined = load_json(pm.combined_json_path)
#             if not combined:
#                 print(f"Error: Could not load or parse summary file from {pm.combined_json_path}")
#                 return None # Indicate failure

#             project_summary = combined.get("project_summary", "No project summary available.")
#             file_summaries_str = ""
#             files_data = combined.get("files", {})
#             if not files_data:
#                  print("Warning: Summary exists but contains no file entries. Treating as standard query (might create new files).")
#                  # Construct prompt assuming user might want to add files to an empty project structure
#                  prompt = f"""This is a user query for a project with a summary but no files yet: {input_query}
# Project summary: {project_summary}
# There are currently no files with summaries in the project.
# Generate the necessary file(s) or instructions based on the query. If creating files, provide the path and the complete code/content for the new file in 'instructions_to_modify'.
# Respond ONLY in JSON format, starting with [ and ending with ], following this structure exactly:
# [{{"file_path": "relative/path/to/new_file.ext", "concise_summary": "Purpose of the new file.", "instructions_to_modify": "Complete code/content for the new file."}}, ...]
# Ensure the output is valid JSON. Do not include any other text, explanations, or markdown formatting outside the JSON structure. Ensure 'file_path' uses forward slashes '/' and is relative to the project root.
# """
#             else:
#                  # Standard prompt for existing projects
#                  for path, data in files_data.items():
#                      if isinstance(data, dict):
#                           concise_summary = data.get('concise_summary', 'No concise summary available.')
#                           file_summaries_str += f"\nFile path: {path}\nConcise Summary: {concise_summary}\n"
#                      else:
#                           print(f"Warning: Unexpected data format for file '{path}' in summary.")
#                           file_summaries_str += f"\nFile path: {path}\nConcise Summary: Error loading summary.\n"

#                  prompt = f"""This is user query: {input_query}
# Project summary: {project_summary}
# File summaries: {file_summaries_str}
# Select the files that are most relevant to the query and provide instructions for modifications. If the query requires creating a new file, provide the path and the complete code/content for the new file in 'instructions_to_modify'.
# Respond ONLY in JSON format, starting with [ and ending with ], following this structure exactly:
# [{{"file_path": "relative/path/to/file.ext", "concise_summary": "Brief explanation of how this file relates to the user query, or the purpose of a new file.", "instructions_to_modify": "Specific, actionable instructions for how the code in this file should be changed, OR the complete code/content for a new file."}}, ...]
# Ensure the output is valid JSON. Do not include any other text, explanations, or markdown formatting outside the JSON structure. Ensure 'file_path' uses forward slashes '/' and is relative to the project root.
# """

#         # --- Common Logic: Call LLM and Process Response ---

#         client = self.clients_mapping.get(client_type)
#         if not client:
#              print(f"Warning: Client type '{client_type}' not found. Using default (openai).")
#              client = self.clients_mapping.get("openai") # Fallback to default
#              if not client:
#                  print("CRITICAL ERROR: Default LLM client 'openai' not found.")
#                  return None # Indicate critical failure

#         print(f"--- Sending Prompt to {client_type} ---")
#         # print(prompt) # Optional: Log the prompt
#         print("--- End Prompt ---")

#         start_time = time.time()
#         response = None
#         try:
#             response = client.get_response(prompt)
#             print(f"--- Raw Response from {client_type} ---")
#             # print(response) # Optional: Log the raw response
#             temp_store_file_path = pm.output_dir / f"raw_response_qh_{uuid.uuid4()}.txt"
#             try:
#                 with open(temp_store_file_path, "w", encoding="utf-8") as file:
#                     file.write(response)
#                 print(f"Saved raw LLM response details to {temp_store_file_path}")
#             except Exception as e:
#                 print(f"Error saving raw LLM response details to {temp_store_file_path}: {e}")
#             print("--- End Raw Response ---")
#         except Exception as e:
#             print(f"Error calling LLM client {client_type}: {e}")
#             return None # Indicate failure
#         elapsed = time.time() - start_time
#         print(f"LLM response received in {elapsed:.2f} seconds.")

#         # --- Process Response based on context (New Project vs Existing) ---
#         query_id = str(uuid.uuid4())
#         file_recommendations = None # Initialize

#         if is_new_project_query:
#             # Expecting the project structure JSON
#             project_structure_data = extract_json(response)

#             if not isinstance(project_structure_data, dict) or \
#                "project_name" not in project_structure_data or \
#                "files" not in project_structure_data or \
#                "project_summary" not in project_structure_data:
#                 print(f"Error: LLM response for new project was not the expected JSON structure. Raw:\n{response}")
#                 # Save error state in history
#                 file_recommendations = [{"error": "Failed to parse valid project structure JSON from LLM response.", "raw_response": response}]
#             else:
#                 print("Received valid project structure definition.")
#                 # Save this structure as the combined summary
#                 save_json(project_structure_data, pm.combined_json_path)
#                 print(f"Saved new project structure to {pm.combined_json_path}")
#                 pm.update_project_record({
#                     "last_summarized": datetime.now().isoformat(),
#                     "status": "summarized", # Mark as summarized now
#                     "file_count": project_structure_data.get("file_count", len(project_structure_data.get("files", {}))),
#                     "total_lines": project_structure_data.get("total_lines", 0) # Likely 0 initially
#                 })

#                 # Prepare the data for the *next* step (code generation)
#                 # This data will be stored in the query history's 'response' field
#                 files_to_generate = project_structure_data.get("files", {})
#                 file_recommendations = []
#                 for path, data in files_to_generate.items():
#                     if isinstance(data, dict):
#                         file_recommendations.append({
#                             "file_path": data.get("path", path),
#                             # Use concise summary for context if available
#                             "concise_summary": data.get("concise_summary", "New file to be generated."),
#                             # Use the ORIGINAL user query as the instruction for ALL files
#                             "instructions_to_modify": input_query
#                         })

#                 if file_recommendations:
#                     trigger_code_generation = True # Signal app.py to start modification flow
#                     print(f"Prepared {len(file_recommendations)} files for code generation step.")
#                 else:
#                     print("Warning: Project structure received, but no files listed for generation.")
#                     # Keep file_recommendations empty or add an info message?
#                     file_recommendations = [{"info": "Project structure created, but no files defined for generation."}]

#         else:
#             # --- Existing Project Response Processing (as before) ---
#             file_recommendations = extract_json(response)
#             temp_store_file_path_rec = pm.output_dir / f"file_recommendations_{uuid.uuid4()}.json"
#             try:
#                 with open(temp_store_file_path_rec, "w", encoding="utf-8") as file:
#                     json.dump(file_recommendations, file, indent=4)
#                 print(f"Saved file recommendations to {temp_store_file_path_rec}")
#             except Exception as e:
#                 print(f"Error saving file recommendations: {e}")

#             if not isinstance(file_recommendations, list):
#                  print(f"Warning: LLM response was not parsed as a valid JSON list. Raw response:\n{response}")
#                  if isinstance(file_recommendations, dict) and "file_path" in file_recommendations:
#                      print("Attempting to wrap single dictionary response into a list.")
#                      file_recommendations = [file_recommendations]
#                  else:
#                      file_recommendations = [{"error": "Failed to parse valid JSON list from LLM response.", "file_path": None, "instructions_to_modify": None}]

#         # --- Save Query History (Common Logic) ---
#         query_entry = {
#             "id": query_id,
#             "timestamp": datetime.now().isoformat(),
#             "input_query": input_query,
#             "client_type": client_type,
#             "response": file_recommendations, # Store parsed/prepared data
#             "raw_response": response,
#             "response_time": elapsed,
#             "is_new_project_query": is_new_project_query,
#             "trigger_code_generation": trigger_code_generation # Store the flag
#         }

#         try:
#             history = pm.load_query_history()
#             history.insert(0, query_entry)
#             pm.save_query_history(history)
#         except Exception as e:
#             print(f"Error saving query history: {e}")
#             # Return ID even if saving failed? Yes, processing happened.
#             return query_id, trigger_code_generation # Return both

#         # Return the query_id and the flag
#         return query_id, trigger_code_generation
    

    def process_query(self, input_query, client_type):
        pm = self.project_manager
        prompt = ""
        is_new_project_query = False
        trigger_code_generation = False  # Flag to signal code generation step

        # Check if the project is effectively empty: either no summary exists or there are no processable files.
        if not pm.has_summary() or pm.is_project_empty():
            is_new_project_query = True
            print("Processing query for a new/empty project (project is empty or lacks summary).")
            # Use the specific prompt for generating the project structure definition.
            prompt = NEW_PROJECT_CREATION_PROMPT.format(input_query=input_query)
            # The expected response is the JSON structure resembling combined_code_summary.json
        else:
            # --- Existing Project Logic (remains largely the same) ---
            combined = load_json(pm.combined_json_path)
            if not combined:
                print(f"Error: Could not load or parse summary file from {pm.combined_json_path}")
                return None  # Indicate failure

            project_summary = combined.get("project_summary", "No project summary available.")
            file_summaries_str = ""
            files_data = combined.get("files", {})
            if not files_data:
                print("Warning: Summary exists but contains no file entries. Treating as standard query (might create new files).")
                # Construct prompt assuming user might want to add files to an empty project structure
                prompt = f"""This is a user query for a project with a summary but no files yet: {input_query}
    Project summary: {project_summary}
    There are currently no files with summaries in the project.
    Generate the necessary file(s) or instructions based on the query. If creating files, provide the path and the complete code/content for the new file in 'instructions_to_modify'.
    Respond ONLY in JSON format, starting with [ and ending with ], following this structure exactly:
    [{{"file_path": "relative/path/to/new_file.ext", "concise_summary": "Purpose of the new file.", "instructions_to_modify": "Complete code/content for the new file."}}, ...]
    Ensure the output is valid JSON. Do not include any other text, explanations, or markdown formatting outside the JSON structure. Ensure 'file_path' uses forward slashes '/' and is relative to the project root.
    """
            else:
                # Standard prompt for existing projects
                for path, data in files_data.items():
                    if isinstance(data, dict):
                        concise_summary = data.get('concise_summary', 'No concise summary available.')
                        file_summaries_str += f"\nFile path: {path}\nConcise Summary: {concise_summary}\n"
                    else:
                        print(f"Warning: Unexpected data format for file '{path}' in summary.")
                        file_summaries_str += f"\nFile path: {path}\nConcise Summary: Error loading summary.\n"

                prompt = f"""This is user query: {input_query}
    Project summary: {project_summary}
    File summaries: {file_summaries_str}
    Select the files that are most relevant to the query and provide instructions for modifications. If the query requires creating a new file, provide the path and the complete code/content for the new file in 'instructions_to_modify'.
    Respond ONLY in JSON format, starting with [ and ending with ], following this structure exactly:
    [{{"file_path": "relative/path/to/file.ext", "concise_summary": "Brief explanation of how this file relates to the user query, or the purpose of a new file.", "instructions_to_modify": "Specific, actionable instructions for how the code in this file should be changed, OR the complete code/content for a new file."}}, ...]
    Ensure the output is valid JSON. Do not include any other text, explanations, or markdown formatting outside the JSON structure. Ensure 'file_path' uses forward slashes '/' and is relative to the project root.
    """
        # --- Common Logic: Call LLM and Process Response ---

        client = self.clients_mapping.get(client_type)
        if not client:
            print(f"Warning: Client type '{client_type}' not found. Using default (openai).")
            client = self.clients_mapping.get("openai")  # Fallback to default
            if not client:
                print("CRITICAL ERROR: Default LLM client 'openai' not found.")
                return None  # Indicate critical failure

        print(f"--- Sending Prompt to {client_type} ---")
        print("--- End Prompt ---")

        start_time = time.time()
        response = None
        try:
            response = client.get_response(prompt)
            print(f"--- Raw Response from {client_type} ---")
            temp_store_file_path = pm.output_dir / f"raw_response_qh_{uuid.uuid4()}.txt"
            try:
                with open(temp_store_file_path, "w", encoding="utf-8") as file:
                    file.write(response)
                print(f"Saved raw LLM response details to {temp_store_file_path}")
            except Exception as e:
                print(f"Error saving raw LLM response details to {temp_store_file_path}: {e}")
            print("--- End Raw Response ---")
        except Exception as e:
            print(f"Error calling LLM client {client_type}: {e}")
            return None  # Indicate failure
        elapsed = time.time() - start_time
        print(f"LLM response received in {elapsed:.2f} seconds.")

        # --- Process Response based on context (New Project vs Existing) ---
        query_id = str(uuid.uuid4())
        file_recommendations = None  # Initialize

        if is_new_project_query:
            # Expecting the project structure JSON
            project_structure_data = extract_json(response)

            if not isinstance(project_structure_data, dict) or \
            "project_name" not in project_structure_data or \
            "files" not in project_structure_data or \
            "project_summary" not in project_structure_data:
                print(f"Error: LLM response for new project was not the expected JSON structure. Raw:\n{response}")
                # Save error state in history
                file_recommendations = [{"error": "Failed to parse valid project structure JSON from LLM response.", "raw_response": response}]
            else:
                print("Received valid project structure definition.")
                # Save this structure as the combined summary
                save_json(project_structure_data, pm.combined_json_path)
                print(f"Saved new project structure to {pm.combined_json_path}")
                pm.update_project_record({
                    "last_summarized": datetime.now().isoformat(),
                    "status": "summarized",  # Mark as summarized now
                    "file_count": project_structure_data.get("file_count", len(project_structure_data.get("files", {}))),
                    "total_lines": project_structure_data.get("total_lines", 0)  # Likely 0 initially
                })

                # Prepare the data for the *next* step (code generation)
                files_to_generate = project_structure_data.get("files", {})
                file_recommendations = []
                for path, data in files_to_generate.items():
                    if isinstance(data, dict):
                        file_recommendations.append({
                            "file_path": data.get("path", path),
                            "concise_summary": data.get("concise_summary", "New file to be generated."),
                            "instructions_to_modify": input_query  # Use the ORIGINAL user query as the instruction for ALL files
                        })

                if file_recommendations:
                    trigger_code_generation = True  # Signal app.py to start modification flow
                    print(f"Prepared {len(file_recommendations)} files for code generation step.")
                else:
                    print("Warning: Project structure received, but no files listed for generation.")
                    file_recommendations = [{"info": "Project structure created, but no files defined for generation."}]
        else:
            # --- Existing Project Response Processing (as before) ---
            file_recommendations = extract_json(response)
            temp_store_file_path_rec = pm.output_dir / f"file_recommendations_{uuid.uuid4()}.json"
            try:
                with open(temp_store_file_path_rec, "w", encoding="utf-8") as file:
                    json.dump(file_recommendations, file, indent=4)
                print(f"Saved file recommendations to {temp_store_file_path_rec}")
            except Exception as e:
                print(f"Error saving file recommendations: {e}")

            if not isinstance(file_recommendations, list):
                print(f"Warning: LLM response was not parsed as a valid JSON list. Raw response:\n{response}")
                if isinstance(file_recommendations, dict) and "file_path" in file_recommendations:
                    print("Attempting to wrap single dictionary response into a list.")
                    file_recommendations = [file_recommendations]
                else:
                    file_recommendations = [{"error": "Failed to parse valid JSON list from LLM response.", "file_path": None, "instructions_to_modify": None}]

        # --- Save Query History (Common Logic) ---
        query_entry = {
            "id": query_id,
            "timestamp": datetime.now().isoformat(),
            "input_query": input_query,
            "client_type": client_type,
            "response": file_recommendations,  # Store parsed/prepared data
            "raw_response": response,
            "response_time": elapsed,
            "is_new_project_query": is_new_project_query,
            "trigger_code_generation": trigger_code_generation
        }

        try:
            history = pm.load_query_history()
            history.insert(0, query_entry)
            pm.save_query_history(history)
        except Exception as e:
            print(f"Error saving query history: {e}")
            return query_id, trigger_code_generation

        return query_id, trigger_code_generation
    
    
