from core_paths import RULES_FILE, FEISHU_CONFIG_FILE, CACHE_DIR, DATA_DIR
"""
工具2：核心KPI与加时修正计算器 (kpi_calculator.py)
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List
from antigravity.tools import tool
from tools.tms_extractor import TMSExtractor

# 读取 rules.json 规则配置
try:
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        rules_config = json.load(f)
except Exception:
    rules_config = {}

VEHICLE_CAPACITY = rules_config.get("vehicle_capacity", {
    "53' Trailer": 12000,
    "26' Boxtruck": 4000,
    "22' Box Truck": 3385,
    "16' Box Truck": 1615,
    "15' Box Truck": 1615,
    "Cargo Van": 1480
})

METRICS_RED_LINE = {
    "发车准点率": 0.95,
    "线路装载率": 0.50,
    "班次发货及时率": 0.95,
    "TMS操作率": 0.92,
    "卸车及时率": 0.95
}


@tool("calculate_dispatch_metrics")
def calculate_dispatch_metrics(raw_data_path: str) -> str:
    """
    读取原始TMS数据，使用 Pandas 计算各项 KPI，执行串点线路加时修正与特殊免除判定，并返回指标和异常项的 JSON 结构。
    参数: raw_data_path: 每日原始数据的临时存储/加载路径
    """
    # 1. 抽取数据
    extractor = TMSExtractor(raw_data_path)
    raw_data = extractor.extract()

    metrics_results = {}
    exceptions = []

    # ----------------- 指标 1：发车准点率 -----------------
    if "dispatch_punctuality" in raw_data:
        df = pd.DataFrame(raw_data["dispatch_punctuality"])
        
        def check_row_punctuality(row):
            trip_id = row["trip_id"]
            planned = row["planned_departure"]
            actual = row["actual_departure"]
            next_arrival = row["actual_arrival_next_station"]
            upstream_arrival = row.get("upstream_actual_arrival")
            hub_op_min = row.get("hub_operation_minutes", 0)
            shift_start = row.get("shift_start")
            shift_end = row.get("shift_end")
            is_from_site = row.get("is_from_site", False)

            # 判定剔除：到发时间均为空
            if pd.isna(actual) and pd.isna(next_arrival):
                return "剔除", planned, "到发时间均为空"

            # 串点线路加时修正
            adjusted_planned = planned
            reason = ""
            if not pd.isna(upstream_arrival) and upstream_arrival > planned:
                # 判定是否在班次内
                in_shift = False
                if not pd.isna(shift_start) and not pd.isna(shift_end):
                    in_shift = (shift_start <= upstream_arrival <= shift_end)
                
                if in_shift or is_from_site:
                    # ① 班次内或站点：MAX{上游到达+HUB操作时间, 原计划发车}
                    pot = upstream_arrival + timedelta(minutes=hub_op_min)
                    if pot > planned:
                        adjusted_planned = pot
                        reason = f"触发班次内/站点加时至 {pot}"
                else:
                    # ② 班次外：MAX{班次开始时间+HUB操作时间, 原计划发车}
                    if not pd.isna(shift_start):
                        pot = shift_start + timedelta(minutes=hub_op_min)
                        if pot > planned:
                            adjusted_planned = pot
                            reason = f"触发班次外加时至 {pot}"

            # 判定准点
            if pd.isna(actual):
                if not pd.isna(next_arrival):
                    return "已到站未发车", adjusted_planned, f"本站无发车打卡但下一站已到站。{reason}"
                else:
                    return "晚点", adjusted_planned, f"超时未录入发车数据。{reason}"

            if actual <= adjusted_planned:
                return "准点", adjusted_planned, "符合时效"
            else:
                return "晚点", adjusted_planned, f"晚发车打卡。{reason}"

        if not df.empty:
            results = df.apply(check_row_punctuality, axis=1)
            df["status"] = [r[0] for r in results]
            df["adjusted_planned"] = [r[1] for r in results]
            df["reason"] = [r[2] for r in results]

            valid_df = df[df["status"] != "剔除"]
            total_valid = len(valid_df)
            punctual_count = len(valid_df[valid_df["status"] == "准点"])
            rate = punctual_count / total_valid if total_valid > 0 else 1.0

            metrics_results["发车准点率"] = {
                "rate": rate,
                "status": "正常" if rate >= METRICS_RED_LINE["发车准点率"] else "异常"
            }

            # 收集异常
            for _, row in valid_df[valid_df["status"] != "准点"].iterrows():
                exceptions.append({
                    "metric_name": "发车准点率",
                    "id": row["trip_id"],
                    "status": row["status"],
                    "reason": row["reason"],
                    "details": f"计划: {row['planned_departure']}, 实际: {row['actual_departure']}"
                })

    # ----------------- 指标 2：线路装载率 -----------------
    if "route_load_rate" in raw_data:
        total_weighted_load = 0.0
        total_miles = 0.0
        for r in raw_data["route_load_rate"]:
            trip_id = r["trip_id"]
            vehicle = r["vehicle_type"]
            capacity = VEHICLE_CAPACITY.get(vehicle, 12000)
            
            # 使用 pandas 计算各分段装载率
            legs_df = pd.DataFrame(r["legs"])
            if not legs_df.empty:
                legs_df = legs_df.sort_values("leg_index")
                rates = []
                prev_remaining = 0
                for _, leg in legs_df.iterrows():
                    loaded = leg["loaded_qty"]
                    unloaded = leg["unloaded_qty"]
                    leg_idx = leg["leg_index"]
                    
                    if leg_idx == 1:
                        rate = loaded / capacity
                    else:
                        rate = (loaded + prev_remaining) / capacity
                    
                    rates.append(rate)
                    prev_remaining = (prev_remaining + loaded) - unloaded
                
                legs_df["load_rate"] = rates
                legs_df["weighted_load"] = legs_df["load_rate"] * legs_df["miles"]
                
                trip_miles = legs_df["miles"].sum()
                trip_weighted = legs_df["weighted_load"].sum()
                trip_load_rate = trip_weighted / trip_miles if trip_miles > 0 else 0.0
                
                total_weighted_load += trip_weighted
                total_miles += trip_miles
                
                if trip_load_rate < METRICS_RED_LINE["线路装载率"]:
                    exceptions.append({
                        "metric_name": "线路装载率",
                        "id": trip_id,
                        "status": "装载不足",
                        "reason": f"车型 {vehicle} 综合装载率 {trip_load_rate*100:.1f}% 低于 50% 红线",
                        "details": f"分段明细: {r['legs']}"
                    })
        
        overall_load = total_weighted_load / total_miles if total_miles > 0 else 0.0
        metrics_results["线路装载率"] = {
            "rate": overall_load,
            "status": "正常"
        }

    # ----------------- 指标 3：运行合格率 -----------------
    if "duration_qualification" in raw_data:
        df = pd.DataFrame(raw_data["duration_qualification"])
        if not df.empty:
            def check_duration(row):
                planned = row["planned_duration_hours"]
                actual = row["actual_duration_hours"]
                arrival = row["actual_arrival"]
                
                if pd.isna(actual):
                    if not pd.isna(arrival):
                        return "不合格", "实际运行时间为空但有到达时间，判定不合格"
                    else:
                        return "剔除", "到发时间均为空"
                
                if actual <= planned:
                    return "合格", "合格"
                return "不合格", f"实际运行时长 {actual}h > 计划时长 {planned}h"
                
            res = df.apply(check_duration, axis=1)
            df["status"] = [r[0] for r in res]
            df["reason"] = [r[1] for r in res]
            
            valid_df = df[df["status"] != "剔除"]
            rate = len(valid_df[valid_df["status"] == "合格"]) / len(valid_df) if len(valid_df) > 0 else 1.0
            
            metrics_results["运行合格率"] = {
                "rate": rate,
                "status": "正常"
            }
            for _, row in valid_df[valid_df["status"] == "不合格"].iterrows():
                exceptions.append({
                    "metric_name": "运行合格率",
                    "id": row["trip_id"],
                    "status": "不合格",
                    "reason": row["reason"],
                    "details": f"计划: {row['planned_duration_hours']}h, 实际: {row['actual_duration_hours']}h"
                })

    # ----------------- 指标 4：到达准点率 -----------------
    if "arrival_punctuality" in raw_data:
        df = pd.DataFrame(raw_data["arrival_punctuality"])
        if not df.empty:
            def check_arrival(row):
                planned = row["planned_arrival"]
                actual = row["actual_arrival"]
                prev_dep = row["prev_station_departure"]
                
                if pd.isna(actual):
                    if not pd.isna(prev_dep):
                        return "晚点", "上一站有发车但本站无到车"
                    return "剔除", "到车和发车时间均为空"
                    
                if actual <= planned:
                    return "准点", "符合时效"
                return "晚点", f"实际到达 {actual} > 计划 {planned}"
                
            res = df.apply(check_arrival, axis=1)
            df["status"] = [r[0] for r in res]
            df["reason"] = [r[1] for r in res]
            
            valid_df = df[df["status"] != "剔除"]
            rate = len(valid_df[valid_df["status"] == "准点"]) / len(valid_df) if len(valid_df) > 0 else 1.0
            
            metrics_results["到达准点率"] = {
                "rate": rate,
                "status": "正常"
            }
            for _, row in valid_df[valid_df["status"] == "晚点"].iterrows():
                exceptions.append({
                    "metric_name": "到达准点率",
                    "id": row["trip_id"],
                    "status": "晚点",
                    "reason": row["reason"],
                    "details": f"计划: {row['planned_arrival']}, 实际: {row['actual_arrival']}"
                })

    # ----------------- 指标 5：加班占比 -----------------
    if "overtime_percentage" in raw_data:
        df = pd.DataFrame(raw_data["overtime_percentage"])
        if not df.empty:
            origin_df = df[df["is_origin"] == True]
            if not origin_df.empty:
                overtime_count = len(origin_df[origin_df["is_overtime"] == True])
                rate = overtime_count / len(origin_df)
                metrics_results["加班占比"] = {
                    "rate": rate,
                    "status": "正常"
                }

    # ----------------- 指标 6：班次发货及时率 -----------------
    if "shift_dispatch_timeliness" in raw_data:
        df = pd.DataFrame(raw_data["shift_dispatch_timeliness"])
        if not df.empty:
            # 过滤周一至周五，且是干线发货
            df["weekday"] = pd.to_datetime(df["date"]).dt.weekday
            valid_df = df[(df["weekday"] < 5) & (df["is_mainline_leg"] == True)]
            if not valid_df.empty:
                total_signed = valid_df["signed_in_qty"].sum()
                total_dispatched = valid_df["on_time_dispatched_qty"].sum()
                rate = total_dispatched / total_signed if total_signed > 0 else 1.0
                
                metrics_results["班次发货及时率"] = {
                    "rate": rate,
                    "status": "正常" if rate >= METRICS_RED_LINE["班次发货及时率"] else "异常"
                }
                
                for _, row in valid_df.iterrows():
                    row_rate = row["on_time_dispatched_qty"] / row["signed_in_qty"] if row["signed_in_qty"] > 0 else 1.0
                    if row_rate < METRICS_RED_LINE["班次发货及时率"]:
                        exceptions.append({
                            "metric_name": "班次发货及时率",
                            "id": row["shift_id"],
                            "status": "发货不及时",
                            "reason": f"班次及时率 {row_rate*100:.1f}% 低于 95% 考核红线",
                            "details": f"签入件量: {row['signed_in_qty']}, 准时发货件量: {row['on_time_dispatched_qty']}"
                        })

    # ----------------- 指标 7：TMS操作率 -----------------
    if "tms_operation_rate" in raw_data:
        df = pd.DataFrame(raw_data["tms_operation_rate"])
        if not df.empty:
            total_expected = 0
            total_actual = 0
            
            for _, row in df.iterrows():
                if row.get("is_jfk_ewr_customs_clearance", False):
                    continue  # JFK-EWR 清关行剔除
                    
                expected = row.get("expected_operations", 4)
                actual = row.get("actual_operations", 0)
                
                if row.get("is_origin_site", False):
                    expected = max(0, expected - 2)
                elif row.get("is_dest_ground", False):
                    expected = max(0, expected - 1)
                    
                if row.get("is_jfk", False):
                    expected = max(0, expected - 1)
                if row.get("is_stopover", False):
                    expected = max(0, expected - 1)
                    
                if expected <= 0:
                    continue
                    
                total_expected += expected
                total_actual += actual
                
                rate_single = actual / expected
                if rate_single < METRICS_RED_LINE["TMS操作率"]:
                    exceptions.append({
                        "metric_name": "TMS操作率",
                        "id": row["trip_id"],
                        "status": "漏操作",
                        "reason": f"趟车操作率 {rate_single*100:.1f}% 低于 92% 红线",
                        "details": f"应操作数: {expected}, 实操作数: {actual}"
                    })
                    
            rate = total_actual / total_expected if total_expected > 0 else 1.0
            metrics_results["TMS操作率"] = {
                "rate": rate,
                "status": "正常" if rate >= METRICS_RED_LINE["TMS操作率"] else "异常"
            }

    # ----------------- 指标 8：卸车及时率 -----------------
    if "unloading_timeliness" in raw_data:
        df = pd.DataFrame(raw_data["unloading_timeliness"])
        if not df.empty:
            total_valid = 0
            punctual_count = 0
            
            for _, row in df.iterrows():
                route = row.get("route_name")
                # 剔除 JFK-EWR 清关行
                if route and isinstance(route, str) and ("JFK.H-EWR.H" in route or "JFK-EWR" in route):
                    continue
                    
                actual_arr = row.get("actual_arrival")
                first_scan = row.get("first_unloading_scan")
                has_manifest = row.get("has_inbound_manifest", True)
                loaded_bags = row.get("loaded_bags_qty", 1)
                shift_start = row.get("shift_start")
                
                # 剔除：已完成装车但无实际到车
                if has_manifest and pd.isna(actual_arr):
                    continue
                    
                total_valid += 1
                
                # 定责上游：到车正常，但装车袋数为 0
                if not pd.isna(actual_arr) and loaded_bags == 0:
                    exceptions.append({
                        "metric_name": "卸车及时率",
                        "id": row["trip_id"],
                        "status": "定责上游",
                        "reason": "装车袋数为0，视为本站发车未扫袋牌，定责上游异常，扣减上游",
                        "details": f"到车: {actual_arr}, 装车袋数: 0"
                    })
                    continue
                
                # 漏卸车判定
                if not pd.isna(actual_arr) and has_manifest and pd.isna(first_scan):
                    exceptions.append({
                        "metric_name": "卸车及时率",
                        "id": row["trip_id"],
                        "status": "漏卸车",
                        "reason": "车辆已到达但无任何卸车扫描第一枪记录",
                        "details": f"到达: {actual_arr}"
                    })
                    continue
                
                # 计算卸车时效
                if not pd.isna(actual_arr) and not pd.isna(first_scan):
                    min_from_arr = (first_scan - actual_arr).total_seconds() / 60.0
                    if min_from_arr < 60.0:
                        punctual_count += 1
                        continue
                        
                    if not pd.isna(shift_start):
                        min_from_shift = (first_scan - shift_start).total_seconds() / 60.0
                        if min_from_shift <= 120.0:
                            punctual_count += 1
                            continue
                            
                    exceptions.append({
                        "metric_name": "卸车及时率",
                        "id": row["trip_id"],
                        "status": "卸车超时",
                        "reason": f"到车后 {min_from_arr:.1f}min 且班次开始后 {((first_scan - shift_start).total_seconds() / 60.0) if not pd.isna(shift_start) else 'N/A'}min 卸车，超时",
                        "details": f"到达: {actual_arr}, 第一枪: {first_scan}"
                    })
                    
            rate = punctual_count / total_valid if total_valid > 0 else 1.0
            metrics_results["卸车及时率"] = {
                "rate": rate,
                "status": "正常" if rate >= METRICS_RED_LINE["卸车及时率"] else "异常"
            }

    # 返回给 Agent 的结构化大盘快照
    processed_metrics = {
        "metrics": metrics_results,
        "exceptions": exceptions,
        "total_rows_extracted": raw_data.get("_total_rows", 0),
        "raw_data_sample": raw_data.get("_raw_sample", [])
    }
    return json.dumps(processed_metrics, ensure_ascii=False)
