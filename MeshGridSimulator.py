import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

"""Mesh‑Grid Inverter Simulator (local voltage‑driven response)

Update highlights
─────────────────
• **Line current & voltage‑drop** use the actual upstream node voltage, not the nominal 230 V.
• A node ramps its inverter by 100 W/step **only when**
    1. its sensed voltage < 225 V **and**
    2. its own inverter output is still below its local load (needs support).
• If upstream surplus already satisfies the local load, that node will no longer ramp and its voltage will recover.
"""

# ---------------- UI ----------------
st.title("Mesh Grid Time‑Step Simulator")
SIDE = st.sidebar
SIDE.header("Configuration")
N = SIDE.slider("Number of Inverters", 2, 10, 4)
leader_idx = SIDE.selectbox("Leader (grid‑forming) inverter", range(N), format_func=lambda i: f"Inv {i+1}")
STEP_W = 100  # W per local step

# --------------- Constants ---------------
V_NOM   = 230.0
F_NOM   = 60.0
CAP_W   = 2000.0
WARN_V  = 225.0
MIN_V   = 100.0
R_LINE  = 0.3        # Ω per 300 m span (1 Ω/km)

# --------------- State -------------------
if "base_load" not in st.session_state:
    st.session_state.base_load = [0.0]*N
    st.session_state.req_power  = [0.0]*N  # requested/incrementing value

if len(st.session_state.base_load) != N:
    st.session_state.base_load = [0.0]*N
    st.session_state.req_power  = [0.0]*N

# --------------- Helper ------------------

def inv_output(p_req, v):
    """Clip to CAP_W at given terminal voltage."""
    p_out = min(p_req, CAP_W)
    i_out = p_out / v if v else 0.0
    return p_out, i_out


def solve_network(req_power):
    """Return leader_v, lists: P_out, V_node, line_drop."""
    # leader voltage sag if over capacity
    leader_req = req_power[leader_idx]
    leader_v   = V_NOM if leader_req <= CAP_W else max(CAP_W/leader_req*V_NOM, MIN_V)

    P_out=[]; I_out=[]; V_node=[]; drop_seg=[]
    cum_drop=0.0
    for i in range(N):
        v = leader_v - cum_drop
        V_node.append(v)
        p,i = inv_output(req_power[i], v)
        P_out.append(p); I_out.append(i)
        if i < N-1:
            # net surplus power to left of next segment
            surplus_left = sum(float(x) for x in P_out[:i+1]) - sum(float(x) for x in st.session_state.base_load[:i+1])
            line_I = surplus_left / v if v else 0.0  # use upstream voltage
            vd = abs(line_I) * R_LINE
            drop_seg.append(vd)
            cum_drop += vd
    return leader_v, P_out, V_node, drop_seg

# --------------- Sidebar sliders ---------
SIDE.subheader("Local Loads (W)")
changed=False
placeholders=[]
for i in range(N):
    with SIDE.expander(f"Inverter {i+1}"):
        new_load = st.slider("Load", 0.0, 3000.0, st.session_state.base_load[i], 50.0, key=f"load_{i}")
        if new_load != st.session_state.base_load[i]:
            changed=True
            st.session_state.base_load[i]=new_load
        placeholders.append(st.empty())

if changed:
    # reset requested power to exactly match new loads (starting point)
    st.session_state.req_power = st.session_state.base_load.copy()

# --------------- Step Button -------------
if st.button("⏭ Step"):
    leader_v, P_out_tmp, V_tmp, _ = solve_network(st.session_state.req_power)
    for i in range(N):
        need = st.session_state.base_load[i] - P_out_tmp[i]
        if V_tmp[i] < WARN_V and need > 0 and st.session_state.req_power[i] < CAP_W:
            st.session_state.req_power[i] = min(st.session_state.req_power[i] + STEP_W, CAP_W)

# --------------- Final solve -------------
leader_v, P_out, V_node, drop_seg = solve_network(st.session_state.req_power)

# update placeholders
for i in range(N):
    placeholders[i].markdown(f"**Output:** {P_out[i]:.0f} W")

# --------------- Metrics -----------------
TOTAL_W = sum(P_out)
shift = max(0.0,(TOTAL_W - N*CAP_W)/1000*0.5)
col1,col2,col3 = st.columns(3)
col1.metric("Total Output (W)", f"{TOTAL_W:.0f}")
col2.metric("Leader V (V)", f"{leader_v:.1f}")
col3.metric("Freq (Hz)", f"{F_NOM - shift:.2f}")

# --------------- Plot --------------------
fig, ax = plt.subplots(figsize=(12,3.5))
for i in range(N):
    x = i*2
    ax.plot([x,x],[0,0.3],color='black')
    ax.plot([x-0.05,x+0.05],[0.3,0.33],color='black')
    ax.text(x,0.35,f"Inv {i+1}",ha='center',weight='bold')
    ax.text(x,0.52,f"{V_node[i]:.0f} V",ha='center',fontsize=8,color='purple')
    ax.bar(x-0.2, st.session_state.base_load[i]/10000, 0.15, bottom=0.6, color='orange')
    ax.bar(x+0.05, P_out[i]/10000,                0.15, bottom=0.6, color='steelblue')
    if i==leader_idx:
        ax.text(x,-0.05,"Leader",ha='center',va='top',fontsize=8,color='gold')
    # line to next
    if i < N-1:
        ax.plot([x,x+2],[0.33,0.33],color='gray',ls='--')
        mid=x+1
        vd=drop_seg[i]
        ax.text(mid,0.36,f"{vd:.2f} V",ha='center',fontsize=8,color='red')
        if vd>1e-3:
            surplus_left = sum(float(x) for x in P_out[:i+1]) - sum(float(x) for x in st.session_state.base_load[:i+1])
            direction = -1 if surplus_left<0 else 1
            ax.annotate('',xy=(mid+0.3*direction,0.34),xytext=(mid-0.3*direction,0.34),arrowprops=dict(arrowstyle='->',color='green'))

ax.set_xlim(-1, 2*N)
ax.set_ylim(-0.1, 1.3)
ax.axis('off')
st.pyplot(fig)

# --------------- Warning -----------------
if any(v < WARN_V for v in V_node):
    st.warning("Some nodes below 225 V — keep stepping until all recover.")

