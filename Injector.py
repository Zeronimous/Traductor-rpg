import json
import os
import argparse
import re # For parsing translated lines

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

        if os.path.exists(path_in_comaps):
            original_json_path = path_in_comaps
            source_folder = "comaps"
        elif os.path.exists(path_in_otros):
            original_json_path = path_in_otros
            source_folder = "otros"
        else:
            print(f"Error: Original JSON file {json_filename} not found in {args.comaps_folder} or {args.otros_folder}. Skipping {text_filename}.")
            continue

        # Load translated lines
        parsed_translated_lines = []
        try:
            with open(text_filepath, 'r', encoding='utf-8') as f_text:
                for line_num, line in enumerate(f_text):
                    match = re.match(r"^\d+\) (.*)", line)
                    if match:
                        parsed_translated_lines.append(match.group(1).strip())
                    else:
                        # Allow empty lines or lines that don't match the "N) " pattern
                        # These will effectively be skipped if they were empty during extraction
                        # or represent structural newlines from the original text that weren't meant to be separate entries.
                        # If the original extraction logic strictly created N) for every piece of text,
                        # then a mismatch here indicates a problem with the .txt file.
                        # For now, we'll be somewhat lenient and just append the stripped line if it's not empty,
                        # or an empty string if it is, to maintain the count if needed.
                        # However, the core logic relies on matching non-empty original texts.
                        stripped_line = line.strip()
                        # if stripped_line: # Only add if it's not an empty line after stripping N)
                        #    print(f"Warning: Line {line_num+1} in {text_filepath} ('{line}') does not match 'N) Text' format. Treating as raw text.")
                        #    parsed_translated_lines.append(stripped_line)
                        # else:
                        #    parsed_translated_lines.append("") # Keep index consistent for now
                        # For a stricter approach:
                        if line.strip(): # If the line has content but doesn't match
                             print(f"Warning: Line {line_num+1} in {text_filepath} ('{line}') does not match 'N) Text' format. Skipping this line.")
                        # parsed_translated_lines.append(None) # Or some other placeholder to indicate a skip
        except Exception as e:
            print(f"Error reading or parsing {text_filepath}: {e}. Skipping.")
            continue
        
        if not parsed_translated_lines:
            print(f"No translated lines found in {text_filepath}. Skipping.")
            continue

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
                    for d_item in data:
                        if d_item is None or not isinstance(d_item, dict): continue

                        if d_item.get('name') and isinstance(d_item.get('name'), str) and d_item.get('name').strip():
                            translation = get_next_translation_from_wrapper(iter_wrapper)
                            if translation is not None: d_item['name'] = translation
                            else: print(f"Warning: Ran out of translations for {json_filename} (name).")
                        
                        if d_item.get('description') and isinstance(d_item.get('description'), str) and d_item.get('description').strip():
                            translation = get_next_translation_from_wrapper(iter_wrapper)
                            if translation is not None: d_item['description'] = translation
                            else: print(f"Warning: Ran out of translations for {json_filename} (description).")

                        if d_item.get('profile') and isinstance(d_item.get('profile'), str) and d_item.get('profile').strip():
                            translation = get_next_translation_from_wrapper(iter_wrapper)
                            if translation is not None: d_item['profile'] = translation
                            else: print(f"Warning: Ran out of translations for {json_filename} (profile).")

                        for m_idx in range(1, 5): # message1 to message4
                            msg_key = f'message{m_idx}'
                            if d_item.get(msg_key) and isinstance(d_item.get(msg_key), str) and d_item.get(msg_key).strip():
                                translation = get_next_translation_from_wrapper(iter_wrapper)
                                if translation is not None: d_item[msg_key] = translation
                                else: print(f"Warning: Ran out of translations for {json_filename} ({msg_key}).")
                elif data is None and (json_filename.endswith("Items.json") # etc.
                                     or json_filename.endswith("Armors.json")
                                     or json_filename.endswith("Weapons.json")
                                     or json_filename.endswith("Enemies.json")
                                     or json_filename.endswith("Skills.json")
                                     or json_filename.endswith("States.json")
                                     or json_filename.endswith("MapInfos.json")):
                    pass # No data to inject into

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
