import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# -------------------- Constants --------------------
V_NOM = 230.0
CAP_W = 2000.0
I_MAX = CAP_W / V_NOM
MIN_V = 100.0
WARN_V = 225.0
STEP_I = 0.5
R_LINE = 0.3  # Ohms per 300m

# -------------------- UI Setup --------------------
st.set_page_config(page_title="Mesh Grid Simulator", layout="wide")
st.title("Mesh-Grid Current and Power Simulation")
st.sidebar.header("Inverter & Load Settings")

N = st.sidebar.slider("Number of inverters", 2, 10, 4)
leader_idx = st.sidebar.selectbox("Grid-forming (leader) inverter", range(N),
                                  format_func=lambda i: f"Inverter {i+1}")

# -------------------- Init Session State --------------------
if "load_W" not in st.session_state or len(st.session_state.load_W) != N:
    st.session_state.load_W = [0.0] * N
    st.session_state.I_local = [0.0] * N

# -------------------- Load Input & Display --------------------
for j in range(N):
    st.sidebar.markdown(f"### Inverter {j+1}")
    st.session_state.load_W[j] = st.sidebar.slider(
        "Local load (W)", 0.0, 3000.0, st.session_state.load_W[j],
        key=f"load_{j}", step=50.0
    )
    I_demand = st.session_state.load_W[j] / V_NOM
    st.sidebar.caption(f"Current demand: **{I_demand:.2f} A**")
    st.sidebar.caption(f"Current supplied: **{st.session_state.I_local[j]:.2f} A**")
    P_node = st.session_state.I_local[j] * V_NOM
    st.sidebar.caption(f"Power output: **{P_node:.0f} W**")

# -------------------- Simulation Step Button --------------------
if st.button("⏭ Step"):
    V_now = st.session_state.get("V_nodes", [V_NOM]*N)
    for j in range(N):
        if V_now[j] < WARN_V and st.session_state.I_local[j] < I_MAX:
            st.session_state.I_local[j] = min(st.session_state.I_local[j] + STEP_I, I_MAX)

# -------------------- Solver --------------------
def solve(load_W, I_local):
    surplus = [I_local[j] - load_W[j] / V_NOM for j in range(N)]

    line_I = []
    cum = 0.0
    for seg in reversed(range(1, N)):
        cum += surplus[seg]
        line_I.insert(0, cum)

    import_I = line_I[0] if line_I else 0.0
    eff_I0 = max(I_local[leader_idx] - import_I, 0.0)
    I_local[leader_idx] = eff_I0
    st.session_state.I_local[leader_idx] = eff_I0

    V_nodes = [V_NOM] * N
    drop_seg = []
    for j in range(1, N):
        drop = abs(line_I[j - 1]) * R_LINE
        drop_seg.append(drop)
        V_nodes[j] = max(V_nodes[j - 1] - drop, MIN_V)

    P_out = []
    for j in range(N):
        I = I_local[j]
        V = V_nodes[j]
        P = I * V
        if P > CAP_W:
            I = CAP_W / V
            P = CAP_W
        P_out.append(P)
        st.session_state.I_local[j] = I

    return V_nodes, P_out, line_I, drop_seg

# -------------------- Run Simulation --------------------
V_nodes, P_out, line_I, drop_seg = solve(st.session_state.load_W, st.session_state.I_local)
st.session_state.V_nodes = V_nodes

# -------------------- Grid Metrics --------------------
col1, col2, col3 = st.columns(3)
col1.metric("Total Power (W)", f"{sum(P_out):.0f}")
col2.metric("Leader Voltage (V)", f"{V_nodes[leader_idx]:.1f}")
col3.metric("Frequency (Hz)", "60.00")

# -------------------- Visualization --------------------
st.subheader("Mesh Grid Visualisation")
fig, ax = plt.subplots(figsize=(12, 4))
spacing = 3.5

for j in range(N):
    x = j * spacing
    ax.plot([x, x], [0, 0.4], 'k', lw=2)
    ax.text(x, 0.60, f"Inv {j+1}", ha='center', fontsize=9)
    ax.text(x, 0.54, f"{V_nodes[j]:.0f} V", ha='center', color='purple', fontsize=8)
    demand_bar = st.session_state.load_W[j] / 10000
    output_bar = max(P_out[j] / 10000, 0.002)
    ax.bar(x - 0.15, demand_bar, width=0.1, color='orange', bottom=0.6)
    ax.bar(x + 0.05, output_bar, width=0.1, color='steelblue', bottom=0.6)
    if j == leader_idx:
        ax.text(x, 0.48, "Leader", ha='center', color='gold')

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
