# constants.py

# # HTML report template
HTML_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name} - Code Summary</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background-color: #f5f5f5;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
            border-left: 5px solid #2c3e50;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        .summary-box {{
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 3px solid #3498db;
        }}
        .file-entry {{
            margin-bottom: 30px;
            padding: 15px;
            background-color: #fff;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .file-path {{
            font-family: monospace;
            background-color: #f0f0f0;
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        .file-meta {{
            color: #777;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .stats {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-box {{
            flex: 1;
            min-width: 200px;
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }}
        .stat-label {{
            color: #7f8c8d;
            text-transform: uppercase;
            font-size: 0.8em;
        }}
    </style>
</head>
<body>
    <header>
        <h1 id="projectTitle"></h1>
        <p id="projectInfo"></p>
    </header>
    
    <div class="stats">
        <div class="stat-box">
            <div class="stat-value" id="fileCount"></div>
            <div class="stat-label">Files Analyzed</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" id="totalLines"></div>
            <div class="stat-label">Total Lines of Code</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" id="excludedDirsCount"></div>
            <div class="stat-label">Directories Excluded</div>
        </div>
    </div>
    
    <h2>Project Summary</h2>
    <div class="summary-box" id="projectSummary"></div>
    
    <h2>File Summaries</h2>
    <div id="fileSummaries"></div>
    
    <!-- Load marked.js for Markdown parsing -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>
    fetch('code_summary.json')
      .then(response => response.json())
      .then(data => {{
          document.getElementById('projectTitle').innerText = data.project_name + " Code Summary";
          document.getElementById('projectInfo').innerText = "Detailed summary generated using Ollama service";
          document.getElementById('fileCount').innerText = data.file_count;
          document.getElementById('totalLines').innerText = data.total_lines;
          document.getElementById('excludedDirsCount').innerText = data.excluded_dirs.length;
          
          const fileSummariesDiv = document.getElementById('fileSummaries');
          const files = data.files;
          const sortedPaths = Object.keys(files).sort();
          sortedPaths.forEach(path => {{
              const file = files[path];
              const entry = document.createElement('div');
              entry.className = 'file-entry';
              
              const pathElem = document.createElement('h3');
              pathElem.className = 'file-path';
              pathElem.innerText = path;
              
              const metaElem = document.createElement('div');
              metaElem.className = 'file-meta';
              metaElem.innerText = file.lines + " lines | " + Math.round(file.size / 1024) + " KB";
              
              const summaryElem = document.createElement('div');
              summaryElem.className = 'summary-box';
              summaryElem.innerHTML = marked.parse(file.summary);
              
              entry.appendChild(pathElem);
              entry.appendChild(metaElem);
              entry.appendChild(summaryElem);
              fileSummariesDiv.appendChild(entry);
          }});
      }})
      .catch(error => {{
          console.error("Error loading JSON data:", error);
      }});
    </script>
</body>
</html>
"""


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

# HTML template for combined report
HTML_COMBINED_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name} - Code Summary</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background-color: #f5f5f5;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
            border-left: 5px solid #2c3e50;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        .summary-box {{
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 3px solid #3498db;
        }}
        .concise-box {{
            background-color: #f0f7ff;
            border-left: 3px solid #2ecc71;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
        }}
        .file-entry {{
            margin-bottom: 30px;
            padding: 15px;
            background-color: #fff;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .file-path {{
            font-family: monospace;
            background-color: #f0f0f0;
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        .file-meta {{
            color: #777;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .stats {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-box {{
            flex: 1;
            min-width: 200px;
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }}
        .stat-label {{
            color: #7f8c8d;
            text-transform: uppercase;
            font-size: 0.8em;
        }}
        .tabs {{
            display: flex;
            margin-bottom: 15px;
        }}
        .tab {{
            padding: 10px 15px;
            cursor: pointer;
            border: 1px solid #ddd;
            background: #f1f1f1;
            border-radius: 5px 5px 0 0;
            margin-right: 5px;
        }}
        .tab.active {{
            background: #fff;
            border-bottom: 1px solid #fff;
        }}
        .tab-content {{
            display: none;
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 0 5px 5px 5px;
        }}
        .tab-content.active {{
            display: block;
        }}
        #search-input {{
            width: 100%;
            padding: 10px;
            margin-bottom: 20px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        .file-grid {{
            display: grid;
            grid-template-columns: 1fr 3fr;
            gap: 20px;
        }}
        #file-list {{
            list-style: none;
            padding: 0;
            max-height: 500px;
            overflow-y: auto;
            border: 1px solid #eee;
            border-radius: 5px;
        }}
        #file-list li {{
            padding: 8px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
        }}
        #file-list li:hover {{
            background-color: #f5f5f5;
        }}
        @media (max-width: 768px) {{ 
            .file-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>Code Summary: {project_name}</h1>
    </header>
    
    <input type="text" id="search-input" placeholder="Search files...">
    
    <div class="tabs">
        <div class="tab active" onclick="showTab('project')">Project Summary</div>
        <div class="tab" onclick="showTab('files')">File Summaries</div>
    </div>
    
    <div class="stats">
        <div class="stat-box">
            <div class="stat-value" id="fileCount"></div>
            <div class="stat-label">Files Analyzed</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" id="totalLines"></div>
            <div class="stat-label">Total Lines of Code</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" id="excludedFilesCount"></div>
            <div class="stat-label">Files Excluded</div>
        </div>
    </div>
    
    <div id="project" class="tab-content active">
        <div class="summary-box">
            <h2>Project Overview</h2>
            <div id="project-summary-content"></div>
        </div>
    </div>
    
    <div id="files" class="tab-content">
        <div class="file-grid">
            <div>
                <h3>Files</h3>
                <ul id="file-list"></ul>
            </div>
            <div id="file-summary">
                <p>Select a file to view its summary</p>
            </div>
        </div>
    </div>

    <script>
        // Load the JSON data
        fetch('combined_code_summary.json')
            .then(response => response.json())
            .then(data => {{
                // Populate project summary
                document.getElementById('project-summary-content').innerHTML = data.project_summary.replace(/\\n/g, '<br>');
                
                // Populate stats
                document.getElementById('fileCount').innerText = data.file_count;
                document.getElementById('totalLines').innerText = data.total_lines;
                document.getElementById('excludedFilesCount').innerText = data.excluded_files;
                
                // Populate file list
                const fileList = document.getElementById('file-list');
                Object.keys(data.files).sort().forEach(path => {{
                    const li = document.createElement('li');
                    li.textContent = path;
                    li.onclick = function() {{ 
                        showFileSummary(data.files[path], path); 
                    }};
                    fileList.appendChild(li);
                }});
                
                // Set up search functionality
                document.getElementById('search-input').addEventListener('keyup', function() {{
                    const searchTerm = this.value.toLowerCase();
                    Array.from(fileList.children).forEach(item => {{
                        const filePath = item.textContent.toLowerCase();
                        if (filePath.includes(searchTerm)) {{
                            item.style.display = '';
                        }} else {{
                            item.style.display = 'none';
                        }}
                    }});
                }});
            }})
            .catch(error => console.error('Error loading summary data:', error));
        
        function showFileSummary(fileData, path) {{
            const summaryDiv = document.getElementById('file-summary');
            
            let fileSize = fileData.size;
            let sizeUnit = 'bytes';
            if (fileSize > 1024) {{
                fileSize = (fileSize / 1024).toFixed(2);
                sizeUnit = 'KB';
            }}
            if (fileSize > 1024) {{
                fileSize = (fileSize / 1024).toFixed(2);
                sizeUnit = 'MB';
            }}
            
            summaryDiv.innerHTML = `
                <div class="file-path">
                    <h3>${{path}}</h3>
                    <div class="file-meta">${{fileData.lines}} lines | ${{fileSize}} ${{sizeUnit}}</div>
                </div>
                
                <div class="concise-box">
                    <h4>Concise Summary</h4>
                    <p>${{fileData.concise_summary.replace(/\\n/g, '<br>')}}</p>
                </div>
                
                <div class="summary-box">
                    <h4>Detailed Summary</h4>
                    <p>${{fileData.detailed_summary.replace(/\\n/g, '<br>')}}</p>
                </div>
            `;
        }}
        
        function showTab(tabId) {{
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {{
                tab.classList.remove('active');
            }});
            
            // Deactivate all tab buttons
            document.querySelectorAll('.tab').forEach(tabButton => {{
                tabButton.classList.remove('active');
            }});
            
            // Show selected tab
            document.getElementById(tabId).classList.add('active');
            
            // Activate selected tab button
            document.querySelector('.tab[onclick="showTab(\\'' + tabId + '\\')"]').classList.add('active');
        }}
    </script>
</body>
</html>
"""

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



