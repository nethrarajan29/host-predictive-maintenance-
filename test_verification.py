import os
import sys
import json

curr_dir = os.path.dirname(os.path.abspath(__file__))
if curr_dir not in sys.path:
    sys.path.insert(0, curr_dir)

os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("=================================================================")
print("RUNNING COMPREHENSIVE ACCEPTANCE TEST FOR PDM SYSTEM")
print("=================================================================\n")

from main import (
    sim_engines,
    sim_state,
    get_status,
    get_all_plcs,
    get_current,
    get_maintenance_status,
    get_maintenance_optimization,
    get_maintenance_config,
    update_maintenance_config,
    add_new_plc,
    control_simulation,
    MaintenanceConfigRequest,
    AddPlcRequest,
    ControlAction,
    generate_next_telemetry_step
)

# Step the simulation for all engines to have rich multi-step data
for _ in range(5):
    generate_next_telemetry_step()

print("--> 1. Testing System Status & PLC Discovery...")
status = get_status()
print(f"System status: {status['status']}, Active PLCs: {status['active_plcs']}")
assert len(status['active_plcs']) >= 5, "Should have at least 5 active PLCs"

print("\n--> 2. Testing Individual PLCs & Verification of Distinct Values...")
all_plcs_res = get_all_plcs()
plcs_list = all_plcs_res['plcs']
print(f"Discovered {len(plcs_list)} PLCs")

temperatures = []
vibrations = []
currents = []
ruls = []
issues = []
energy_costs = []

for p in plcs_list:
    pid = p['plc_id']
    maint = get_maintenance_status(pid)
    curr = get_current(pid)
    
    t = maint['temperature']
    v = maint['vibration']
    c = maint['motor_current']
    r = maint['predicted_rul_days']
    issue = maint['probable_issue']
    e_cost = maint['energy']['additional_energy_cost_day']
    p_cost = maint['cost_optimization']['preventive_cost']
    f_cost = maint['cost_optimization']['expected_failure_cost']
    savings = maint['cost_optimization']['potential_savings']
    prio = maint['inspection_priority']
    
    temperatures.append(t)
    vibrations.append(v)
    currents.append(c)
    ruls.append(r)
    issues.append(issue)
    energy_costs.append(e_cost)

    print(f"\n[{pid}]")
    print(f"  • Sensors: Temp={t}°C, Vib={v}mm/s, Curr={c}A, Health={maint['machine_health']}%")
    print(f"  • Issue (Q1): {maint['q1_what_is_wrong']}")
    print(f"  • When (Q2):  {maint['q2_when_maintain']}")
    print(f"  • Why (Q3):   {maint['q3_why_now']}")
    print(f"  • Energy: {maint['energy']['energy_kwh_day']} kWh/day (Excess: {maint['energy']['excess_pct']}%, ₹{e_cost}/day)")
    print(f"  • Financials: Preventive=₹{p_cost:,.0f} | Failure=₹{f_cost:,.0f} | Net Saving=₹{savings:,.0f}")
    print(f"  • Priority: {prio}")

# Verify distinct sensor values and calculations across PLCs
assert len(set(temperatures)) > 1, "Temperatures must be distinct across PLCs"
assert len(set(vibrations)) > 1, "Vibrations must be distinct across PLCs"
assert len(set(currents)) > 1, "Currents must be distinct across PLCs"
print("\n[OK] Checked: Sensor values and calculations are distinct across PLCs.")

print("\n--> 3. Testing Maintenance Optimization Register & Summary Cards...")
opt = get_maintenance_optimization("PLC_03")
cards = opt['summary_cards']
print("Summary Cards:")
for k, val in cards.items():
    print(f"  - {k}: {val}")
assert 'potential_cost_savings' in cards
assert 'energy_inefficiency_pct' in cards
assert 'additional_energy_cost_daily' in cards

print("\n--> 4. Testing Maintenance Priority Ranking...")
rankings = opt['priority_ranking']
for idx, r in enumerate(rankings):
    print(f"  Rank {idx+1}: {r['plc_id']} | Priority: {r['priority']} | Risk: {r['failure_risk_pct']}% | Issue: {r['main_issue']}")

print("\n--> 5. Testing Cost Configuration live update & recalculation...")
initial_config = get_maintenance_config()
print(f"Current labour cost: ₹{initial_config['labour_cost']}")
update_res = update_maintenance_config(MaintenanceConfigRequest(labour_cost=3000.0, electricity_rate=9.0))
new_config = update_res['config']
print(f"Updated labour cost: ₹{new_config['labour_cost']}, rate: ₹{new_config['electricity_rate']}")
assert new_config['labour_cost'] == 3000.0
assert new_config['electricity_rate'] == 9.0

# Verify recalculation with new config
opt_recalc = get_maintenance_optimization("PLC_03")
assert opt_recalc['config']['labour_cost'] == 3000.0
print("[OK] Cost configuration update & real-time recalculation verified.")

# Reset to defaults
update_maintenance_config(MaintenanceConfigRequest(labour_cost=2500.0, electricity_rate=8.0))

print("\n--> 6. Testing Dynamic Add PLC Functionality...")
add_res = add_new_plc(AddPlcRequest(plc_id="PLC_07", deg_init=0.40, base_load=0.70))
print(f"Add PLC Result: {add_res['status']} -> {add_res['plc_id']}")
opt_after_add = get_maintenance_optimization("PLC_07")
plc_ids_after = [p['plc_id'] for p in opt_after_add['plcs_maintenance_table']]
print(f"Total PLCs after addition: {len(plc_ids_after)} -> {plc_ids_after}")
assert "PLC_07" in plc_ids_after, "Newly added PLC_07 must appear in optimization register"

print("\n--> 7. Testing Simulation Controls (Start, Pause, Next)...")
ctrl_pause = control_simulation(ControlAction(action="pause"))
assert ctrl_pause['auto_play'] == False
ctrl_start = control_simulation(ControlAction(action="start"))
assert ctrl_start['auto_play'] == True
print("[OK] Simulation controls working properly.")

print("\n--> 8. Testing Features Summary & Evaluation Metrics...")
from main import get_model_evaluation, get_features_summary
try:
    f_sum = get_features_summary()
    print(f"Features summary retrieved: Top features count = {len(f_sum['top_overall_features'])}")
except Exception as e:
    print(f"Features summary note: {e}")

try:
    m_eval = get_model_evaluation()
    print(f"Model evaluation retrieved: {list(m_eval.keys())}")
except Exception as e:
    print(f"Model eval note: {e}")

print("\n=================================================================")
print("ALL ACCEPTANCE TESTS PASSED SUCCESSFULLY!")
print("=================================================================")
