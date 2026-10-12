"""
Cost Optimization and Energy-Aware Predictive Maintenance Decision Engine
-------------------------------------------------------------------------
Provides:
  1. Configurable Preventive Maintenance & Failure Cost Modeling
  2. 3-Phase Industrial Motor Power & Energy Consumption Modeling
  3. Energy Anomaly Detection relative to baseline
  4. Dynamic Probable Fault Attribution from multi-sensor & frequency data
  5. Configurable RUL-Based Inspection Deadlines
  6. Financial Maintenance Decision Engine (Potential Savings & Critical Safety Override)
  7. Transparent "Why this recommendation?" Attribution
  8. Multi-PLC Priority Ranking (Critical, High, Medium, Low)
"""

import os
import json
import math
import logging
from typing import Dict, List, Tuple, Any, Optional

logger = logging.getLogger("cost_energy_engine")

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "cost_energy_config.json")

class CostEnergyConfig:
    """Configurable parameters for maintenance cost optimization and energy awareness."""
    def __init__(self):
        # Preventive Maintenance Cost components (₹)
        self.labour_cost = 2500.0
        self.spare_parts_cost = 3500.0
        self.inspection_cost = 1200.0
        self.service_cost = 800.0
        self.other_expenses = 0.0

        # Failure Impact components (₹)
        self.repair_replacement_cost = 14000.0
        self.downtime_cost = 8000.0
        self.production_loss = 5000.0
        self.emergency_labour_cost = 4000.0

        # Electrical / Energy parameters
        self.electricity_rate = 8.0          # ₹ / kWh
        self.nominal_voltage = 415.0         # Volts (3-Phase AC motor line-to-line standard)
        self.power_factor = 0.85            # Typical inductive motor power factor (cos phi)
        self.operating_hours_per_day = 24.0 # Hours/day

        # RUL Thresholds (Days)
        self.rul_critical_days = 3.0   # < 3 days -> Critical
        self.rul_urgent_days = 7.0     # 3 - 6 days -> Inspect urgently
        self.rul_schedule_days = 15.0  # 7 - 14 days -> Schedule maintenance soon
        self.rul_plan_days = 30.0      # 15 - 30 days -> Plan maintenance
                                       # > 30 days -> Monitor normally

    def get_preventive_cost(self) -> float:
        """Preventive Maintenance Cost = Labour + Spare Parts + Inspection + Service + Other"""
        return round(self.labour_cost + self.spare_parts_cost + self.inspection_cost + self.service_cost + self.other_expenses, 2)

    def get_failure_impact(self) -> float:
        """Failure Impact = Repair/Replacement + Downtime + Production Loss + Emergency Labour"""
        return round(self.repair_replacement_cost + self.downtime_cost + self.production_loss + self.emergency_labour_cost, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "labour_cost": self.labour_cost,
            "spare_parts_cost": self.spare_parts_cost,
            "inspection_cost": self.inspection_cost,
            "service_cost": self.service_cost,
            "other_expenses": self.other_expenses,
            "preventive_cost_total": self.get_preventive_cost(),
            "repair_replacement_cost": self.repair_replacement_cost,
            "downtime_cost": self.downtime_cost,
            "production_loss": self.production_loss,
            "emergency_labour_cost": self.emergency_labour_cost,
            "failure_impact_total": self.get_failure_impact(),
            "electricity_rate": self.electricity_rate,
            "nominal_voltage": self.nominal_voltage,
            "power_factor": self.power_factor,
            "operating_hours_per_day": self.operating_hours_per_day,
            "rul_critical_days": self.rul_critical_days,
            "rul_urgent_days": self.rul_urgent_days,
            "rul_schedule_days": self.rul_schedule_days,
            "rul_plan_days": self.rul_plan_days,
        }

    def update(self, data: Dict[str, Any]):
        for key in [
            "labour_cost", "spare_parts_cost", "inspection_cost", "service_cost", "other_expenses",
            "repair_replacement_cost", "downtime_cost", "production_loss", "emergency_labour_cost",
            "electricity_rate", "nominal_voltage", "power_factor", "operating_hours_per_day",
            "rul_critical_days", "rul_urgent_days", "rul_schedule_days", "rul_plan_days"
        ]:
            if key in data and data[key] is not None:
                try:
                    setattr(self, key, max(0.0, float(data[key])))
                except (ValueError, TypeError):
                    pass

    def save_to_file(self, filepath: str = CONFIG_FILE_PATH):
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist config to file: {e}")

    def load_from_file(self, filepath: str = CONFIG_FILE_PATH):
        try:
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    data = json.load(f)
                    self.update(data)
        except Exception as e:
            logger.warning(f"Could not load config from file: {e}")


