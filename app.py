# app.py
import os
import json
import time
import uuid  # Ensure uuid is imported
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from project_manager import ProjectManager
from code_summarizer import CodeSummarizer
from query_handler import QueryHandler
from modification_handler import ModificationHandler
from project_config import ollama_client, openai_client, dsv3_client, claude_client
from utils import format_time, load_json, extract_json  # Ensure extract_json is imported if needed directly here
from constants import DEFAULT_EXCLUDES, CODE_EXTENSIONS

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Mapping for available LLM clients
clients_mapping = {
    "openai": openai_client,
    "ollama": ollama_client,
    "dsv3": dsv3_client,
    "anthropic": claude_client
}

DEFAULT_LOCAL_STORAGE = './projects'

def init_session():
    if 'source_projects' not in session:
        session['source_projects'] = []
    if 'current_source_project' not in session:
        session['current_source_project'] = None
    if 'temp_id' not in session:
        session['temp_id'] = None
@app.template_filter('format_datetime')
def format_datetime(value, format='%Y-%m-%d %H:%M'):
    try:
        return value.strftime(format)
    except AttributeError:
        return 'N/A'
@app.template_filter('nl2br')
def nl2br(value):
    """Convert newlines to <br> tags for HTML output."""
    return value.replace('\n', '<br>')

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
    else:
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
    if request.method == "POST" and "selected_files" in request.form:
        selected_files = request.form.getlist("selected_files")
        processable_files = []
        for root, dirs, files in os.walk(source_code_path):
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in CODE_EXTENSIONS:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, source_code_path)
                    processable_files.append(relative_path)
        # Also build the file tree selection information
        file_tree = build_file_tree([{"relative_path": f, "checked": (f in selected_files)} for f in processable_files])
        
        project_record = project_manager.get_project_record() or {}
        project_record["file_selection"] = file_tree
        # Ensure that the project record is fully serializable
        project_manager.update_project_record(project_record)
    
    source_project_info = project_manager.get_project_info()
    for key, value in source_project_info.items():
        if isinstance(value, Path):
            source_project_info[key] = str(value)
    session['current_source_project'] = source_project_info
    print(f"source_project_info saved in session: {source_project_info}\n")
    if request.method == "POST":
        return redirect(url_for("project_files"))
    else:
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

        parts = relative_path.split(os.sep)

        # Skip if any part is in excluded folders
        if any(part in excluded_folders for part in parts):
            continue

        current = tree
        for index, part in enumerate(parts):
            if index == len(parts) - 1:
                current[part] = {
                    "type": "file",
                    "name": part,
                    "relative_path": relative_path,
                    "checked": file_info.get('checked', False)
                }
            else:
                if part not in current:
                    current[part] = {
                        "type": "folder",
                        "name": part,
                        "children": {}
                    }
                if current[part]["type"] == "folder":
                    current = current[part]["children"]
                else:
                    print(f"Warning: Path conflict in build_file_tree for {relative_path} at part '{part}'")
                    break

    def dict_to_list(d):
        lst = []
        for key in sorted(d.keys()):
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
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in CODE_EXTENSIONS:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, source_code_path)
                files_list.append({
                    "webkitRelativePath": relative_path,
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
    project_wide_excludes = project_record.get("project_wide_excludes", [])
    processable_files = []
    for root, dirs, files in os.walk(source_code_path):
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
        for file in files:
            print(file)
            ext = os.path.splitext(file)[1]
            if ext in CODE_EXTENSIONS:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, source_code_path)
                is_excluded = relative_path in project_wide_excludes
                processable_files.append({
                    "relative_path": relative_path,
                    "checked": not is_excluded
                })
    file_tree = build_file_tree(processable_files)
    print(file_tree)
    return render_template("project_files.html", source_project=current_source_project, file_tree=file_tree)

@app.route("/update_file_selection", methods=["POST"])
def update_file_selection():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
         flash("No source project selected", "error")
         return redirect(url_for("home"))
    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    processable_files = []
    for root, dirs, files in os.walk(current_source_project['source_code_path']):
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in CODE_EXTENSIONS:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, current_source_project['source_code_path'])
                processable_files.append(relative_path)
    selected_files = request.form.getlist("selected_files")
    project_wide_excludes = [f for f in processable_files if f not in selected_files]
    file_tree = build_file_tree([{"relative_path": f, "checked": (f in selected_files)} for f in processable_files])
    
    project_record = pm.get_project_record() or {}
    project_record["file_selection"] = file_tree
    pm.update_project_record(project_record)
    flash("File selection updated", "success")
    return redirect(url_for("project_dashboard"))

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
        client_type = request.form.get("client_type", "openai")

        if not input_query:
            flash("Query cannot be empty.", "warning")
            return redirect(url_for("project_dashboard"))

        if not pm.has_summary():
            flash("Please summarize the source code first before querying.", "error")
            return redirect(url_for("project_dashboard"))

        qh = QueryHandler(pm, clients_mapping)
        try:
            query_id = qh.process_query(input_query, client_type)
            if query_id:
                flash("Query processed. Review the details below.", "info")
                # Redirect to the detail page for the new query
                return redirect(url_for("query_detail", query_id=query_id))
            else:
                flash("Failed to process query (QueryHandler returned None).", "error")
                return redirect(url_for("project_dashboard"))
        except Exception as e:
            flash(f"An error occurred while processing the query: {str(e)}", "error")
            print(f"Error processing query: {e}")
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
                           summary=summary_data) # Pass the full summary data

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
         flash(f"{len(modified_files)} file(s) changed. Please update summaries.", "info")
    else:
         flash("No changes detected.", "info")
    return redirect(url_for("project_dashboard"))

