import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

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
V_NOMINAL = 230  # nominal voltage
F_NOMINAL = 60.0  # nominal frequency
INVERTER_CAPACITY = 2000  # 2 kW per inverter
I_MAX_CONTINUOUS = 8.0  # max continuous current in A
I_MAX_INPUT = 15.0  # max current input via slider
V_MIN = 100  # minimum voltage allowed for sagging calculation
V_WARNING = 225  # threshold for voltage sag warning

# Voltage sag function based on current draw
def calculate_voltage_from_power(power):
    current = power / V_NOMINAL
    if power <= INVERTER_CAPACITY:
        voltage = V_NOMINAL
    else:
        voltage = max(INVERTER_CAPACITY / current, V_MIN)
        power = voltage * current
    return voltage, current, min(power, INVERTER_CAPACITY)

# Step 1: Collect manual power input
for i in range(num_inverters):
    with st.sidebar.expander(f"Inverter {i+1} Settings"):
        power = st.slider("Power Draw (W)", 0.0, 3000.0, 1000.0, step=50.0, key=f"power_{i}")
        manual_powers.append(power)

# Step 2: Apply logic based on leader inverter voltage
leader_power = manual_powers[leader_index]
leader_voltage, leader_current, actual_leader_power = calculate_voltage_from_power(leader_power)

# If voltage is too low, try to compensate using remaining inverters
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

# Step 3: Calculate outputs based on adjusted powers
load_data = []
for i in range(num_inverters):
    power = adjusted_powers[i]
    voltage, current, actual_power = calculate_voltage_from_power(power)
    load_data.append({
        "Inverter": f"Inv {i+1}",
        "Current (A)": current,
        "Voltage (V)": voltage,
        "Power (W)": actual_power
    })
    st.sidebar.markdown(f"**Inverter {i+1} Power Output:** {actual_power:.2f} W")
    if voltage < V_WARNING:
        st.sidebar.error(f"⚠️ Voltage sag detected: {voltage:.2f} V")

# Compute total system performance
total_power = sum(ld["Power (W)"] for ld in load_data)
grid_voltage = load_data[leader_index]["Voltage (V)"] if load_data else V_NOMINAL
frequency_shift = max(0, (total_power - num_inverters * INVERTER_CAPACITY) / 1000 * 0.5)  # 0.5 Hz per kW overload

# Display results
st.subheader("Grid State")
st.metric("Total Power (W)", f"{total_power:.0f}")
st.metric("Grid Voltage (V)", f"{grid_voltage:.2f}")
st.metric("Grid Frequency (Hz)", f"{F_NOMINAL - frequency_shift:.2f}")

# Dataframe and plots
df = pd.DataFrame(load_data)
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(df["Inverter"], df["Power (W)"], label="Power (W)", color='steelblue')
ax.set_ylabel("Power (W)")
ax.set_title("Power Output per Inverter")
ax.set_ylim(0, 2000)
st.pyplot(fig)

# Warnings
if frequency_shift > 0:
    st.warning("System is overloaded — frequency drop may cause instability!")
if any(ld["Voltage (V)"] < V_NOMINAL for ld in load_data):
    st.warning("One or more inverters are voltage sagging to meet power limits!")

