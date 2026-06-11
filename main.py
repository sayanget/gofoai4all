"""
主入口：Antigravity 工作流编排与启动 (main.py)
"""

import os
from core_paths import RULES_FILE, FEISHU_CONFIG_FILE, CACHE_DIR, DATA_DIR
import json
import logging
from agents.dispatcher_agent import create_dispatcher_agent
from feishu.card_sender import send_feishu_card

# 启用日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MainWorkflow")


def run_daily_pipeline():
    logger.info("Initializing Daily Pipeline using Antigravity Agent framework...")

    # 1. 初始化 Agent
    dispatcher_agent = create_dispatcher_agent()
    
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            rules_config = json.load(f)
            # 默认取发车准点率的数据源作为全局入口
            feishu_url = rules_config.get("metrics", {}).get("发车准点率", {}).get("data_source", "data/depatcher.xlsx")
    except Exception:
        feishu_url = "data/depatcher.xlsx"

    # 2. 触发 Agent 任务（让它自己去调工具计算指标并诊断）
    user_input = f"请读取今日的调度日志数据源 {feishu_url}，进行KPI规则审查，给出各环节异常汇总，最后生成飞书推送卡片结构。"
    logger.info("Triggering Agent running tasks...")
    response = dispatcher_agent.run(user_input)
    
    # 3. 解析 Agent 返回的结构化 JSON
    analysis_result = json.loads(response.content)
    
    # 4. 读取飞书配置 (优先读取环境变量，其次读取配置文件)
    FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
    FEISHU_SECRET = os.getenv("FEISHU_SECRET")
    FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
    FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
    FEISHU_CHAT_ID = os.getenv("FEISHU_CHAT_ID")

    config_path = FEISHU_CONFIG_FILE
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                if not FEISHU_WEBHOOK:
                    FEISHU_WEBHOOK = config_data.get("feishu_webhook")
                if not FEISHU_SECRET:
                    FEISHU_SECRET = config_data.get("feishu_secret")
                if not FEISHU_APP_ID:
                    FEISHU_APP_ID = config_data.get("app_id")
                if not FEISHU_APP_SECRET:
                    FEISHU_APP_SECRET = config_data.get("app_secret")
                if not FEISHU_CHAT_ID:
                    FEISHU_CHAT_ID = config_data.get("chat_id")
        except Exception as e:
            logger.error(f"无法读取配置文件 {config_path}: {e}")

    # 兜底默认值
    FEISHU_WEBHOOK = FEISHU_WEBHOOK or "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR-UUID"
    FEISHU_SECRET = FEISHU_SECRET or ""

    if FEISHU_APP_ID and FEISHU_APP_SECRET and FEISHU_CHAT_ID:
        logger.info(f"Sending formatted interactive card to Feishu via Enterprise App: {FEISHU_APP_ID}")
    else:
        logger.info(f"Sending formatted interactive card to Feishu via Webhook: {FEISHU_WEBHOOK}")
        
    status_code = send_feishu_card(
        analysis_result,
        FEISHU_WEBHOOK,
        secret=FEISHU_SECRET,
        app_id=FEISHU_APP_ID,
        app_secret=FEISHU_APP_SECRET,
        chat_id=FEISHU_CHAT_ID
    )
    
    logger.info(f"Feishu notification completed. Status code: {status_code}")
    
    # 将结果写入本地文件以备检查
    output_report = {
        "analysis_result": analysis_result,
        "feishu_status_code": status_code
    }
    with open("daily_pipeline_output.json", "w", encoding="utf-8") as f:
        json.dump(output_report, f, indent=2, ensure_ascii=False)
    
    logger.info("Daily pipeline output has been written to daily_pipeline_output.json")


if __name__ == "__main__":
    run_daily_pipeline()
