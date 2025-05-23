import os
import json
import re
import math 
import copy # Added copy import

# --- Configuration ---
M_TEXT_WRAP_LINE_LENGTH = 50 # Max line length for formatted text output.

# Copied from translator.py 
def print_neatly(text, M_val):
    """
    Formats a given text string into multiple lines using a dynamic programming approach
    for optimal line wrapping (word wrapping). Aims to minimize the "badness" of lines,
    where badness is typically (M - line_length)^3.
    """
    if not text or not isinstance(text, str) or text.isspace():
        return text 
    
    words = text.split(' ')
    n = len(words)
    if n == 0: 
        return ""

    min_penalty = [float('inf')] * (n + 1)
    break_points = [-1] * (n + 1) 
    min_penalty[0] = 0

    for j in range(1, n + 1):
        for i in range(1, j + 1):
            line_words = words[i-1:j] 
            line_length = len(' '.join(line_words)) 
            
            cost = M_val - line_length 
            current_line_penalty = 0
            
            if cost < 0: 
                current_line_penalty = float('inf')
            elif j == n and cost >=0: 
                current_line_penalty = 0
            else: 
                current_line_penalty = cost ** 3 
            
            if min_penalty[i-1] != float('inf') and (min_penalty[i-1] + current_line_penalty < min_penalty[j]):
                min_penalty[j] = min_penalty[i-1] + current_line_penalty
                break_points[j] = i - 1 

    if min_penalty[n] == float('inf'):
        if len(text) > M_val :
            result_lines_simple = []
            current_line = []
            current_length = 0
            for word in words:
                if current_length + len(word) + len(current_line) > M_val: 
                    if current_line: 
                        result_lines_simple.append(" ".join(current_line))
                    current_line = [word] 
                    current_length = len(word)
                else:
                    current_line.append(word)
                    current_length += len(word)
            if current_line: 
                result_lines_simple.append(" ".join(current_line))
            return "\n".join(result_lines_simple)
        return text 

    result_lines = []
    current_word_idx = n 
    while current_word_idx > 0:
        start_of_line_idx = break_points[current_word_idx] 
        
        if start_of_line_idx >= current_word_idx :
            line = ' '.join(words[0:current_word_idx]) 
            result_lines.insert(0, line)
            break 
        
        line = ' '.join(words[start_of_line_idx:current_word_idx]) 
        result_lines.insert(0, line) 
        current_word_idx = start_of_line_idx 
    
    return "\n".join(result_lines)

