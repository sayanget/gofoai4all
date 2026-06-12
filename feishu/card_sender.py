"""
飞书卡片渲染与发送 (card_sender.py)
"""

import json
import logging
import requests
from typing import Dict, Any

import os
import time
import hmac
import hashlib
import base64

logger = logging.getLogger("FeishuCardSender")

def send_feishu_card(agent_output: Dict[str, Any], webhook_url: str, secret: str = None, app_id: str = None, app_secret: str = None, chat_id: str = None) -> int:
    """
    将 Antigravity Agent 的 analysis_result 映射到飞书卡片并发送，支持群机器人 Webhook 与企业自建应用 API 两种途径
    """
    secret = secret or os.getenv("FEISHU_SECRET")
    app_id = app_id or os.getenv("FEISHU_APP_ID")
    app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
    chat_id = chat_id or os.getenv("FEISHU_CHAT_ID")
    status = agent_output.get("status", "success")
    title = agent_output.get("title", "物流调度部运营分析报告")
    date_str = agent_output.get("date", "")
    summary = agent_output.get("summary", "")

    # 1. 动态映射卡片模板颜色
    header_color = "red" if status == "danger" else ("orange" if status == "warning" else "blue")

    # 2. 组装指标快览表格 (Feishu Table Component)
    metrics_table = {
        "tag": "table",
        "page_size": 10,
        "row_height": "low",
        "header_style": {
            "text_align": "left",
            "bold": True
        },
        "columns": [
            {"name": "name", "display_name": "指标名称", "width": "auto", "data_type": "lark_md"},
            {"name": "val", "display_name": "实际数值", "width": "auto", "data_type": "lark_md"},
            {"name": "status", "display_name": "判定状态", "width": "auto", "data_type": "lark_md"}
        ],
        "rows": []
    }
    
    for m in agent_output.get("metrics_display", []):
        name = m.get("name", "")
        val = m.get("value", "")
        m_status = m.get("status", "正常")
        icon = "🔴" if m_status == "异常" else "🟢"
        status_text = f"<font color='red'>**{m_status}**</font>" if m_status == "异常" else f"<font color='green'>{m_status}</font>"
        val_text = f"**{val}**" if m_status == "异常" else f"{val}"
        
        metrics_table["rows"].append({
            "name": f"{icon} {name}",
            "val": val_text,
            "status": status_text
        })
    
    # 3. 组装诊断结论 & 改善建议 markdown (采用引言块/引用块，使其极具层次感)
    diagnosis_items = []
    for d in agent_output.get("diagnosis_details", []):
        d_type = d.get("type", "异常")
        content = d.get("content", "")
        icon = "🚨" if d_type == "核心异常" else "⚠️"
        diagnosis_items.append(f"> {icon} **[{d_type}]** {content}")
    diagnosis_content = "\n>\n".join(diagnosis_items) if diagnosis_items else "> *未检测到核心异常*"
        
    suggestions_items = []
    for i, s in enumerate(agent_output.get("action_suggestions", []), 1):
        suggestions_items.append(f"> 💡 **行动建议 {i}**: {s}")
    suggestions_content = "\n>\n".join(suggestions_items) if suggestions_items else "> *无需额外改善动作*"

    title_content = f"{title} ({date_str})" if date_str else title

    # 4. 构造飞书 Card Payload
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title_content
                },
                "template": header_color
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📢 运营大盘快报：**\n> {summary}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "markdown",
                    "content": "**📊 核心指标达成情况：**"
                },
                metrics_table,
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**🔍 AI 专家定责诊断：**\n{diagnosis_content}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📋 协同改善要求：**\n{suggestions_content}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "📥 转为跟进工单"
                            },
                            "type": "primary",
                            "value": {
                                "action_type": "create_ticket",
                                "source": "ai_dispatch"
                            }
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "❓ 申诉/误报反馈"
                            },
                            "type": "default",
                            "value": {
                                "action_type": "appeal"
                            }
                        }
                    ]
                }
            ]
        }
    }

    # 如果启用了签名校验，生成签名并注入 payload
    if secret:
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        payload["timestamp"] = timestamp
        payload["sign"] = sign

    # 总是将最新的 Payload 写入本地以供审查
    try:
        with open("feishu_payload.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"无法将 Payload 写入本地: {e}")

    # 如果启用了自建应用 (App ID & App Secret & Chat ID)，优先通过开放平台消息接口发送
    if app_id and app_secret and chat_id:
        logger.info(f"使用企业自建应用发送消息 (App ID: {app_id}, Chat ID: {chat_id})...")
        try:
            token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            token_res = requests.post(token_url, json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
            token_res.raise_for_status()
            token = token_res.json().get("tenant_access_token")
            if not token:
                logger.error(f"获取 tenant_access_token 失败: {token_res.text}")
                return 500
            
            msg_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8"
            }
            msg_payload = {
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(payload["card"], ensure_ascii=False)
            }
            response = requests.post(msg_url, json=msg_payload, headers=headers, timeout=10)
            logger.info(f"自建应用消息卡片发送完成，HTTP 返回码: {response.status_code}，响应: {response.text}")
            return response.status_code
        except Exception as e:
            logger.error(f"自建应用发送卡片异常: {e}")
            return 500

    # 如果 Webhook 链接无效或为默认占位符，不发送 HTTP 请求，直接模拟 200 返回
    if not webhook_url or not webhook_url.startswith("http") or "YOUR-UUID" in webhook_url:
        logger.info("使用 Mock / 占位符 Webhook 链接，已成功跳过网络请求并模拟返回 200。")
        return 200

    try:
        headers = {"Content-Type": "application/json"}
        response = requests.post(webhook_url, headers=headers, json=payload, timeout=10)
        logger.info(f"飞书卡片已发送，Webhook 返回码: {response.status_code}")
        return response.status_code
    except Exception as e:
        logger.error(f"发送飞书卡片异常: {e}")
        return 500
