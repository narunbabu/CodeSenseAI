// static/js/script.js

// DOMContentLoaded listener to set up initial state and event listeners
document.addEventListener('DOMContentLoaded', function() {

    // --- Tab Switching Logic ---
    const tabLinks = document.querySelectorAll('.tab-link');
    const tabContents = document.querySelectorAll('.tab-content');

    // Function to open a specific tab
    window.openTab = function(evt, tabName) {
        // Hide all tab contents
        tabContents.forEach(content => {
            content.style.display = "none";
            content.classList.remove("active");
        });

        // Remove 'active' class from all tab links
        tabLinks.forEach(link => {
            link.classList.remove("active");
        });

        // Show the current tab and add 'active' class to the content and link
        const currentTab = document.getElementById(tabName);
        if (currentTab) {
            currentTab.style.display = "block";
            currentTab.classList.add("active");
        }
        if (evt && evt.currentTarget) {
            evt.currentTarget.classList.add("active");
        }
    }

    // Add click event listeners to tab links
    tabLinks.forEach(link => {
        link.addEventListener('click', (event) => {
            // Find the target tab name from the button's onclick attribute (a bit hacky but works)
            const onclickAttr = event.currentTarget.getAttribute('onclick');
            const tabNameMatch = onclickAttr.match(/openTab\(event, '(.*?)'\)/);
            if (tabNameMatch && tabNameMatch[1]) {
                openTab(event, tabNameMatch[1]);
            }
        });
    });

    // Activate the default active tab on page load (if needed, CSS handles initial state)
    // const initialActiveTab = document.querySelector('.tab-link.active');
    // if (initialActiveTab) {
    //     const onclickAttr = initialActiveTab.getAttribute('onclick');
    //     const tabNameMatch = onclickAttr.match(/openTab\(event, '(.*?)'\)/);
    //      if (tabNameMatch && tabNameMatch[1]) {
    //         document.getElementById(tabNameMatch[1]).style.display = 'block';
    //      }
    // }


    // --- File Preview Logic (for Select Project Tab) ---
    const loadPathBtn = document.getElementById('loadPathBtn');
    if (loadPathBtn) {
        loadPathBtn.addEventListener('click', function() {
            const sourceCodeInput = document.getElementById('source_code_input'); // The display input
            const sourceCodePathHidden = document.getElementById('source_code_path'); // The hidden input for submission
            const fileTreePreviewDiv = document.getElementById('fileTreePreview');
            const fileTreeContainer = document.getElementById('fileTreeContainer');
            const selectProjectBtn = document.getElementById('createProjectBtn'); // Button in the "Select Project" tab

            if (!sourceCodeInput || !sourceCodePathHidden || !fileTreePreviewDiv || !fileTreeContainer || !selectProjectBtn) {
                console.error("One or more elements for file preview not found.");
                return;
            }

            const sourcePath = sourceCodeInput.value.trim();
            if (!sourcePath) {
                alert("Please enter a source code path.");
                return;
            }
            // Set the hidden field value for form submission.
            sourceCodePathHidden.value = sourcePath;

            // Show preview area and loading state
            fileTreePreviewDiv.style.display = 'block';
            fileTreeContainer.innerHTML = "<p><em>Loading file list...</em></p>";
            selectProjectBtn.style.display = 'none'; // Hide button until loaded

            // Fetch the list of files using the /list_files endpoint.
            fetch('/list_files?source_code_path=' + encodeURIComponent(sourcePath))
                .then(response => {
                    if (!response.ok) {
                        // Try to parse error json, otherwise use status text
                        return response.json().then(err => { throw new Error(err.error || `Server error: ${response.statusText}`); })
                                             .catch(() => { throw new Error(`Server error: ${response.statusText}`); });
                    }
                    return response.json();
                })
                .then(data => {
                    fileTreeContainer.innerHTML = ""; // Clear loading message
                    if (data.error) { // Should be caught by !response.ok now, but double check
                        fileTreeContainer.innerHTML = "<p class='text-danger'>Error: " + data.error + "</p>";
                    } else if (data.length === 0) {
                        fileTreeContainer.innerHTML = "<p>No processable code files found in this directory.</p>";
                        selectProjectBtn.style.display = 'block'; // Show button even if empty
                    } else {
                        // Build a simple file tree list (could be enhanced later)
                        let fileListHtml = '<ul style="list-style-type: none; padding-left: 0;">';
                        data.forEach(function(file) {
                            // Basic filtering display for common non-code files if needed, though server filters extensions
                            // const isLikelyCode = /\.(js|py|html|css|java|cpp|c|h|php|ts|jsx|tsx)$/i.test(file.name);
                            fileListHtml += `<li style="font-family: monospace; font-size: 0.9em; margin-bottom: 2px;">${escapeHtml(file.webkitRelativePath)}</li>`;
                        });
                        fileListHtml += '</ul>';
                        fileTreeContainer.innerHTML = fileListHtml;
                        selectProjectBtn.style.display = 'block'; // Show button
                    }
                })
                .catch(error => {
                    console.error("Error loading file tree:", error);
                    fileTreeContainer.innerHTML = "<p class='text-danger'>Error loading file tree: " + error.message + "</p>";
                    selectProjectBtn.style.display = 'none'; // Keep button hidden on error
                });
        });
    }


    // --- Validation Logic (for Create New Project Tab) ---
    const createProjectForm = document.getElementById('createProjectForm');
    if (createProjectForm) {
        createProjectForm.addEventListener('submit', function(event) {
            const nameInput = document.getElementById('project_name');
            const pathInput = document.getElementById('project_path');
            let isValid = true;
            let errors = [];

            // Validate Project Name
            const projectName = nameInput.value.trim();
            if (!projectName) {
                errors.push('Project Name cannot be empty.');
                isValid = false;
            } else if (!/^[a-zA-Z0-9._-]+$/.test(projectName)) {
                 // Allow dots, underscores, hyphens along with alphanumerics
                errors.push('Project Name can only contain letters, numbers, dots (.), underscores (_), and hyphens (-).');
                isValid = false;
            } else if (projectName.length > 100) { // Optional: Max length
                 errors.push('Project Name is too long (max 100 characters).');
                 isValid = false;
             }

            // Validate Source Code Path
            const projectPath = pathInput.value.trim();
            if (!projectPath) {
                errors.push('Source Code Path cannot be empty.');
                isValid = false;
            }
            // Basic check for absolute path (starts with / or drive letter C:\ etc.) - OS dependent!
            // This check is rudimentary. Server-side validation is more reliable.
            else if (!projectPath.startsWith('/') && !/^[a-zA-Z]:[\\/]/.test(projectPath)) {
                 errors.push('Please provide an absolute path for the Source Code Path (e.g., /path/to/project or C:\\path\\to\\project).');
                 isValid = false;
             }

            if (!isValid) {
                event.preventDefault(); // Stop form submission
                alert("Please fix the following errors:\n- " + errors.join("\n- "));
                // Focus the first invalid field
                if (errors[0].includes('Name')) nameInput.focus();
                else pathInput.focus();
            }
            // If valid, the form will submit normally to /create_project
        });
    }

    // --- Flash Message Dismissal ---
    setTimeout(function() {
        let flashMessages = document.getElementById('flash-messages');
        if (flashMessages) {
            // Add fade-out effect
            flashMessages.style.transition = 'opacity 0.5s ease-out';
            flashMessages.style.opacity = '0';
            // Remove from DOM after fade out
            setTimeout(() => {
                 if (flashMessages.parentNode) {
                     flashMessages.parentNode.removeChild(flashMessages);
                 }
             }, 500); // Match transition duration
        }
    }, 5000); // Start fade out after 5 seconds

}); // End DOMContentLoaded