@app.route("/combined_summary")
def combined_summary():
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        return "No source project selected", 404
    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    if not pm.combined_json_path.exists():
        return "Summary not found", 404
    summary_data = load_json(str(pm.combined_json_path))
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
    client_type = request.form.get("client_type", "openai")
    print(f"Client selected for summarization: {client_type}")

    client = clients_mapping.get(client_type, openai_client) # Use mapping, fallback to openai
    # Consider if a different fallback is desired or if error should be raised
    if client_type not in clients_mapping:
        flash(f"Warning: Client type '{client_type}' not found, using default.", "warning")

    # The 'fallout_client' in CodeSummarizer seems unused based on get_llm_response_with_timeout logic.
    # Let's simplify its initialization if fallout_client is indeed handled internally by get_llm_response_with_timeout's fallback.
    # If CodeSummarizer needs a specific fallback client instance, pass it here.
    # Assuming get_llm_response_with_timeout handles fallback internally for now.
    summarizer = CodeSummarizer(api_key=None, # API key managed by client instances
                                ollama_client=client, # Pass the selected client here
                                # fallout_client=openai_client # Pass fallback if CodeSummarizer uses it explicitly
                                )
    pm = ProjectManager(source_code_path, local_storage_path)
    start_time = time.time()
    flash(f"Starting source code summarization using {client_type} at {format_time(start_time)}", "info")

    results = None # Initialize results
    try:
        if only_modified:
            # get_modified_files updates hashes and returns list
            modified_files = pm.get_modified_files()
            if not modified_files:
                flash("No modified files detected since last summary/check.", "info")
                # No need to redirect here, let it fall through to update record below
                # return redirect(url_for("project_dashboard")) # Old logic
            else:
                flash(f"Updating summaries for {len(modified_files)} modified file(s)...", "info")
                # update_modified_summaries now handles saving and project summary refresh internally
                results = pm.update_modified_summaries(modified_files, summarizer)
                if results is None: # Check if update failed
                     flash("Failed to update summaries for modified files.", "error")

        else: # Full scan requested
            flash("Performing full project summarization...", "info")
            project_record = pm.get_project_record()
            selected_files = []
            # Extract selected files from project record's file_selection tree
            if project_record and isinstance(project_record.get("file_selection"), list):
                 def extract_checked_files(tree_nodes):
                     checked = []
                     for node in tree_nodes:
                          if isinstance(node, dict):
                              if node.get("type") == "file" and node.get("checked"):
                                   rel_path = node.get("relative_path")
                                   if rel_path: checked.append(str(rel_path)) # Ensure string
                              elif node.get("type") == "folder":
                                   checked.extend(extract_checked_files(node.get("children", [])))
                     return checked
                 selected_files = extract_checked_files(project_record["file_selection"])

            if not selected_files:
                 flash("No files selected in project settings. Performing scan based on default extensions/exclusions.", "warning")
                 # scan_project generates file summaries and project summary
                 results = summarizer.scan_project(source_code_path)
            else:
                 flash(f"Summarizing {len(selected_files)} selected files...", "info")
                 # scan_specific_files generates file summaries and project summary for the selection
                 results = summarizer.scan_specific_files(source_code_path, selected_files)

            # Save results from full scan or specific files scan
            # update_modified_summaries saves internally, so only save here for full/specific scans
            if results and not only_modified:
                 pm.save_results(results) # save_results now also updates project record

        elapsed = time.time() - start_time
        # Success/completion message depends on whether results were generated
        if results:
            flash(f"Source code summarization completed in {elapsed:.2f} seconds", "success")
            # Project record is updated within save_results or update_modified_summaries
        elif not only_modified: # If full/specific scan yielded no results
            flash("Summarization process did not produce results.", "warning")
        # If only_modified and no files needed update, message was already flashed

        # -------------------------------------------------------------------- #
        # --- REMOVED Query History Update for Summarization Runs ---
        # The following block that created 'summary_entry' and saved it to
        # query history has been removed as per the requirement.
        #
        # summary_entry = { ... }
        # history = pm.load_query_history()
        # history.append(summary_entry)
        # pm.save_query_history(history)
        # -------------------------------------------------------------------- #

    except Exception as e:
        flash(f"An error occurred during summarization: {str(e)}", "error")
        print(f"Summarization Error: {e}")
        # Optionally update project record status to error
        try:
             pm.update_project_record({"status": "error"})
        except Exception as update_err:
             print(f"Failed to update project record status after error: {update_err}")


    return redirect(url_for("project_dashboard"))

