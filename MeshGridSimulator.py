import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# -----------------------------
# Mesh Grid Current & Power Simulator
# -----------------------------

st.title("Mesh Grid Current and Power Simulation")

# ----- Sidebar Controls -----
st.sidebar.header("Inverter Power Settings")
num_inverters = st.sidebar.slider("Number of Inverters", 2, 10, 4)
leader_index = st.sidebar.selectbox(
    "Select Grid‑Forming (Leader) Inverter",
    options=range(num_inverters),
    format_func=lambda x: f"Inverter {x+1}"
)

# ----- Constants -----
V_NOMINAL = 230          # V
F_NOMINAL = 60.0         # Hz
INVERTER_CAPACITY = 2000 # W (2 kW)
V_MIN = 100              # V minimum sag
V_WARNING = 225          # V warning threshold
RESISTANCE_PER_KM = 1.0  # Ω/km
DIST_M = 300             # m between poles
R_LINE = (DIST_M / 1000) * RESISTANCE_PER_KM  # Ω

# ----- Helper -----

def inverter_model(power):
    """Return (voltage, current, clipped_power) given desired power draw."""
    current = power / V_NOMINAL if V_NOMINAL else 0
    if power <= INVERTER_CAPACITY:
        voltage = V_NOMINAL
        clipped_power = power
    else:
        voltage = max(INVERTER_CAPACITY / current, V_MIN) if current else V_MIN
        clipped_power = voltage * current
    return voltage, current, clipped_power

# ----- Collect User Loads -----
manual_powers = []
placeholders = []  # to update after adjustment
for i in range(num_inverters):
    with st.sidebar.expander(f"Inverter {i+1} Settings"):
        p_draw = st.slider(
            "Power Draw (W)", 0.0, 3000.0, 0.0, 50.0, key=f"p_{i}")
        manual_powers.append(p_draw)
        v0, _, _ = inverter_model(p_draw)
        if v0 < V_WARNING:
            st.error(f"⚠️ Voltage sag detected: {v0:.2f} V")
        placeholders.append(st.empty())

# ----- Assistance Logic (simple) -----
leader_power = manual_powers[leader_index]
leader_v, leader_i, leader_actual = inverter_model(leader_power)

adjusted_powers = manual_powers.copy()
if leader_v < V_WARNING:
    deficit = max(leader_power - INVERTER_CAPACITY, 0)
    for i in range(num_inverters):
        if i == leader_index or deficit <= 0:
            continue
        margin = 3000.0 - adjusted_powers[i]
        share = min(deficit, margin)
        adjusted_powers[i] += share
        deficit -= share

# ----- Solve Inverter Outputs -----
load_data = []
for i in range(num_inverters):
    v, i_curr, p_out = inverter_model(adjusted_powers[i])
    load_data.append({
        "name": f"Inv {i+1}",
        "V": v,
        "I": i_curr,
        "P_out": p_out,
        "P_load": manual_powers[i]
    })
    placeholders[i].markdown(f"**Inverter Power Output:** {p_out:.2f} W")

# ----- Grid‑level Metrics -----
total_power = sum(d["P_out"] for d in load_data)
grid_voltage = load_data[leader_index]["V"]
frequency_shift = max(0, (total_power - num_inverters*INVERTER_CAPACITY)/1000 * 0.5)

st.subheader("Grid State")
st.metric("Total Power (W)", f"{total_power:.0f}")
st.metric("Grid Voltage (V)", f"{grid_voltage:.2f}")
st.metric("Grid Frequency (Hz)", f"{F_NOMINAL - frequency_shift:.2f}")

# ----- Visualisation -----
st.subheader("Mesh Grid Visualization")
fig, ax = plt.subplots(figsize=(12, 3.5))

# Draw poles & bars
for idx, d in enumerate(load_data):
    x = idx * 2
    ax.plot([x, x], [0, 0.3], color='black', lw=2)
    ax.plot([x-0.05, x+0.05], [0.3, 0.33], color='black', lw=2)
    ax.text(x, 0.35, d["name"], ha='center', fontsize=9, weight='bold')
    # Display inverter voltage just below the label
    # voltage above inverter label to avoid overlap
    ax.text(x, 0.52, f"{d['V']:.0f} V", ha='center', fontsize=8, color='purple')
    # Local load (orange) & inverter output (blue)
    ax.bar(x-0.2, d["P_load"] / 10000, 0.15, bottom=0.6, color='orange')
    ax.bar(x + 0.05, d["P_out"] / 10000, 0.15, bottom=0.6, color='steelblue')
    if idx == leader_index:
        ax.text(x, -0.05, "Leader", ha='center', va='top', fontsize=8, weight='bold', color='gold')

# Draw lines, voltage drop & arrows
for i in range(num_inverters - 1):
    x0, x1 = i * 2, (i + 1) * 2
    mid_x = (x0 + x1) / 2
    ax.plot([x0, x1], [0.33, 0.33], color='gray', ls='--')

    # Net surplus (positive) or deficit (negative) at each node
    p0_net = load_data[i]["P_out"] - load_data[i]["P_load"]
    p1_net = load_data[i + 1]["P_out"] - load_data[i + 1]["P_load"]

    # Only show flow when the two nodes have opposite signs (surplus → deficit)
    if p0_net * p1_net < 0:  # opposite signs ⇒ real transfer
        # magnitude of power actually transferred = min(|surplus|, |deficit|)
        flow_power = min(abs(p0_net), abs(p1_net))
        current_flow = flow_power / V_NOMINAL
        v_drop = current_flow * R_LINE
        ax.text(mid_x, 0.36, f"{v_drop:.2f} V", ha='center', fontsize=8, color='red')

        direction = 1 if p0_net > 0 else -1  # arrow from surplus to deficit
        ax.annotate('', xy=(mid_x + 0.3 * direction, 0.34), xytext=(mid_x - 0.3 * direction, 0.34),
                    arrowprops=dict(arrowstyle='->', color='green', lw=1.5))
    else:
        # no meaningful transfer → no arrow, zero drop label
        ax.text(mid_x, 0.36, "0.00 V", ha='center', fontsize=8, color='gray')

ax.set_xlim(-1, 2 * num_inverters)
ax.set_ylim(-0.1, 1.3)
ax.axis('off')
st.pyplot(fig)

# ----- Warnings -----
if frequency_shift > 0:
    st.warning("System is overloaded — frequency drop may cause instability!")
if any(d["V"] < V_NOMINAL for d in load_data):
    st.warning("One or more inverters are voltage sagging to meet power limits!")


