# app.py
# Title: Add New Project Creation Feature
# Summary:
# - Added a new route `/create_project` to handle the creation of new, empty projects.
# - Modified the `home` route and template (`home.html`) to include a tab for creating new projects with inputs for name and source path.

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
        # If it's already a datetime object
        if isinstance(value, datetime):
            return value.strftime(format)
        # If it's a string, try to parse it
        elif isinstance(value, str):
            try:
                # Attempt ISO format first
                dt_obj = datetime.fromisoformat(value)
                return dt_obj.strftime(format)
            except ValueError:
                # Fallback to common formats if needed
                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
                    try:
                        dt_obj = datetime.strptime(value, fmt)
                        return dt_obj.strftime(format)
                    except ValueError:
                        continue
                return value # Return original string if parsing fails
        else:
            return 'N/A' # Handle other types or None
    except Exception:
        return 'N/A' # General fallback

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
                        # Ensure essential keys exist before adding
                        if "project_name" in record and "source_code_path" in record:
                             projects_list.append({
                                 "project_name": record.get("project_name", sub.name), # Use record name if available
                                 "source_code_path": record.get("source_code_path", ""),
                                 "local_storage_path": str(sub),
                                 "has_summary": (sub / "combined_code_summary.json").exists() and \
                                                (sub / "combined_code_summary.json").stat().st_size > 50 # Basic check for non-empty summary
                             })
                        else:
                             print(f"Skipping project in {sub}: Missing essential keys in project_record.json")
                    except Exception as e:
                        print(f"Error reading project record for {sub}: {e}")
                        # Optionally add with placeholder data if needed
                        # projects_list.append({
                        #     "project_name": sub.name + " (Error Reading Record)",
                        #     "source_code_path": "N/A",
                        #     "local_storage_path": str(sub),
                        #     "has_summary": False
                        # })

    # Sort projects alphabetically by name
    projects_list.sort(key=lambda p: p.get("project_name", "").lower())

    return render_template("home.html", projects=projects_list, default_local_storage=DEFAULT_LOCAL_STORAGE)


@app.route("/create_project", methods=["POST"])
def create_project():
    init_session()
    project_name = request.form.get("project_name", "").strip()
    source_code_path_str = request.form.get("project_path", "").strip()

    if not project_name or not source_code_path_str:
        flash("Project name and source code path are required.", "error")
        return redirect(url_for("home"))

    source_code_path = Path(source_code_path_str) / project_name
    local_storage_path = Path(DEFAULT_LOCAL_STORAGE) / project_name

    # Basic validation
    if local_storage_path.exists():
        flash(f"A project named '{project_name}' already exists in local storage.", "error")
        return redirect(url_for("home"))
    if source_code_path.exists() and not source_code_path.is_dir():
        flash("The specified source code path exists but is not a directory.", "error")
        return redirect(url_for("home"))
    # Check if source path contains existing files (warn user?) - For now, just create it if needed.

    try:
        # Create the source code directory if it doesn't exist
        source_code_path.mkdir(parents=True, exist_ok=True)
        print(f"Ensured source directory exists: {source_code_path}")

        # Create the local storage directory
        local_storage_path.mkdir(parents=True, exist_ok=True)
        print(f"Created local storage directory: {local_storage_path}")

        # Initialize ProjectManager - this will create the structure and empty files
        pm = ProjectManager(str(source_code_path), str(local_storage_path), is_new=True)
        # pm.create_empty_project_structure() # Logic moved into __init__ and _init_project_record

        # Store project info in session
        project_info = pm.get_project_info()
        # Ensure paths are strings for session serialization
        for key, value in project_info.items():
            if isinstance(value, Path):
                project_info[key] = str(value)

        session['current_source_project'] = project_info
        print(f"New project '{project_name}' created and set in session.")
        flash(f"New empty project '{project_name}' created successfully.", "success")
        return redirect(url_for("project_dashboard"))

    except OSError as e:
        flash(f"Error creating project directories: {e}", "error")
        # Clean up potentially created directories? Maybe not necessary.
        return redirect(url_for("home"))
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "error")
        return redirect(url_for("home"))

