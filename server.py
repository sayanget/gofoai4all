import os
from core_paths import RULES_FILE, FEISHU_CONFIG_FILE, CACHE_DIR, DATA_DIR
import json
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify, send_file
from feishu.card_sender import send_feishu_card

# 配置日志
os.makedirs("logs", exist_ok=True)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = RotatingFileHandler('logs/app.log', maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger("FeishuConfigServer")

app = Flask(__name__, static_folder='.', static_url_path='')

class EndpointFilter(logging.Filter):
    def filter(self, record):
        return '/api/logs' not in record.getMessage()

logging.getLogger("werkzeug").addFilter(EndpointFilter())

FEISHU_CONFIG_FILE = FEISHU_CONFIG_FILE
RULES_FILE = RULES_FILE

@app.route("/")
@app.route("/feishu_config.html")
def index():
    return send_file("feishu_config.html")

@app.route("/view_logs.html")
def view_logs_page():
    return send_file("view_logs.html")

@app.route("/api/logs", methods=["GET"])
def get_logs():
    try:
        log_path = 'logs/app.log'
        if not os.path.exists(log_path):
            return jsonify({"success": True, "logs": "等待日志生成..."})
        
        with open(log_path, 'r', encoding='utf-8') as f:
            # Read last 500 lines
            lines = f.readlines()
            last_lines = lines[-500:]
            return jsonify({"success": True, "logs": "".join(last_lines)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/clear_logs", methods=["POST"])
def clear_logs():
    try:
        log_path = 'logs/app.log'
        if os.path.exists(log_path):
            # Truncate the file
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/card_editor")
@app.route("/card_editor.html")
def card_editor():
    return send_file("card_editor.html")

@app.route("/api/get_config", methods=["GET"])
def get_config():
    feishu_config = {}
    if os.path.exists(FEISHU_CONFIG_FILE):
        try:
            with open(FEISHU_CONFIG_FILE, "r", encoding="utf-8") as f:
                feishu_config = json.load(f)
        except Exception as e:
            logger.error(f"Error reading feishu_config.json: {e}")

    rules_config = {}
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                rules_config = json.load(f)
        except Exception as e:
            logger.error(f"Error reading rules.json: {e}")

    return jsonify({
        "feishu_config": feishu_config,
        "rules_config": rules_config
    })

@app.route("/api/save_config", methods=["POST"])
def save_config():
    data = request.get_json(force=True, silent=True) or {}
    
    # 1. 保存/更新飞书通道凭证
    feishu_config = {}
    if os.path.exists(FEISHU_CONFIG_FILE):
        try:
            with open(FEISHU_CONFIG_FILE, "r", encoding="utf-8") as f:
                feishu_config = json.load(f)
        except Exception:
            pass

    channel = data.get("channel", "webhook")
    if channel == "webhook":
        feishu_config["feishu_webhook"] = data.get("webhook_url", "")
        feishu_config["feishu_secret"] = data.get("secret_key", "")
    else:
        feishu_config["app_id"] = data.get("app_id", "")
        feishu_config["app_secret"] = data.get("app_secret", "")
        feishu_config["chat_id"] = data.get("chat_id", "")

    # 保存自定义大模型配置
    llm_api_key = data.get("llm_api_key", "")
    llm_api_base = data.get("llm_api_base", "")
    llm_model = data.get("llm_model", "")
    
    # --- AI 配置自动验证逻辑 ---
    # 已移除：不在此处做强校验，防止网络超时导致整个规则无法保存。
    # 用户可以在实际诊断执行时暴露错误。
    # ---------------------------

    feishu_config["llm_api_key"] = llm_api_key
    feishu_config["llm_api_base"] = llm_api_base
    feishu_config["llm_model"] = llm_model
    feishu_config["llm_custom_prompts"] = data.get("llm_custom_prompts", {})

    try:
        os.makedirs(os.path.dirname(FEISHU_CONFIG_FILE), exist_ok=True)
        with open(FEISHU_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(feishu_config, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved Feishu credentials to {FEISHU_CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Failed to save Feishu credentials: {e}")
        return jsonify({"success": False, "error": f"Failed to save Feishu config: {e}"}), 500

    # 2. 保存/更新 rules.json 中的 KPI 红线值
    rules_config = {}
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                rules_config = json.load(f)
        except Exception:
            pass

    if "categories" not in rules_config:
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
            }

    try:
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(rules_config, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved KPI metrics to {RULES_FILE}")
    except Exception as e:
        logger.error(f"Failed to save KPI metrics: {e}")
        return jsonify({"success": False, "error": f"Failed to save rules: {e}"}), 500

    return jsonify({"success": True})

@app.route("/api/send_test_card", methods=["POST"])
def send_test_card():
    # 尝试使用真实的 RulesChecker & LLM 诊断流水线
    try:
        from run_pipeline import run_pipeline
        logger.info("Executing real daily pipeline for test distribution...")
        pipeline_results = run_pipeline()
        agent_output = pipeline_results["ai_report"]
        logger.info("Daily pipeline completed successfully, using LLM-analyzed results.")
    except Exception as e:
        logger.error(f"Failed to execute real pipeline: {e}. Falling back to structured mock data.")
        # 兜底测试数据（必须符合 card_sender.py 要求的新版 Schema）
        agent_output = {
            "status": "danger",
            "title": "物流调度部运营分析与 AI 定责考核报告",
            "date": "2026-06-08",
            "summary": "自配置页面发起的测试分发。今日发车准点率与卸车及时率均未达到考核红线，已触发系统警告。",
            "metrics_display": [
                {"name": "发车准点率", "value": "50.0%", "status": "异常", "rule_triggered": "触发考核指标未达标拦截规则"},
                {"name": "线路装载率", "value": "54.7%", "status": "正常", "rule_triggered": "符合正常运作要求"},
                {"name": "运行合格率", "value": "33.3%", "status": "正常", "rule_triggered": "符合正常运作要求"},
                {"name": "卸车及时率", "value": "33.3%", "status": "异常", "rule_triggered": "触发考核指标未达标拦截规则"}
            ],
            "diagnosis_details": [
                {"type": "核心异常", "content": "发车准点率异常：实际发车 (2026-06-08 11:20:00) > 计划发车 (2026-06-08 11:00:00)。"},
                {"type": "核心异常", "content": "卸车超时：到车后 90.0min 且班次开始后 150.0min 卸车，超时。"}
            ],
            "action_suggestions": [
                "协调涉及责任节点，在24小时内完成排查并提交纠偏报告。",
                "加强对异常趟车TMS节点扫描的规范培训，避免漏扫误判。"
            ]
        }

    # 读取当前最新飞书配置
    feishu_config = {}
    if os.path.exists(FEISHU_CONFIG_FILE):
        try:
            with open(FEISHU_CONFIG_FILE, "r", encoding="utf-8") as f:
                feishu_config = json.load(f)
        except Exception:
            pass

    webhook = feishu_config.get("feishu_webhook", "")
    secret = feishu_config.get("feishu_secret", "")
    app_id = feishu_config.get("app_id", "")
    app_secret = feishu_config.get("app_secret", "")
    chat_id = feishu_config.get("chat_id", "")

    try:
        status_code = send_feishu_card(
            agent_output,
            webhook,
            secret=secret,
            app_id=app_id,
            app_secret=app_secret,
            chat_id=chat_id
        )
        return jsonify({"success": status_code in (200, 0), "status_code": status_code})
    except Exception as e:
        logger.error(f"Failed to send test card: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/save_all_rules", methods=["POST"])
def save_all_rules():
    try:
        data = request.get_json(force=True, silent=True) or {}
        if "categories" not in data or "vehicle_capacity" not in data:
            return jsonify({"success": False, "error": "Invalid rules format. Must contain categories and vehicle_capacity."}), 400
        
        os.makedirs(os.path.dirname(RULES_FILE), exist_ok=True)
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved all rules to {RULES_FILE}")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Failed to save all rules: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/export_rules", methods=["GET"])
def export_rules():
    try:
        if not os.path.exists(RULES_FILE):
            return jsonify({"success": False, "error": "rules.json does not exist"}), 404
        return send_file(RULES_FILE, as_attachment=True, download_name="rules.json", mimetype="application/json")
    except Exception as e:
        logger.error(f"Failed to export rules: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/import_rules", methods=["POST"])
def import_rules():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "No selected file"}), 400
        
        content = file.read().decode("utf-8")
        parsed_json = json.loads(content)
        if "metrics" not in parsed_json or "vehicle_capacity" not in parsed_json:
            return jsonify({"success": False, "error": "Uploaded file is not a valid rules.json (must contain metrics and vehicle_capacity)"}), 400
        
        os.makedirs(os.path.dirname(RULES_FILE), exist_ok=True)
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(parsed_json, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully imported rules to {RULES_FILE}")
        return jsonify({"success": True, "rules_config": parsed_json})
    except Exception as e:
        logger.error(f"Failed to import rules: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/create_backup", methods=["POST"])
def create_backup():
    try:
        if not os.path.exists(RULES_FILE):
            return jsonify({"success": False, "error": "No rules.json to backup"}), 404
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"rules_backup_{timestamp}.json"
        backup_dir = os.path.join("config", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, backup_filename)
        
        import shutil
        shutil.copy2(RULES_FILE, backup_path)
        logger.info(f"Backup created: {backup_path}")
        return jsonify({"success": True, "filename": backup_filename})
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/list_backups", methods=["GET"])
def list_backups():
    try:
        backup_dir = os.path.join("config", "backups")
        if not os.path.exists(backup_dir):
            return jsonify({"success": True, "backups": []})
        
        import glob
        files = glob.glob(os.path.join(backup_dir, "rules_backup_*.json"))
        backups = []
        for f in files:
            filename = os.path.basename(f)
            stat = os.stat(f)
            from datetime import datetime
            created_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            backups.append({
                "filename": filename,
                "created_at": created_time,
                "size": stat.st_size
            })
        
        backups.sort(key=lambda x: x["filename"], reverse=True)
        return jsonify({"success": True, "backups": backups})
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/restore_backup", methods=["POST"])
def restore_backup():
    try:
        data = request.get_json(force=True, silent=True) or {}
        filename = data.get("filename")
        if not filename:
            return jsonify({"success": False, "error": "No backup filename provided"}), 400
        
        if ".." in filename or "/" in filename or "\\" in filename:
            return jsonify({"success": False, "error": "Invalid filename"}), 400
        
        backup_path = os.path.join("config", "backups", filename)
        if not os.path.exists(backup_path):
            return jsonify({"success": False, "error": "Backup file not found"}), 404
        
        import shutil
        shutil.copy2(backup_path, RULES_FILE)
        logger.info(f"Restored backup {filename} to {RULES_FILE}")
        
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            rules_config = json.load(f)
            
        return jsonify({"success": True, "rules_config": rules_config})
    except Exception as e:
        logger.error(f"Failed to restore backup: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/verify_url", methods=["POST"])
def verify_url():
    try:
        import requests
        import re
        import urllib3
        # Suppress insecure request warnings for self-signed SSL on local/test DMS systems
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        data = request.get_json(force=True, silent=True) or {}
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"success": False, "error": "链接不能为空"})
            
        # Regex validation: Feishu or DMS
        is_feishu = bool(re.search(r"feishu\.cn|larksuite\.com", url, re.I))
        is_dms = bool(re.search(r"dms", url, re.I))
        
        if not (is_feishu or is_dms):
            return jsonify({"success": False, "error": "数据源只能是飞书文档链接(feishu.cn)或DMS页面链接"})
            
        # Connectivity / readability verification
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            # Perform a GET request to verify responsiveness
            response = requests.get(url, headers=headers, timeout=5, allow_redirects=True, verify=False)
            
            if response.status_code < 500:
                return jsonify({
                    "success": True,
                    "message": f"连接成功 (HTTP {response.status_code})"
                })
            else:
                return jsonify({
                    "success": False,
                    "error": f"目标服务器响应异常 (HTTP {response.status_code})"
                })
        except requests.exceptions.RequestException as e:
            return jsonify({
                "success": False,
                "error": f"连接超时或无法访问 ({type(e).__name__})"
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/extract_rules", methods=["POST"])
def extract_rules():
    try:
        import base64
        import re
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        text_content = ""
        image_base64 = None
        image_mime = None

        # Check if file is uploaded
        if "file" in request.files:
            uploaded_file = request.files["file"]
            filename = uploaded_file.filename.lower()
            if filename:
                file_bytes = uploaded_file.read()
                is_image = any(filename.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"])
                if is_image:
                    image_base64 = base64.b64encode(file_bytes).decode("utf-8")
                    if filename.endswith(".png"):
                        image_mime = "image/png"
                    elif filename.endswith(".webp"):
                        image_mime = "image/webp"
                    else:
                        image_mime = "image/jpeg"
                else:
                    if filename.endswith(".csv"):
                        import pandas as pd
                        import io
                        try:
                            df = pd.read_csv(io.BytesIO(file_bytes))
                            text_content = df.to_csv(index=False)
                        except Exception as e:
                            logger.error(f"Error parsing CSV: {e}")
                            text_content = file_bytes.decode("utf-8", errors="ignore")
                    elif filename.endswith(".xlsx") or filename.endswith(".xls"):
                        import pandas as pd
                        import io
                        try:
                            df = pd.read_excel(io.BytesIO(file_bytes))
                            text_content = df.to_csv(index=False)
                        except Exception as e:
                            logger.error(f"Error parsing Excel: {e}")
                            text_content = ""
                    else:
                        # Treat as text file
                        try:
                            text_content = file_bytes.decode("utf-8")
                        except Exception:
                            text_content = file_bytes.decode("gbk", errors="ignore")

        # Try to read url or text from form/json
        url = ""
        if not text_content and not image_base64:
            if request.is_json:
                data = request.get_json(force=True, silent=True) or {}
                text_content = data.get("text", "")
                url = data.get("url", "")
            else:
                text_content = request.form.get("text", "")
                url = request.form.get("url", "")

        # Handle URL scraping
        if url and not text_content and not image_base64:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                resp = requests.get(url, headers=headers, timeout=10, verify=False)
                if resp.status_code == 200:
                    html = resp.text
                    html = re.sub(r"<script.*?>.*?</script>", "", html, flags=re.DOTALL | re.I)
                    html = re.sub(r"<style.*?>.*?</style>", "", html, flags=re.DOTALL | re.I)
                    text_content = re.sub(r"<.*?>", " ", html)
                    text_content = re.sub(r"\s+", " ", text_content).strip()
            except Exception as e:
                logger.error(f"Error scraping URL for rule extraction: {e}")

        # If nothing is provided, return error
        if not text_content and not image_base64:
            return jsonify({"success": False, "error": "请提供规则的图片、文档、描述文本或网页链接。"}), 400

        # Load LLM config
        feishu_config = {}
        if os.path.exists(FEISHU_CONFIG_FILE):
            try:
                with open(FEISHU_CONFIG_FILE, "r", encoding="utf-8") as f:
                    feishu_config = json.load(f)
            except Exception:
                pass

        api_key = feishu_config.get("llm_api_key") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        api_base = feishu_config.get("llm_api_base") or os.getenv("LLM_API_URL") or os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
        model = feishu_config.get("llm_model") or os.getenv("LLM_MODEL") or "gpt-4o"

        if not api_base:
            api_base = "https://api.openai.com/v1"

        api_configured = bool(api_key) or bool(api_base)
        error_detail = None
        
        # Dynamically query supported models and fall back if target model is not in list
        if api_key:
            try:
                models_url = f"{api_base.rstrip('/')}/models"
                m_resp = requests.get(models_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=5, verify=False)
                if m_resp.status_code == 200:
                    models_data = m_resp.json()
                    supported_models = [m["id"] for m in models_data.get("data", [])]
                    if supported_models and model not in supported_models:
                        fallback_model = None
                        for keyword in ["auto", "pro", "flash", "thinking"]:
                            candidates = [m for m in supported_models if keyword in m.lower()]
                            if candidates:
                                fallback_model = candidates[0]
                                break
                        if not fallback_model:
                            fallback_model = supported_models[0]
                        logger.info(f"Model {model} was not found on LLM endpoint. Falling back to: {fallback_model}")
                        model = fallback_model
            except Exception as me:
                logger.warning(f"Could not query supported models from LLM endpoint: {me}")

        system_prompt = (
            "你是一个物流时效与调度指标规则提取专家。请从用户输入的图片或文本描述中，提取出所有的指标考核规则和车型财务容量配置，并以标准的 JSON 格式输出。\n"
            "输出的 JSON 结构必须严格符合如下格式，且不要包含任何 markdown 代码块包裹（如 ```json），也不要有任何其他文字：\n"
            "{\n"
            "  \"metrics\": {\n"
            "    \"指标名称\": {\n"
            "      \"control_level\": \"考核\" 或 \"通晒\",\n"
            "      \"data_source\": \"数据来源(如TMS-出发到达管理、班次监控等)\",\n"
            "      \"description\": \"详细的指标计算公式和判定规则说明\",\n"
            "      \"red_line\": 浮点数值 (例如 0.95 代表 95%，若没有特定红线则设为 null)\n"
            "    }\n"
            "  },\n"
            "  \"vehicle_capacity\": {\n"
            "    \"车型名称\": 额定装载量数值 (整数)\n"
            "  }\n"
            "}"
        )

        extracted_rules = None
        using_mock = False
        
        if api_configured:
            try:
                # 您的本地 8085 代理是 Gemini 官方协议代理，所以必须走 Google GenAI SDK！
                if "gemini" in model.lower():
                    from google import genai
                    from google.genai import types
                    
                    http_options = {'base_url': api_base} if api_base else None
                    client = genai.Client(
                        api_key=api_key or "dummy_key",
                        http_options=http_options
                    )
                    
                    if image_base64:
                        import base64
                        img_bytes = base64.b64decode(image_base64)
                        prompt = "请分析图片，提取其中的物流考核指标规则与车型容积配置。请直接返回标准的 JSON，不要用 markdown 格式包裹。"
                        if text_content:
                            prompt += f"\n补充上下文：\n{text_content}"
                            
                        response = client.models.generate_content(
                            model=model,
                            contents=[
                                prompt, 
                                types.Part.from_bytes(data=img_bytes, mime_type=image_mime or "image/jpeg")
                            ],
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt,
                                temperature=0.1
                            )
                        )
                    else:
                        prompt = f"请分析以下文本，提取其中的物流考核指标规则与车型容积配置：\n{text_content}"
                        response = client.models.generate_content(
                            model=model,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt,
                                temperature=0.1
                            )
                        )
                    
                    raw_content = response.text
                    if not raw_content or not raw_content.strip():
                        raise ValueError("大模型返回空文本或未包含有效内容")
                else:
                    # Prepare LLM request payload for OpenAI compatible APIs
                    messages = [{"role": "system", "content": system_prompt}]
                    
                    if image_base64:
                        user_content = [
                            {"type": "text", "text": "请分析图片，提取其中的物流考核指标规则与车型容积配置。请直接返回标准的 JSON，不要用 markdown 格式包裹。"},
                            {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_base64}"}}
                        ]
                        if text_content:
                            user_content.append({"type": "text", "text": f"补充上下文：\n{text_content}"})
                        messages.append({"role": "user", "content": user_content})
                    else:
                        messages.append({"role": "user", "content": f"请分析以下文本，提取其中的物流考核指标规则与车型容积配置：\n{text_content}"})
    
                    headers = {
                        "Content-Type": "application/json"
                    }
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                    payload = {
                        "model": model,
                        "messages": messages,
                        "temperature": 0.1
                    }
                    if "gpt" in model.lower():
                        payload["response_format"] = {"type": "json_object"}
    
                    url_endpoint = f"{api_base.rstrip('/')}/chat/completions"
                    resp = requests.post(url_endpoint, headers=headers, json=payload, timeout=40, verify=False)
                    resp.raise_for_status()
    
                    result_json = resp.json()
                    raw_content = result_json["choices"][0]["message"]["content"].strip()

                if raw_content.startswith("```"):
                    lines = raw_content.splitlines()
                    if lines[0].startswith("```json") or lines[0].startswith("```"):
                        raw_content = "\n".join(lines[1:-1])
                raw_content = raw_content.strip()
                extracted_rules = json.loads(raw_content)

            except Exception as e:
                logger.error(f"Error calling LLM for rule extraction: {e}")
                using_mock = True
                error_detail = f"{str(e)} (evaluated model: {model})"
        else:
            using_mock = True

        if using_mock:
            logger.info("Using heuristic/mock parser for rule extraction.")
            # Scan text for typical rules
            search_text = text_content or ""
            extracted_rules = {"metrics": {}, "vehicle_capacity": {}}

            # Heuristic scanning mappings
            metrics_keywords = {
                "发车准点率": {"control_level": "考核", "data_source": "TMS-出发到达管理", "red_line": 0.95, "description": "准点率 = 当日应发车次的准点发车车次 / 当日应发总车次。超出计划发车时间未打卡或本站无发车但下一站已到车记为晚点。"},
                "卸车及时率": {"control_level": "考核", "data_source": "TMS-出发到达管理", "red_line": 0.95, "description": "准点卸车车次数 / (准点 + 晚点 + 漏卸车 + 本站发车未扫袋牌车次)。"},
                "班次发货及时率": {"control_level": "考核", "data_source": "班次监控", "red_line": 0.95, "description": "又称HUB发货及时率。区分集货与散货班次，件中转与箱中转判定截单时间，支持有无车到达时间的自适应窗口。"},
                "TMS操作率": {"control_level": "考核", "data_source": "TMS-出发到达管理", "red_line": 0.92, "description": "总实际操作次数 / (发车+装车+到达+卸车)应操作车次数。支持免操作和剔除判断。"},
                "线路装载率": {"control_level": "通晒", "data_source": "TMS-出发到达管理", "red_line": 0.50, "description": "综合装载率 = SUM(路段装载率_i * 路段英里数_i) / 线路总英里数。"},
                "到达准点率": {"control_level": "通晒", "data_source": "TMS-出发到达管理", "red_line": 0.90, "description": "到达准点率 = 当日准点到达车次数 / 当日应到达车次数。"},
                "运行合格率": {"control_level": "通晒", "data_source": "TMS-出发到达管理", "red_line": 0.90, "description": "运行合格车次 / 总发车车次。实际运行时长 <= 计划运行时长为合格。"},
                "加班占比": {"control_level": "通晒", "data_source": "TMS-出发到达管理", "red_line": 0.20, "description": "加班占比 = 当日加班车次数 / 当日应发总车次数。"}
            }

            found_any = False
            for k, meta in metrics_keywords.items():
                if k in search_text:
                    red_line = meta["red_line"]
                    percent_match = re.search(k + r".*?(\d+)%", search_text)
                    if percent_match:
                        red_line = float(percent_match.group(1)) / 100.0
                    
                    extracted_rules["metrics"][k] = {
                        "control_level": meta["control_level"],
                        "data_source": meta["data_source"],
                        "description": meta["description"],
                        "red_line": red_line
                    }
                    found_any = True

            capacity_keywords = {
                "53' Trailer": 12000,
                "26' Boxtruck": 4000,
                "22' Box Truck": 3385,
                "16' Box Truck": 1615,
                "15' Box Truck": 1615,
                "Cargo Van": 1480
            }
            for vname, vcap in capacity_keywords.items():
                if vname in search_text or vname.replace("'", "") in search_text:
                    extracted_rules["vehicle_capacity"][vname] = vcap

            if not found_any:
                # Default demonstration fallback rule
                extracted_rules["metrics"]["智能解析指标"] = {
                    "control_level": "考核",
                    "data_source": "未知",
                    "description": f"从输入智能提取出的时效规则。输入摘要: {search_text[:50]}...",
                    "red_line": 0.95
                }

        return jsonify({
            "success": True,
            "rules": extracted_rules,
            "using_mock": using_mock,
            "api_configured": api_configured,
            "error_detail": error_detail
        })
    except Exception as e:
        logger.error(f"Failed in extract_rules: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/generate_report", methods=["POST"])
def generate_report():
    try:
        file_path = None
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            target_category = request.form.get("target_category", "")
            file = request.files.get("file")
            if file and file.filename:
                os.makedirs("uploads", exist_ok=True)
                file_path = os.path.join("uploads", file.filename)
                file.save(file_path)
        else:
            data = request.get_json(force=True, silent=True) or {}
            target_category = data.get("target_category", "")
            
        from run_pipeline import run_pipeline
        logger.info(f"Executing real daily pipeline for manual review... target_category: {target_category}, file_path: {file_path}")
        pipeline_results = run_pipeline(target_category, file_path)
        agent_output = pipeline_results["ai_report"]
        logger.info("Daily pipeline completed successfully.")
        return jsonify({"success": True, "report": agent_output})
    except Exception as e:
        error_msg = str(e)
        if "数据源读取失败" in error_msg:
            logger.error(f"Data source read failed: {error_msg}")
            return jsonify({"success": False, "error": error_msg})
            
        logger.error(f"Failed to execute real pipeline: {e}. Using baseline mockup report.")
        from datetime import date
        today_str = date.today().strftime("%Y-%m-%d")
        fallback_output = {
            "status": "danger",
            "title": f"物流调度部运营分析与 AI 定责考核报告 ({today_str})",
            "date": today_str,
            "summary": "今日发车准点率与卸车及时率均未达到公司设定的考核红线，需重点跟进督办。",
            "metrics_display": [
                {"name": "发车准点率", "value": "50.0%", "status": "异常", "rule_triggered": "触发考核指标未达标拦截规则"},
                {"name": "线路装载率", "value": "54.7%", "status": "正常", "rule_triggered": "符合正常运作要求"},
                {"name": "卸车及时率", "value": "33.3%", "status": "异常", "rule_triggered": "触发考核指标未达标拦截规则"}
            ],
            "diagnosis_details": [
                {"type": "核心异常", "content": "发车准点率异常：实际发车 (2026-06-08 11:20:00) > 计划发车 (2026-06-08 11:00:00)。"},
                {"type": "核心异常", "content": "卸车超时：到车后 90.0min 且班次开始后 150.0min 卸车，超时。"}
            ],
            "action_suggestions": [
                "协调涉及责任节点，在24小时内完成排查并提交纠偏报告。",
                "加强对异常趟车TMS节点扫描的规范培训，避免漏扫误判。"
            ]
        }
        return jsonify({"success": True, "report": fallback_output, "warning": str(e)})

@app.route("/api/iterate_report", methods=["POST"])
def iterate_report():
    try:
        data = request.get_json(force=True, silent=True) or {}
        current_report = data.get("current_report")
        user_feedback = data.get("user_feedback")
        
        if not current_report or not user_feedback:
            return jsonify({"success": False, "error": "Missing current_report or user_feedback"}), 400
            
        from llm_analyzer import LLMAnalyzer
        analyzer = LLMAnalyzer()
        logger.info(f"Executing AI iteration with feedback: {user_feedback}")
        
        new_report = analyzer.iterate(current_report, user_feedback)
        return jsonify({"success": True, "report": new_report})
    except Exception as e:
        logger.error(f"Failed to iterate report: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/upgrade_rule", methods=["POST"])
def upgrade_rule():
    try:
        data = request.get_json(force=True, silent=True) or {}
        target_category = data.get("target_category")
        user_feedback = data.get("user_feedback")
        
        if not target_category or not user_feedback:
            return jsonify({"success": False, "error": "Missing target_category or user_feedback"}), 400
            
        feishu_config = {}
        if os.path.exists(FEISHU_CONFIG_FILE):
            with open(FEISHU_CONFIG_FILE, "r", encoding="utf-8") as f:
                feishu_config = json.load(f)
                
        prompts = feishu_config.get("llm_custom_prompts", {})
        existing_prompt = prompts.get(target_category, "")
        
        # Append the new rule
        if existing_prompt:
            new_prompt = existing_prompt + f"\n\n【附加诊断规则】\n{user_feedback}"
        else:
            new_prompt = f"你是一个精通“跨境物流”的资深分析专家。请针对【{target_category}】环节，根据提供的时效数据和异常信息，输出专业的定责考核报告。\n\n【附加诊断规则】\n{user_feedback}"
            
        prompts[target_category] = new_prompt
        feishu_config["llm_custom_prompts"] = prompts
        
        with open(FEISHU_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(feishu_config, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Successfully upgraded rule for {target_category} with feedback: {user_feedback}")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Failed to upgrade rule: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/send_edited_card", methods=["POST"])
def send_edited_card():
    try:
        data = request.get_json(force=True, silent=True) or {}
        report = data.get("report") or (data if ("status" in data or "title" in data) else None)
        if not report:
            return jsonify({"success": False, "error": "No report content provided"}), 400

        # Read current Feishu credentials
        feishu_config = {}
        if os.path.exists(FEISHU_CONFIG_FILE):
            try:
                with open(FEISHU_CONFIG_FILE, "r", encoding="utf-8") as f:
                    feishu_config = json.load(f)
            except Exception:
                pass

        webhook = feishu_config.get("feishu_webhook", "")
        secret = feishu_config.get("feishu_secret", "")
        app_id = feishu_config.get("app_id", "")
        app_secret = feishu_config.get("app_secret", "")
        chat_id = feishu_config.get("chat_id", "")

        status_code = send_feishu_card(
            report,
            webhook,
            secret=secret,
            app_id=app_id,
            app_secret=app_secret,
            chat_id=chat_id
        )
        return jsonify({"success": status_code in (200, 0), "status_code": status_code})
    except Exception as e:
        logger.error(f"Failed to send edited card: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9999, debug=True, use_reloader=False)
