
# new app.py

import os
import json
import time
import uuid
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from project_manager import ProjectManager
from code_summarizer import CodeSummarizer
from query_handler import QueryHandler
from modification_handler import ModificationHandler
from project_config import ollama_client, openai_client, dsv3_client, claude_client, google_client

from utils import format_time, load_json, extract_json
from constants import DEFAULT_EXCLUDES, CODE_EXTENSIONS

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Mapping for available LLM clients
clients_mapping = {
    "google": google_client,
    "openai": openai_client,
    "ollama": ollama_client,
    "dsv3": dsv3_client,
    "anthropic": claude_client
}

DEFAULT_LOCAL_STORAGE = './projects'

# --- Helper Functions (init_session, format_datetime, nl2br) ---
# ... (Keep existing helper functions) ...
def init_session():
    if 'source_projects' not in session:
        session['source_projects'] = []
    if 'current_source_project' not in session:
        session['current_source_project'] = None
    if 'temp_id' not in session:
        session['temp_id'] = None # This might be redundant if current_temp_id is used
    if 'current_temp_id' not in session:
        session['current_temp_id'] = None

@app.template_filter('format_datetime')
def format_datetime(value, format='%Y-%m-%d %H:%M'):
    try:
        return value.strftime(format)
    except AttributeError:
        return 'N/A'

# @app.template_filter('nl2br')
# def nl2br(value):
#     """Convert newlines to <br> tags for HTML output."""
#     # Be careful using this on pre-formatted code/diffs
#     # return value.replace('\\n', '<br>') # Might be better handled by CSS white-space: pre-wrap
#     import jinja2
#     return jinja2.Markup(value.replace('\n', '<br>\n'))
@app.template_filter('nl2br')
def nl2br(value):
    """Convert newlines to <br> tags for HTML output."""
    return value.replace('\n', '<br>')

# --- Routes (home, select_project, build_file_tree, list_files, project_files, update_file_selection) ---
# ... (Keep existing routes, assuming they are correct) ...
@app.route("/", methods=["GET"])
def home():
    init_session()
    # Scan for existing local projects in the storage directory
    local_storage_dir = Path(DEFAULT_LOCAL_STORAGE)
    projects_list = []
    if local_storage_dir.exists():
        for sub in local_storage_dir.iterdir():
            if sub.is_dir():
                record_file = sub / "project_record.json"
                if record_file.exists():
                    try:
                        with open(record_file, 'r', encoding='utf-8') as f:
                            record = json.load(f)
                    except Exception:
                        record = {}
                    projects_list.append({
                        "project_name": sub.name,
                        "source_code_path": record.get("source_code_path", ""),
                        "local_storage_path": str(sub),
                        "has_summary": (sub / "combined_code_summary.json").exists()
                    })
    return render_template("home.html", projects=projects_list)

@app.route("/select_project", methods=["GET", "POST"])
def select_project():
    print(f"In select project...............{request.method}")
    if request.method == "GET":
        source_code_path = request.args.get("source_code_path", "")
        local_storage_path = request.args.get("local_storage_path", DEFAULT_LOCAL_STORAGE)
        project_name = Path(source_code_path).name
        # Pass the full project directory as local_storage_path for ProjectManager
        project_dir = Path(local_storage_path)
        if project_dir.exists() and (project_dir / "project_record.json").exists():
            pm = ProjectManager(source_code_path, str(project_dir))
            project_info = pm.get_project_info()
            for key, value in project_info.items():
                if isinstance(value, Path):
                    project_info[key] = str(value)
            session['current_source_project'] = project_info
            print(f"project_info: {project_info}\n")
            return redirect(url_for("project_dashboard"))
    else: # POST
        source_code_path = request.form.get("source_code_path", "")
        local_storage_path = request.form.get("local_storage_path", DEFAULT_LOCAL_STORAGE)

    print(f"source_code_path: {source_code_path}\nlocal_storage_path: {local_storage_path}")

    if not source_code_path:
        flash("No source code path provided", "error")
        return redirect(url_for("home"))

    # Create full project directory and pass it to the ProjectManager
    project_dir = Path(local_storage_path) / Path(source_code_path).name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Initialize ProjectManager with the full project directory
    project_manager = ProjectManager(source_code_path, str(project_dir))

    # If file selection is submitted, update file exclusion and selection info
    # This part seems related to initial setup, might not be hit often in POST here?
    # if request.method == "POST" and "selected_files" in request.form:
    #     selected_files = request.form.getlist("selected_files")
    #     # ... logic to update project record based on selected_files ...
    #     # This seems more relevant for /update_file_selection route

    source_project_info = project_manager.get_project_info()
    for key, value in source_project_info.items():
        if isinstance(value, Path):
            source_project_info[key] = str(value)
    session['current_source_project'] = source_project_info
    print(f"source_project_info saved in session: {source_project_info}\n")

    # Always redirect to dashboard after selecting/creating project info
    return redirect(url_for("project_dashboard"))