@app.route("/select_project", methods=["GET", "POST"])
def select_project():
    print(f"In select project...............{request.method}")
    init_session() # Ensure session is initialized

    if request.method == "GET":
        source_code_path = request.args.get("source_code_path", "")
        local_storage_path = request.args.get("local_storage_path", "") # Expect full path from link

        if not source_code_path or not local_storage_path:
             flash("Missing source code path or local storage path for selection.", "error")
             return redirect(url_for("home"))

        # Validate paths
        if not Path(source_code_path).exists() or not Path(local_storage_path).is_dir():
             flash("Invalid source or local storage path provided.", "error")
             return redirect(url_for("home"))

        # Load existing project
        try:
            pm = ProjectManager(source_code_path, local_storage_path)
            project_info = pm.get_project_info()
            # Ensure paths are strings for session
            for key, value in project_info.items():
                if isinstance(value, Path):
                    project_info[key] = str(value)
            session['current_source_project'] = project_info
            print(f"Selected existing project: {project_info}\n")
            return redirect(url_for("project_dashboard"))
        except Exception as e:
             flash(f"Error loading selected project: {e}", "error")
             return redirect(url_for("home"))

    else: # POST (from the 'Select Project' tab's form)
        source_code_path_str = request.form.get("source_code_path", "").strip()
        local_storage_base = request.form.get("local_storage_path", DEFAULT_LOCAL_STORAGE).strip()

        print(f"POST - source_code_path: {source_code_path_str}\nlocal_storage_base: {local_storage_base}")

        if not source_code_path_str:
            flash("No source code path provided", "error")
            return redirect(url_for("home"))

        source_path = Path(source_code_path_str)
        if not source_path.is_dir():
             flash("Provided source code path is not a valid directory.", "error")
             return redirect(url_for("home"))

        # Determine the full local storage path for the project
        project_name = source_path.name
        project_dir = Path(local_storage_base) / project_name

        # Ensure the local storage directory exists (it should for existing projects, create if not?)
        project_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ProjectManager with the full project directory
        try:
            project_manager = ProjectManager(str(source_path), str(project_dir))
            source_project_info = project_manager.get_project_info()
            # Ensure paths are strings for session
            for key, value in source_project_info.items():
                if isinstance(value, Path):
                    source_project_info[key] = str(value)
            session['current_source_project'] = source_project_info
            print(f"Source project info saved in session: {source_project_info}\n")
            return redirect(url_for("project_dashboard"))
        except Exception as e:
            flash(f"Error initializing project manager: {e}", "error")
            return redirect(url_for("home"))


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
    source_path_obj = Path(source_code_path)
    if not source_path_obj.exists():
        return jsonify({"error": "The provided source code path does not exist"}), 400
    if not source_path_obj.is_dir():
        return jsonify({"error": "The provided source code path is not a directory"}), 400

    files_list = []
    try:
        for root, dirs, files in os.walk(source_code_path):
            # Exclude specified directories
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
            # Filter root path itself if it contains excluded parts (less common, but possible)
            rel_root = os.path.relpath(root, source_code_path)
            if any(part in DEFAULT_EXCLUDES for part in Path(rel_root).parts if part != '.'): # Avoid checking '.' part
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
    except Exception as e:
        print(f"Error walking directory {source_code_path}: {e}")
        return jsonify({"error": f"Error reading directory structure: {e}"}), 500

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
    source_path_obj = Path(source_code_path)
    if not source_path_obj.is_dir():
         flash(f"Source code path '{source_code_path}' is not a valid directory.", "error")
         # Render template with empty tree or redirect? Redirect seems safer.
         return redirect(url_for("project_dashboard"))

    try:
        for root, dirs, files in os.walk(source_code_path):
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
            rel_root = os.path.relpath(root, source_code_path)
            if any(part in DEFAULT_EXCLUDES for part in Path(rel_root).parts if part != '.'):
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
    except Exception as e:
         flash(f"Error reading project files: {e}", "error")
         # Render template with empty tree or redirect?
         file_tree = [] # Show empty tree on error
         return render_template("project_files.html", source_project=current_source_project, file_tree=file_tree)


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
    source_path_obj = Path(current_source_project['source_code_path'])
    if not source_path_obj.is_dir():
         flash("Source code path is not a valid directory.", "error")
         return redirect(url_for("project_dashboard"))

    try:
        for root, dirs, files in os.walk(current_source_project['source_code_path']):
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
            rel_root = os.path.relpath(root, current_source_project['source_code_path'])
            if any(part in DEFAULT_EXCLUDES for part in Path(rel_root).parts if part != '.'):
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
    except Exception as e:
        flash(f"Error reading project files during update: {e}", "error")
        return redirect(url_for("project_dashboard"))

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


