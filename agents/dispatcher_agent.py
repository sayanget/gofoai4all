"""
调度专家 Agent 定义 (dispatcher_agent.py)
"""

from antigravity.agents import Agent
from tools.kpi_calculator import calculate_dispatch_metrics

def create_dispatcher_agent() -> Agent:
    """
    实例化并配置 Logistics_Dispatch_Expert 智能体。
    """
    system_prompt = """
    你是一位精通物流调度与中转站运营的资深专家。
    请调用 'calculate_dispatch_metrics' 工具获取今日清洗后的核心 KPI 指标。
    结合返回的触发规则（如漏扫描、串点未加时），进行物流专业度的根因分析与定责。
    你必须严格输出符合以下要求的 JSON Schema 格式，不要包裹 markdown 代码块标记：
    
    {
      "status": "success" | "warning" | "danger",
      "title": "报告主标题",
      "date": "YYYY-MM-DD",
      "summary": "大盘总结性描述",
      "metrics_display": [
        {
          "name": "指标名称",
          "value": "实际数值(百分比形式)",
          "status": "正常" | "异常",
          "rule_triggered": "触发的具体规则说明"
        }
      ],
      "diagnosis_details": [
        {
          "type": "核心异常" | "运营瓶颈",
          "content": "具体的根因分析与定责结论"
        }
      ],
      "action_suggestions": [
        "建议1：具体的动作以及时效要求",
        "建议2"
      ]
    }
    """
    
    # 实例化 Antigravity Agent
    agent = Agent(
        name="Logistics_Dispatch_Expert",
        instructions=system_prompt,
        tools=[calculate_dispatch_metrics],
        model="gpt-4o",  # 或者公司内部主力模型
        response_format={"type": "json_object"} 
    )
    return agent
