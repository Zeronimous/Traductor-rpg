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

def extract_quoted_strings(text_block):
    if not isinstance(text_block, str):
        return []
    
    # Regex for double-quoted strings, handling escaped double quotes
    double_quoted_pattern = r'"((?:[^"\\]|\\.)*)"'
    # Regex for single-quoted strings, handling escaped single quotes
    single_quoted_pattern = r"'((?:[^'\\]|\\.)*)'"
    
    found_strings = []
    
    # Find all double-quoted strings
    for match in re.finditer(double_quoted_pattern, text_block):
        try:
            # Group 1 contains the content within the quotes
            # Attempt to decode standard Python string escapes (e.g., \n, \t, \xHH, \uHHHH, \UHHHHHHHH)
            # The 'unicode_escape' codec is good for this.
            # We need to encode to a byte string first, as decode expects bytes.
            unescaped_str = match.group(1).encode('latin-1', 'backslashreplace').decode('unicode_escape')
            found_strings.append(unescaped_str)
        except UnicodeDecodeError:
            found_strings.append(match.group(1)) # Append raw if unicode_escape fails
            
    # Find all single-quoted strings
    for match in re.finditer(single_quoted_pattern, text_block):
        try:
            unescaped_str = match.group(1).encode('latin-1', 'backslashreplace').decode('unicode_escape')
            found_strings.append(unescaped_str)
        except UnicodeDecodeError:
            found_strings.append(match.group(1))

    return found_strings

