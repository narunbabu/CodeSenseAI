#new code_summarizer.py

import os
import re
import time
import concurrent.futures
from datetime import datetime
from pathlib import Path
from constants import COMBINED_FILE_PROMPT, PROJECT_SUMMARY_PROMPT, AGGREGATED_SUMMARY_PROMPT, DEFAULT_EXCLUDES, CODE_EXTENSIONS
from utils import format_time, safe_filename
import json


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
        return f"Error: Failed to get response after multiple attempts. Last error: {ollama_error}"

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

    def scan_specific_files(self, project_path, file_paths, output_dir=None):
        results = {
            "project_name": Path(project_path).name,
            "files": {},
            "file_count": 0,
            "total_lines": 0,
            "project_summary": ""
        }
        start_time = time.time()
        print(f"Starting scan for {len(file_paths)} specific files at {format_time(start_time)}")
        project_path_obj = Path(project_path)
        for relative_path in file_paths:
            file_path = project_path_obj / relative_path.replace("\\", "/")
            if not file_path.exists() or not self.should_process_file(str(file_path)):
                print(f"Skipping {relative_path}")
                continue
            content = self.read_file_content(str(file_path))
            if content is None:
                continue
            print(f"Summarizing {relative_path}...")
            detailed, concise = self.summarize_file_combined(content, str(file_path))
            line_count = len(content.splitlines())
            try:
                file_size = file_path.stat().st_size
            except OSError:
                file_size = 0
            file_summary = {
                "path": relative_path,
                "detailed_summary": detailed,
                "concise_summary": concise,
                "lines": line_count,
                "size": file_size
            }
            results["files"][relative_path] = file_summary
            results["file_count"] += 1
            results["total_lines"] += line_count
            # Save individual summary if output_dir is provided
            if output_dir:
                out_path = Path(output_dir) / (safe_filename(relative_path) + ".json")
                try:
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(file_summary, f, indent=4)
                except Exception as e:
                    print(f"Error saving summary for {relative_path}: {e}")
        if results["files"]:
            print("Generating project-level summary for specific files...")
            aggregated = "\n\n".join(
                f"File: {path}\nSummary: {data.get('detailed_summary', 'N/A')}"
                for path, data in results["files"].items()
            )
            if aggregated:
                try:
                    prompt_project = AGGREGATED_SUMMARY_PROMPT.format(aggregated=aggregated)
                    project_summary = self.get_llm_response_with_timeout(prompt_project)
                    results["project_summary"] = project_summary
                    print("Project-level summary generated.")
                except Exception as e:
                    print(f"Error generating project summary: {e}")
                    results["project_summary"] = f"Error: {e}"
            else:
                results["project_summary"] = "No file summaries available."
        else:
            results["project_summary"] = "No files were scanned."
        print(f"Total scan time for specific files: {time.time() - start_time:.2f} seconds")
        return results

    def scan_project(self, project_path, output_dir=None):
        project_path_obj = Path(project_path)
        if not project_path_obj.exists():
            raise ValueError(f"Project path does not exist: {project_path}")
        processed_files = set()
        results = {
            "project_name": project_path_obj.name,
            "files": {},
            "file_count": 0,
            "total_lines": 0,
            "excluded_files": 0,
            "project_summary": ""
        }
        start_time = time.time()
        print("*" * 80)
        print(f"Starting full project scan at {format_time(start_time)}")
        for root, dirs, files in os.walk(str(project_path_obj)):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not self.should_skip_directory(str(root_path / d))]
            for file in files:
                file_path = root_path / file
                try:
                    if file_path.is_relative_to(project_path_obj):
                        relative_path = str(file_path.relative_to(project_path_obj)).replace("\\", "/")
                    else:
                        print(f"Warning: {file_path} not relative to {project_path_obj}. Skipping.")
                        continue
                except ValueError as e:
                    print(f"Warning: Could not compute relative path for {file_path}: {e}")
                    continue
                if relative_path in processed_files or not self.should_process_file(str(file_path)):
                    results["excluded_files"] += 1
                    continue
                processed_files.add(relative_path)
                content = self.read_file_content(str(file_path))
                if content is None:
                    results["excluded_files"] += 1
                    continue
                print(f"Summarizing {relative_path}...")
                try:
                    detailed, concise = self.summarize_file_combined(content, str(file_path))
                    line_count = len(content.splitlines())
                    try:
                        file_size = file_path.stat().st_size
                    except OSError:
                        file_size = 0
                    file_summary = {
                        "path": relative_path,
                        "detailed_summary": detailed,
                        "concise_summary": concise,
                        "lines": line_count,
                        "size": file_size
                    }
                    results["files"][relative_path] = file_summary
                    results["file_count"] += 1
                    results["total_lines"] += line_count
                    if output_dir:
                        out_path = Path(output_dir) / (safe_filename(relative_path) + ".json")
                        try:
                            with open(out_path, "w", encoding="utf-8") as f:
                                json.dump(file_summary, f, indent=4)
                        except Exception as e:
                            print(f"Error saving summary for {relative_path}: {e}")
                except Exception as e:
                    print(f"Error summarizing {relative_path}: {e}")
                    results["files"][relative_path] = {
                        "path": relative_path,
                        "detailed_summary": f"Error: {e}",
                        "concise_summary": "Error summarizing file.",
                        "lines": 0,
                        "size": 0
                    }
                    results["excluded_files"] += 1
        if results["files"]:
            print("Generating project-level summary...")
            aggregated = "\n\n".join(
                f"File: {path}\nSummary: {data.get('detailed_summary', 'N/A')}"
                for path, data in results["files"].items() if isinstance(data, dict)
            )
            if aggregated:
                try:
                    prompt_project = AGGREGATED_SUMMARY_PROMPT.format(aggregated=aggregated)
                    project_summary = self.get_llm_response_with_timeout(prompt_project)
                    results["project_summary"] = project_summary
                    print("Project-level summary generated.")
                except Exception as e:
                    print(f"Error generating project summary: {e}")
                    results["project_summary"] = f"Error: {e}"
            else:
                results["project_summary"] = "No valid file summaries available."
        else:
            results["project_summary"] = "No files were found or summarized."
        print(f"Total processing time: {time.time() - start_time:.2f} seconds")
        print("*" * 80)
        return results
