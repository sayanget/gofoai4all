"""
物流调度部 AI 考核报告与飞书融合分发系统 - 大模型交互分析层
"""

import os
import json
import logging
import requests
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMAnalyzer")


class LLMAnalyzer:
    """
    大模型 API 调用层：传入静态规则与动态快照，返回结构化诊断报告。
    """

    def __init__(self, target_category: str = ""):
        # 优先读取配置文件中的自定义大模型配置，其次读取环境变量，最后使用默认值
        config_api_key = None
        config_api_base = None
        config_model = None
        config_custom_prompt = None
        
        config_path = os.path.join("config", "feishu_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    config_api_key = config_data.get("llm_api_key")
                    config_api_base = config_data.get("llm_api_base")
                    config_model = config_data.get("llm_model")
                    config_custom_prompts = config_data.get("llm_custom_prompts", {})
                    config_custom_prompt = config_custom_prompts.get(target_category, "") if target_category else ""
            except Exception as e:
                logger.error(f"Error loading LLM config from {config_path}: {e}")

        self.api_key = config_api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.api_base = config_api_base or os.getenv("LLM_API_URL") or os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
        self.model = config_model or os.getenv("LLM_MODEL") or "gpt-4o"
        self.custom_prompt = config_custom_prompt
        
        # 默认的 OpenAI 兼容端点
        if not self.api_base:
            self.api_base = "https://api.openai.com/v1"

        # Dynamically query supported models and fall back if target model is not in list
        if self.api_key:
            try:
                models_url = f"{self.api_base.rstrip('/')}/models"
                m_resp = requests.get(models_url, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=5)
                if m_resp.status_code == 200:
                    models_data = m_resp.json()
                    supported_models = [m["id"] for m in models_data.get("data", [])]
                    if supported_models and self.model not in supported_models:
                        fallback_model = None
                        for keyword in ["auto", "pro", "flash", "thinking"]:
                            candidates = [m for m in supported_models if keyword in m.lower()]
                            if candidates:
                                fallback_model = candidates[0]
                                break
                        if not fallback_model:
                            fallback_model = supported_models[0]
                        logger.info(f"Model {self.model} was not found on LLM endpoint. Falling back to: {fallback_model}")
                        self.model = fallback_model
            except Exception as me:
                logger.warning(f"Could not query supported models from LLM endpoint: {me}")
            
    def analyze(self, metrics: Dict[str, Any], exceptions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        根据校验结果调用大模型进行根因分析与定责
        """
        # 构建 prompt
        prompt = self._build_prompt(metrics, exceptions)
        system_prompt = self.custom_prompt if getattr(self, 'custom_prompt', None) else (
            "你是一个精通“美国接收国内电商尾程业务”的资深跨境物流调度专家。请根据提供的美国本地化时效数据和异常信息（如清关提货、干线Linehaul、尾程承运商注入、Hub集包），输出专业的定责考核报告，重点关注承运商截单时间和交件准点率。语言客观中立。\n"
            "你的核心任务是：\n"
            "1. 找出未达标指标（发车准点率、班次发货及时率、TMS操作率、卸车及时率红线为 92%-95%，请根据具体策略判断）。\n"
            "2. 根据串点加时、漏扫描定责等底层规则，准确指出异常原因，避免误判。\n"
            "3. 给出的优化建议必须具体、可执行，拒绝务虚。\n"
            "4. 必须输出符合 Schema 要求的标准 JSON 字符串，不能含有 Markdown 格式的包裹（如 ```json），直接返回 JSON 本身。"
        )

        try:
            if "gemini" in self.model.lower():
                import google.generativeai as genai
                client_options = {'api_endpoint': self.api_base} if self.api_base else None
                genai.configure(
                    api_key=self.api_key or "dummy_key",
                    transport='rest',
                    client_options=client_options
                )
                model = genai.GenerativeModel(
                    self.model,
                    system_instruction=system_prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.2
                    )
                )
                response = model.generate_content(prompt)
                
                try:
                    raw_content = response.text
                except ValueError as e:
                    if "function_call" in str(e) and response.candidates:
                        part = response.candidates[0].content.parts[0]
                        if part.function_call:
                            import json
                            args_dict = type(part.function_call.args).to_dict(part.function_call.args) if hasattr(type(part.function_call.args), 'to_dict') else dict(part.function_call.args)
                            raw_content = json.dumps(args_dict)
                        else:
                            raise
                    else:
                        raise
                        
                if not raw_content.strip():
                    if response.candidates:
                        part = response.candidates[0].content.parts[0]
                        if part.function_call:
                            import json
                            args_dict = type(part.function_call.args).to_dict(part.function_call.args) if hasattr(type(part.function_call.args), 'to_dict') else dict(part.function_call.args)
                            raw_content = json.dumps(args_dict)
                        else:
                            raise ValueError(f"大模型返回空文本，中断原因: {response.candidates[0].finish_reason}")
                    else:
                        raise ValueError("大模型未返回任何有效 Candidate")
                        
                return self._parse_and_validate_json(raw_content, metrics, exceptions)
                
            else:
                if not self.api_key:
                    logger.warning("未检测到 API 密钥，且非本地代理 Gemini 模型，尝试使用无鉴权方式调用")
                
                headers = {
                    "Content-Type": "application/json"
                }
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
        
                # 构造请求体，开启 json_object 响应格式（如果模型支持）
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }
                
                # 如果是 gpt-4o 等模型，启用 response_format json_object
                if "gpt" in self.model.lower():
                    payload["response_format"] = {"type": "json_object"}
        
                url = f"{self.api_base.rstrip('/')}/chat/completions"
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                res_json = response.json()
                raw_content = res_json["choices"][0]["message"]["content"]
                
                return self._parse_and_validate_json(raw_content, metrics, exceptions)
                
        except Exception as e:
            logger.error(f"大模型 API 调用失败: {e}，触发本地 Mock 降级")
            return self._heuristic_mock_analysis(metrics, exceptions)

    def _build_prompt(self, metrics: Dict[str, Any], exceptions: List[Dict[str, Any]]) -> str:
        """
        构建包含静态规则和动态运行快照的 Prompt
        """
        import rules_config
        
        # 提取动态规则内容
        rules_text = "【当前生效的大盘考核规则与红线】\n"
        for k, v in rules_config.METRICS_CONFIG.items():
            red_line_str = f"{v.get('red_line', 0)*100}%" if v.get("red_line") else "N/A"
            rules_text += f"- {k} ({v.get('control_level')}): 考核红线 {red_line_str}。规则说明: {v.get('description', '无')}\n"
        rules_text += "\n【当前生效的车型财务容量配置】\n"
        for k, v in rules_config.VEHICLE_CAPACITY.items():
            rules_text += f"- {k}: 额定 {v} 件\n"

        formatted_metrics = []
        for name, val in metrics.items():
            rate_str = f"{val['rate']*100:.1f}%" if "rate" in val else "N/A"
            formatted_metrics.append(f"- {name}: 实际完成 {rate_str} (状态: {val['status']})")

        formatted_exceptions = []
        max_exceptions_to_prompt = 5
        for i, ex in enumerate(exceptions[:max_exceptions_to_prompt], 1):
            formatted_exceptions.append(
                f"{i}. 指标: {ex['metric_name']} | ID: {ex['id']} | 异常状态: {ex['status']}\n"
                f"   - 原因: {ex['reason']}\n"
                f"   - 数据细节: {ex['details']}"
            )
            
        if len(exceptions) > max_exceptions_to_prompt:
            formatted_exceptions.append(f"\n... (由于篇幅限制，已省略其余 {len(exceptions) - max_exceptions_to_prompt} 条异常数据。请根据以上样本进行定责分析。)")

        prompt = f"""
{rules_text}

【今日物流调度运行数据快照】
1. 指标达成率：
{chr(10).join(formatted_metrics)}

2. 系统判定异常/红线拦截项：
{chr(10).join(formatted_exceptions) if formatted_exceptions else "今日无触发规则异常项，各项指标表现优异。"}

请针对以上规则与数据快照进行深入诊断，并按照以下 JSON Schema 输出分析结果：
{{
  "status": "success" | "warning" | "danger",  // 整体评估：全达标为 success；仅有通晒指标异常/轻微考核指标未达标为 warning；有核心考核指标严重未达标为 danger
  "title": "报告标题",
  "date": "报告日期 (格式 YYYY-MM-DD)",
  "summary": "当日运营情况的精简全局总结",
  "metrics_display": [
    {{
      "name": "指标名称",
      "value": "实际数值 (百分比形式)",
      "status": "正常" | "异常",
      "rule_triggered": "导致此项指标扣分/剔除的主要规则或无异常说明"
    }}
  ],
  "diagnosis_details": [
    {{
      "type": "核心异常" | "运营瓶颈",
      "content": "精准针对异常车次/班次的定责与根因分析（须指出责任方如始发地、HUB等）"
    }}
  ],
  "action_suggestions": [
    "改善建议（包含具体动作、责任主体及截止时间）"
  ]
}}
"""
        return prompt

    def _parse_and_validate_json(self, raw_text: str, metrics: Dict[str, Any], exceptions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        清理并解析 JSON，确保不崩溃，且包含完整必填项。
        """
        cleaned_text = raw_text.strip()
        # 去除 markdown 标记
        if cleaned_text.startswith("```"):
            lines = cleaned_text.splitlines()
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                cleaned_text = "\n".join(lines[1:-1])
        cleaned_text = cleaned_text.strip()

        try:
            data = json.loads(cleaned_text)
            # 基础格式补全校验
            required_keys = ["status", "title", "date", "summary", "metrics_display", "diagnosis_details", "action_suggestions"]
            for key in required_keys:
                if key not in data:
                    raise KeyError(f"Missing key: {key}")
            return data
        except Exception as e:
            logger.error(f"JSON 解析或验证失败: {e}，原始内容: {raw_text}")
            return self._heuristic_mock_analysis(metrics, exceptions)

    def _heuristic_mock_analysis(self, metrics: Dict[str, Any], exceptions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        启发式 Mock 算法：根据 rules_checker 输出的异常数和指标达成情况自动拼装出符合格式的诊断报告。
        """
        # 判断全局状态
        failures = [name for name, val in metrics.items() if val.get("status") == "异常"]
        
        if len(failures) >= 2:
            status = "danger"
        elif len(failures) == 1 or len(exceptions) > 0:
            status = "warning"
        else:
            status = "success"

        from datetime import date
        today_str = date.today().strftime("%Y-%m-%d")

        import rules_config
        metrics_display = []
        for name, val in metrics.items():
            if name not in rules_config.METRICS_CONFIG:
                continue
            rate_str = f"{val['rate']*100:.1f}%" if "rate" in val else "100.0%"
            metrics_display.append({
                "name": name,
                "value": rate_str,
                "status": "异常" if val.get("status") == "异常" else "正常",
                "rule_triggered": "触发考核指标未达标拦截规则" if val.get("status") == "异常" else "符合正常运作要求"
            })

        diagnosis_details = []
        action_suggestions = []

        if exceptions:
            for ex in exceptions[:3]:  # 取前3个异常做精准诊断
                diagnosis_details.append({
                    "type": "降级诊断",
                    "content": f"指标【{ex['metric_name']}】(ID: {ex['id']}) 发生异常，系统定责原因：{ex['reason']} (详情: {ex['details']})"
                })
            
            action_suggestions.append("⚠️ 请优先检查配置页面的 AI 模型接口与密钥是否正确填写并验证通过。")
            action_suggestions.append(f"协调【{exceptions[0]['metric_name']}】涉及责任节点，在24小时内完成排查并提交纠偏报告。")
            action_suggestions.append("加强对异常趟车TMS节点扫描的规范培训，避免漏扫误判。")
        else:
            diagnosis_details.append({
                "type": "降级诊断",
                "content": "今日大盘各项关键时效与操作率表现符合公司考核预期，无突出运营瓶颈。"
            })
            action_suggestions.append("⚠️ 请优先检查配置页面的 AI 模型接口与密钥是否正确填写并验证通过。")
            action_suggestions.append("继续保持现有精细化运作，建议对连续一周无异常的班次班组予以通报表扬。")

        summary = "⚠️ [大模型连接失败，已触发本地启发式降级分析]\n"
        summary += f"今日物流网络整体运行状态为 {status.upper()}。"
        if failures:
            summary += f"其中核心考核指标【{', '.join(failures)}】未达到公司设定的考核红线，需重点跟进督办。"
        else:
            summary += "全网各项考核指标均在红线以上，运行质量良好。"

        return {
            "status": status,
            "title": "物流调度部运营分析与 AI 定责考核报告",
            "date": today_str,
            "summary": summary,
            "metrics_display": metrics_display,
            "diagnosis_details": diagnosis_details,
            "action_suggestions": action_suggestions
        }