# Updated looks_like_code_or_path function
def looks_like_code_or_path(text_input):
    if not isinstance(text_input, str):
        return False 
    
    text = text_input.strip()
    if not text:
        return False

    # Rule out obvious text first
    if ' ' in text and text[-1] in '.?!¡¿':
        if text[0].isupper() or text[0] in '¡¿"\'': # Note: Corrected unescaped single quote from prompt
            if not (re.search(r'[=\[\]{}();]', text) or 
                    '//' in text or '/*' in text or '*/' in text or 
                    text.startswith("this.") or text.startswith("$game") or 
                    re.search(r'\b(function|var|let|const|return|if|else|for|while)\b', text)):
                return False

    # Path / File extensions
    if re.search(r'\.(png|jpg|jpeg|gif|ogg|mp3|wav|json|txt|dll|exe|js|py|rb|html|css|yaml|ini|dat|ttf|woff|woff2)$', text, re.IGNORECASE):
        return True
    if re.search(r'(^|\s)[a-zA-Z]:\\', text) or re.search(r'^(/|\\|\.\./|\.~([\\/]))', text): # Windows/Unix paths (note: fixed regex for \.~/)
        return True
    if text.startswith("img/") or text.startswith("audio/") or text.startswith("data/") or text.startswith("js/") or text.startswith("effects/") or text.startswith("fonts/"):
        return True

    # Plugin tags
    if re.fullmatch(r'<[^<>:]+:[^<>]*>', text) or re.fullmatch(r'<[^<>]+>', text): # Simpler second part for <tag>
        return True

    # RPG Maker specific script calls / patterns
    if text.startswith("this._") or (text.startswith("this.") and '(' in text and ')' in text and not text.split('(')[0].count(' ') > 0):
        return True
    if text.startswith(("$game", "Game_Interpreter.prototype.", "SceneManager.", "DataManager.", "Window_", "Sprite_")): # Made tuple
        if '.' in text or '(' in text: 
            return True
    if re.search(r"\b(eval|setTimeout|setInterval|clearInterval|clearTimeout)\(", text): # Escaped (
        return True

    # JavaScript keywords
    js_keywords_indicators = ['function', 'var ', 'let ', 'const ', 'return ', 'if (', 'else {', 'for (', 'while (', 'switch (', 'case ', '.prototype', '=>']
    if any(kw in text for kw in js_keywords_indicators):
        return True
    
    # Assignments
    if re.match(r'^[a-zA-Z_$.][a-zA-Z0-9_$.]*\s*=[^=]', text): 
        return True
       
    # Function calls
    # Check for word characters, then optional dot and more word characters, then optional spaces, then parentheses.
    # Avoids matching things like "Name (Nickname):"
    if re.match(r'^[a-zA-Z_$\s][a-zA-Z0-9_$.]*\s*\([^)]*\)$', text) and not text.split('(')[0].strip().count(' ') > 1: # if there are many spaces before '(', it's likely text
        # Further check if the part before parenthesis is a common function name pattern (no spaces)
        func_name_part = text.split('(')[0].strip()
        if not (' ' in func_name_part or func_name_part.endswith(':')) :
             # Avoid flagging simple user text like "Objective (Optional):"
            if not (func_name_part.endswith(":") and text.endswith(":") and text.count(":") == 1):
                return True
                
    # Specific patterns to filter
    if re.fullmatch(r'[A-Z_][A-Z0-9_]{2,}', text): # CONSTANT_CASE, at least 3 chars
        return True
    # WordNumberWord or WordNumber - e.g. Actor1Face, Item2, Var5
    if re.fullmatch(r'[a-zA-Z]+[0-9]+[a-zA-Z0-9]*', text) and not ' ' in text:
        return True
    
    # PascalCase or camelCase (stricter: require at least one lower->upper or upper->lower transition if mixed)
    # and not a common text pattern.
    if not ' ' in text and len(text) > 1: # Single word
        is_pascal = text[0].isupper() and any(c.islower() for c in text[1:]) and any(c.isupper() for c in text[1:])
        is_camel = text[0].islower() and any(c.isupper() for c in text[1:])
        if (is_pascal or is_camel) and len(text) < 20: # Shorter likely to be identifiers
             # Avoid flagging single capitalized words like "Chase" or "Hello" if they are common.
            if text.lower() not in ['name', 'text', 'desc', 'description', 'title', 'message', 'label', 'caption', 'profile', 'note', 'event', 'actor', 'item', 'skill', 'class', 'enemy', 'troop', 'state', 'system', 'map']:
                return True
                
    # High ratio of non-alphanumeric (excluding common text punctuation)
    # Allow: a-z A-Z 0-9 space . ? ! ¡ ¿ - ' " ( ) : ; , % \ (for RPG Maker codes like \C[1])
    allowed_text_chars_pattern = r'[a-zA-Z0-9\s\.,!\?\-'"\(\):;%\\]' # Note: removed ¡¿ from allowed for this specific regex
    non_text_chars = re.sub(allowed_text_chars_pattern, '', text)
    if len(text) > 0 and len(non_text_chars) > len(text) * 0.35 and len(text) > 3: 
        return True
       
    if text in ['true', 'false', 'null', 'undefined']:
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
        
        original_note = event_obj.get("note")
        if "note" in DATABASE_KEYS_TO_EXTRACT and is_valid_string(original_note):
            quoted_texts = extract_quoted_strings(original_note)
            if quoted_texts:
                for i_q, q_text in enumerate(quoted_texts): # Process each quoted string individually
                    if is_valid_string(q_text) and not looks_like_code_or_path(q_text):
                        found_strings.append({"path": ".".join(current_event_path_base + ["note", f"q_{i_q}"]), "original": q_text})
            elif not looks_like_code_or_path(original_note): # If no usable quoted strings, check the whole note
                 found_strings.append({"path": ".".join(current_event_path_base + ["note"]), "original": original_note})


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

                handled_specific_event = False
                if code in [401, 405] and isinstance(parameters, list) and len(parameters) > 0: 
                    text_val = parameters[0]
                    if is_valid_string(text_val) and not looks_like_code_or_path(text_val):
                        found_strings.append({"path": ".".join(parameter_path_base + ["0"]), "original": text_val})
                    handled_specific_event = True
                
                elif code == 102 and isinstance(parameters, list) and len(parameters) > 0 and isinstance(parameters[0], list): 
                    choices_list = parameters[0]
                    for choice_idx, choice_text in enumerate(choices_list):
                        if is_valid_string(choice_text) and not looks_like_code_or_path(choice_text):
                            found_strings.append({"path": ".".join(parameter_path_base + ["0", str(choice_idx)]), "original": choice_text})
                    handled_specific_event = True 
                
                elif code in [108, 408] and isinstance(parameters, list) and len(parameters) > 0: 
                    comment_text = parameters[0]
                    if is_valid_string(comment_text) and not looks_like_code_or_path(comment_text):
                        found_strings.append({"path": ".".join(parameter_path_base + ["0"]), "original": comment_text})
                    handled_specific_event = True
                
                elif code in [355, 655] and isinstance(parameters, list) and len(parameters) > 0 and isinstance(parameters[0], str): 
                    script_content_full = parameters[0]
                    quoted_texts = extract_quoted_strings(script_content_full)
                    if quoted_texts:
                        for i_q, q_text in enumerate(quoted_texts): # Process each quoted string
                             if is_valid_string(q_text) and not looks_like_code_or_path(q_text):
                                found_strings.append({"path": ".".join(parameter_path_base + ["0", f"script_content_q{i_q}"]), "original": q_text})
                    handled_specific_event = True

                if isinstance(parameters, list) and not handled_specific_event:
                    for param_idx, param_val in enumerate(parameters):
                        if isinstance(param_val, str) and is_valid_string(param_val) and \
                           not looks_like_code_or_path(param_val) and \
                           len(param_val) >= MIN_STRING_LENGTH_GENERIC and not param_val.isdigit():
                            found_strings.append({"path": ".".join(parameter_path_base + [str(param_idx)]), "original": param_val})
                        elif isinstance(param_val, (dict,list)):
                            extract_text_from_general_structure(param_val, parameter_path_base + [str(param_idx)], found_strings)


