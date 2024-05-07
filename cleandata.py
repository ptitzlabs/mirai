import json
import yaml

def load_messages(file_path):
    """ Load messages from a JSON file. """
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)['messages']

def process_messages(messages):
    """ Process messages to format them, arrange in threads, and merge consecutive messages from the same user. """
    # Mapping messages by id for quick lookup
    message_dict = {message['id']: message for message in messages}

    # Building threads
    threads = {}
    for message in messages:
        content = ''.join(entity['text'] for entity in message['text_entities'])
        if 'from' not in message: continue
        formatted_message = {
            "from": message["from"],
            "text": content
        }

        reply_id = message.get('reply_to_message_id')
        current_thread = threads.get(reply_id, []) if reply_id and reply_id in message_dict else threads.get(message['id'], [])

        if current_thread and current_thread[-1]['from'] == message['from']:
            # Merge text with the last message if from the same user
            current_thread[-1]['text'] += "\n\n" + content
        else:
            # Otherwise, add a new message to the thread
            current_thread.append(formatted_message)

        if reply_id and reply_id in message_dict:
            threads[reply_id] = current_thread
        else:
            threads[message['id']] = current_thread

    # Flatten threads into a list for YAML formatting
    formatted_threads = []
    for thread in threads.values():
        if len(thread) > 1:
            formatted_threads.extend(thread)
        else:
            formatted_threads.append(thread[0])

    return formatted_threads

def save_to_yaml(data, output_file):
    """ Save the processed data to a YAML file. """
    yaml_output = yaml.dump(data, allow_unicode=True)
    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(yaml_output)

# Example usage
file_path = 'result.json'  # Update this path
output_file = 'asile.yml'

# Load and process messages
messages = load_messages(file_path)
formatted_threads = process_messages(messages)

# Save formatted data to a file
save_to_yaml(formatted_threads, output_file)
print(f"Data has been formatted and saved to '{output_file}'")