def build_file_tree(processable_files):
    """
    Build a hierarchical tree structure from a list of file dictionaries.
    Strictly excludes any paths containing DEFAULT_EXCLUDES folders.
    """
    tree = {}
    excluded_folders = set(DEFAULT_EXCLUDES)

    for file_info in processable_files:
        # Ensure relative_path is treated as a string
        relative_path = str(file_info.get('relative_path', ''))
        if not relative_path:
            continue  # Skip if path is empty

        # Normalize path separators for consistency
        relative_path = relative_path.replace('\\', '/')
        parts = relative_path.split('/')

        # Skip if any part is in excluded folders
        if any(part in excluded_folders for part in parts):
            continue

        current = tree
        for index, part in enumerate(parts):
            if index == len(parts) - 1: # It's a file
                current[part] = {
                    "type": "file",
                    "name": part,
                    "relative_path": relative_path, # Store normalized path
                    "checked": file_info.get('checked', False)
                }
            else: # It's a folder
                if part not in current:
                    current[part] = {
                        "type": "folder",
                        "name": part,
                        "children": {}
                    }
                # Handle potential conflict: path part exists but is a file
                if current[part]["type"] == "folder":
                    current = current[part]["children"]
                else:
                    print(f"Warning: Path conflict in build_file_tree for {relative_path} at part '{part}' - expected folder, found file.")
                    # Decide how to handle: skip, overwrite, log? Skipping for now.
                    break

    # Convert nested dictionary to list structure for easier template rendering
    def dict_to_list(d):
        lst = []
        # Sort keys to ensure consistent order (folders first, then files, alphabetically)
        sorted_keys = sorted(d.keys(), key=lambda k: (d[k].get("type", "file") == "folder", k))
        for key in sorted_keys:
            node = d[key]
            if node.get("type") == "folder":
                lst.append({
                    "type": "folder",
                    "name": node.get("name", key),
                    "children": dict_to_list(node.get("children", {}))
                })
            elif node.get("type") == "file":
                lst.append(node)
        return lst

    return dict_to_list(tree)

@app.route("/list_files", methods=["GET"])
def list_files():
    source_code_path = request.args.get("source_code_path", "")
    if not source_code_path:
        return jsonify({"error": "No source code path provided"}), 400
    if not os.path.exists(source_code_path):
        return jsonify({"error": "The provided source code path does not exist"}), 400

    files_list = []
    for root, dirs, files in os.walk(source_code_path):
        # Exclude specified directories
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
        # Filter root path itself if it contains excluded parts (less common, but possible)
        rel_root = os.path.relpath(root, source_code_path)
        if any(part in DEFAULT_EXCLUDES for part in Path(rel_root).parts):
            continue

        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in CODE_EXTENSIONS:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, source_code_path).replace('\\', '/')
                # Double-check exclusion based on relative path parts
                if not any(part in DEFAULT_EXCLUDES for part in Path(relative_path).parts):
                    files_list.append({
                        "webkitRelativePath": relative_path, # Use normalized path
                        "name": file
                    })
    return jsonify(files_list)

