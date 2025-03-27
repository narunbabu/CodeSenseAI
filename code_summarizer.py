# code_summarizer.py
import os
import re
import time
import concurrent.futures
from datetime import datetime
from pathlib import Path
from constants import COMBINED_FILE_PROMPT, PROJECT_SUMMARY_PROMPT, AGGREGATED_SUMMARY_PROMPT, DEFAULT_EXCLUDES, CODE_EXTENSIONS
from utils import format_time

class CodeSummarizer:
    def __init__(self, api_key, exclude_dirs=None, max_file_size=1_000_000, ollama_client=None, fallout_client=None):
        self.api_key = api_key
        self.exclude_dirs = exclude_dirs or DEFAULT_EXCLUDES
        self.max_file_size = max_file_size
        self.ollama_client = ollama_client
        self.fallout_client = fallout_client

    def should_skip_directory(self, dir_path):
        dir_name = os.path.basename(dir_path)
        return any(
            re.match(pattern.replace("*", ".*"), dir_name) if "*" in pattern else dir_name == pattern
            for pattern in self.exclude_dirs
        )

    def should_process_file(self, file_path):
        if not any(file_path.endswith(ext) for ext in CODE_EXTENSIONS):
            return False
        try:
            if os.path.getsize(file_path) > self.max_file_size:
                print(f"Skipping {file_path} (too large)")
                return False
        except OSError:
            return False
        return True

    def read_file_content(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return None

    def get_llm_response_with_timeout(self, prompt, timeout=120, max_retries=2):
        ollama_error = None
        for attempt in range(max_retries):
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self.ollama_client.get_response, prompt)
                    response = future.result(timeout=timeout)
                    response = re.sub(r'<thought>.*?</thought>', '', response, flags=re.DOTALL)
                    return response
            except concurrent.futures.TimeoutError:
                print(f"Response timed out on attempt {attempt+1}/{max_retries}")
                ollama_error = "Timeout"
                time.sleep(2)
            except Exception as e:
                print(f"Error calling Ollama API: {e}")
                ollama_error = str(e)
                time.sleep(2)
        print("Falling back to fallout_client.")
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self.fallout_client.get_response, prompt)
                response = future.result(timeout=timeout)
                response = re.sub(r'<thought>.*?</thought>', '', response, flags=re.DOTALL)
                return response
        except Exception as e:
            print(f"Error calling fallout_client API: {e}")
        return f"Error: Failed to get response after multiple attempts. Last error from ollama_client: {ollama_error}"

    def parse_combined_summary(self, response):
        detailed_pattern = r'<detailed>(.*?)</detailed>'
        concise_pattern = r'<concise>(.*?)</concise>'
        detailed_match = re.search(detailed_pattern, response, re.DOTALL)
        concise_match = re.search(concise_pattern, response, re.DOTALL)
        detailed_summary = detailed_match.group(1).strip() if detailed_match else "Error: No detailed summary found"
        concise_summary = concise_match.group(1).strip() if concise_match else "Error: No concise summary found"
        return detailed_summary, concise_summary

    def summarize_file_combined(self, code, file_path):
        prompt = COMBINED_FILE_PROMPT.format(file_path=file_path, file_type=os.path.splitext(file_path)[1], code=code)
        response = self.get_llm_response_with_timeout(prompt)
        return self.parse_combined_summary(response)

    def summarize_project(self, aggregated_summaries):
        prompt = PROJECT_SUMMARY_PROMPT.format(code=aggregated_summaries)
        return self.get_llm_response_with_timeout(prompt)

    def scan_specific_files(self, project_path, file_paths):
        results = {
            "project_name": os.path.basename(project_path),
            "files": {},
            "file_count": 0,
            "total_lines": 0,
            "project_summary": "" # Initialize project summary field
        }
        start_time = time.time()
        print(f"\nStarting scan for {len(file_paths)} specific files at {format_time(start_time)}")
        project_path_obj = Path(project_path)

        for relative_path in file_paths:
            # Use Path object for path joining and checking
            file_path = project_path_obj / str(relative_path).replace("\\", "/") # Normalize

            # Use Path object methods for checks
            if not file_path.exists() or not self.should_process_file(str(file_path)):
                print(f"Skipping {relative_path}")
                continue

            # Use utility function (if defined, otherwise keep inline)
            content = self.read_file_content(str(file_path))
            if content is None:
                continue

            # Pass string path if required by summarize_file_combined
            detailed_summary, concise_summary = self.summarize_file_combined(content, str(file_path))
            line_count = len(content.splitlines())
            try:
                file_size = file_path.stat().st_size
            except OSError:
                 file_size = 0

            results["files"][relative_path] = {
                "path": relative_path,
                "detailed_summary": detailed_summary,
                "concise_summary": concise_summary,
                "lines": line_count,
                "size": file_size
            }
            results["file_count"] += 1
            results["total_lines"] += line_count

        # --- Generate Project Summary for specific files scan ---
        if results["files"]:
             print("\nGenerating project-level summary for scanned files...")
             # Use DETAILED summaries
             aggregated = "\n\n".join(
                 f"File: {path}\nSummary: {data.get('detailed_summary', 'N/A')}"
                 for path, data in results["files"].items() if isinstance(data, dict)
             )
             if aggregated:
                 try:
                     prompt_project = AGGREGATED_SUMMARY_PROMPT.format(aggregated=aggregated)
                     start_summary = time.time()
                     project_summary = self.get_llm_response_with_timeout(prompt_project)
                     results["project_summary"] = project_summary
                     print(f"Project-level summary generated in {time.time() - start_summary:.2f} seconds")
                 except Exception as e:
                     print(f"Error generating project-level summary: {e}")
                     results["project_summary"] = f"Error generating project summary: {e}"
             else:
                  results["project_summary"] = "No file summaries available to generate project summary."
        else:
             results["project_summary"] = "No files were scanned."


        print(f"\nTotal scan time for specific files: {time.time() - start_time:.2f} seconds")
        return results

    def scan_project(self, project_path):
        project_path_obj = Path(project_path) # Use Path object
        if not project_path_obj.exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        processed_files = set()
        results = {
            "project_name": project_path_obj.name,
            "files": {},
            "file_count": 0,
            "total_lines": 0,
            "excluded_dirs": [], # Consider removing if not used
            "excluded_files": 0,
            "project_summary": "" # Initialize
        }
        start_time = time.time()
        print("*"*80)
        print(f"\nStarting full project scan at {format_time(start_time)}")

        for root, dirs, files in os.walk(str(project_path_obj)): # os.walk needs string path
            root_path = Path(root) # Convert root back to Path object
            # Filter directories based on name using should_skip_directory
            # Note: should_skip_directory expects the full path
            dirs[:] = [d for d in dirs if not self.should_skip_directory(str(root_path / d))]

            for file in files:
                file_path = root_path / file # Path object
                try:
                    # Ensure robust relative path calculation
                    if file_path.is_relative_to(project_path_obj):
                         relative_path = str(file_path.relative_to(project_path_obj)).replace("\\", "/")
                    else:
                         print(f"Warning: File path {file_path} not relative to project path {project_path_obj}. Skipping.")
                         continue
                except ValueError as e:
                    print(f"Warning: Could not compute relative path for {file_path}: {e}")
                    continue

                # Skip if already processed or doesn't meet criteria
                if relative_path in processed_files or not self.should_process_file(str(file_path)):
                    # print(f"Skipping: {relative_path}") # Optional debug
                    results["excluded_files"] += 1
                    continue

                processed_files.add(relative_path)
                content = self.read_file_content(str(file_path))
                if content is None:
                    results["excluded_files"] += 1 # Count files we couldn't read
                    continue

                print(f"Summarizing file: {relative_path}") # Add progress indicator
                try:
                    detailed_summary, concise_summary = self.summarize_file_combined(content, str(file_path))
                    line_count = len(content.splitlines())
                    try:
                         file_size = file_path.stat().st_size
                    except OSError:
                         file_size = 0

                    results["files"][relative_path] = {
                        "path": relative_path,
                        "detailed_summary": detailed_summary,
                        "concise_summary": concise_summary,
                        "lines": line_count,
                        "size": file_size
                    }
                    results["file_count"] += 1
                    results["total_lines"] += line_count
                except Exception as e:
                     print(f"Error summarizing file {relative_path}: {e}")
                     # Add error entry?
                     results["files"][relative_path] = { # Add placeholder with error
                         "path": relative_path,
                         "detailed_summary": f"Error creating summary: {e}",
                         "concise_summary": "Error creating summary.",
                         "lines": 0, "size": 0
                     }
                     results["excluded_files"] += 1 # Count as excluded/failed

        # --- Generate Project Summary ---
        if results["files"]:
             print("\nGenerating project-level summary...")
             # Aggregate using DETAILED summaries
             aggregated = "\n\n".join(
                 f"File: {path}\nSummary: {data.get('detailed_summary', 'N/A')}" # Correctly uses detailed summary
                 for path, data in results["files"].items() if isinstance(data, dict) # Ensure data is dict
             )
             if aggregated:
                 try:
                     # Use the AGGREGATED_SUMMARY_PROMPT
                     prompt_project = AGGREGATED_SUMMARY_PROMPT.format(aggregated=aggregated)
                     start_summary = time.time()
                     project_summary = self.get_llm_response_with_timeout(prompt_project)
                     results["project_summary"] = project_summary
                     print(f"Project-level summary generated in {time.time() - start_summary:.2f} seconds")
                 except Exception as e:
                     print(f"Error generating project-level summary: {e}")
                     results["project_summary"] = f"Error generating project summary: {e}"
             else:
                  results["project_summary"] = "No valid file summaries available to generate project summary."
        else:
             results["project_summary"] = "No files were found or summarized in the project."


        print(f"Total processing time: {time.time() - start_time:.2f} seconds")
        print("*"*80)
        return results