@app.route("/project_dashboard", methods=["GET", "POST"])
def project_dashboard():
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))

    try:
        source_code_path = str(current_source_project['source_code_path'])
        local_storage_path = str(current_source_project['local_storage_path'])
        pm = ProjectManager(source_code_path, local_storage_path)
    except Exception as e:
        flash(f"Error initializing project: {e}", "error")
        session.pop('current_source_project', None)
        return redirect(url_for("home"))

    if request.method == "POST":
        # --- Handle Query Submission from Dashboard ---
        input_query = request.form.get("input_query", "").strip()
        client_type = request.form.get("client_type", "openai")

        if not input_query:
            flash("Query cannot be empty.", "warning")
            return redirect(url_for("project_dashboard"))

        if client_type not in clients_mapping:
             flash(f"Invalid client type '{client_type}'. Using default.", "warning")
             client_type = "openai"

        qh = QueryHandler(pm, clients_mapping)
        # mod_handler = ModificationHandler(pm, clients_mapping) # Instantiate ModificationHandler

        try:
            # process_query now returns (query_id, trigger_code_generation)
            query_id, trigger_code_generation = qh.process_query(input_query, client_type)

            if query_id and trigger_code_generation:
                # New project structure defined, redirect to /modify route
                # which will handle prompt preparation and confirmation display
                flash("New project structure defined. Prepare code generation...", "info")
                print(f"Redirecting to modify route for new project query_id: {query_id}")
                # Pass client_type as query parameter for the GET request to /modify
                return redirect(url_for('modify_files', query_id=query_id, client_type=client_type))
            

            elif query_id:
                # Standard query processed, redirect to detail page
                flash("Query processed. Review the details below.", "info")
                return redirect(url_for("query_detail", query_id=query_id))
            else:
                # Query processing failed entirely
                flash("Failed to process query (QueryHandler returned None ID). Check logs.", "error")
                return redirect(url_for("project_dashboard"))

        except Exception as e:
            flash(f"An error occurred while processing the query: {str(e)}", "error")
            print(f"Error processing query/triggering generation: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for debugging
            return redirect(url_for("project_dashboard"))
        # --- End Query Submission Handling ---

    # --- Handle GET Request (remains the same) ---
    summary_status = pm.get_summary_status()
    query_history = pm.load_query_history()
    summary_data = {}
    if pm.combined_json_path.exists():
        summary_data = load_json(str(pm.combined_json_path)) or {}

    return render_template("project_dashboard.html",
                           source_project=current_source_project,
                           summary_status=summary_status,
                           query_history=query_history,
                           summary=summary_data,
                           available_clients=list(clients_mapping.keys()))

        # --- End Query Submission Handling ---


@app.route("/modify/<query_id>", methods=["GET", "POST"])
def modify_files(query_id):
    init_session()
    current_source_project = session.get('current_source_project')
    if not current_source_project:
        flash("No source project selected", "error")
        return redirect(url_for("home"))

    pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])

    # Determine client_type based on method
    if request.method == "POST":
        # Submitted from query_detail page
        client_type = request.form.get("client_type", "openai")
    elif request.method == "GET":
        # Redirected from project_dashboard for new project generation
        client_type = request.args.get("client_type", "openai")
    else:
        # Should not happen, default or error
        client_type = "openai"

    if client_type not in clients_mapping:
        flash(f"Invalid client type '{client_type}'. Using default.", "warning")
        client_type = "openai"

    mod_handler = ModificationHandler(pm, clients_mapping)

    try:
        # Prepare the modification/generation prompt
        temp_id, prompt_display, small_data = mod_handler.prepare_modification_prompt(query_id, client_type)

        if not temp_id or not small_data:
            flash("Failed to prepare modification prompt. Check query response and logs.", "error")
            # Redirect back to query detail if possible, else dashboard
            # We might not have come *from* query_detail if it's a new project generation
            # Let's redirect to dashboard as a safe fallback
            return redirect(url_for("project_dashboard"))
            # Could try redirecting to query_detail, but it might fail if query_id isn't suitable
            # return redirect(url_for("query_detail", query_id=query_id))

        # Store the SMALL data dictionary in the session, keyed by temp_id for potential future use (though usually not needed directly)
        # session[temp_id] = small_data # Optional: Store if needed elsewhere, otherwise just current_temp_id is enough
        # Store the *current* temp_id under a known key for the next step (/process_modifications)
        session['current_temp_id'] = temp_id
        # Store the small_data itself under a known key, as process_modifications needs it
        session['modification_data'] = small_data
        session.modified = True # Mark session as modified

        print(f"Prepared prompt for temp_id: {temp_id}. Stored in session.")
        # print(f"Session modification_data set: {session['modification_data']}") # Debug print

        # Pass necessary data to the confirmation template
        return render_template("confirm_prompt.html",
                               source_project=current_source_project,
                               query_id=query_id,
                               prompt=prompt_display,
                               temp_id=temp_id, # Pass temp_id to template
                               client_type=client_type) # Pass client_type if needed in template
        #upto this working fine. Then it move to generate_modifications
    except Exception as e:
        flash(f"Error preparing modification: {str(e)}", "error")
        print(f"Error in /modify/{query_id} ({request.method}): {e}")
        import traceback; traceback.print_exc() # For debugging
        # Redirect back to query detail or dashboard
        return redirect(url_for("project_dashboard"))

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
             # Allow viewing empty summary for new projects
             summary_data = {"project_name": pm.project_name, "files": {}, "project_summary": "Project is empty or not summarized."}
             # flash("Summary file is empty or invalid JSON.", "warning") # Don't flash warning for empty
             # return redirect(url_for("project_dashboard"))
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

    # Check if source path exists before summarizing
    if not Path(source_code_path).is_dir():
        flash(f"Source code directory '{source_code_path}' not found. Cannot summarize.", "error")
        return redirect(url_for("project_dashboard"))

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

            # If no files are selected OR if the project source path is empty, scan all (which will be none if empty)
            source_is_empty = not any(Path(source_code_path).iterdir())
            if not selected_files or source_is_empty:
                 if source_is_empty:
                      flash("Source directory is empty. Generating empty summary.", "info")
                 elif not selected_files:
                      flash("No files explicitly selected in project settings. Summarizing all detected code files based on extensions/exclusions.", "warning")

                 # scan_project generates file summaries and project summary
                 results = summarizer.scan_project(source_code_path, output_dir=pm.summaries_dir)
            else:
                 flash(f"Summarizing {len(selected_files)} selected files...", "info")
                 # scan_specific_files generates file summaries and project summary for the selection
                 results = summarizer.scan_specific_files(source_code_path, selected_files, output_dir=pm.summaries_dir)

            # Save results from full scan or specific files scan
            # update_modified_summaries saves internally, so only save here for full/specific scans
            if results is not None and not only_modified:
                 # pm.save_results(results) # save_results updated hashes, combined summary, project record
                 # Refactored: scan methods now save individual summaries. Need to combine and update record.
                 pm.combine_summaries(summarizer) # Pass summarizer to generate project summary during combine
                 pm.update_file_hashes() # Update hashes based on current files
                 pm.update_project_record({ # Update record after successful full/specific scan
                     "status": "summarized",
                     "last_summary_end": datetime.now().isoformat(),
                     "summary_client": client_type,
                     "file_count": results.get("file_count", 0), # Update counts from results
                     "total_lines": results.get("total_lines", 0)
                 })
            elif results is None and not only_modified:
                # Handle case where scan_project returned None (e.g., error during scan)
                status_message = "Summarization process failed during scan. Check logs."
                status_category = "error"
                pm.update_project_record({"status": "error"})


        elapsed = time.time() - start_time
        # Final status message based on whether results were generated/updated
        if results is not None: # Covers both modified and full/specific scans that yielded results
            status_message = f"Source code summarization/update completed in {elapsed:.2f} seconds using {client_type}."
            status_category = "success"
            # Project record update for 'summarized' status happens within update_modified_summaries or above for full scan
        elif status_category != "error" and not only_modified: # If full/specific scan yielded no results (and wasn't an error reported above)
            status_message = "Summarization process finished but did not produce results (perhaps no code files found or selected?)."
            status_category = "warning"
            # Don't mark as error if it simply found no files. Maybe 'summarized_empty'?
            pm.update_project_record({"status": "summarized", "file_count": 0, "total_lines": 0})
        elif status_category == "info": # Case where only_modified=True and no files were modified
             pass # Message already set
        # else: # Catch-all if no message set yet (shouldn't happen ideally)
        #      status_message = f"Summarization process finished in {elapsed:.2f} seconds, but outcome unclear."
        #      status_category = "warning"

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

    # MODIFICATION: Allow querying even if no summary exists (for new projects)
    # if not pm.has_summary():
    #     flash("Please summarize the source code first before querying.", "error")
    #     return redirect(url_for("project_dashboard"))

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
    # Template filter handles formatting now

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
            # Redirect to dashboard after delete from detail page? Or query list? Let's go to dashboard.
            return jsonify({"success": True, "redirect": url_for("project_dashboard")}), 200
        # If not AJAX, redirect to dashboard (or query list page if preferred)
        return redirect(url_for("project_dashboard"))
    else:
        flash("Query not found or could not be deleted.", "warning")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Query not found"}), 404
        return redirect(url_for("project_dashboard")) # Stay on dashboard