@app.route("/project_files", methods=["GET"])
def project_files():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))
    source_code_path = current_source_project['source_code_path']
    pm = ProjectManager(source_code_path, current_source_project['local_storage_path'])
    project_record = pm.get_project_record() or {}

    # --- Determine which files are currently selected/checked ---
    # Option 1: Use saved file_selection tree if available
    saved_file_tree = project_record.get("file_selection")
    checked_files_from_record = set()
    if isinstance(saved_file_tree, list):
        def extract_checked(nodes):
            checked = set()
            for node in nodes:
                if isinstance(node, dict):
                    if node.get("type") == "file" and node.get("checked") and node.get("relative_path"):
                        checked.add(str(node["relative_path"]).replace('\\', '/'))
                    elif node.get("type") == "folder":
                        checked.update(extract_checked(node.get("children", [])))
            return checked
        checked_files_from_record = extract_checked(saved_file_tree)

    # Option 2: Fallback or default - assume all non-excluded files are checked initially
    # Let's use the saved state primarily. If no saved state, default to checking all valid files.

    processable_files_info = []
    for root, dirs, files in os.walk(source_code_path):
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
        rel_root = os.path.relpath(root, source_code_path)
        if any(part in DEFAULT_EXCLUDES for part in Path(rel_root).parts):
            continue

        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in CODE_EXTENSIONS:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, source_code_path).replace('\\', '/')

                if not any(part in DEFAULT_EXCLUDES for part in Path(relative_path).parts):
                    # Determine checked status: use saved record if available, else default to True
                    is_checked = (relative_path in checked_files_from_record) if checked_files_from_record else True
                    processable_files_info.append({
                        "relative_path": relative_path,
                        "checked": is_checked
                    })

    # Build the tree structure based on the collected files and their checked status
    file_tree = build_file_tree(processable_files_info)
    # print(file_tree) # Debugging

    return render_template("project_files.html", source_project=current_source_project, file_tree=file_tree)


@app.route("/update_file_selection", methods=["POST"])
def update_file_selection():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
         flash("No source project selected", "error")
         return redirect(url_for("home"))

    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    selected_files_paths = set(request.form.getlist("selected_files")) # Get paths of checked files

    # Regenerate the list of all potentially processable files to compare against
    all_processable_files = []
    for root, dirs, files in os.walk(current_source_project['source_code_path']):
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
        rel_root = os.path.relpath(root, current_source_project['source_code_path'])
        if any(part in DEFAULT_EXCLUDES for part in Path(rel_root).parts):
            continue

        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in CODE_EXTENSIONS:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, current_source_project['source_code_path']).replace('\\', '/')
                if not any(part in DEFAULT_EXCLUDES for part in Path(relative_path).parts):
                     all_processable_files.append({
                         "relative_path": relative_path,
                         # Mark as checked if it was submitted in the form
                         "checked": (relative_path in selected_files_paths)
                     })

    # Build the file tree structure reflecting the new selection
    file_tree = build_file_tree(all_processable_files)

    # Update the project record
    project_record = pm.get_project_record() or {}
    project_record["file_selection"] = file_tree
    # Optional: Could also store project_wide_excludes derived from this, but the tree itself holds the state.
    # project_wide_excludes = [f["relative_path"] for f in all_processable_files if not f["checked"]]
    # project_record["project_wide_excludes"] = project_wide_excludes
    pm.update_project_record(project_record)

    flash("File selection updated", "success")
    return redirect(url_for("project_dashboard"))


# --- Routes (project_dashboard, refresh_project, combined_summary, summarize_project) ---
# ... (Keep existing routes, assuming they are correct) ...
@app.route("/project_dashboard", methods=["GET", "POST"])
def project_dashboard():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))

    source_code_path = str(current_source_project['source_code_path'])
    local_storage_path = str(current_source_project['local_storage_path'])
    pm = ProjectManager(source_code_path, local_storage_path)

    if request.method == "POST":
        # --- Handle Query Submission from Dashboard ---
        input_query = request.form.get("input_query", "")
        client_type = request.form.get("client_type", "openai") # Default to openai if not specified

        if not input_query:
            flash("Query cannot be empty.", "warning")
            return redirect(url_for("project_dashboard"))

        if not pm.has_summary():
            flash("Please summarize the source code first before querying.", "error")
            return redirect(url_for("project_dashboard"))

        # Ensure selected client exists
        if client_type not in clients_mapping:
             flash(f"Invalid client type '{client_type}' selected. Using default.", "warning")
             client_type = "openai" # Or your preferred default

        qh = QueryHandler(pm, clients_mapping)
        try:
            query_id = qh.process_query(input_query, client_type)
            if query_id:
                flash("Query processed. Review the details below.", "info")
                # Redirect to the detail page for the new query
                return redirect(url_for("query_detail", query_id=query_id))
            else:
                # More specific error? Check qh.process_query potential return values/exceptions
                flash("Failed to process query (QueryHandler returned None or empty ID). Check logs.", "error")
                return redirect(url_for("project_dashboard"))
        except Exception as e:
            flash(f"An error occurred while processing the query: {str(e)}", "error")
            print(f"Error processing query: {e}") # Log the full error
            # Consider logging traceback: import traceback; traceback.print_exc()
            return redirect(url_for("project_dashboard"))
        # --- End Query Submission Handling ---

    # --- Handle GET Request (Original Dashboard Logic) ---
    # get_summary_status() also updates hashes and project record status
    summary_status = pm.get_summary_status()
    # Load query history (now only contains modification queries)
    query_history = pm.load_query_history()
    # Load summary data for display (including the project summary)
    summary_data = load_json(str(pm.combined_json_path)) or {}

    return render_template("project_dashboard.html",
                           source_project=current_source_project,
                           summary_status=summary_status,
                           query_history=query_history, # Pass the filtered history
                           summary=summary_data, # Pass the full summary data
                           available_clients=list(clients_mapping.keys())) # Pass client names

