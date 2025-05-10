import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

"""Mesh‑Grid Inverter Simulator – current‑driven version

Sidebar now displays:
• **Current demand (A)**  = load / 230 V
• **Current supplied (A)** = inverter output current
• **Power output (W)**     = current supplied × node voltage

Step logic: any node < 225 V ramps its current target by 0.5 A (≈ 115 W) up to 8.7 A.
Voltage sag arises when current demand exceeds 8.7 A.
"""

# ───────── Constants ─────────
V_NOM   = 230.0
F_NOM   = 60.0
CAP_W   = 2000.0
I_MAX   = CAP_W / V_NOM       # ≈ 8.70 A
WARN_V  = 225.0
MIN_V   = 100.0
R_LINE  = 0.3                 # Ω / 300 m span (1 Ω / km)
STEP_I  = 0.5                 # A per step increment ≈ 115 W

# ───────── UI ─────────
st.title("Mesh‑Grid Time‑Step Simulator – current mode")
SIDE = st.sidebar
SIDE.header("Configuration")
N = SIDE.slider("Number of Inverters", 2, 10, 4)
leader_idx = SIDE.selectbox("Leader inverter (grid‑forming)", range(N), format_func=lambda i: f"Inv {i+1}")

# ───────── State ─────────
state = st.session_state
if "load_W" not in state:
    state.load_W  = [0.0]*N   # user‑set load (W)
    state.req_I   = [0.0]*N   # inverter current target (A)

if len(state.load_W)!=N:
    state.load_W  = [0.0]*N
    state.req_I   = [0.0]*N

# ───────── Helper ─────────

def inv_terminal(I_req: float, I_need: float, v_up: float):
    """Return (I_out, P_out, v_term).
    • Inverter delivers I_out = min(I_req, I_need).
    • If that I_out > I_MAX → drop voltage so P ≤ 2 kW (v = CAP_W / I_out).
    • Voltage never exceeds upstream voltage nor goes below MIN_V.
    """
    I_out = min(I_req, I_need)
    if I_out > I_MAX:
        v = max(CAP_W / I_out, MIN_V)
        v = min(v, v_up)
    else:
        v = v_up
    P_out = I_out * v
    return I_out, P_out, v


def solve(req_I):
    """Two‑pass solve where leader voltage is recalculated using
    net current after right‑hand contributions.
    """
    def forward(v_leader):
        I_sup, P_sup, V_node, drop_seg = [], [], [], []
        cum_drop = 0.0
        surplus_P = 0.0
        leader_surplus = None  # surplus right after leader node computed
        for i in range(N):
            v_up = v_leader - cum_drop
            rem_P = max(state.load_W[i] - surplus_P, 0.0)
            I_need = rem_P / v_up if v_up else 0.0
            I_out, P_out, v_node = inv_terminal(req_I[i], I_need, v_up)
            I_sup.append(I_out); P_sup.append(P_out); V_node.append(v_node)
            surplus_P += P_out - state.load_W[i]
            if i == 0:
                leader_surplus = surplus_P  # capture immediately after leader
            if i < N-1:
                line_I = surplus_P / v_node if v_node else 0.0
                v_d = abs(line_I) * R_LINE
                drop_seg.append(v_d)
                cum_drop += v_d
        return I_sup, P_sup, V_node, drop_seg, leader_surplus

    # initial leader voltage based on its requested current alone
    leader_I_req = req_I[leader_idx]
    v_leader_initial = V_NOM if leader_I_req <= I_MAX else max(CAP_W / leader_I_req, MIN_V)

    I1, P1, V1, drop1, leader_surplus1 = forward(v_leader_initial)

        # power imported to leader from followers = max(total follower surplus, 0)
    imported_P = max(sum(P1[1:]) - sum(state.load_W[1:]), 0.0)
    eff_leader_I = max((state.load_W[0] - imported_P) / V_NOM, 0.0)

            v_leader_recovered = V_NOM if eff_leader_I <= I_MAX else max(CAP_W / eff_leader_I, MIN_V)
