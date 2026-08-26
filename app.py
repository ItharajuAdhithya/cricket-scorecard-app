import streamlit as st
import copy
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

st.set_page_config(page_title="Ultimate Box Cricket Scorecard", layout="centered")
st.title("🏏 Ultimate Box Cricket Scorecard")

# --- INITIALIZE MASTER STATE ---
if "initialized" not in st.session_state:
    st.session_state.max_overs = 10
    st.session_state.innings = 1
    
    st.session_state.team_a_name = "Team Alpha"
    st.session_state.team_b_name = "Team Beta"
    st.session_state.team_a_players = [f"Player A{i}" for i in range(1, 9)]
    st.session_state.team_b_players = [f"Player B{i}" for i in range(1, 9)]
    
    st.session_state.i1_runs = 0
    st.session_state.i1_wickets = 0
    st.session_state.i1_balls = 0
    st.session_state.i2_runs = 0
    st.session_state.i2_wickets = 0
    st.session_state.i2_balls = 0
    
    # DRS Review Counters (3 per team)
    st.session_state.i1_drs_left = 3
    st.session_state.i2_drs_left = 3
    
    st.session_state.history = []
    st.session_state.undo_stack = []
    st.session_state.player_stats = {}
    st.session_state.pending_wicket = False
    st.session_state.drs_active = False
    
    for p in st.session_state.team_a_players + st.session_state.team_b_players:
        st.session_state.player_stats[p] = {"runs": 0, "balls": 0, "4s": 0, "6s": 0, "b_balls": 0, "b_runs": 0, "wickets": 0, "out_how": "not out"}
        
    st.session_state.striker = st.session_state.team_a_players[0]
    st.session_state.non_striker = st.session_state.team_a_players[1]
    st.session_state.current_bowler = st.session_state.team_b_players[0]
    st.session_state.initialized = True

def save_snapshot():
    snapshot = {
        "i1_runs": st.session_state.i1_runs,
        "i1_wickets": st.session_state.i1_wickets,
        "i1_balls": st.session_state.i1_balls,
        "i2_runs": st.session_state.i2_runs,
        "i2_wickets": st.session_state.i2_wickets,
        "i2_balls": st.session_state.i2_balls,
        "i1_drs_left": st.session_state.i1_drs_left,
        "i2_drs_left": st.session_state.i2_drs_left,
        "innings": st.session_state.innings,
        "history": copy.deepcopy(st.session_state.history),
        "player_stats": copy.deepcopy(st.session_state.player_stats),
        "striker": st.session_state.striker,
        "non_striker": st.session_state.non_striker,
        "current_bowler": st.session_state.current_bowler,
        "pending_wicket": st.session_state.pending_wicket,
        "drs_active": st.session_state.drs_active
    }
    st.session_state.undo_stack.append(snapshot)

def undo_last():
    if st.session_state.undo_stack:
        snap = st.session_state.undo_stack.pop()
        for key, val in snap.items():
            st.session_state[key] = val
        st.rerun()

