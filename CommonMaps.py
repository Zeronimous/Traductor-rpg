import argparse
import copy
import json
import os

def main():
    parser = argparse.ArgumentParser(description="Extract text from CommonMap JSON files.")
    parser.add_argument('--input_folder', default='comaps', help="Input folder containing JSON files.")
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

            extracted_texts = []

            if 'events' in data and data['events'] is not None: # Check if 'events' is not None
                for event in data['events']:
                    if event is None: # Skip if event itself is None
                        continue
                    if 'pages' in event:
                        for page in event['pages']:
                            if 'list' in page:
                                for item in page['list']:
                                    if 'code' in item:
                                        if item['code'] == 401: # Plain text
                                            if 'parameters' in item and len(item['parameters']) > 0:
                                                text = item['parameters'][0]
                                                if text and str(text).strip(): # Ensure text is not empty or just whitespace
                                                    extracted_texts.append(str(text))
                                        elif item['code'] == 102: # Choices
                                            if 'parameters' in item and len(item['parameters']) > 0 and item['parameters'][0]:
                                                for choice in item['parameters'][0]:
                                                    if choice and str(choice).strip(): # Ensure choice is not empty
                                                        extracted_texts.append(str(choice))
                                        elif item['code'] == 402: # Choice answer
                                             if 'parameters' in item and len(item['parameters']) == 2:
                                                text = item['parameters'][1]
                                                if text and str(text).strip(): # Ensure text is not empty
                                                    extracted_texts.append(str(text))
            
            if extracted_texts:
                try:
                    with open(output_filepath, 'w', encoding='utf-8') as f_out:
                        for i, text in enumerate(extracted_texts):
                            # Write text as is, preserving original newlines
                            f_out.write(f"{i+1}) {text}\n")
                    print(f"Processed {input_filepath} -> {output_filepath}")
                except Exception as e:
                    print(f"Error writing to {output_filepath}: {e}")
            else:
                print(f"No text extracted from {input_filepath}. Output file not created.")


if __name__ == '__main__':
    main()
