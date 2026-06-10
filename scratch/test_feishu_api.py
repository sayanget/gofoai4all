import os
import json
import requests

def test_feishu():
    app_id = "cli_a9fc1c1c0bb8dbcb"
    app_secret = "XeStEZgDlQQUnUU93w1d3emYSdMSfiq6"
    
    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(token_url, json={"app_id": app_id, "app_secret": app_secret})
    if res.status_code != 200:
        print("Failed to get token", res.text)
        return
    token = res.json().get("tenant_access_token")
    print("Token length:", len(token))
    
    # KMqBsrOsAhkepOtmYhrcSM23nqh?sheet=307Usp
    spreadsheet_token = "KMqBsrOsAhkepOtmYhrcSM23nqh"
    sheet_id = "307Usp"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    # GET https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/:spreadsheetToken/values/:range
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_id}"
    res = requests.get(url, headers=headers)
    print("Status:", res.status_code)
    try:
        data = res.json()
        print("Keys:", data.keys())
        if 'data' in data:
            print("Data keys:", data['data'].keys())
            if 'valueRange' in data['data']:
                values = data['data']['valueRange'].get('values', [])
                print("Rows fetched:", len(values))
                if values:
                    print("Header row:", values[0])
                    if len(values) > 1:
                        print("First data row:", values[1])
        else:
            print("Response:", data)
    except Exception as e:
        print("Error parsing json:", e)

test_feishu()
