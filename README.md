GRIS - 3D Editor Inspired by INTERLOPER Series

This project was created out of pure passion for the INTERLOPER series by Anomidae. I couldn't find any recreation that aimed to introduce as many features as possible to make it feel like a real editor, so I built this one. GRIS is a 3D scene editor with AI entities, custom dialogs, and retro-styled GUI elements, built using PyQt5 and OpenGL.

This is the latest version. There's also an older version in the "oldver" folder ("PRE-COMPILE"), which was made before some small edits for compiling the project. I'm not sure if there's anything significantly different there, but I've included it anyway.

I hope you enjoy the project! I wanted to leave a small mark on my favorite community. All credit goes to Anomidae for the INTERLOPER series and Pumodi for the great music—these belong to those wonderful creators.

## Asset Usage Disclaimer
The textures located in the materials folder, excluding those specifically for the floor and GUI (which were created by the project author), are not owned or authored by the maintainer of this project. These assets may include materials derived from games developed by Valve Corporation and are provided solely for testing and demonstration purposes within this non-commercial, open-source tool.
Users are advised to replace these textures with their own legally obtained assets to ensure compliance with applicable copyright laws. The project author disclaims any liability for potential copyright issues arising from the use of these materials and recommends reviewing Valve's guidelines on asset usage for fan projects and mods, as outlined in the Valve Developer Community. This project respects intellectual property rights and encourages responsible usage.

## Features
- 3D scene editing with objects like cubes, cones, brushes, and models.
- AI behaviors for entities (e.g., wandering, capturing).
- Custom file dialogs and settings dialogs.
- Drawing canvas for textures or outlines.
- Support for loading OBJ models and MTL materials.
- Retro 3D-bordered GUI style.
- Background music and sound effects.
- Discord Rich Presence integration.
- And more—explore the code or run the app to see!

## Prerequisites
- **Python**: Version 3.8 or higher (tested on 3.8.0 and 3.12, with compatibility expected across intermediate versions).
- **Operating System**: Windows, macOS, or Linux (though primarily developed on Windows; cross-platform compatibility via PyQt5).
- **Dependencies**: The project requires a few Python libraries. See `requirements.txt` for details.
- **Hardware**: A graphics card supporting OpenGL 3.3+ for the 3D rendering. Basic CPU/GPU should suffice for simple scenes.
- **Optional**: Fonts in the `fonts` folder (e.g., "Forum" font for GUI). If missing, the app will use system defaults.
- **Optional**: Sounds and materials in the `sound` and `materials` folders. The app creates these if missing, but you can add your own WAV/MP3/OGG files for custom audio.

With all that being said I also feel the need to say that I did used some of AI assistance while writing this code, again, not professional

Note: The project used AI assistance during development, but no generative AI was used for GUI icons. Icons were hand-made, edited, or upscaled. The "makeface" logo was omitted as it overlapped with console elements.

## Installation
1. **Clone the Repository**:
   ```
   git clone https://github.com/yourusername/GRIS.git
   cd GRIS
   ```

2. **Set Up a Virtual Environment** (recommended to avoid conflicts):
   ```
   python -m venv venv
   source venv/bin/activate  # On Linux/macOS
   venv\Scripts\activate     # On Windows
   ```

3. **Install Dependencies**:
   ```
   pip install -r requirements.txt
   ```
   This will install:
   - PyQt5 (for GUI and dialogs)
   - PyOpenGL (for 3D rendering)
   - pypresence (for Discord Rich Presence)

   If you encounter issues with PyQt5 on certain platforms, ensure you have Qt5 installed via your package manager (e.g., `apt install python3-pyqt5` on Ubuntu).

4. **Prepare Assets** (optional but recommended):
   - Place custom fonts in `fonts/`.
   - Add sounds to `sound/` (e.g., `music/sbox.wav` for background music).
   - Add materials/textures/models to `materials/` (subfolders like `gui/`, `special/`, `models/` are auto-created if needed).

## Usage
1. **Run the Application**:
   ```
   python main.py
   ```
   - The app will launch in windowed mode by default (configurable in settings).
   - Use the toolbar for actions like creating objects, editing AI, saving/loading scenes.
   - Navigate the 3D view with WASD (movement), mouse (look), space/shift (up/down).
   - Right-click objects for context menus (e.g., edit AI, delete).

2. **Key Features in Action**:
   - **Scene Editing**: Add objects via the "Create" menu or toolbar. Select and manipulate with mouse/keyboard.
   - **AI Settings**: Right-click AI entities to configure behaviors (e.g., FSKY_CAPTURE_CBSGY for capturing).
   - **Drawing Mode**: Use the built-in canvas for textures (supports brush, shapes, undo/redo).
   - **General Settings**: Access via menu for window mode, sounds, skybox, etc.
   - **Saving/Loading**: Use File > Save/Load to work with JSON scene files.
   - **INT_MENU Mode**: Submit scenes to a simulated "INT_MENU" for AI interactions.

3. **Customizations**:
   - Edit `app_config.json` (auto-generated) for persistent settings.
   - Add custom OBJ models to `materials/models/`.
   - Visit the in-app Help for a link to the FSKY website (or check the `FSKY/` folder).

4. **Troubleshooting**:
   - If sounds don't play, ensure QtMultimedia is working (part of PyQt5).
   - OpenGL errors? Update your graphics drivers.
   - Missing folders? The app creates them on first run.
   - 
## Contributing
Feel free to fork, edit, or modify the project! Introduce new features, fix bugs, or optimize the code (it might be a bit messy—I'm not a professional). Just include credit to the original author (me) and the inspirations (Anomidae's INTERLOPER).

- **Issues**: Report bugs or suggestions via GitHub Issues.
- **Pull Requests**: Welcome for improvements.
- **Questions**: Message me on Discord: BEST_BASTARD / best_bastard#4512.

Will there be updates? Not sure—I'm tired and lack advanced skills to add more. But you're free to take it further!

## Credits
- **Anomidae**: Creator of the INTERLOPER series, the main inspiration.
- **Pumodi**: Music composer for sounds used.
- **programmer1o1**: Their SourceBox project inspired some modifications and was used for screenshots in FSKY html(screenshots only).
- Icons and GUI: Hand-made or edited by me and my friend.

## Fun Fact
Did you know that "KULCS" means "key" in Hungarian? (Sorry, couldn't resist the joke—it was my first time!)

## License
This project is open-source under the MIT License. See `LICENSE` file for details (add one if not present: standard MIT text). Feel free to use, modify, and distribute.
