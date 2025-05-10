import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Title
st.title("Mesh Grid Power and Current Simulation")

# Inverter settings
st.sidebar.header("Inverter Power Settings")

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
def calculate_voltage_from_power(power):
    voltage = V_NOMINAL
    current = power / voltage
    if current <= I_MAX_CONTINUOUS:
        return voltage, current
    else:
        voltage = max(INVERTER_CAPACITY / current, V_MIN)
        current = power / voltage
        return voltage, current

for i in range(num_inverters):
    with st.sidebar.expander(f"Inverter {i+1} Settings"):
        power = st.slider("Power Draw (W)", 0, 2500, 1000, step=50, key=f"power_{i}")
        voltage, current = calculate_voltage_from_power(power)
        load_data.append({
            "Inverter": f"Inv {i+1}",
            "Power (W)": power,
            "Voltage (V)": voltage,
            "Current (A)": current
        })
        st.markdown(f"**Current Output:** {current:.2f} A")

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

