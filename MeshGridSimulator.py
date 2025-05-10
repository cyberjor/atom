import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

"""
Mesh‑Grid Inverter Simulator (time‑step version)

• Sliders set the **local load** (W) each inverter must supply.
• The grid‑forming leader tries to carry its own load; if it overloads (>2 kW)
  each click of **⏭ Step** transfers 100 W of power from a follower inverter
  (with spare margin) toward the leader until equilibrium.
• Every inverter sees the leader voltage minus cumulative line‑drop.
  Voltage labels & line‑drop values update every step.
"""

# ------------------ UI ------------------
st.title("Mesh Grid Time‑Step Simulator")
SIDE = st.sidebar
SIDE.header("Configuration")
N = SIDE.slider("Number of Inverters", 2, 10, 4, key="n_inv")
leader_idx = SIDE.selectbox("Leader (grid‑forming) inverter", range(N), format_func=lambda i: f"Inv {i+1}")
STEP_W = 100  # W per step to redistribute

# ------------------ Constants ------------------
V_NOM = 230
CAP = 2000  # W
V_MIN = 100
WARN = 225
R_PER_KM = 1.0  # Ω / km
DIST_M = 300
R_LINE = DIST_M/1000 * R_PER_KM  # Ω per segment

# ------------------ Helper ------------------

def inv_model(p_req, v_grid):
    """Given requested power & grid voltage, return (p_out, current)."""
    p_out = min(p_req, CAP)
    i_out = p_out / v_grid if v_grid else 0
    return p_out, i_out

# ------------------ Session State Init ------------------
if "base_load" not in st.session_state:
    st.session_state.base_load = [0.0]*N
    st.session_state.adj_power = [0.0]*N

# Reset adjusted powers if user changed sliders or N
if len(st.session_state.base_load)!=N:
    st.session_state.base_load = [0.0]*N
    st.session_state.adj_power = [0.0]*N

# Collect sliders
SIDE.subheader("Loads (W)")
changed = False
for i in range(N):
    val = SIDE.slider(f"Inv {i+1} load", 0.0, 3000.0, st.session_state.base_load[i], 50.0, key=f"load_{i}")
    if val!=st.session_state.base_load[i]:
        changed=True
        st.session_state.base_load[i]=val

# If loads changed: reset adjusted powers to requested
if changed:
    st.session_state.adj_power = st.session_state.base_load.copy()

# ------------------ Time‑step button ------------------
if st.button("⏭ Step"):
    # One redistribution step of 100 W from a follower (with margin) to the leader if overloaded
    leader_p = st.session_state.adj_power[leader_idx]
    if leader_p > CAP:  # need relief
        deficit = min(leader_p-CAP, STEP_W)
        # find follower with max spare margin
        margins = [(i, CAP-st.session_state.adj_power[i]) for i in range(N) if i!=leader_idx]
        margins = [m for m in margins if m[1]>0]
        if margins:
            donor = max(margins, key=lambda m: m[1])[0]
            give = min(deficit, margins[margins.index((donor, CAP-st.session_state.adj_power[donor]))][1])
            st.session_state.adj_power[donor] += give
            st.session_state.adj_power[leader_idx]   -= give

# ------------------ Solve grid ------------------
# First, compute leader voltage (may sag if still >CAP)
leader_p = st.session_state.adj_power[leader_idx]
leader_v = V_NOM if leader_p<=CAP else max(CAP*(1)/leader_p*V_NOM, V_MIN)

p_out = []
current = []
seg_drops = []  # voltage drop per line
cum_drop = 0.0
for i in range(N):
    # sensed grid voltage at node i
    v_node = leader_v - cum_drop
    # inverter output power & current
    p_i, i_i = inv_model(st.session_state.adj_power[i], v_node)
    p_out.append(p_i)
    current.append(i_i)
    # compute current through line i->i+1 (positive away from leader)
    if i<N-1:
        # net surplus at node i
        surplus = p_out[i]-st.session_state.base_load[i]
        seg_I = surplus / v_node
        seg_drop = abs(seg_I)*R_LINE
        seg_drops.append(seg_drop)
        cum_drop += seg_drop

# last segment list length N-1
# ------------------ Metrics ------------------
TOT_P = sum(p_out)
shift = max(0,(TOT_P - N*CAP)/1000*0.5)

col1,col2,col3 = st.columns(3)
col1.metric("Total Output (W)", f"{TOT_P:.0f}")
col2.metric("Leader V (V)", f"{leader_v:.1f}")
col3.metric("Freq (Hz)", f"{F_NOM - shift:.2f}")

# ------------------ Plot ------------------
fig, ax = plt.subplots(figsize=(12,3.5))

cum_drop=0.0
for i in range(N):
    x=i*2
    v_node=leader_v - cum_drop
    # pole
    ax.plot([x,x],[0,0.3],color='black')
    ax.plot([x-0.05,x+0.05],[0.3,0.33],color='black')
    ax.text(x,0.35,f"Inv {i+1}",ha='center',weight='bold')
    ax.text(x,0.52,f"{v_node:.0f} V",ha='center',fontsize=8,color='purple')
    ax.bar(x-0.2, st.session_state.base_load[i]/10000, 0.15, bottom=0.6,color='orange')
    ax.bar(x+0.05,p_out[i]/10000,0.15,bottom=0.6,color='steelblue')
    if i==leader_idx:
        ax.text(x,-0.05,"Leader",ha='center',va='top',fontsize=8,color='gold')
    # draw line to next
    if i<N-1:
        ax.plot([x,x+2],[0.33,0.33],color='gray',ls='--')
        vdrop=seg_drops[i]
        mid=(x+x+2)/2
        ax.text(mid,0.36,f"{vdrop:.2f} V",ha='center',fontsize=8,color='red')
        if abs(vdrop)>0.01:
            dir_sign = 1 if p_out[i]>st.session_state.base_load[i] else -1
            ax.annotate('',xy=(mid+0.3*dir_sign,0.34),xytext=(mid-0.3*dir_sign,0.34),
                        arrowprops=dict(arrowstyle='->',color='green'))
        cum_drop+=vdrop

ax.set_xlim(-1,2*N)
ax.set_ylim(-0.1,1.3)
ax.axis('off')

st.pyplot(fig)

# ------------------ Warnings ------------------
if leader_v<V_NOM:
    st.warning("Leader voltage sagging – redistribute load via ⏭ Step.")