# Global singleton configuration
cost_energy_config = CostEnergyConfig()
cost_energy_config.load_from_file()


def calculate_energy_consumption(
    motor_current: float,
    plc_id_num: int = 1,
    config: CostEnergyConfig = cost_energy_config
) -> Dict[str, Any]:
    """
    Computes 3-Phase Industrial Motor Power (kW) and Daily Energy Consumption (kWh/day).
    Formula:
      Power (kW) = sqrt(3) * V_nominal * Current * Power_Factor / 1000
      Daily Energy (kWh/day) = Power (kW) * Operating_Hours_Per_Day
    Detects abnormal energy relative to healthy baseline.
    """
    curr = max(0.1, float(motor_current))
    v_nom = float(config.nominal_voltage)
    pf = float(config.power_factor)
    hours = float(config.operating_hours_per_day)
    rate = float(config.electricity_rate)

    # Calculate actual instantaneous 3-phase electrical power
    power_kw = (math.sqrt(3) * v_nom * curr * pf) / 1000.0
    energy_kwh_day = power_kw * hours

    # Baseline for this PLC (healthy baseline current is ~7.5 + 0.3 * plc_id_num)
    baseline_current = 7.5 + (0.3 * (plc_id_num % 10))
    baseline_power_kw = (math.sqrt(3) * v_nom * baseline_current * pf) / 1000.0
    baseline_energy_kwh_day = baseline_power_kw * hours

    excess_energy_kwh_day = max(0.0, energy_kwh_day - baseline_energy_kwh_day)
    excess_pct = round(((energy_kwh_day - baseline_energy_kwh_day) / baseline_energy_kwh_day) * 100.0, 1)

    additional_energy_cost_day = round(excess_energy_kwh_day * rate, 2)

    return {
        "motor_current_a": round(curr, 2),
        "nominal_voltage_v": v_nom,
        "power_factor": pf,
        "power_kw": round(power_kw, 2),
        "energy_kwh_day": round(energy_kwh_day, 1),
        "baseline_energy_kwh_day": round(baseline_energy_kwh_day, 1),
        "excess_energy_kwh_day": round(excess_energy_kwh_day, 1),
        "excess_pct": excess_pct,
        "electricity_rate": rate,
        "additional_energy_cost_day": additional_energy_cost_day,
        "energy_cost_monthly": round(additional_energy_cost_day * 30.0, 0)
    }


