# #new project_manager.py

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from constants import HTML_COMBINED_REPORT_TEMPLATE, DEFAULT_EXCLUDES, AGGREGATED_SUMMARY_PROMPT
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
    def __init__(self, project_path, output_dir='./projects'):
        self.project_path = project_path
        self.project_name = Path(project_path).name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir = self.output_dir / 'backups'
        self.backups_dir.mkdir(exist_ok=True)
        # Create a summaries directory to store individual file summaries
        self.summaries_dir = self.output_dir / 'summaries'
        self.summaries_dir.mkdir(exist_ok=True)
        
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
            "file_selection": []
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
        return load_json(self.project_record_path)

    def update_project_record(self, data):
        record = self.get_project_record()
        if record:
            record.update(data)
            save_json(record, self.project_record_path)
        else:
            print(f"Warning: Could not load project record for {self.project_name}")

    def has_summary(self):
        return self.combined_json_path.exists()

    def get_summary_status(self):
        record = self.get_project_record()
        if not self.has_summary():
            return {"status": "not_summarized", "message": "Project has not been summarized yet."}

        summary_data = load_json(self.combined_json_path)
        if not summary_data:
            self.update_project_record({"status": "error_loading_summary"})
            return {"status": "error_loading_summary", "message": "Failed to load existing summary data."}

        modified_files = self.get_modified_files()
        if modified_files:
            self.update_project_record({"status": "needs_update"})
            return {
                "status": "needs_update",
                "message": f"Project summary needs updating. {len(modified_files)} file(s) modified since last check.",
                "modified_files": modified_files,
                "last_summarized": record.get("last_summarized"),
                "file_count": summary_data.get("file_count", 0)
            }
        else:
            self.update_project_record({"status": "up_to_date"})
            return {
                "status": "up_to_date",
                "message": "Project summary is up to date.",
                "last_summarized": record.get("last_summarized"),
                "file_count": summary_data.get("file_count", 0)
            }

    def compute_file_hash(self, file_path):
        abs_file_path = Path(file_path)
        if not abs_file_path.is_absolute():
            abs_file_path = Path(self.project_path) / file_path
        if not abs_file_path.is_file():
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
        current_hashes = load_json(self.file_hashes_path) or {}
        modified_files = []
        found_files = set()
        record = self.get_project_record()
        selected_files = set()

        if record and isinstance(record.get("file_selection"), list):
            def extract_checked(tree_nodes):
                paths = set()
                for node in tree_nodes:
                    if isinstance(node, dict):
                        if node.get("type") == "file" and node.get("checked"):
                            rel = node.get("relative_path")
                            if rel:
                                paths.add(str(rel).replace("\\", "/"))
                        elif node.get("type") == "folder":
                            paths.update(extract_checked(node.get("children", [])))
                return paths
            selected_files = extract_checked(record["file_selection"])

        project_path_obj = Path(self.project_path)
        if not project_path_obj.exists():
            print(f"Error: Project source path does not exist: {self.project_path}")
            return []

        for root, dirs, files in os.walk(self.project_path, topdown=True):
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
            for file in files:
                full_path = Path(root) / file
                try:
                    if full_path.is_relative_to(project_path_obj):
                        rel = str(full_path.relative_to(project_path_obj)).replace("\\", "/")
                    else:
                        continue
                except ValueError as e:
                    print(f"Warning: Could not compute relative path for {full_path}: {e}")
                    continue

                found_files.add(rel)
                should_check = not selected_files or rel in selected_files
                if should_check:
                    new_hash = self.compute_file_hash(full_path)
                    if new_hash is None:
                        continue
                    if rel not in current_hashes or current_hashes.get(rel) != new_hash:
                        modified_files.append(rel)
                        current_hashes[rel] = new_hash

        keys_to_remove = set(current_hashes.keys()) - found_files
        if selected_files:
            keys_to_remove.update(found_files - selected_files)
        for key in keys_to_remove:
            if key in current_hashes:
                del current_hashes[key]
        save_json(current_hashes, self.file_hashes_path)
        return modified_files

    def update_modified_summaries(self, modified_files, summarizer):
        if not self.combined_json_path.exists():
            print("Warning: Combined summary file does not exist. Creating a new structure.")
            combined = {
                "project_name": self.project_name,
                "files": {},
                "file_count": 0,
                "total_lines": 0,
                "project_summary": ""
            }
        else:
            combined = load_json(self.combined_json_path)
            if not combined or "files" not in combined:
                print("Warning: Invalid combined summary file. Creating new structure.")
                combined = {
                    "project_name": self.project_name,
                    "files": {},
                    "file_count": 0,
                    "total_lines": 0,
                    "project_summary": ""
                }

        print(f"Updating summaries for {len(modified_files)} file(s)...")
        project_path_obj = Path(self.project_path)
        for rel in modified_files:
            full_path = project_path_obj / rel.replace("\\", "/")
            if not full_path.exists():
                print(f"Warning: File {rel} not found. Removing from summary.")
                combined["files"].pop(rel, None)
                continue
            content = read_file_content(full_path)
            if content is None:
                print(f"Warning: Could not read {rel}.")
                continue
            print(f"Summarizing file: {rel}")
            try:
                detailed, concise = summarizer.summarize_file_combined(content, str(full_path))
                lines = len(content.splitlines())
                size = full_path.stat().st_size if full_path.exists() else 0
                file_entry = {
                    "path": rel,
                    "detailed_summary": detailed,
                    "concise_summary": concise,
                    "lines": lines,
                    "size": size
                }
                combined["files"][rel] = file_entry
                # Also save individual summary to summaries_dir
                out_file = self.summaries_dir / (safe_filename(rel) + ".json")
                save_json(file_entry, out_file)
            except Exception as e:
                print(f"Error summarizing {rel}: {e}")
                combined["files"][rel] = {
                    "path": rel,
                    "detailed_summary": f"Error: {e}",
                    "concise_summary": "Error summarizing file.",
                    "lines": 0,
                    "size": 0
                }
        if modified_files:
            print("Generating project-level summary...")
            aggregated = "\n\n".join(
                f"File: {path}\nSummary: {data.get('detailed_summary', 'N/A')}"
                for path, data in combined["files"].items()
                if isinstance(data, dict) and "Error" not in data.get("detailed_summary", "")
            )
            if aggregated:
                try:
                    prompt_project = AGGREGATED_SUMMARY_PROMPT.format(aggregated=aggregated)
                    project_summary = summarizer.get_llm_response_with_timeout(prompt_project)
                    combined["project_summary"] = project_summary
                    print("Project-level summary updated.")
                except Exception as e:
                    print(f"Error generating project summary: {e}")
                    combined["project_summary"] += f"\n\n[Error: {e}]"
            else:
                combined["project_summary"] = "No valid file summaries available."
        combined["file_count"] = len(combined["files"])
        combined["total_lines"] = sum(
            f.get("lines", 0) for f in combined["files"].values() if isinstance(f, dict)
        )
        save_json(combined, self.combined_json_path)
        print(f"Combined summary saved to {self.combined_json_path}")
        self.update_project_record({
            "last_summarized": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_count": combined["file_count"],
            "total_lines": combined["total_lines"],
            "status": "up_to_date"
        })
        return combined

    def combine_summaries(self):
        """Read all JSON files in self.summaries_dir and combine them into one summary."""
        combined = {
            "project_name": self.project_name,
            "files": {},
            "file_count": 0,
            "total_lines": 0,
            "project_summary": ""
        }
        for summary_file in self.summaries_dir.glob("*.json"):
            try:
                file_summary = load_json(summary_file)
                if file_summary and "path" in file_summary:
                    rel = file_summary["path"]
                    combined["files"][rel] = file_summary
            except Exception as e:
                print(f"Error reading summary {summary_file}: {e}")
        combined["file_count"] = len(combined["files"])
        combined["total_lines"] = sum(
            f.get("lines", 0) for f in combined["files"].values() if isinstance(f, dict)
        )
        save_json(combined, self.combined_json_path)
        print(f"Summaries combined into {self.combined_json_path}")
        return combined

    def update_file_hashes(self):
        """Refresh the file hashes by calling get_modified_files (which updates the hash file)."""
        _ = self.get_modified_files()

    def save_results(self, results):
        if not isinstance(results, dict):
            print(f"Error: Invalid results format: {type(results)}")
            return
        save_json(results, self.combined_json_path)
        print(f"Results saved to {self.combined_json_path}")
        self.update_project_record({
            "last_summarized": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_count": results.get("file_count", 0),
            "total_lines": results.get("total_lines", 0),
            "status": "up_to_date"
        })

    def generate_html_report(self, results):
        html = HTML_COMBINED_REPORT_TEMPLATE.format(
            project_name=results.get("project_name", self.project_name)
        )
        with open(self.combined_html_path, 'w', encoding='utf-8') as f:
            f.write(html)

    def load_query_history(self):
        if os.path.exists(self.query_history_path):
            history = load_json(self.query_history_path)
            return history if isinstance(history, list) else []
        return []

    def save_query_history(self, history):
        if isinstance(history, list):
            save_json(history, self.query_history_path)
        else:
            print(f"Error: Query history must be a list for {self.project_name}")

    def delete_query(self, query_id):
        history = self.load_query_history()
        history = [item for item in history if item.get("id") != query_id]
        self.save_query_history(history)

    def load_modifications_history(self):
        if os.path.exists(self.modifications_history_path):
            history = load_json(self.modifications_history_path)
            return history if isinstance(history, list) else []
        return []

    def save_modifications_history(self, history):
        if isinstance(history, list):
            save_json(history, self.modifications_history_path)
        else:
            print(f"Error: Modifications history must be a list for {self.project_name}")
