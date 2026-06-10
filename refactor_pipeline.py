import re

with open('run_pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_feishu_url = '''    if not feishu_url:
        rules_file = os.path.join(os.path.dirname(__file__), "config", "rules.json")
        if os.path.exists(rules_file):
            with open(rules_file, "r", encoding="utf-8") as f:
                rules_config = json.load(f)
            feishu_url = rules_config.get("metrics", {}).get("发车准点率", {}).get("data_source", "")
        if not feishu_url:
            feishu_url = ""'''

new_feishu_url = '''    if not feishu_url:
        rules_file = os.path.join(os.path.dirname(__file__), "config", "rules.json")
        if os.path.exists(rules_file):
            with open(rules_file, "r", encoding="utf-8") as f:
                rules_config = json.load(f)
            
            categories = rules_config.get("categories", {})
            for cat_data in categories.values():
                if cat_data.get("data_source"):
                    feishu_url = cat_data.get("data_source")
                    break
        if not feishu_url:
            feishu_url = ""'''

content = content.replace(old_feishu_url, new_feishu_url)

with open('run_pipeline.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('run_pipeline.py updated')
