# utils.py
import json
from datetime import datetime
import os
import re
from pathlib import Path
def safe_filename(name):
    """Convert a file path into a safe filename by replacing directory separators."""
    return name.replace('/', '_').replace('\\', '_')

def format_time(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
def serialize_data(obj):
    """Recursively convert Path objects to strings."""
    if isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: serialize_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_data(item) for item in obj]
    else:
        return obj


def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(data, path):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(serialize_data(data), f, indent=2)
    except Exception as e:
        print(f"Error saving JSON to {path}: {e}")

def read_file_content(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def write_file_content(file_path, content):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Error writing to {file_path}: {e}")
        return False

def backup_file(file_path, timestamp, backups_dir):
    content = read_file_content(file_path)
    if content is None:
        return False
    backup_filename = f"{os.path.basename(file_path)}_{timestamp.replace(':', '-').replace(' ', '_')}.bak"
    backup_path = os.path.join(backups_dir, backup_filename)
    return write_file_content(backup_path, content)


def extract_json(trimmed_output):
    from bs4 import BeautifulSoup
    import re
    import json
    
    # First, check if we're dealing with HTML content
    if "<" in trimmed_output and ">" in trimmed_output:
        try:
            soup = BeautifulSoup(trimmed_output, 'html.parser')
            
            # Look for code blocks in HTML
            code_blocks = soup.find_all('code')
            if len(code_blocks) > 0:
                # Check if it's JSON
                try:
                    return json.loads(code_blocks[-1].get_text())
                except json.JSONDecodeError:
                    # Check if it's LaTeX
                    latex_text = code_blocks[-1].get_text()
                    if latex_text.strip().startswith('\\') or '\\begin{' in latex_text:
                        return {"latex": latex_text}
                    # If neither JSON nor LaTeX, continue to other parsing methods
            
            # Get the text content from HTML
            response = soup.get_text(separator="\n", strip=True)
        except Exception:
            # If HTML parsing fails, use the original content
            response = trimmed_output
    else:
        response = trimmed_output
    
    # Handle code blocks with backticks (```)
    if response.startswith("```"):
        lines = response.splitlines()
        # Remove the first line if it starts with ``` (and any language hint)
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove the last line if it ends with ```
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        response = "\n".join(lines).strip()
    
    # Try to parse as JSON directly
    try:
        result = json.loads(response)
        return result
    except json.JSONDecodeError:
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Try to find LaTeX in the response
        latex_patterns = [
            r'\\begin\{.*?\}.*?\\end\{.*?\}',  # For environments
            r'\$\$(.*?)\$\$',                  # For display math
            r'\$(.*?)\$'                       # For inline math
        ]
        
        for pattern in latex_patterns:
            latex_match = re.search(pattern, response, re.DOTALL)
            if latex_match:
                return {"latex": latex_match.group()}
    
    # If we couldn't find valid JSON or LaTeX, return the text response
    return {"result": response}
