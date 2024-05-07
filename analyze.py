import yaml
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
import numpy as np
import pickle

def load_yaml_data(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def chunk_messages(messages, chunk_size=10):
    """Combine messages into chunks of a specified size."""
    chunks = []
    chunk_data = []  # to keep track of original messages for each chunk
    for i in range(0, len(messages), chunk_size):
        chunk_text = ' '.join(message['text'].strip() for message in messages[i:i + chunk_size])
        chunks.append(chunk_text)
        chunk_data.append([message['text'].strip() for message in messages[i:i + chunk_size]])
    return chunks, chunk_data

def is_question(text):
    return text.endswith('?')

def generate_embeddings(chunks):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(chunks)
    return embeddings, model

def cluster_messages(embeddings, num_clusters=50):
    kmeans = KMeans(n_clusters=num_clusters, random_state=0).fit(embeddings)
    return kmeans.labels_, kmeans.cluster_centers_

def extract_questions_from_chunks(chunk_data):
    """Extract questions from each chunk along with their original text."""
    questions = []
    for chunk in chunk_data:
        chunk_questions = [text for text in chunk if is_question(text) and len(text) > 100]
        questions.append(chunk_questions)
    return questions

def find_closest_questions(questions, embeddings, labels, centers):
    """Find closest questions to the cluster centers."""
    top_questions = {}
    for i in range(len(centers)):
        cluster_questions = [q for idx, ques in enumerate(questions) if labels[idx] == i for q in ques]
        if cluster_questions:
            cluster_embeddings = [embeddings[idx] for idx, ques in enumerate(questions) if labels[idx] == i for _ in ques]
            distances = np.linalg.norm(cluster_embeddings - centers[i], axis=1)
            closest_indices = np.argsort(distances)[:10]
            top_questions[i] = [cluster_questions[idx] for idx in closest_indices]
    return top_questions

def save_data(data, output_file):
    with open(output_file, 'wb') as file:
        pickle.dump(data, file)

# Example usage
file_path = 'asile.yml'
output_file = 'message_clusters.pkl'

# Load YAML data
messages = load_yaml_data(file_path)

# Chunk messages and process
chunks, chunk_data = chunk_messages(messages)
embeddings, model = generate_embeddings(chunks)
labels, centers = cluster_messages(embeddings)

# Extract questions from chunks
questions = extract_questions_from_chunks(chunk_data)

# Find top questions for each cluster
top_questions = find_closest_questions(questions, embeddings, labels, centers)

# Save data
save_data({'embeddings': embeddings, 'labels': labels, 'top_questions': top_questions}, output_file)

print("Top 10 Questions in Each Cluster (Over 100 Characters, Closest to Center):")
for cluster_id, question_list in top_questions.items():
    print(f"\nCluster {cluster_id}:")
    for question in question_list:
        print(f"  - {question}")
