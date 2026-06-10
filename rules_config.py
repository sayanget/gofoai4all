"""
物流调度部 AI 考核报告与飞书融合分发系统 - 静态规则库 (Static Ruleset)
版本: V1.0 (2026-06)
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List


import os
import json

# ==============================================================================
# 1. 动态加载配置文件 (Load from config/rules.json)
# ==============================================================================
VEHICLE_CAPACITY: Dict[str, int] = {}
METRICS_CONFIG: Dict[str, Dict[str, Any]] = {}

config_path = os.path.join(os.path.dirname(__file__), "config", "rules.json")
try:
    with open(config_path, "r", encoding="utf-8") as f:
        _rules_data = json.load(f)
        VEHICLE_CAPACITY = _rules_data.get("vehicle_capacity", {})
        _categories = _rules_data.get("categories", {})
        METRICS_CONFIG = {}
        for cat_data in _categories.values():
            if "metrics" in cat_data:
                METRICS_CONFIG.update(cat_data["metrics"])
except Exception as e:
    print(f"Error loading rules.json: {e}")

# ==============================================================================
# 3. 判定逻辑与规则引擎实现 (Rules Engine)
# ==============================================================================

def evaluate_dispatch_punctuality(
    planned_departure: datetime,
    actual_departure: Optional[datetime],
    actual_arrival_next_station: Optional[datetime],
    upstream_actual_arrival: Optional[datetime] = None,
    hub_operation_minutes: int = 0,
    shift_start: Optional[datetime] = None,
    shift_end: Optional[datetime] = None,
    is_from_site: bool = False
) -> Dict[str, Any]:
    """
    指标 1：发车准点率判定逻辑 (含串点线路加时修正)
    
    返回字典:
        {
            "status": "准点" | "晚点" | "剔除" | "已到站未发车",
            "adjusted_planned_departure": datetime,
            "reason": str
        }
    """
    # 剔除情况：本站实际发车时间、下一站实际到车时间均为空的，剔除
    if actual_departure is None and actual_arrival_next_station is None:
        return {
            "status": "剔除",
            "adjusted_planned_departure": planned_departure,
            "reason": "本站实际发车时间与下一站实际到车时间均为空"
        }

    # 串点线路加时修正：上游发车线路有晚到情况的，进行分情况加时
    adjusted_planned = planned_departure
    is_adjusted = False
    adjustment_reason = ""
    
    if upstream_actual_arrival and upstream_actual_arrival > planned_departure:
        # 确定是否在班次内 (上游到达时间在班次内)
        in_shift = False
        if shift_start and shift_end:
            in_shift = (shift_start <= upstream_actual_arrival <= shift_end)
            
        if in_shift or is_from_site:
            # ①如果在班次内，或者出发地是站点
            # 本段实际计划发车时间 = MAX{上游实际到达时间 + HUB班次操作时间, 原计划发车时间}
            potential_planned = upstream_actual_arrival + timedelta(minutes=hub_operation_minutes)
            if potential_planned > planned_departure:
                adjusted_planned = potential_planned
                is_adjusted = True
                adjustment_reason = f"串点线路班次内/站点加时(上游实际到达 {upstream_actual_arrival} + HUB操作时间 {hub_operation_minutes}min)"
        else:
            # ②如果在班次外 (班次结束到下一班班次开始)
            # 本段实际计划发车时间 = MAX{班次开始时间 + HUB班次操作时间, 原计划发车时间}
            if shift_start:
                potential_planned = shift_start + timedelta(minutes=hub_operation_minutes)
                if potential_planned > planned_departure:
                    adjusted_planned = potential_planned
                    is_adjusted = True
                    adjustment_reason = f"串点线路班次外加时(下班次开始 {shift_start} + HUB操作时间 {hub_operation_minutes}min)"

    # 实际发车时间为空，但下一站有实际到车时间
    if actual_departure is None and actual_arrival_next_station is not None:
        return {
            "status": "已到站未发车",  # 在V2中记为已到站未发车，视为晚点统计
            "adjusted_planned_departure": adjusted_planned,
            "reason": f"本站无发车记录，但下一站已到车。{adjustment_reason}".strip()
        }

    # 超过计划发车时间仍未有发车打卡记录的，记为晚点 (没有下一站到车，且实际发车为空)
    # 此处默认若当前时间已超过adjusted_planned，视为晚点
    if actual_departure is None:
        return {
            "status": "晚点",
            "adjusted_planned_departure": adjusted_planned,
            "reason": f"超时未录入发车打卡数据。{adjustment_reason}".strip()
        }

    # 正常判定
    if actual_departure <= adjusted_planned:
        return {
            "status": "准点",
            "adjusted_planned_departure": adjusted_planned,
            "reason": f"实际发车 ({actual_departure}) <= 计划发车 ({adjusted_planned})。" + (" (已加时)" if is_adjusted else "")
        }
    else:
        return {
            "status": "晚点",
            "adjusted_planned_departure": adjusted_planned,
            "reason": f"实际发车 ({actual_departure}) > 计划发车 ({adjusted_planned})。{adjustment_reason}".strip()
        }


def get_vehicle_financial_capacity(vehicle_type: str) -> Optional[int]:
    """
    指标 2：获取车型财务口径额定装载量
    """
    # 模糊匹配或精确匹配
    for name, cap in VEHICLE_CAPACITY.items():
        if name.lower() in vehicle_type.lower() or vehicle_type.lower() in name.lower():
            return cap
    return None


def calculate_leg_load_rate(
    leg_index: int,
    loaded_qty: int,
    unloaded_qty: int,
    prev_remaining_qty: int,
    vehicle_capacity: int
) -> float:
    """
    指标 2：分段装载率计算
    - 第1段装载率: 节点1装货-件 / 车型额定装载量
    - 第2段及后续装载率: [本节点装货-件 + (前序剩余件数 - 前序本站卸货)] / 车型额定装载量
    """
    if vehicle_capacity <= 0:
        return 0.0
        
    if leg_index == 1:
        return loaded_qty / vehicle_capacity
    else:
        # 前序剩余货物 = 上段装载货物 - 上段本站卸货
        current_cargo = loaded_qty + prev_remaining_qty
        return current_cargo / vehicle_capacity


def calculate_route_comprehensive_load_rate(
    legs_data: List[Dict[str, Any]],
    vehicle_type: str
) -> Optional[float]:
    """
    指标 2：综合装载率计算
    legs_data 结构:
        [
            {
                "leg_index": 1, 
                "loaded_qty": 1000, 
                "unloaded_qty": 0, 
                "miles": 50.0
            },
            ...
        ]
    """
    capacity = get_vehicle_financial_capacity(vehicle_type)
    if not capacity:
        return None
        
    total_weighted_load = 0.0
    total_miles = 0.0
    
    prev_remaining = 0
    for leg in legs_data:
        leg_idx = leg["leg_index"]
        loaded = leg["loaded_qty"]
        unloaded = leg["unloaded_qty"]
        miles = leg["miles"]
        
        # 计算该段装载率
        load_rate = calculate_leg_load_rate(leg_idx, loaded, unloaded, prev_remaining, capacity)
        total_weighted_load += load_rate * miles
        total_miles += miles
        
        # 滚动更新前序剩余件数：第一段后，剩余 = 第一段装货 - 第一段卸货
        prev_remaining = (prev_remaining + loaded) - unloaded
        
    if total_miles == 0:
        return 0.0
    return total_weighted_load / total_miles


def evaluate_duration_qualification(
    planned_duration_hours: float,
    actual_duration_hours: Optional[float],
    actual_arrival: Optional[datetime]
) -> Dict[str, Any]:
    """
    指标 3：运行合格率判定
    """
    if actual_duration_hours is None:
        if actual_arrival is not None:
            return {
                "status": "不合格",
                "reason": "实际运行时间为空，但有实际抵达时间，判定为不合格"
            }
        else:
            return {
                "status": "剔除",
                "reason": "实际到发车时间均为空，数据剔除"
            }
            
    if actual_duration_hours <= planned_duration_hours:
        return {
            "status": "合格",
            "reason": f"实际运行时长 ({actual_duration_hours}h) <= 计划运行时长 ({planned_duration_hours}h)"
        }
    else:
        return {
            "status": "不合格",
            "reason": f"实际运行时长 ({actual_duration_hours}h) > 计划运行时长 ({planned_duration_hours}h)"
        }


def evaluate_arrival_punctuality(
    planned_arrival: datetime,
    actual_arrival: Optional[datetime],
    prev_station_departure: Optional[datetime]
) -> Dict[str, Any]:
    """
    指标 4：到达准点率判定
    """
    if actual_arrival is None:
        if prev_station_departure is not None:
            return {
                "status": "晚点",
                "reason": "上一站有发车时间，本站无实际到车时间，判定为晚点"
            }
        else:
            return {
                "status": "剔除",
                "reason": "上一站发车时间为空，本站到车时间为空，剔除"
            }
            
    if actual_arrival <= planned_arrival:
        return {
            "status": "准点",
            "reason": f"实际到车 ({actual_arrival}) <= 计划到车 ({planned_arrival})"
        }
    else:
        return {
            "status": "晚点",
            "reason": f"实际到车 ({actual_arrival}) > 计划到车 ({planned_arrival})"
        }


def is_weekday(dt: datetime) -> bool:
    """
    指标 6：是否为周一至周五
    """
    return dt.weekday() < 5


def evaluate_unloading_punctuality(
    actual_arrival: Optional[datetime],
    first_unloading_scan: Optional[datetime],
    shift_start: Optional[datetime] = None,
    has_inbound_manifest: bool = True,
    loaded_bags_qty: int = 0,
    route_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    指标 8：卸车及时率判定逻辑
    
    返回字典:
        {
            "status": "准点" | "晚点" | "剔除" | "定责上游晚点",
            "reason": str
        }
    """
    # 剔除情况 ④：JFK.H-EWR.H：清关行提货场景（未执行一箱一码），剔除
    if route_name and ("JFK.H-EWR.H" in route_name or "JFK-EWR" in route_name):
        return {
            "status": "剔除",
            "reason": f"由于为清关行提货场景，已剔除该线路 ({route_name})"
        }

    # 剔除情况 ③：已完成装车签出（有运单记录），但未记录实际到车时间，视为未到车，剔除
    if has_inbound_manifest and actual_arrival is None:
        return {
            "status": "剔除",
            "reason": "已完成装车签出(有运单记录)，但未记录实际到车时间，视为未到车，剔除"
        }

    # 判定情况 ②：车辆到达地已记录到车时间，但对应装车袋数为0
    # 视为本站发车未扫袋牌，定责出发地，按上游卸车不及时统计
    if actual_arrival is not None and loaded_bags_qty == 0:
        return {
            "status": "定责上游晚点",
            "reason": "对应装车袋数为0，视为本站发车未扫袋牌，定责出发地，按上游卸车不及时统计"
        }

    # 判定情况 ①：车辆已到达，且有装车签出运单记录，但未记录卸车签入时间
    # 视为漏卸车，记为晚点
    if actual_arrival is not None and has_inbound_manifest and first_unloading_scan is None:
        return {
            "status": "晚点",
            "reason": "车辆已到达且有装车记录，但无卸车签入，视为漏卸车"
        }

    # 判定正常卸车时效
    if actual_arrival and first_unloading_scan:
        # 条件 1：卸车扫描第一枪时间 - 实际抵达目的站时间 < 60min
        minutes_from_arrival = (first_unloading_scan - actual_arrival).total_seconds() / 60.0
        if minutes_from_arrival < 60.0:
            return {
                "status": "准点",
                "reason": f"到车卸车时效符合要求 ({minutes_from_arrival:.1f} min < 60 min)"
            }
            
        # 条件 2：卸车扫描第一枪时间 - 班次开始时间 <= 120min
        if shift_start:
            minutes_from_shift_start = (first_unloading_scan - shift_start).total_seconds() / 60.0
            if minutes_from_shift_start <= 120.0:
                return {
                    "status": "准点",
                    "reason": f"班次开始后时效符合要求 ({minutes_from_shift_start:.1f} min <= 120 min)"
                }
                
        return {
            "status": "晚点",
            "reason": f"卸车超时 (实际到车后 {minutes_from_arrival:.1f} min, 班次开始后 "
                      f"{((first_unloading_scan - shift_start).total_seconds() / 60.0) if shift_start else 'N/A'} min)"
        }

    return {
        "status": "剔除",
        "reason": "数据缺失或不符合统计边界条件"
    }


