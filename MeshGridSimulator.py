import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Title
st.title("Mesh Grid Load Simulation")

# Inverter settings
st.sidebar.header("Inverter Load Settings")

# Number of inverters
num_inverters = st.sidebar.slider("Number of Inverters", min_value=2, max_value=10, value=4)

load_data = []

# Constants
V_NOMINAL = 230  # nominal voltage
F_NOMINAL = 60.0  # nominal frequency
INVERTER_CAPACITY = 2000  # 2 kW per inverter

for i in range(num_inverters):
    with st.sidebar.expander(f"Inverter {i+1} Load"):
        load = st.slider("Local Load (W)", 0, 2000, 500, step=50, key=f"load_{i}")
        load_data.append({
            "Inverter": f"Inv {i+1}",
            "Load": load
        })

# Compute total load and system performance
total_load = sum(ld["Load"] for ld in load_data)

# Assume all inverters share load equally up to capacity
load_per_inverter = total_load / num_inverters
voltage_drop = max(0, (load_per_inverter - INVERTER_CAPACITY) / 1000 * 10)  # simple linear model
frequency_shift = max(0, (total_load - num_inverters * INVERTER_CAPACITY) / 1000 * 0.5)  # 0.5 Hz per kW overload

# Display results
st.subheader("Grid State")
st.metric("Total Load (W)", f"{total_load:.0f}")
st.metric("Grid Voltage (V)", f"{V_NOMINAL - voltage_drop:.2f}")
st.metric("Grid Frequency (Hz)", f"{F_NOMINAL - frequency_shift:.2f}")

# Bar chart of loads
df = pd.DataFrame(load_data)
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(df["Inverter"], df["Load"], color='steelblue')
ax.set_ylabel("Load (W)")
ax.set_title("Local Loads on Inverters")
st.pyplot(fig)

# Warning if overloaded
if frequency_shift > 0:
    st.warning("System is overloaded — frequency drop may cause instability!")
if voltage_drop > 5:
    st.warning("Voltage drop exceeds normal range!")
