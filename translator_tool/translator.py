import os
import json
# Removed: from googletrans import Translator, LANGUAGES
import math
import copy
import time
# Removed: import asyncio
import translators as ts # Added translators import

# --- Configuration ---
M = 50 # Max line length for formatted text output. Used by the print_neatly function.
ETR_UPDATE_INTERVAL = 5 # Update Estimated Time Remaining (ETR) every N strings processed.
ETR_MIN_ITEMS_FOR_ETR_DISPLAY = 1 # Minimum number of items that need to be processed before ETR is displayed for the first time.
MAX_CHARS_FOR_LOG_SNIPPET = 50 # Max characters for log snippets
REQUEST_DELAY = 0.1 # Seconds to delay each translation request (used in translate_text)

# --- Configuration for Text Identification ---
# List of common JSON keys that usually contain translatable text in RPG Maker and similar game JSON structures.
COMMON_TEXT_KEYS = [
    "message", "text", "description", "name", "profile", "note",
    "title", "subtitle", "displayName", "nickname", "scenario",
]
# List of JSON keys that typically do NOT contain translatable text.
# These are often internal identifiers, filenames, or script-related data.
EXCLUDED_KEYS = [
    "script", "command", "code", "bgm", "se", "animationId", "tilesetId",
    "bgmName", "bgsName", "meName", "actorId", "classId", "weaponId", "armorId",
    "enemyId", "troopId", "itemId", "skillId", "stateId", "mapId", "eventId",
    "variableId", "switchId", "vehicleId", "characterName", "faceName",
    "battlerName", "title1Name", "title2Name", "actionButton", "trigger",
    "image", "iconIndex", "bgImage", "picture", "bgPicture", "fgPicture",
    "mapName", # Typically an internal map name; 'displayName' is preferred for translatable map names.
]
# Minimum string length for a value to be considered for translation,
# unless its key is in COMMON_TEXT_KEYS.
MIN_STRING_LENGTH = 4
# Minimum string length for values associated with COMMON_TEXT_KEYS.
# Allows for shorter common terms like "Yes", "No", "OK".
MIN_STRING_LENGTH_FOR_COMMON_KEYS = 2

def find_json_files(input_dir):
    """
    Recursively finds all JSON files (ending with .json) in the given input directory.

    Args:
        input_dir (str): The directory path to search for JSON files.

    Returns:
        list[str]: A list of full file paths to the found JSON files.
    """
    json_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith(".json"):
                json_files.append(os.path.join(root, file))
    return json_files

def looks_like_code_or_path(s):
    """
    Heuristic function to determine if a string looks like code, a file path, or an internal ID.
    Helps in excluding non-translatable strings.

    Args:
        s (str): The string to check.

    Returns:
        bool: True if the string matches any of the heuristics for code/path, False otherwise.
    """
    if not isinstance(s, str):
        return False
    # Check for common file extensions or path indicators
    if ".png" in s or ".jpg" in s or ".ogg" in s or ".mp3" in s or \
       "img/" in s or "audio/" in s or "data/" in s or "js/" in s:
        return True
    # Check for RPG Maker variable syntax (e.g., variable[10])
    if "variable[" in s and "]" in s:
        return True
    # Check for common script/variable prefixes or special characters
    if "$" in s and s.strip().startswith("$"): # e.g., $gameVariables
        return True
    # Check for RPG Maker style tags (e.g., <WordWrap>)
    if s.strip().startswith("<") and s.strip().endswith(">"):
        return True
    # Check for URLs
    if "http://" in s or "https://" in s:
        return True
    # Check for snake_case strings without spaces (often internal IDs)
    if "_" in s and not " " in s:
        if all(c.isalnum() or c == '_' for c in s): # Ensure it's predominantly alphanumeric with underscores
            return True
    # (Further heuristics for camelCase or PascalCase could be added but are currently disabled
    # to avoid being too aggressive and excluding valid text).
    return False