@app.route("/query", methods=["GET", "POST"])
def query():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))

    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])

    if not pm.has_summary():
        flash("Please summarize the source code first", "error")
        return redirect(url_for("project_dashboard"))

    if request.method == "POST":
        input_query = request.form.get("input_query", "")
        client_type = request.form.get("client_type", "openai")

        if not input_query:
            flash("Query cannot be empty.", "warning")
            return redirect(url_for("query"))

        qh = QueryHandler(pm, clients_mapping)
        try:
            query_id = qh.process_query(input_query, client_type)
            if query_id:
                flash("Query processed. Review the details below.", "info")
                return redirect(url_for("query_detail", query_id=query_id))
            else:
                flash("Failed to process query.", "error")
                return redirect(url_for("query"))
        except Exception as e:
            flash(f"An error occurred while processing the query: {str(e)}", "error")
            print(f"Error processing query: {e}")
            return redirect(url_for("query"))

    history = pm.load_query_history()
    return render_template("query.html", history=history, source_project=current_source_project)

@app.route("/query/<query_id>")
def query_detail(query_id):
    init_session() # Ensure session context is available if needed
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected. Please select a project.", "warning")
        return redirect(url_for("home"))

    try:
        # Assuming ProjectManager requires these paths
        pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
        history = pm.load_query_history() # Expecting a list of dictionaries
    except Exception as e:
        flash(f"Error loading project data: {e}", "error")
        # Redirect to a more appropriate place if PM fails, maybe dashboard
        return redirect(url_for("project_dashboard")) # Or url_for("home")

    # Find the dictionary entry using .get() for safer key access in the loop
    entry = next((item for item in history if item.get("id") == query_id), None)

    # --- Check if entry was found ---
    if not entry:
        flash(f"Query with ID '{query_id}' not found in history.", "warning")
        # Redirect to the project dashboard or query list page might be better
        return redirect(url_for("project_dashboard")) # Or wherever query history is listed

    # --- Timestamp Conversion Logic ---
    # Define the format your timestamp *string* is expected to be in
    # Example: '2023-10-27 10:30:00.123456' -> "%Y-%m-%d %H:%M:%S"
    # Example: '2023-10-27 10:30:00' -> "%Y-%m-%d %H:%M:%S"
    timestamp_format = "%Y-%m-%d %H:%M:%S" # ADJUST THIS FORMAT if necessary based on your actual string data

    timestamp_value = entry.get('timestamp') # Safely get the timestamp value

    if isinstance(timestamp_value, str): # Check if it's a string that needs conversion
        try:
            # Convert the string to a datetime object and update the dictionary
            entry['timestamp'] = datetime.strptime(timestamp_value, timestamp_format)
        except (ValueError, TypeError) as e:
            # Handle cases where conversion fails (e.g., wrong format, invalid date)
            print(f"Warning: Could not parse timestamp string '{timestamp_value}'. Error: {e}")
            entry['timestamp'] = None # Set to None if conversion fails
    # If timestamp_value is already a datetime object, None, or the key doesn't exist,
    # entry['timestamp'] will either retain its original non-string value or remain None.

    # --- Render Template ---
    # Pass the modified entry dictionary and history list to the template
    return render_template(
        "query_detail.html",
        entry=entry,
        source_project=current_source_project,
        queries=history # Pass the full history for the sidebar
    )