# Robust update_json_value_by_path function
def update_json_value_by_path(json_data, path_str, new_value):
    """
    Updates a value within a nested JSON structure (represented as Python dicts/lists)
    at a location specified by a dot-separated path string.
    Returns True on success, False on failure.
    """
    path_segments = path_str.split('.')
    current_element = json_data
    try:
        for i, segment in enumerate(path_segments):
            is_last_segment = (i == len(path_segments) - 1)
            
            # Try to convert segment to int if it's a digit, for list index access
            try:
                idx = int(segment)
                is_segment_digit = True
            except ValueError:
                is_segment_digit = False

            if is_last_segment:
                if is_segment_digit and isinstance(current_element, list):
                    if 0 <= idx < len(current_element):
                        current_element[idx] = new_value
                    else:
                        # print(f"  Path error: Index {idx} out of bounds for segment '{segment}' at path '{path_str}'.")
                        return False
                elif not is_segment_digit and isinstance(current_element, dict):
                    current_element[segment] = new_value
                else:
                    # print(f"  Path error: Segment '{segment}' type mismatch or invalid for assignment at path '{path_str}'. Element type: {type(current_element)}")
                    return False
            else: # Navigate deeper
                if is_segment_digit and isinstance(current_element, list):
                    if 0 <= idx < len(current_element):
                        current_element = current_element[idx]
                    else:
                        # print(f"  Path error: Index {idx} out of bounds during navigation for segment '{segment}' at path '{path_str}'.")
                        return False
                elif not is_segment_digit and isinstance(current_element, dict):
                    if segment in current_element:
                        current_element = current_element[segment]
                    else:
                        # print(f"  Path error: Key '{segment}' not found during navigation at path '{path_str}'.")
                        return False
                else:
                    # print(f"  Path error: Segment '{segment}' type mismatch or invalid for navigation at path '{path_str}'. Element type: {type(current_element)}")
                    return False
        return True
    except Exception as e: # Catch any other unexpected errors during path traversal or assignment
        # print(f"  Unexpected error updating path '{path_str}': {e}")
        return False

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    textos_base_dir = os.path.join(script_dir, "textos")
    originales_base_dir = os.path.join(script_dir, "originales") 
    traducidos_base_dir = os.path.join(script_dir, "traducidos") 
    os.makedirs(traducidos_base_dir, exist_ok=True)

    if not os.path.isdir(textos_base_dir):
        print(f"Error: Text input directory '{textos_base_dir}' not found. Please run the extractor script first.")
        return

    all_extracted_data_for_injection = [] 

    print(f"Scanning for .txt and .jsonpaths files in '{os.path.relpath(textos_base_dir, script_dir)}'...")

    for filename in os.listdir(textos_base_dir):
        if filename.endswith(".txt"):
            base_name = os.path.splitext(filename)[0]
            txt_file_path = os.path.join(textos_base_dir, filename)
            jsonpaths_file_path = os.path.join(textos_base_dir, f"{base_name}.jsonpaths")

            print(f"\nProcessing pair: {filename} and {os.path.basename(jsonpaths_file_path)}")

            if not os.path.exists(jsonpaths_file_path):
                print(f"  Error: Paths file '{os.path.basename(jsonpaths_file_path)}' not found for '{filename}'. Skipping.")
                continue
            
            original_json_file_path = os.path.join(originales_base_dir, f"{base_name}.json")
            if not os.path.exists(original_json_file_path):
                print(f"  Error: Original JSON file '{os.path.basename(original_json_file_path)}' not found in '{originales_base_dir}'. Skipping pair for '{base_name}'.")
                continue

            try:
                with open(txt_file_path, 'r', encoding='utf-8') as f_txt:
                    raw_translated_lines = [line.strip() for line in f_txt if line.strip()] 
                
                translated_lines = []
                for line_num, line in enumerate(raw_translated_lines, 1):
                    stripped_line = re.sub(r"^\s*\d+\s*[\.\):]\s*", "", line).lstrip()
                    reverted_line = stripped_line.replace('[NEWLINE]', '\n')
                    translated_lines.append(reverted_line)

                with open(jsonpaths_file_path, 'r', encoding='utf-8') as f_paths:
                    paths_data = json.load(f_paths)
                
                if not isinstance(paths_data, list):
                    print(f"  Error: Paths file '{os.path.basename(jsonpaths_file_path)}' does not contain a valid list. Skipping.")
                    continue

                if len(translated_lines) != len(paths_data):
                    print(f"  Error: Mismatch between text lines ({len(translated_lines)}) and paths ({len(paths_data)}) for '{base_name}'. Skipping.")
                    print(f"    First few translated lines: {translated_lines[:3]}")
                    print(f"    First few paths: {paths_data[:3]}")
                    continue
                
                if not translated_lines: 
                    print(f"  Info: No text lines found in '{filename}' after stripping prefixes and empty lines. Skipping.")
                    continue

                print(f"  Successfully read and validated: {len(translated_lines)} entries for '{base_name}'.")
                all_extracted_data_for_injection.append({
                    'base_name': base_name,
                    'original_json_path': original_json_file_path, 
                    'translated_lines': translated_lines,
                    'paths_data': paths_data
                })

            except IOError as e:
                print(f"  Error reading files for '{base_name}': {e}")
            except json.JSONDecodeError as e:
                print(f"  Error decoding JSON from '{os.path.basename(jsonpaths_file_path)}': {e}")
            except Exception as e:
                print(f"  An unexpected error occurred processing '{base_name}': {e}")
    
    if not all_extracted_data_for_injection:
        print("\nNo file pairs were successfully read and validated for injection. Please check previous steps.") # Updated message
        return

    # --- Main Injection Loop ---
    print(f"\nStarting injection process for {len(all_extracted_data_for_injection)} file(s)...")
    
    for file_data in all_extracted_data_for_injection:
        base_name = file_data['base_name']
        original_json_path = file_data['original_json_path']
        translated_lines = file_data['translated_lines'] # Already have \n from earlier step
        paths_data = file_data['paths_data']

        print(f"  Injecting translations for: {base_name}.json")

        try:
            with open(original_json_path, 'r', encoding='utf-8') as f_orig:
                original_json_data = json.load(f_orig)
            
            modified_json_data = copy.deepcopy(original_json_data)
            
            update_success_count = 0
            update_failure_count = 0

            for i in range(len(translated_lines)):
                translated_text = translated_lines[i]
                json_path = paths_data[i]
                
                # Apply print_neatly formatting
                formatted_text = print_neatly(translated_text, M_TEXT_WRAP_LINE_LENGTH)
                
                if update_json_value_by_path(modified_json_data, json_path, formatted_text):
                    update_success_count += 1
                else:
                    update_failure_count += 1
                    print(f"    Warning: Failed to update path '{json_path}' in {base_name}.json") # Keep warning
            
            if update_failure_count > 0:
                print(f"    Finished injecting for {base_name}.json with {update_failure_count} path update failures.")
            else:
                print(f"    Successfully prepared all {update_success_count} updates for {base_name}.json.")

            output_file_path = os.path.join(traducidos_base_dir, f"{base_name}.json")
            # Ensure the specific output subdirectory exists (though traducidos_base_dir itself is created)
            # This is more relevant if base_name could contain subpaths, but here it's just a filename part.
            # os.makedirs(os.path.dirname(output_file_path), exist_ok=True) # Generally good practice but less critical here

            with open(output_file_path, 'w', encoding='utf-8') as f_out:
                json.dump(modified_json_data, f_out, ensure_ascii=False, indent=2)
            print(f"    -> Saved translated file: {os.path.relpath(output_file_path, script_dir)}") # Use relpath

        except FileNotFoundError:
            print(f"    Error: Original JSON file not found: {original_json_path}")
        except json.JSONDecodeError as e:
            print(f"    Error decoding original JSON from {original_json_path}: {e}")
        except IOError as e:
            print(f"    Error writing translated file for {base_name}.json: {e}")
        except Exception as e:
            print(f"    An unexpected error occurred processing {base_name}: {e}")

    print("\nInjection process complete.")


if __name__ == "__main__":
    main()
