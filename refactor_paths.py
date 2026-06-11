import os

files_to_update = [
    'server.py',
    'tools/tms_extractor.py',
    'llm_analyzer.py',
    'tools/kpi_calculator.py',
    'run_pipeline.py',
    'rules_config.py',
    'main.py',
    'feishu_config.html'
]

replacements = {
    '"config/rules.json"': 'RULES_FILE',
    '"config/feishu_config.json"': 'FEISHU_CONFIG_FILE',
    "'config/rules.json'": 'RULES_FILE',
    "'config/feishu_config.json'": 'FEISHU_CONFIG_FILE',
    'os.path.join("config", "rules.json")': 'RULES_FILE',
    'os.path.join("config", "feishu_config.json")': 'FEISHU_CONFIG_FILE',
    'os.path.join("scratch", "cache")': 'CACHE_DIR',
    'os.path.join(os.path.dirname(__file__), "config", "rules.json")': 'RULES_FILE',
    # HTML replacements
    '保存并同步 rules.json': '保存并同步 data/config/rules.json',
    '导出 rules.json 备份': '导出 data/config/rules.json 备份',
    '导入 rules.json 备份': '导入 data/config/rules.json 备份',
    '同步至 config/rules.json': '同步至 data/config/rules.json',
    '正在保存规则修改到 rules.json': '正在保存规则修改到 data/config/rules.json',
    'feishu_config.json 与 rules.json 已成功同步': 'feishu_config.json 与 rules.json 已成功同步到 data/config'
}

for file in files_to_update:
    if not os.path.exists(file): continue
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add import core_paths
    if file.endswith('.py') and 'import core_paths' not in content:
        if 'import os' in content:
            content = content.replace('import os', 'import os\nfrom core_paths import RULES_FILE, FEISHU_CONFIG_FILE, CACHE_DIR, DATA_DIR', 1)
        else:
            content = 'from core_paths import RULES_FILE, FEISHU_CONFIG_FILE, CACHE_DIR, DATA_DIR\n' + content
            
    for old, new in replacements.items():
        content = content.replace(old, new)
        
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)

print('Refactored hardcoded paths to use core_paths.')
