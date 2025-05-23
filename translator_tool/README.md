# RPG Maker MV/MZ JSON Translator

This Python script translates text content within JSON files from RPG Maker MV/MZ projects from English to Spanish. It aims to identify user-facing text while leaving game code and pointers intact.

## Features

*   Reads JSON files from an `originales` subfolder.
*   Identifies potential translatable text based on common RPG Maker keys and heuristics.
*   Translates text using the `googletrans` library (unofficial Google Translate API).
*   Formats translated text using a line-wrapping algorithm to fit typical game message boxes.
*   Saves modified JSON files to a `traducidos` subfolder, preserving original file names and structure.
*   Provides console output for progress, real-time translation display, error messages, and estimated time remaining.

## Requirements

*   Python 3.6+
*   Pip (Python package installer)

## Setup and Installation

1.  Ensure Python 3 is installed on your system.
2.  Clone or download this tool into a directory (e.g., `translator_tool`).
3.  Open a terminal or command prompt in the `translator_tool` directory.
4.  Install the required Python libraries using the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```
    This will install `googletrans`.

## How to Use

1.  Place the RPG Maker JSON files (e.g., `MapXXX.json`, `CommonEvents.json`, `Items.json`, etc.) that you want to translate into the `translator_tool/originales/` subfolder.
    *   If your JSON files are in subdirectories within your game's data folder, try to replicate that structure within `originales/` if you want it mirrored in `traducidos/`.
2.  Run the script from the `translator_tool` directory:
    ```bash
    python translator.py
    ```
3.  The script will process the files, showing progress in the console.
4.  Translated files will be created in the `translator_tool/traducidos/` subfolder, maintaining the same filenames (and subdirectory structure, if any) as the originals.
5.  The original files in the `originales` folder will remain unchanged.

## Important Considerations & Limitations

*   **Translation Quality:** Uses `googletrans`, an unofficial library. Translation quality may vary, and the service might be unreliable or block requests if overused. Always review translations.
*   **Text Identification:** The script uses heuristics (common keys like "text", "message", "description", etc., and filtering rules) to identify translatable text. This may not be perfect for all RPG Maker plugins or custom JSON structures. Some game/event code might be mistakenly identified as translatable, or some user-facing text might be missed.
*   **Formatting:** Text is formatted to a maximum line width (default `M=50`). This might need adjustment based on your specific game's UI.
*   **No GUI:** This is a command-line tool.
*   **Backup your data:** While the script only writes to the `traducidos` folder, always back up your game project data before use.

## Error Handling

*   If translation fails for a specific string, the original string is kept in its place.
*   The script reports errors to the console (e.g., file not found, JSON parsing issues, translation API issues).
