import os

# Default data directory is 'data' in the project root, or override via GOFOAI_DATA_DIR env var
DATA_DIR = os.getenv("GOFOAI_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))

RULES_FILE = os.path.join(DATA_DIR, "config", "rules.json")
FEISHU_CONFIG_FILE = os.path.join(DATA_DIR, "config", "feishu_config.json")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

os.makedirs(os.path.join(DATA_DIR, "config"), exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
