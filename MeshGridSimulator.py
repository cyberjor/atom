import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# ──────────────── Constants ────────────────
V_NOM   = 230.0
CAP_W   = 2000.0
I_MAX   = CAP_W / V_NOM
MIN_V   = 100.0
WARN_V  = 225.0
STEP_I  = 0.5
R_LINE  = 0.3  # ohms per 300m segment

# ─────────────── Setup ───────────────
st.set_page_config(page_title="Mesh Grid Simulator", layout="wide")
st.title("Mesh-Grid Current and Power Simulation")
st.sidebar.header("Inverter & Load Settings")

N = st.sidebar.slider("Number of inverters", 2, 10, 4)
leader_idx = st.sidebar.selectbox("Grid-forming (leader) inverter", range(N),
                                  format_func=lambda i: f"Inverter {i+1}")

if "load_W" not in st.session_state or len(st.session_state.load_W) != N:
    st.session_state.load_W = [0.0] * N
    st.session_state.I_local = [0.0] * N

# ───────────── Load sliders and current demand display ─────────────
for i in range(N):
    with st.sidebar.expander(f"Inverter {i+1}"):
        st.session_state.load_W[i] = st.slider(
            "Local load (W)", 0.0, 3000.0, st.session_state.load_W[i],
            key=f"load_{i}", step=50.0
        )
        I_demand = st.session_state.load_W[i] / V_NOM
        st.caption(f"Current demand: **{I_demand:.2f} A**")
        st.caption(f"Current supplied: **{st.session_state.I_local[i]:.2f} A**")

# ───────────── Step Logic ─────────────
if st.button("⏭ Step"):
    V_now = st.session_state.get("V_nodes", [V_NOM] * N)
    for i in range(N):
        if V_now[i] < WARN_V and st.session_state.I_local[i] < I_MAX:
            st.session_state.I_local[i] = min(st.session_state.I_local[i] + STEP_I, I_MAX)

# ───────────── Solver ─────────────
def solve(load_W, I_local):
    def node_voltage(i_local):
        return V_NOM if i_local * V_NOM <= CAP_W else max(CAP_W / i_local, MIN_V)

    V0 = [node_voltage(i) for i in I_local]
    surplus = [I_local[i] - load_W[i] / V_NOM for i in range(N)]

    line_I = []
    cum = 0.0
    for seg in reversed(range(1, N)):
        cum += surplus[seg]
        line_I.insert(0, cum)

    import_I = line_I[0] if line_I else 0.0
    eff_I0 = max(I_local[leader_idx] - import_I, 0.0)
    V0[0] = V_NOM if eff_I0 <= I_MAX else max(CAP_W / eff_I0, MIN_V)

    V_nodes = [0.0] * N
    V_nodes[0] = V0[0]
    drop_seg = []

    for seg in range(1, N):
        vd = abs(line_I[seg - 1]) * R_LINE
        drop_seg.append(vd)
        V_nodes[seg] = max(V_nodes[seg - 1] - vd, MIN_V)

    P_out = [I_local[i] * V_nodes[i] for i in range(N)]
    return V_nodes, P_out, line_I, drop_seg

# Run the simulation step
V_nodes, P_out, line_I, drop_seg = solve(st.session_state.load_W, st.session_state.I_local)
st.session_state.V_nodes = V_nodes

# ───────────── Updated Sidebar Display ─────────────
for i in range(N):
    st.sidebar.caption(
        f"Inverter {i+1} – **V = {V_nodes[i]:.1f} V**, "
        f"Current supplied = **{st.session_state.I_local[i]:.2f} A**, "
        f"Power output = **{P_out[i]:.0f} W**"
    )

# ───────────── Metrics ─────────────
col1, col2, col3 = st.columns(3)
col1.metric("Total Power (W)", f"{sum(P_out):.0f}")
col2.metric("Leader V (V)", f"{V_nodes[leader_idx]:.1f}")
col3.metric("Freq (Hz)", "60.00")

# ───────────── Visualisation ─────────────
st.subheader("Mesh Grid Visualisation")
fig, ax = plt.subplots(figsize=(10, 3))

for i in range(N):
    x = i * 2
    ax.plot([x, x], [0, 0.4], 'k', lw=2)
    ax.text(x, 0.42, f"Inv {i+1}", ha='center', fontsize=9)
    ax.text(x, 0.34, f"{V_nodes[i]:.0f} V", ha='center', color='purple', fontsize=8)

    demand = st.session_state.load_W[i] / 10000
    supply = max(P_out[i] / 10000, 0.001)  # Ensures visible blue bar
    ax.bar(x - 0.15, demand, width=0.1, color='orange', bottom=0.6)
    ax.bar(x + 0.05, supply, width=0.1, color='steelblue', bottom=0.6)

    if i == leader_idx:
        ax.text(x, -0.05, "Leader", ha='center', color='gold')

for seg in range(N - 1):
    x0, x1 = seg * 2, (seg + 1) * 2
    ax.plot([x0, x1], [0.4, 0.4], '--', color='gray')
    vd = abs(line_I[seg]) * R_LINE
    ax.text((x0 + x1) / 2, 0.44, f"{vd:.2f} V", ha='center', color='red', fontsize=8)
    if abs(line_I[seg]) > 0.01:
        direction = -1 if line_I[seg] > 0 else 1
        ax.annotate('', xy=((x0 + x1) / 2 + direction * 0.3, 0.405),
                    xytext=((x0 + x1) / 2 - direction * 0.3, 0.405),
                    arrowprops=dict(arrowstyle='->', color='green'))

ax.set_ylim(-0.1, 1.2)
ax.set_xlim(-1, 2 * N - 1)
ax.axis('off')
st.pyplot(fig)
