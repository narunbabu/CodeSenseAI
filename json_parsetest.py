from utils import extract_json
file_path="ra_response_qh.txt"
with open(file_path, "r", encoding="utf-8") as file:
    response = file.read()
# mystr="""[
#   {
#     "project_name": "web-snake-game",
#     "file_path": "index.html",
#     "files": {
#       "index.html": {
#         "path": "index.html",
#         "detailed_summary": "This HTML file serves as the main entry point for the web-based Snake game. It sets up the basic structure of the page, including the game canvas, score display, control buttons (start, pause, reset), and speed control slider. It links to the external CSS file for styling and JavaScript file for game logic. The file uses semantic HTML5 elements for better accessibility and structure, with a responsive layout that should work across different devices.",
#         "concise_summary": "Main HTML file that defines the structure of the Snake game interface, including the game canvas, controls, and score display."
#       },
#       "styles.css": {
#         "path": "styles.css",
#         "detailed_summary": "The CSS file provides styling for the Snake game interface. It implements a clean, modern design with a dark theme that's easy on the eyes during gameplay. The styling includes responsive design elements to ensure the game is playable on various screen sizes. The file organizes styles for the game container, canvas, score display, control buttons, and speed slider. It also includes hover and active states for interactive elements to provide visual feedback to the user.",
#         "concise_summary": "Stylesheet that defines the visual appearance of the Snake game, implementing a responsive design with a dark theme and interactive elements."     
#       },
#       "script.js": {
#         "path": "script.js",
#         "detailed_summary": "This JavaScript file contains all the game logic for the Snake game. It implements the core game mechanics including snake movement, collision detection, food generation, score tracking, and game state management. The code uses the Canvas API for rendering the game. Key features include: dynamic speed adjustment through a slider control, pause/resume functionality, game reset capability, responsive controls that work with both keyboard and on-screen buttons, and proper game loop management using requestAnimationFrame for smooth animation. The code is organized into clear functions with separation of concerns between game logic, rendering, and user input handling.",
#         "concise_summary": "Main JavaScript file that implements the Snake game logic, including movement, collision detection, scoring, and game state management using the Canvas API."
#       },
#       "favicon.ico": {
#         "path": "favicon.ico",
#         "detailed_summary": "A small snake-themed icon file that appears in the browser tab when the game is loaded. This helps with branding and makes the game more recognizable when users have multiple tabs open. The favicon adds a professional touch to the web application.",
#         "concise_summary": "Snake-themed favicon that appears in the browser tab for the game."
#       }
#     },
#     "file_count": 4,
#     "project_summary": "# Web Snake Game\n\n## Purpose and Functionality\nThis project implements a classic Snake game as a web application. Players control a snake that grows longer as it consumes food items, while trying to avoid collisions with walls and itself. The game features score tracking, adjustable speed, and standard game controls (start, pause, reset).\n\n## Key Components\n- **HTML Structure**: Defines the game interface with canvas and controls\n- **CSS Styling**: Provides responsive, visually appealing design\n- **Game Logic**: JavaScript code handling core game mechanics\n- **User Interface**: Control buttons and displays for interacting with the game\n\n## Technologies Used\n- **HTML5**: Semantic markup and Canvas API for game rendering\n- **CSS3**: Modern styling with flexbox for responsive layout\n- **Vanilla JavaScript**: No external libraries, using requestAnimationFrame for game loop\n- **LocalStorage API**: For persisting high scores between sessions\n\n## Core Data Structures\n- **Snake**: Array of coordinates representing snake segments\n- **Food**: Object with x,y coordinates for food position\n- **Game State**: Object tracking current game status (running, paused, game over)\n- **Score**: Integer value updated as food is consumed\n\n## Information Flow\n1. User input (keyboard/buttons) → Game state changes\n2. Game loop updates snake position and checks collisions\n3. Canvas rendering displays current game state\n4. UI updates show score and allow control adjustments\n\n## User Workflows\n- **Starting a game**: Click start button or press Enter key\n- **Controlling the snake**: Arrow keys or on-screen buttons\n- **Pausing/resuming**: Space bar or pause button\n- **Adjusting speed**: Slider control to make gameplay easier or more challenging\n- **Restarting after game over**: Reset button to start a new game\n\n## Areas for Improvement\n- Add mobile touch/swipe controls for better mobile experience\n- Implement different difficulty levels with obstacles\n- Add sound effects and background music\n- Create a multiplayer mode\n- Add power-ups for enhanced gameplay variety\n\n## Implementation Details\n- The game uses requestAnimationFrame for efficient animation\n- Collision detection is optimized to check only the snake's head against other objects\n- The speed control dynamically adjusts the game's difficulty without requiring a restart\n- Responsive design ensures playability across devices with different screen sizes"
#   }
# ]"""
extraction=extract_json(response)

print(extraction)
print(extraction.keys())