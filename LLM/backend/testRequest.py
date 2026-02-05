# Programa que manda un curl RAW con un log del raw de una peticion a ollama y devuelve el resultado


import requests
import json
import sys
import time

def send_ollama_request(log_file_path):
    with open(log_file_path, 'r') as file:
        raw_data = file.read()

    url = "http://localhost:11404/v1/chat/completions"
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, data=raw_data)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: Received status code {response.status_code}")
        print(f"Response: {response.text}")
        return None
    
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python testRequest.py <log_file_path>")
        sys.exit(1)

    log_file_path = sys.argv[1]
    result = send_ollama_request(log_file_path)

    if result:
        print(json.dumps(result, indent=2))
