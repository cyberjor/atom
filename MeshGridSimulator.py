import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

"""
Mesh‑Grid Inverter Simulator (time‑step)
• Sliders set **local load** (W) for each inverter.
• **⏭ Step** shifts 100 W per click from a donor inverter (with spare margin) toward the leader when the leader is overloaded (> 2 kW).
• Every inverter senses the leader voltage minus cumulative line‑drop (1 Ω/km over 300 m ⇒ 0.3 Ω per span).
• Visual shows poles, load/output bars, node voltage, per‑line voltage drop and power‑flow arrow.
• Sidebar now also shows **actual inverter power output** under each load slider.
"""

# ---------- UI ----------
st.title("Mesh Grid Time‑Step Simulator")
SIDE = st.sidebar
SIDE.header("Configuration")
N = SIDE.slider("Number of Inverters", 2, 10, 4, key="n_inv")
leader_idx = SIDE.selectbox("Leader (grid‑forming) inverter", range(N), format_func=lambda i: f"Inv {i+1}")
STEP_W = 100  # W redistributed per click

# ---------- Constants ----------
V_NOM = 230.0      # nominal grid voltage (V)
F_NOM = 60.0       # Hz
CAP    = 2000.0    # inverter continuous rating (W)
V_MIN  = 100.0     # absolute minimum (V)
WARN   = 225.0     # warning threshold (V)
R_LINE = 0.3       # Ω per 300 m span (1 Ω/km)

# ---------- Session State ----------
if "base_load" not in st.session_state:
    st.session_state.base_load = [0.0]*N
    st.session_state.adj_power = [0.0]*N

# reset lists if N changed
if len(st.session_state.base_load) != N:
    st.session_state.base_load = [0.0]*N
    st.session_state.adj_power = [0.0]*N

# ---------- Helper ----------

def inverter_output(p_req: float, v_grid: float):
    """Return (P_out, I_out) limited by CAP at given voltage."""
    p_out = min(p_req, CAP)
    i_out = p_out / v_grid if v_grid else 0.0
    return p_out, i_out

# ---------- Collect Loads & Placeholders ----------
SIDE.subheader("Local Loads (W)")
placeholders = []
changed = False
for i in range(N):
    with SIDE.expander(f"Inverter {i+1}"):
        val = st.slider("Load (W)", 0.0, 3000.0, st.session_state.base_load[i], 50.0, key=f"load_{i}")
        if val != st.session_state.base_load[i]:
            changed = True
            st.session_state.base_load[i] = val
        placeholders.append(st.empty())  # will fill with power output later

# If any load changed, reset adjusted power to requested loads
if changed:
    st.session_state.adj_power = st.session_state.base_load.copy()

# ---------- Step Button ----------
if st.button("⏭ Step"):
    leader_p = st.session_state.adj_power[leader_idx]
    if leader_p > CAP:  # needs relief
        deficit = min(leader_p - CAP, STEP_W)
        # pick donor with largest spare margin
        donors = [(i, CAP - st.session_state.adj_power[i]) for i in range(N) if i != leader_idx and CAP - st.session_state.adj_power[i] > 0]
        if donors:
            donor = max(donors, key=lambda t: t[1])[0]
            give = min(deficit, CAP - st.session_state.adj_power[donor])
            st.session_state.adj_power[donor]   += give
            st.session_state.adj_power[leader_idx] -= give

# ---------- Electrical Solve ----------
leader_req = st.session_state.adj_power[leader_idx]
leader_v = V_NOM if leader_req <= CAP else max(CAP / leader_req * V_NOM, V_MIN)

p_out = []
currents = []
node_V = []
seg_drop = []

cum_drop = 0.0
for i in range(N):
    v_node = leader_v - cum_drop
    node_V.append(v_node)
    p_i, i_i = inverter_output(st.session_state.adj_power[i], v_node)
    p_out.append(p_i)
    currents.append(i_i)

    if i < N - 1:
        surplus = sum(p_out[:i+1]) - sum(st.session_state.base_load[:i+1])
        line_I = surplus / V_NOM if V_NOM else 0.0
        drop = abs(line_I) * R_LINE
        seg_drop.append(drop)
        cum_drop += drop

# ---------- Update Power‑output placeholders ----------
for i in range(N):
    placeholders[i].markdown(f"**Output:** {p_out[i]:.0f} W")

# ---------- Metrics ----------
TOT = sum(p_out)
shift = max(0.0, (TOT - N*CAP)/1000 * 0.5)
col1, col2, col3 = st.columns(3)
col1.metric("Total Power (W)", f"{TOT:.0f}")
col2.metric("Leader V (V)", f"{leader_v:.1f}")
col3.metric("Freq (Hz)", f"{F_NOM - shift:.2f}")

# ---------- Plot ----------
fig, ax = plt.subplots(figsize=(12, 3.5))

cum_drop = 0.0
for i in range(N):
    x = i * 2
    # pole & labels
    ax.plot([x, x], [0, 0.3], color='black')
    ax.plot([x-0.05, x+0.05], [0.3, 0.33], color='black')
    ax.text(x, 0.35, f"Inv {i+1}", ha='center', weight='bold')
    ax.text(x, 0.52, f"{node_V[i]:.0f} V", ha='center', fontsize=8, color='purple')
    # bars
    ax.bar(x-0.2, st.session_state.base_load[i]/10000, 0.15, bottom=0.6, color='orange')
    ax.bar(x+0.05, p_out[i]/10000, 0.15, bottom=0.6, color='steelblue')
    if i == leader_idx:
        ax.text(x, -0.05, "Leader", ha='center', va='top', fontsize=8, color='gold')
    # line & drop to next
    if i < N - 1:
        ax.plot([x, x+2], [0.33, 0.33], color='gray', ls='--')
        mid = x + 1
        v_d = seg_drop[i]
        ax.text(mid, 0.36, f"{v_d:.2f} V", ha='center', fontsize=8, color='red')
        if v_d > 1e-3:
            # Current direction based on net surplus up to node i
            surplus_left = sum(p_out[:i+1]) - sum(st.session_state.base_load[:i+1])
            direction = -1 if surplus_left < 0 else 1  # negative → arrow left
            ax.annotate('', xy=(mid + 0.3*direction, 0.34), xytext=(mid - 0.3*direction, 0.34),
                        arrowprops=dict(arrowstyle='->', color='green'))
        cum_drop += v_d

ax.set_xlim(-1, 2*N)
ax.set_ylim(-0.1, 1.3)
ax.axis('off')
st.pyplot(fig)

# ---------- Warnings ----------
if leader_v < V_NOM:
    st.warning("Leader voltage sagging – press ⏭ Step to redistribute load.")