@app.route("/refresh_project", methods=["POST"])
def refresh_project():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
         flash("No source project selected", "error")
         return redirect(url_for("home"))
    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    modified_files = pm.get_modified_files()  # This updates file_hashes.json and returns list.
    if modified_files:
         flash(f"{len(modified_files)} file(s) changed since last check. Consider updating summaries.", "info")
    else:
         flash("No file changes detected since last check.", "info")
    # Update the status in the project record after check
    pm.update_project_record({"status": "checked", "last_checked": datetime.now().isoformat()})
    return redirect(url_for("project_dashboard"))

@app.route("/combined_summary")
def combined_summary():
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home")) # Redirect home if no project
    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    if not pm.combined_json_path.exists():
        flash("Combined summary file not found.", "warning")
        return redirect(url_for("project_dashboard")) # Redirect dashboard if no summary
    try:
        summary_data = load_json(str(pm.combined_json_path))
        if not summary_data:
             raise ValueError("Summary file is empty or invalid JSON.")
    except Exception as e:
        flash(f"Error loading summary data: {e}", "error")
        return redirect(url_for("project_dashboard"))

    return render_template("combined_summary.html", source_project=current_source_project, summary=summary_data)

@app.route("/summarize_project", methods=["POST"])
def summarize_project():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))

    source_code_path = current_source_project['source_code_path']
    local_storage_path = current_source_project['local_storage_path']
    only_modified = request.form.get("only_modified", "false") == "true"
    client_type = request.form.get("client_type", "openai") # Default to openai
    print(f"Client selected for summarization: {client_type}")

    client = clients_mapping.get(client_type)
    if not client:
        flash(f"Warning: Client type '{client_type}' not found, using default (OpenAI).", "warning")
        client = clients_mapping.get("openai") # Fallback explicitly
        client_type = "openai" # Update type for flashing message

    # Initialize Summarizer with the selected client
    summarizer = CodeSummarizer(api_key=None, # API key managed by client instances
                                ollama_client=client # Pass the selected client
                                # fallout_client=... # Define fallback if needed by Summarizer
                               )
    pm = ProjectManager(source_code_path, local_storage_path)
    start_time = time.time()
    flash(f"Starting source code summarization using {client_type} at {format_time(start_time)}...", "info")
    # Update project status immediately
    pm.update_project_record({"status": "summarizing", "last_summary_start": datetime.now().isoformat()})

    results = None # Initialize results
    status_message = ""
    status_category = "info"

    try:
        if only_modified:
            modified_files = pm.get_modified_files() # updates hashes
            if not modified_files:
                status_message = "No modified files detected since last summary/check. Summaries are up-to-date."
                status_category = "info"
                pm.update_project_record({"status": "summarized"}) # Mark as summarized if no changes
            else:
                flash(f"Updating summaries for {len(modified_files)} modified file(s)...", "info")
                # update_modified_summaries handles saving and project summary refresh
                results = pm.update_modified_summaries(modified_files, summarizer)
                if results is None: # Check if update failed internally
                     status_message = "Attempted to update summaries, but process failed or yielded no results. Check logs."
                     status_category = "error"
                     pm.update_project_record({"status": "error"})
                # else: results were generated, success message below

        else: # Full scan requested
            flash("Performing full project summarization...", "info")
            project_record = pm.get_project_record() or {}
            selected_files = []
            # Extract selected files from project record's file_selection tree
            if project_record and isinstance(project_record.get("file_selection"), list):
                 def extract_checked_files(tree_nodes):
                     checked = []
                     for node in tree_nodes:
                          if isinstance(node, dict):
                              if node.get("type") == "file" and node.get("checked"):
                                   rel_path = node.get("relative_path")
                                   if rel_path: checked.append(str(rel_path).replace('\\','/')) # Ensure string, normalize
                              elif node.get("type") == "folder":
                                   # Recursively check children only if the folder itself implies inclusion
                                   # (Current logic includes file if checked, implicitly includes folders containing checked files)
                                   checked.extend(extract_checked_files(node.get("children", [])))
                     return list(set(checked)) # Return unique list
                 selected_files = extract_checked_files(project_record["file_selection"])

            if not selected_files:
                 flash("No files explicitly selected in project settings. Summarizing all detected code files based on extensions/exclusions.", "warning")
                 # scan_project generates file summaries and project summary
                 results = summarizer.scan_project(source_code_path, output_dir=pm.summaries_dir)
            else:
                 flash(f"Summarizing {len(selected_files)} selected files...", "info")
                 # scan_specific_files generates file summaries and project summary for the selection
                 results = summarizer.scan_specific_files(source_code_path, selected_files, output_dir=pm.summaries_dir)

            # Save results from full scan or specific files scan
            # update_modified_summaries saves internally, so only save here for full/specific scans
            if results and not only_modified:
                 # pm.save_results(results) # save_results updated hashes, combined summary, project record
                 # Refactored: scan methods now save individual summaries. Need to combine and update record.
                 pm.combine_summaries() # Combine individual json files
                 pm.update_file_hashes() # Update hashes based on current files
                 pm.update_project_record({ # Update record after successful full/specific scan
                     "status": "summarized",
                     "last_summary_end": datetime.now().isoformat(),
                     "summary_client": client_type
                 })


        elapsed = time.time() - start_time
        # Final status message based on whether results were generated/updated
        if results is not None: # Covers both modified and full/specific scans that yielded results
            status_message = f"Source code summarization/update completed in {elapsed:.2f} seconds using {client_type}."
            status_category = "success"
            # Project record update for 'summarized' status happens within update_modified_summaries or above for full scan
        elif status_category != "error" and not only_modified: # If full/specific scan yielded no results
            status_message = "Summarization process finished but did not produce results (perhaps no code files found or selected?)."
            status_category = "warning"
            pm.update_project_record({"status": "error"}) # Or maybe 'empty'?
        elif status_category == "info": # Case where only_modified=True and no files were modified
             pass # Message already set
        else: # Catch-all if no message set yet (shouldn't happen ideally)
             status_message = f"Summarization process finished in {elapsed:.2f} seconds, but outcome unclear."
             status_category = "warning"

    except Exception as e:
        elapsed = time.time() - start_time
        status_message = f"An error occurred during summarization after {elapsed:.2f} seconds: {str(e)}"
        status_category = "error"
        print(f"Summarization Error: {e}") # Log the full error
        # import traceback; traceback.print_exc() # For detailed debugging
        # Update project record status to error
        try:
             pm.update_project_record({"status": "error", "last_summary_end": datetime.now().isoformat()})
        except Exception as update_err:
             print(f"Failed to update project record status after error: {update_err}")

    flash(status_message, status_category)
    return redirect(url_for("project_dashboard"))