@app.route("/generate_modifications/<query_id>", methods=["POST"])
def generate_modifications(query_id):
    init_session()
    current_source_project = session.get('current_source_project')
    temp_id = session.get('current_temp_id')  # Get the ID of the current modification process
    print("Here 1")
    if not current_source_project or not temp_id:
        flash("Session data missing or expired. Please start the modification process again.", "error")
        return redirect(url_for("query_detail", query_id=query_id))
    print("Here 2")
    # Retrieve the small session data stored earlier using the fixed key 'modification_data'
    small_session_data = session.get("modification_data")
    if not small_session_data:
        flash(f"Session data missing for modification. Please start again.", "error")
        session.pop('current_temp_id', None)
        session.modified = True
        return redirect(url_for("query_detail", query_id=query_id))
    print("Here 3")
    pm = ProjectManager(current_source_project['source_code_path'],
                        current_source_project['local_storage_path'])
    mod_handler = ModificationHandler(pm, clients_mapping)
    print("Here 4")
    # Process modifications; this calls the LLM and generates a preview (with diffs for both old and new files)
    result = mod_handler.process_modifications(temp_id, small_session_data)
    if result is None or result.get("error"):
        error_msg = result.get("error", "Failed to generate modifications. LLM call or response parsing likely failed.")
        flash(error_msg, "error")
        return redirect(url_for("query_detail", query_id=query_id))
    print("Here 5")
    preview_modifications = result.get("preview")
    if preview_modifications is None:
        flash("Modification generation finished, but no preview data was returned. Check logs.", "warning")
        return redirect(url_for("query_detail", query_id=query_id))
    print("Here 6")
    # Update session small data with LLM details
    small_session_data['llm_response'] = result.get('llm_response', '')
    small_session_data['llm_response_time'] = result.get('llm_response_time', 0)
    session["modification_data"] = small_session_data  # Save back under the same key
    session.modified = True
    print("Here 7")
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
    app.logger.info(f"Accepting modifications for query {query_id}. Temp ID: {temp_id}")
    # print(f"Hare Ram 0 temp_id: {temp_id} current_source_project: {current_source_project}")
    if not current_source_project or not temp_id:
        flash("Session data missing or expired. Please start the modification process again.", "error")
        return redirect(url_for("query_detail", query_id=query_id))
    
    small_session_data = session.get("modification_data")
    print(f"Hare Ram 1 small_session_data: {small_session_data}")
    if not small_session_data:
        flash(f"Session data missing for modification {temp_id}. Please start again.", "error")
        session.pop('current_temp_id', None)
        session.modified = True
        return redirect(url_for("query_detail", query_id=query_id))

    # Instead of retrieving the modifications JSON from the form, load it from the stored file.
    pm = ProjectManager(current_source_project['source_code_path'],
                        current_source_project['local_storage_path'])
    proposed_modifications_dir = pm.output_dir / "proposed_modifications"
    proposed_modifications_file = proposed_modifications_dir / f"{query_id}.json"
    

    if not proposed_modifications_file.exists():
        flash("Proposed modifications file not found. Please generate modifications again.", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    try:
        with open(proposed_modifications_file, "r", encoding="utf-8") as f:
            modifications_to_apply = json.load(f)
    except Exception as e:
        flash(f"Error reading proposed modifications file: {str(e)}", "error")
        return redirect(url_for("query_detail", query_id=query_id))
    print("Hare Ram 2")
    # Validate the modifications structure
    if not isinstance(modifications_to_apply, list):
        flash("Proposed modifications data is not in the expected list format.", "error")
        return redirect(url_for("query_detail", query_id=query_id))

    # Basic validation of list items (can be more robust)
    for idx, m in enumerate(modifications_to_apply):
        if not isinstance(m, dict) or 'file_path' not in m or 'new_code' not in m:
             flash(f"Invalid modification item format at index {idx}. Missing 'file_path' or 'new_code'.", "error")
             return redirect(url_for("query_detail", query_id=query_id))
        if not isinstance(m['file_path'], str) or not m['file_path']:
             flash(f"Modification item at index {idx} has invalid 'file_path'.", "error")
             return redirect(url_for("query_detail", query_id=query_id))
        # Allow empty new_code (e.g., for file deletion if implemented later)
        if not isinstance(m['new_code'], str):
             flash(f"Modification item at index {idx} has invalid 'new_code' (must be a string).", "error")
             return redirect(url_for("query_detail", query_id=query_id))


    mod_handler = ModificationHandler(pm, clients_mapping)
    try:
        modification_result = mod_handler.apply_modifications(temp_id, small_session_data, modifications_to_apply)

        # Clean up session keys and temp files AFTER successful apply or definite failure
        mod_handler.cleanup_temp_file(temp_id) # Clean up temp prompt file
        session.pop(temp_id, None)
        session.pop('current_temp_id', None)
        session.modified = True
        # Delete the proposed modifications JSON file
        try:
            proposed_modifications_file.unlink(missing_ok=True)
        except OSError as e:
            print(f"Warning: Could not delete proposed modifications file {proposed_modifications_file}: {e}")


        if not modification_result or not modification_result.get("success"):
            error_msg = modification_result.get("error", "Failed to apply modifications. Check logs for details.")
            flash(error_msg, "error")
            # Stay on detail page after failure? Or redirect to dashboard? Detail seems better.
            return redirect(url_for("query_detail", query_id=query_id))

        new_modification_id = modification_result.get("id")
        flash(f"Modifications applied successfully (ID: {new_modification_id})! Project summaries may need updating.", "success")
        # Redirect to dashboard after successful application
        return redirect(url_for("project_dashboard"))

    except Exception as e:
         flash(f"An unexpected error occurred while applying modifications: {str(e)}", "error")
         print(f"Error in /accept_modifications/{query_id}: {e}")
         # import traceback; traceback.print_exc() # For debugging
         # Attempt cleanup even on error
         try:
             mod_handler.cleanup_temp_file(temp_id)
             session.pop(temp_id, None)
             session.pop('current_temp_id', None)
             session.modified = True
             proposed_modifications_file.unlink(missing_ok=True)
         except Exception as cleanup_err:
             print(f"Error during cleanup after apply error: {cleanup_err}")
         return redirect(url_for("query_detail", query_id=query_id))


@app.route("/cancel_modification/<query_id>", methods=["GET", "POST"]) # Allow GET if using a link, POST if using form
def cancel_modification(query_id):
    init_session()
    temp_id = session.get('current_temp_id')
    current_source_project = session.get('current_source_project')

    if temp_id and current_source_project:
        try:
            pm = ProjectManager(current_source_project['source_code_path'], current_source_project['local_storage_path'])
            mod_handler = ModificationHandler(pm, clients_mapping)

            # Clean up temp prompt file associated with the session temp_id
            mod_handler.cleanup_temp_file(temp_id)
            print(f"Cleaned up temp prompt file for cancelled modification: {temp_id}")

            # Clean up the proposed modifications JSON file if it exists
            proposed_modifications_dir = pm.output_dir / "proposed_modifications"
            proposed_modifications_file = proposed_modifications_dir / f"{query_id}.json"
            try:
                proposed_modifications_file.unlink(missing_ok=True)
                print(f"Deleted proposed modifications file: {proposed_modifications_file}")
            except OSError as e:
                print(f"Warning: Could not delete proposed modifications file {proposed_modifications_file} during cancel: {e}")

        except Exception as e:
            print(f"Error during modification cleanup for {temp_id}: {e}")
            flash("Error during cleanup, but cancelling process anyway.", "warning")

        # Clean up session keys regardless of file cleanup success
        session.pop(temp_id, None)
        session.pop('current_temp_id', None)
        session.modified = True
        flash("Modification process cancelled.", "info")
    else:
        flash("No active modification process found in session to cancel.", "warning")

    # Redirect back to the query detail page where the modification was initiated
    return redirect(url_for('query_detail', query_id=query_id))

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
        flash(f"Successfully reverted '{file_path}' to its state before modification {modification_id}. Summaries may need updating.", "success")
    else:
        flash(f"Failed to revert '{file_path}'. Backup might be missing or an error occurred.", "error")

    # Redirect back to the detail page of the modification being reverted
    return redirect(url_for("modification_detail", modification_id=modification_id))


# --- Main Execution ---
if __name__ == "__main__":
    # Use environment variables for config, with defaults
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", 5002))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ["true", "1", "yes"]
    print(f" * Starting Flask server on http://{host}:{port}/ (Debug: {debug})")
    app.run(debug=debug, host=host, port=port)
