import requests
import os
import json
from datetime import datetime

def test_dhan():
    client_id = "1109467957"
    access_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzcwNzI5NzMxLCJpYXQiOjE3NzA2NDMzMzEsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA5NDY3OTU3In0.ywpR-oiXNjHM_KlFy3WZqx7caIONL2C_8L3MTw-7nmULVSO0IevoM9xLMeYCXV_nxMLG_KqZ-_0xp1tRQ0nQ8w"
    
    url = "https://api.dhan.co/v2/charts/historical"
    
    headers = {
        'client-id': client_id,
        'access-token': access_token,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "securityId": "2885", # RELIANCE
        "exchangeSegment": "NSE_EQ",
        "instrument": "EQUITY",
        "expiryCode": 0,
        "fromDate": "2026-02-01",
        "toDate": "2026-02-05"
    }
    
    print(f"Requesting: {url}")
    print(f"Payload: {json.dumps(payload)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_dhan()