# --- Routes (query, query_detail, delete_query) ---
# ... (Keep existing routes, assuming they are correct) ...
@app.route("/query", methods=["GET", "POST"])
def query():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))

    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])

    if not pm.has_summary():
        flash("Please summarize the source code first before querying.", "error")
        return redirect(url_for("project_dashboard"))

    if request.method == "POST":
        input_query = request.form.get("input_query", "")
        client_type = request.form.get("client_type", "openai")

        if not input_query:
            flash("Query cannot be empty.", "warning")
            return redirect(url_for("query")) # Redirect back to query page

        if client_type not in clients_mapping:
             flash(f"Invalid client type '{client_type}' selected. Using default.", "warning")
             client_type = "openai"

        qh = QueryHandler(pm, clients_mapping)
        try:
            query_id = qh.process_query(input_query, client_type)
            if query_id:
                flash("Query processed. Review the details below.", "info")
                return redirect(url_for("query_detail", query_id=query_id))
            else:
                flash("Failed to process query (QueryHandler returned None or empty ID). Check logs.", "error")
                return redirect(url_for("query"))
        except Exception as e:
            flash(f"An error occurred while processing the query: {str(e)}", "error")
            print(f"Error processing query: {e}")
            # import traceback; traceback.print_exc()
            return redirect(url_for("query"))

    # GET request: Load history and render query page
    history = pm.load_query_history()
    return render_template("query.html",
                           history=history,
                           source_project=current_source_project,
                           available_clients=list(clients_mapping.keys()))

