"""
物流调度部 AI 考核报告与飞书融合分发系统 - 飞书卡片组装与分发模块
"""

import json
import logging
import requests
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FeishuDistributor")


class FeishuDistributor:
    """
    负责将大模型输出的结构化 JSON 转化为飞书 Interactive 卡片并发送
    """

    def build_card_payload(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于 LLM 分析报告组装飞书卡片 Payload
        """
        status = report.get("status", "success")
        title = report.get("title", "运营分析报告")
        date_str = report.get("date", "")
        summary = report.get("summary", "")

        # 1. 颜色映射
        color_map = {
            "danger": "red",
            "warning": "orange",
            "success": "blue"
        }
        header_color = color_map.get(status, "blue")

        # 2. 组装指标快览 markdown 表格
        metrics_markdown = "**📊 核心指标表现：**\n| 指标名称 | 实际数值 | 判定状态 |\n| :--- | :---: | :---: |\n"
        for m in report.get("metrics_display", []):
            name = m.get("name", "")
            val = m.get("value", "")
            m_status = m.get("status", "正常")
            
            icon = "🔴" if m_status == "异常" else "🟢"
            val_display = f"**{val}**" if m_status == "异常" else val
            m_status_display = f"**{m_status}**" if m_status == "异常" else m_status
            
            metrics_markdown += f"| {icon} **{name}** | {val_display} | {m_status_display} |\n"

        # 3. 组装诊断结论 & 改善建议 markdown 列表
        diagnosis_items = []
        for d in report.get("diagnosis_details", []):
            d_type = d.get("type", "异常")
            content = d.get("content", "")
            icon = "⚠️" if d_type == "核心异常" else "💡"
            diagnosis_items.append(f"{icon} **[{d_type}]** {content}")
            
        suggestions_items = []
        for i, s in enumerate(report.get("action_suggestions", []), 1):
            suggestions_items.append(f" {i}. {s}")
            
        diagnosis_markdown = (
            "\\n".join(diagnosis_items) + 
            "\\n\\n**📋 协同改善要求：**\\n" + 
            "\\n".join(suggestions_items)
        )

        # 4. 构建标准飞书 Interactive 卡片 Payload
        # 注意：此处将占位符替换为相应的实际数据。由于是 JSON 结构，需要以 python dict 形式构造然后 dumps
        # 字段转义由 json.dumps 自动完成以防止 JSON 解析错误。
        
        card_structure = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{title} ({date_str})"
                },
                "template": header_color
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📢 运营快报：**\n{summary}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "markdown",
                    "content": metrics_markdown
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "lark_md",
                            "content": f"**🔍 AI 专家诊断方案：**\n{diagnosis_markdown}"
                        }
                    ]
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

        payload = {
            "msg_type": "interactive",
            "card": card_structure
        }
        
        return payload

    def send_to_webhook(self, webhook_url: str, card_payload: Dict[str, Any]) -> bool:
        """
        发送交互卡片到飞书 webhook 端点
        """
        if not webhook_url or not webhook_url.startswith("http"):
            logger.warning("无效的飞书 Webhook 链接，跳过实际网络请求发送。")
            return False
            
        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(webhook_url, headers=headers, json=card_payload, timeout=10)
            response.raise_for_status()
            logger.info("飞书卡片消息发送成功。")
            return True
        except Exception as e:
            logger.error(f"飞书卡片消息发送失败: {e}")
            return False
