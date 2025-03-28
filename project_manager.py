# project_manager.py

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from constants import  DEFAULT_EXCLUDES, AGGREGATED_SUMMARY_PROMPT, CODE_EXTENSIONS
from utils import load_json, save_json, safe_filename  # (Define safe_filename below or in utils)


def read_file_content(file_path):
    """Utility to read file content safely."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

class ProjectManager:
    def __init__(self, project_path, output_dir='./projects', is_new=False):
        """
        Initializes the ProjectManager.

        Args:
            project_path (str): Absolute path to the source code directory.
            output_dir (str): Path to the directory where project management files
                              (summaries, history, etc.) will be stored. This should
                              be the specific directory for *this* project,
                              e.g., './projects/my_project_name'.
            is_new (bool): Flag indicating if this is a newly created empty project.
        """
        self.project_path = str(project_path) # Store as string for consistency
        self.project_path_obj = Path(project_path) # Keep Path object for operations
        self.output_dir = Path(output_dir)
        self.project_name = self.output_dir.name # Derive name from output dir

        # Ensure the main output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Define paths for management files
        self.backups_dir = self.output_dir / 'backups'
        self.summaries_dir = self.output_dir / 'summaries'
        self.temp_dir = self.output_dir / 'temp' # For temporary files like prompts
        self.proposed_modifications_dir = self.output_dir / 'proposed_modifications'

        self.combined_json_path = self.output_dir / 'combined_code_summary.json'
        self.combined_html_path = self.output_dir / 'combined_code_summary.html'
        self.project_record_path = self.output_dir / 'project_record.json'
        self.query_history_path = self.output_dir / 'query_history.json'
        self.modifications_history_path = self.output_dir / 'modifications_history.json'
        self.file_hashes_path = self.output_dir / 'file_hashes.json'

        print(f"ProjectManager initialized:")
        print(f"  Source Path: {self.project_path}")
        print(f"  Output Dir: {self.output_dir}")
        print(f"  Project Name: {self.project_name}")
        print(f"  Is New: {is_new}")

        # Initialize project structure and files if they don't exist
        self._ensure_project_structure(is_new)


    def _ensure_project_structure(self, is_new):
        """Creates necessary directories and initializes essential JSON files if they don't exist."""
        self.backups_dir.mkdir(exist_ok=True)
        self.summaries_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
        self.proposed_modifications_dir.mkdir(exist_ok=True)

        # Initialize project record if it doesn't exist
        if not self.project_record_path.exists():
            self._init_project_record(status="new" if is_new else "initialized")

        # Initialize other JSON files if they don't exist
        if not self.file_hashes_path.exists():
            save_json({}, self.file_hashes_path)
            print(f"  Created empty: {self.file_hashes_path.name}")

        if not self.query_history_path.exists():
            save_json([], self.query_history_path)
            print(f"  Created empty: {self.query_history_path.name}")

        if not self.modifications_history_path.exists():
            save_json([], self.modifications_history_path)
            print(f"  Created empty: {self.modifications_history_path.name}")

        # Create empty summary only for truly new projects or if missing
        if (is_new or not self.combined_json_path.exists()):
             # Check again to avoid race conditions? Unlikely here.
             if not self.combined_json_path.exists():
                 empty_summary = {
                     "project_name": self.project_name,
                     "files": {},
                     "file_count": 0,
                     "total_lines": 0,
                     "project_summary": "New project, no files summarized yet." if is_new else "Summary not generated yet."
                 }
                 save_json(empty_summary, self.combined_json_path)
                 print(f"  Created empty: {self.combined_json_path.name}")


    def _init_project_record(self, status="initialized"):
        """Initializes the project_record.json file."""
        record = {
            "project_name": self.project_name,
            "source_code_path": self.project_path, # Store string path
            "local_storage_path": str(self.output_dir),
            "created_at": datetime.now().isoformat(),
            "last_summarized": None,
            "last_checked": None,
            "summary_count": 0, # Number of times summarization ran? Or files summarized? Let's say files.
            "query_count": 0,
            "modification_count": 0,
            "file_count": 0, # Number of source files tracked/hashed
            "total_lines": 0, # Total lines in tracked/hashed files
            "status": status, # e.g., 'initialized', 'new', 'summarized', 'needs_update', 'error'
            "file_selection": [] # Stores the tree structure from project_files.html selection
        }
        save_json(record, self.project_record_path)
        print(f"  Initialized project record: {self.project_record_path.name} with status '{status}'")

    def get_project_info(self):
        """Returns basic project information."""
        # Load record to get potentially updated info if needed, but mostly rely on instance vars
        # record = self.get_project_record() # Avoid reading file just for this
        return {
            "project_name": self.project_name,
            "source_code_path": self.project_path,
            "local_storage_path": str(self.output_dir),
            "output_base": str(self.output_dir.parent), # Base dir like './projects'
            "output_dir": str(self.output_dir)     # Specific dir like './projects/myproj'
        }

    def get_project_record(self):
        """Loads and returns the project record dictionary."""
        if not self.project_record_path.exists():
            print(f"Warning: Project record file missing for {self.project_name}. Reinitializing.")
            # Attempt to reinitialize based on current state
            is_new_check = not any(self.project_path_obj.iterdir()) if self.project_path_obj.is_dir() else True
            self._ensure_project_structure(is_new=is_new_check)
            # Try loading again
            if not self.project_record_path.exists():
                print(f"Error: Failed to create project record for {self.project_name}.")
                return None # Return None if it still fails
        return load_json(self.project_record_path)

    def update_project_record(self, data):
        """Updates the project record with new data."""
        record = self.get_project_record()
        if record:
            # Convert datetime objects in data to isoformat strings before saving
            for key, value in data.items():
                 if isinstance(value, datetime):
                     data[key] = value.isoformat()
            record.update(data)
            save_json(record, self.project_record_path)
        else:
            print(f"Warning: Could not load project record for {self.project_name}. Update failed.")

    def has_summary(self):
        """
        Checks if a potentially meaningful summary exists.
        Returns True if the combined summary file exists and contains file entries.
        """
        if not self.combined_json_path.exists():
            return False
        summary_data = load_json(self.combined_json_path)
        # Check if it's a dict and has a non-empty 'files' dictionary
        return isinstance(summary_data, dict) and bool(summary_data.get("files"))

    def is_project_empty(self):
        """Checks if the source project directory contains any processable code files."""
        if not self.project_path_obj.is_dir():
            return True # Non-existent or file path is considered empty

        for root, dirs, files in os.walk(self.project_path_obj, topdown=True):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
            # Check root itself (relative path check)
            try:
                rel_root = Path(root).relative_to(self.project_path_obj)
                if any(part in DEFAULT_EXCLUDES for part in rel_root.parts):
                    dirs[:] = [] # Don't descend further into excluded root
                    continue
            except ValueError: # Should not happen if walk starts within project_path
                 continue

            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in CODE_EXTENSIONS:
                    # Check if file path itself contains excluded parts
                    try:
                        full_path = Path(root) / file
                        rel_file_path = full_path.relative_to(self.project_path_obj)
                        if not any(part in DEFAULT_EXCLUDES for part in rel_file_path.parts):
                            return False # Found at least one processable file
                    except ValueError:
                        continue # Should not happen
        return True # No processable files found


    def get_summary_status(self):
        """Determines the status of the project summary."""
        record = self.get_project_record()
        if not record:
             return {"status": "error", "message": "Project record unavailable."}

        last_summarized_iso = record.get("last_summarized")
        last_summarized_dt = None
        if last_summarized_iso:
            try:
                last_summarized_dt = datetime.fromisoformat(last_summarized_iso)
            except ValueError:
                print(f"Warning: Could not parse last_summarized timestamp '{last_summarized_iso}'")


        if not self.combined_json_path.exists():
            # If record status is 'new', reflect that
            if record.get("status") == "new":
                 return {"status": "new", "message": "New empty project. Ready for first query to create files."}
            else:
                 # Check if source is actually empty
                 if self.is_project_empty():
                      return {"status": "empty_source", "message": "Source directory is empty. Summarization not applicable."}
                 else:
                      return {"status": "not_summarized", "message": "Project has not been summarized yet."}


        summary_data = load_json(self.combined_json_path)
        if not summary_data:
            self.update_project_record({"status": "error_loading_summary"})
            return {"status": "error_loading_summary", "message": "Failed to load existing summary data."}

        # Check if summary is just the empty shell
        if not summary_data.get("files") and isinstance(summary_data.get("files"), dict):
             if record.get("status") == "new": # Should match empty summary
                  return {"status": "new", "message": "New empty project. Ready for first query to create files."}
             elif self.is_project_empty(): # Source is empty, summary reflects that
                  return {"status": "empty_source", "message": "Source directory is empty. Summary reflects no files."}
             else: # Summary exists but is empty, source is NOT empty -> needs summary
                  return {"status": "not_summarized", "message": "Summary file is present but empty. Project needs summarization."}


        # Summary exists and has content, check for modifications
        modified_files = self.get_modified_files() # This also updates hashes
        if modified_files:
            # Don't overwrite 'summarizing' or 'error' status here
            if record.get("status") not in ["summarizing", "error"]:
                 self.update_project_record({"status": "needs_update", "last_checked": datetime.now().isoformat()})
            return {
                "status": "needs_update",
                "message": f"Project summary needs updating. {len(modified_files)} file(s) modified since last check.",
                "modified_files": modified_files,
                "last_summarized": last_summarized_iso,
                "file_count": summary_data.get("file_count", 0)
            }
        else:
            # Don't overwrite 'summarizing' or 'error' status here
            if record.get("status") not in ["summarizing", "error"]:
                 self.update_project_record({"status": "up_to_date", "last_checked": datetime.now().isoformat()})
            return {
                "status": "up_to_date",
                "message": "Project summary is up to date.",
                "last_summarized": last_summarized_iso,
                "file_count": summary_data.get("file_count", 0)
            }

    def compute_file_hash(self, file_path):
        """Computes MD5 hash for a given file path (can be relative or absolute)."""
        abs_file_path = Path(file_path)
        if not abs_file_path.is_absolute():
            # Assume relative to project source path
            abs_file_path = self.project_path_obj / file_path
        if not abs_file_path.is_file():
            # print(f"Warning: Path is not a file, cannot compute hash: {abs_file_path}")
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
        Compares current file hashes in the source directory against stored hashes.
        Updates the stored hashes (file_hashes.json).
        Returns a list of relative paths of modified or new files relevant to the selection.
        """
        current_hashes = load_json(self.file_hashes_path) or {}
        new_hashes = {}
        modified_files = []
        found_files_in_source = set() # Track all processable files found
        record = self.get_project_record()
        selected_files_from_record = set() # Files marked as 'checked' in the record

        # Extract selected files from the project record's file_selection tree
        if record and isinstance(record.get("file_selection"), list):
            def extract_checked(tree_nodes):
                paths = set()
                for node in tree_nodes:
                    if isinstance(node, dict):
                        if node.get("type") == "file" and node.get("checked"):
                            rel = node.get("relative_path")
                            if rel: paths.add(str(rel).replace("\\", "/"))
                        elif node.get("type") == "folder":
                            # Only add children if the folder itself is considered selected
                            # How to determine if folder is selected? If it contains ANY checked file? Or explicit folder checkbox?
                            # Current JS doesn't seem to have folder checkboxes, so rely on file checks.
                             paths.update(extract_checked(node.get("children", []))) # Recursive check
                return paths
            selected_files_from_record = extract_checked(record["file_selection"])
            # print(f"Debug: Selected files from record: {selected_files_from_record}")

        # Check if source path exists
        if not self.project_path_obj.is_dir():
            print(f"Warning: Project source path does not exist or is not a directory: {self.project_path}")
            # If source is gone, all previously hashed files are effectively "modified" (removed)
            # Clear hashes and return empty list? Or list of removed files?
            # Let's clear hashes and return empty, assuming user needs to fix path or summarize.
            if current_hashes:
                 save_json({}, self.file_hashes_path)
            return []

        # Walk the source directory
        try:
            for root, dirs, files in os.walk(self.project_path_obj, topdown=True):
                # Prune excluded directories early
                dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]

                # Check if the current directory itself should be excluded based on relative path
                try:
                    rel_root_path = Path(root).relative_to(self.project_path_obj)
                    if any(part in DEFAULT_EXCLUDES for part in rel_root_path.parts):
                        # print(f"Skipping excluded directory root: {rel_root_path}")
                        dirs[:] = [] # Don't process files in this dir or descend further
                        continue
                except ValueError:
                     print(f"Warning: Could not get relative path for {root}")
                     continue # Skip this directory

                for file in files:
                    ext = os.path.splitext(file)[1]
                    if ext in CODE_EXTENSIONS:
                        full_path = Path(root) / file
                        try:
                            # Get relative path, normalized
                            rel_path_str = str(full_path.relative_to(self.project_path_obj)).replace("\\", "/")

                            # Final check if any part of the relative path is excluded
                            if any(part in DEFAULT_EXCLUDES for part in Path(rel_path_str).parts):
                                # print(f"Skipping excluded file path: {rel_path_str}")
                                continue

                            found_files_in_source.add(rel_path_str) # Track this file

                            # Determine if this file should be checked for modification
                            # Check if:
                            # 1. No specific selection exists in record (check all found files) OR
                            # 2. This file is in the set of selected files from the record
                            is_relevant_for_check = not selected_files_from_record or rel_path_str in selected_files_from_record

                            if is_relevant_for_check:
                                new_hash = self.compute_file_hash(full_path)
                                if new_hash is None:
                                    print(f"Warning: Could not compute hash for {rel_path_str}, skipping.")
                                    continue # Skip files we can't hash

                                new_hashes[rel_path_str] = new_hash # Store the current hash

                                # Check if modified compared to *stored* hash
                                if rel_path_str not in current_hashes or current_hashes[rel_path_str] != new_hash:
                                    modified_files.append(rel_path_str)
                                    # print(f"Detected change/new file: {rel_path_str}")

                        except ValueError:
                            print(f"Warning: Could not compute relative path for {full_path}")
                            continue
                        except Exception as walk_err:
                             print(f"Error processing file {full_path}: {walk_err}")
                             continue # Skip problematic file

        except Exception as e:
            print(f"Error walking directory {self.project_path}: {e}")
            # Return empty list or raise? Let's return empty for now.
            return []

        # Update the stored hashes:
        # Keep only hashes for files found AND relevant (i.e., selected or all if no selection)
        final_hashes_to_save = {}
        if not selected_files_from_record: # No selection, save hashes for all found processable files
             final_hashes_to_save = {k: v for k, v in new_hashes.items() if k in found_files_in_source}
        else: # Selection exists, save hashes only for selected files that were found
             final_hashes_to_save = {k: v for k, v in new_hashes.items() if k in selected_files_from_record and k in found_files_in_source}


        # Only save if the hashes actually changed to avoid unnecessary writes
        if final_hashes_to_save != current_hashes:
             save_json(final_hashes_to_save, self.file_hashes_path)
             # print(f"Updated file hashes saved. {len(final_hashes_to_save)} files tracked.")
             # Update file count in project record
             self.update_project_record({"file_count": len(final_hashes_to_save)})


        # Return the list of modified files that are relevant to the current selection
        return modified_files


    def update_modified_summaries(self, modified_files, summarizer):
        """Updates summaries only for the provided list of modified files."""
        if not self.combined_json_path.exists():
            print("Warning: Combined summary file does not exist. Cannot update modified files. Run full summarization.")
            # Or maybe initialize an empty one here? Let's require full summary first.
            return None # Indicate failure

        combined = load_json(self.combined_json_path)
        if not combined or "files" not in combined:
            print("Warning: Invalid combined summary file structure. Cannot update.")
            return None # Indicate failure

        print(f"Updating summaries for {len(modified_files)} modified file(s)...")
        updated_count = 0
        total_lines_updated = 0 # Track line changes for record update

        for rel_path_str in modified_files:
            full_path = self.project_path_obj / rel_path_str.replace("\\", "/") # Ensure Path object
            if not full_path.exists():
                print(f"Warning: File {rel_path_str} listed as modified but not found. Removing from summary.")
                if rel_path_str in combined["files"]:
                    # Adjust total lines before removing
                    total_lines_updated -= combined["files"][rel_path_str].get("lines", 0)
                    combined["files"].pop(rel_path_str)
                continue

            content = read_file_content(full_path)
            if content is None:
                print(f"Warning: Could not read {rel_path_str}. Skipping summary update.")
                # Keep old summary? Or mark as error? Mark as error.
                old_lines = combined["files"].get(rel_path_str, {}).get("lines", 0)
                combined["files"][rel_path_str] = {
                    "path": rel_path_str,
                    "detailed_summary": "Error: Could not read file content during update.",
                    "concise_summary": "Error reading file.",
                    "lines": 0, # Reset lines
                    "size": 0  # Reset size
                }
                total_lines_updated -= old_lines # Adjust total lines
                continue

            print(f"Summarizing modified file: {rel_path_str}")
            try:
                detailed, concise = summarizer.summarize_file_combined(content, str(full_path))
                lines = len(content.splitlines())
                size = full_path.stat().st_size
                old_lines = combined["files"].get(rel_path_str, {}).get("lines", 0)
                file_entry = {
                    "path": rel_path_str,
                    "detailed_summary": detailed,
                    "concise_summary": concise,
                    "lines": lines,
                    "size": size
                }
                combined["files"][rel_path_str] = file_entry
                total_lines_updated += (lines - old_lines) # Accumulate line difference
                # Also save individual summary to summaries_dir
                out_file = self.summaries_dir / (safe_filename(rel_path_str) + ".json")
                save_json(file_entry, out_file)
                updated_count += 1
            except Exception as e:
                print(f"Error summarizing {rel_path_str}: {e}")
                old_lines = combined["files"].get(rel_path_str, {}).get("lines", 0)
                combined["files"][rel_path_str] = {
                    "path": rel_path_str,
                    "detailed_summary": f"Error during summary update: {e}",
                    "concise_summary": "Error updating summary.",
                    "lines": 0, # Reset lines on error
                    "size": 0
                }
                total_lines_updated -= old_lines # Adjust total lines
                # Save error state to individual file too? Maybe not.

        if updated_count > 0:
            print(f"Successfully updated summaries for {updated_count} file(s).")
            print("Regenerating project-level summary...")
            # Regenerate project summary based on ALL current file summaries
            aggregated = "\n\n".join(
                f"File: {path}\nConcise Summary: {data.get('concise_summary', 'N/A')}" # Use concise for project summary input
                for path, data in combined.get("files", {}).items()
                if isinstance(data, dict) and data.get('concise_summary') and "Error" not in data.get('concise_summary', "")
            )
            if aggregated:
                try:
                    prompt_project = AGGREGATED_SUMMARY_PROMPT.format(aggregated=aggregated)
                    project_summary = summarizer.get_llm_response_with_timeout(prompt_project)
                    combined["project_summary"] = project_summary
                    print("Project-level summary updated.")
                except Exception as e:
                    print(f"Error generating project summary during update: {e}")
                    combined["project_summary"] = combined.get("project_summary", "") + f"\n\n[Error updating project summary: {e}]"
            else:
                combined["project_summary"] = "No valid file summaries available to generate project summary."

            # Update counts and save
            combined["file_count"] = len(combined["files"])
            # Ensure total lines is calculated correctly over all files, not just updated diff
            combined["total_lines"] = sum(f.get("lines", 0) for f in combined["files"].values() if isinstance(f, dict))

            save_json(combined, self.combined_json_path)
            print(f"Combined summary updated and saved to {self.combined_json_path}")

            # Update project record
            self.update_project_record({
                "last_summarized": datetime.now().isoformat(),
                "file_count": combined["file_count"],
                "total_lines": combined["total_lines"],
                "status": "up_to_date" # Mark as up-to-date after successful update
            })
            return combined # Return the updated summary data
        elif modified_files: # Modified files existed, but none were updated (e.g., all had errors)
             print("No summaries were successfully updated.")
             # Update status to reflect error?
             self.update_project_record({"status": "error_during_summary_update"})
             return None # Indicate failure
        else: # No modified files provided
             print("No modified files provided for update.")
             return combined # Return existing summary


    def combine_summaries(self, summarizer=None):
        """
        Reads all individual JSON files from self.summaries_dir,
        combines them, generates a new project-level summary using the provided summarizer,
        and saves the result to combined_code_summary.json.
        """
        combined = {
            "project_name": self.project_name,
            "files": {},
            "file_count": 0,
            "total_lines": 0,
            "project_summary": "" # Will be generated
        }
        print(f"Combining summaries from: {self.summaries_dir}")
        found_summaries = 0
        for summary_file in self.summaries_dir.glob("*.json"):
            try:
                file_summary = load_json(summary_file)
                # Basic validation of the loaded summary structure
                if file_summary and isinstance(file_summary, dict) and "path" in file_summary:
                    rel_path_str = file_summary["path"]
                    # Ensure essential keys exist, provide defaults if not
                    combined["files"][rel_path_str] = {
                        "path": rel_path_str,
                        "detailed_summary": file_summary.get("detailed_summary", "N/A"),
                        "concise_summary": file_summary.get("concise_summary", "N/A"),
                        "lines": file_summary.get("lines", 0),
                        "size": file_summary.get("size", 0)
                    }
                    found_summaries += 1
                else:
                     print(f"Warning: Skipping invalid summary file {summary_file.name}. Content: {file_summary}")
            except Exception as e:
                print(f"Error reading or processing summary file {summary_file}: {e}")

        print(f"Found {found_summaries} individual summary files.")
        combined["file_count"] = len(combined["files"])
        combined["total_lines"] = sum(
            f.get("lines", 0) for f in combined["files"].values() if isinstance(f, dict)
        )

        # Generate project-level summary if a summarizer is provided and there are files
        if summarizer and combined["files"]:
            print("Generating project-level summary...")
            aggregated = "\n\n".join(
                f"File: {path}\nConcise Summary: {data.get('concise_summary', 'N/A')}"
                for path, data in combined["files"].items()
                if isinstance(data, dict) and data.get('concise_summary') and "Error" not in data.get('concise_summary', "")
            )
            if aggregated:
                try:
                    prompt_project = AGGREGATED_SUMMARY_PROMPT.format(aggregated=aggregated)
                    project_summary = summarizer.get_llm_response_with_timeout(prompt_project)
                    combined["project_summary"] = project_summary
                    print("Project-level summary generated.")
                except Exception as e:
                    print(f"Error generating project summary during combine: {e}")
                    combined["project_summary"] = f"[Error generating project summary: {e}]"
            else:
                 combined["project_summary"] = "No valid file summaries available to generate project summary."
        elif not combined["files"]:
             combined["project_summary"] = "Project contains no summarized files."
        else: # No summarizer provided
             combined["project_summary"] = combined.get("project_summary", "Project summary generation skipped (no summarizer provided).")


        save_json(combined, self.combined_json_path)
        print(f"Combined summary saved to {self.combined_json_path}")
        return combined # Return the newly combined summary

    def update_file_hashes(self):
        """Refreshes the file hashes by calling get_modified_files (which updates the hash file)."""
        print("Updating file hashes...")
        modified = self.get_modified_files() # Call primarily for its side effect of saving hashes
        print(f"File hash update complete. {len(modified)} files detected as changed since last hash save.")

    # save_results might be redundant if combine_summaries and update_modified_summaries handle saving
    # def save_results(self, results):
    #     # ... (keep if direct saving is needed elsewhere) ...

    # generate_html_report seems unused, can be kept or removed
    # def generate_html_report(self, results):
    #     # ...

    def load_query_history(self):
        """Loads the query history list from its JSON file."""
        if self.query_history_path.exists():
            history = load_json(self.query_history_path)
            # Ensure it's a list, return empty list if not or if error
            return history if isinstance(history, list) else []
        return [] # Return empty list if file doesn't exist

    def save_query_history(self, history):
        """Saves the query history list to its JSON file."""
        if isinstance(history, list):
            # Update query count in project record before saving
            self.update_project_record({"query_count": len(history)})
            save_json(history, self.query_history_path)
        else:
            print(f"Error: Query history must be a list for {self.project_name}. Save failed.")

    def delete_query(self, query_id):
        """Deletes a specific query entry from the history by its ID."""
        history = self.load_query_history()
        initial_length = len(history)
        history = [item for item in history if item.get("id") != query_id]
        if len(history) < initial_length:
            self.save_query_history(history) # Save also updates count
            print(f"Deleted query {query_id} from history.")
            return True
        else:
            print(f"Query ID {query_id} not found in history.")
            return False


    def load_modifications_history(self):
        """Loads the modifications history list from its JSON file."""
        if self.modifications_history_path.exists():
            history = load_json(self.modifications_history_path)
            return history if isinstance(history, list) else []
        return []

    def save_modifications_history(self, history):
        """Saves the modifications history list to its JSON file."""
        if isinstance(history, list):
             # Update modification count in project record before saving
            self.update_project_record({"modification_count": len(history)})
            save_json(history, self.modifications_history_path)
        else:
            print(f"Error: Modifications history must be a list for {self.project_name}. Save failed.")
