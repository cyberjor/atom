import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Title
st.title("Mesh Grid Current and Power Simulation")

# Inverter settings
st.sidebar.header("Inverter Power Settings")

# Number of inverters
num_inverters = st.sidebar.slider("Number of Inverters", min_value=2, max_value=10, value=4)

# Leader inverter selection
leader_index = st.sidebar.selectbox("Select Grid-Forming (Leader) Inverter", options=range(num_inverters), format_func=lambda x: f"Inverter {x+1}")

manual_powers = []

# Constants
V_NOMINAL = 230
F_NOMINAL = 60.0
INVERTER_CAPACITY = 2000
I_MAX_CONTINUOUS = 8.0
I_MAX_INPUT = 15.0
V_MIN = 100
V_WARNING = 225
RESISTANCE_PER_KM = 1.0  # ohms/km
DISTANCE_BETWEEN_INVERTERS_M = 300
R_LINE = (DISTANCE_BETWEEN_INVERTERS_M / 1000.0) * RESISTANCE_PER_KM

# Voltage sag function
def calculate_voltage_from_power(power):
    current = power / V_NOMINAL
    if power <= INVERTER_CAPACITY:
        voltage = V_NOMINAL
    else:
        voltage = max(INVERTER_CAPACITY / current, V_MIN)
        power = voltage * current
    return voltage, current, min(power, INVERTER_CAPACITY)

# Step 1: Collect manual power input
output_placeholders = []  # placeholders to update after adjustment
for i in range(num_inverters):
    with st.sidebar.expander(f"Inverter {i+1} Settings"):
        power = st.slider("Power Draw (W)", 0.0, 3000.0, 1000.0, step=50.0, key=f"power_{i}")
        manual_powers.append(power)
        voltage, current, _ = calculate_voltage_from_power(power)
        if voltage < V_WARNING:
            st.error(f"⚠️ Voltage sag detected: {voltage:.2f} V")
        # placeholder for adjusted power output
        placeholder = st.empty()
        output_placeholders.append(placeholder)

# Step 2: Leader logic
leader_power = manual_powers[leader_index]
leader_voltage, leader_current, actual_leader_power = calculate_voltage_from_power(leader_power)

adjusted_powers = manual_powers.copy()
if leader_voltage < V_WARNING:
    deficit_power = leader_power - INVERTER_CAPACITY
    if deficit_power > 0:
        assist_voltage = V_NOMINAL
        remaining_deficit = deficit_power
        for i in range(num_inverters):
            if i == leader_index:
                continue
            available_margin = 3000.0 - adjusted_powers[i]
            assist_power = min(remaining_deficit, available_margin)
            adjusted_powers[i] += assist_power
            remaining_deficit -= assist_power
            if remaining_deficit <= 0:
                break

# Step 3: Calculate outputs
load_data = []
for i in range(num_inverters):
    power = adjusted_powers[i]
    voltage, current, actual_power = calculate_voltage_from_power(power)
    load_data.append({
        "Inverter": f"Inv {i+1}",
        "Current (A)": current,
        "Voltage (V)": voltage,
        "Power (W)": actual_power,
        "Local Load (W)": manual_powers[i]
    })
    # update the placeholder with adjusted output
    output_placeholders[i].markdown(f"**Inverter Power Output:** {actual_power:.2f} W")

# Grid stats
(figsize=(12, 3.5))

for i, ld in enumerate(load_data):
    x = i * 2
    ax.plot([x, x], [0, 0.3], color='black', lw=2)
    ax.plot([x-0.05, x+0.05], [0.3, 0.33], color='black', lw=2)
    ax.text(x, 0.35, f"Inv {i+1}", ha='center', fontsize=9, weight='bold')
    ax.bar(x - 0.2, ld["Local Load (W)"] / 10000, width=0.15, color='orange', bottom=0.4)
    ax.bar(x + 0.05, ld["Power (W)"] / 10000, width=0.15, color='steelblue', bottom=0.4)
    if i == leader_index:
        ax.text(x, -0.05, "Leader", ha='center', va='top', fontsize=8, weight='bold', color='gold')

# Draw lines and voltage drops with arrows
for i in range(num_inverters - 1):
    x0, x1 = i * 2, (i + 1) * 2
    mid_x = (x0 + x1) / 2

    # Always plot the line between poles
    ax.plot([x0, x1], [0.33, 0.33], color='gray', linestyle='--')

    # Net power surplus/deficit at each inverter
    p0_net = load_data[i]["Power (W)"] - load_data[i]["Local Load (W)"]
    p1_net = load_data[i+1]["Power (W)"] - load_data[i+1]["Local Load (W)"]
    power_flow = p0_net - p1_net  # +ve means flow from i → i+1

    # Voltage drop based on power flow (|I| * R)
    voltage_drop = abs(power_flow / V_NOMINAL) * R_LINE
    ax.text(mid_x, 0.36, f"{voltage_drop:.2f} V", ha='center', fontsize=8, color='red')

    # Draw arrow only if significant power transfers (>1 W)
    if abs(power_flow) > 1:
        direction = 1 if power_flow > 0 else -1  # 1: i→i+1, -1: i+1→i
        ax.annotate(
            '',
            xy=(mid_x + 0.3 * direction, 0.34),
            xytext=(mid_x - 0.3 * direction, 0.34),
            arrowprops=dict(arrowstyle='->', color='green', lw=1.5)
        )

ax.set_xlim(-1, 2 * num_inverters)
ax.set_ylim(-0.1, 1)
ax.axis('off')
st.pyplot(fig)

# Warnings
if frequency_shift > 0:
    st.warning("System is overloaded — frequency drop may cause instability!")
if any(ld["Voltage (V)"] < V_NOMINAL for ld in load_data):
    st.warning("One or more inverters are voltage sagging to meet power limits!")

