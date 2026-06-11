import json

config_path = 'data/config/rules.json'
with open(config_path, 'r', encoding='utf-8') as f:
    rules = json.load(f)

# Update vehicle capacity based on the provided image (units in 票)
rules['vehicle_capacity'] = {
    "53' Trailer": 12000,
    "26' Boxtruck": 4000,
    "22' Box Truck": 3385,
    "16' Box Truck": 1615,
    "15' Box Truck": 1615,
    "Cargo Van": 1480
}

with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(rules, f, indent=2, ensure_ascii=False)

print('Updated rules.json successfully.')