@app.route("/query/<query_id>")
def query_detail(query_id):
    init_session() # Ensure session context is available if needed
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected. Please select a project.", "warning")
        return redirect(url_for("home"))

    try:
        pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
        history = pm.load_query_history() # Expecting a list of dictionaries
    except Exception as e:
        flash(f"Error loading project data: {e}", "error")
        return redirect(url_for("project_dashboard")) # Or url_for("home")

    # Find the dictionary entry using .get() for safer key access
    entry = next((item for item in history if item.get("id") == query_id), None)

    if not entry:
        flash(f"Query with ID '{query_id}' not found in history.", "warning")
        return redirect(url_for("project_dashboard")) # Or query list page

    # --- Timestamp Conversion Logic (if needed, seems less critical now) ---
    timestamp_value = entry.get('timestamp')
    if isinstance(timestamp_value, str):
        # Attempt to parse ISO format first, then fallback
        parsed_time = None
        try:
            # Python 3.7+ supports fromisoformat directly
            parsed_time = datetime.fromisoformat(timestamp_value)
        except ValueError:
            # Fallback to common formats if ISO fails
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    parsed_time = datetime.strptime(timestamp_value, fmt)
                    break
                except ValueError:
                    pass
        if parsed_time:
             entry['timestamp'] = parsed_time
        else:
             print(f"Warning: Could not parse timestamp string '{timestamp_value}'. Displaying as is.")
             # Keep original string if parsing fails, template filter can handle it
    # If it's already a datetime object or None, it's fine.

    return render_template(
        "query_detail.html",
        entry=entry,
        source_project=current_source_project,
        queries=history, # Pass the full history for the sidebar
        available_clients=list(clients_mapping.keys()) # For modify dropdown
    )


@app.route("/delete_query/<query_id>", methods=["POST"])
def delete_query(query_id):
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        # Return JSON error response if called via JS, otherwise redirect
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "No project selected"}), 400
        return redirect(url_for("home"))

    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    deleted = pm.delete_query(query_id) # Assume returns True if deleted, False otherwise

    if deleted:
        flash("Query deleted successfully", "success")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": True, "redirect": url_for("query")}), 200
        return redirect(url_for("query")) # Redirect to the main query list
    else:
        flash("Query not found or could not be deleted.", "warning")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Query not found"}), 404
        return redirect(url_for("query"))


# --- Modification Routes ---

@app.route("/modify/<query_id>", methods=["POST"])
def modify_files(query_id):
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))

    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    client_type = request.form.get("client_type", "openai") # Get selected client

    if client_type not in clients_mapping:
        flash(f"Invalid client type '{client_type}' selected. Using default.", "warning")
        client_type = "openai"

    mod_handler = ModificationHandler(pm, clients_mapping)

    # prepare_modification_prompt now returns (temp_id, prompt_for_display, small_session_data)
    # result = mod_handler.prepare_modification_prompt(query_id, client_type)
