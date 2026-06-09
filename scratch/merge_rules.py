import json
import os

rules_file = r"d:\project\gofoai\config\rules.json"
extracted_file = r"d:\project\gofoai\scratch\extracted_rules.json"

if not os.path.exists(rules_file):
    print(f"Error: {rules_file} does not exist.")
    exit(1)

if not os.path.exists(extracted_file):
    print(f"Error: {extracted_file} does not exist.")
    exit(1)

with open(rules_file, "r", encoding="utf-8") as f:
    rules = json.load(f)

with open(extracted_file, "r", encoding="utf-8") as f:
    extracted = json.load(f)

# Merge metrics
for metric_name, metric_info in extracted.get("metrics", {}).items():
    rules["metrics"][metric_name] = metric_info

# Merge vehicle capacity
for vehicle_name, capacity_val in extracted.get("vehicle_capacity", {}).items():
    rules["vehicle_capacity"][vehicle_name] = capacity_val

# Write back to rules.json
with open(rules_file, "w", encoding="utf-8") as f:
    json.dump(rules, f, ensure_ascii=False, indent=2)

print("Rules successfully merged and saved to config/rules.json")
