import re

with open('server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update /api/save_config
old_save_config = '''    if "metrics" not in rules_config:
        rules_config["metrics"] = {}

    dynamic_kpis = data.get("dynamic_kpis", {})
    for metric_name, val in dynamic_kpis.items():
        if metric_name in rules_config["metrics"]:
            rules_config["metrics"][metric_name]["red_line"] = val
        else:
            # 如果规则里完全没有这个指标（一般不常见，但在扩展时可能需要）
            rules_config["metrics"][metric_name] = {
                "control_level": "考核",
                "red_line": val
            }'''
new_save_config = '''    if "categories" not in rules_config:
        rules_config["categories"] = {}

    dynamic_kpis = data.get("dynamic_kpis", {})
    for metric_name, val in dynamic_kpis.items():
        found = False
        for cat_data in rules_config["categories"].values():
            if "metrics" in cat_data and metric_name in cat_data["metrics"]:
                cat_data["metrics"][metric_name]["red_line"] = val
                found = True
                break
        if not found:
            # Fallback for dynamic KPI if not found in any category (create a default category)
            if "默认分类" not in rules_config["categories"]:
                rules_config["categories"]["默认分类"] = {"data_source": "", "metrics": {}}
            rules_config["categories"]["默认分类"]["metrics"][metric_name] = {
                "control_level": "考核",
                "red_line": val
            }'''
content = content.replace(old_save_config, new_save_config)

# 2. Update /api/save_all_rules
old_save_all = '''        data = request.get_json(force=True, silent=True) or {}
        if "metrics" not in data or "vehicle_capacity" not in data:
            return jsonify({"success": False, "error": "Invalid rules format. Must contain metrics and vehicle_capacity."}), 400'''
new_save_all = '''        data = request.get_json(force=True, silent=True) or {}
        if "categories" not in data or "vehicle_capacity" not in data:
            return jsonify({"success": False, "error": "Invalid rules format. Must contain categories and vehicle_capacity."}), 400'''
content = content.replace(old_save_all, new_save_all)

with open('server.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('server.py refactored')
