import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

"""
Mesh‑Grid Inverter Simulator (time‑step, local‑voltage response)
Adds live **Current demand** read‑out (A) beneath each load slider alongside **Output** (W).
"""

# ───────── UI ─────────
st.title("Mesh Grid Time‑Step Simulator")
SIDE = st.sidebar
SIDE.header("Configuration")
N = SIDE.slider("Number of Inverters", 2, 10, 4)
leader_idx = SIDE.selectbox("Leader (grid‑forming) inverter", range(N), format_func=lambda i: f"Inv {i+1}")
STEP_W = 100  # W per step

# ───────── Constants ─────────
V_NOM   = 230.0
F_NOM   = 60.0
CAP_W   = 2000.0
WARN_V  = 225.0
MIN_V   = 100.0
R_LINE  = 0.3  # Ω / 300 m
I_MAX   = CAP_W / V_NOM

# ───────── State ─────────
state = st.session_state
if "base_load" not in state:
    state.base_load = [0.0]*N
    state.req_power = [0.0]*N

if len(state.base_load)!=N:
    state.base_load = [0.0]*N
    state.req_power = [0.0]*N

# ───────── Helpers ─────────

def inv_output(p_req, v_base):
    I_req = p_req / V_NOM if V_NOM else 0
    if I_req <= I_MAX:
        v_term = v_base
        p_out  = min(p_req, CAP_W)
    else:
        v_term = max(CAP_W / I_req, MIN_V)
        v_term = min(v_term, v_base)
        p_out  = CAP_W
    i_out = p_out / v_term if v_term else 0
    return p_out, i_out, v_term


def solve_network(req):
    leader_req = req[leader_idx]
    leader_v = V_NOM if leader_req<=CAP_W else max(CAP_W/leader_req*V_NOM, MIN_V)
    P_out=[]; V_node=[]; drop=[]
    cum_drop=0; surplus=0
    for i in range(N):
        v=leader_v-cum_drop
        p,_ ,_= inv_output(req[i], v)
        P_out.append(p)
        V_node.append(v)
        surplus += p - state.base_load[i]
        if i<N-1:
            I_line = surplus / v if v else 0
            vd = abs(I_line)*R_LINE
            drop.append(vd)
            cum_drop += vd
    return leader_v, P_out, V_node, drop

# ───────── Sidebar sliders ─────────
SIDE.subheader("Local Loads (W)")
changed=False
placeholder_cur=[]
placeholder_out=[]
for i in range(N):
    with SIDE.expander(f"Inverter {i+1}"):
        load = st.slider("Load",0.0,3000.0,state.base_load[i],50.0,key=f"load_{i}")
        if load!=state.base_load[i]:
            changed=True
            state.base_load[i]=load
        cur_ph=st.empty(); out_ph=st.empty()
        placeholder_cur.append(cur_ph); placeholder_out.append(out_ph)

if changed:
    state.req_power = state.base_load.copy()

# update current demand labels
for i in range(N):
    placeholder_cur[i].markdown(f"**Current demand:** {state.base_load[i]/V_NOM:.2f} A")

# ───────── Step logic ─────────
if st.button("⏭ Step"):
    _, P_tmp, V_tmp, _ = solve_network(state.req_power)
    for i in range(N):
        if V_tmp[i]<WARN_V and state.req_power[i]<CAP_W:
            state.req_power[i]=min(state.req_power[i]+STEP_W,CAP_W)

# ───────── Final solve ─────────
leader_v,P_out,V_node,drop=solve_network(state.req_power)
for i in range(N):
    placeholder_out[i].markdown(f"**Output:** {P_out[i]:.0f} W")

# ───────── Metrics ─────────
TOTAL=sum(P_out)
shift=max(0,(TOTAL-N*CAP_W)/1000*0.5)
col1,col2,col3=st.columns(3)
col1.metric("Total (W)",f"{TOTAL:.0f}")
col2.metric("Leader V (V)",f"{leader_v:.1f}")
col3.metric("Freq (Hz)",f"{F_NOM-shift:.2f}")

# ───────── Plot ─────────
fig,ax=plt.subplots(figsize=(12,3.5))
for i in range(N):
    x=i*2
    ax.plot([x,x],[0,0.3],color='black')
    ax.plot([x-0.05,x+0.05],[0.3,0.33],color='black')
    ax.text(x,0.35,f"Inv {i+1}",ha='center',weight='bold')
    ax.text(x,0.52,f"{V_node[i]:.0f} V",ha='center',fontsize=8,color='purple')
    ax.bar(x-0.2,state.base_load[i]/10000,0.15,bottom=0.6,color='orange')
    ax.bar(x+0.05,P_out[i]/10000,0.15,bottom=0.6,color='steelblue')
    if i==leader_idx:
        ax.text(x,-0.05,"Leader",ha='center',va='top',fontsize=8,color='gold')
    if i<N-1:
        ax.plot([x,x+2],[0.33,0.33],color='gray',ls='--')
        mid=x+1
        ax.text(mid,0.36,f"{drop[i]:.2f} V",ha='center',fontsize=8,color='red')
        if drop[i]>1e-3:
            surplus_left=sum(P_out[:i+1])-sum(state.base_load[:i+1])
            arrow=-1 if surplus_left<0 else 1
            ax.annotate('',xy=(mid+0.3*arrow,0.34),xytext=(mid-0.3*arrow,0.34),arrowprops=dict(arrowstyle='->',color='green'))
ax.set_xlim(-1,2*N)
ax.set_ylim(-0.1,1.3)
ax.axis('off')
st.pyplot(fig)

if any(v<WARN_V for v in V_node):
    st.warning("Nodes below 225 V — press ⏭ Step.")