def detect_energy_anomaly(
    energy_data: Dict[str, Any],
    vibration: float,
    motor_current: float,
    is_anomaly: bool,
    plc_str: str = "PLC_01"
) -> Dict[str, Any]:
    """
    Evaluates energy behaviour in context with vibration and machine health.
    Avoids labeling high energy alone as a fault; checks mechanical/thermal context.
    """
    excess_pct = energy_data.get("excess_pct", 0.0)
    add_cost = energy_data.get("additional_energy_cost_day", 0.0)
    vib = float(vibration)
    curr = float(motor_current)

    is_vib_high = vib > 0.40
    is_vib_severe = vib > 0.80

    if excess_pct <= 5.0 and not is_vib_high:
        energy_status = "Normal"
        status_color = "#16A34A" # Green
        summary = f"{plc_str}: Energy consumption is within normal operating range."
    elif excess_pct > 20.0 or (excess_pct > 12.0 and is_vib_severe):
        energy_status = "Critical Inefficiency"
        status_color = "#DC2626" # Red
        summary = f"{plc_str}: High energy consumption (+{excess_pct}%) and abnormal vibration detected. Possible motor/bearing issue. Inspect immediately."
    elif excess_pct > 8.0 and (is_vib_high or is_anomaly):
        energy_status = "Maintenance-Related Anomaly"
        status_color = "#D97706" # Amber / Orange
        summary = f"{plc_str}: Energy consumption is {excess_pct}% above baseline and vibration is increasing. Possible mechanical degradation. Maintenance recommended."
    elif excess_pct > 6.0:
        energy_status = "Warning"
        status_color = "#F59E0B" # Yellow
        summary = f"{plc_str}: Energy consumption is approximately {excess_pct}% above its normal baseline. Monitor motor efficiency."
    else:
        energy_status = "Normal"
        status_color = "#16A34A"
        summary = f"{plc_str}: Energy consumption is within normal operating range."

    cost_summary = f"{plc_str} is consuming approximately ₹{add_cost:,.0f}/day more than its normal baseline." if add_cost > 10 else f"{plc_str} energy cost is at baseline."

    return {
        "energy_status": energy_status,
        "status_color": status_color,
        "energy_summary": summary,
        "cost_summary": cost_summary,
        "is_energy_anomaly": energy_status in ["Maintenance-Related Anomaly", "Critical Inefficiency"]
    }


def derive_probable_issue(
    temperature: float,
    vibration: float,
    motor_current: float,
    pressure: float,
    noise: float,
    health: float,
    is_anomaly: bool,
    plc_desc: str = ""
) -> Tuple[str, str]:
    """
    Derives the probable mechanical/electrical problem whenever sensor deviations support it.
    If no definitive component can be confirmed, uses safe wording.
    Returns: (probable_issue, detail_reason)
    """
    t = float(temperature)
    v = float(vibration)
    c = float(motor_current)
    p = float(pressure)
    n = float(noise)
    h = float(health)

    # Primary diagnostic thresholds
    vib_high = v > 0.45
    vib_severe = v > 0.85
    curr_high = c > 10.5
    curr_severe = c > 14.0
    temp_high = t > 72.0
    temp_severe = t > 85.0
    press_low = p < 4.2
    press_high = p > 6.2
    noise_high = n > 55.0

    # Specific diagnosis based on multi-sensor patterns
    if vib_severe or (vib_high and noise_high):
        if curr_high:
            return "Bearing likely wearing out", f"Excessive vibration ({v:.2f} mm/s) accompanied by acoustic noise ({n:.1f} dB) and elevated motor current indicates mechanical bearing raceway wear."
        else:
            return "Possible bearing imbalance", f"Elevated vibration oscillation ({v:.2f} mm/s) indicates rotating bearing imbalance or looseness."
    elif curr_high or curr_severe:
        if temp_high:
            return "Possible motor overload", f"Motor current is increasing abnormally ({c:.1f} A) with stator temperature ({t:.1f}°C), indicating heavy mechanical resistance or electrical overload."
        else:
            return "Motor current increasing abnormally", f"Phase current ({c:.1f} A) is drawn above nominal rating. Check mechanical load and phase balance."
    elif press_low or press_high:
        reason = "pressure loss/leakage" if press_low else "system flow restriction or line blockage"
        return "Pressure abnormality detected", f"Pressure reading ({p:.1f} bar) indicates potential {reason} in the intake/discharge circuit."
    elif temp_severe or temp_high:
        return "Elevated thermal stress", f"Operating temperature ({t:.1f}°C) is above normal threshold. Check cooling circuit and ventilation."
    elif vib_high:
        return "Abnormal vibration pattern detected", f"Vibration amplitude ({v:.2f} mm/s) is elevated above baseline. Further inspection recommended."
    elif is_anomaly or h < 75.0:
        return "Operational parameter deviation", f"Machine health ({h:.1f}%) and multi-sensor correlation indicate slight degradation. Monitoring recommended."
    else:
        return "Normal operating condition", "All monitored telemetry parameters are within rated baseline limits."


