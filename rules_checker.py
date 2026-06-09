"""
物流调度部 AI 考核报告与飞书融合分发系统 - 规则校验拦截层
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
import rules_config


class RulesChecker:
    """
    数据校验与拦截层：比对原始数据，计算指标数值，标记不符合规则的异常。
    """
    
    def __init__(self, raw_data: Dict[str, List[Dict[str, Any]]]):
        self.raw_data = raw_data
        self.metrics_results: Dict[str, Dict[str, Any]] = {}
        self.exceptions: List[Dict[str, Any]] = []

    def check_all_metrics(self) -> Dict[str, Any]:
        """
        运行所有指标校验
        """
        self._check_dispatch_punctuality()
        self._check_route_load_rate()
        self._check_duration_qualification()
        self._check_arrival_punctuality()
        self._check_overtime_percentage()
        self._check_shift_dispatch_timeliness()
        self._check_tms_operation_rate()
        self._check_unloading_timeliness()
        
        return {
            "metrics": self.metrics_results,
            "exceptions": self.exceptions
        }

    def _check_dispatch_punctuality(self):
        """
        校验发车准点率 (指标 1)
        """
        records = self.raw_data.get("dispatch_punctuality", [])
        if not records:
            return
            
        total_valid = 0
        punctual_count = 0
        
        for r in records:
            res = rules_config.evaluate_dispatch_punctuality(
                planned_departure=r["planned_departure"],
                actual_departure=r.get("actual_departure"),
                actual_arrival_next_station=r.get("actual_arrival_next_station"),
                upstream_actual_arrival=r.get("upstream_actual_arrival"),
                hub_operation_minutes=r.get("hub_operation_minutes", 0),
                shift_start=r.get("shift_start"),
                shift_end=r.get("shift_end"),
                is_from_site=r.get("is_from_site", False)
            )
            
            if res["status"] == "剔除":
                continue
                
            total_valid += 1
            if res["status"] == "准点":
                punctual_count += 1
            else:
                self.exceptions.append({
                    "metric_name": "发车准点率",
                    "id": r["trip_id"],
                    "status": res["status"],
                    "reason": res["reason"],
                    "details": f"计划发车: {r['planned_departure']}, 实际发车: {r.get('actual_departure')}"
                })
                
        rate = punctual_count / total_valid if total_valid > 0 else 1.0
        red_line = rules_config.METRICS_CONFIG.get("发车准点率", {}).get("red_line", 0.95)
        self.metrics_results["发车准点率"] = {
            "rate": rate,
            "total_valid": total_valid,
            "punctual_count": punctual_count,
            "status": "正常" if rate >= red_line else "异常"
        }

    def _check_route_load_rate(self):
        """
        校验线路装载率 (指标 2)
        """
        records = self.raw_data.get("route_load_rate", [])
        if not records:
            return
            
        total_weighted_load_rate = 0.0
        total_miles = 0.0
        
        for r in records:
            load_rate = rules_config.calculate_route_comprehensive_load_rate(
                legs_data=r["legs"],
                vehicle_type=r["vehicle_type"]
            )
            if load_rate is None:
                continue
                
            miles = sum(leg["miles"] for leg in r["legs"])
            total_weighted_load_rate += load_rate * miles
            total_miles += miles
            
            # 如果某条线总体装载率太低（比如低于50%），计入异常报警
            if load_rate < 0.50:
                self.exceptions.append({
                    "metric_name": "线路装载率",
                    "id": r["trip_id"],
                    "status": "装载不足",
                    "reason": f"车型 {r['vehicle_type']} 综合装载率 {load_rate*100:.1f}% 低于 50% 阈值",
                    "details": f"腿数据: {r['legs']}"
                })
                
        overall_rate = total_weighted_load_rate / total_miles if total_miles > 0 else 0.0
        self.metrics_results["线路装载率"] = {
            "rate": overall_rate,
            "status": "正常"  # 通晒指标，仅做展示
        }

    def _check_duration_qualification(self):
        """
        校验运行合格率 (指标 3)
        """
        records = self.raw_data.get("duration_qualification", [])
        if not records:
            return
            
        total_valid = 0
        qualified_count = 0
        
        for r in records:
            res = rules_config.evaluate_duration_qualification(
                planned_duration_hours=r["planned_duration_hours"],
                actual_duration_hours=r.get("actual_duration_hours"),
                actual_arrival=r.get("actual_arrival")
            )
            
            if res["status"] == "剔除":
                continue
                
            total_valid += 1
            if res["status"] == "合格":
                qualified_count += 1
            else:
                self.exceptions.append({
                    "metric_name": "运行合格率",
                    "id": r["trip_id"],
                    "status": "不合格",
                    "reason": res["reason"],
                    "details": f"计划运行时长: {r['planned_duration_hours']}h, 实际运行时长: {r.get('actual_duration_hours')}h"
                })
                
        rate = qualified_count / total_valid if total_valid > 0 else 1.0
        self.metrics_results["运行合格率"] = {
            "rate": rate,
            "total_valid": total_valid,
            "qualified_count": qualified_count,
            "status": "正常"  # 通晒指标
        }

    def _check_arrival_punctuality(self):
        """
        校验到达准点率 (指标 4)
        """
        records = self.raw_data.get("arrival_punctuality", [])
        if not records:
            return
            
        total_valid = 0
        punctual_count = 0
        
        for r in records:
            res = rules_config.evaluate_arrival_punctuality(
                planned_arrival=r["planned_arrival"],
                actual_arrival=r.get("actual_arrival"),
                prev_station_departure=r.get("prev_station_departure")
            )
            
            if res["status"] == "剔除":
                continue
                
            total_valid += 1
            if res["status"] == "准点":
                punctual_count += 1
            else:
                self.exceptions.append({
                    "metric_name": "到达准点率",
                    "id": r["trip_id"],
                    "status": "晚点",
                    "reason": res["reason"],
                    "details": f"计划到达: {r['planned_arrival']}, 实际到达: {r.get('actual_arrival')}"
                })
                
        rate = punctual_count / total_valid if total_valid > 0 else 1.0
        self.metrics_results["到达准点率"] = {
            "rate": rate,
            "total_valid": total_valid,
            "punctual_count": punctual_count,
            "status": "正常"
        }

    def _check_overtime_percentage(self):
        """
        校验加班占比 (指标 5)
        """
        records = self.raw_data.get("overtime_percentage", [])
        if not records:
            return
            
        total_trips = 0
        overtime_trips = 0
        
        for r in records:
            if not r.get("is_origin", False):
                continue  # 仅统计本站始发的任务
            total_trips += 1
            if r.get("is_overtime", False):
                overtime_trips += 1
                
        rate = overtime_trips / total_trips if total_trips > 0 else 0.0
        self.metrics_results["加班占比"] = {
            "rate": rate,
            "total_trips": total_trips,
            "overtime_trips": overtime_trips,
            "status": "正常"
        }

    def _check_shift_dispatch_timeliness(self):
        """
        校验班次发货及时率 (指标 6)
        """
        records = self.raw_data.get("shift_dispatch_timeliness", [])
        if not records:
            return
            
        total_signed_in = 0
        on_time_dispatched = 0
        
        for r in records:
            dt = r["date"]
            if not rules_config.is_weekday(dt):
                continue  # 仅统计周一至周五
            if not r.get("is_mainline_leg", False):
                continue  # 仅限干线发货件量 (非本区件量)
                
            total_signed_in += r["signed_in_qty"]
            on_time_dispatched += r["on_time_dispatched_qty"]
            
            # 计算单班次发货及时率，如果过低则触发异常
            shift_rate = r["on_time_dispatched_qty"] / r["signed_in_qty"] if r["signed_in_qty"] > 0 else 1.0
            shift_red_line = rules_config.METRICS_CONFIG.get("班次发货及时率", {}).get("red_line", 0.95)
            if shift_rate < shift_red_line:
                self.exceptions.append({
                    "metric_name": "班次发货及时率",
                    "id": r["shift_id"],
                    "status": "发货不及时",
                    "reason": f"班次发货率 {shift_rate*100:.1f}% 低于红线",
                    "details": f"签入件数: {r['signed_in_qty']}, 准时发出件数: {r['on_time_dispatched_qty']}"
                })
                
        rate = on_time_dispatched / total_signed_in if total_signed_in > 0 else 1.0
        red_line = rules_config.METRICS_CONFIG.get("班次发货及时率", {}).get("red_line", 0.95)
        self.metrics_results["班次发货及时率"] = {
            "rate": rate,
            "total_signed_in": total_signed_in,
            "on_time_dispatched": on_time_dispatched,
            "status": "正常" if rate >= red_line else "异常"
        }

    def _check_tms_operation_rate(self):
        """
        校验 TMS 操作率 (指标 7)
        """
        records = self.raw_data.get("tms_operation_rate", [])
        if not records:
            return
            
        total_expected = 0
        total_actual = 0
        
        for r in records:
            # 免除与剔除判定:
            # 1. 始发地为站点的，不用做签入签出 (免签)。
            # 2. JFK不需要签出 (免签)。
            # 3. JFK-EWR清关行提货场景，予以剔除。
            # 4. 目的地为ground的，始发地不用签入 (免签)。
            if r.get("is_jfk_ewr_customs_clearance", False):
                continue  # JFK-EWR 清关行提货，直接剔除
                
            actual_ops = r.get("actual_operations", 0)
            expected_ops = r.get("expected_operations", 4)  # 默认满载操作为装、发、到、卸(4个)
            
            # 根据特殊规则减少应操作项 (免除操作)
            if r.get("is_origin_site", False):
                # 始发地为站点，免发车+装车 (这里简单减2次应操作)
                expected_ops = max(0, expected_ops - 2)
            elif r.get("is_dest_ground", False):
                # 目的地为 ground，始发地免签入装车操作 (这里减1次)
                expected_ops = max(0, expected_ops - 1)
                
            if r.get("is_jfk", False):
                # JFK免签出 (减1次)
                expected_ops = max(0, expected_ops - 1)
                
            if r.get("is_stopover", False):
                # 经停点免签出 (减1次)
                expected_ops = max(0, expected_ops - 1)
                
            if expected_ops <= 0:
                continue
                
            total_expected += expected_ops
            total_actual += actual_ops
            
            # 单趟车操作率不足
            op_rate = actual_ops / expected_ops
            tms_red_line = rules_config.METRICS_CONFIG.get("TMS操作率", {}).get("red_line", 0.92)
            if op_rate < tms_red_line:
                self.exceptions.append({
                    "metric_name": "TMS操作率",
                    "id": r["trip_id"],
                    "status": "漏操作",
                    "reason": f"操作率 {op_rate*100:.1f}% 低于红线 (应操作: {expected_ops}, 实操作: {actual_ops})",
                    "details": f"规则触发 - JFK: {r.get('is_jfk')}, JFK-EWR: {r.get('is_jfk_ewr_customs_clearance')}, 站点始发: {r.get('is_origin_site')}, 地面目的: {r.get('is_dest_ground')}"
                })
                
        rate = total_actual / total_expected if total_expected > 0 else 1.0
        tms_red_line = rules_config.METRICS_CONFIG.get("TMS操作率", {}).get("red_line", 0.92)
        self.metrics_results["TMS操作率"] = {
            "rate": rate,
            "total_expected": total_expected,
            "total_actual": total_actual,
            "status": "正常" if rate >= tms_red_line else "异常"
        }

    def _check_unloading_timeliness(self):
        """
        校验卸车及时率 (指标 8)
        """
        records = self.raw_data.get("unloading_timeliness", [])
        if not records:
            return
            
        total_valid = 0
        punctual_count = 0
        
        for r in records:
            res = rules_config.evaluate_unloading_punctuality(
                actual_arrival=r.get("actual_arrival"),
                first_unloading_scan=r.get("first_unloading_scan"),
                shift_start=r.get("shift_start"),
                has_inbound_manifest=r.get("has_inbound_manifest", True),
                loaded_bags_qty=r.get("loaded_bags_qty", 1),
                route_name=r.get("route_name")
            )
            
            if res["status"] == "剔除":
                continue
                
            total_valid += 1
            if res["status"] == "准点":
                punctual_count += 1
            elif res["status"] == "定责上游晚点":
                # 定责出发地，在分母中计为异常车辆，本车不扣本站卸车率，但列入定责上游异常列表
                self.exceptions.append({
                    "metric_name": "卸车及时率",
                    "id": r["trip_id"],
                    "status": "定责上游",
                    "reason": res["reason"],
                    "details": f"到车: {r.get('actual_arrival')}, 装车袋数: {r.get('loaded_bags_qty')}"
                })
            else:
                self.exceptions.append({
                    "metric_name": "卸车及时率",
                    "id": r["trip_id"],
                    "status": res["status"],
                    "reason": res["reason"],
                    "details": f"到车: {r.get('actual_arrival')}, 第一枪: {r.get('first_unloading_scan')}"
                })
                
        rate = punctual_count / total_valid if total_valid > 0 else 1.0
        unload_red_line = rules_config.METRICS_CONFIG.get("卸车及时率", {}).get("red_line", 0.95)
        self.metrics_results["卸车及时率"] = {
            "rate": rate,
            "total_valid": total_valid,
            "punctual_count": punctual_count,
            "status": "正常" if rate >= unload_red_line else "异常"
        }
