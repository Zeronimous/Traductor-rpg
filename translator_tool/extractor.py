import os
import json
import re # Keep re for .txt file line stripping in main, if used there.

# --- Configuration for Specialized Extraction ---

DATABASE_KEYS_TO_EXTRACT = [
    "name", "description", "message1", "message2", "message3", "message4", 
    "nickname", "profile", "note", "title", 
    # Specific System.json terms are handled directly in its parsing logic
    # "terms.messages.actionFailure" # This kind of path is not for this list
]

# For GalleryList.json
GALLERY_KEYS = ["title", "comment", "text"] 

# For RubiList.json
RUBI_TEXT_KEYS = ["title", "text", "comment", "desc"]

# Minimum length for a string to be considered, if not covered by specific key lists/logic
MIN_STRING_LENGTH_GENERIC = 1 # Applied in generic scans like parameters or list items


def find_json_files(input_dir):
    """
    Recursively finds all JSON files (ending with .json) in the given input directory.
    """
    json_files = []
    for root, _, files in os.walk(input_dir):
        for file_name in files: 
            if file_name.endswith(".json"):
                json_files.append(os.path.join(root, file_name))
    return json_files

def is_valid_string(text_val):
    """
    Checks if a value is a non-empty string after stripping whitespace.
    """
    return isinstance(text_val, str) and text_val.strip() != ""

# More comprehensive looks_like_code_or_path from previous iterations (e.g., Turn 76)
def looks_like_code_or_path(s_val):
    if not isinstance(s_val, str):
        return False
    s_val_strip = s_val.strip()
    if not s_val_strip: 
        return False

    common_extensions = [".png", ".jpg", ".ogg", ".wav", ".json", ".txt", ".mv", ".mz"]
    if any(ext in s_val_strip.lower() for ext in common_extensions) and ('/' in s_val_strip or '\\' in s_val_strip or s_val_strip.count('.') > 1):
        return True
    if "img/" in s_val_strip or "audio/" in s_val_strip or "data/" in s_val_strip or "js/" in s_val_strip:
        return True
    if s_val_strip.startswith("<") and s_val_strip.endswith(">"): # RPG Maker style tags
        return True
    if "$" in s_val_strip or "variable[" in s_val_strip or "switch[" in s_val_strip or "item[" in s_val_strip or "selfSwitch[" in s_val_strip: # Script/variable patterns
        return True
    if "DataManager." in s_val_strip or "SceneManager." in s_val_strip or "BattleManager." in s_val_strip: # Common JS classes
        return True
    
    # Check for dot notation if it's not part of a sentence (e.g. "Plugin.command" vs "Hello. World.")
    # This heuristic checks if there are no spaces immediately around the dot(s).
    if s_val_strip.count('.') > 0:
        parts = s_val_strip.split('.')
        is_code_like_dot_notation = True
        if len(parts) > 1 : # Ensure there's at least one dot to make two parts
            for i, part in enumerate(parts):
                if i == 0 and part.endswith(' '): # space before dot: "example ."
                    is_code_like_dot_notation = False; break
                if i == len(parts) -1 and part.startswith(' '): # space after dot: ". example"
                    is_code_like_dot_notation = False; break
                if i > 0 and i < len(parts) -1 and (part.startswith(' ') or part.endswith(' ')): # space around dot: ". example ."
                    is_code_like_dot_notation = False; break
            if is_code_like_dot_notation and not any(' ' in p for p in parts): # If no spaces within parts either
                 if s_val_strip.count('.') > 1: # Typically, multiple dots without spaces are code.
                    return True


    # Refined camelCase/PascalCase check
    if ' ' not in s_val_strip and '(' not in s_val_strip and ')' not in s_val_strip and ':' not in s_val_strip:
        if s_val_strip[0].islower() and any(c.isupper() for c in s_val_strip[1:]) and not s_val_strip.isupper() and not s_val_strip.islower():
            return True # camelCase like myVariableName
        if s_val_strip[0].isupper() and any(c.islower() for c in s_val_strip[1:]) and any(c.isupper() for c in s_val_strip[1:]) and not s_val_strip.isupper():
             # PascalCase with multiple caps, not just a single capitalized word like "Chase"
             # Example: "MyObjectProperty", but not "Name" or "Title" (those are usually in COMMON_TEXT_KEYS)
             if len([c for c in s_val_strip if c.isupper()]) > 1: # Ensure more than one cap for this rule
                return True


    if "_" in s_val_strip and not " " in s_val_strip: # snake_case or ALL_CAPS_SNAKE
        if all(c.isalnum() or c == '_' for c in s_val_strip):
            return True
    if s_val_strip.isdigit(): # Purely digits
        return True
    if s_val_strip.startswith(" سید") or s_val_strip.endswith("سید "): # Specific non-English example from a test case
        return True
        
    return False

