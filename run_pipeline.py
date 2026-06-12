"""
物流调度部 AI 考核报告与飞书融合分发系统 - 全套处理流水线与单元测试
"""

import os
from core_paths import RULES_FILE, FEISHU_CONFIG_FILE, CACHE_DIR, DATA_DIR
import json
from datetime import datetime
from rules_checker import RulesChecker
from llm_analyzer import LLMAnalyzer
from feishu_distributor import FeishuDistributor

# ==============================================================================
# 1. 构造 Mock 每日调度数据
# ==============================================================================
def get_mock_daily_data() -> dict:
    """
    产生覆盖全部8个指标、包含正常和各类触发异常规则的调度数据快照
    """
    base_date = datetime(2026, 6, 8)  # 2026-06-08 是周一 (Weekday)
    
    return {
        # 指标 1：发车准点率数据
        "dispatch_punctuality": [
            {
                "trip_id": "T001",
                "planned_departure": base_date.replace(hour=10, minute=0),
                "actual_departure": base_date.replace(hour=9, minute=55),
                "actual_arrival_next_station": base_date.replace(hour=11, minute=0),
                "is_from_site": False
            },
            {
                # 异常：常规发车晚点
                "trip_id": "T002",
                "planned_departure": base_date.replace(hour=11, minute=0),
                "actual_departure": base_date.replace(hour=11, minute=20),
                "actual_arrival_next_station": base_date.replace(hour=12, minute=30),
                "is_from_site": False
            },
            {
                # 异常：本站无发车打卡但下一站有到车打卡 -> 判定为晚点
                "trip_id": "T003",
                "planned_departure": base_date.replace(hour=12, minute=0),
                "actual_departure": None,
                "actual_arrival_next_station": base_date.replace(hour=13, minute=15),
                "is_from_site": False
            },
            {
                # 剔除：发车和下一站到车均为空
                "trip_id": "T004",
                "planned_departure": base_date.replace(hour=13, minute=0),
                "actual_departure": None,
                "actual_arrival_next_station": None,
                "is_from_site": False
            },
            {
                # 正常 (串点加时修正)：上游晚到15分钟，班次内，HUB操作需要20分钟。
                # 实际计划发车 = 15:15 + 20min = 15:35。实际发车 15:30 <= 15:35 -> 判定为准点！
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
        # 指标 2：线路装载率数据
        "route_load_rate": [
            {
                "trip_id": "L001",
                "vehicle_type": "53' Trailer",  # 额定: 12000
                "legs": [
                    {"leg_index": 1, "loaded_qty": 6000, "unloaded_qty": 0, "miles": 120.0},
                    {"leg_index": 2, "loaded_qty": 4000, "unloaded_qty": 2000, "miles": 80.0}
                ]
            },
            {
                # 异常：综合装载率低于 50% 报警线
                "trip_id": "L002",
                "vehicle_type": "26' Boxtruck",  # 额定: 4000
                "legs": [
                    {"leg_index": 1, "loaded_qty": 1500, "unloaded_qty": 0, "miles": 100.0}  # 装载率 37.5%
                ]
            }
        ],
        # 指标 3：运行合格率数据
        "duration_qualification": [
            {
                "trip_id": "D001",
                "planned_duration_hours": 4.0,
                "actual_duration_hours": 3.8,
                "actual_arrival": base_date.replace(hour=15, minute=0)
            },
            {
                # 异常：超时运行
                "trip_id": "D002",
                "planned_duration_hours": 3.0,
                "actual_duration_hours": 3.5,
                "actual_arrival": base_date.replace(hour=16, minute=0)
            },
            {
                # 异常：实际运行时长为空，但有实际抵达时间 -> 判定为不合格
                "trip_id": "D003",
                "planned_duration_hours": 5.0,
                "actual_duration_hours": None,
                "actual_arrival": base_date.replace(hour=18, minute=0)
            }
        ],
        # 指标 4：到达准点率数据
        "arrival_punctuality": [
            {
                "trip_id": "A001",
                "planned_arrival": base_date.replace(hour=18, minute=0),
                "actual_arrival": base_date.replace(hour=17, minute=55),
                "prev_station_departure": base_date.replace(hour=16, minute=0)
            },
            {
                # 异常：上一站有发车但本站无到达 -> 判定为晚点
                "trip_id": "A002",
                "planned_arrival": base_date.replace(hour=19, minute=0),
                "actual_arrival": None,
                "prev_station_departure": base_date.replace(hour=17, minute=30)
            }
        ],
        # 指标 5：加班占比数据
        "overtime_percentage": [
            {"trip_id": "O001", "is_origin": True, "is_overtime": False},
            {"trip_id": "O002", "is_origin": True, "is_overtime": True},
            {"trip_id": "O003", "is_origin": False, "is_overtime": True}  # 经停/非始发不计入
        ],
        # 指标 6：班次发货及时率数据
        "shift_dispatch_timeliness": [
            {
                "shift_id": "S001",
                "date": base_date,
                "is_mainline_leg": True,
                "signed_in_qty": 1000,
                "on_time_dispatched_qty": 970
            },
            {
                # 异常：发货率 (420/500 = 84.0%) 低于考核线 (95%)
                "shift_id": "S002",
                "date": base_date,
                "is_mainline_leg": True,
                "signed_in_qty": 500,
                "on_time_dispatched_qty": 420
            }
        ],
        # 指标 7：TMS 操作率数据
        "tms_operation_rate": [
            {
                "trip_id": "TMS001",
                "expected_operations": 4,
                "actual_operations": 4
            },
            {
                # JFK免签出，应操作降为3次。实操2次，操作率66.7% -> 报警
                "trip_id": "TMS002",
                "expected_operations": 4,
                "actual_operations": 2,
                "is_jfk": True
            },
            {
                # JFK-EWR清关行，直接剔除
                "trip_id": "TMS003",
                "expected_operations": 4,
                "actual_operations": 1,
                "is_jfk_ewr_customs_clearance": True
            }
        ],
        # 指标 8：卸车及时率数据
        "unloading_timeliness": [
            {
                "trip_id": "U001",
                "actual_arrival": base_date.replace(hour=8, minute=0),
                "first_unloading_scan": base_date.replace(hour=8, minute=45),  # 45分钟 -> 准点
                "has_inbound_manifest": True,
                "loaded_bags_qty": 10
            },
            {
                # 异常：到车已达，有装车记录，但无卸车扫描第一枪 -> 漏卸车 (晚点)
                "trip_id": "U002",
                "actual_arrival": base_date.replace(hour=9, minute=0),
                "first_unloading_scan": None,
                "has_inbound_manifest": True,
                "loaded_bags_qty": 5
            },
            {
                # 异常：装车袋数为0 -> 本站发车未扫袋牌，定责上游异常，剔除本站卸车责任
                "trip_id": "U003",
                "actual_arrival": base_date.replace(hour=10, minute=0),
                "first_unloading_scan": base_date.replace(hour=11, minute=30),
                "has_inbound_manifest": True,
                "loaded_bags_qty": 0
            },
            {
                # 剔除：清关行提货场景
                "trip_id": "U004",
                "route_name": "JFK.H-EWR.H",
                "actual_arrival": base_date.replace(hour=11, minute=0),
                "first_unloading_scan": base_date.replace(hour=13, minute=0)
            }
        ]
    }


# ==============================================================================
# 2. 流水线执行
# ==============================================================================
def run_pipeline(target_category: str = "", file_path: str = None) -> dict:
    """
    运行完整的处理流水线：校验 -> 诊断分析 -> 组装卡片
    """
    # Step 1: 获取真实飞书数据或降级为 Mock 数据并运行拦截校验层
    raw_data = None
    if file_path and os.path.exists(file_path):
        from tools.tms_extractor import TMSExtractor
        extractor = TMSExtractor(file_path, target_category=target_category)
        raw_data = extractor.extract()
    else:
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                rules_config = json.load(f)
                feishu_url = rules_config.get("categories", {}).get(target_category, {}).get("data_source", "")
                import logging
                logging.getLogger("FeishuConfigServer").info(f"Read feishu_url from rules.json: '{feishu_url}' for category '{target_category}'")
        except Exception as e:
            import logging
            logging.getLogger("FeishuConfigServer").error(f"Error reading rules.json: {e}")
            feishu_url = ""

        if feishu_url and feishu_url.startswith("http") and "feishu.cn" in feishu_url:
            from tools.tms_extractor import TMSExtractor
            extractor = TMSExtractor(feishu_url, target_category=target_category)
            raw_data = extractor.extract()
        else:
            import logging
            logging.getLogger("FeishuConfigServer").info(f"No valid feishu_url found. Falling back to mock data.")
            raw_data = get_mock_daily_data()
            
    checker = RulesChecker(raw_data)
    check_results = checker.check_all_metrics()
    
    # Step 2: 提取结果送入 AI 诊断引擎
    analyzer = LLMAnalyzer(target_category=target_category)
    ai_report = analyzer.analyze(
        check_results["metrics"], 
        check_results["exceptions"],
        total_rows_extracted=check_results.get("total_rows_extracted", 0),
        raw_data_sample=check_results.get("raw_data_sample", [])
    )
    
    # Step 3: 使用飞书分发层渲染 interactive payload
    distributor = FeishuDistributor()
    feishu_payload = distributor.build_card_payload(ai_report)
    
    return {
        "check_results": check_results,
        "ai_report": ai_report,
        "feishu_payload": feishu_payload
    }


# ==============================================================================
# 3. 单元测试与文件输出（避免控制台中文编码报错）
# ==============================================================================
if __name__ == "__main__":
    results = run_pipeline()
    
    output_lines = []
    output_lines.append("====== 1. 开始运行物流调度 AI 考核报告流水线 ======\n")
    
    output_lines.append("====== 2. 规则校验拦截层输出统计与异常项 ======")
    metrics = results["check_results"]["metrics"]
    for name, m in metrics.items():
        rate_str = f"{m['rate']*100:.1f}%" if "rate" in m else "N/A"
        output_lines.append(f"- 指标: {name.ljust(12)} | 达成率/占比: {rate_str.ljust(6)} | 状态: {m['status']}")
        
    output_lines.append(f"\n捕获的规则校验异常条数: {len(results['check_results']['exceptions'])}")
    for ex in results["check_results"]["exceptions"]:
        output_lines.append(f"  * 异常指标: {ex['metric_name']} (ID: {ex['id']}) | 状态: {ex['status']} | 原因: {ex['reason']}")
        
    output_lines.append("\n====== 3. AI 智能诊断引擎输出成果 (JSON) ======")
    output_lines.append(json.dumps(results["ai_report"], indent=2, ensure_ascii=False))
    
    output_lines.append("\n====== 4. 组装后的飞书交互卡片完整 Payload ======")
    output_lines.append(json.dumps(results["feishu_payload"], indent=2, ensure_ascii=False))
    
    # 将完整的带中文的报告写入日志文件，以 UTF-8 编码保存
    with open("pipeline_run_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
        
    # 同时写入单独的 JSON 格式 Payload 以备后续直接调用
    with open("feishu_payload_output.json", "w", encoding="utf-8") as f:
        json.dump(results["feishu_payload"], f, indent=2, ensure_ascii=False)
        
    # 控制台只输出 ASCII 安全的英文成功消息
    print("Pipeline run completed successfully!")
    print("Full report with diagnostic info written to: pipeline_run_output.txt")
    print("Feishu payload written to: feishu_payload_output.json")