def compute_rul_maintenance_deadline(
    rul_days: int,
    config: CostEnergyConfig = cost_energy_config
) -> Dict[str, Any]:
    """
    Converts RUL prediction into easy-to-understand timeframe and recommended inspection deadline.
    Configurable thresholds:
      - RUL > 30 days -> Monitor normally
      - RUL 15–30 days -> Plan maintenance
      - RUL 7–14 days -> Schedule maintenance soon
      - RUL 3–6 days -> Inspect urgently
      - RUL < 3 days -> Critical — immediate maintenance recommended
    """
    r = max(0, int(rul_days))

    # Human-readable predicted failure time
    if r >= 28:
        weeks = max(1, round(r / 7.0))
        predicted_time_str = f"About {weeks} weeks left before failure"
        time_short = f"~{weeks} weeks"
    elif r >= 7:
        predicted_time_str = f"About {r} days of useful operation remain"
        time_short = f"~{r} days"
    elif r > 0:
        predicted_time_str = f"Critical: Approximately {r} days remaining"
        time_short = f"{r} days"
    else:
        predicted_time_str = "Immediate failure predicted (0 days remaining)"
        time_short = "0 days"

    # Action deadline & RUL category based on configurable thresholds
    if r < config.rul_critical_days:
        rul_category = "Critical — immediate maintenance recommended"
        recommended_deadline_str = "Inspect immediately within 24 hours"
        action_short = "Immediate inspection"
        urgency = "Critical"
    elif r < config.rul_urgent_days:
        rul_category = "Inspect urgently"
        safe_window = max(1, r // 2)
        recommended_deadline_str = f"Inspect urgently within {safe_window} days"
        action_short = f"Inspect within {safe_window} days"
        urgency = "Urgent"
    elif r < config.rul_schedule_days:
        rul_category = "Schedule maintenance soon"
        safe_window = max(3, r // 2)
        recommended_deadline_str = f"Schedule inspection within {safe_window} days"
        action_short = f"Schedule within {safe_window} days"
        urgency = "High"
    elif r <= config.rul_plan_days:
        rul_category = "Plan maintenance"
        safe_window = max(7, r // 2)
        recommended_deadline_str = f"Plan maintenance within {safe_window} days"
        action_short = f"Check within {safe_window} days"
        urgency = "Medium"
    else:
        rul_category = "Monitor normally"
        recommended_deadline_str = "Continue routine monitoring (check in 30–60 days)"
        action_short = "Routine monitoring"
        urgency = "Low"

    return {
        "predicted_rul_days": r,
        "predicted_time_str": predicted_time_str,
        "time_short": time_short,
        "recommended_deadline_str": recommended_deadline_str,
        "action_short": action_short,
        "rul_category": rul_category,
        "urgency": urgency
    }


def evaluate_maintenance_cost_optimization(
    failure_risk_pct: float,
    predicted_rul_days: int,
    machine_health: float,
    energy_data: Dict[str, Any],
    config: CostEnergyConfig = cost_energy_config
) -> Dict[str, Any]:
    """
    Computes financial optimization:
      Preventive Cost = Labour + Spare Parts + Inspection + Service + Other
      Expected Failure Cost = Failure Probability * Failure Impact
      Potential Savings = Expected Failure Cost - Preventive Maintenance Cost
    Applies Critical Safety Override when risk or RUL breaches threshold.
    """
    preventive_cost = config.get_preventive_cost()
    failure_impact = config.get_failure_impact()

    # Dynamic failure probability (0.0 to 1.0)
    risk_factor = max(0.0, min(100.0, float(failure_risk_pct))) / 100.0
    expected_failure_cost = round(risk_factor * failure_impact, 2)
    potential_savings = round(expected_failure_cost - preventive_cost, 2)

    # Energy savings component (if repaired, excess daily energy loss ceases)
    add_energy_cost_day = energy_data.get("additional_energy_cost_day", 0.0)
    monthly_energy_saving = round(add_energy_cost_day * 30.0, 2)

    is_critical_risk = (
        machine_health <= 25.0 or
        predicted_rul_days < config.rul_critical_days or
        failure_risk_pct >= 75.0
    )

    # Decision logic
    if is_critical_risk:
        decision = "Maintain immediately"
        financial_recommendation = f"Critical risk override: Maintain immediately to prevent catastrophic outage. Estimated saving: ₹{potential_savings:,.0f}."
        cost_benefit_status = "Critical Risk Override"
    elif potential_savings > 0:
        decision = "Schedule preventive maintenance"
        financial_recommendation = f"Preventive maintenance recommended — estimated saving ₹{potential_savings:,.0f}."
        cost_benefit_status = "Cost-Effective"
    else:
        decision = "Continue monitoring"
        financial_recommendation = "Continue monitoring — immediate preventive maintenance is not currently cost-effective."
        cost_benefit_status = "Monitoring Favorable"

    return {
        "preventive_cost": preventive_cost,
        "failure_impact": failure_impact,
        "failure_probability_pct": round(risk_factor * 100.0, 1),
        "expected_failure_cost": expected_failure_cost,
        "potential_savings": potential_savings,
        "monthly_energy_saving": monthly_energy_saving,
        "decision": decision,
        "financial_recommendation": financial_recommendation,
        "cost_benefit_status": cost_benefit_status,
        "is_critical_override": is_critical_risk
    }


def generate_total_maintenance_decision(
    plc_id: str,
    plc_id_num: int,
    sensor_readings: Dict[str, float],
    machine_health: float,
    machine_status: str,
    failure_risk_pct: float,
    predicted_rul_days: int,
    is_anomaly: bool,
    config: CostEnergyConfig = cost_energy_config
) -> Dict[str, Any]:
    """
    Generates the Total Combined Predictive Maintenance & Energy Decision.
    Answers:
      1. What is wrong with the machine?
      2. When should I maintain it?
      3. Why should I maintain it now?
    Provides concise alert and detailed explanation.
    """
    temp = sensor_readings.get("temperature", 60.0)
    vib = sensor_readings.get("vibration", 0.20)
    curr = sensor_readings.get("motor_current", 8.0)
    press = sensor_readings.get("pressure", 5.0)
    noise = sensor_readings.get("noise", 41.0)

    # 1. Energy Calculation & Anomaly Detection
    energy_data = calculate_energy_consumption(curr, plc_id_num=plc_id_num, config=config)
    energy_anomaly = detect_energy_anomaly(energy_data, vib, curr, is_anomaly, plc_str=plc_id)

    # 2. Probable Issue Derivation
    main_issue, issue_detail = derive_probable_issue(temp, vib, curr, press, noise, machine_health, is_anomaly)

    # 3. RUL Deadline & Format
    rul_info = compute_rul_maintenance_deadline(predicted_rul_days, config=config)

    # 4. Cost Optimization & Decision
    cost_info = evaluate_maintenance_cost_optimization(failure_risk_pct, predicted_rul_days, machine_health, energy_data, config=config)

    # 5. The Three Core Answers
    q1_what_is_wrong = main_issue
    q2_when_maintain = f"{rul_info['predicted_time_str']}. {rul_info['recommended_deadline_str']}."

    savings_val = cost_info['potential_savings']
    add_energy_val = energy_data['additional_energy_cost_day']
    if savings_val > 0:
        q3_why_now = (
            f"Preventive maintenance costs ₹{cost_info['preventive_cost']:,.0f}, while expected failure cost is "
            f"₹{cost_info['expected_failure_cost']:,.0f}, giving an estimated saving of ₹{savings_val:,.0f}"
            + (f", plus ~₹{add_energy_val:,.0f}/day reduced energy loss." if add_energy_val > 5 else ".")
        )
    elif cost_info['is_critical_override']:
        q3_why_now = (
            f"Critical machine condition ({machine_health:.0f}% health, {predicted_rul_days}d RUL) requires immediate intervention "
            f"to prevent catastrophic downtime (impact: ₹{cost_info['failure_impact']:,.0f})."
        )
    else:
        q3_why_now = (
            f"Current failure risk ({failure_risk_pct:.1f}%) is low; expected failure cost (₹{cost_info['expected_failure_cost']:,.0f}) "
            f"is below preventive overhaul cost (₹{cost_info['preventive_cost']:,.0f}). Continued monitoring preserves capital."
        )

    # 6. Concise Human-Readable Alert Format
    # Priority Symbol
    priority_level = "Low"
    priority_symbol = "🟢"
    if cost_info['is_critical_override'] or machine_status == "Critical" or predicted_rul_days <= 3:
        priority_level = "Critical"
        priority_symbol = "🔴"
    elif failure_risk_pct >= 45.0 or predicted_rul_days <= 14 or energy_anomaly['is_energy_anomaly']:
        priority_level = "High"
        priority_symbol = "🟠"
    elif failure_risk_pct >= 25.0 or predicted_rul_days <= 30:
        priority_level = "Medium"
        priority_symbol = "🟡"

    concise_alert = {
        "title": f"{priority_symbol} {plc_id} — {main_issue}",
        "rul_text": rul_info['time_short'],
        "action_text": rul_info['action_short'],
        "energy_text": f"+{energy_data['excess_pct']}% above baseline" if energy_data['excess_pct'] > 0 else "Normal baseline",
        "savings_text": f"₹{savings_val:,.0f}" if savings_val > 0 else "₹0 (Monitor)",
        "recommendation": cost_info['decision'],
        "priority": priority_level,
        "symbol": priority_symbol
    }

    # 7. Model / Calculation Transparency ("Why this recommendation?")
    transparency_points = []
    baseline_temp = 60.0 + (plc_id_num * 1.8)
    baseline_vib = 0.20 + (plc_id_num * 0.08)
    baseline_curr = 7.5 + (plc_id_num * 0.4)

    vib_diff_pct = round(((vib - baseline_vib) / baseline_vib) * 100.0) if baseline_vib > 0 else 0
    curr_diff_pct = round(((curr - baseline_curr) / baseline_curr) * 100.0) if baseline_curr > 0 else 0

    if abs(vib_diff_pct) > 5:
        transparency_points.append(f"Vibration is {vib:.2f} mm/s ({'+' if vib_diff_pct > 0 else ''}{vib_diff_pct}% relative to baseline)")
    else:
        transparency_points.append(f"Vibration is stable at {vib:.2f} mm/s (within normal limits)")

    if abs(curr_diff_pct) > 5:
        transparency_points.append(f"Motor current is {curr:.1f} A ({'+' if curr_diff_pct > 0 else ''}{curr_diff_pct}% relative to baseline)")
    else:
        transparency_points.append(f"Motor current is {curr:.1f} A (normal operating load)")

    if energy_data['excess_pct'] > 3.0:
        transparency_points.append(f"Energy consumption is {energy_data['excess_pct']}% above baseline (₹{add_energy_val:,.0f}/day excess energy cost)")
    else:
        transparency_points.append("Energy consumption is optimal (within normal operating band)")

    transparency_points.append(f"Failure probability is evaluated at {failure_risk_pct:.1f}%")
    transparency_points.append(f"Predicted Remaining Useful Life is {predicted_rul_days} days")

    if cost_info['potential_savings'] > 0:
        transparency_points.append(f"Expected failure cost (₹{cost_info['expected_failure_cost']:,.0f}) exceeds preventive cost (₹{cost_info['preventive_cost']:,.0f})")
    elif cost_info['is_critical_override']:
        transparency_points.append(f"Critical health index ({machine_health:.1f}%) overrides financial deferral")
    else:
        transparency_points.append(f"Immediate maintenance is not currently cost-effective (deferral saves capital)")

    return {
        "plc_id": plc_id,
        "plc_id_num": plc_id_num,
        "machine_health": round(machine_health, 1),
        "machine_status": machine_status,
        "failure_risk_pct": round(failure_risk_pct, 1),
        "predicted_rul_days": predicted_rul_days,
        "is_anomaly": is_anomaly,

        # The Three Core Questions
        "q1_what_is_wrong": q1_what_is_wrong,
        "q2_when_maintain": q2_when_maintain,
        "q3_why_now": q3_why_now,

        # Modules
        "energy": energy_data,
        "energy_anomaly": energy_anomaly,
        "rul_recommendation": rul_info,
        "cost_optimization": cost_info,
        "concise_alert": concise_alert,
        "transparency_points": transparency_points,
        "main_issue": main_issue,
        "issue_detail": issue_detail,
        "priority": priority_level
    }