# --- Specialized Extraction Functions ---

def extract_text_from_map_events(map_events_list, base_event_list_path_parts, found_strings):
    if not isinstance(map_events_list, list):
        return

    for event_idx, event_obj in enumerate(map_events_list):
        if event_obj is None or not isinstance(event_obj, dict):
            continue
        
        current_event_path_base = base_event_list_path_parts + [str(event_idx)]

        event_name = event_obj.get("name")
        if "name" in DATABASE_KEYS_TO_EXTRACT and is_valid_string(event_name) and not looks_like_code_or_path(event_name):
             found_strings.append({"path": ".".join(current_event_path_base + ["name"]), "original": event_name})
        
        event_note = event_obj.get("note")
        if "note" in DATABASE_KEYS_TO_EXTRACT and is_valid_string(event_note) and not looks_like_code_or_path(event_note):
             found_strings.append({"path": ".".join(current_event_path_base + ["note"]), "original": event_note})

        pages = event_obj.get("pages")
        if not isinstance(pages, list):
            continue

        for page_idx, page_obj in enumerate(pages):
            if not isinstance(page_obj, dict):
                continue
            
            command_list = page_obj.get("list")
            if not isinstance(command_list, list):
                continue
            
            current_command_list_path_base = current_event_path_base + ["pages", str(page_idx), "list"]

            for cmd_idx, command_obj in enumerate(command_list):
                if not isinstance(command_obj, dict):
                    continue

                code = command_obj.get("code")
                parameters = command_obj.get("parameters")
                current_command_path_base = current_command_list_path_base + [str(cmd_idx)]
                
                parameter_path_base = current_command_path_base + ["parameters"]

                # Specific event command handling
                handled_specific_event = False
                if code in [401, 405] and isinstance(parameters, list) and len(parameters) > 0: # Show Text, Show Scrolling Text
                    text_val = parameters[0]
                    if is_valid_string(text_val) and not looks_like_code_or_path(text_val):
                        found_strings.append({"path": ".".join(parameter_path_base + ["0"]), "original": text_val})
                    handled_specific_event = True
                
                elif code == 102 and isinstance(parameters, list) and len(parameters) > 0 and isinstance(parameters[0], list): # Show Choices
                    choices_list = parameters[0]
                    for choice_idx, choice_text in enumerate(choices_list):
                        if is_valid_string(choice_text) and not looks_like_code_or_path(choice_text):
                            found_strings.append({"path": ".".join(parameter_path_base + ["0", str(choice_idx)]), "original": choice_text})
                    handled_specific_event = True 
                
                elif code in [108, 408] and isinstance(parameters, list) and len(parameters) > 0: # Comment
                    comment_text = parameters[0]
                    if is_valid_string(comment_text) and not looks_like_code_or_path(comment_text): # Only add if not code-like
                        found_strings.append({"path": ".".join(parameter_path_base + ["0"]), "original": comment_text})
                    handled_specific_event = True

                # Generic scan of parameters for this command (if not specifically handled or if it can have more text)
                if isinstance(parameters, list):
                    for param_idx, param_val in enumerate(parameters):
                        if handled_specific_event and param_idx == 0 : # Avoid double-adding param[0] for handled events
                            # For choices (102), param[0] is the list of choices, already iterated.
                            # Other params for 102 (like param[1] for cancel type) could still be strings.
                            if code == 102: continue # Skip all params for 102 in this generic scan for now
                        
                        if isinstance(param_val, str) and is_valid_string(param_val) and \
                           not looks_like_code_or_path(param_val) and \
                           len(param_val) >= MIN_STRING_LENGTH_GENERIC and not param_val.isdigit():
                            found_strings.append({"path": ".".join(parameter_path_base + [str(param_idx)]), "original": param_val})
                        elif isinstance(param_val, (dict,list)): # Recurse for complex parameters
                            extract_text_from_general_structure(param_val, parameter_path_base + [str(param_idx)], found_strings)


def extract_text_from_database_object_array(data_array, found_strings):
    if not isinstance(data_array, list):
        return

    for i, item in enumerate(data_array):
        if item is None or not isinstance(item, dict):
            continue
        base_path = [str(i)]
        for key in DATABASE_KEYS_TO_EXTRACT:
            if "." in key: continue # This list is for simple keys at object root
            text_val = item.get(key)
            if is_valid_string(text_val) and not looks_like_code_or_path(text_val):
                found_strings.append({"path": ".".join(base_path + [key]), "original": text_val})
        # Recursively check other parts of the item for non-standard text structures
        for key, value in item.items():
            if key not in DATABASE_KEYS_TO_EXTRACT and isinstance(value, (dict,list)): # Avoid re-processing known keys
                 extract_text_from_general_structure(value, base_path + [key], found_strings)


