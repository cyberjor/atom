import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

"""
Mesh‑Grid Inverter Simulator (time‑step)
• Sliders: local load per inverter (W)
• ⏭ Step: shifts 100 W at a time from a donor (with spare margin) to the overloaded leader until ≤2 kW
• Each inverter sees leader voltage minus cumulative line‑drop (1 Ω/km, 300 m span)
• Visual shows poles, loads (orange), inverter output (blue), voltage at each node, line drops and flow arrow
"""

# ----- UI -----
st.title("Mesh Grid Time‑Step Simulator")
SIDE = st.sidebar
SIDE.header("Configuration")
N = SIDE.slider("Number of Inverters", 2, 10, 4, key="n_inv")
leader_idx = SIDE.selectbox("Leader (grid-forming) inverter", range(N), format_func=lambda i: f"Inv {i+1}")
STEP_W = 100  # redistribution quantum

# ----- Constants -----
V_NOM = 230
F_NOM = 60.0
CAP   = 2000
V_MIN = 100
WARN  = 225
R_LINE = 0.3        # Ω per 300 m segment (1 Ω/km)

# ----- Session init -----
if "base_load" not in st.session_state:
    st.session_state.base_load = [0.0]*N
    st.session_state.adj_power = [0.0]*N

if len(st.session_state.base_load)!=N:
    st.session_state.base_load = [0.0]*N
    st.session_state.adj_power = [0.0]*N

# ----- Load sliders -----
SIDE.subheader("Local Loads (W)")
changed=False
for i in range(N):
    val=SIDE.slider(f"Inv {i+1}",0.0,3000.0,st.session_state.base_load[i],50.0,key=f"load_{i}")
    if val!=st.session_state.base_load[i]:
        changed=True
        st.session_state.base_load[i]=val

if changed:
    st.session_state.adj_power = st.session_state.base_load.copy()

# ----- Step Button -----
if st.button("⏭ Step"):
    leader_p = st.session_state.adj_power[leader_idx]
    if leader_p>CAP:
        deficit=min(leader_p-CAP,STEP_W)
        margins=[(i,CAP-st.session_state.adj_power[i]) for i in range(N) if i!=leader_idx and CAP-st.session_state.adj_power[i]>0]
        if margins:
            donor=max(margins,key=lambda m:m[1])[0]
            give=min(deficit, CAP-st.session_state.adj_power[donor])
            st.session_state.adj_power[donor]+=give
            st.session_state.adj_power[leader_idx]-=give

# ----- Electrical model -----

def inv_model(p_req,v):
    p_out=min(p_req,CAP)
    i_out=p_out/v if v else 0
    return p_out,i_out

leader_p=st.session_state.adj_power[leader_idx]
leader_v=V_NOM if leader_p<=CAP else max(CAP/leader_p*V_NOM,V_MIN)

p_out=[]; currents=[]; node_V=[]; seg_drop=[]
cum_drop=0
for i in range(N):
    v_node=leader_v-cum_drop
    node_V.append(v_node)
    p,i_out=inv_model(st.session_state.adj_power[i],v_node)
    p_out.append(p); currents.append(i_out)
    if i<N-1:
        surplus=p_out[i]-st.session_state.base_load[i]
        line_I=surplus/v_node
        drop=abs(line_I)*R_LINE
        seg_drop.append(drop)
        cum_drop+=drop

# ----- Metrics -----
TOT=np.sum(p_out)
shift=max(0,(TOT-N*CAP)/1000*0.5)
col1,col2,col3=st.columns(3)
col1.metric("Total Power (W)",f"{TOT:.0f}")
col2.metric("Leader V (V)",f"{leader_v:.1f}")
col3.metric("Freq (Hz)",f"{F_NOM-shift:.2f}")

# ----- Plot -----
fig,ax=plt.subplots(figsize=(12,3.5))

cum_drop=0
for i in range(N):
    x=i*2
    # Poles & labels
    ax.plot([x,x],[0,0.3],color='black')
    ax.plot([x-0.05,x+0.05],[0.3,0.33],color='black')
    ax.text(x,0.35,f"Inv {i+1}",ha='center',weight='bold')
    ax.text(x,0.52,f"{node_V[i]:.0f} V",ha='center',fontsize=8,color='purple')
    # bars
    ax.bar(x-0.2, st.session_state.base_load[i]/10000,0.15,bottom=0.6,color='orange')
    ax.bar(x+0.05,p_out[i]/10000,0.15,bottom=0.6,color='steelblue')
    if i==leader_idx:
        ax.text(x,-0.05,"Leader",ha='center',va='top',fontsize=8,color='gold')
    # line (between i and i+1)
    if i < N-1:
        ax.plot([x, x+2], [0.33, 0.33], color='gray', ls='--')
        mid = (x + x + 2) / 2

        # Voltage drop on this segment
        ax.text(mid, 0.36, f"{seg_drop[i]:.2f} V", ha='center', fontsize=8, color='red')

        # Draw arrow **toward the leader** when there is non‑zero surplus/deficit
        if abs(seg_drop[i]) > 1e-3:
            surplus = p_out[i] - st.session_state.base_load[i]
            # Determine leader direction: -1 (left) if leader is left of segment, +1 (right) otherwise
            lead_dir = -1 if leader_idx <= i else 1
            # Arrow points from surplus node toward leader
            direction = -lead_dir if surplus > 0 else lead_dir
            ax.annotate('',
                        xy=(mid + 0.3 * direction, 0.34),
                        xytext=(mid - 0.3 * direction, 0.34),
                        arrowprops=dict(arrowstyle='->', color='green'))
        cum_drop += seg_drop[i]

ax.set_xlim(-1,2*N)
ax.set_ylim(-0.1,1.3)
ax.axis('off')
st.pyplot(fig)

# ----- Warnings -----
if leader_v<V_NOM:
    st.warning("Leader voltage sagging – press ⏭ Step to redistribute load.")

