import os
import json

# --- Configuration for Text Identification ---
COMMON_TEXT_KEYS = [
    "name", "description", "note", "message", "text", 
    "title", "subtitle", "displayName", "profile", "scenario"
]
EXCLUDED_KEYS = [
    "actorId", "classId", "skillId", "itemId", "weaponId", "armorId", "enemyId", 
    "troopId", "animationId", "tilesetId", "bgm", "bgs", "me", "se", 
    "mapName", "script", "pluginId", "variableId", "switchId", "characterName", "faceName",
    "battlerName", "actionButton", "trigger", "image", "iconIndex",
    "bgImage", "picture", "bgPicture", "fgPicture", "code" 
]
MIN_STRING_LENGTH_FOR_COMMON_KEYS = 2 
MIN_STRING_LENGTH_OTHER = 10 # Default for other non-common-key strings
MIN_STRING_LENGTH_GENERIC_LIST_ITEM = 1 # For strings directly in lists or generic parameter lists

def find_json_files(input_dir):
    json_files = []
    for root, _, files in os.walk(input_dir):
        for file_name in files: 
            if file_name.endswith(".json"):
                json_files.append(os.path.join(root, file_name))
    return json_files

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
    if s_val_strip.startswith("<") and s_val_strip.endswith(">"):
        return True
    if "$" in s_val_strip or "variable[" in s_val_strip or "switch[" in s_val_strip or "item[" in s_val_strip or "selfSwitch[" in s_val_strip:
        return True
    if "DataManager." in s_val_strip or "SceneManager." in s_val_strip or "BattleManager." in s_val_strip:
        return True
    # Check for dot notation if it's not part of a sentence (e.g. "Plugin.command" vs "Hello. World.")
    if s_val_strip.count('.') > 0 and not any(c.isspace() for c in s_val_strip.split('.')[0] + s_val_strip.split('.')[-1]): # Heuristic: check for spaces around dots
         if s_val_strip.count('.') > 1 : # Usually, multiple dots without spaces indicate code.
             return True


    # Refined camelCase/PascalCase check - less aggressive
    # Checks for myVariableName or MyVariableName, but not "Chase", "Attack", "UPPER_CASE_WORD"
    if (' ' not in s_val_strip and 
        '(' not in s_val_strip and ')' not in s_val_strip and ':' not in s_val_strip and # Avoid if it contains typical method/property access chars
        s_val_strip[0].islower() and any(c.isupper() for c in s_val_strip[1:]) and # Starts lowercase, has uppercase later
        not s_val_strip.isupper() and not s_val_strip.islower()): # Not all upper or all lower
        return True
    
    # Check for PascalCase that isn't just a single capitalized word (e.g. "MyObject" but not "Chase")
    if (' ' not in s_val_strip and s_val_strip[0].isupper() and 
        any(c.islower() for c in s_val_strip[1:]) and # Has lowercase letters after the first
        any(c.isupper() for c in s_val_strip[1:]) and # Has other uppercase letters
        not s_val_strip.isupper()): # Not all uppercase
        return True


    if "_" in s_val_strip and not " " in s_val_strip:
        if all(c.isalnum() or c == '_' for c in s_val_strip):
            return True
    if s_val_strip.isdigit():
        return True
    return False

