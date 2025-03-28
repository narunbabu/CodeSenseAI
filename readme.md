# CodeSenseAI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**CodeSenseAI** is an intelligent Flask-based web application leveraging Large Language Models (LLMs) to summarize codebases and facilitate automated code modifications through natural language queries.

## Core Features

- **Project Management:** Organizes metadata and storage for multiple code projects.
- **Multi-LLM Integration:** Supports OpenAI, Anthropic, Google AI, Deepseek, and local Ollama via a unified client.
- **Selective Summarization:** Analyze specific files or directories.
- **Automated Summaries:** Provides detailed file-level and overall project summaries using LLMs.
- **Intelligent Querying:** Perform natural language searches within the codebase.
- **Automated Code Modification:**
  - Generates modification instructions based on queries.
  - Provides previews and highlighted diffs before applying changes.
  - Maintains history and supports reverting changes.

## How It Works

1. **Project Setup:** Select a source directory; the app manages data in `./projects/`.
2. **File Selection:** Choose specific files for summarization or modification.
3. **Summarization:** LLMs generate JSON summaries, aggregated into an overall project summary.
4. **Querying:** Submit queries to identify relevant files and get modification instructions.
5. **Modification Workflow:**
   - LLM generates modifications.
   - Preview diffs and apply or revert changes with automated backups.

## Tech Stack

- **Backend:** Flask (Python)
- **Frontend:** HTML (Jinja2), CSS, JavaScript
- **Data Storage:** JSON-based summaries and histories
- **LLM Providers:** OpenAI, Anthropic, Google AI, Deepseek, Ollama

## Installation & Usage

### Clone the Repository
```bash
git clone <repository-url>
cd codesenseai
```

### Virtual Environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configure API Keys
Copy `.env.example` to `.env` and configure your LLM API keys:
```dotenv
OPENAI_API_KEY="sk-..."
ANTHROPIC_API="sk-ant-..."
DEEPSEEK_API="sk-..."
GOOGLE_AI_API="..."
# OLLAMA_HOST="http://localhost:11434"
```

### Run the Application
```bash
python app.py
```
App available at: `http://127.0.0.1:5001`

## Project Structure
```
codesenseai/
├── app.py
├── project_manager.py
├── code_summarizer.py
├── query_handler.py
├── modification_handler.py
├── llm_client.py
├── project_config.py
├── constants.py
├── utils.py
├── templates/
├── static/
├── projects/
│   └── <project_name>/
├── .env
├── requirements.txt
└── README.md
```

## Future Development
- LLM cost estimation
- Project planning automation
- Asynchronous task handling
- Enhanced UI/UX
- Containerization & security improvements
- Expanded language support and model fine-tuning

## Contributing
Pull requests and issues are welcome! Check [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