# --- CUSTOM SETUP (EDIT NAMES & SELECT PLAYERS) ---
with st.expander("⚙️ Match Setup & Edit Player Names"):
    st.session_state.max_overs = st.number_input("Max Overs", min_value=1, value=st.session_state.max_overs)
    
    c_t1, c_t2 = st.columns(2)
    st.session_state.team_a_name = c_t1.text_input("Team 1 Name", value=st.session_state.team_a_name)
    st.session_state.team_b_name = c_t2.text_input("Team 2 Name", value=st.session_state.team_b_name)
    
    batting_squad = st.session_state.team_a_players if st.session_state.innings == 1 else st.session_state.team_b_players
    bowling_squad = st.session_state.team_b_players if st.session_state.innings == 1 else st.session_state.team_a_players
    
    c1, c2, c3 = st.columns(3)
    st.session_state.striker = c1.selectbox("Striker", batting_squad, index=batting_squad.index(st.session_state.striker) if st.session_state.striker in batting_squad else 0)
    st.session_state.non_striker = c2.selectbox("Non-Striker", batting_squad, index=batting_squad.index(st.session_state.non_striker) if st.session_state.non_striker in batting_squad else 1)
    st.session_state.current_bowler = c3.selectbox("Bowler", bowling_squad, index=bowling_squad.index(st.session_state.current_bowler) if st.session_state.current_bowler in bowling_squad else 0)
    
    st.subheader("✏️ Rename Active Players")
    c_edit1, c_edit2, c_edit3 = st.columns(3)
    new_s = c_edit1.text_input("Edit Striker Name", value=st.session_state.striker)
    new_ns = c_edit2.text_input("Edit Non-Striker Name", value=st.session_state.non_striker)
    new_bw = c_edit3.text_input("Edit Bowler Name", value=st.session_state.current_bowler)
    
    if st.button("Apply Renames"):
        if new_s != st.session_state.striker:
            st.session_state.player_stats[new_s] = st.session_state.player_stats.pop(st.session_state.striker)
            idx = batting_squad.index(st.session_state.striker)
            batting_squad[idx] = new_s
            st.session_state.striker = new_s
        if new_ns != st.session_state.non_striker:
            st.session_state.player_stats[new_ns] = st.session_state.player_stats.pop(st.session_state.non_striker)
            idx = batting_squad.index(st.session_state.non_striker)
            batting_squad[idx] = new_ns
            st.session_state.non_striker = new_ns
        if new_bw != st.session_state.current_bowler:
            st.session_state.player_stats[new_bw] = st.session_state.player_stats.pop(st.session_state.current_bowler)
            idx = bowling_squad.index(st.session_state.current_bowler)
            bowling_squad[idx] = new_bw
            st.session_state.current_bowler = new_bw
        st.rerun()

# --- SCORE & DRS DISPLAY ---
tot_runs = st.session_state.i1_runs if st.session_state.innings == 1 else st.session_state.i2_runs
tot_w = st.session_state.i1_wickets if st.session_state.innings == 1 else st.session_state.i2_wickets
tot_b = st.session_state.i1_balls if st.session_state.innings == 1 else st.session_state.i2_balls
max_b = st.session_state.max_overs * 6
drs_remaining = st.session_state.i1_drs_left if st.session_state.innings == 1 else st.session_state.i2_drs_left

overs_fmt = f"{tot_b // 6}.{tot_b % 6}"
crr = (tot_runs / (tot_b / 6)) if tot_b > 0 else 0.0

if st.session_state.innings == 1:
    st.header(f"1st Innings — {st.session_state.team_a_name}")
    st.metric("Score", f"{tot_runs} / {tot_w}", f"Overs: {overs_fmt} / {st.session_state.max_overs} | CRR: {crr:.2f} | DRS Left: {drs_remaining}/3 📺")
else:
    st.header(f"2nd Innings — {st.session_state.team_b_name}")
    target = st.session_state.i1_runs + 1
    runs_needed = target - st.session_state.i2_runs
    balls_left = max_b - st.session_state.i2_balls
    
    if runs_needed <= 0:
        st.balloons()
        st.success(f"🏆 {st.session_state.team_b_name} won by {len(st.session_state.team_b_players) - tot_w} wickets!")
    elif tot_w >= len(st.session_state.team_b_players) - 1 or balls_left <= 0:
        st.error(f"🏆 {st.session_state.team_a_name} won by {runs_needed - 1} runs!")
    else:
        st.info(f"🎯 **Target:** {target} runs | Need **{runs_needed}** runs off **{balls_left}** balls")
    
    st.metric("Score", f"{tot_runs} / {tot_w}", f"Overs: {overs_fmt} / {st.session_state.max_overs} | CRR: {crr:.2f} | DRS Left: {drs_remaining}/3 📺")

# --- RECENT BALL TRACKER ---
if st.session_state.history:
    badges = []
    for b in st.session_state.history[-12:]:
        if b in ["4", "6"]: badges.append(f"🟢 **{b}**")
        elif "W" in b: badges.append(f"🔴 **{b}**")
        elif any(x in b for x in ["WD", "NB", "B", "LB"]): badges.append(f"🟡 **{b}**")
        else: badges.append(f"⚪ **{b}**")
    st.markdown(" | ".join(badges))

