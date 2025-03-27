# modification_handler.py
import os
import json
import time
import uuid
import difflib
from datetime import datetime
from pathlib import Path # Use Path object
from utils import read_file_content, write_file_content, backup_file, save_json, load_json # Ensure save/load_json are imported
import re
class ModificationHandler:
    def __init__(self, project_manager, clients_mapping):
        self.pm = project_manager
        self.clients_mapping = clients_mapping
        # Create a dedicated directory for temporary modification data
        self.temp_dir = Path(self.pm.output_dir) / 'temp_mods'
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _get_temp_filepath(self, temp_id):
        """Helper to get the path to the temporary data file."""
        return self.temp_dir / f"{temp_id}.json"

    def prepare_modification_prompt(self, query_id, client_type):
        """
        Prepares modification prompt, saves large data to a temp file.
        Returns:
            tuple: (temp_id, prompt_for_display, small_session_data) or (None, None, None)
        """
        history = self.pm.load_query_history()
        query_entry = next((item for item in history if item.get("id") == query_id), None)

        if not query_entry:
            print(f"Error: Query ID {query_id} not found.")
            return None, None, None

        # ... (rest of the logic to validate query_entry and files_to_modify_data remains the same) ...
        files_to_modify_data = query_entry.get("response", [])
        if not isinstance(files_to_modify_data, list) or not files_to_modify_data:
            print(f"Error: No valid files/instructions found in query response for {query_id}.")
            return None, None, None

        valid_files_data = [
            item for item in files_to_modify_data
            if isinstance(item, dict) and item.get("file_path") and item.get("instructions_to_modify")
        ]
        if not valid_files_data:
            print(f"Error: No files with modification instructions found for query {query_id}.")
            return None, None, None


        prompt = f"""
You are a code modification expert. I need you to modify the following files according to this requirement:

USER REQUIREMENT:
{query_entry.get('input_query', '')}

You will be given the current code and specific modification instructions for one or more files.
Carefully apply the instructions to the provided code.
Respond ONLY with the complete, modified code for each file, enclosed in triple backticks, clearly indicating the file path before each block.

Example format of your response:
```html public/index.html
<!DOCTYPE html>
<html>
...your modified code here...
</html>
```

```javascript src/App.js
import React from 'react';
...your modified code here...
```

IMPORTANT:
1. Provide the COMPLETE modified file, not just the changes
2. Maintain the same indentation style as the original
3. Include all imports and dependencies
4. Do not omit any sections of the code
5. Make only the changes needed to fulfill the requirements

Here are the files to modify:
"""
        file_contents = {}
        files_processed_count = 0
        project_base_path = Path(self.pm.project_path).resolve() # Use resolved Path

        for file_info in valid_files_data:
            file_path_str = file_info.get("file_path", "").replace("\\", "/")
            # Construct full path safely using Path objects
            try:
                 # Resolve potentially relative paths from the query against the project base
                 full_path = (project_base_path / file_path_str).resolve()
                 # Security check: Ensure the path stays within the project directory
                 if not full_path.is_relative_to(project_base_path):
                      print(f"Warning: Skipping potentially unsafe path outside project: {file_path_str}")
                      continue
            except Exception as e: # Catch potential errors during path resolution
                 print(f"Warning: Error processing path '{file_path_str}': {e}. Skipping.")
                 continue


            content = read_file_content(str(full_path)) # read_file_content expects string path
            if content is not None:
                instructions = file_info.get('instructions_to_modify', '').strip()
                # Use relative path in prompt for clarity
                relative_path_for_prompt = str(full_path.relative_to(project_base_path)).replace("\\", "/")
                prompt += f"\n=== FILE: {relative_path_for_prompt} ===\nINSTRUCTIONS: {instructions}\nCURRENT CODE:\n```{content}\n```\n"
                # Store content keyed by the normalized relative path used in prompt
                file_contents[relative_path_for_prompt] = content
                files_processed_count += 1
            else:
                 print(f"Warning: Could not read content for file: {full_path}")


        if files_processed_count == 0:
             print(f"Error: Could not read content for any requested files for query {query_id}.")
             return None, None, None

        temp_id = str(uuid.uuid4())

        # Data to be saved to the temporary file (large parts)
        large_data_to_save = {
            "modification_prompt": prompt,
            "original_file_contents": file_contents
        }

        # Save the large data to the temp file
        temp_filepath = self._get_temp_filepath(temp_id)
        try:
            save_json(large_data_to_save, temp_filepath)
            print(f"Saved large modification data to {temp_filepath}")
        except Exception as e:
            print(f"Error saving temporary modification data to {temp_filepath}: {e}")
            return None, None, None

        # Small data to be stored in the session
        small_session_data = {
            "query_id": query_id,
            "modification_client_type": client_type,
            # Store list of file paths involved for potential future use/validation
            "involved_files": list(file_contents.keys())
        }

        # Return temp_id, the prompt (for display only), and the small session data dict
        return temp_id, prompt, small_session_data

    def _parse_llm_code_modification_response(self, response_text):
        """
        Parses the LLM response to extract modified code blocks for each file.
        Expects format:
        === FILE: path/to/file.ext ===
        ```language
        ... code ...
        ``` {data-source-line="722"}
        """
        # modifications = {}
        modified_files = {}
        # Regex to find file path and the code block immediately following it
        # Handles optional language hint after ```
        pattern = r'```(?:[\w.]+)?\s*([\w./\\-]+)(?:\s+//.*?|(?:\s*;.*?|\s+.*?))?(?:\n)(.*?)```'
        # matches = pattern.findall(response_text)
        matches = re.finditer(pattern, response_text, re.DOTALL)

        for match in matches:
            filename = match.group(1).strip()
            print(filename)
            code = match.group(2).strip()
            modified_files[filename] = code
        return modified_files

        # if not matches:
        #      # Fallback: Maybe the LLM just gave one block without headers?
        #      # Try finding a single code block
        #      single_block_match = re.search(r'```(?:[a-zA-Z0-9_.-]*)?\s*(.*?)\s*```', response_text, re.DOTALL)
        #      if single_block_match:
        #          # Problem: We don't know which file this belongs to if multiple were requested.
        #          # This is ambiguous. We might return an error or make a guess if only one file was in the prompt.
        #          print("Warning: Ambiguous response. Found a single code block without file headers.")
        #          # For now, let's not assign it if we can't be sure.
        #          # If only one file was requested, we could potentially assign it.
        #          return None # Indicate parsing failure due to ambiguity or lack of structure

        # for file_path, code in matches:
        #     # Normalize path and remove potential leading/trailing whitespace
        #     normalized_path = file_path.strip().replace("\\", "/")
        #     modifications[normalized_path] = code.strip()

        # if not modifications:
        #      print("Error: Could not parse any code blocks in the expected format from LLM response.")
        #      return None # Indicate failure

        # return modifications

    def process_modifications(self, temp_id, small_session_data):
        """
        Processes modifications, response generation from LLM using (prompt) data read from temp file and session.
        Args:
            temp_id (str): The temporary modification identifier.
            small_session_data (dict): Data retrieved from the session.
        Returns:
            dict: {'preview': preview_list, 'llm_response': ..., 'llm_response_time': ...}
                  or None on failure.
        """
        print(f"In process_modifications with temp_id: {temp_id}")
        if not small_session_data or not temp_id:
            print(f"Error: Missing temp_id or session data for process_modifications.")
            return None

        client_type = small_session_data.get("modification_client_type")
        query_id = small_session_data.get("query_id") # For logging context

        if not client_type or not query_id:
            print(f"Error: Missing client_type or query_id in session data.")
            return None

        # Load large data (prompt, original contents) from the temp file
        temp_filepath = self._get_temp_filepath(temp_id)
        large_data = load_json(temp_filepath)

        if not large_data:
            print(f"Error: Could not load temporary modification data from {temp_filepath}.")
            return None

        prompt = large_data.get("modification_prompt")
        print(f"Prompt in process_modifications:\n{prompt[:1000]}")
        original_contents = large_data.get("original_file_contents")

        if not prompt or not original_contents:
            print(f"Error: Missing prompt or original_contents in loaded temp data from {temp_filepath}.")
            return None

        # Get the LLM client instance
        client = self.clients_mapping.get(client_type)
        if not client:
            print(f"Error: Modification client type '{client_type}' not found.")
            return None

        print(f"Sending modification prompt to LLM client: {client_type} for Query ID: {query_id} (Temp ID: {temp_id})")
        start_time = time.time()
        llm_response_raw = None
        llm_error = None
        try:
            # ... (LLM call logic remains the same) ...
            if hasattr(client, 'get_response'):
                llm_response_raw = client.get_response(prompt)
            else:
                raise NotImplementedError(f"LLM interaction method not defined for client type: {client_type}")

        except Exception as e:
            llm_error = e
            print(f"Error calling LLM ({client_type}) for code modification: {e}")
            # Return None to indicate failure
            return None
        finally:
            elapsed = time.time() - start_time
            print(f"LLM response received (or error occurred) in {elapsed:.2f} seconds.")
            # Prepare response details for return (will be saved to session by caller)
            llm_response_details = {
                "llm_response": llm_response_raw if llm_response_raw else f"Error during LLM call: {llm_error}",
                "llm_response_time": elapsed
            }
        temp_store_file_path = self.output_dir / "llm_response_details.json"
        # Dump the JSON file
        with open(temp_store_file_path, "w", encoding="utf-8") as file:
            json.dump(llm_response_details, file)
        # print the response has been saved at path
        print(f"Saved LLM response details to {temp_store_file_path}")
        

        if llm_response_raw is None:
            print("Error: LLM did not return a response.")
            # llm_response_details contains the error, return it with None preview
            return {"preview": None, **llm_response_details} # Indicate failure but provide LLM details

        # Parse the actual LLM response
        parsed_modifications = self._parse_llm_code_modification_response(llm_response_raw)
        temp_store_file_path = self.output_dir / "parsed_modifications.json"
        # Dump the JSON file
        with open(temp_store_file_path, "w", encoding="utf-8") as file:
            json.dump(llm_response_details, file)
        # print the response has been saved at path
        print(f"Saved parsed modifications to {temp_store_file_path}")
        
        if parsed_modifications is None:
             print("Error: Failed to parse modifications from LLM response.")
             # Return None preview, but include LLM details
             return {"preview": None, **llm_response_details}

        # --- Generate preview with diffs ---
        preview_modifications = []
        # Ensure we only generate previews for files requested AND successfully parsed
        for file_path, old_code in original_contents.items():
             normalized_file_path = file_path.replace("\\", "/") # Path keys in original_contents are already normalized
             if normalized_file_path in parsed_modifications:
                 new_code = parsed_modifications[normalized_file_path]
                 # ... (Diff generation logic remains the same) ...
                 diff_lines = list(difflib.ndiff(old_code.splitlines(), new_code.splitlines()))
                 highlighted_diff = []
                 for line in diff_lines:
                     escaped_line_content = line[2:].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                     if line.startswith('+ '):
                         highlighted_diff.append(f'<span class="diff-added">{line[0]} {escaped_line_content}</span>')
                     elif line.startswith('- '):
                         highlighted_diff.append(f'<span class="diff-removed">{line[0]} {escaped_line_content}</span>')
                     elif line.startswith('? '):
                         highlighted_diff.append(f'<span class="diff-changed-marker">{line[0]} {escaped_line_content}</span>')
                     else:
                         highlighted_diff.append(f'  {escaped_line_content}')

                 preview_modifications.append({
                     "file_path": normalized_file_path,
                     "old_code": old_code,
                     "new_code": new_code,
                     "highlighted_diff": "\n".join(highlighted_diff)
                 })
             else:
                  print(f"Warning: LLM did not provide modified code for requested file: {normalized_file_path}")

        if not preview_modifications:
             print("Error: No valid modifications could be prepared for preview (parsing or LLM response issue).")
             return {"preview": None, **llm_response_details} # Indicate failure but provide LLM details

        # Return successful preview along with LLM details
        return {"preview": preview_modifications, **llm_response_details}
    
    def apply_modifications(self, temp_id, small_session_data, modifications_to_apply):
        """
        Applies the modifications, saves history, and cleans up temp file.
        Args:
            temp_id (str): The temporary modification identifier.
            small_session_data (dict): Data from session (incl. query_id, client_type, LLM details).
            modifications_to_apply (list): List of dicts with 'file_path' and 'new_code'.
        Returns:
            str: The ID of the modification record, or None on failure.
        """
        pm = self.pm
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        modification_results = []

        if not small_session_data or not temp_id:
            print("Error: Invalid or missing session data/temp_id provided to apply_modifications.")
            return None
        query_id = small_session_data.get("query_id")
        client_type = small_session_data.get("modification_client_type") # For history record
        llm_response = small_session_data.get("llm_response", "") # Get LLM details saved by caller
        llm_response_time = small_session_data.get("llm_response_time", 0)

        if not query_id or not client_type:
            print("Error: Missing query_id or client_type in session data during apply_modifications.")
            return None

        if not isinstance(modifications_to_apply, list):
             print("Error: apply_modifications received invalid modifications data format.")
             return None

        applied_files_count = 0
        project_base_path = Path(self.pm.project_path).resolve() # Use resolved Path

        for mod_info in modifications_to_apply:
            # ... (File path normalization, security check, backup, and write logic remains the same) ...
            if not isinstance(mod_info, dict) or "file_path" not in mod_info or "new_code" not in mod_info:
                 print(f"Warning: Skipping invalid modification item: {mod_info}")
                 continue

            file_path_str = mod_info["file_path"].replace("\\", "/") # Normalize path from input JSON
            new_code = mod_info["new_code"]

            # Construct full path safely
            try:
                full_path = (project_base_path / file_path_str).resolve()
                # Security check
                if not full_path.is_relative_to(project_base_path):
                     print(f"Error: Attempted write outside project directory: {file_path_str}. Skipping.")
                     modification_results.append({
                         "file_path": file_path_str, "status": "error",
                         "message": "Write outside project directory denied"
                     })
                     continue
            except Exception as e:
                 print(f"Error resolving path '{file_path_str}' for writing: {e}. Skipping.")
                 modification_results.append({
                     "file_path": file_path_str, "status": "error",
                     "message": f"Path resolution error: {e}"
                 })
                 continue

            # Backup original file before writing
            pm.backups_dir.mkdir(parents=True, exist_ok=True)
            backup_success = backup_file(str(full_path), timestamp, backups_dir=pm.backups_dir)
            if not backup_success:
                print(f"Warning: Failed to create backup for {full_path}. Proceeding...")

            # Write the new content
            success = write_file_content(str(full_path), new_code)
            # ... (Append to modification_results based on success/failure) ...
            if success:
                modification_results.append({
                    "file_path": file_path_str, "status": "success",
                    "message": "File modified successfully"
                })
                applied_files_count += 1
            else:
                modification_results.append({
                    "file_path": file_path_str, "status": "error",
                    "message": "Failed to write modified content"
                })


        if applied_files_count == 0 and modifications_to_apply:
             print("Error: Failed to apply modifications to any file.")
             # Do NOT delete temp file yet, might be needed for retry/debug
             return None # Indicate complete failure

        # Load history and add entry
        history = pm.load_modifications_history()
        modification_entry = {
            "id": str(uuid.uuid4()),
            "query_id": query_id,
            "timestamp": timestamp,
            "files_modified": modification_results,
            # Include LLM details from session data
            "llm_response": llm_response,
            "response_time": llm_response_time,
            "modification_client_type": client_type
        }
        history.append(modification_entry)
        pm.save_modifications_history(history)

        # --- Clean up the temporary file ---
        temp_filepath = self._get_temp_filepath(temp_id)
        try:
            temp_filepath.unlink(missing_ok=True) # Delete the file, ignore if already gone
            print(f"Cleaned up temporary modification file: {temp_filepath}")
        except Exception as e:
            print(f"Warning: Failed to clean up temporary file {temp_filepath}: {e}")

        # Session cleanup happens in the Flask route

        return modification_entry["id"] # Return ID of the successful modification record
    
    def revert_file(self, modification_id, file_path):
        # ... (Revert logic remains largely the same) ...
        # Ensure it uses safe path joining and normalization
        pm = self.pm
        record = next((mod for mod in pm.load_modifications_history() if mod.get("id") == modification_id), None)
        # ... (rest of revert logic) ...
        if not record:
            print(f"Error: Modification record {modification_id} not found.")
            return False

        timestamp_str = record.get("timestamp")
        if not timestamp_str:
             print(f"Error: Timestamp missing in modification record {modification_id}.")
             return False

        formatted_timestamp = None
        try:
            dt_obj = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            formatted_timestamp = dt_obj.strftime("%Y-%m-%d_%H-%M-%S")
        except (ValueError, TypeError):
             formatted_timestamp = timestamp_str.replace(":", "-").replace(" ", "_")
             print(f"Warning: Using fallback timestamp format '{formatted_timestamp}' for revert.")

        if not formatted_timestamp: return False

        normalized_file_path = file_path.replace("\\", "/")
        backup_filename_base = normalized_file_path.replace('/', '_')
        backup_filename = f"{backup_filename_base}_{formatted_timestamp}.bak"
        backup_path = pm.backups_dir / backup_filename

        if not backup_path.exists():
            print(f"Error: Backup file not found: {backup_path}")
            return False

        backup_content = read_file_content(str(backup_path))
        if backup_content is None: return False

        project_base_path = Path(pm.project_path).resolve()
        try:
            full_path = (project_base_path / normalized_file_path).resolve()
            if not full_path.is_relative_to(project_base_path):
                 print(f"Error: Revert target path outside project: {normalized_file_path}.")
                 return False
        except Exception as e:
             print(f"Error resolving path '{normalized_file_path}' for revert: {e}.")
             return False


        print(f"Reverting file '{normalized_file_path}' from backup '{backup_filename}'")
        return write_file_content(str(full_path), backup_content)

    def cleanup_temp_file(self, temp_id):
        """Explicitly cleans up a temporary file if needed (e.g., on cancel)."""
        if not temp_id: return
        temp_filepath = self._get_temp_filepath(temp_id)
        try:
            deleted = temp_filepath.unlink(missing_ok=True)
            if deleted:
                print(f"Cleaned up temporary modification file on cancel/error: {temp_filepath}")
        except Exception as e:
            print(f"Warning: Failed to clean up temporary file {temp_filepath} on cancel/error: {e}")