def extract_translatable_strings_recursive(data, current_path_parts, found_strings):
    if isinstance(data, dict):
        for key, value in data.items():
            new_path_parts = current_path_parts + [str(key)]
            if key in EXCLUDED_KEYS:
                continue

            if isinstance(value, str):
                if key in COMMON_TEXT_KEYS:
                    if not looks_like_code_or_path(value) and len(value.strip()) >= MIN_STRING_LENGTH_FOR_COMMON_KEYS:
                        found_strings.append({"path": ".".join(new_path_parts), "original": value})
                # Generic string check (not a common key, not part of handled parameters list directly)
                elif not looks_like_code_or_path(value) and len(value.strip()) >= MIN_STRING_LENGTH_OTHER:
                    found_strings.append({"path": ".".join(new_path_parts), "original": value})
            
            # New generic 'parameters' list handling (comes after string value check for the key itself, before general recursion)
            elif key == 'parameters' and isinstance(value, list):
                for i, param_item in enumerate(value):
                    if isinstance(param_item, str) and not looks_like_code_or_path(param_item) and \
                       len(param_item.strip()) >= MIN_STRING_LENGTH_GENERIC_LIST_ITEM and not param_item.isdigit():
                        param_path_parts = new_path_parts + [str(i)]
                        found_strings.append({"path": ".".join(param_path_parts), "original": param_item})
                # Always recurse into 'parameters' list as it might contain dicts or further lists with text
                extract_translatable_strings_recursive(value, new_path_parts, found_strings)
            
            # General recursion for other dicts or lists
            elif isinstance(value, (dict, list)):
                extract_translatable_strings_recursive(value, new_path_parts, found_strings)

    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_path_parts = current_path_parts + [str(i)]
            if isinstance(item, str):
                # Updated condition for strings directly in lists
                if not looks_like_code_or_path(item) and \
                   len(item.strip()) >= MIN_STRING_LENGTH_GENERIC_LIST_ITEM and not item.isdigit():
                    parent_key_if_any = current_path_parts[-1] if current_path_parts and not current_path_parts[-1].isdigit() else ""
                    if parent_key_if_any not in EXCLUDED_KEYS:
                        found_strings.append({"path": ".".join(new_path_parts), "original": item})
            
            elif isinstance(item, (dict, list)):
                # Specific handling for RPG Maker event command lists (item is a dict command)
                # This existing logic should take precedence for items that are event command dicts
                is_event_command_dict = isinstance(item, dict) and 'code' in item # Simplified check
                
                if is_event_command_dict:
                    code = item.get('code')
                    parameters = item.get('parameters') # parameters is a key within the item dict
                    
                    # Path to the parameters list itself within this event command item
                    # e.g., events.0.list.0.parameters (if new_path_parts is events.0.list.0)
                    item_params_base_path = new_path_parts + ['parameters']

                    if code == 401 and isinstance(parameters, list) and len(parameters) > 0 and isinstance(parameters[0], str):
                        text_val = parameters[0]
                        if not looks_like_code_or_path(text_val) and len(text_val.strip()) >= MIN_STRING_LENGTH_FOR_COMMON_KEYS:
                            param_path = item_params_base_path + ['0']
                            found_strings.append({"path": ".".join(param_path), "original": text_val})
                            # To avoid double-dipping by the generic parameters list handler later if we recurse on 'item',
                            # we could pass a modified item or ensure the generic handler is smart.
                            # For now, the generic handler for 'parameters' key won't apply here since 'code' is not 'parameters'.
                            # We still need to recurse into the rest of 'item' skipping 'parameters' if handled.
                            temp_item_for_recursion = item.copy()
                            temp_item_for_recursion.pop('parameters', None) # Remove parameters as they were handled or will be by generic
                            extract_translatable_strings_recursive(temp_item_for_recursion, new_path_parts, found_strings)
                            # Also, explicitly recurse into the parameters if they might contain more than just this string
                            if isinstance(parameters, list): # Recurse into parameters list itself for other items/structures
                                extract_translatable_strings_recursive(parameters, item_params_base_path, found_strings)
                            continue # Handled this event command dict, move to next item in list

                    elif code == 102 and isinstance(parameters, list) and len(parameters) > 0 and isinstance(parameters[0], list):
                        choices = parameters[0]
                        for choice_idx, choice_text in enumerate(choices):
                            if isinstance(choice_text, str) and not looks_like_code_or_path(choice_text) and \
                               len(choice_text.strip()) >= MIN_STRING_LENGTH_FOR_COMMON_KEYS:
                                choice_path = item_params_base_path + ['0', str(choice_idx)]
                                found_strings.append({"path": ".".join(choice_path), "original": choice_text})
                        temp_item_for_recursion = item.copy()
                        temp_item_for_recursion.pop('parameters', None)
                        extract_translatable_strings_recursive(temp_item_for_recursion, new_path_parts, found_strings)
                        if isinstance(parameters, list):
                            extract_translatable_strings_recursive(parameters, item_params_base_path, found_strings)
                        continue
                        
                    elif code == 405 and isinstance(parameters, list) and len(parameters) > 0 and isinstance(parameters[0], str):
                        text_val = parameters[0]
                        if not looks_like_code_or_path(text_val) and len(text_val.strip()) >= MIN_STRING_LENGTH_FOR_COMMON_KEYS:
                            param_path = item_params_base_path + ['0']
                            found_strings.append({"path": ".".join(param_path), "original": text_val})
                        temp_item_for_recursion = item.copy()
                        temp_item_for_recursion.pop('parameters', None)
                        extract_translatable_strings_recursive(temp_item_for_recursion, new_path_parts, found_strings)
                        if isinstance(parameters, list):
                             extract_translatable_strings_recursive(parameters, item_params_base_path, found_strings)
                        continue
                
                # Default recursion for other items in the list (if not a specially handled event command dict)
                extract_translatable_strings_recursive(item, new_path_parts, found_strings)


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
        print(f"Processing file: {os.path.relpath(file_path, script_dir)}...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            found_strings_for_current_file = []
            extract_translatable_strings_recursive(data, [], found_strings_for_current_file)
            
            unique_texts_in_file = []
            seen_tuples_in_file = set()
            for text_info in found_strings_for_current_file:
                identity_tuple = (text_info["path"], text_info["original"]) # Use path and original for uniqueness
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
        print(f"Please check the .txt and .jsonpaths files in the '{os.path.relpath(textos_base_dir, script_dir)}' directory.")
    else:
        print("\nExtraction complete. No translatable strings were found in any file.")

if __name__ == "__main__":
    main()
