// static/js/script.js
// document.addEventListener('DOMContentLoaded', function() {
//     var folderInput = document.getElementById('folderInput');
//     if (folderInput) {
//         folderInput.addEventListener('change', function(event) {
//             if (this.files.length > 0) {
//                 // Use the webkitRelativePath from the first file to get the folder name.
//                 var path = this.files[0].webkitRelativePath;
//                 var folder = path.split("/")[0];
//                 var folderLabel = document.getElementById('folderLabel');
//                 if (folderLabel) {
//                     folderLabel.innerText = "Selected Folder: " + folder;
//                 }
//                 // Updated to target the correct hidden input id
//                 var projectPathInput = document.getElementById('source_code_path');
//                 if (projectPathInput) {
//                     projectPathInput.value = folder;
//                 }
                
//                 // Build and display file tree preview
//                 displayFileTree(Array.from(this.files));
//             }
//         });
//     }
// });
document.addEventListener('DOMContentLoaded', function() {
    var loadBtn = document.getElementById('loadPathBtn');
    if (loadBtn) {
        loadBtn.addEventListener('click', function() {
            var sourceInput = document.getElementById('source_code_input');
            var sourcePathHidden = document.getElementById('source_code_path');
            if (!sourceInput || !sourcePathHidden) return;
            
            var folder = sourceInput.value.trim();
            if (!folder) {
                alert("Please enter a valid source code path");
                return;
            }
            // Set the hidden field value so it gets submitted with the form
            sourcePathHidden.value = folder;
            
            // Make an AJAX call to the server to get the file list for the folder
            fetch('/list_files?source_code_path=' + encodeURIComponent(folder))
                .then(response => response.json())
                .then(files => {
                    if (files.error) {
                        alert(files.error);
                        return;
                    }
                    displayFileTree(files);
                })
                .catch(error => {
                    console.error("Error loading file list:", error);
                    alert("Error loading file list. Check console for details.");
                });
        });
    }
});

function displayFileTree(files) {
    const fileTreeContainer = document.getElementById('fileTreeContainer');
    const fileTreePreview = document.getElementById('fileTreePreview');
    const createProjectBtn = document.getElementById('createProjectBtn');
    const goToDashboardBtn = document.getElementById('goToDashboardBtn');
    
    if (!fileTreeContainer || !fileTreePreview) return;
    
    fileTreePreview.style.display = 'block';
    
    // For a new project, show the Create Project button and hide the Dashboard button
    if (createProjectBtn) createProjectBtn.style.display = 'block';
    if (goToDashboardBtn) goToDashboardBtn.style.display = 'none';
    
    // Build tree structure with strict excluded-folder filtering
    const tree = {};
    const excludedFolders = ['node_modules', '.git', '__pycache__', 'venv', 'env', 'dist', 'build'];
    
    files.forEach(file => {
        // The server returns a property "webkitRelativePath" (the relative path of the file)
        const pathParts = file.webkitRelativePath.split('/');
        let currentLevel = tree;
        let shouldExclude = false;
        
        // Check if any folder in the path is excluded
        for (const part of pathParts.slice(0, -1)) {
            if (excludedFolders.includes(part)) {
                shouldExclude = true;
                break;
            }
        }
        
        if (shouldExclude) return;
        
        pathParts.forEach((part, index) => {
            if (!currentLevel[part]) {
                if (index === pathParts.length - 1) {
                    const ext = part.split('.').pop().toLowerCase();
                    const isCodeFile = ['js', 'py', 'html', 'css', 'java', 'cpp', 'c', 'h', 'php', 'ts', 'jsx', 'tsx'].includes(ext);
                    
                    currentLevel[part] = {
                        type: 'file',
                        name: part,
                        path: file.webkitRelativePath,
                        isCode: isCodeFile
                    };
                } else {
                    currentLevel[part] = {
                        type: 'folder',
                        name: part,
                        children: {}
                    };
                }
            }
            
            if (index < pathParts.length - 1) {
                currentLevel = currentLevel[part].children;
            }
        });
    });
    
    fileTreeContainer.innerHTML = generateTreeHTML(tree);
    
    // Auto-select all code files by default
    document.querySelectorAll('input[data-type="file"]').forEach(checkbox => {
        if (checkbox.parentElement.querySelector('.code-file')) {
            checkbox.checked = true;
        }
    });
}

function generateTreeHTML(tree) {
    let html = '<ul class="file-tree">';
    
    // Sort entries: folders first, then files (alphabetically)
    const entries = Object.entries(tree).sort((a, b) => {
        if (a[1].type !== b[1].type) {
            return a[1].type === 'folder' ? -1 : 1;
        }
        return a[0].localeCompare(b[0]);
    });
    
    for (const [name, item] of entries) {
        if (item.type === 'folder') {
            const isExcluded = ['node_modules', '.git', '.idea', '__pycache__', 'venv', 'env'].includes(name);
            const checked = isExcluded ? '' : 'checked';
            
            html += '<li>';
            html += '<label>';
            html += `<input type="checkbox" data-type="folder" data-path="${name}" ${checked}>`;
            html += `<span class="folder-name">${name}/</span>`;
            html += '</label>';
            html += generateTreeHTML(item.children);
            html += '</li>';
        } else {
            const ext = name.split('.').pop().toLowerCase();
            const isCodeFile = ['js', 'py', 'html', 'css', 'java', 'cpp', 'c', 'h', 'php', 'ts', 'jsx', 'tsx'].includes(ext);
            const checked = isCodeFile ? 'checked' : '';
            
            html += '<li>';
            html += '<label>';
            html += `<input type="checkbox" name="selected_files" data-type="file" data-path="${item.path}" ${checked}>`;
            html += `<span class="file-name ${isCodeFile ? 'code-file' : ''}">${name}</span>`;
            html += '</label>';
            html += '</li>';
        }
    }
    
    html += '</ul>';
    return html;
}