# ----
    # prepare_modification_prompt now returns (temp_id, prompt_for_display, small_session_data)
    temp_id, prompt_display, small_data = mod_handler.prepare_modification_prompt(query_id, client_type)

    if not temp_id or not small_data:
        flash("Failed to prepare modification prompt. Check logs and query response.", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    # Store the SMALL data dictionary in the session, keyed by temp_id
    session[temp_id] = small_data
    # Store the current temp_id under a known key
    session['current_temp_id'] = temp_id

    # Pass only the prompt_display to the template
    return render_template("confirm_prompt.html", query_id=query_id, prompt=prompt_display)

@app.route("/generate_modifications/<query_id>", methods=["POST"])
def generate_modifications(query_id):
    init_session()
    current_source_project = session.get('current_source_project')
    temp_id = session.get('current_temp_id')  # Get the ID of the current modification process

    if not current_source_project or not temp_id:
        flash("Session data missing or expired. Please start the modification process again.", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    # Retrieve the small session data stored earlier using temp_id
    small_session_data = session.get(temp_id)
    if not small_session_data:
        flash(f"Session data missing for modification {temp_id}. Please start again.", "error")
        session.pop('current_temp_id', None)
        session.modified = True
        return redirect(url_for("query_detail", query_id=query_id))

    pm = ProjectManager(current_source_project['source_code_path'],
                        current_source_project['local_storage_path'])
    mod_handler = ModificationHandler(pm, clients_mapping)

    # Process modifications; this calls the LLM and generates a preview (with diffs for both old and new files)
    result = mod_handler.process_modifications(temp_id, small_session_data)
    if result is None or result.get("error"):
        error_msg = result.get("error", "Failed to generate modifications. LLM call or response parsing likely failed.")
        flash(error_msg, "error")
        return redirect(url_for("query_detail", query_id=query_id))

    preview_modifications = result.get("preview")
    if preview_modifications is None:
        flash("Modification generation finished, but no preview data was returned. Check logs.", "warning")
        return redirect(url_for("query_detail", query_id=query_id))

    # Update session small data with LLM details
    small_session_data['llm_response'] = result.get('llm_response', '')
    small_session_data['llm_response_time'] = result.get('llm_response_time', 0)
    session[temp_id] = small_session_data
    session.modified = True

    # Save the preview modifications into a JSON file under the current query id.
    proposed_modifications_dir = os.path.join(current_source_project['local_storage_path'], "proposed_modifications")
    os.makedirs(proposed_modifications_dir, exist_ok=True)
    proposed_modifications_file = os.path.join(proposed_modifications_dir, f"{query_id}.json")
    try:
        with open(proposed_modifications_file, "w", encoding="utf-8") as f:
            json.dump(preview_modifications, f, indent=4)
        app.logger.info(f"Stored proposed modifications to {proposed_modifications_file}")
    except Exception as e:
        flash(f"Error saving proposed modifications file: {str(e)}", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    # Render the preview template without passing modifications_json via the form.
    return render_template("preview_modification.html",
                           query_id=query_id,
                           modifications=preview_modifications)
@app.route("/accept_modifications/<query_id>", methods=["POST"])
def accept_modifications(query_id):
    init_session()
    current_source_project = session.get('current_source_project')
    temp_id = session.get('current_temp_id')
    app.logger.info(f"Current source project: {current_source_project}, Temp ID: {temp_id}")

    if not current_source_project or not temp_id:
        flash("Session data missing or expired. Please start the modification process again.", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    small_session_data = session.get(temp_id)
    if not small_session_data:
        flash(f"Session data missing for modification {temp_id}. Please start again.", "error")
        session.pop('current_temp_id', None)
        session.modified = True
        return redirect(url_for("query_detail", query_id=query_id))

    # Instead of retrieving the modifications JSON from the form, load it from the stored file.
    proposed_modifications_dir = os.path.join(current_source_project['local_storage_path'], "proposed_modifications")
    proposed_modifications_file = os.path.join(proposed_modifications_dir, f"{query_id}.json")
    if not os.path.exists(proposed_modifications_file):
        flash("Proposed modifications file not found. Please generate modifications again.", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    try:
        with open(proposed_modifications_file, "r", encoding="utf-8") as f:
            modifications_to_apply = json.load(f)
    except Exception as e:
        flash(f"Error reading proposed modifications file: {str(e)}", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    # Validate the modifications structure
    if not isinstance(modifications_to_apply, list):
        flash("Proposed modifications data is not in the expected format.", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    for idx, m in enumerate(modifications_to_apply):
        if not isinstance(m, dict):
            flash(f"Invalid modification item at index {idx}.", "error")
            return redirect(url_for("query_detail", query_id=query_id))
        if 'file_path' not in m or not isinstance(m['file_path'], str) or not m['file_path']:
            flash(f"Modification item at index {idx} missing or invalid 'file_path'.", "error")
            return redirect(url_for("query_detail", query_id=query_id))
        if 'new_code' not in m or not isinstance(m['new_code'], str):
            flash(f"Modification item at index {idx} missing or invalid 'new_code'.", "error")
            return redirect(url_for("query_detail", query_id=query_id))

    pm = ProjectManager(current_source_project['source_code_path'],
                        current_source_project['local_storage_path'])
    mod_handler = ModificationHandler(pm, clients_mapping)

    modification_result = mod_handler.apply_modifications(temp_id, small_session_data, modifications_to_apply)

    # Clean up session keys after applying modifications.
    session.pop(temp_id, None)
    session.pop('current_temp_id', None)
    session.modified = True

    if not modification_result or not modification_result.get("success"):
        error_msg = modification_result.get("error", "Failed to apply modifications. Check logs for details.")
        flash(error_msg, "error")
        return redirect(url_for("query_detail", query_id=query_id))

    new_modification_id = modification_result.get("id")
    flash(f"Modifications applied successfully (ID: {new_modification_id})! Project summaries may need updating.", "success")
    return redirect(url_for("project_dashboard"))


@app.route("/cancel_modification/<query_id>", methods=["GET", "POST"]) # Allow GET if using a link, POST if using form
def cancel_modification(query_id):
    init_session()
    temp_id = session.get('current_temp_id')

    if temp_id:
        # Retrieve PM details to instantiate handler for cleanup
        current_source_project = session.get('current_source_project')
        if current_source_project:
             try:
                 pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
                 # Pass mapping just to instantiate, might not be needed for cleanup
                 mod_handler = ModificationHandler(pm, clients_mapping)
                 mod_handler.cleanup_temp_file(temp_id) # Call cleanup explicitly
                 print(f"Cleaned up temp file for cancelled modification: {temp_id}")
             except Exception as e:
                 print(f"Error during modification cleanup for {temp_id}: {e}")
                 flash("Error during cleanup, but cancelling process anyway.", "warning")

        # Clean up session keys regardless of cleanup success
        session.pop(temp_id, None)
        session.pop('current_temp_id', None)
        session.modified = True
        flash("Modification process cancelled.", "info")
    else:
        flash("No active modification process found in session to cancel.", "warning")

    # Redirect back to the query detail page where the modification was initiated
    return redirect(url_for('query_detail', query_id=query_id))


# --- Modification History Routes ---
# ... (Keep existing routes: modifications_list, modification_detail, revert_file) ...
@app.route("/modifications")
def modifications_list():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))
    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    modifications = pm.load_modifications_history() # Expecting list sorted newest first?
    return render_template("modifications.html", modifications=modifications, source_project=current_source_project)

@app.route("/modification/<modification_id>")
def modification_detail(modification_id):
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))
    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    modifications = pm.load_modifications_history()
    modification = next((item for item in modifications if item.get("id") == modification_id), None)

    if not modification:
        flash("Modification record not found", "error")
        return redirect(url_for("modifications_list"))

    # Try to find the original query for context
    query = None
    query_id = modification.get("query_id")
    if query_id:
        history = pm.load_query_history()
        query = next((item for item in history if item.get("id") == query_id), None)

    # Enhancement: Load diffs for display if not stored directly
    # This might involve ModificationHandler having a method to regenerate diffs from backups
    # For now, assume 'applied_modifications' list in the record has enough info or diffs are stored.
    # Example structure assumed in modification record:
    # modification = {
    #    "id": "...", "timestamp": "...", "query_id": "...", "client_type": "...",
    #    "llm_response": "...", "llm_response_time": ...,
    #    "applied_modifications": [
    #        {"file_path": "...", "backup_path": "...", "is_new": True/False, /* maybe diff here? */}, ...
    #    ]
    # }
    # If diffs need generating on the fly, you'd call a handler method here.

    return render_template("modification_detail.html",
                           modification=modification,
                           query=query, # Pass found query, can be None
                           source_project=current_source_project)


@app.route("/revert/<modification_id>/<path:file_path>", methods=["POST"])
def revert_file(modification_id, file_path):
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))

    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    # Pass mappings if handler needs client info, though likely not for revert
    mod_handler = ModificationHandler(pm, clients_mapping)
    success = mod_handler.revert_file(modification_id, file_path)

    if success:
        flash(f"Successfully reverted '{file_path}' to its state before modification {modification_id}", "success")
    else:
        flash(f"Failed to revert '{file_path}'. Backup might be missing or an error occurred.", "error")

    # Redirect back to the detail page of the modification being reverted
    return redirect(url_for("modification_detail", modification_id=modification_id))


# --- Deprecated Route ---
# @app.route("/update_summaries_for_modified", methods=["POST"])
# def update_summaries_for_modified():
#     flash("Functionality moved to dashboard button submitting to /summarize_project with 'only_modified=true'.", "info")
#     return redirect(url_for('project_dashboard'))

# --- Main Execution ---
if __name__ == "__main__":
    # Use environment variables for config, with defaults
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ["true", "1", "yes"]
    print(f" * Starting Flask server on http://{host}:{port}/ (Debug: {debug})")
    app.run(debug=debug, host=host, port=port)
