import os
import json

# --- Configuration for Text Identification ---
# List of common JSON keys that usually contain translatable text.
COMMON_TEXT_KEYS = [
    "name", "description", "note", "message", "text", 
    "title", "subtitle", "displayName", "profile", "scenario"
    # Add other keys that are common in your specific JSON files if needed
]

# List of JSON keys that typically do NOT contain translatable text.
EXCLUDED_KEYS = [
    "actorId", "classId", "skillId", "itemId", "weaponId", "armorId", "enemyId", 
    "troopId", "animationId", "tilesetId", "bgm", "bgs", "me", "se", 
    "mapName", # Usually an internal name; 'displayName' is often used for the visible name
    "script", "pluginId", "variableId", "switchId", "characterName", "faceName",
    "battlerName", "actionButton", "trigger", "image", "iconIndex",
    "bgImage", "picture", "bgPicture", "fgPicture", "code" # 'code' for event commands
    # Add other technical keys to exclude if necessary
]

MIN_STRING_LENGTH_FOR_COMMON_KEYS = 2 # For keys in COMMON_TEXT_KEYS
MIN_STRING_LENGTH_OTHER = 10 # For strings found in other contexts (e.g., direct list items)


def find_json_files(input_dir):
    """
    Recursively finds all JSON files (ending with .json) in the given input directory.
    """
    json_files = []
    for root, _, files in os.walk(input_dir):
        for file_name in files: # Renamed 'file' to 'file_name' to avoid conflict
            if file_name.endswith(".json"):
                json_files.append(os.path.join(root, file_name))
    return json_files

def looks_like_code_or_path(s_val):
    """
    Heuristic function to determine if a string looks like code, a file path, an ID, or a tag.
    """
    if not isinstance(s_val, str):
        return False
    
    s_val_strip = s_val.strip()
    if not s_val_strip: # Empty or whitespace-only string
        return False

    # Check for common file extensions or path-like structures
    common_extensions = [".png", ".jpg", ".ogg", ".wav", ".json", ".txt", ".mv", ".mz"]
    if any(ext in s_val_strip.lower() for ext in common_extensions) and ('/' in s_val_strip or '\\' in s_val_strip or s_val_strip.count('.') > 1):
        return True
    if "img/" in s_val_strip or "audio/" in s_val_strip or "data/" in s_val_strip or "js/" in s_val_strip:
        return True
        
    # Check for RPG Maker style tags (e.g., <WordWrap>, <Color:Red>)
    if s_val_strip.startswith("<") and s_val_strip.endswith(">"):
        return True
        
    # Check for script calls or variable access patterns (e.g., $gameVariables.value(10))
    if "$" in s_val_strip or "variable[" in s_val_strip or "switch[" in s_val_strip or "item[" in s_val_strip or "selfSwitch[" in s_val_strip:
        return True
    if "DataManager." in s_val_strip or "SceneManager." in s_val_strip or "BattleManager." in s_val_strip: # Common JS classes
        return True
    if s_val_strip.count('.') > 1 and not any(c.isspace() for c in s_val_strip): # e.g. Plugin.Command.Name, but not "Hello. World."
        return True

    # Check for camelCase or PascalCase (often indicates code variables or internal names)
    # if no spaces and contains mixed case (and not just a single proper noun)
    if ' ' not in s_val_strip and s_val_strip.lower() != s_val_strip and s_val_strip.upper() != s_val_strip:
        # A simple check: more than one uppercase char, or starts lowercase and has an uppercase
        num_upper = sum(1 for c in s_val_strip if c.isupper())
        if num_upper > 1 or (s_val_strip[0].islower() and num_upper > 0):
            # This is a heuristic and might catch some edge cases like "McDonald"
            # but is generally good for variable names like "myVariableName" or "MyObjectProperty"
            # Avoid if it contains numbers, as it could be an ID like "Item1"
            if not any(c.isdigit() for c in s_val_strip):
                return True
    
    # Check for strings that are likely IDs (e.g., all caps with underscores, or alphanumeric with underscores)
    if "_" in s_val_strip and not " " in s_val_strip:
        if all(c.isalnum() or c == '_' for c in s_val_strip):
            return True
            
    # Check for digits only
    if s_val_strip.isdigit():
        return True
        
    return False

