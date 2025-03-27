import os
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime
# Ensure AGGREGATED_SUMMARY_PROMPT is imported
from constants import HTML_COMBINED_REPORT_TEMPLATE, DEFAULT_EXCLUDES, AGGREGATED_SUMMARY_PROMPT
from utils import load_json, save_json

def read_file_content(file_path):
    """Utility to read file content safely."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

class ProjectManager:
    def __init__(self, project_path, output_dir='./projects'):
        self.project_path = project_path
        self.project_name = Path(project_path).name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir = self.output_dir / 'backups'
        self.backups_dir.mkdir(exist_ok=True)
        print(f"ProjectManager: self.output_dir: {self.output_dir}")
        self.combined_json_path = self.output_dir / 'combined_code_summary.json'
        self.combined_html_path = self.output_dir / 'combined_code_summary.html'
        self.project_record_path = self.output_dir / 'project_record.json'
        self.query_history_path = self.output_dir / 'query_history.json'
        self.modifications_history_path = self.output_dir / 'modifications_history.json'
        self.file_hashes_path = self.output_dir / 'file_hashes.json'
        if not self.project_record_path.exists():
            self._init_project_record()
        if not self.file_hashes_path.exists():
            save_json({}, self.file_hashes_path)

    def _init_project_record(self):
        record = {
            "project_name": self.project_name,
            "source_code_path": self.project_path,
            "local_storage_path": str(self.output_dir),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_summarized": None,
            "summary_count": 0,
            "query_count": 0,
            "modification_count": 0,
            "file_count": 0,
            "total_lines": 0,
            "status": "initialized",
            "file_selection": []  # Optionally store file selection details
        }
        save_json(record, self.project_record_path)

    def get_project_info(self):
        return {
            "project_name": self.project_name,
            "source_code_path": self.project_path,
            "local_storage_path": str(self.output_dir),
            "output_base": str(self.output_dir.parent),
            "output_dir": str(self.output_dir)
        }

    def get_project_record(self):
        if not self.project_record_path.exists():
            self._init_project_record()
        # Ensure loading uses the utility function for consistency
        return load_json(self.project_record_path)

    def update_project_record(self, data):
        record = self.get_project_record()
        # Ensure record is loaded correctly before updating
        if record:
            record.update(data)
            save_json(record, self.project_record_path)
        else:
            print(f"Warning: Could not load project record to update for {self.project_name}")
            # Optionally re-initialize if load failed critically
            # self._init_project_record()
            # record = load_json(self.project_record_path)
            # if record:
            #     record.update(data)
            #     save_json(record, self.project_record_path)

    def has_summary(self):
        return self.combined_json_path.exists()

    def get_summary_status(self):
        record = self.get_project_record()
        if not self.has_summary():
            return {"status": "not_summarized", "message": "Project has not been summarized yet."}

        summary_data = load_json(self.combined_json_path)
        if not summary_data:
            # Update record status if summary load fails
            self.update_project_record({"status": "error_loading_summary"})
            return {"status": "error_loading_summary", "message": "Failed to load existing summary data."}

        # Check for modified files – this call also updates file_hashes.json
        modified_files = self.get_modified_files()
        if modified_files:
            # Update record status
            self.update_project_record({"status": "needs_update"})
            return {
                "status": "needs_update",
                "message": f"Project summary needs updating. {len(modified_files)} file(s) potentially modified since last check.",
                "modified_files": modified_files,
                "last_summarized": record.get("last_summarized"),
                "file_count": summary_data.get("file_count", 0)
            }
        else:
            # Update record status
            self.update_project_record({"status": "up_to_date"})
            return {
                "status": "up_to_date",
                "message": "Project summary is up to date.",
                "last_summarized": record.get("last_summarized"),
                "file_count": summary_data.get("file_count", 0)
            }

    def compute_file_hash(self, file_path):
        """Compute MD5 hash for a file in chunks to support large files."""
        abs_file_path = Path(file_path)
        if not abs_file_path.is_absolute():
            # Ensure project_path is Path object or convert
            base_path = Path(self.project_path)
            abs_file_path = base_path / file_path
        if not abs_file_path.is_file():
            # print(f"Debug: File not found for hashing: {abs_file_path}") # Optional debug
            return None
        try:
            hasher = hashlib.md5()
            with open(abs_file_path, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            print(f"Error computing hash for {abs_file_path}: {e}")
            return None

    def get_modified_files(self):
        """
        Checks for modified files based on hashes and updates the hash record.
        Returns a list of relative paths of modified files.
        """
        current_hashes = load_json(self.file_hashes_path) or {}
        modified_files = []
        found_files = set()
        project_record = self.get_project_record()
        selected_files = set()

        # Extract selected files only if file_selection exists and is valid
        if project_record and isinstance(project_record.get("file_selection"), list):
            def extract_checked_relative_paths(tree_nodes):
                paths = set()
                for node in tree_nodes:
                    if isinstance(node, dict): # Basic check for valid node structure
                        if node.get("type") == "file" and node.get("checked"):
                            rel_path = node.get("relative_path")
                            if rel_path:
                                paths.add(str(rel_path).replace("\\", "/")) # Ensure string and normalize
                        elif node.get("type") == "folder":
                            paths.update(extract_checked_relative_paths(node.get("children", [])))
                return paths
            selected_files = extract_checked_relative_paths(project_record["file_selection"])
        # print(f"Debug: Selected files for hash check: {selected_files}") # Optional debug

        project_path_obj = Path(self.project_path) # Use Path object for iteration
        if not project_path_obj.exists():
             print(f"Error: Project source path does not exist: {self.project_path}")
             return [] # Return empty list if source path is invalid

        for root, dirs, files in os.walk(self.project_path, topdown=True):
            # Exclude directories based on DEFAULT_EXCLUDES
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
            for file in files:
                full_path = Path(root) / file # Use Path object
                try:
                    # Ensure relative path calculation is robust
                    if full_path.is_relative_to(project_path_obj):
                         rel_path = str(full_path.relative_to(project_path_obj)).replace("\\", "/")
                    else:
                         # Fallback or error if not relative (shouldn't happen with os.walk)
                         print(f"Warning: File path {full_path} not relative to project path {project_path_obj}. Skipping.")
                         continue
                except ValueError as e:
                    print(f"Warning: Could not compute relative path for {full_path}: {e}")
                    continue

                found_files.add(rel_path)
                # Only check hash if file is selected or if no selection exists (selected_files is empty)
                should_check = not selected_files or rel_path in selected_files
                if should_check:
                    new_hash = self.compute_file_hash(full_path) # Pass Path object
                    if new_hash is None:
                        # print(f"Debug: Skipping hash check for {rel_path} (compute failed or file not found)") # Optional debug
                        continue # Skip if hash computation failed

                    # Check if file is new, modified, or hash missing
                    if rel_path not in current_hashes or current_hashes.get(rel_path) != new_hash:
                        # print(f"Debug: File modified or new: {rel_path}") # Optional debug
                        modified_files.append(rel_path)
                        current_hashes[rel_path] = new_hash # Update hash immediately

        # Remove hashes for files that no longer exist OR are deselected
        # Start with all keys currently tracked
        keys_to_remove = set(current_hashes.keys())
        # Subtract files that were actually found during the walk
        keys_to_remove -= found_files
        # If a selection exists, also remove files that were found but are NOT in the selection
        if selected_files:
            keys_to_remove.update(found_files - selected_files)

        if keys_to_remove:
            print(f"Removing hashes for deleted/deselected files: {keys_to_remove}")
            for rel_path in keys_to_remove:
                if rel_path in current_hashes:
                    del current_hashes[rel_path]

        # Save the potentially updated hashes
        save_json(current_hashes, self.file_hashes_path)
        # print(f"Debug: Modified files detected: {modified_files}") # Optional debug
        return modified_files

    def update_modified_summaries(self, modified_files, summarizer):
        """
        Updates summaries for the given list of modified files and refreshes the project summary.
        """
        if not self.combined_json_path.exists():
            print("Warning: Combined summary file does not exist. Cannot update modified summaries.")
            return None

        combined = load_json(self.combined_json_path)
        if not combined or "files" not in combined:
            print("Warning: Invalid or empty combined summary file. Cannot update.")
            # Optionally try to re-initialize or return an error structure
            return None

        updated_files_data = {}
        files_actually_updated = 0
        print(f"Attempting to update summaries for {len(modified_files)} files...")
        project_path_obj = Path(self.project_path) # Use Path object

        for rel_path in modified_files:
            # Use Path object for path manipulation
            full_path = project_path_obj / str(rel_path).replace("\\", "/") # Ensure normalized rel_path

            if not full_path.exists():
                print(f"Warning: Modified file '{rel_path}' not found at {full_path}. Removing from summary.")
                if rel_path in combined["files"]:
                    del combined["files"][rel_path]
                # Also remove from hashes if it got added somehow
                current_hashes = load_json(self.file_hashes_path) or {}
                if rel_path in current_hashes:
                     del current_hashes[rel_path]
                     save_json(current_hashes, self.file_hashes_path)
                continue

            # Use the utility function to read content
            content = read_file_content(full_path)
            if content is None:
                print(f"Warning: Could not read content for modified file '{rel_path}'. Skipping summary update.")
                continue

            print(f"Summarizing modified file: {rel_path}")
            try:
                # Pass string path to summarizer if it expects strings
                detailed, concise = summarizer.summarize_file_combined(content, str(full_path))
                line_count = len(content.splitlines())
                try:
                    file_size = full_path.stat().st_size
                except OSError as e:
                    print(f"Warning: Could not get size for {full_path}: {e}")
                    file_size = 0

                file_entry = {
                    "path": rel_path,
                    "detailed_summary": detailed,
                    "concise_summary": concise,
                    "lines": line_count,
                    "size": file_size
                }
                combined["files"][rel_path] = file_entry
                updated_files_data[rel_path] = file_entry
                files_actually_updated += 1
            except Exception as e:
                print(f"Error summarizing file {rel_path}: {e}")
                # Update summary entry with error message if it exists
                if rel_path in combined["files"]:
                    combined["files"][rel_path]["detailed_summary"] = f"Error updating summary: {e}"
                    combined["files"][rel_path]["concise_summary"] = "Error updating summary."
                else: # If summarizing failed on first attempt for a modified file
                     combined["files"][rel_path] = {
                         "path": rel_path,
                         "detailed_summary": f"Error creating summary: {e}",
                         "concise_summary": "Error creating summary.",
                         "lines": 0, "size": 0 # Add placeholders
                     }

        # --- Automatic Project Summary Refresh ---
        # Check if any files were updated OR if files were removed (implicitly updated)
        # Always refresh if modified_files list was not empty, even if summarization failed for some
        if modified_files: # Trigger refresh if *any* change was detected initially
             print("Refreshing project-level summary...")
             # Aggregate using DETAILED summaries for better context
             aggregated_summaries = "\n\n".join(
                 f"File: {path}\nSummary: {data.get('detailed_summary', 'N/A')}"
                 for path, data in combined["files"].items() if isinstance(data, dict) and "Error" not in data.get('detailed_summary', '')
             )

             if not aggregated_summaries:
                  print("Warning: No valid file summaries available to generate project summary.")
                  combined["project_summary"] = "Error: Could not generate project summary as no file summaries are available."
             else:
                 try:
                     # Prompt is already formatted in constants
                     prompt_project = AGGREGATED_SUMMARY_PROMPT.format(aggregated=aggregated_summaries)
                     # Use the passed summarizer instance
                     new_project_summary = summarizer.get_llm_response_with_timeout(prompt_project)
                     combined["project_summary"] = new_project_summary
                     print("Project-level summary refreshed successfully.")
                 except Exception as e:
                     print(f"Error refreshing project-level summary via LLM: {e}")
                     # Append error message to existing summary or set error message
                     existing_summary = combined.get("project_summary", "")
                     combined["project_summary"] = existing_summary + f"\n\n[Error updating project summary: {e}]"

        # Update overall file count and lines based on the current state of combined["files"]
        combined["file_count"] = len(combined["files"])
        combined["total_lines"] = sum(
            f.get("lines", 0) for f in combined["files"].values() if isinstance(f, dict)
        )

        # Save the final combined summary (with updated files and project summary)
        save_json(combined, self.combined_json_path)
        print(f"Combined summary saved to {self.combined_json_path}")

        # Update project record timestamp and status
        self.update_project_record({
            "last_summarized": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_count": combined["file_count"],
            "total_lines": combined["total_lines"],
            "status": "up_to_date" # Assuming update brings it up-to-date
        })

        return combined # Return the updated data

    def save_results(self, results):
        """Saves the summary results and updates the file hashes based on current files."""
        # Ensure results is a dictionary
        if not isinstance(results, dict):
            print(f"Error: Invalid results format passed to save_results: {type(results)}")
            return

        # --- Update Hashes ---
        current_hashes = load_json(self.file_hashes_path) or {}
        updated_hashes = {}
        files_in_results = results.get("files", {})
        project_path_obj = Path(self.project_path) # Use Path object

        # Iterate through files included in the summarization results
        for rel_path in files_in_results.keys():
            full_path = project_path_obj / str(rel_path).replace("\\", "/") # Ensure normalized
            hash_val = self.compute_file_hash(full_path) # Pass Path object
            if hash_val:
                updated_hashes[rel_path] = hash_val

        # --- Handle files NOT in results (deselected/excluded) ---
        # Need to know which files *should* have been processed based on selection
        project_record = self.get_project_record()
        selected_files = set()
        if project_record and isinstance(project_record.get("file_selection"), list):
             # Use the same extraction logic as get_modified_files
             def extract_checked_relative_paths(tree_nodes):
                 paths = set()
                 for node in tree_nodes:
                     if isinstance(node, dict):
                         if node.get("type") == "file" and node.get("checked"):
                             rel_path = node.get("relative_path")
                             if rel_path: paths.add(str(rel_path).replace("\\", "/"))
                         elif node.get("type") == "folder":
                             paths.update(extract_checked_relative_paths(node.get("children", [])))
                 return paths
             selected_files = extract_checked_relative_paths(project_record["file_selection"])

        # If a selection exists, remove hashes for selected files that are NOT in the results
        if selected_files:
             files_processed = set(files_in_results.keys())
             files_selected_but_not_processed = selected_files - files_processed
             if files_selected_but_not_processed:
                  print(f"Removing hashes for selected files not included in results: {files_selected_but_not_processed}")
                  for rel_path in files_selected_but_not_processed:
                       if rel_path in updated_hashes: # Remove if added above
                            del updated_hashes[rel_path]
                       if rel_path in current_hashes:
                           del current_hashes[rel_path]

        # Decide on saving strategy: Overwrite with updated_hashes or merge?
        # Overwriting with only hashes from results seems safer if results reflect the desired state.
        # However, get_modified_files already updates hashes, so maybe save_results shouldn't touch them.
        # Let's make get_modified_files the single source of truth for hash updates.
        # Rationale: save_results runs after a full scan, get_modified_files runs on dashboard load/refresh.
        # Let's REMOVE hash updates from save_results to avoid conflicts. get_modified_files will handle it.

        # --- Save Summary Results ---
        save_json(results, self.combined_json_path)
        print(f"Summary results saved: {self.combined_json_path}")

        # --- Update Project Record ---
        self.update_project_record({
            "last_summarized": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_count": results.get("file_count", 0),
            "total_lines": results.get("total_lines", 0),
            "status": "up_to_date" # Assume full scan results in up-to-date status
        })

        # --- (Optional) Generate HTML Report ---
        # self.generate_html_report(results) # Uncomment if needed

    def generate_html_report(self, results):
        html = HTML_COMBINED_REPORT_TEMPLATE.format(
            project_name=results.get("project_name", self.project_name)
        )
        with open(self.combined_html_path, 'w', encoding='utf-8') as f:
            f.write(html)

    def load_query_history(self):
        if os.path.exists(self.query_history_path):
            # Use load_json utility
            history = load_json(self.query_history_path)
            # Ensure it returns a list, even if file is empty/invalid
            return history if isinstance(history, list) else []
        return []

    def save_query_history(self, history):
        # Ensure history is a list before saving
        if isinstance(history, list):
            save_json(history, self.query_history_path)
        else:
            print(f"Error: Attempted to save non-list data to query history for {self.project_name}")

    def delete_query(self, query_id):
        history = self.load_query_history()
        # Filter out the query, ensuring comparison works even if IDs are numbers/strings
        history = [item for item in history if item.get("id") != query_id]
        self.save_query_history(history)

    def load_modifications_history(self):
        if os.path.exists(self.modifications_history_path):
            # Use load_json utility
            history = load_json(self.modifications_history_path)
            return history if isinstance(history, list) else []
        return []

    def save_modifications_history(self, history):
         if isinstance(history, list):
             save_json(history, self.modifications_history_path)
         else:
             print(f"Error: Attempted to save non-list data to modifications history for {self.project_name}")
