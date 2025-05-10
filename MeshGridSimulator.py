import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

"""Mesh‑Grid Inverter Simulator – current‑driven version (fixed indentation)

Highlights
──────────
* Sidebar shows **Current demand (A)**, **Current supplied (A)** and **Power output (W)**.
* Two‑pass solver lets the leader’s voltage recover when followers supply power.
* Fixed indentation/syntax errors that caused crashes.
"""

# ───────── Constants ─────────
V_NOM   = 230.0
F_NOM   = 60.0
CAP_W   = 2000.0
I_MAX   = CAP_W / V_NOM       # 8.70 A
WARN_V  = 225.0
MIN_V   = 100.0
R_LINE  = 0.3                 # Ω / 300 m span (1 Ω/km)
STEP_I  = 0.5                 # A per step ≈ 115 W

# ───────── UI ─────────
st.title("Mesh‑Grid Time‑Step Simulator – current mode")
SIDE = st.sidebar
SIDE.header("Configuration")
N = SIDE.slider("Number of Inverters", 2, 10, 4)
leader_idx = SIDE.selectbox("Leader inverter (grid‑forming)", range(N), format_func=lambda i: f"Inv {i+1}")

# ───────── State ─────────
state = st.session_state
if "load_W" not in state:
    state.load_W = [0.0]*N     # user loads (W)
    state.req_I  = [0.0]*N     # requested current targets (A)

if len(state.load_W) != N:
    state.load_W = [0.0]*N
    state.req_I  = [0.0]*N

# ───────── Helpers ─────────

def inv_terminal(I_req: float, I_need: float, v_up: float):
    """Return (I_out, P_out, v_node) with sag if I_out > I_MAX."""
    I_out = min(I_req, I_need)
    if I_out > I_MAX:
        v_node = min(v_up, max(CAP_W / I_out, MIN_V))
    else:
        v_node = v_up
    P_out = I_out * v_node
    return I_out, P_out, v_node


def solve(req_I):
    """Two‑pass solve: forward → compute imported power → adjust leader voltage → forward again."""

    def forward(v_leader):
        I_sup, P_sup, V_node, drop_seg = [], [], [], []
        cum_drop = 0.0
        surplus_P = 0.0  # running surplus power (W)
        leader_surplus = 0.0
        for i in range(N):
            v_up = v_leader - cum_drop
            remaining_P = max(state.load_W[i] - surplus_P, 0.0)
            I_need = remaining_P / v_up if v_up else 0.0
            I_out, P_out, v_node = inv_terminal(req_I[i], I_need, v_up)
            I_sup.append(I_out); P_sup.append(P_out); V_node.append(v_node)
            surplus_P += P_out - state.load_W[i]
            if i == 0:
                leader_surplus = surplus_P  # surplus immediately after leader contribution
            if i < N-1:
                line_I = surplus_P / v_node if v_node else 0.0
                v_d = abs(line_I) * R_LINE
                drop_seg.append(v_d)
                cum_drop += v_d
        return I_sup, P_sup, V_node, drop_seg, leader_surplus

    # ── Pass 1 using requested leader current ──
    I_leader_req = state.req_I[leader_idx]
    v_leader_initial = V_NOM if I_leader_req <= I_MAX else max(CAP_W / I_leader_req, MIN_V)

    I1, P1, V1, drop1, leader_surplus1 = forward(v_leader_initial)

    # imported power to leader (negative surplus means import)
    imported_P = max(-leader_surplus1, 0.0)
    eff_I_leader = max((state.load_W[0] - imported_P) / V_NOM, 0.0)
    v_leader_recovered = V_NOM if eff_I_leader <= I_MAX else max(CAP_W / eff_I_leader, MIN_V)

    if abs(v_leader_recovered - v_leader_initial) < 1e-3:
        return v_leader_recovered, I1, P1, V1, drop1

    # ── Pass 2 with recovered leader voltage ──
    return forward(v_leader_recovered)[0:5]

# ───────── Sidebar controls ─────────
SIDE.subheader("Loads & Currents")
place_I_demand = []
place_I_sup = []
place_P_out = []
changed = False
for i in range(N):
    with SIDE.expander(f"Inverter {i+1}"):
        load = st.slider("Load (W)", 0.0, 3000.0, state.load_W[i], 50.0, key=f"load_{i}")
        if load != state.load_W[i]:
            changed = True
            state.load_W[i] = load
        I_demand = load / V_NOM
        place_I_demand.append(st.markdown(f"**Current demand:** {I_demand:.2f} A"))
        place_I_sup.append(st.empty())
        place_P_out.append(st.empty())

# reset current targets to demand on slider change (no cap now)
if changed:
    state.req_I = [ld / V_NOM for ld in state.load_W]

# ───────── Step button ─────────
if st.button("⏭ Step"):
    _, I_tmp, _, V_tmp, _ = solve(state.req_I)
    for i in range(N):
        if V_tmp[i] < WARN_V and state.req_I[i] < I_MAX:
            state.req_I[i] = min(state.req_I[i] + STEP_I, I_MAX)

# ───────── Solve & update sidebar ─────────
leader_v, I_out, P_out, V_node, drop = solve(state.req_I)
for i in range(N):
    place_I_sup[i].markdown(f"**Current supplied:** {I_out[i]:.2f} A")
    place_P_out[i].markdown(f"**Power output:** {P_out[i]:.0f} W")

# ───────── Metrics ─────────
TOTAL_W = sum(P_out)
shift = max(0.0, (TOTAL_W - N * CAP_W) / 1000 * 0.5)
col1, col2, col3 = st.columns(3)
col1.metric("Total Power (W)", f"{TOTAL_W:.0f}")
col2.metric("Leader V (V)", f"{leader_v:.1f}")
col3.metric("Freq (Hz)", f"{F_NOM - shift:.2f}")

# ───────── Plot ─────────
fig, ax = plt.subplots(figsize=(12, 3.5))
for i in range(N):
    x = i * 2
    ax.plot([x, x], [0, 0.3], color='black')
    ax.plot([x - 0.05, x + 0.05], [0.3, 0.33], color='black')
    ax.text(x, 0.35, f"Inv {i+1}", ha='center', weight='bold')
    ax.text(x, 0.52, f"{V_node[i]:.0f} V", ha='center', fontsize=8, color='purple')
    ax.bar(x - 0.2, state.load_W[i] / 10000, 0.15, bottom=0.6, color='orange')
    ax.bar(x + 0.05, P_out[i] / 10000, 0.15, bottom=0.6, color='steelblue')
    if i == leader_idx:
        ax.text(x, -0.05, "Leader", ha='center', va='top', fontsize=8, color='gold')
    if i < N - 1:
        ax.plot([x, x + 2], [0.33, 0.33], color='gray', ls='--')
        mid = x + 1
        ax.text(mid, 0.36, f"{drop[i]:.2f} V", ha='center', fontsize=8, color='red')
        if drop[i] > 1e-3:
            surplus_left = sum(P_out[:i + 1]) - sum(state.load_W[:i + 1])
            arrow = -1 if surplus_left < 0 else 1
            ax.annotate('', xy=(mid + 0.3 * arrow, 0.34), xytext=(mid - 0.3 * arrow, 0.34),
                        arrowprops=dict(arrowstyle='->', color='green'))
ax.set_xlim(-1, 2 * N)
ax.set_ylim(-0.1, 1.3)
ax.axis('off')
st.pyplot(fig)

if any(v < WARN_V for v in V_node):
    st.warning("Some nodes below 225 V — tap ⏭ Step until recovered.")
