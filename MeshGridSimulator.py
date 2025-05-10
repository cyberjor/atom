import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# Constants
V_NOM = 230.0
CAP_W = 2000.0
I_MAX = CAP_W / V_NOM
MIN_V = 100.0
WARN_V = 225.0
STEP_I = 0.5
R_LINE = 0.3  # ohms per 300m

# Init
st.set_page_config(page_title="Mesh Grid Simulator", layout="wide")
st.title("Mesh-Grid Current and Power Simulation")
st.sidebar.header("Inverter & Load Settings")

N = st.sidebar.slider("Number of inverters", 2, 10, 4)
leader_idx = st.sidebar.selectbox("Grid-forming (leader) inverter", range(N),
                                  format_func=lambda i: f"Inverter {i+1}")

if "load_W" not in st.session_state or len(st.session_state.load_W) != N:
    st.session_state.load_W = [0.0] * N
    st.session_state.I_local = [0.0] * N

# Sidebar sliders
for i in range(N):
    with st.sidebar.expander(f"Inverter {i+1}"):
        st.session_state.load_W[i] = st.slider(
            "Local load (W)", 0.0, 3000.0, st.session_state.load_W[i],
            key=f"load_{i}", step=50.0
        )
        I_demand = st.session_state.load_W[i] / V_NOM
        st.caption(f"Current demand: **{I_demand:.2f} A**")

# Set initial I_local to match demand
for i in range(N):
    st.session_state.I_local[i] = st.session_state.load_W[i] / V_NOM

# Step
if st.button("⏭ Step"):
    V_now = st.session_state.get("V_nodes", [V_NOM]*N)
    for i in range(N):
        if V_now[i] < WARN_V and st.session_state.I_local[i] < I_MAX:
            st.session_state.I_local[i] = min(st.session_state.I_local[i] + STEP_I, I_MAX)

# Solver
def solve(load_W, I_local):
    surplus = [I_local[i] - load_W[i]/V_NOM for i in range(N)]

    line_I = []
    cum = 0.0
    for seg in reversed(range(1, N)):
        cum += surplus[seg]
        line_I.insert(0, cum)

    import_I = line_I[0] if line_I else 0.0
    eff_I0 = max(I_local[leader_idx] - import_I, 0.0)

    if eff_I0 * V_NOM > CAP_W:
        V_leader = max(CAP_W / eff_I0, MIN_V)
    else:
        V_leader = V_NOM

    V_nodes = [0.0] * N
    V_nodes[0] = V_leader
    drop_seg = []

    for i in range(1, N):
        drop = abs(line_I[i-1]) * R_LINE
        drop_seg.append(drop)
        V_nodes[i] = max(V_nodes[i-1] - drop, MIN_V)

    P_out = [I_local[i] * V_nodes[i] for i in range(N)]
    return V_nodes, P_out, line_I, drop_seg

# Run simulation
V_nodes, P_out, line_I, drop_seg = solve(st.session_state.load_W, st.session_state.I_local)
st.session_state.V_nodes = V_nodes

# Sidebar output
for i in range(N):
    st.sidebar.caption(
        f"**Inverter {i+1}**: V = {V_nodes[i]:.1f} V | "
        f"I = {st.session_state.I_local[i]:.2f} A | "
        f"P = {P_out[i]:.0f} W"
    )

# Grid state
col1, col2, col3 = st.columns(3)
col1.metric("Total Power (W)", f"{sum(P_out):.0f}")
col2.metric("Leader Voltage (V)", f"{V_nodes[leader_idx]:.1f}")
col3.metric("Frequency (Hz)", "60.00")

# Visualization
st.subheader("Mesh Grid Visualisation")
fig, ax = plt.subplots(figsize=(12, 4))

spacing = 3.5  # increased spacing
for i in range(N):
    x = i * spacing
    ax.plot([x, x], [0, 0.4], 'k', lw=2)

    ax.text(x, 0.55, f"Inv {i+1}", ha='center', fontsize=9)
    ax.text(x, 0.50, f"{V_nodes[i]:.0f} V", ha='center', color='purple', fontsize=8)

    demand_bar = st.session_state.load_W[i] / 10000
    output_bar = max(P_out[i] / 10000, 0.002)
    ax.bar(x - 0.15, demand_bar, width=0.1, color='orange', bottom=0.6)
    ax.bar(x + 0.05, output_bar, width=0.1, color='steelblue', bottom=0.6)

    if i == leader_idx:
        ax.text(x, 0.45, "Leader", ha='center', color='gold')

# Draw lines & arrows
for seg in range(N - 1):
    x0, x1 = seg * spacing, (seg + 1) * spacing
    ax.plot([x0, x1], [0.4, 0.4], '--', color='gray')
    vd = drop_seg[seg]
    ax.text((x0 + x1)/2, 0.44, f"{vd:.2f} V", ha='center', color='red', fontsize=8)

    if abs(line_I[seg]) > 0.01:
        direction = -1 if line_I[seg] > 0 else 1
        ax.annotate('', xy=((x0 + x1)/2 + direction * 0.5, 0.405),
                    xytext=((x0 + x1)/2 - direction * 0.5, 0.405),
                    arrowprops=dict(arrowstyle='->', color='green'))

ax.set_ylim(-0.1, 1.3)
ax.set_xlim(-1, spacing * (N - 1) + 2)
ax.axis('off')
st.pyplot(fig)