st.divider()

# --- LIVE PLAYER CARDS ---
s_p = st.session_state.player_stats[st.session_state.striker]
ns_p = st.session_state.player_stats[st.session_state.non_striker]
bw_p = st.session_state.player_stats[st.session_state.current_bowler]

s_sr = (s_p["runs"] / s_p["balls"] * 100) if s_p["balls"] > 0 else 0.0
ns_sr = (ns_p["runs"] / ns_p["balls"] * 100) if ns_p["balls"] > 0 else 0.0
bw_ov = f"{bw_p['b_balls'] // 6}.{bw_p['b_balls'] % 6}"
bw_ec = (bw_p['b_runs'] / (bw_p['b_balls'] / 6)) if bw_p['b_balls'] > 0 else 0.0

col_b1, col_b2 = st.columns(2)
col_b1.markdown(f"**🏏 {st.session_state.striker} \***\n\n**{s_p['runs']}** ({s_p['balls']}) | 4s: {s_p['4s']} | 6s: {s_p['6s']} | SR: {s_sr:.1f}")
col_b2.markdown(f"**🏏 {st.session_state.non_striker}**\n\n**{ns_p['runs']}** ({ns_p['balls']}) | 4s: {ns_p['4s']} | 6s: {ns_p['6s']} | SR: {ns_sr:.1f}")
st.markdown(f"**⚾ Bowler: {st.session_state.current_bowler}** — Overs: {bw_ov} | Wkts: {bw_p['wickets']} | Runs: {bw_p['b_runs']} | Econ: {bw_ec:.2f}")

st.divider()

