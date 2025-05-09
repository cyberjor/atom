import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Title
st.title("Mesh Grid Inverter Simulation")

# Inverter settings
st.sidebar.header("Inverter Settings")

# Number of inverters
num_inverters = st.sidebar.slider("Number of Inverters", min_value=2, max_value=10, value=4)

inverter_data = []

# Constants
V_NOMINAL = 230  # nominal voltage
F_NOMINAL = 60.0  # nominal frequency

for i in range(num_inverters):
    with st.sidebar.expander(f"Inverter {i+1}"):
        role = st.selectbox("Role", ["Grid-Forming", "Grid-Following"], key=f"role_{i}")
        p_set = st.slider("Real Power Setpoint (W)", -2000, 2000, 500, key=f"p_{i}")
        q_set = st.slider("Reactive Power Setpoint (VAR)", -1000, 1000, 0, key=f"q_{i}")
        droop_p = st.slider("Frequency Droop (Hz/kW)", 0.0, 1.0, 0.05 if role == "Grid-Forming" else 0.0, key=f"dp_{i}")
        droop_q = st.slider("Voltage Droop (V/kVAR)", 0.0, 1.0, 0.05 if role == "Grid-Forming" else 0.0, key=f"dq_{i}")
        inverter_data.append({
            "role": role,
            "P": p_set,
            "Q": q_set,
            "droop_P": droop_p,
            "droop_Q": droop_q
        })

# Compute system-wide effects
p_total = sum(inv["P"] for inv in inverter_data)
q_total = sum(inv["Q"] for inv in inverter_data)

# Compute frequency and voltage from grid-forming inverters
f_grid = F_NOMINAL
v_grid = V_NOMINAL

for inv in inverter_data:
    if inv["role"] == "Grid-Forming":
        f_grid -= inv["droop_P"] * (inv["P"] / 1000)  # convert to kW
        v_grid -= inv["droop_Q"] * (inv["Q"] / 1000)  # convert to kVAR

# Visualization
st.subheader("Grid State")
st.metric("Total Real Power (W)", f"{p_total:.0f}")
st.metric("Total Reactive Power (VAR)", f"{q_total:.0f}")
st.metric("Grid Frequency (Hz)", f"{f_grid:.2f}")
st.metric("Grid Voltage (V)", f"{v_grid:.2f}")

# Power flow bar chart
df = pd.DataFrame(inverter_data)
df["Inverter"] = [f"Inv {i+1}" for i in range(num_inverters)]

fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(df["Inverter"], df["P"], label="Real Power (W)")
ax.bar(df["Inverter"], df["Q"], bottom=df["P"], label="Reactive Power (VAR)")
ax.axhline(0, color='black')
ax.set_ylabel("Power")
ax.legend()
ax.set_title("Inverter Power Contribution")
st.pyplot(fig)

# Stability check
if abs(f_grid - F_NOMINAL) > 2.0:
    st.warning("Frequency deviation too high — system may be unstable!")
if abs(v_grid - V_NOMINAL) > 20:
    st.warning("Voltage deviation too high — voltage regulation issue!")
