"""
工具1：数据抽取 (tms_extractor.py)
"""

import os
from core_paths import RULES_FILE, FEISHU_CONFIG_FILE, CACHE_DIR, DATA_DIR
import json
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List

class TMSExtractor:
    """
    负责从原始数据源 (Excel/CSV) 抽取调度数据，并转化为统一结构。
    """
    def __init__(self, data_path: str, target_category: str = ""):
        self.data_path = data_path
        self.target_category = target_category

    def extract(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        加载数据源。如果文件存在则使用 Pandas 读取；
        如果不存在或格式有误，自动降级为完备的 Mock 数据，以确保 Pipeline 的稳健运行。
        """
        import logging
        logger = logging.getLogger("FeishuConfigServer")
        logger.info(f"TMSExtractor.extract called with data_path={self.data_path}")
        try:
            # 优先检查是否是网络链接（飞书表格）
            if self.data_path.startswith('http') and ('feishu.cn/sheets/' in self.data_path or 'feishu.cn/wiki/' in self.data_path):
                logger.info(f"Feishu URL detected: {self.data_path}, fetching...")
                try:
                    df = self.fetch_feishu_sheet(self.data_path)
                    logger.info(f"Feishu fetch success, raw rows: {len(df)}")
                    
                    # 尝试根据用户的自定义提示词，动态使用大模型生成 Pandas 过滤条件
                    df = self._apply_dynamic_prompt_filter(df)
                    
                    res = self._map_feishu_data(df.to_dict(orient="records"))
                    res["_total_rows"] = len(df)
                    res["_raw_sample"] = df.head(5).to_dict(orient="records")
                    return res
                except Exception as e:
                    logger.error(f"Feishu fetch failed: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    raise ValueError(f"数据源读取失败: {str(e)}")

            # 本地文件读取逻辑

            if not os.path.exists(self.data_path):
                return self._get_fallback_mock_data()
                
            if self.data_path.endswith('.xlsx'):
                if 'depatcher.xlsx' in self.data_path.lower() or 'rules' in self.data_path.lower():
                    return self._get_fallback_mock_data()
                # 尝试读取 Excel (如果该 Excel 不是规则表而是运行日志的话)
                xls = pd.ExcelFile(self.data_path)
                data = {}
                for sheet in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet)
                    data[sheet] = df.to_dict(orient="records")
                return self._parse_extracted_dfs(data)
            elif self.data_path.endswith('.csv'):
                df = pd.read_csv(self.data_path)
                # 简单解析并包装为字典
                return {"raw_records": df.to_dict(orient="records")}
            else:
                return self._get_fallback_mock_data()
        except ValueError as ve:
            # Propagate the explicit data source error
            raise ve
        except Exception as e:
            logger.error(f"Unknown error in extract: {e}")
            return self._get_fallback_mock_data()

    def _apply_dynamic_prompt_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """根据 LLM 自定义提示词中的要求，动态过滤 DataFrame"""
        import logging
        logger = logging.getLogger("FeishuConfigServer")
        if not self.target_category:
            return df
            
        feishu_config = {}
        if os.path.exists(FEISHU_CONFIG_FILE):
            try:
                with open(FEISHU_CONFIG_FILE, "r", encoding="utf-8") as f:
                    feishu_config = json.load(f)
            except Exception:
                pass
                
        custom_prompts = feishu_config.get("llm_custom_prompts", {})
        prompt = custom_prompts.get(self.target_category, "")
        
        if not prompt or ("筛选" not in prompt and "只看" not in prompt and "过滤" not in prompt and "仅分析" not in prompt):
            return df
            
        logger.info(f"Detected filter intent in custom prompt for {self.target_category}. Asking LLM to generate pandas query...")
        
        try:
            from llm_analyzer import LLMAnalyzer
            analyzer = LLMAnalyzer(target_category=self.target_category)
            columns_str = ", ".join(df.columns.tolist()[:30]) # Show first 30 cols to save tokens
            system_instruction = (
                "你是一个精通 Python Pandas 的程序员。用户提示词中包含对数据的过滤需求。\n"
                f"当前 DataFrame `df` 的列名包含：[{columns_str}]\n"
                "请编写一个 Python 过滤函数。函数签名必须是 `def filter_df(df):`。\n"
                "函数内部请实现对应的过滤逻辑并返回新的 df。如果无需过滤请直接 return df。\n"
                "如果需要基于日期或月份筛选，请注意把相应的字符串列转为 datetime 对象后再过滤。过滤时处理好空值。\n"
                "千万不要使用未导入的外部函数（如 empty() ），直接使用 pandas 自带的 df.empty 或 pd.isna()。\n"
                "你的输出必须只有纯 Python 代码，绝对不能包含 markdown 标记或任何其他文本！"
            )
            
            code_str = analyzer._call_llm(system_instruction, f"用户的提示词为：\n{prompt}")
            code_str = code_str.strip()
            if code_str.startswith("```"):
                lines = code_str.splitlines()
                if len(lines) > 2:
                    code_str = "\n".join(lines[1:-1]).strip()
                    
            logger.info(f"Executing LLM generated filter function:\n{code_str}")
            local_vars = {}
            exec(code_str, {'pd': pd, 'datetime': datetime}, local_vars)
            
            if 'filter_df' in local_vars:
                df_filtered = local_vars['filter_df'](df)
                logger.info(f"Filtered rows from {len(df)} to {len(df_filtered)}")
                return df_filtered
        except Exception as e:
            logger.warning(f"Failed to apply dynamic prompt filter: {e}")
            
        return df

    def fetch_feishu_sheet(self, url: str) -> pd.DataFrame:
        import requests
        import re
        
        # 1. 获取凭证
        app_id = os.getenv("FEISHU_APP_ID")
        app_secret = os.getenv("FEISHU_APP_SECRET")
        config_path = FEISHU_CONFIG_FILE
        if os.path.exists(config_path) and (not app_id or not app_secret):
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                app_id = app_id or config_data.get("app_id")
                app_secret = app_secret or config_data.get("app_secret")
        
        if not app_id or not app_secret:
            raise ValueError("未配置 FEISHU_APP_ID 或 FEISHU_APP_SECRET，无法拉取飞书表格。")
            
        # 2. 解析 URL 获取 token 和 sheet_id
        is_wiki = False
        match_sheet = re.search(r'/sheets/([a-zA-Z0-9_]+)', url)
        match_wiki = re.search(r'/wiki/([a-zA-Z0-9_]+)', url)
        
        if match_sheet:
            spreadsheet_token = match_sheet.group(1)
        elif match_wiki:
            spreadsheet_token = match_wiki.group(1)  # 暂时保存 wiki token
            is_wiki = True
        else:
            raise ValueError("无效的飞书表格链接，无法提取 spreadsheetToken 或 wikiToken。")
        
        sheet_id = ""
        if "sheet=" in url:
            sheet_id = url.split("sheet=")[-1].split("&")[0]
        else:
            raise ValueError("链接中缺少 sheet 参数 (sheet_id)。")

        # 3. 获取 tenant_access_token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_res = requests.post(token_url, json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
        token_res.raise_for_status()
        tenant_access_token = token_res.json().get("tenant_access_token")
        if not tenant_access_token:
            raise ValueError("获取飞书 API Token 失败。")

        headers = {
            "Authorization": f"Bearer {tenant_access_token}"
        }

        # 如果是 wiki 链接，需要先通过 wiki token 获取底层的 obj_token (即真实的 sheet token)
        if is_wiki:
            wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={spreadsheet_token}"
            wiki_res = requests.get(wiki_url, headers=headers, timeout=10)
            wiki_res.raise_for_status()
            wiki_data = wiki_res.json()
            if wiki_data.get("code") != 0:
                raise ValueError(f"飞书 Wiki API 报错: {wiki_data.get('msg')}")
            
            # 替换为真实的 spreadsheet_token
            spreadsheet_token = wiki_data.get("data", {}).get("node", {}).get("obj_token")
            if not spreadsheet_token:
                raise ValueError("无法从 Wiki 节点中解析出底层的表格 Token。")
        # 使用读取单个工作表的接口
        sheet_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_id}"
        sheet_res = requests.get(sheet_url, headers=headers, timeout=10)
        sheet_res.raise_for_status()
        
        sheet_data = sheet_res.json()
        if sheet_data.get("code") != 0:
            raise ValueError(f"飞书 API 报错: {sheet_data.get('msg')}")
            
        values = sheet_data.get("data", {}).get("valueRange", {}).get("values", [])
        if not values:
            return pd.DataFrame()
            
        # 第一行为表头
        columns = values[0]
        data_rows = values[1:]
        
        # 补齐或裁剪长度以匹配 columns
        processed_rows = []
        for row in data_rows:
            if len(row) < len(columns):
                row.extend([None] * (len(columns) - len(row)))
            elif len(row) > len(columns):
                row = row[:len(columns)]
            processed_rows.append(row)
            
        df = pd.DataFrame(processed_rows, columns=columns)
        return df

    def _map_feishu_data(self, feishu_rows: list) -> dict:
        """
        将飞书的扁平结构映射到系统支持的字典列表中。对于飞书中没有的数据，暂用 Mock 数据占位。
        """
        from datetime import timedelta
        
        def excel_to_dt(val):
            if pd.isna(val) or val == "":
                return None
            try:
                if isinstance(val, (int, float)):
                    if val < 100000:
                        return datetime(1899, 12, 30) + timedelta(days=val)
                    return datetime.fromtimestamp(val / 1000)
                return pd.to_datetime(val)
            except:
                return None

        dispatch_punctuality = []
        arrival_punctuality = []
        unloading_timeliness = []
        
        for row in feishu_rows:
            trip_id = row.get("运输任务编码", "Unknown")
            
            plan_dep = excel_to_dt(row.get("计划发车时间(本地时区)"))
            act_dep = excel_to_dt(row.get("实际发车时间(本地时区)"))
            plan_arr = excel_to_dt(row.get("计划到车时间(本地时区)"))
            act_arr = excel_to_dt(row.get("实际到车时间(本地时区)"))
            route = row.get("发车路段", "")
            departure_loc = row.get("车辆出发地", "")
            arrival_loc = row.get("车辆到达地", "")
            
            # 只有当包含有效 trip_id 时才加入 (过滤掉空行)
            if str(trip_id).strip() and str(trip_id).strip() != "Unknown":
                dispatch_punctuality.append({
                    **row,
                    "trip_id": trip_id,
                    "planned_departure": plan_dep,
                    "actual_departure": act_dep,
                    "actual_arrival_next_station": act_arr,
                    "origin": departure_loc,
                    "destination": arrival_loc,
                    "is_from_site": False
                })
                
                arrival_punctuality.append({
                    **row,
                    "trip_id": trip_id,
                    "planned_arrival": plan_arr,
                    "actual_arrival": act_arr,
                    "origin": departure_loc,
                    "destination": arrival_loc,
                    "prev_station_departure": act_dep
                })
                
                unloading_timeliness.append({
                    **row,
                    "trip_id": trip_id,
                    "actual_arrival": act_arr,
                    "first_unloading_scan": excel_to_dt(row.get("最小卸车签入时间(本地时区)")),
                    "has_inbound_manifest": True,
                    "loaded_bags_qty": row.get("装车签出袋号数", 10),
                    "route_name": route,
                    "origin": departure_loc,
                    "destination": arrival_loc
                })

        mock = self._get_fallback_mock_data()
        
        # 仅当成功解析出数据时，才覆盖 mock
        if dispatch_punctuality:
            mock["dispatch_punctuality"] = dispatch_punctuality
        if arrival_punctuality:
            mock["arrival_punctuality"] = arrival_punctuality
        if unloading_timeliness:
            mock["unloading_timeliness"] = unloading_timeliness
            
        return mock

    def _parse_extracted_dfs(self, raw_sheets_data: dict) -> dict:
        """
        转换 Pandas DataFrame 列表为 RulesChecker 可识别的统一字段结构
        """
        # 如果是标准格式，进行转换；如果是空数据，降级
        if not raw_sheets_data:
            return self._get_fallback_mock_data()
        return raw_sheets_data

    def _get_fallback_mock_data(self) -> dict:
        """
        生产级 Mock 数据集（与之前设计的规则验证集一致）
        """
        base_date = datetime(2026, 6, 8)
        return {
            "dispatch_punctuality": [
                {
                    "trip_id": "T001",
                    "planned_departure": base_date.replace(hour=10, minute=0),
                    "actual_departure": base_date.replace(hour=9, minute=55),
                    "actual_arrival_next_station": base_date.replace(hour=11, minute=0),
                    "is_from_site": False
                },
                {
                    "trip_id": "T002",
                    "planned_departure": base_date.replace(hour=11, minute=0),
                    "actual_departure": base_date.replace(hour=11, minute=20),
                    "actual_arrival_next_station": base_date.replace(hour=12, minute=30),
                    "is_from_site": False
                },
                {
                    "trip_id": "T003",
                    "planned_departure": base_date.replace(hour=12, minute=0),
                    "actual_departure": None,
                    "actual_arrival_next_station": base_date.replace(hour=13, minute=15),
                    "is_from_site": False
                },
                {
                    "trip_id": "T004",
                    "planned_departure": base_date.replace(hour=13, minute=0),
                    "actual_departure": None,
                    "actual_arrival_next_station": None,
                    "is_from_site": False
                },
                {
                    "trip_id": "T005",
                    "planned_departure": base_date.replace(hour=15, minute=0),
                    "actual_departure": base_date.replace(hour=15, minute=30),
                    "actual_arrival_next_station": base_date.replace(hour=17, minute=0),
                    "upstream_actual_arrival": base_date.replace(hour=15, minute=15),
                    "hub_operation_minutes": 20,
                    "shift_start": base_date.replace(hour=14, minute=0),
                    "shift_end": base_date.replace(hour=22, minute=0),
                    "is_from_site": False
                }
            ],
            "route_load_rate": [
                {
                    "trip_id": "L001",
                    "vehicle_type": "53' Trailer",
                    "legs": [
                        {"leg_index": 1, "loaded_qty": 6000, "unloaded_qty": 0, "miles": 120.0},
                        {"leg_index": 2, "loaded_qty": 4000, "unloaded_qty": 2000, "miles": 80.0}
                    ]
                },
                {
                    "trip_id": "L002",
                    "vehicle_type": "26' Boxtruck",
                    "legs": [
                        {"leg_index": 1, "loaded_qty": 1500, "unloaded_qty": 0, "miles": 100.0}
                    ]
                }
            ],
            "duration_qualification": [
                {
                    "trip_id": "D001",
                    "planned_duration_hours": 4.0,
                    "actual_duration_hours": 3.8,
                    "actual_arrival": base_date.replace(hour=15, minute=0)
                },
                {
                    "trip_id": "D002",
                    "planned_duration_hours": 3.0,
                    "actual_duration_hours": 3.5,
                    "actual_arrival": base_date.replace(hour=16, minute=0)
                },
                {
                    "trip_id": "D003",
                    "planned_duration_hours": 5.0,
                    "actual_duration_hours": None,
                    "actual_arrival": base_date.replace(hour=18, minute=0)
                }
            ],
            "arrival_punctuality": [
                {
                    "trip_id": "A001",
                    "planned_arrival": base_date.replace(hour=18, minute=0),
                    "actual_arrival": base_date.replace(hour=17, minute=55),
                    "prev_station_departure": base_date.replace(hour=16, minute=0)
                },
                {
                    "trip_id": "A002",
                    "planned_arrival": base_date.replace(hour=19, minute=0),
                    "actual_arrival": None,
                    "prev_station_departure": base_date.replace(hour=17, minute=30)
                }
            ],
            "overtime_percentage": [
                {"trip_id": "O001", "is_origin": True, "is_overtime": False},
                {"trip_id": "O002", "is_origin": True, "is_overtime": True},
                {"trip_id": "O003", "is_origin": False, "is_overtime": True}
            ],
            "shift_dispatch_timeliness": [
                {
                    "shift_id": "S001",
                    "date": base_date,
                    "is_mainline_leg": True,
                    "signed_in_qty": 1000,
                    "on_time_dispatched_qty": 970
                },
                {
                    "shift_id": "S002",
                    "date": base_date,
                    "is_mainline_leg": True,
                    "signed_in_qty": 500,
                    "on_time_dispatched_qty": 420
                }
            ],
            "tms_operation_rate": [
                {
                    "trip_id": "TMS001",
                    "expected_operations": 4,
                    "actual_operations": 4
                },
                {
                    "trip_id": "TMS002",
                    "expected_operations": 4,
                    "actual_operations": 2,
                    "is_jfk": True
                },
                {
                    "trip_id": "TMS003",
                    "expected_operations": 4,
                    "actual_operations": 1,
                    "is_jfk_ewr_customs_clearance": True
                }
            ],
            "unloading_timeliness": [
                {
                    "trip_id": "U001",
                    "actual_arrival": base_date.replace(hour=8, minute=0),
                    "first_unloading_scan": base_date.replace(hour=8, minute=45),
                    "has_inbound_manifest": True,
                    "loaded_bags_qty": 10
                },
                {
                    "trip_id": "U002",
                    "actual_arrival": base_date.replace(hour=9, minute=0),
                    "first_unloading_scan": None,
                    "has_inbound_manifest": True,
                    "loaded_bags_qty": 5
                },
                {
                    "trip_id": "U003",
                    "actual_arrival": base_date.replace(hour=10, minute=0),
                    "first_unloading_scan": base_date.replace(hour=11, minute=30),
                    "has_inbound_manifest": True,
                    "loaded_bags_qty": 0
                },
                {
                    "trip_id": "U004",
                    "route_name": "JFK.H-EWR.H",
                    "actual_arrival": base_date.replace(hour=11, minute=0),
                    "first_unloading_scan": base_date.replace(hour=13, minute=0)
                }
            ]
        }