def extract_text_from_database_object_array(data_array, found_strings):
    if not isinstance(data_array, list):
        return

    for i, item in enumerate(data_array):
        if item is None or not isinstance(item, dict):
            continue
        base_path = [str(i)]
        for key in DATABASE_KEYS_TO_EXTRACT:
            if "." in key: continue
            original_value = item.get(key)

            if key == 'note':
                if is_valid_string(original_value):
                    quoted_texts = extract_quoted_strings(original_value)
                    if quoted_texts:
                        for i_q, q_text in enumerate(quoted_texts): # Process each quoted string
                            if is_valid_string(q_text) and not looks_like_code_or_path(q_text):
                                found_strings.append({"path": ".".join(base_path + [key, f"q_{i_q}"]), "original": q_text})
                    elif not looks_like_code_or_path(original_value):
                        found_strings.append({"path": ".".join(base_path + [key]), "original": original_value})
            elif is_valid_string(original_value) and not looks_like_code_or_path(original_value):
                found_strings.append({"path": ".".join(base_path + [key]), "original": original_value})
        
        for key, value in item.items():
            if key not in DATABASE_KEYS_TO_EXTRACT and isinstance(value, (dict,list)):
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
        for i, item_val in enumerate(element): 
            new_path_parts = current_path_parts + [str(i)]
            extract_text_from_gallery_list_recursive(item_val, new_path_parts, found_strings)

def extract_text_from_rubi_list_recursive(element, current_path_parts, found_strings):
    if isinstance(element, dict):
        for key, value in element.items():
            new_path_parts = current_path_parts + [key]
            if key in RUBI_TEXT_KEYS and is_valid_string(value) and not looks_like_code_or_path(value): 
                found_strings.append({"path": ".".join(new_path_parts), "original": value})
            elif isinstance(value, (dict, list)):
                extract_text_from_rubi_list_recursive(value, new_path_parts, found_strings)
    elif isinstance(element, list):
        for i, item_val in enumerate(element): 
            new_path_parts = current_path_parts + [str(i)]
            extract_text_from_rubi_list_recursive(item_val, new_path_parts, found_strings)

def extract_text_from_general_structure(data, base_path_parts, found_strings):
    if isinstance(data, dict):
        for key, value in data.items():
            is_potential_text_key = any(key.lower().endswith(suffix) for suffix in ["name", "title", "text", "desc", "note", "message", "profile", "scenario"])
            if is_potential_text_key and is_valid_string(value) and not looks_like_code_or_path(value):
                found_strings.append({"path": ".".join(base_path_parts + [key]), "original": value})
            elif isinstance(value, str) and is_valid_string(value) and not looks_like_code_or_path(value) and len(value) >= 10: 
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
        game_title = json_content.get("gameTitle")
        if is_valid_string(game_title) and not looks_like_code_or_path(game_title):
            found_strings.append({'path': 'gameTitle', 'original': game_title})
        
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
        
        for key in DATABASE_KEYS_TO_EXTRACT: 
            if "." in key: continue
            text_val = json_content.get(key)
            if is_valid_string(text_val) and not looks_like_code_or_path(text_val):
                found_strings.append({"path": key, "original": text_val})
        
        extract_text_from_general_structure(json_content, [], found_strings)


    elif isinstance(json_content, list): 
        extract_text_from_database_object_array(json_content, found_strings)
    
    elif isinstance(json_content, dict): 
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
            with open(file_path, 'r', encoding='utf-8-sig') as f: 
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