@app.route("/delete_query/<query_id>", methods=["POST"])
def delete_query(query_id):
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))
    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    pm.delete_query(query_id)
    flash("Query deleted successfully", "success")
    return redirect(url_for("query"))

@app.route("/modify/<query_id>", methods=["POST"])
def modify_files(query_id):
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))

    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    mod_handler = ModificationHandler(pm, clients_mapping)
    client_type = request.form.get("client_type", "openai")

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
    temp_id = session.get('current_temp_id')

    if not current_source_project or not temp_id:
        flash("Session data missing. Please start the modification process again.", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    # Retrieve the SMALL data dictionary from the session
    small_session_data = session.get(temp_id)
    if not small_session_data:
        flash(f"Session data missing for modification {temp_id}. Please start again.", "error")
        session.pop('current_temp_id', None) # Clean up pointer
        return redirect(url_for("query_detail", query_id=query_id))

    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    mod_handler = ModificationHandler(pm, clients_mapping)

    # Pass temp_id and the small session data to process_modifications
    result = mod_handler.process_modifications(temp_id, small_session_data)
    # result is expected to be {'preview': ..., 'llm_response': ..., 'llm_response_time': ...} or None

    if result is None or result.get("preview") is None:
        flash("Failed to generate modifications. Check logs (LLM call or parsing failed).", "error")
        # Optionally cleanup temp file here if failure is definitive? Or leave for manual/later cleanup.
        # mod_handler.cleanup_temp_file(temp_id) # Uncomment to cleanup on failure
        # session.pop(temp_id, None)
        # session.pop('current_temp_id', None)
        return redirect(url_for("query_detail", query_id=query_id))

    preview_modifications = result["preview"]

    # --- IMPORTANT: Store LLM details back into the session's small data dict ---
    # This makes them available to apply_modifications for the history record
    small_session_data['llm_response'] = result.get('llm_response', '')
    small_session_data['llm_response_time'] = result.get('llm_response_time', 0)
    session[temp_id] = small_session_data # Update the session data

    modifications_json = json.dumps(preview_modifications)

    return render_template("preview_modification.html",
                           query_id=query_id,
                           modifications=preview_modifications,
                           modifications_json=modifications_json)


@app.route("/accept_modifications/<query_id>", methods=["POST"])
def accept_modifications(query_id):
    init_session()
    current_source_project = session.get('current_source_project')
    temp_id = session.get('current_temp_id')

    if not current_source_project or not temp_id:
        flash("Session data missing. Please start again.", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    small_session_data = session.get(temp_id)
    if not small_session_data:
        flash(f"Session data missing for modification {temp_id}. Please start again.", "error")
        session.pop('current_temp_id', None)
        return redirect(url_for("query_detail", query_id=query_id))

    modifications_json_str = request.form.get("modifications_json")

    # --- DEBUG PRINT ---
    print("-" * 20)
    print(f"Received modifications_json string in accept_modifications (temp_id: {temp_id}):")
    # Print first 500 chars to avoid flooding logs if it's huge
    print(modifications_json_str[:500] + ("..." if len(modifications_json_str) > 500 else ""))
    print("-" * 20)
    # --- END DEBUG PRINT ---

    try:
        modifications_to_apply = json.loads(modifications_json_str)
        # Add more robust validation
        if not isinstance(modifications_to_apply, list):
             raise ValueError("Modifications data is not a list.")
        if not all(isinstance(m, dict) and 'file_path' in m and 'new_code' in m for m in modifications_to_apply):
             # Find the first invalid item for better debugging
             invalid_item = next((item for item in modifications_to_apply if not (isinstance(item, dict) and 'file_path' in item and 'new_code' in item)), None)
             raise ValueError(f"Invalid modification item structure. Problematic item (or first found): {invalid_item}")

    except (json.JSONDecodeError, ValueError, TypeError) as e: # Added TypeError
        flash(f"Error processing modifications data: {str(e)}", "error")
        print(f"Error decoding or validating modifications JSON: {e}") # Log the error server-side
        # Don't clean up session yet, might need to retry or debug
        return redirect(url_for("query_detail", query_id=query_id)) # Or maybe back to preview?


    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    mod_handler = ModificationHandler(pm, clients_mapping)

    modification_id = mod_handler.apply_modifications(temp_id, small_session_data, modifications_to_apply)

    # Clean up session data AFTER apply_modifications call (success or failure)
    session.pop(temp_id, None)
    session.pop('current_temp_id', None)

    if not modification_id:
        flash("Failed to apply modifications (check logs). Temp files might still exist if error occurred before cleanup.", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    flash("Modifications applied successfully! Summary may need updating.", "success")
    return redirect(url_for("project_dashboard")) # Redirect to dashboard after success
# Add a route or logic to handle cancellation and cleanup temp files
@app.route("/cancel_modification/<query_id>", methods=["POST"]) # Or GET if using a link
def cancel_modification(query_id):
    init_session()
    temp_id = session.get('current_temp_id')
    if temp_id:
        # Need PM to get handler to cleanup file
        current_source_project = session.get('current_source_project')
        if current_source_project:
             pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
             mod_handler = ModificationHandler(pm, clients_mapping) # Need mapping just to instantiate
             mod_handler.cleanup_temp_file(temp_id) # Call cleanup explicitly

        # Clean up session keys regardless
        session.pop(temp_id, None)
        session.pop('current_temp_id', None)
        flash("Modification process cancelled.", "info")
    else:
        flash("No active modification process found to cancel.", "warning")

    # Redirect back to the query detail page
    return redirect(url_for('query_detail', query_id=query_id))
@app.route("/modifications")
def modifications_list():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))
    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    modifications = pm.load_modifications_history()
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
    modification = next((item for item in modifications if item["id"] == modification_id), None)
    if not modification:
        flash("Modification not found", "error")
        return redirect(url_for("modifications_list"))
    history = pm.load_query_history()
    query = next((item for item in history if item["id"] == modification["query_id"]), None)
    return render_template("modification_detail.html", modification=modification, query=query, source_project=current_source_project)

@app.route("/revert/<modification_id>/<path:file_path>", methods=["POST"])
def revert_file(modification_id, file_path):
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))
    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
    mod_handler = ModificationHandler(pm)
    success = mod_handler.revert_file(modification_id, file_path)
    if success:
        flash(f"Successfully reverted {file_path}", "success")
    else:
        flash(f"Failed to revert {file_path}", "error")
    return redirect(url_for("modification_detail", modification_id=modification_id))

@app.route("/update_summaries_for_modified", methods=["POST"])
def update_summaries_for_modified():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))
    flash("Functionality moved to dashboard button submitting to /summarize_project.", "info")
    return redirect(url_for('project_dashboard'))

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", True),
            host=os.environ.get("FLASK_HOST", "127.0.0.1"),
            port=int(os.environ.get("FLASK_PORT", 5000)))
