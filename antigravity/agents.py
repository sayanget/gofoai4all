import json
import logging
from typing import List, Callable, Dict, Any, Optional
from llm_analyzer import LLMAnalyzer

logger = logging.getLogger("AntigravityAgent")


class AgentResponse:
    """
    Antigravity Agent Run Response Wrapper
    """
    def __init__(self, content: str):
        self.content = content


class Agent:
    """
    Antigravity Agent Class
    """
    def __init__(
        self,
        name: str,
        instructions: str,
        tools: List[Callable],
        model: str = "gpt-4o",
        response_format: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.instructions = instructions
        self.tools = tools
        self.model = model
        self.response_format = response_format
        self.analyzer = LLMAnalyzer()

    def run(self, user_input: str) -> AgentResponse:
        """
        运行 Agent 任务。
        1. 自动定位绑定的 KPI 计算工具并执行。
        2. 将工具返回的数据结合规则送入 LLM 进行分析与诊断。
        """
        logger.info(f"Agent '{self.name}' is running with input: {user_input}")
        
        # 1. 查找并运行 KPI 计算工具
        kpi_tool = None
        for tool_func in self.tools:
            if getattr(tool_func, "is_tool", False) and "calculate" in tool_func.tool_name:
                kpi_tool = tool_func
                break
                
        if not kpi_tool:
            # 备用：取第一个绑定的工具
            kpi_tool = self.tools[0] if self.tools else None
            
        tool_output_str = "{}"
        if kpi_tool:
            logger.info(f"Executing bound tool: {kpi_tool.tool_name}")
            # 模拟参数传递，将输入中指定的路径传给工具。
            # 如果没有路径，使用默认值
            path = "./data/daily_raw.csv"
            if "daily_raw.csv" in user_input:
                path = "./data/daily_raw.csv"
            elif "depatcher.xlsx" in user_input:
                path = "depatcher.xlsx"
                
            try:
                tool_output_str = kpi_tool(path)
            except Exception as e:
                logger.error(f"Error executing tool {kpi_tool.tool_name}: {e}")
                
        # 2. 解析工具输出，做 AI 分析
        try:
            tool_output = json.loads(tool_output_str)
        except Exception:
            tool_output = {}
            
        # 3. 调用 LLM 分析诊断（或调用 Fallback 启发式分析）
        metrics = tool_output.get("metrics", {})
        exceptions = tool_output.get("exceptions", [])
        
        # 使用 LLM 或者是内置的 LLMAnalyzer 逻辑
        ai_report = self.analyzer.analyze(
            metrics, 
            exceptions,
            total_rows_extracted=tool_output.get("total_rows_extracted", 0),
            raw_data_sample=tool_output.get("raw_data_sample", [])
        )
        
        # 返回符合 response.content 的 Response 结构
        report_str = json.dumps(ai_report, ensure_ascii=False)
        return AgentResponse(report_str)
