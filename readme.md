# Code Summarizer & Modifier

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Example Badge -->
<!-- Add other badges: CI/CD status, Code Coverage, etc. -->

An intelligent Flask web application that uses Large Language Models (LLMs) to summarize codebases and assist with automated code modifications based on user queries.

## Core Features

*   **Project Management:** Manages metadata and storage for multiple code projects.
*   **Multi-LLM Support:** Integrates with various LLM providers (OpenAI, Anthropic, Google, Deepseek, local Ollama) via a unified client.
*   **Selective Summarization:** Allows users to select specific files or directories for analysis.
*   **Code Summarization:** Generates detailed and concise summaries for individual code files and an overall project summary using LLMs.
*   **Change Detection:** Tracks file modifications using content hashing to identify when summaries need updating.
*   **Intelligent Querying:** Allows users to query the codebase using natural language, leveraging the generated summaries to identify relevant files.
*   **LLM-Powered Modification:**
    *   Generates modification instructions based on user queries and code context.
    *   Uses LLMs to generate the modified code.
    *   Provides a preview with highlighted diffs before applying changes.
    *   Applies changes with automatic backups.
*   **History Tracking:** Records query history and applied modifications.
*   **Revert Functionality:** Allows reverting individual files modified in a specific change set.

## How it Works

1.  **Project Setup:** Select a source code directory. The app creates a corresponding storage directory under `./projects/` to hold summaries, history, backups, etc.
2.  **File Selection:** Users can review the file tree and select which code files should be included in the analysis and potential modifications.
3.  **Summarization:** The application scans the selected code files.
    *   For each file, it sends the content to the chosen LLM to generate detailed and concise summaries, saving each as a separate JSON file (`summaries/*.json`).
    *   It then combines these individual summaries into a single `combined_code_summary.json`.
    *   Finally, it generates an overall project summary based on the individual file summaries using the LLM.
    *   File hashes are stored (`file_hashes.json`) to detect changes later.
4.  **Querying:** Users submit natural language queries (e.g., "Add error handling to the login function").
    *   The query, project summary, and concise file summaries are sent to an LLM.
    *   The LLM identifies relevant files and generates specific modification instructions in a JSON format.
5.  **Modification:**
    *   The user initiates a modification based on a query result.
    *   A detailed prompt containing the original code and modification instructions is prepared.
    *   The prompt is sent to an LLM, which generates the modified code for the relevant files.
    *   The application parses the LLM response and presents a preview showing the original code, the proposed new code, and a highlighted diff.
    *   The user can review the changes and choose to accept or cancel.
    *   If accepted, the application backs up the original files and writes the new code. The modification event is logged.
    *   Users can later view modification history and revert specific file changes.

## Technical Stack

*   **Backend:** Python, Flask
*   **LLM Integration:** OpenAI, Anthropic, Google AI, Deepseek APIs, Ollama (via requests)
*   **Frontend:** HTML (Jinja2 Templates), CSS, JavaScript (basic interactions)
*   **Data Storage:** JSON files for summaries, history, hashes, and project records.

## Setup & Running

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd code_summarizer
    ```
2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # On Windows:
    # venv\\Scripts\\activate
    # On macOS/Linux:
    # source venv/bin/activate
    ```
3.  **Install dependencies:**
    *(Note: Ensure you have a `requirements.txt` file)*
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure API Keys:**
    *   Copy or rename `.env.example` to `.env`.
    *   Alternatively, create a `.env` file in the project root or `C:/ArunApps/.env`.
    *   Add your API keys for the desired LLM services:
        ```dotenv
        OPENAI_API_KEY="sk-..."
        ANTHROPIC_API="sk-ant-..."
        DEEPSEEK_API="sk-..."
        GOOGLE_AI_API="..."
        # OLLAMA_HOST="http://localhost:11434" # If not default
        ```
5.  **Run the Flask application:**
    ```bash
    python app.py
    ```
    The application will typically be available at `http://127.0.0.1:5001`.

## Project Structure

```
code_summarizer/
├── app.py                  # Main Flask application
├── project_manager.py      # Handles project data, summaries, history
├── code_summarizer.py      # Handles scanning and summarizing code
├── query_handler.py        # Handles processing user queries against summaries
├── modification_handler.py # Handles the code modification workflow
├── llm_client.py           # Unified client for various LLM APIs
├── project_config.py       # Loads config and initializes LLM clients
├── constants.py            # Prompts, default excludes, extensions
├── utils.py                # Helper functions (JSON I/O, path handling, etc.)
├── templates/              # HTML templates (Jinja2)
│   ├── base.html
│   ├── home.html
│   ├── project_dashboard.html
│   ├── query.html
│   ├── query_detail.html
│   ├── confirm_prompt.html
│   ├── preview_modification.html
│   └── ...
├── static/                 # CSS, JavaScript, images
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── ...
├── projects/               # Default storage location for project data
│   └── <project_name>/
│       ├── project_record.json
│       ├── combined_code_summary.json
│       ├── file_hashes.json
│       ├── query_history.json
│       ├── modifications_history.json
│       ├── summaries/        # Individual file summaries
│       │   └── file1_py.json
│       │   └── ...
│       ├── backups/          # Backups of modified files
│       ├── temp_mods/        # Temporary data for ongoing modifications
│       └── proposed_modifications/ # Generated code changes awaiting acceptance
├── .env                    # API keys and environment variables (ignored by git)
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Future Improvements Pipeline

*   **LLM Cost Estimation:** Before sending requests to paid LLM APIs (OpenAI, Anthropic, Google, Deepseek), estimate the token count and provide an approximate cost based on the selected model's pricing.
*   **Project Planning Phase:** Add a feature where users can define a high-level goal for a new project, and an LLM generates a potential project structure, file breakdown, and initial task list.
*   **Plan Review & Refinement:** Allow users to review the LLM-generated project plan, make edits, and approve it before potentially using it to bootstrap the project or guide further modifications.
*   **Asynchronous Operations:** Use task queues (like Celery with Redis/RabbitMQ) for long-running operations (summarization, LLM calls) to prevent blocking the web server and provide a better user experience (e.g., progress indicators).
*   **Enhanced UI/UX:**
    *   Implement more JavaScript for dynamic updates (e.g., loading states, AJAX for history loading).
    *   Improve the diff viewer (e.g., side-by-side diffs, syntax highlighting within diffs).
    *   Better visual feedback during processing.
*   **More Robust Error Handling:** Implement more specific error catching and user-friendly feedback throughout the application. Centralized logging.
*   **Testing:** Add comprehensive unit and integration tests (mocking LLM calls and file system interactions where appropriate).
*   **Containerization:** Provide Dockerfile and docker-compose configurations for easier deployment.
*   **Security Hardening:** Rigorous input validation, dependency security scanning, ensure no path traversal vulnerabilities (especially with file operations).
*   **Expanded Language/Framework Support:** Improve prompts and parsing to better handle a wider variety of programming languages and frameworks.
*   **Model Fine-tuning:** Explore fine-tuning smaller/open-source models specifically for code summarization or modification tasks for potentially better performance or cost-efficiency.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.
<!-- Add more specific contribution guidelines if desired -->

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. <!-- Make sure to add a LICENSE file -->