def extract_translatable_strings_recursive(data, current_path_parts, found_strings):
    """
    Recursively traverses JSON data to find translatable strings.
    - data: The current piece of JSON data (dict, list, or primitive).
    - current_path_parts: A list of keys/indices representing the path to the current data.
    - found_strings: A list to append found translatable strings to.
                     Each item is a dict: {"path": "dot.separated.path", "original": "string"}.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            new_path_parts = current_path_parts + [str(key)]
            
            if key in EXCLUDED_KEYS: # Skip explicitly excluded keys
                continue

            if isinstance(value, str):
                # Heuristic 1: Key is a common text key
                if key in COMMON_TEXT_KEYS:
                    if not looks_like_code_or_path(value) and len(value.strip()) >= MIN_STRING_LENGTH_FOR_COMMON_KEYS:
                        found_strings.append({"path": ".".join(new_path_parts), "original": value})
                # Heuristic 2: Specific handling for RPG Maker event commands (e.g., Show Text code 401)
                # 'code' is usually at the same level as 'parameters' in an event command object
                elif key == 'parameters' and isinstance(value, list) and 'code' in data:
                    parent_code = data.get('code')
                    # Show Text (401), Show Choices (102), Show Scrolling Text (405)
                    # For 401 (Show Text), the text is typically value[0]
                    if parent_code == 401 and value and len(value) > 0 and isinstance(value[0], str):
                        if not looks_like_code_or_path(value[0]) and len(value[0].strip()) >= MIN_STRING_LENGTH_FOR_COMMON_KEYS:
                            text_param_path = new_path_parts + ['0']
                            found_strings.append({"path": ".".join(text_param_path), "original": value[0]})
                    # For 102 (Show Choices), choices are in value[0] (a list of strings)
                    elif parent_code == 102 and value and len(value) > 0 and isinstance(value[0], list):
                        for choice_idx, choice_text in enumerate(value[0]):
                            if isinstance(choice_text, str) and not looks_like_code_or_path(choice_text) and len(choice_text.strip()) >= MIN_STRING_LENGTH_FOR_COMMON_KEYS:
                                choice_path = new_path_parts + ['0', str(choice_idx)]
                                found_strings.append({"path": ".".join(choice_path), "original": choice_text})
                    # For 405 (Show Scrolling Text), text is value[0]
                    elif parent_code == 405 and value and len(value) > 0 and isinstance(value[0], str):
                         if not looks_like_code_or_path(value[0]) and len(value[0].strip()) >= MIN_STRING_LENGTH_FOR_COMMON_KEYS:
                            text_param_path = new_path_parts + ['0']
                            found_strings.append({"path": ".".join(text_param_path), "original": value[0]})
                # Heuristic 3: Other string values not caught by above, if they are long enough
                # and not associated with an excluded key or look like code/path.
                elif not looks_like_code_or_path(value) and len(value.strip()) >= MIN_STRING_LENGTH_OTHER:
                    found_strings.append({"path": ".".join(new_path_parts), "original": value})
            
            # Recurse if value is a dictionary or list
            elif isinstance(value, (dict, list)):
                extract_translatable_strings_recursive(value, new_path_parts, found_strings)

    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_path_parts = current_path_parts + [str(i)]
            if isinstance(item, str):
                # Strings directly in lists (e.g. some plugin parameters, descriptions in a list)
                # Apply a general length and content check.
                if not looks_like_code_or_path(item) and len(item.strip()) >= MIN_STRING_LENGTH_OTHER:
                    # Check if the parent key (if the list is part of a dict) is an excluded key.
                    parent_key_if_any = current_path_parts[-1] if current_path_parts and not current_path_parts[-1].isdigit() else ""
                    if parent_key_if_any not in EXCLUDED_KEYS:
                        found_strings.append({"path": ".".join(new_path_parts), "original": item})
            
            # Recurse if item is a dictionary or list
            elif isinstance(item, (dict, list)):
                extract_translatable_strings_recursive(item, new_path_parts, found_strings)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    originales_base_dir = os.path.join(script_dir, "originales")
    textos_base_dir = os.path.join(script_dir, "textos") # Define output directory for text files
    os.makedirs(textos_base_dir, exist_ok=True) # Ensure 'textos' directory exists

    if not os.path.isdir(originales_base_dir):
        print(f"Error: Input directory '{originales_base_dir}' not found.")
        return

    json_files_to_process = find_json_files(originales_base_dir)

    if not json_files_to_process:
        print(f"No JSON files found in '{originales_base_dir}'.")
        return

    print(f"Found {len(json_files_to_process)} JSON files to process.")
    total_strings_extracted_all_files = 0 # Renamed from total_strings_across_all_files

    for file_path in json_files_to_process:
        print(f"Processing file: {os.path.relpath(file_path, script_dir)}...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            found_strings_for_current_file = []
            extract_translatable_strings_recursive(data, [], found_strings_for_current_file)
            
            unique_texts_in_file = []
            seen_tuples_in_file = set()
            for text_info in found_strings_for_current_file:
                identity_tuple = (text_info["path"], text_info["original"])
                if identity_tuple not in seen_tuples_in_file:
                    unique_texts_in_file.append(text_info)
                    seen_tuples_in_file.add(identity_tuple)
            
            if unique_texts_in_file:
                print(f"  Found {len(unique_texts_in_file)} unique translatable strings in {os.path.basename(file_path)}.")
                total_strings_extracted_all_files += len(unique_texts_in_file)

                base_filename = os.path.splitext(os.path.basename(file_path))[0]
                txt_output_path = os.path.join(textos_base_dir, f"{base_filename}.txt")
                jsonpaths_output_path = os.path.join(textos_base_dir, f"{base_filename}.jsonpaths")

                try:
                    # Create .txt file
                    with open(txt_output_path, 'w', encoding='utf-8') as txt_file:
                        for i, entry in enumerate(unique_texts_in_file):
                            text_to_write = entry['original'].replace('\n', '[NEWLINE]')
                            txt_file.write(f"{i+1}) {text_to_write}\n") 
                    print(f"    Generated: {os.path.relpath(txt_output_path, script_dir)} ({len(unique_texts_in_file)} strings)")

                    # Create .jsonpaths file
                    paths_only = [entry['path'] for entry in unique_texts_in_file]
                    with open(jsonpaths_output_path, 'w', encoding='utf-8') as paths_file:
                        json.dump(paths_only, paths_file, indent=2)
                    print(f"    Generated: {os.path.relpath(jsonpaths_output_path, script_dir)} ({len(paths_only)} paths)")

                except IOError as e:
                    print(f"    Error writing output files for {base_filename}: {e}")
            else:
                print(f"  No translatable strings found in {os.path.basename(file_path)}.")

        except FileNotFoundError:
            print(f"Error: File not found during processing: {file_path}")
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {file_path}")
        except Exception as e:
            print(f"An unexpected error occurred with {file_path}: {e}")
    
    if total_strings_extracted_all_files > 0:
        print(f"\nExtraction complete. Found a total of {total_strings_extracted_all_files} translatable strings across all files.")
        print(f"Please check the .txt and .jsonpaths files in the '{os.path.relpath(textos_base_dir, script_dir)}' directory.") # Show relative path
    else:
        print("\nExtraction complete. No translatable strings were found in any file.")

if __name__ == "__main__":
    main()