def extract_translatable_strings_recursive(data, current_path_parts, found_strings):
    """
    Recursively traverses JSON data (dictionaries and lists) to identify and extract
    potentially translatable strings based on defined heuristics.

    Args:
        data (dict | list): The current piece of JSON data to traverse.
        current_path_parts (list[str]): A list of keys/indices representing the path to the current data.
        found_strings (list[dict]): A list where found translatable strings are appended.
                                     Each item is a dict: {"path": "dot.separated.path", "original": "string"}.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            new_path_parts = current_path_parts + [str(key)] # Append current key to path
            
            # Skip keys that are explicitly excluded
            if key in EXCLUDED_KEYS:
                continue

            if isinstance(value, str):
                is_common_key = key in COMMON_TEXT_KEYS
                min_len = MIN_STRING_LENGTH_FOR_COMMON_KEYS if is_common_key else MIN_STRING_LENGTH
                
                # Specific handling for RPG Maker event command parameters (often in 'parameters' list)
                # Example: 'parameters' key for event code 401 (Show Text)
                if key == "parameters" and isinstance(value, list) and len(value) > 0 and isinstance(value[0], str):
                    # Path for the first parameter string
                    param_path_parts = new_path_parts + ["0"] 
                    text_to_check = value[0]
                    if len(text_to_check.strip()) >= MIN_STRING_LENGTH_FOR_COMMON_KEYS and not looks_like_code_or_path(text_to_check):
                         found_strings.append({"path": ".".join(param_path_parts), "original": text_to_check})
                         # Check subsequent parameters in the same list if they are also strings
                         for i, sub_param in enumerate(value[1:]):
                            if isinstance(sub_param, str) and len(sub_param.strip()) >= MIN_STRING_LENGTH and not looks_like_code_or_path(sub_param):
                                found_strings.append({"path": ".".join(new_path_parts + [str(i+1)]), "original": sub_param})
                # General handling for strings based on common keys or length/content heuristics
                elif is_common_key:
                    if len(value.strip()) >= min_len and not looks_like_code_or_path(value):
                        found_strings.append({"path": ".".join(new_path_parts), "original": value})
                elif len(value.strip()) >= MIN_STRING_LENGTH and not looks_like_code_or_path(value) and not value.isdigit():
                    # Avoid keys that typically point to filenames or internal names but aren't in EXCLUDED_KEYS
                    if not (key.lower().endswith("file") or key.lower().endswith("path") or \
                            (key.lower().endswith("name") and key.lower() != "displayname" and key.lower() != "nickname")):
                        found_strings.append({"path": ".".join(new_path_parts), "original": value})

            # If value is a dictionary or list, recurse
            elif isinstance(value, (dict, list)):
                extract_translatable_strings_recursive(value, new_path_parts, found_strings)

    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_path_parts = current_path_parts + [str(i)] # Append current index to path
            
            if isinstance(item, str):
                # Handle strings found directly in lists
                parent_key = current_path_parts[-1] if current_path_parts else ""
                if len(item.strip()) >= MIN_STRING_LENGTH and not looks_like_code_or_path(item) and not item.isdigit():
                    # Avoid strings in lists under excluded parent keys (e.g., "scripts": ["line1", "line2"])
                    if parent_key not in EXCLUDED_KEYS and parent_key != "scripts":
                        found_strings.append({"path": ".".join(new_path_parts), "original": item})
            # If item is a dictionary or list, recurse
            elif isinstance(item, (dict, list)):
                # Special handling for RPG Maker event command lists
                # Check if current list is part of an event's 'pages' and 'list' structure
                is_event_command_list = "list" in ".".join(current_path_parts) and "pages" in ".".join(current_path_parts)
                if isinstance(item, dict) and is_event_command_list and "code" in item:
                    code = item.get("code")
                    parameters = item.get("parameters")
                    # Specifically handle event code 401 (Show Text)
                    if code == 401 and isinstance(parameters, list) and len(parameters) > 0 and isinstance(parameters[0], str):
                        text_val = parameters[0]
                        if len(text_val.strip()) >= MIN_STRING_LENGTH_FOR_COMMON_KEYS and not looks_like_code_or_path(text_val):
                            param_path = new_path_parts + ["parameters", "0"]
                            # Avoid duplicates if already handled by the generic 'parameters' list check above.
                            # This check is a safeguard; ideally, the logic paths are distinct.
                            is_duplicate = False
                            for fs in found_strings:
                                if fs["path"] == ".".join(param_path) and fs["original"] == text_val:
                                    is_duplicate = True
                                    break
                            if not is_duplicate:
                                found_strings.append({"path": ".".join(param_path), "original": text_val})
                            
                            # Create a temporary item copy without 'parameters' to avoid re-processing them in the subsequent generic recursion.
                            temp_item = item.copy()
                            temp_item.pop("parameters", None) 
                            extract_translatable_strings_recursive(temp_item, new_path_parts, found_strings)
                            continue # Skip default recursion for this item as its relevant part is handled.
                
                # Default recursion for other list items (dicts or lists)
                extract_translatable_strings_recursive(item, new_path_parts, found_strings)

def parse_and_identify_text(file_path):
    """
    Parses a JSON file and identifies all translatable texts within it.

    Args:
        file_path (str): The path to the JSON file.

    Returns:
        list[dict]: A list of dictionaries, each representing a translatable text,
                    containing its 'path' in the JSON and 'original' string.
                    Returns an empty list if errors occur or no texts are found.
    """
    translatable_texts = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f) # Load JSON data from file
        
        extracted_data_with_paths = []
        # Start recursive extraction from the root of the JSON data
        extract_translatable_strings_recursive(data, [], extracted_data_with_paths)
        
        # Remove duplicates that might arise from different extraction paths finding the same text
        unique_texts = []
        seen_tuples = set() # Set to keep track of (path, original_text) tuples for uniqueness
        for text_info in extracted_data_with_paths:
            identity_tuple = (text_info["path"], text_info["original"])
            if identity_tuple not in seen_tuples:
                unique_texts.append(text_info)
                seen_tuples.add(identity_tuple)
        translatable_texts = unique_texts

        if translatable_texts:
            print(f"Found {len(translatable_texts)} potential texts in {os.path.basename(file_path)}.")
    except FileNotFoundError:
        print(f"Error: File not found {file_path}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred while parsing {file_path}: {e}")
    return translatable_texts

# Function to translate text using the 'translators' library
def translate_text(text_to_translate, src_language='en', dest_language='es'):
    """
    Translates a given text string using the 'translators' library (defaulting to Bing).
    """
    if not text_to_translate or not isinstance(text_to_translate, str) or text_to_translate.isspace():
        return text_to_translate

    try:
        # Using 'bing' as the translator. Others like 'google', 'mymemory', 'yandex' could also be used.
        # The 'translators' library handles fetching the translation.
        # Using REQUEST_DELAY for sleep_seconds to be polite to the API.
        # Note: time.sleep() is implicitly handled by the library if sleep_seconds > 0.
        # However, the problem description asks for REQUEST_DELAY to be passed to sleep_seconds.
        # The library's own time.sleep might be sufficient, but adhering to prompt.
        
        # The library itself calls time.sleep(sleep_seconds) if sleep_seconds > 0.
        # So, explicit time.sleep(REQUEST_DELAY) before the call is redundant if REQUEST_DELAY is also passed as sleep_seconds.
        # I will remove the explicit time.sleep() here as it's handled by the library via sleep_seconds.

        translated_str = ts.translate_text(
            query_text=text_to_translate,
            translator='bing', 
            from_language=src_language,
            to_language='es-ES', # Changed from 'es' for Bing
            sleep_seconds=REQUEST_DELAY, # Pass the delay here
            timeout=10.0 # Adding a timeout for robustness
        )
        
        if translated_str:
            return translated_str
        else:
            # Handle cases where translation might return None or empty string
            # without raising an exception.
            print(f"Warning: Translation for '{text_to_translate[:MAX_CHARS_FOR_LOG_SNIPPET]}...' resulted in empty text using 'bing'. Original text kept.")
            return text_to_translate
            
    except Exception as e:
        print(f"Error during translation of '{text_to_translate[:MAX_CHARS_FOR_LOG_SNIPPET]}...' using 'bing': {e}. Original text kept.")
        return text_to_translate

def print_neatly(text, M_val):
    """
    Formats a given text string into multiple lines using a dynamic programming approach
    for optimal line wrapping (word wrapping). Aims to minimize the "badness" of lines,
    where badness is typically (M - line_length)^3.

    Args:
        text (str): The text to be formatted.
        M_val (int): The maximum allowed line length.

    Returns:
        str: The formatted text with newlines ('\n') separating the lines.
             Returns the original text if it's empty, whitespace-only, or if formatting fails.
    """
    # Return original text if it's empty, whitespace-only, or otherwise unsuitable for formatting
    if not text or not isinstance(text, str) or text.isspace():
        return text 
    
    words = text.split(' ')
    n = len(words)
    if n == 0: # If there are no words, return an empty string
        return ""

    # min_penalty[j] stores the minimum penalty for formatting the first j words (words[0...j-1]).
    min_penalty = [float('inf')] * (n + 1)
    # break_points[j] stores the index k (0-indexed) such that the last line of the optimal
    # layout for the first j words consists of words[k...j-1].
    break_points = [-1] * (n + 1) 
    min_penalty[0] = 0 # Base case: penalty for zero words is zero.

    # Dynamic programming loop to calculate minimum penalties and break points.
    # j represents the number of words considered so far (words[0] to words[j-1]).
    for j in range(1, n + 1):
        # i represents the starting word (0-indexed) of the current line being considered.
        # The current line would be words[i-1...j-1].
        for i in range(1, j + 1):
            line_words = words[i-1:j] # Words in the current potential line
            line_length = len(' '.join(line_words)) # Length of these words joined by single spaces
            
            cost = M_val - line_length # Remaining space on the line
            current_line_penalty = 0
            
            if cost < 0: # Line is too long
                current_line_penalty = float('inf')
            elif j == n and cost >=0: # Last line of the entire text, no penalty if it fits
                current_line_penalty = 0
            else: # Regular line, penalty is (remaining space)^3
                current_line_penalty = cost ** 3 
            
            # If the penalty for the previous words (up to words[i-2]) plus the current line's penalty
            # is less than the currently known minimum penalty for words[0...j-1], update it.
            if min_penalty[i-1] != float('inf') and (min_penalty[i-1] + current_line_penalty < min_penalty[j]):
                min_penalty[j] = min_penalty[i-1] + current_line_penalty
                break_points[j] = i - 1 # Store 0-indexed start of this last line

    # If min_penalty[n] is still infinity, no valid layout was found (e.g., a single word exceeds M_val).
    if min_penalty[n] == float('inf'):
        # Fallback: if the original text is too long, try a simpler greedy split.
        if len(text) > M_val :
            result_lines_simple = []
            current_line = []
            current_length = 0
            for word in words:
                if current_length + len(word) + len(current_line) > M_val: # Check if adding word exceeds M
                    if current_line: # If there's content in current_line, add it to results
                        result_lines_simple.append(" ".join(current_line))
                    current_line = [word] # Start new line with current word
                    current_length = len(word)
                else:
                    current_line.append(word)
                    current_length += len(word)
            if current_line: # Add any remaining part
                result_lines_simple.append(" ".join(current_line))
            return "\n".join(result_lines_simple)
        return text # Otherwise, return the original text if it's short or cannot be formatted.

    # Reconstruct the lines from break_points.
    result_lines = []
    current_word_idx = n # Start from the end (n words total)
    while current_word_idx > 0:
        start_of_line_idx = break_points[current_word_idx] # Get the start index of the current line
        
        # Sanity check for break_points logic; this condition should ideally not be met.
        if start_of_line_idx >= current_word_idx :
            line = ' '.join(words[0:current_word_idx]) # Fallback: take all remaining words
            result_lines.insert(0, line)
            break 
        
        line = ' '.join(words[start_of_line_idx:current_word_idx]) # Construct the line
        result_lines.insert(0, line) # Add to the beginning of result_lines
        current_word_idx = start_of_line_idx # Move to the start of the previous line
    
    return "\n".join(result_lines) # Join all formatted lines with newlines

def update_json_value_by_path(json_data, path_str, new_value):
    """
    Updates a value within a nested JSON structure (represented as Python dicts/lists)
    at a location specified by a dot-separated path string.

    Args:
        json_data (dict | list): The JSON data to update.
        path_str (str): The dot-separated path (e.g., "events.0.pages.0.list.1.parameters.0").
        new_value (any): The new value to set at the specified path.

    Returns:
        bool: True if the update was successful, False otherwise.
    """
    path_segments = path_str.split('.')
    current_element = json_data
    try:
        for i, segment in enumerate(path_segments):
            is_last_segment = (i == len(path_segments) - 1)
            
            if is_last_segment: # If this is the last segment, we need to set the value
                if isinstance(current_element, list):
                    if segment.isdigit(): # List indices must be digits
                        idx = int(segment)
                        if 0 <= idx < len(current_element):
                            current_element[idx] = new_value
                        else:
                            print(f"\nError updating JSON at path '{path_str}': Index {idx} out of bounds for list segment '{segment}'.")
                            return False
                    else:
                        print(f"\nError updating JSON at path '{path_str}': Segment '{segment}' is not a valid numeric index for a list.")
                        return False
                elif isinstance(current_element, dict):
                    current_element[segment] = new_value # Set value for dict key
                else:
                    # Cannot set value if current element is not a list or dict (e.g., a string or number)
                    print(f"\nError updating JSON at path '{path_str}': Cannot set value on non-dict/list element for segment '{segment}'. Current element type: {type(current_element)}")
                    return False
            else: # If not the last segment, navigate deeper
                if isinstance(current_element, list):
                    if segment.isdigit():
                        idx = int(segment)
                        if 0 <= idx < len(current_element):
                            current_element = current_element[idx]
                        else:
                            print(f"\nError navigating JSON at path '{path_str}': Index {idx} out of bounds for list segment '{segment}'.")
                            return False
                    else:
                        print(f"\nError navigating JSON at path '{path_str}': Segment '{segment}' is not a valid numeric index for list navigation.")
                        return False
                elif isinstance(current_element, dict):
                    if segment in current_element:
                        current_element = current_element[segment]
                    else:
                        print(f"\nError navigating JSON at path '{path_str}': Key '{segment}' not found in dictionary.")
                        return False
                else:
                    # Cannot navigate deeper if current element is not a list or dict
                    print(f"\nError navigating JSON at path '{path_str}': Cannot navigate non-dict/list element for segment '{segment}'. Current element type: {type(current_element)}")
                    return False
        return True # Update successful
    except (KeyError, IndexError, TypeError) as e: # Catch common errors during access
        print(f"\nError processing JSON path '{path_str}': {e}. Problematic segment: '{segment}'")
        return False
    except ValueError as e: # Catch errors from int(segment) if segment is not a valid integer string
        print(f"\nError processing JSON path '{path_str}': Invalid index format '{segment}'. {e}")
        return False

# Main execution block
if __name__ == "__main__":
    # Determine base directories for original and translated files
    # Assumes script is in 'translator_tool', and 'originales'/'traducidos' are siblings.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    originales_base_dir = os.path.join(script_dir, "originales")
    traducidos_base_dir = os.path.join(script_dir, "traducidos")
    
    # Check if the 'originales' directory exists
    if not os.path.isdir(originales_base_dir):
        print(f"Error: Directory '{originales_base_dir}' not found. Please create it and place JSON files inside.")
    else:
        # Step 1: Find all JSON files in the 'originales' directory
        json_file_paths = find_json_files(originales_base_dir)
        
        if json_file_paths:
            print(f"Found {len(json_file_paths)} JSON file(s) in '{originales_base_dir}'. Identifying texts...")
            
            # Step 2: Parse each JSON file and identify all translatable texts
            all_texts_to_process = []
            for file_path in json_file_paths:
                texts_in_file = parse_and_identify_text(file_path) 
                for text_info in texts_in_file:
                    text_info['file_path'] = file_path # Add file_path to each text_info for context
                    all_texts_to_process.append(text_info)
            
            if all_texts_to_process:
                print(f"\n--- Starting Translation & Formatting (English to Spanish, Max Line Length: {M}) ---")
                total_strings_to_process = len(all_texts_to_process)
                print(f"Found {total_strings_to_process} total potential translatable strings across all files.")
                
                processed_texts_data = [] # To store texts after translation and formatting
                translation_start_time = time.time() # For ETR calculation

                # Step 3: Translate and format each identified text
                for i, text_info in enumerate(all_texts_to_process):
                    items_processed_count = i # Number of items fully processed before this one
                    
                    # Display ETR at specified intervals
                    if items_processed_count >= ETR_MIN_ITEMS_FOR_ETR_DISPLAY and \
                       (items_processed_count % ETR_UPDATE_INTERVAL == 0 or \
                        items_processed_count < ETR_MIN_ITEMS_FOR_ETR_DISPLAY + ETR_UPDATE_INTERVAL -1 ) :
                        elapsed_time = time.time() - translation_start_time
                        if items_processed_count > 0: 
                            items_remaining = total_strings_to_process - items_processed_count
                            avg_time_per_item = elapsed_time / items_processed_count
                            etr_seconds = avg_time_per_item * items_remaining
                            etr_minutes = int(etr_seconds // 60)
                            etr_secs_part = int(etr_seconds % 60)
                            print(f"Progress: {items_processed_count}/{total_strings_to_process} strings processed. ETR: {etr_minutes:02d}m {etr_secs_part:02d}s.")

                    original_text = text_info['original']
                    translated_str = original_text # Default to original if issues occur
                    
                    current_item_number = i + 1 # For user-friendly 1-based counting
                    if not isinstance(original_text, str) or not original_text.strip():
                        print(f"Skipping item ({current_item_number}/{total_strings_to_process}): Path {text_info['path']} (Not a translatable string or empty)")
                    else:
                        print(f"Translating ({current_item_number}/{total_strings_to_process}): '{original_text.replace(chr(10), ' ')[:50]}...' (Path: {text_info['path']})")
                        translated_str = translate_text(original_text, dest_language='es') # Translate
                        
                        if original_text != translated_str :
                            print(f"  -> Translated: '{translated_str.replace(chr(10), ' ')[:50]}...'")
                        else:
                            print(f"  -> (Original text kept or translation failed)")
                    
                    # Format the translated (or original if translation failed) text
                    formatted_text = translated_str 
                    if isinstance(translated_str, str) and translated_str.strip():
                        formatted_text = print_neatly(translated_str, M) # Apply word wrapping

                    # Store all processed information
                    processed_info = {
                        'file_path': text_info['file_path'],
                        'path': text_info['path'],
                        'original': original_text,
                        'translated': translated_str,
                        'formatted': formatted_text # This is the text to be saved in the output JSON
                    }
                    processed_texts_data.append(processed_info)
                
                # Summary of translation and formatting phase
                total_processing_time = time.time() - translation_start_time
                print(f"\n--- Translation & Formatting Summary ---")
                print(f"Processed {len(processed_texts_data)} strings in {total_processing_time:.2f} seconds.")

                # Step 4: Save processed texts into new JSON files
                if processed_texts_data:
                    print(f"\n--- Saving Translated Files ---")
                    
                    # Group processed texts by their original file path
                    texts_by_file = {}
                    for item in processed_texts_data:
                        texts_by_file.setdefault(item['file_path'], []).append(item)

                    # Ensure base 'traducidos' directory exists
                    if not os.path.exists(traducidos_base_dir):
                        os.makedirs(traducidos_base_dir, exist_ok=True)

                    # Process each file: load original, update with formatted text, save to 'traducidos'
                    for original_file_path, items_in_file in texts_by_file.items():
                        try:
                            # Load the original JSON data
                            with open(original_file_path, 'r', encoding='utf-8') as f:
                                original_json_data = json.load(f)
                            
                            # Create a deep copy to modify; preserves original data structure for non-text parts
                            modified_json_data = copy.deepcopy(original_json_data)
                            
                            update_count = 0 # Total strings attempted to update in this file
                            successful_updates = 0 # Strings successfully updated
                            for item in items_in_file:
                                # Update the deep copied JSON data with the formatted text at the correct path
                                if update_json_value_by_path(modified_json_data, item['path'], item['formatted']):
                                    successful_updates +=1
                                update_count += 1
                            
                            # Determine the output file path in the 'traducidos' directory
                            # This preserves any subdirectory structure from 'originales'.
                            relative_path = os.path.relpath(original_file_path, start=originales_base_dir)
                            output_file_path = os.path.join(traducidos_base_dir, relative_path)
                            
                            # Ensure the specific output subdirectory exists
                            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
                            
                            # Save the modified JSON data to the new file
                            with open(output_file_path, 'w', encoding='utf-8') as f:
                                json.dump(modified_json_data, f, ensure_ascii=False, indent=2)
                            
                            print(f"Successfully saved translated file: {output_file_path} (updated {successful_updates}/{update_count} strings)")

                        except FileNotFoundError:
                            print(f"Error: Original file not found {original_file_path} during save operation.")
                        except json.JSONDecodeError:
                            print(f"Error: Could not decode JSON from {original_file_path} during save operation.")
                        except Exception as e:
                            print(f"An error occurred while processing or saving changes for {original_file_path}: {e}")
                else:
                    print("No processed texts to save.") # If no texts were processed (e.g. all empty)
            else:
                print("No translatable texts found to process across all files.") # If no texts were identified
        else:
            print(f"No JSON files found in '{originales_base_dir}'.") # If no JSON files were found initially