def extract_text_from_gallery_list_recursive(element, current_path_parts, found_strings):
    if isinstance(element, dict):
        for key, value in element.items():
            new_path_parts = current_path_parts + [key]
            if key in GALLERY_KEYS and is_valid_string(value) and not looks_like_code_or_path(value):
                found_strings.append({"path": ".".join(new_path_parts), "original": value})
            elif isinstance(value, (dict, list)):
                extract_text_from_gallery_list_recursive(value, new_path_parts, found_strings)
    elif isinstance(element, list):
        for i, item in enumerate(element):
            new_path_parts = current_path_parts + [str(i)]
            extract_text_from_gallery_list_recursive(item, new_path_parts, found_strings)

def extract_text_from_rubi_list_recursive(element, current_path_parts, found_strings):
    if isinstance(element, dict):
        for key, value in element.items():
            new_path_parts = current_path_parts + [key]
            if key in RUBI_TEXT_KEYS and is_valid_string(value) and not looks_like_code_or_path(value):
                found_strings.append({"path": ".".join(new_path_parts), "original": value})
            elif isinstance(value, (dict, list)):
                extract_text_from_rubi_list_recursive(value, new_path_parts, found_strings)
    elif isinstance(element, list):
        for i, item in enumerate(element):
            new_path_parts = current_path_parts + [str(i)]
            extract_text_from_rubi_list_recursive(item, new_path_parts, found_strings)

