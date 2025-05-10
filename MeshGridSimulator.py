import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Title
st.title("Mesh Grid Current Simulation")

# Inverter settings
st.sidebar.header("Inverter Current Settings")

# Number of inverters
num_inverters = st.sidebar.slider("Number of Inverters", min_value=2, max_value=10, value=4)

load_data = []

# Constants
V_NOMINAL = 230  # nominal voltage
F_NOMINAL = 60.0  # nominal frequency
INVERTER_CAPACITY = 2000  # 2 kW per inverter
I_MAX_CONTINUOUS = 8.0  # max continuous current in A
V_MIN = 180  # minimum voltage allowed for sagging calculation

# Voltage sag function
def calculate_voltage(current):
    if current <= I_MAX_CONTINUOUS:
        return V_NOMINAL
    else:
        power_limit = INVERTER_CAPACITY  # W
        voltage = power_limit / current
        return max(voltage, V_MIN)

for i in range(num_inverters):
    with st.sidebar.expander(f"Inverter {i+1} Current"):
        current = st.slider("Local Current (A)", 0.0, 10.0, 4.0, step=0.1, key=f"current_{i}")
        voltage = calculate_voltage(current)
        power = current * voltage
        load_data.append({
            "Inverter": f"Inv {i+1}",
            "Current (A)": current,
            "Voltage (V)": voltage,
            "Power (W)": power
        })

# Compute total system performance
total_power = sum(ld["Power (W)"] for ld in load_data)
voltage_avg = np.mean([ld["Voltage (V)"] for ld in load_data])
frequency_shift = max(0, (total_power - num_inverters * INVERTER_CAPACITY) / 1000 * 0.5)  # 0.5 Hz per kW overload

# Display results
st.subheader("Grid State")
st.metric("Total Power (W)", f"{total_power:.0f}")
st.metric("Average Voltage (V)", f"{voltage_avg:.2f}")
st.metric("Grid Frequency (Hz)", f"{F_NOMINAL - frequency_shift:.2f}")

# Dataframe and plots
df = pd.DataFrame(load_data)
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(df["Inverter"], df["Power (W)"], label="Power (W)", color='steelblue')
ax.set_ylabel("Power (W)")
ax.set_title("Power Output per Inverter")
st.pyplot(fig)

# Warnings
if frequency_shift > 0:
    st.warning("System is overloaded — frequency drop may cause instability!")
if any(ld["Voltage (V)"] < V_NOMINAL for ld in load_data):
    st.warning("One or more inverters are voltage sagging to meet power limits!")
