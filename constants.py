# constants.py


# Prompt for generating both detailed and concise summaries in one call
COMBINED_FILE_PROMPT = """Analyze this code file and provide BOTH a detailed and concise summary.

File path: {file_path}
File type: {file_type}

For the detailed summary, include:
1. The main purpose and functionality of the file
2. Key functions, classes, or components and what they do
3. Important dependencies or imports and their roles
4. Notable design patterns, algorithms, or techniques
5. Any complex logic or non-obvious behavior
6. Error handling approaches
7. Configuration options or customization points
8. How this file integrates with the rest of the codebase

For the concise summary, provide a brief overview that captures:
1. The core purpose of the file in 1-2 sentences
2. The most important functions/classes (only key ones)
3. Critical dependencies or technologies
4. Any particularly notable or unique aspects

Format your response with the detailed summary wrapped in <detailed> tags and the concise summary wrapped in <concise> tags:

<detailed>
[Your detailed summary here]
</detailed>

<concise>
[Your concise summary here]
</concise>

CODE:
```{file_type}
{code}
```"""

# Prompt for summarizing a project
PROJECT_SUMMARY_PROMPT = """Please provide a comprehensive project summary based on the following context:

{code}

Include:
1. The overall purpose and functionality of the project
2. Main components and their relationships
3. Key technologies, frameworks, or libraries used
4. Notable architecture, design patterns, or algorithms
5. Data flow and processing patterns
6. Main entry points and execution paths
7. Integration points with external systems
8. Potential areas for improvement or optimization

Structure your summary to be both informative and actionable for developers who need to understand or modify this codebase."""

# Prompt for generating a project-level summary from aggregated file summaries
AGGREGATED_SUMMARY_PROMPT = """Based on the following file summaries from a codebase, create a comprehensive project overview:

{aggregated}

Your project summary should include:
1. The overall purpose and functionality of the application/system
2. Key components and how they interact
3. Main technologies, frameworks, and design patterns used
4. Core data structures and flow of information
5. Primary user workflows or execution paths
6. Potential areas for improvement or optimization
7. Any notable implementation details, challenges, or unique approaches

This summary should help a developer quickly understand the architecture and design decisions of the project. Keep the summary concise but thorough enough to provide a clear mental model of the codebase."""

NEW_PROJECT_CREATION_PROMPT="""This is a request to create code for a brand new project. The user query is: {input_query}
There are no existing files or summaries.
Generate the necessary file(s) to fulfill the user's request.
Respond ONLY in JSON format, following this structure exactly:
{{"project_name": "given crip and apt project name",
"file_path": "relative/path/to/new_file.ext", 
"files": {{
"new_file.ext": {{
"path": "relative/path/to/new_file.ext",
"detailed_summary": "Detailed summary. This summary should help a developer quickly understand the architecture and design decisions of the project",
"concise_summary": "Purpose of the file and what is its functionality. This will be used to understand the nature of this file for further queries.", 
}},...}},
"file_count": 4, #number of code or non-code files
"project_summary":"Your project summary should include:
1. The overall purpose and functionality of the application/system
2. Key components and how they interact
3. Main technologies, frameworks, and design patterns used
4. Core data structures and flow of information
5. Primary user workflows or execution paths
6. Potential areas for improvement or optimization
7. Any notable implementation details, challenges, or unique approaches"
}}

Ensure the output is valid JSON. Do not include any other text, explanations, or markdown formatting outside the JSON structure. Ensure 'file_path' uses forward slashes '/' and is relative to the project root.

Eg. {{
  "project_name": "arun-chat",
  "files": {{
    "main.py": {{
      "path": "main.py",
      "detailed_summary": "",
      "concise_summary": "",

    }},
    "static\\app.js": {{
      "path": "static\\app.js",
      "detailed_summary": "The `app.js` file serves as the main JavaScript logic ...",
      "concise_summary": "The `app.js` file implements the client-side logic for a chat application,... ",

    }},
    "static\\style.css": {{
      "path": "static\\style.css",
      "detailed_summary": "This CSS file primarily serves to style a chat application, structuring and... ",
      "concise_summary": "This CSS file styles a chat application, defining layout, components, and user... ",

    }},
    "templates\\index.html": {{
      "path": "templates\\index.html",
      "detailed_summary": "The provided HTML code represents the main structure of a web application titled...",
      "concise_summary": "The HTML file serves as the user interface for the \"Coding Chat\" application, ...",

    }}
  }},
  "file_count": 4,
  "project_summary": "## Project Overview: ..."
}}
Your response here:"""

DEFAULT_EXCLUDES = [
    "node_modules", "vendor", "__pycache__", ".github", ".git", "venv", "env", "projects", "notused",
    "dist", "build", ".vscode", ".idea", ".DS_Store", "*.pyc", "*.pyo", "*.md", "yarn.lock","LICENSE",
    "*.pyd", "*.so", "*.dll", "*.exe", "*.egg-info", "*.egg", "package-lock.json", "*.yaml", "dump*",
    "extractFilesContent.js", "__init__.py", ".gitignore", ".gitattributes", ".gitmodules"
]

CODE_EXTENSIONS = [
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss", ".sass",
    ".php", ".rb", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp", ".cs",
    ".swift", ".kt", ".sql", ".xml", ".sh", ".bash", ".ps1", ".dockerfile", ".vue"
]



