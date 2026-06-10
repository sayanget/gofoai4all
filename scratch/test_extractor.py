import json
from tools.tms_extractor import TMSExtractor

def test_tms_feishu():
    with open("config/rules.json", "r", encoding="utf-8") as f:
        rules = json.load(f)
        
    url = rules["metrics"]["到达准点率"]["data_source"]
    print("Testing with URL:", url)
    
    extractor = TMSExtractor(url)
    result = extractor.extract()
    
    if "feishu_raw_data" in result:
        print("Success! Extracted rows:", len(result["feishu_raw_data"]))
        if result["feishu_raw_data"]:
            print("First row keys:", result["feishu_raw_data"][0].keys())
            print("First row values:", list(result["feishu_raw_data"][0].values())[:5])
    else:
        print("Fallback data returned:", result.keys())

if __name__ == "__main__":
    test_tms_feishu()
