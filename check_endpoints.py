import requests
import json

response = requests.get("http://localhost:8000/openapi.json")
openapi = response.json()

print("Verfügbare API Endpoints:")
for path in openapi["paths"].keys():
    if "/api/v1" in path:
        print(f"  {path}")