# --- DISMISSAL MODAL & DRS HAWKEYE ENGINE ---
if st.session_state.pending_wicket:
    st.warning("⚠️ **Select Wicket Type:**")
    
    # Check if DRS reviews are available for the current team
    drs_avail = drs_remaining > 0
    w_options = ["Bowled 🎳", "Caught 🖐️", "Run Out 🏃", "Hit Wicket 🪵"]
    if drs_avail:
        w_options.append(f"🔍 DRS Review (LBW) [{drs_remaining} left]")
    else:
        st.error("🚫 No DRS Reviews remaining for this team!")

    w_type = st.radio("How Out?", w_options, horizontal=True)
    
    if "DRS Review" in w_type:
        st.session_state.drs_active = True
    else:
        st.session_state.drs_active = False

    if st.session_state.drs_active:
        st.info(f"📐 **PROFESSOR HAWKEYE DRS ENGINE** (Reviews Remaining: {drs_remaining})")
        drs_pitch = st.selectbox("1. Pitching Line", ["In Line", "Outside Off", "Outside Leg"])
        drs_impact = st.selectbox("2. Impact Line", ["In Line", "Outside Off"])
        drs_length = st.selectbox("3. Delivery Length", ["Yorker 🎯", "Full Length", "Good Length", "Short Ball"])
        drs_bounce = st.selectbox("4. Bounce Height", ["Low (Below Knee)", "Medium (At Knee)", "High (Thigh / Waist)"])
        drs_move = st.selectbox("5. Movement / Spin", ["Straight", "In-Swinger / Turn IN", "Out-Swinger / Turn OUT"])

        # Calculate Hawkeye Verdict
        is_out = True
        reasons = []

        # Pitching Rules
        if drs_pitch == "Outside Leg":
            is_out = False
            reasons.append("❌ Pitching Outside Leg")

        # Impact Rules
        if drs_impact == "Outside Off":
            is_out = False
            reasons.append("❌ Impact Outside Off")

        # Yorker Specific Logic vs Standard Bounce Rules
        if drs_length == "Yorker 🎯":
            if drs_pitch != "Outside Leg" and drs_impact != "Outside Off":
                is_out = True
                reasons.append("🎯 Perfect Yorker (Under the bat / Hitting base of stumps)")
        else:
            if drs_bounce == "High (Thigh / Waist)" or drs_length == "Short Ball":
                is_out = False
                reasons.append("❌ Bouncing Over Stumps")

        # Movement / Drift Rules
        if drs_move == "Out-Swinger / Turn OUT" and drs_pitch == "Outside Off":
            is_out = False
            reasons.append("❌ Missing Off Stump (Swinging Away)")

        if drs_move == "In-Swinger / Turn IN" and drs_pitch == "In Line" and drs_impact == "In Line":
            is_out = True
            reasons.append("✅ Turning Into Stumps")

        st.subheader("📺 HAWKEYE PREDICTED TRAJECTORY")
        if is_out:
            st.error("🔴 **VERDICT: OUT (HITTING STUMPS)** — Review Lost! ❌")
        else:
            st.success("🟢 **VERDICT: NOT OUT** (" + ", ".join(reasons) + ") — Review Retained! 🔁")

    batting_squad = st.session_state.team_a_players if st.session_state.innings == 1 else st.session_state.team_b_players
    next_batters = [p for p in batting_squad if p not in [st.session_state.striker, st.session_state.non_striker] and st.session_state.player_stats[p]["out_how"] == "not out"]
    
    new_batter = st.selectbox("Next Batter Coming In", next_batters if next_batters else ["No more batters"])

    c_confirm, c_cancel = st.columns(2)
    if c_confirm.button("Confirm Decision"):
        save_snapshot()
        out_player = st.session_state.striker
        st.session_state.player_stats[out_player]["balls"] += 1
        
        if st.session_state.drs_active and not is_out:
            # Revert if DRS returned NOT OUT -> Review Retained!
            st.session_state.history.append("0")
            bw_p["b_balls"] += 1
            if st.session_state.innings == 1: st.session_state.i1_balls += 1
            else: st.session_state.i2_balls += 1
        else:
            # Record Out & Deduct Review if DRS was used and lost
            if st.session_state.drs_active and is_out:
                if st.session_state.innings == 1:
                    st.session_state.i1_drs_left -= 1
                else:
                    st.session_state.i2_drs_left -= 1

            lbl_type = "LBW" if st.session_state.drs_active else w_type.split()[0]
            if "Run Out" not in w_type:
                bw_p["wickets"] += 1
                st.session_state.player_stats[out_player]["out_how"] = f"{lbl_type} b {st.session_state.current_bowler}"
            else:
                st.session_state.player_stats[out_player]["out_how"] = "run out"

            bw_p["b_balls"] += 1
            if st.session_state.innings == 1:
                st.session_state.i1_wickets += 1
                st.session_state.i1_balls += 1
            else:
                st.session_state.i2_wickets += 1
                st.session_state.i2_balls += 1
                
            st.session_state.history.append(f"W({lbl_type})")
            if new_batter != "No more batters":
                st.session_state.striker = new_batter

        st.session_state.pending_wicket = False
        st.session_state.drs_active = False
        st.rerun()

    if c_cancel.button("Cancel"):
        st.session_state.pending_wicket = False
        st.session_state.drs_active = False
        st.rerun()

# --- SCORING CONTROLS ---
st.subheader("⚡ Record Delivery")
c1, c2, c3, c4 = st.columns(4)
r0 = c1.button("+0 Dot")
r1 = c2.button("+1 Run")
r2 = c3.button("+2 Runs")
r3 = c4.button("+3 Runs")

c5, c6, c7 = st.columns(3)
r4 = c5.button("FOUR (+4)")
r6 = c6.button("SIX (+6)")
wk = c7.button("❌ WICKET / DRS")

st.subheader("🚨 Extras")
e1, e2, e3, e4, e5 = st.columns(5)
wd = e1.button("Wide (+1)")
nb = e2.button("No Ball (+1)")
b1 = e3.button("Bye (+1)")
lb1 = e4.button("LegBye (+1)")
wd4 = e5.button("Wide+4 (5)")

if st.button("↩️ Undo Last Delivery"):
    undo_last()

if wk:
    st.session_state.pending_wicket = True
    st.rerun()