# ==============================================================================
# 4. HUB发货及时率指标计算逻辑 (HUB Delivery Timeliness Indicator Calculation Logic)
# ==============================================================================

def classify_cargo_type(route_path: List[str], current_hub: str) -> str:
    """
    判断货物类型: 集货 或 散货
    目的HUB为包裹在最终抵达目的站点前，途经的最后一个转运中心。
    - 到达目的HUB之前（不含目的HUB的签入）: 集货
    - 到达目的HUB之后（含目的HUB的签入）: 散货
    """
    # 找出最后一个以 .H 结尾或包含 HUB 的节点作为目的 HUB
    hubs = [node for node in route_path[:-1] if node.endswith(".H") or "hub" in node.lower()]
    if not hubs:
        return "集货"
    dest_hub = hubs[-1]
    
    try:
        current_idx = route_path.index(current_hub)
        dest_idx = route_path.index(dest_hub)
        if current_idx >= dest_idx:
            return "散货"
        else:
            return "集货"
    except ValueError:
        return "集货"


def determine_transfer_style(inbound_dept: str, dest_hub: str, internet_hub: str) -> str:
    """
    签入部门判定规则:
    IF 签入部门 == 目的HUB or 签入部门 == 上网HUB => 件中转
    ELSE => 箱中转
    
    特殊情况: 签入部门 == 目的HUB == 始发HUB => 计入散货班次 (在外部班次分配时处理)
    """
    if inbound_dept == dest_hub or inbound_dept == internet_hub:
        return "件中转"
    return "箱中转"


