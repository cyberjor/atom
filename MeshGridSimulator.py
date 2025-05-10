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

def inv_terminal(I_req: float, v_up: float):
    """Return (I_out, P_out, v_term)."""
    if I_req <= I_MAX:
        v = v_up
        I_out = I_req
    else:
        v = max(CAP_W / I_req, MIN_V)
        v = min(v, v_up)
        I_out = I_req
    P_out = min(I_out * v, CAP_W)
    return I_out, P_out, v


def solve(req_I):
    """Sequential power‑flow solve.

    For each node from leader → right:
    1. Incoming surplus_P (W) arrives from the left.
    2. Remaining load to cover = max(load_i – surplus_P, 0).
    3. Inverter supplies I_sup = min(I_req, remaining_load / V_up, I_MAX).
       • If I_req > I_MAX, voltage droops so power ≤ 2 kW.
    4. Update surplus_P = surplus_P + P_supplied – load_i.
    5. Compute line drop to next node using that surplus_P.
    """
    leader_I = req_I[leader_idx]
    leader_v = V_NOM if leader_I <= I_MAX else max(CAP_W / leader_I, MIN_V)

    I_sup, P_sup, V_node, drop_seg = [], [], [], []
    cum_drop = 0.0
    surplus_P = 0.0  # power flowing rightward (W)

    for i in range(N):
        v_up = leader_v - cum_drop

        # incoming power meets part of the load
        remaining_P = max(state.load_W[i] - surplus_P, 0.0)
        I_needed   = remaining_P / v_up if v_up else 0.0

        # requested & limited current
        I_target = min(req_I[i], I_MAX)
        I_supplied = min(I_target, I_needed)

        # voltage sag if I_target > I_MAX (already limited) handled implicitly
        # If inverter asked for >I_MAX, it's already capped.
        # Compute terminal voltage for sag IF current demand > I_MAX
        if I_target > I_MAX:
            v_term = max(CAP_W / I_target, MIN_V)
            v_term = min(v_term, v_up)
        else:
            v_term = v_up

        P_out_i = I_supplied * v_term

        # record metrics
        I_sup.append(I_supplied)
        P_sup.append(P_out_i)
        V_node.append(v_term)

        # update surplus (positive → power available to right)
        surplus_P += P_out_i - state.load_W[i]

        # line drop to next node
        if i < N - 1:
            line_I = surplus_P / v_term if v_term else 0.0
            v_d = abs(line_I) * R_LINE
            drop_seg.append(v_d)
            cum_drop += v_d

    return leader_v, I_sup, P_sup, V_node, drop_seg

# ───────── Sidebar sliders ─────────
SIDE.subheader("Loads & Currents")
place_I_demand, place_I_sup, place_P_out = [], [], []
changed=False
for i in range(N):
    with SIDE.expander(f"Inverter {i+1}"):
        load = st.slider("Load (W)", 0.0, 3000.0, state.load_W[i], 50.0, key=f"load_{i}")
        if load!=state.load_W[i]:
            changed=True
            state.load_W[i]=load
        I_demand = load / V_NOM
        place_I_demand.append(st.markdown(f"**Current demand:** {I_demand:.2f} A"))
        place_I_sup.append(st.empty())
        place_P_out.append(st.empty())

if changed:
    state.req_I = [min(ld/V_NOM, I_MAX) for ld in state.load_W]

# ───────── Step button ─────────
if st.button("⏭ Step"):
    _, I_tmp, _, V_tmp, _ = solve(state.req_I)
    for i in range(N):
        if V_tmp[i] < WARN_V and state.req_I[i] < I_MAX:
            state.req_I[i] = min(state.req_I[i] + STEP_I, I_MAX)

# ───────── Final solve & sidebar update ─────────
leader_v, I_out, P_out, V_node, drop = solve(state.req_I)
for i in range(N):
    place_I_sup[i].markdown(f"**Current supplied:** {I_out[i]:.2f} A")
    place_P_out[i].markdown(f"**Power output:** {I_out[i]*V_node[i]:.0f} W")

# ───────── Metrics ─────────
TOTAL_W = sum(P_out)
shift = max(0.0, (TOTAL_W - N*CAP_W)/1000*0.5)
col1,col2,col3 = st.columns(3)
col1.metric("Total Power (W)", f"{TOTAL_W:.0f}")
col2.metric("Leader V (V)", f"{leader_v:.1f}")
col3.metric("Freq (Hz)", f"{F_NOM - shift:.2f}")

# ───────── Plot ─────────
fig,ax=plt.subplots(figsize=(12,3.5))
for i in range(N):
    x=i*2
    ax.plot([x,x],[0,0.3],color='black')
    ax.plot([x-0.05,x+0.05],[0.3,0.33],color='black')
    ax.text(x,0.35,f"Inv {i+1}",ha='center',weight='bold')
    ax.text(x,0.52,f"{V_node[i]:.0f} V",ha='center',fontsize=8,color='purple')
    ax.bar(x-0.2, state.load_W[i]/10000, 0.15, bottom=0.6, color='orange')
    ax.bar(x+0.05, P_out[i]/10000,          0.15, bottom=0.6, color='steelblue')
    if i==leader_idx:
        ax.text(x,-0.05,"Leader",ha='center',va='top',fontsize=8,color='gold')
    if i<N-1:
        ax.plot([x,x+2],[0.33,0.33],color='gray',ls='--')
        mid=x+1
        ax.text(mid,0.36,f"{drop[i]:.2f} V",ha='center',fontsize=8,color='red')
        if drop[i]>1e-3:
            surplus_left = sum(P_out[:i+1]) - sum(state.load_W[:i+1])
            arrow = -1 if surplus_left<0 else 1
            ax.annotate('',xy=(mid+0.3*arrow,0.34),xytext=(mid-0.3*arrow,0.34),arrowprops=dict(arrowstyle='->',color='green'))
ax.set_xlim(-1,2*N)
ax.set_ylim(-0.1,1.3)
ax.axis('off')
st.pyplot(fig)

if any(v < WARN_V for v in V_node):
    st.warning("Some nodes below 225 V — tap ⏭ Step until recovered.")
