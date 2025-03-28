**Documentation Points (GitHub Wiki / Docs Section)**

Here are key areas to document in more detail, potentially on a GitHub Wiki or in separate Markdown files within a `docs/` directory:

1.  **Overview:**
    *   Project goal: Leverage LLMs for code understanding and modification.
    *   Target audience: Developers looking to quickly understand or refactor codebases.

2.  **Architecture:**
    *   **Flask Application (`app.py`):** Core request handling, routing, session management, orchestrates calls to handlers.
    *   **`ProjectManager`:** Central class for managing all persistent data related to a specific project (metadata, summaries, hashes, history, backups). Explains the file structure within a project's directory (`projects/<project_name>/`).
    *   **`CodeSummarizer`:** Responsible for walking the filesystem, filtering files, reading content, interacting with LLMs via `LLM_Client` for summarization tasks, and saving individual summaries.
    *   **`QueryHandler`:** Takes user input and context (summaries), formats prompts for the LLM to identify relevant files and generate modification instructions, saves query results.
    *   **`ModificationHandler`:** Manages the multi-step code modification workflow: prompt preparation, temporary data storage (`temp_mods/`), LLM interaction for code generation, response parsing, diff generation, applying changes (including backups), reverting changes, and cleaning up temporary data. Highlights the use of `proposed_modifications/` for staging changes.
    *   **`LLM_Client`:** Abstraction layer for interacting with different LLM APIs. Handles authentication and API-specific request/response formats.
    *   **`project_config.py`:** Configuration loading (`.env`), initialization of `LLM_Client` instances.
    *   **Data Flow:** Diagrams or descriptions for key workflows (Summarization, Querying, Modification).

3.  **Key Workflows (Detailed):**
    *   **Project Setup & File Selection:** How `ProjectManager` initializes, how the file tree is built (`build_file_tree`), how selections are saved and used (`update_file_selection`, `get_modified_files`).
    *   **Summarization Process:**
        *   Full Scan vs. Update (`summarize_project` route logic).
        *   Role of `CodeSummarizer.scan_project`/`scan_specific_files`.
        *   Saving individual summaries (`summaries/`).
        *   Combining summaries (`ProjectManager.combine_summaries`).
        *   Generating the final project-level summary (`AGGREGATED_SUMMARY_PROMPT`).
        *   Hash checking (`get_modified_files`) and triggering updates.
    *   **Querying:** Prompt construction, LLM interaction, expected JSON output format from the LLM, saving to `query_history.json`.
    *   **Code Modification:**
        *   Step 1: `modify_files` route -> `ModificationHandler.prepare_modification_prompt` (creates prompt, saves large data to `temp_mods/`, returns `temp_id`).
        *   Step 2: `confirm_prompt.html` displays prompt, user confirms.
        *   Step 3: `generate_modifications` route -> `ModificationHandler.process_modifications` (reads temp data, calls LLM, parses response, generates diffs, *saves proposed changes to `proposed_modifications/<query_id>.json`*).
        *   Step 4: `preview_modification.html` displays diffs by loading data associated with the active file button.
        *   Step 5: `accept_modifications` route -> *Loads modifications from `proposed_modifications/<query_id>.json`* -> `ModificationHandler.apply_modifications` (backs up files, writes changes, saves history, cleans up `temp_mods/` file).
        *   Step 6 (Optional): `cancel_modification` route -> `ModificationHandler.cleanup_temp_file`.
        *   Reverting: `revert_file` route -> `ModificationHandler.revert_file` (finds backup based on modification ID timestamp, restores file).

4.  **Configuration:**
    *   Detailed explanation of the `.env` file and all required/optional environment variables (API keys, Ollama host).
    *   How `project_config.py` uses these variables to set up `LLM_Client` instances.

5.  **API Integration (`LLM_Client`):**
    *   How to add support for a new LLM service.
    *   Details on the models used/tested (`project_config.py`).

6.  **Data Storage:**
    *   Detailed description of each JSON file's purpose and schema (`project_record.json`, `combined_code_summary.json`, `file_hashes.json`, `query_history.json`, `modifications_history.json`).
    *   Explanation of the directories (`summaries/`, `backups/`, `temp_mods/`, `proposed_modifications/`).

7.  **Frontend:**
    *   Overview of key templates and their roles.
    *   Brief description of CSS structure (`style.css`, variables).
    *   Mention any significant JavaScript interactions (file tree, preview page file switching - *if applicable*).

8.  **Extensibility & Future Development:**
    *   Elaborate on the "Future Improvements" listed in the README.
    *   Provide guidance on where in the codebase developers might start to implement these features.

9.  **Troubleshooting:**
    *   Common errors (API key issues, dependency conflicts, file not found errors).
    *   Debugging tips (checking Flask logs, examining saved JSON files).