runs = 0; is_l = True; is_4 = False; is_6 = False; lbl = ""
if r0: lbl = "0"
elif r1: runs = 1; lbl = "1"
elif r2: runs = 2; lbl = "2"
elif r3: runs = 3; lbl = "3"
elif r4: runs = 4; is_4 = True; lbl = "4"
elif r6: runs = 6; is_6 = True; lbl = "6"
elif wd: runs = 1; is_l = False; lbl = "WD"
elif wd4: runs = 5; is_l = False; lbl = "5WD"
elif nb: runs = 1; is_l = False; lbl = "NB"
elif b1: runs = 1; is_l = True; lbl = "1B"
elif lb1: runs = 1; is_l = True; lbl = "1LB"

if any([r0, r1, r2, r3, r4, r6, wd, wd4, nb, b1, lb1]):
    save_snapshot()
    
    if st.session_state.innings == 1:
        st.session_state.i1_runs += runs
        if is_l: st.session_state.i1_balls += 1
    else:
        st.session_state.i2_runs += runs
        if is_l: st.session_state.i2_balls += 1

    bw_p["b_runs"] += runs
    if is_l: bw_p["b_balls"] += 1

    if is_l: s_p["balls"] += 1
    if lbl not in ["WD", "5WD", "1B", "1LB"]:
        s_p["runs"] += runs
        if is_4: s_p["4s"] += 1
        if is_6: s_p["6s"] += 1
        
    if runs in [1, 3]:
        st.session_state.striker, st.session_state.non_striker = st.session_state.non_striker, st.session_state.striker
    if is_l and tot_b > 0 and (tot_b + 1) % 6 == 0:
        st.session_state.striker, st.session_state.non_striker = st.session_state.non_striker, st.session_state.striker
            
    st.session_state.history.append(lbl)
    
    if st.session_state.innings == 1 and (st.session_state.i1_wickets >= len(st.session_state.team_a_players) - 1 or st.session_state.i1_balls >= max_b):
        st.session_state.innings = 2
        st.session_state.striker = st.session_state.team_b_players[0]
        st.session_state.non_striker = st.session_state.team_b_players[1]
        st.session_state.current_bowler = st.session_state.team_a_players[0]
        
    st.rerun()

# --- FULL SCORECARD SUMMARY & PDF EXPORT ---
with st.expander("📊 Full Match Scorecard & PDF Export"):
    st.write("### Batting Performance")
    bat_data = []
    for p, s in st.session_state.player_stats.items():
        if s["balls"] > 0 or s["runs"] > 0 or s["out_how"] != "not out":
            sr = (s["runs"] / s["balls"] * 100) if s["balls"] > 0 else 0
            bat_data.append({"Player": p, "Status": s["out_how"], "Runs": s["runs"], "Balls": s["balls"], "4s": s["4s"], "6s": s["6s"], "SR": f"{sr:.1f}"})
    if bat_data: st.table(bat_data)
    
    def generate_pdf():
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = [Paragraph("Match Summary Report", styles['Title']), Spacer(1, 12)]
        
        summary_data = [["Innings", "Runs", "Wickets", "Overs", "DRS Remaining"],
                        ["1st Innings", str(st.session_state.i1_runs), str(st.session_state.i1_wickets), f"{st.session_state.i1_balls//6}.{st.session_state.i1_balls%6}", f"{st.session_state.i1_drs_left}/3"],
                        ["2nd Innings", str(st.session_state.i2_runs), str(st.session_state.i2_wickets), f"{st.session_state.i2_balls//6}.{st.session_state.i2_balls%6}", f"{st.session_state.i2_drs_left}/3"]]
        t = Table(summary_data)
        t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.grey), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke)]))
        elements.append(t)
        
        doc.build(elements)
        buffer.seek(0)
        return buffer

    st.download_button(
        label="📄 Download PDF Scorecard Report",
        data=generate_pdf(),
        file_name="match_scorecard.pdf",
        mime="application/pdf"
    )

st.divider()

if st.button("🔄 Reset Entire Match"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()