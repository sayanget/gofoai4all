import requests

api_key = "sk-gemini"
api_base = "http://localhost:8082/v1"
url_endpoint = f"{api_base.rstrip('/')}/models"
headers = {
    "Authorization": f"Bearer {api_key}"
}

try:
    resp = requests.get(url_endpoint, headers=headers, timeout=10)
    print("Status code:", resp.status_code)
    print("Models:", resp.json())
except Exception as e:
    print("Exception:", e)