// --- Helper Functions ---
function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return unsafe
         .toString()
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}


// --- Optional: File Tree Interaction (for project_files.html page) ---
// This part belongs on the project_files.html template's script block or a separate JS file loaded there.
// Example of handling checkbox clicks for hierarchical selection (if needed):
/*
document.addEventListener('DOMContentLoaded', function() {
    const fileTree = document.querySelector('.file-tree'); // Assuming the tree container has this class

    if (fileTree) {
        fileTree.addEventListener('change', function(event) {
            const target = event.target;
            if (target.matches('input[type="checkbox"]')) {
                const isChecked = target.checked;
                const listItem = target.closest('li');

                // If it's a folder checkbox, check/uncheck all children
                if (target.dataset.type === 'folder' && listItem) {
                    const childCheckboxes = listItem.querySelectorAll('input[type="checkbox"]');
                    childCheckboxes.forEach(cb => {
                        if (cb !== target) { // Don't re-trigger on the same checkbox
                            cb.checked = isChecked;
                        }
                    });
                }
                // Optional: If a file is unchecked, uncheck parent folders? (Can be complex)
                // else if (target.dataset.type === 'file' && !isChecked) {
                //     let parentLi = listItem.parentElement.closest('li');
                //     while(parentLi) {
                //         const folderCheckbox = parentLi.querySelector(':scope > label > input[data-type="folder"]');
                //         if(folderCheckbox) folderCheckbox.checked = false;
                //         parentLi = parentLi.parentElement.closest('li');
                //     }
                // }
                 // Optional: If a file is checked, ensure parent folders are checked?
                 // else if (target.dataset.type === 'file' && isChecked) {
                 //    // Similar logic walking up the tree
                 // }
            }
        });
    }
});
*/