def calculate_cutoff_time(
    planned_departure: datetime,
    cargo_type: str,
    transfer_style: str,
    piece_transfer_duration_mins: int = 120,
    box_transfer_duration_mins: int = 60
) -> datetime:
    """
    计算运输批次的截单时间:
    - 集货班次:
      - 上网HUB (件中转)：截单时间 = 正班计划发车时间 - 件中转时长
      - 中转HUB (箱中转)：截单时间 = 正班计划发车时间 - 箱中转时长
    - 散货班次:
      - 目的HUB (件中转)：截单时间 = 正班计划发车时间 - 件中转时长
    """
    if cargo_type == "集货":
        if transfer_style == "件中转":
            return planned_departure - timedelta(minutes=piece_transfer_duration_mins)
        else:
            return planned_departure - timedelta(minutes=box_transfer_duration_mins)
    else:  # 散货
        return planned_departure - timedelta(minutes=piece_transfer_duration_mins)


def evaluate_expected_cargo_volume(
    waybill_scan_time: datetime,
    scan_type: str,  # "车辆到达/中心到件" (优先级1) 或 "集包" (优先级2)
    prev_cutoff: datetime,
    current_cutoff: datetime,
    actual_arrival_time: Optional[datetime],
    is_internet_hub: bool,
    is_dest_hub: bool,
    planned_departure: datetime
) -> bool:
    """
    判断运单是否属于本批次的“应发件量”:
    当有到车时间时: 扫描时间在 (上个批次截单时间, 本批次截单时间]
    当没有到车时间时 (仅限上网HUB与目的HUB):
      采用集包时间核算，整体时间窗 (上个批次截单时间, 本次批次截单时间]，
      且整体截止时间往后挪一小时（即相对于计划发车，发车前4小时做集包的，需纳入该批次的应发件量）
    """
    if actual_arrival_time is not None:
        # 有到车时间：扫描时间在批次时间窗内
        return prev_cutoff < waybill_scan_time <= current_cutoff
    else:
        # 没有到车时间，仅限上网HUB与目的HUB
        if is_internet_hub or is_dest_hub:
            # 整体时间窗往后挪一小时 (代表比原发车时间提早1小时，即 cutoff 减去 1小时)
            adjusted_current_cutoff = current_cutoff - timedelta(hours=1)
            adjusted_prev_cutoff = prev_cutoff - timedelta(hours=1)
            if scan_type == "集包":
                return adjusted_prev_cutoff < waybill_scan_time <= adjusted_current_cutoff
        return False


