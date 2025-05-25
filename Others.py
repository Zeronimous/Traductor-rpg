import argparse
import json
import os

def main():
    parser = argparse.ArgumentParser(description="Extract text from JSON files in 'Otros' folder.")
    parser.add_argument('--input_folder', default='Otros', help="Input folder containing JSON files.")
    parser.add_argument('--output_folder', default='Textos', help="Output folder for extracted text files.")
    args = parser.parse_args()

    # Create input folder if it doesn't exist
    if not os.path.exists(args.input_folder):
        os.makedirs(args.input_folder)
        print(f"Created input folder: {args.input_folder}")

    # Create output folder if it doesn't exist
    if not os.path.exists(args.output_folder):
        os.makedirs(args.output_folder)
        print(f"Created output folder: {args.output_folder}")

    extracted_texts_global = [] # To be used by the recursive helper

    def extract_recursively(current_data, keys_to_extract, is_array_translate=False):
        nonlocal extracted_texts_global
        if isinstance(current_data, dict):
            for key, value in current_data.items():
                if isinstance(value, (dict, list)):
                    extract_recursively(value, keys_to_extract, is_array_translate)
                elif key in keys_to_extract and isinstance(value, str) and value.strip():
                    extracted_texts_global.append(value)
        elif isinstance(current_data, list):
            for item in current_data:
                if isinstance(item, (dict, list)):
                    extract_recursively(item, keys_to_extract, is_array_translate)
                elif is_array_translate and isinstance(item, str) and item.strip():
                    extracted_texts_global.append(item)

    for filename in os.listdir(args.input_folder):
        if filename.endswith(".json"):
            input_filepath = os.path.join(args.input_folder, filename)
            output_filename = os.path.splitext(filename)[0] + ".txt"
            output_filepath = os.path.join(args.output_folder, output_filename)

            if os.path.exists(output_filepath):
                print(f"Output file {output_filepath} already exists. Skipping.")
                continue

            try:
                with open(input_filepath, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
            except FileNotFoundError:
                print(f"Error: Input file {input_filepath} not found.")
                continue
            except json.JSONDecodeError:
                print(f"Error: Could not decode JSON from {input_filepath}.")
                continue
            except Exception as e:
                print(f"An unexpected error occurred while reading {input_filepath}: {e}")
                continue

            extracted_texts_global = [] # Reset for each file

            if filename.endswith("GalleryList.json"):
                extract_recursively(data, ['displayName', 'hint', 'stageText', 'sceneText', 'text'])
            elif filename.endswith("RubiList.json"):
                extract_recursively(data, [], is_array_translate=True)
            else: # For other JSON files like Items, Armors, etc.
                if isinstance(data, list): # Ensure data is a list for these files
                    for d in data:
                        if d is not None and isinstance(d, dict): # Ensure d is a dictionary
                            if d.get('name') and isinstance(d.get('name'), str) and d.get('name').strip():
                                extracted_texts_global.append(d.get('name'))
                            if d.get('description') and isinstance(d.get('description'), str) and d.get('description').strip():
                                extracted_texts_global.append(d.get('description'))
                            if d.get('profile') and isinstance(d.get('profile'), str) and d.get('profile').strip():
                                extracted_texts_global.append(d.get('profile'))
                            for m in range(1, 5): # message1 to message4
                                msg_key = f'message{m}'
                                if d.get(msg_key) and isinstance(d.get(msg_key), str) and d.get(msg_key).strip():
                                    extracted_texts_global.append(d.get(msg_key))
                elif data is None and (filename.endswith("Items.json") or filename.endswith("Armors.json") or filename.endswith("Weapons.json") or filename.endswith("Enemies.json") or filename.endswith("Skills.json") or filename.endswith("States.json") or filename.endswith("MapInfos.json")) :
                    print(f"Warning: {filename} is empty or null. No text extracted.")


            # Remove duplicates while preserving order for specific files
            if filename.endswith("GalleryList.json") or filename.endswith("RubiList.json"):
                seen = set()
                ordered_unique_texts = []
                for txt in extracted_texts_global:
                    if txt not in seen:
                        ordered_unique_texts.append(txt)
                        seen.add(txt)
                extracted_texts_global = ordered_unique_texts


            if extracted_texts_global:
                try:
                    with open(output_filepath, 'w', encoding='utf-8') as f_out:
                        for i, text in enumerate(extracted_texts_global):
                            # Replace newline characters with literal '\\n'
                            processed_text = text.replace('\n', '\\n')
                            f_out.write(f"{i+1}) {processed_text}\n")
                    print(f"Processed {input_filepath} -> {output_filepath}")
                except Exception as e:
                    print(f"Error writing to {output_filepath}: {e}")
            else:
                print(f"No text extracted from {input_filepath} (or content was null/empty). Output file not created.")

if __name__ == '__main__':
    main()
