import json
import os
import argparse
import re # For parsing translated lines
import copy # For deepcopy

def main():
    parser = argparse.ArgumentParser(description="Inject translated texts back into JSON files.")
    parser.add_argument('--text_folder', default='Textos', help="Folder with translated .txt files.")
    parser.add_argument('--comaps_folder', default='comaps', help="Folder with original Map*.json files.")
    parser.add_argument('--otros_folder', default='Otros', help="Folder with other original .json files.")
    parser.add_argument('--output_folder', default='Traducidos', help="Folder to save translated .json files.")
    args = parser.parse_args()

    if not os.path.exists(args.output_folder):
        os.makedirs(args.output_folder)
        print(f"Created output folder: {args.output_folder}")

    for text_filename in os.listdir(args.text_folder):
        if not text_filename.endswith(".txt"):
            continue

        text_filepath = os.path.join(args.text_folder, text_filename)
        json_filename = os.path.splitext(text_filename)[0] + ".json"
        
        original_json_path = None
        source_folder = None

        path_in_comaps = os.path.join(args.comaps_folder, json_filename)
        path_in_otros = os.path.join(args.otros_folder, json_filename)

        # Define a list of filenames that are typically data files from 'Otros' and should prioritize that folder
        # This helps prevent using a similarly named (potentially empty) file from 'comaps'
        known_otros_data_files = [
            "Actors.json", "Items.json", "Armors.json", "Weapons.json", 
            "Enemies.json", "Skills.json", "States.json", "MapInfos.json",
            "Classes.json", "CommonEvents.json", "System.json", "Tilesets.json" # Added more common RPG Maker data files
        ]

        original_json_path = None
        source_folder = None

        if json_filename in known_otros_data_files:
            if os.path.exists(path_in_otros):
                print(f"Info: Prioritizing 'Otros' folder for known data file: {json_filename}.")
                original_json_path = path_in_otros
                source_folder = "otros"
            elif os.path.exists(path_in_comaps): # Fallback if not in Otros for some reason
                print(f"Warning: Known data file {json_filename} not found in 'Otros', checking 'comaps'.")
                original_json_path = path_in_comaps
                source_folder = "comaps"
            else:
                print(f"Error: Known data file {json_filename} not found in {args.otros_folder} or {args.comaps_folder}. Skipping {text_filename}.")
                continue
        else: # Standard priority for other files (e.g. MapXXX.json which are expected in comaps)
            if os.path.exists(path_in_comaps):
                original_json_path = path_in_comaps
                source_folder = "comaps"
            elif os.path.exists(path_in_otros):
                original_json_path = path_in_otros
                source_folder = "otros"
            else:
                print(f"Error: Original JSON file {json_filename} not found in {args.comaps_folder} or {args.otros_folder}. Skipping {text_filename}.")
                continue
        
        if original_json_path is None: # Should be caught by 'continue' statements above, but as a safeguard
            print(f"Error: Could not determine path for {json_filename}. Skipping.")
            continue

        # New parsing logic for multi-line entries
        parsed_translated_lines = []
        current_entry_text = None  # Holds the accumulating text for the current entry

        try:
            with open(text_filepath, 'r', encoding='utf-8') as f_text:
                for line_num, raw_line in enumerate(f_text):
                    line = raw_line.strip() # Process stripped lines

                    # Regex to match 'N) Text' or 'N)Text' (optional space after ')')
                    # Also captures the text part (group 2)
                    match = re.match(r'^(\d+)\)\s?(.*)', line)

                    if match:  # A new entry starts (e.g., "1) Text")
                        if current_entry_text is not None:
                            # If there was a previous entry, add its accumulated text
                            parsed_translated_lines.append(current_entry_text)
                        
                        # Start the new entry with the text part from this line
                        current_entry_text = match.group(2)
                    else:  # This line is a continuation of the current entry, or an unexpected line
                        if current_entry_text is not None:
                            # Append this line's content to the current entry
                            # An actual newline character is added to join the lines
                            current_entry_text += '\n' + line
                        else:
                            # This is a non-prefixed line without a preceding entry
                            # (e.g., at the beginning of the file, or after an empty entry that was just 'N)')
                            if line: # Only warn if the line has actual content
                                print(f"Warning: Line {line_num+1} in {text_filepath} ('{line}') is a non-prefixed line without an active entry. Skipping.")
                
                # After processing all lines, add the last accumulated entry if it exists
                if current_entry_text is not None:
                    parsed_translated_lines.append(current_entry_text)

        except Exception as e:
            print(f"Error reading or parsing {text_filepath}: {e}. Skipping file.")
            # Skip further processing for this file by continuing the outer loop
            # Ensure parsed_translated_lines is empty so subsequent checks handle this.
            parsed_translated_lines = [] # Clear any partial data
            # The 'continue' below will apply to the main loop over text_filename
        
        if not parsed_translated_lines:
            if os.path.exists(text_filepath): # Only print if file actually existed
                 print(f"No translated lines successfully parsed from {text_filepath}. Skipping.")
            # else: file not found error already handled by initial original_json_path check
            continue # Skip to the next text_filename

        translated_lines_iter = iter(parsed_translated_lines)
        
        try:
            with open(original_json_path, 'r', encoding='utf-8-sig') as f_json:
                data = json.load(f_json)
        except FileNotFoundError: # Should have been caught above, but as a safeguard
            print(f"Error: Original JSON file {original_json_path} disappeared. Skipping.")
            continue
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {original_json_path}. Skipping.")
            continue
        except Exception as e:
            print(f"An unexpected error occurred while reading {original_json_path}: {e}. Skipping.")
            continue

        # --- Injection Logic ---
        original_data_copy = json.loads(json.dumps(data)) # Deep copy for comparison if needed, or for checking non-empty
        
        # Helper to get next translation, advances iterator
        def get_next_translation():
            try:
                return next(translated_lines_iter)
            except StopIteration:
                # This will be raised if we run out of translated lines.
                # The calling code should handle this by not replacing if None.
                return None 

        if source_folder == "comaps":
            if 'events' in data and data['events'] is not None:
                for event in data['events']:
                    if event is None or 'pages' not in event:
                        continue
                    for page in event['pages']:
                        if 'list' not in page:
                            continue
                        for item in page['list']:
                            if 'code' not in item or 'parameters' not in item:
                                continue
                            
                            if item['code'] == 401: # Plain text
                                if 'parameters' in item and len(item['parameters']) > 0 and str(item['parameters'][0]).strip():
                                    translation = get_next_translation()
                                    if translation is not None:
                                        item['parameters'][0] = translation
                                    else:
                                        print(f"Warning: Ran out of translations for {json_filename} (code 401).")
                            elif item['code'] == 102: # Choices
                                if 'parameters' in item and len(item['parameters']) > 0 and item['parameters'][0]:
                                    new_choices = []
                                    for choice_idx, choice in enumerate(item['parameters'][0]):
                                        if str(choice).strip():
                                            translation = get_next_translation()
                                            if translation is not None:
                                                new_choices.append(translation)
                                            else:
                                                print(f"Warning: Ran out of translations for {json_filename} (code 102, choice {choice_idx}).")
                                                new_choices.append(choice) # Keep original
                                        else:
                                            new_choices.append(choice) # Keep original empty/whitespace choice
                                    item['parameters'][0] = new_choices
                            elif item['code'] == 402: # Choice answer
                                if 'parameters' in item and len(item['parameters']) == 2 and str(item['parameters'][1]).strip():
                                    translation = get_next_translation()
                                    if translation is not None:
                                        item['parameters'][1] = translation
                                    else:
                                        print(f"Warning: Ran out of translations for {json_filename} (code 402).")
        
        elif source_folder == "otros":
            # This global-like approach for the iterator is tricky with recursion.
            # It's better to pass the iterator and have the recursive function manage it.
            
            # Using a list to pass the iterator by reference effectively, so it can be advanced in recursion
            iter_wrapper = [translated_lines_iter] 

            def get_next_translation_from_wrapper(wrapper):
                try:
                    return next(wrapper[0])
                except StopIteration:
                    return None

            def inject_recursively(current_data_node, keys_to_extract, it_wrapper, is_array_translate_mode=False):
                if isinstance(current_data_node, dict):
                    for key, value in current_data_node.items():
                        if isinstance(value, (dict, list)):
                            inject_recursively(value, keys_to_extract, it_wrapper, is_array_translate_mode)
                        elif key in keys_to_extract and isinstance(value, str) and value.strip():
                            translation = get_next_translation_from_wrapper(it_wrapper)
                            if translation is not None:
                                current_data_node[key] = translation
                            else:
                                print(f"Warning: Ran out of translations for {json_filename} (key: {key}).")
                elif isinstance(current_data_node, list):
                    for i, item_in_list in enumerate(current_data_node):
                        if isinstance(item_in_list, (dict, list)):
                            inject_recursively(item_in_list, keys_to_extract, it_wrapper, is_array_translate_mode)
                        elif is_array_translate_mode and isinstance(item_in_list, str) and item_in_list.strip():
                            translation = get_next_translation_from_wrapper(it_wrapper)
                            if translation is not None:
                                current_data_node[i] = translation # Modify list item in place
                            else:
                                print(f"Warning: Ran out of translations for {json_filename} (array translate mode).")
            
            if json_filename.endswith("GalleryList.json"):
                inject_recursively(data, ['displayName', 'hint', 'stageText', 'sceneText', 'text'], iter_wrapper)
            elif json_filename.endswith("RubiList.json"):
                inject_recursively(data, [], iter_wrapper, is_array_translate_mode=True)
            else: # For other JSON files like Items, Armors, etc.
                if isinstance(data, list):
                    # Make a deep copy for modification; decisions based on original 'data' (which is original_data_list here)
                    original_data_list = data 
                    data_to_modify_list = copy.deepcopy(original_data_list)

                    for idx, d_item_to_modify in enumerate(data_to_modify_list):
                        # d_item_to_modify is from the deepcopy and will be modified.
                        # d_item_original is from the original loaded data and is used for decisions.
                        
                        if not isinstance(d_item_to_modify, dict): # If original was None or not dict, deepcopy might make it same, or it might be an issue if structure is inconsistent
                            # Check original item too for consistency in skipping
                            if idx < len(original_data_list) and (original_data_list[idx] is None or not isinstance(original_data_list[idx], dict)):
                                continue # Skip if original was also None or not a dict
                            # If original was dict but copy is not, or vice-versa, could be an issue, but generally deepcopy preserves this.
                            # For safety, primarily rely on original item for decision to skip.
                            if idx >= len(original_data_list) or original_data_list[idx] is None or not isinstance(original_data_list[idx], dict):
                                continue


                        d_item_original = original_data_list[idx] # Get corresponding original item

                        # Name field: Decision based on d_item_original
                        if d_item_original.get('name') and isinstance(d_item_original.get('name'), str) and d_item_original.get('name').strip():
                            translation = get_next_translation_from_wrapper(iter_wrapper)
                            if translation is not None:
                                d_item_to_modify['name'] = translation # Modify the item in the copied list
                            else:
                                print(f"Warning: Ran out of translations for {json_filename} (name for item ID {d_item_original.get('id', 'N/A')}).")
                        
                        # Description field: Decision based on d_item_original
                        if d_item_original.get('description') and isinstance(d_item_original.get('description'), str) and d_item_original.get('description').strip():
                            translation = get_next_translation_from_wrapper(iter_wrapper)
                            if translation is not None:
                                d_item_to_modify['description'] = translation # Modify the item in the copied list
                            else:
                                print(f"Warning: Ran out of translations for {json_filename} (description for item ID {d_item_original.get('id', 'N/A')}).")

                        # Profile field: Decision based on d_item_original
                        if d_item_original.get('profile') and isinstance(d_item_original.get('profile'), str) and d_item_original.get('profile').strip():
                            translation = get_next_translation_from_wrapper(iter_wrapper)
                            if translation is not None:
                                d_item_to_modify['profile'] = translation # Modify the item in the copied list
                            else:
                                print(f"Warning: Ran out of translations for {json_filename} (profile for item ID {d_item_original.get('id', 'N/A')}).")

                        # Message fields (message1 to message4): Decision based on d_item_original
                        for m_idx in range(1, 5):
                            msg_key = f'message{m_idx}'
                            if d_item_original.get(msg_key) and isinstance(d_item_original.get(msg_key), str) and d_item_original.get(msg_key).strip():
                                translation = get_next_translation_from_wrapper(iter_wrapper)
                                if translation is not None:
                                    d_item_to_modify[msg_key] = translation # Modify the item in the copied list
                                else:
                                    print(f"Warning: Ran out of translations for {json_filename} ({msg_key} for item ID {d_item_original.get('id', 'N/A')}).")
                    
                    data = data_to_modify_list # Important: ensure 'data' which is saved later, now points to the modified list

                elif data is None and (json_filename.endswith("Items.json") # etc.
                                     or json_filename.endswith("Armors.json")
                                     or json_filename.endswith("Weapons.json")
                                     or json_filename.endswith("Enemies.json")
                                     or json_filename.endswith("Skills.json")
                                     or json_filename.endswith("States.json")
                                     or json_filename.endswith("MapInfos.json")):
                    pass # No data to inject into, or data is not a list as expected for these file types

        # Check if there are any remaining unused translations
        remaining_translations = list(iter_wrapper[0] if source_folder == "otros" else translated_lines_iter)
        if remaining_translations and any(s is not None and s.strip() for s in remaining_translations): # Check if any non-empty string remains
            print(f"Warning: Unused translations remaining for {json_filename}: {len(remaining_translations)} lines. This might indicate a mismatch.")


        # Save translated JSON
        output_json_path = os.path.join(args.output_folder, json_filename)
        try:
            with open(output_json_path, 'w', encoding='utf-8') as f_out_json:
                json.dump(data, f_out_json, indent=4, ensure_ascii=False)
            print(f"Successfully processed {text_filename} -> {output_json_path}")
        except Exception as e:
            print(f"Error writing translated JSON to {output_json_path}: {e}")

if __name__ == '__main__':
    main()