def classify_overdue_duration(
    planned_departure: datetime,
    actual_departure: Optional[datetime]
) -> str:
    """
    逾时件量按延迟时长区间统计:
    - 逾时件量 (2H)：实际发出时间 - 计划发车时间 > 0 且 <= 2小时
    - 逾时件量 (2-6H)：实际发出时间 - 计划发车时间 > 2小时 且 <= 6小时
    - 逾时件量 (6-24H)：实际发出时间 - 计划发车时间 > 6小时 且 <= 24小时
    - 逾时件量 (24H+)：实际发出时间 - 计划发车时间 > 24小时；及部门发车时间为空的件量
    """
    if actual_departure is None:
        return "24H+"
        
    delay_hours = (actual_departure - planned_departure).total_seconds() / 3600.0
    if delay_hours <= 0:
        return "及时"
    elif delay_hours <= 2.0:
        return "2H"
    elif delay_hours <= 6.0:
        return "2-6H"
    elif delay_hours <= 24.0:
        return "6-24H"
    else:
        return "24H+"


def calculate_hub_dispatch_punctuality_metrics(
    departure_batches: List[Dict[str, Any]],
    waybills: List[Dict[str, Any]],
    piece_transfer_duration_mins: int = 120,
    box_transfer_duration_mins: int = 60
) -> Dict[str, Any]:
    """
    根据班次与发车计划，计算流向运输批次的发货统计数据 (应发件量、及时发出量、落货件量、逾时分布)
    """
    sorted_batches = sorted(departure_batches, key=lambda x: x["planned_departure"])
    results = []
    
    for i, batch in enumerate(sorted_batches):
        planned_dep = batch["planned_departure"]
        actual_dep = batch.get("actual_departure")
        cargo_type = batch["cargo_type"]  # "集货" | "散货"
        transfer_style = batch["transfer_style"]  # "件中转" | "箱中转"
        is_internet = batch.get("is_internet_hub", False)
        is_dest = batch.get("is_dest_hub", False)
        actual_arrival = batch.get("actual_arrival_time")
        shift_end = batch.get("shift_end")
        
        # 计算当前截单时间
        cutoff = calculate_cutoff_time(planned_dep, cargo_type, transfer_style, piece_transfer_duration_mins, box_transfer_duration_mins)
        
        # 上一班次最晚截单时间
        if i > 0:
            prev_planned = sorted_batches[i-1]["planned_departure"]
            prev_cargo = sorted_batches[i-1]["cargo_type"]
            prev_style = sorted_batches[i-1]["transfer_style"]
            prev_cutoff = calculate_cutoff_time(prev_planned, prev_cargo, prev_style, piece_transfer_duration_mins, box_transfer_duration_mins)
        else:
            prev_cutoff = cutoff - timedelta(hours=24)
            
        # 筛选本批次的应发件量
        expected_waybills = []
        for wb in waybills:
            scan_time = wb["scan_time"]
            scan_type = wb.get("scan_type", "车辆到达/中心到件")
            
            is_expected = evaluate_expected_cargo_volume(
                waybill_scan_time=scan_time,
                scan_type=scan_type,
                prev_cutoff=prev_cutoff,
                current_cutoff=cutoff,
                actual_arrival_time=actual_arrival,
                is_internet_hub=is_internet,
                is_dest_hub=is_dest,
                planned_departure=planned_dep
            )
            if is_expected:
                expected_waybills.append(wb)
                
        # 统计及时发运和延时
        on_time_shipped_count = 0
        overdue_counts = {"2H": 0, "2-6H": 0, "6-24H": 0, "24H+": 0}
        
        for wb in expected_waybills:
            shipped_time = wb.get("actual_departure_scan")
            if shipped_time is not None and shift_end is not None and shipped_time <= shift_end:
                on_time_shipped_count += 1
            
            delay_cat = classify_overdue_duration(planned_dep, shipped_time)
            if delay_cat in overdue_counts:
                overdue_counts[delay_cat] += 1
                
        expected_qty = len(expected_waybills)
        left_behind_qty = expected_qty - on_time_shipped_count
        punctuality_rate = on_time_shipped_count / expected_qty if expected_qty > 0 else 1.0
        
        results.append({
            "planned_departure": planned_dep,
            "cutoff_time": cutoff,
            "expected_qty": expected_qty,
            "on_time_shipped_qty": on_time_shipped_count,
            "left_behind_qty": left_behind_qty,
            "punctuality_rate": punctuality_rate,
            "overdue_details": overdue_counts
        })
        
    return {
        "batches": results
    }