def extract_text_from_general_structure(data, base_path_parts, found_strings):
    """
    A generic recursive extractor for unknown structures or parts of known structures.
    Less precise, relies on string length and `looks_like_code_or_path`.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower().endswith("name") or key.lower().endswith("title") or key.lower().endswith("text") or key.lower().endswith("desc") or key.lower().endswith("note"):
                 if is_valid_string(value) and not looks_like_code_or_path(value):
                      found_strings.append({"path": ".".join(base_path_parts + [key]), "original": value})
            elif isinstance(value, str) and is_valid_string(value) and not looks_like_code_or_path(value) and len(value) >= 10: # General heuristic for longer strings
                 found_strings.append({"path": ".".join(base_path_parts + [key]), "original": value})
            elif isinstance(value, (dict, list)):
                extract_text_from_general_structure(value, base_path_parts + [key], found_strings)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, str) and is_valid_string(item) and not looks_like_code_or_path(item) and len(item) >= 10:
                 found_strings.append({"path": ".".join(base_path_parts + [str(i)]), "original": item})
            elif isinstance(item, (dict, list)):
                extract_text_from_general_structure(item, base_path_parts + [str(i)], found_strings)


def extract_text_from_json_content(filename, json_content):
    found_strings = []
    if filename.startswith("Map") and filename.endswith(".json"):
        if isinstance(json_content, dict):
            map_events = json_content.get("events")
            if map_events is not None:
                 extract_text_from_map_events(map_events, ["events"], found_strings)
            display_name = json_content.get('displayName')
            if is_valid_string(display_name) and not looks_like_code_or_path(display_name):
                 found_strings.append({'path': 'displayName', 'original': display_name})
    
    elif filename == "CommonEvents.json":
        if isinstance(json_content, list):
            for i, common_event in enumerate(json_content):
                if common_event is None: continue
                if isinstance(common_event, dict):
                    name = common_event.get("name")
                    if "name" in DATABASE_KEYS_TO_EXTRACT and is_valid_string(name) and not looks_like_code_or_path(name):
                        found_strings.append({'path': f"{i}.name", 'original': name})
                    event_list = common_event.get("list")
                    if event_list is not None:
                        extract_text_from_map_events(event_list, [str(i), "list"], found_strings)

    elif filename == "GalleryList.json":
        extract_text_from_gallery_list_recursive(json_content, [], found_strings)
    elif filename == "RubiList.json":
        extract_text_from_rubi_list_recursive(json_content, [], found_strings)

    elif filename == "System.json" and isinstance(json_content, dict):
        if is_valid_string(json_content.get("gameTitle")) and not looks_like_code_or_path(json_content.get("gameTitle")):
            found_strings.append({'path': 'gameTitle', 'original': json_content['gameTitle']})
        
        terms = json_content.get("terms")
        if isinstance(terms, dict):
            for term_category_key, term_values in terms.items():
                if isinstance(term_values, list):
                    for i, term_val in enumerate(term_values):
                        if is_valid_string(term_val) and not looks_like_code_or_path(term_val):
                            found_strings.append({"path": f"terms.{term_category_key}.{i}", "original": term_val})
                elif isinstance(term_values, dict): 
                     for msg_key, msg_val in term_values.items():
                         if is_valid_string(msg_val) and not looks_like_code_or_path(msg_val):
                             found_strings.append({"path": f"terms.{term_category_key}.{msg_key}", "original": msg_val})
        
        for key in DATABASE_KEYS_TO_EXTRACT: # For other top-level simple keys
            if "." in key: continue
            text_val = json_content.get(key)
            if is_valid_string(text_val) and not looks_like_code_or_path(text_val):
                found_strings.append({"path": key, "original": text_val})
        # Generic scan for any other text in System.json not covered by above
        extract_text_from_general_structure(json_content, [], found_strings)


    elif isinstance(json_content, list): # Default for other database files
        extract_text_from_database_object_array(json_content, found_strings)
    
    elif isinstance(json_content, dict): # For other single-object JSON files
        # Apply generic scan to the root object
        extract_text_from_general_structure(json_content, [], found_strings)
        
    return found_strings


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    originales_base_dir = os.path.join(script_dir, "originales")
    textos_base_dir = os.path.join(script_dir, "textos") 
    os.makedirs(textos_base_dir, exist_ok=True) 

    if not os.path.isdir(originales_base_dir):
        print(f"Error: Input directory '{originales_base_dir}' not found.")
        return

    json_files_to_process = find_json_files(originales_base_dir)

    if not json_files_to_process:
        print(f"No JSON files found in '{originales_base_dir}'.")
        return

    print(f"Found {len(json_files_to_process)} JSON files to process.")
    total_strings_extracted_all_files = 0

    for file_path in json_files_to_process:
        base_filename_for_dispatch = os.path.basename(file_path)
        print(f"Processing file: {os.path.relpath(file_path, script_dir)}...")
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f: # Use utf-8-sig
                data = json.load(f)
            
            found_strings_for_current_file = extract_text_from_json_content(base_filename_for_dispatch, data)
            
            unique_texts_in_file = []
            seen_tuples_in_file = set()
            for text_info in found_strings_for_current_file:
                identity_tuple = (text_info["path"], text_info["original"])
                if identity_tuple not in seen_tuples_in_file:
                    unique_texts_in_file.append(text_info)
                    seen_tuples_in_file.add(identity_tuple)
            
            if unique_texts_in_file:
                print(f"  Found {len(unique_texts_in_file)} unique translatable strings in {base_filename_for_dispatch}.")
                total_strings_extracted_all_files += len(unique_texts_in_file)

                base_filename_output = os.path.splitext(base_filename_for_dispatch)[0]
                txt_output_path = os.path.join(textos_base_dir, f"{base_filename_output}.txt")
                jsonpaths_output_path = os.path.join(textos_base_dir, f"{base_filename_output}.jsonpaths")

                try:
                    with open(txt_output_path, 'w', encoding='utf-8') as txt_file:
                        for i, entry in enumerate(unique_texts_in_file):
                            text_to_write = entry['original'].replace('\n', '[NEWLINE]')
                            txt_file.write(f"{i+1}) {text_to_write}\n") 
                    print(f"    Generated: {os.path.relpath(txt_output_path, script_dir)} ({len(unique_texts_in_file)} strings)")

                    paths_only = [entry['path'] for entry in unique_texts_in_file]
                    with open(jsonpaths_output_path, 'w', encoding='utf-8') as paths_file:
                        json.dump(paths_only, paths_file, indent=2)
                    print(f"    Generated: {os.path.relpath(jsonpaths_output_path, script_dir)} ({len(paths_only)} paths)")

                except IOError as e:
                    print(f"    Error writing output files for {base_filename_output}: {e}")
            else:
                print(f"  No translatable strings found in {base_filename_for_dispatch}.")

        except FileNotFoundError:
            print(f"Error: File not found during processing: {file_path}")
        except json.JSONDecodeError as e: 
            print(f"Error: Could not decode JSON from {file_path}. Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred with {file_path}: {e}")
    
    if total_strings_extracted_all_files > 0:
        print(f"\nExtraction complete. Found a total of {total_strings_extracted_all_files} translatable strings across all files.")
        print(f"Please check the .txt and .jsonpaths files in the '{os.path.relpath(textos_base_dir, script_dir)}' directory.")
    else:
        print("\nExtraction complete. No translatable strings were found in any file.")

if __name__ == "__main__":
    main()