document.addEventListener('DOMContentLoaded', function() {
    var loadBtn = document.getElementById('loadPathBtn');
    if (loadBtn) {
        loadBtn.addEventListener('click', function() {
            var sourceInput = document.getElementById('source_code_input');
            var sourcePathHidden = document.getElementById('source_code_path');
            if (!sourceInput || !sourcePathHidden) return;
            
            var folder = sourceInput.value.trim();
            if (!folder) {
                alert("Please enter a valid source code path");
                return;
            }
            // Set the hidden field value so it gets submitted with the form
            sourcePathHidden.value = folder;
            
            // Make an AJAX call to the server to get the file list for the folder
            fetch('/list_files?source_code_path=' + encodeURIComponent(folder))
                .then(response => response.json())
                .then(files => {
                    if (files.error) {
                        alert(files.error);
                        return;
                    }
                    displayFileTree(files);
                })
                .catch(error => {
                    console.error("Error loading file list:", error);
                    alert("Error loading file list. Check console for details.");
                });
        });
    }
});

function displayFileTree(files) {
    const fileTreeContainer = document.getElementById('fileTreeContainer');
    const fileTreePreview = document.getElementById('fileTreePreview');
    const createProjectBtn = document.getElementById('createProjectBtn');
    const goToDashboardBtn = document.getElementById('goToDashboardBtn');
    
    if (!fileTreeContainer || !fileTreePreview) return;
    
    fileTreePreview.style.display = 'block';
    
    // For a new project, show the Create Project button and hide the Dashboard button
    if (createProjectBtn) createProjectBtn.style.display = 'block';
    if (goToDashboardBtn) goToDashboardBtn.style.display = 'none';
    
    // Build tree structure with strict excluded-folder filtering
    const tree = {};
    const excludedFolders = ['node_modules', '.git', '__pycache__', 'venv', 'env', 'dist', 'build'];
    
    files.forEach(file => {
        // The server returns a property "webkitRelativePath" (the relative path of the file)
        const pathParts = file.webkitRelativePath.split('/');
        let currentLevel = tree;
        let shouldExclude = false;
        
        // Check if any folder in the path is excluded
        for (const part of pathParts.slice(0, -1)) {
            if (excludedFolders.includes(part)) {
                shouldExclude = true;
                break;
            }
        }
        
        if (shouldExclude) return;
        
        pathParts.forEach((part, index) => {
            if (!currentLevel[part]) {
                if (index === pathParts.length - 1) {
                    const ext = part.split('.').pop().toLowerCase();
                    const isCodeFile = ['js', 'py', 'html', 'css', 'java', 'cpp', 'c', 'h', 'php', 'ts', 'jsx', 'tsx'].includes(ext);
                    
                    currentLevel[part] = {
                        type: 'file',
                        name: part,
                        path: file.webkitRelativePath,
                        isCode: isCodeFile
                    };
                } else {
                    currentLevel[part] = {
                        type: 'folder',
                        name: part,
                        children: {}
                    };
                }
            }
            
            if (index < pathParts.length - 1) {
                currentLevel = currentLevel[part].children;
            }
        });
    });
    
    fileTreeContainer.innerHTML = generateTreeHTML(tree);
    
    // Auto-select all code files by default
    document.querySelectorAll('input[data-type="file"]').forEach(checkbox => {
        if (checkbox.parentElement.querySelector('.code-file')) {
            checkbox.checked = true;
        }
    });
}

function generateTreeHTML(tree) {
    let html = '<ul class="file-tree">';
    
    // Sort entries: folders first, then files (alphabetically)
    const entries = Object.entries(tree).sort((a, b) => {
        if (a[1].type !== b[1].type) {
            return a[1].type === 'folder' ? -1 : 1;
        }
        return a[0].localeCompare(b[0]);
    });
    
    for (const [name, item] of entries) {
        if (item.type === 'folder') {
            const isExcluded = ['node_modules', '.git', '.idea', '__pycache__', 'venv', 'env'].includes(name);
            const checked = isExcluded ? '' : 'checked';
            
            html += '<li>';
            html += '<label>';
            html += `<input type="checkbox" data-type="folder" data-path="${name}" ${checked}>`;
            html += `<span class="folder-name">${name}/</span>`;
            html += '</label>';
            html += generateTreeHTML(item.children);
            html += '</li>';
        } else {
            const ext = name.split('.').pop().toLowerCase();
            const isCodeFile = ['js', 'py', 'html', 'css', 'java', 'cpp', 'c', 'h', 'php', 'ts', 'jsx', 'tsx'].includes(ext);
            const checked = isCodeFile ? 'checked' : '';
            
            html += '<li>';
            html += '<label>';
            html += `<input type="checkbox" name="selected_files" data-type="file" data-path="${item.path}" ${checked}>`;
            html += `<span class="file-name ${isCodeFile ? 'code-file' : ''}">${name}</span>`;
            html += '</label>';
            html += '</li>';
        }
    }
    
    html += '</ul>';
    return html;
}

