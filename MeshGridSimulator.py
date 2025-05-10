import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

"""
Mesh-Grid Inverter Simulator (time-step)
Step logic updated:
• After each **⏭ Step**, every inverter whose sensed voltage is < 225 V and whose output < 2 kW will bump its output by 100 W (capped at 2 kW).
• No central redistribution—each inverter reacts locally to low voltage.
"""

# ---------- UI ----------
st.title("Mesh Grid Time-Step Simulator")
SIDE = st.sidebar
SIDE.header("Configuration")
N = SIDE.slider("Number of Inverters", 2, 10, 4, key="n_inv")
leader_idx = SIDE.selectbox("Leader (grid-forming) inverter", range(N), format_func=lambda i: f"Inv {i+1}")
STEP_W = 100  # W each inverter can increment per click

# ---------- Constants ----------
V_NOM = 230.0
F_NOM = 60.0
CAP    = 2000.0
V_MIN  = 100.0
WARN   = 225.0
R_LINE = 0.3  # Ω per 300 m span

# ---------- Session State ----------
if "base_load" not in st.session_state:
    st.session_state.base_load = [0.0]*N
    st.session_state.adj_power = [0.0]*N

if len(st.session_state.base_load)!=N:
    st.session_state.base_load = [0.0]*N
    st.session_state.adj_power = [0.0]*N

# ---------- Helper ----------

def inv_output(p_req, v):
    p_out = min(p_req, CAP)
    i_out = p_out / v if v else 0.0
    return p_out, i_out


def solve_grid(adj_power):
    leader_req = adj_power[leader_idx]
    leader_v = V_NOM if leader_req <= CAP else max(CAP / leader_req * V_NOM, V_MIN)
    p_out = []
    node_V = []
    seg_drop = []
    cum_drop = 0.0
    for i in range(N):
        v_node = leader_v - cum_drop
        node_V.append(v_node)
        p_i, _ = inv_output(adj_power[i], v_node)
        p_out.append(p_i)
        if i < N-1:
            surplus = sum(p_out[:i+1]) - sum(st.session_state.base_load[:i+1])
            line_I = surplus / V_NOM
            drop = abs(line_I)*R_LINE
            seg_drop.append(drop)
            cum_drop += drop
    return leader_v, p_out, node_V, seg_drop

# ---------- Load sliders ----------
SIDE.subheader("Local Loads (W)")
changed=False
placeholders=[]
for i in range(N):
    with SIDE.expander(f"Inverter {i+1}"):
        val=SIDE.slider("Load (W)",0.0,3000.0,st.session_state.base_load[i],50.0,key=f"load_{i}")
        if val!=st.session_state.base_load[i]:
            changed=True
            st.session_state.base_load[i]=val
        placeholders.append(st.empty())

if changed:
    st.session_state.adj_power = st.session_state.base_load.copy()

# ---------- Step button ----------
if st.button("⏭ Step"):
    # compute current voltages
    leader_v, p_out_tmp, node_V_tmp, _ = solve_grid(st.session_state.adj_power)
    # each inverter reacts locally if its sensed voltage < WARN
    for i in range(N):
        if node_V_tmp[i] < WARN and st.session_state.adj_power[i] < CAP:
            st.session_state.adj_power[i] = min(st.session_state.adj_power[i] + STEP_W, CAP)

# ---------- Final solve ----------
leader_v, p_out, node_V, seg_drop = solve_grid(st.session_state.adj_power)

# update placeholders
for i in range(N):
    placeholders[i].markdown(f"**Output:** {p_out[i]:.0f} W")

# ---------- Metrics ----------
TOT = sum(p_out)
shift = max(0.0,(TOT - N*CAP)/1000 *0.5)
col1,col2,col3=st.columns(3)
col1.metric("Total Power (W)",f"{TOT:.0f}")
col2.metric("Leader V (V)",f"{leader_v:.1f}")
col3.metric("Freq (Hz)",f"{F_NOM - shift:.2f}")

# ---------- Plot ----------
fig,ax=plt.subplots(figsize=(12,3.5))

cum_drop=0.0
for i in range(N):
    x=i*2
    ax.plot([x,x],[0,0.3],color='black')
    ax.plot([x-0.05,x+0.05],[0.3,0.33],color='black')
    ax.text(x,0.35,f"Inv {i+1}",ha='center',weight='bold')
    ax.text(x,0.52,f"{node_V[i]:.0f} V",ha='center',fontsize=8,color='purple')
    ax.bar(x-0.2,st.session_state.base_load[i]/10000,0.15,bottom=0.6,color='orange')
    ax.bar(x+0.05,p_out[i]/10000,0.15,bottom=0.6,color='steelblue')
    if i==leader_idx:
        ax.text(x,-0.05,"Leader",ha='center',va='top',fontsize=8,color='gold')
    if i<N-1:
        ax.plot([x,x+2],[0.33,0.33],color='gray',ls='--')
        mid=x+1
        v_d=seg_drop[i]
        ax.text(mid,0.36,f"{v_d:.2f} V",ha='center',fontsize=8,color='red')
        if v_d>1e-3:
            surplus_left=sum(p_out[:i+1])-sum(st.session_state.base_load[:i+1])
            direction=-1 if surplus_left<0 else 1
            ax.annotate('',xy=(mid+0.3*direction,0.34),xytext=(mid-0.3*direction,0.34),arrowprops=dict(arrowstyle='->',color='green'))
        cum_drop+=v_d

ax.set_xlim(-1,2*N)
ax.set_ylim(-0.1,1.3)
ax.axis('off')
st.pyplot(fig)

# ---------- Warnings ----------
if leader_v < V_NOM:
    st.warning("One or more inverters are voltage sagging – press ⏭ Step until all nodes ≥ 225 V.")
