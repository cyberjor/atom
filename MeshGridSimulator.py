"""
Mesh-Grid Current & Power Simulator
----------------------------------
• Sliders set **local load (W)** – they start at 0 W.
• Each inverter initially supplies the full current demand (= load / 230 V).
• If that demand exceeds the 2 kW / 230 V ≈ 8.7 A limit, the node voltage droops
  so power stays ≤ 2 kW.
• Click **⏭ Step** – every node whose voltage is < 225 V and whose own current
  is still < 8.7 A will ramp up by 0.5 A.  Power flows are recalculated and
  the leader’s effective current (after imported current is accounted for)
  is used to decide whether its voltage droop clears.
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# ─────────────────────────────── Constants ────────────────────────────────
V_NOM      = 230.0          # nominal grid volts
CAP_W      = 2000.0         # max inverter power
I_MAX      = CAP_W / V_NOM  # ≈ 8.695 A
MIN_V      = 100.0          # hard floor on voltage sag
WARN_V     = 225.0          # sag warning threshold
STEP_I     = 0.5            # ramp step per click (A)
R_LINE     = 0.3            # Ω per span  (300 m × 1 Ω/km)

# ─────────────────────────── UI – sidebar inputs ──────────────────────────
st.set_page_config(page_title="Mesh Grid Simulator", layout="wide")
st.title("Mesh-Grid Current and Power Simulation")

st.sidebar.header("Inverter & Load Settings")

N = st.sidebar.slider("Number of inverters", 2, 10, 4)
leader_idx = st.sidebar.selectbox(
    "Grid-forming (leader) inverter", range(N),
    format_func=lambda i: f"Inverter {i+1}"
)

# session_state initialisation
if "load_W" not in st.session_state or len(st.session_state.load_W) != N:
    st.session_state.load_W   = [0.0] * N    # W
    st.session_state.I_local  = [0.0] * N    # A – current the local inverter *tries* to supply

# sliders – collect (and update) local loads
for i in range(N):
    with st.sidebar.expander(f"Inverter {i+1}"):
        st.session_state.load_W[i] = st.slider(
            "Local load (W)", 0.0, 3000.0, st.session_state.load_W[i],
            key=f"load_{i}", step=50.0
        )
        I_demand = st.session_state.load_W[i] / V_NOM
        # Show current demand based on 230 V
        st.caption(f"Current demand: **{I_demand:.2f} A**")
        # Current the inverter is presently supplying
        st.caption(f"Current supplied: **{st.session_state.I_local[i]:.2f} A**")
        # Power actually produced at *this* node (will update each frame)
        P_node = st.session_state.I_local[i] * V_NOM  # placeholder – replaces after solve
        st.caption(f"Power output: **{P_node:.0f} W**")

# ────────────────────────── Simulation step button ────────────────────────
if st.button("⏭ Step"):
    # Any node below WARN_V & under I_MAX ramps +0.5 A
    V_now = st.session_state.get("V_nodes", [V_NOM]*N)
    for i in range(N):
        if V_now[i] < WARN_V and st.session_state.I_local[i] < I_MAX:
            st.session_state.I_local[i] = min(st.session_state.I_local[i] + STEP_I, I_MAX)

# ───────────────────── Solver – two-pass radial calculation ───────────────
def solve(load_W, I_local):
    """Return V_nodes, I_local (possibly drooped), P_out, line_drop list."""
    # Helper – apply droop if power would exceed 2 kW
    def node_voltage(i_local):
        return V_NOM if i_local * V_NOM <= CAP_W else max(CAP_W / i_local, MIN_V)

    # Pass-0: set initial node voltages (droop) ignoring line drops
    V0 = [node_voltage(I_local[i]) for i in range(N)]

    # Pass-1: forward (rightward) – compute surplus & line drops
    surplus = []            # I surplus (export +, import −) at each node
    line_I  = []            # current in span i→i-1
    V1      = V0.copy()     # will adjust later with leader recovery
    for i in range(N):
        surplus.append(I_local[i] - load_W[i]/V_NOM)

    # line current: cumulative surplus to the right of the span
    cum = 0.0
    for seg in reversed(range(1, N)):
        cum += surplus[seg]
        line_I.insert(0, cum)      # span seg↔seg-1 current

    # leader effective current = its own supply minus incoming current from span-1
    import_I = line_I[0] if line_I else 0.0   # current coming *into* leader ( + = to the left)
    eff_leader_I = max(I_local[leader_idx] - import_I, 0.0)

    # Re-evaluate leader voltage based on that effective current
    V_leader = V_NOM if eff_leader_I <= I_MAX else max(CAP_W / eff_leader_I, MIN_V)
    V1[leader_idx] = V_leader

    # Pass-2: propagate voltages to the right with the (possibly recovered) leader V
    V_nodes = [0.0]*N
    V_nodes[0] = V_leader
    drop_seg = []
    for seg in range(1, N):
        # drop across span = |I in span| × R_LINE
        vd = abs(line_I[seg-1]) * R_LINE
        drop_seg.append(vd)
        V_nodes[seg] = max(V_nodes[seg-1] - vd, MIN_V)

    # Compute power actually delivered by each inverter at its node voltage
    P_out = [I_local[i] * V_nodes[i] for i in range(N)]

    return V_nodes, P_out, line_I, drop_seg

# run solver & store in session_state for next frame
V_nodes, P_out, line_I, drop_seg = solve(st.session_state.load_W, st.session_state.I_local)
st.session_state.V_nodes = V_nodes  # save for next step condition

# ─────────────────────────── Sidebar outputs update ───────────────────────
for i in range(N):
    key = f"_sidebar{i}"
    st.sidebar.caption(f"Inverter {i+1} – **V = {V_nodes[i]:.1f} V**, "
                       f"Current supplied = **{st.session_state.I_local[i]:.2f} A**, "
                       f"Power = **{P_out[i]:.0f} W**", key=key)

# ──────────────────────────── Grid-state metrics ──────────────────────────
col1, col2, col3 = st.columns(3)
col1.metric("Total Power (W)", f"{sum(P_out):.0f}")
col2.metric("Leader V (V)", f"{V_nodes[leader_idx]:.1f}")
col3.metric("Freq (Hz)", "60.00")  # placeholder

# ──────────────────── Simple pole-and-line visualisation ──────────────────
st.subheader("Mesh Grid Visualisation")
fig, ax = plt.subplots(figsize=(10, 3))
# Poles & bars
for i in range(N):
    x = i*2
    # pole
    ax.plot([x, x], [0, 0.4], 'k', lw=2)
    ax.text(x, 0.42, f"Inv {i+1}", ha='center', fontsize=9)
    ax.text(x, 0.34, f"{V_nodes[i]:.0f} V", ha='center', color='purple', fontsize=8)

    # bar – demand (orange) & supplied (blue)
    demand_bar = st.session_state.load_W[i]/10000
    supply_bar = P_out[i]/10000
    ax.bar(x-0.15, demand_bar, width=0.1, color='orange', bottom=0.6)
    ax.bar(x+0.05, supply_bar, width=0.1, color='steelblue', bottom=0.6)

    if i == leader_idx:
        ax.text(x, -0.05, "Leader", ha='center', color='gold')

# lines, drops & arrows
for seg in range(N-1):
    x0, x1 = seg*2, (seg+1)*2
    ax.plot([x0, x1], [0.4, 0.4], '--', color='gray')
    vd = abs(line_I[seg]) * R_LINE
    ax.text((x0+x1)/2, 0.44, f"{vd:.2f} V", ha='center', color='red', fontsize=8)
    if abs(line_I[seg]) > 0.01:
        direction = -1 if line_I[seg] > 0 else 1
        ax.annotate('', xy=((x0+x1)/2 + direction*0.3, 0.405),
                    xytext=((x0+x1)/2 - direction*0.3, 0.405),
                    arrowprops=dict(arrowstyle='->', color='green'))

ax.set_ylim(-0.1, 1.2)
ax.set_xlim(-1, 2*N-1)
ax.axis('off')
st.pyplot(fig)


