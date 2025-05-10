import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

"""
Mesh‑Grid Inverter Simulator (time‑step, local‑voltage response)

Fixes
─────
• **Indentation/return** inside `solve_network` was wrong → now inside function.
• Added missing `cum_drop` initialisation inside loop.
• Replaced generator expressions with floats to avoid NumPy `TypeError`.
• Clarified comments and variable names.
"""

# ───────── UI ─────────
st.title("Mesh Grid Time‑Step Simulator")
SIDE = st.sidebar
SIDE.header("Configuration")
N = SIDE.slider("Number of Inverters", 2, 10, 4)
leader_idx = SIDE.selectbox("Leader (grid‑forming) inverter", range(N), format_func=lambda i: f"Inv {i+1}")
STEP_W = 100  # W ramp per step

# ───────── Constants ─────────
V_NOM   = 230.0
F_NOM   = 60.0
CAP_W   = 2000.0
WARN_V  = 225.0
MIN_V   = 100.0
R_LINE  = 0.3        # Ω per 300 m span (1 Ω/km)

# ───────── Session state ─────────
state = st.session_state
if "base_load" not in state:
    state.base_load = [0.0]*N  # user load W
    state.req_power = [0.0]*N  # inverter target W

# resize lists if N changed
if len(state.base_load) != N:
    state.base_load = [0.0]*N
    state.req_power = [0.0]*N

# ───────── Helper functions ─────────

def inv_output(p_req: float, v_term: float):
    """Clip power to CAP_W at terminal voltage and return (P_out, I_out)."""
    p_out = min(p_req, CAP_W)
    i_out = p_out / v_term if v_term else 0.0
    return p_out, i_out


def solve_network(req_power):
    """Compute node voltages, inverter outputs & line drops.

    Returns
    -------
    leader_v : float
    P_out    : list[float]
    V_node   : list[float]
    drop_seg : list[float]  (length N‑1)
    """
    leader_req = req_power[leader_idx]
    leader_v   = V_NOM if leader_req <= CAP_W else max(CAP_W / leader_req * V_NOM, MIN_V)

    P_out, V_node, drop_seg = [], [], []
    cum_drop   = 0.0  # cumulative voltage drop from leader
    run_surplus = 0.0  # running power surplus up‑stream of current segment

    for i in range(N):
        v = leader_v - cum_drop
        V_node.append(v)

        p_i, _ = inv_output(req_power[i], v)
        P_out.append(p_i)

        run_surplus += p_i - state.base_load[i]

        # calculate drop for segment i → i+1
        if i < N-1:
            line_I = run_surplus / v if v else 0.0
            v_d    = abs(line_I) * R_LINE
            drop_seg.append(v_d)
            cum_drop += v_d

    return leader_v, P_out, V_node, drop_seg

# ───────── Sidebar sliders ─────────
SIDE.subheader("Local Loads (W)")
changed = False
placeholders = []
for i in range(N):
    with SIDE.expander(f"Inverter {i+1}"):
        val = st.slider("Load", 0.0, 3000.0, state.base_load[i], 50.0, key=f"load_{i}")
        if val != state.base_load[i]:
            changed = True
            state.base_load[i] = val
        placeholders.append(st.empty())

if changed:
    state.req_power = state.base_load.copy()

# ───────── Step logic ─────────
if st.button("⏭ Step"):
    _, P_tmp, V_tmp, _ = solve_network(state.req_power)
    for i in range(N):
        # Ramp locally if voltage below threshold and inverter not at max
        if V_tmp[i] < WARN_V and state.req_power[i] < CAP_W:
            state.req_power[i] = min(state.req_power[i] + STEP_W, CAP_W)

# ───────── Final solve ───────── ─────────
leader_v, P_out, V_node, drop_seg = solve_network(state.req_power)

for i in range(N):
    placeholders[i].markdown(f"**Output:** {P_out[i]:.0f} W")

# ───────── Metrics ─────────
TOTAL_W = sum(P_out)
shift_hz = max(0.0, (TOTAL_W - N*CAP_W) / 1000 * 0.5)
col1, col2, col3 = st.columns(3)
col1.metric("Total Output (W)", f"{TOTAL_W:.0f}")
col2.metric("Leader V (V)", f"{leader_v:.1f}")
col3.metric("Freq (Hz)", f"{F_NOM - shift_hz:.2f}")

# ───────── Plot ─────────
fig, ax = plt.subplots(figsize=(12, 3.5))
for i in range(N):
    x = i * 2
    # pole
    ax.plot([x, x], [0, 0.3], color='black')
    ax.plot([x-0.05, x+0.05], [0.3, 0.33], color='black')
    ax.text(x, 0.35, f"Inv {i+1}", ha='center', weight='bold')
    ax.text(x, 0.52, f"{V_node[i]:.0f} V", ha='center', fontsize=8, color='purple')

    # bars
    ax.bar(x-0.2, state.base_load[i]/10000, 0.15, bottom=0.6, color='orange')
    ax.bar(x+0.05, P_out[i]/10000,      0.15, bottom=0.6, color='steelblue')

    if i == leader_idx:
        ax.text(x, -0.05, "Leader", ha='center', va='top', fontsize=8, color='gold')

    # line to next node
    if i < N-1:
        ax.plot([x, x+2], [0.33, 0.33], color='gray', ls='--')
        mid = x + 1
        v_d = drop_seg[i]
        ax.text(mid, 0.36, f"{v_d:.2f} V", ha='center', fontsize=8, color='red')
        if v_d > 1e-3:
            surplus_left = sum(P_out[:i+1]) - sum(state.base_load[:i+1])
            arrow_dir = -1 if surplus_left < 0 else 1
            ax.annotate('', xy=(mid + 0.3*arrow_dir, 0.34), xytext=(mid - 0.3*arrow_dir, 0.34),
                        arrowprops=dict(arrowstyle='->', color='green'))

ax.set_xlim(-1, 2*N)
ax.set_ylim(-0.1, 1.3)
ax.axis('off')
st.pyplot(fig)

# ───────── Warning ─────────
if any(v < WARN_V for v in V_node):
    st.warning("Nodes below 225 V — press ⏭ Step until all recover.")


