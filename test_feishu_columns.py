import json
import os
from tools.tms_extractor import TMSExtractor

with open('config/rules.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
url = config.get('metrics', {}).get('发车准点率', {}).get('data_source', '')

ext = TMSExtractor(url)
try:
    df = ext.fetch_feishu_sheet(url)
    with open('feishu_columns_output.txt', 'w', encoding='utf-8') as f:
        f.write('COLUMNS:\n')
        f.write(str(df.columns.tolist()) + '\n')
        f.write('\nFIRST ROW:\n')
        f.write(str(df.iloc[0].to_dict()) + '\n')
except Exception as e:
    with open('feishu_columns_output.txt', 'w', encoding='utf-8') as f:
        f.write('Error: ' + str(e))
