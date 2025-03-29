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
    import json
    import re
    from bs4 import BeautifulSoup

    # First, if the response is enclosed in triple backticks, remove them
    stripped = trimmed_output.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Remove the first line if it starts with ``` (and optional language hint)
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove the last line if it starts with ```
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    # Try to parse directly as JSON
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # If not valid JSON, and the text looks like HTML, try to process it as HTML.
    if "<" in stripped and ">" in stripped:
        try:
            soup = BeautifulSoup(stripped, 'html.parser')
            # Look for code blocks in HTML
            code_blocks = soup.find_all('code')
            if code_blocks:
                candidate = code_blocks[-1].get_text()
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
            # Fallback: get all text from HTML
            stripped = soup.get_text(separator="\n", strip=True)
        except Exception:
            pass

    # Try again to parse JSON directly
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        # As a last resort, use regex to extract JSON-like content
        json_match = re.search(r'\{.*\}', stripped, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

    # If no valid JSON is found, check for LaTeX patterns
    latex_patterns = [
        r'\\begin\{.*?\}.*?\\end\{.*?\}',
        r'\$\$(.*?)\$\$',
        r'\$(.*?)\$'
    ]
    for pattern in latex_patterns:
        latex_match = re.search(pattern, stripped, re.DOTALL)
        if latex_match:
            return {"latex": latex_match.group()}

    # If all parsing fails, return the raw text wrapped in a dict
    return {"result": stripped}
