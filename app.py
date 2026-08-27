import streamlit as st
import copy
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

st.set_page_config(page_title="ICC World Feed Scorecard", layout="centered")

st.title("📺 ICC World Feed Scorecard")

# --- INITIALIZE MASTER STATE ---
if "initialized" not in st.session_state:
    st.session_state.total_players_combined = 16  # Default: 16 players
    st.session_state.players_per_team = 8
    st.session_state.has_joker = False
    st.session_state.joker_name = "Joker Player"
    st.session_state.max_overs = 10
    st.session_state.innings = 1
    
    st.session_state.team_a_name = "Team Alpha"
    st.session_state.team_b_name = "Team Beta"
    st.session_state.team_a_players = [f"Player A{i}" for i in range(1, 9)]
    st.session_state.team_b_players = [f"Player B{i}" for i in range(1, 9)]
    
    # Captain tracking
    st.session_state.team_a_captain = st.session_state.team_a_players[0]
    st.session_state.team_b_captain = st.session_state.team_b_players[0]
    
    st.session_state.i1_runs = 0
    st.session_state.i1_wickets = 0
    st.session_state.i1_balls = 0
    st.session_state.i2_runs = 0
    st.session_state.i2_wickets = 0
    st.session_state.i2_balls = 0
    
    st.session_state.i1_drs_left = 3
    st.session_state.i2_drs_left = 3
    
    st.session_state.history = []
    st.session_state.undo_stack = []
    st.session_state.player_stats = {}
    st.session_state.pending_wicket = False
    st.session_state.drs_active = False
    
    all_init = st.session_state.team_a_players + st.session_state.team_b_players
    for p in all_init:
        st.session_state.player_stats[p] = {
            "runs": 0, "balls": 0, "4s": 0, "6s": 0, 
            "b_balls": 0, "b_runs": 0, "wickets": 0, "out_how": "not out"
        }
        
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

def get_player_badge(name):
    badges = []
    if name == st.session_state.team_a_captain or name == st.session_state.team_b_captain:
        badges.append("(C)")
    if st.session_state.has_joker and name == st.session_state.joker_name:
        badges.append("🃏")
    return f"{name} {' '.join(badges)}".strip()

# --- DYNAMIC SETUP & CAPTAIN SELECTION ---
with st.expander("⚙️ Match Setup, Captains & Squads"):
    c_ov, c_tot = st.columns(2)
    st.session_state.max_overs = c_ov.number_input("Max Overs", min_value=1, value=st.session_state.max_overs)
    
    tot_input = c_tot.number_input(
        "Total Players (Both Teams Combined)", 
        min_value=3, 
        step=1, 
        value=st.session_state.total_players_combined,
        help="Odd totals automatically activate a Joker player who plays for both sides!"
    )
    
    # Check for squad adjustments
    if tot_input != st.session_state.total_players_combined:
        st.session_state.total_players_combined = tot_input
        is_odd = (tot_input % 2 != 0)
        st.session_state.has_joker = is_odd
        
        new_per_team = (tot_input - 1) // 2 if is_odd else tot_input // 2
        st.session_state.players_per_team = new_per_team
        
        # Adjust Team A
        if len(st.session_state.team_a_players) < new_per_team:
            for i in range(len(st.session_state.team_a_players) + 1, new_per_team + 1):
                p_name = f"Player A{i}"
                st.session_state.team_a_players.append(p_name)
                st.session_state.player_stats[p_name] = {"runs": 0, "balls": 0, "4s": 0, "6s": 0, "b_balls": 0, "b_runs": 0, "wickets": 0, "out_how": "not out"}
        else:
            st.session_state.team_a_players = st.session_state.team_a_players[:new_per_team]
            
        # Adjust Team B
        if len(st.session_state.team_b_players) < new_per_team:
            for i in range(len(st.session_state.team_b_players) + 1, new_per_team + 1):
                p_name = f"Player B{i}"
                st.session_state.team_b_players.append(p_name)
                st.session_state.player_stats[p_name] = {"runs": 0, "balls": 0, "4s": 0, "6s": 0, "b_balls": 0, "b_runs": 0, "wickets": 0, "out_how": "not out"}
        else:
            st.session_state.team_b_players = st.session_state.team_b_players[:new_per_team]
            
        if is_odd and st.session_state.joker_name not in st.session_state.player_stats:
            st.session_state.player_stats[st.session_state.joker_name] = {"runs": 0, "balls": 0, "4s": 0, "6s": 0, "b_balls": 0, "b_runs": 0, "wickets": 0, "out_how": "not out"}
            
        st.rerun()

    if st.session_state.has_joker:
        st.warning(f"🃏 **Odd total count ({st.session_state.total_players_combined}) detected!** {st.session_state.players_per_team} per team + 1 Joker (plays for both sides).")
    else:
        st.info(f"👥 Squad Allocation: **{st.session_state.players_per_team} players** per team (Even Total)")

    c_t1, c_t2 = st.columns(2)
    st.session_state.team_a_name = c_t1.text_input("Team 1 Name", value=st.session_state.team_a_name)
    st.session_state.team_b_name = c_t2.text_input("Team 2 Name", value=st.session_state.team_b_name)
    
    st.write("---")
    st.write("#### 📝 Edit Squad Names")
    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.write(f"**{st.session_state.team_a_name} Squad ({st.session_state.players_per_team} Players)**")
        new_team_a = []
        for i, old_name in enumerate(st.session_state.team_a_players):
            name = st.text_input(f"Player {i+1}", value=old_name, key=f"t1_p_{i}")
            new_team_a.append(name)
            if name != old_name and old_name in st.session_state.player_stats:
                st.session_state.player_stats[name] = st.session_state.player_stats.pop(old_name)
                if st.session_state.team_a_captain == old_name: st.session_state.team_a_captain = name
                if st.session_state.striker == old_name: st.session_state.striker = name
                if st.session_state.non_striker == old_name: st.session_state.non_striker = name
                if st.session_state.current_bowler == old_name: st.session_state.current_bowler = name
        st.session_state.team_a_players = new_team_a

    with col_p2:
        st.write(f"**{st.session_state.team_b_name} Squad ({st.session_state.players_per_team} Players)**")
        new_team_b = []
        for i, old_name in enumerate(st.session_state.team_b_players):
            name = st.text_input(f"Player {i+1}", value=old_name, key=f"t2_p_{i}")
            new_team_b.append(name)
            if name != old_name and old_name in st.session_state.player_stats:
                st.session_state.player_stats[name] = st.session_state.player_stats.pop(old_name)
                if st.session_state.team_b_captain == old_name: st.session_state.team_b_captain = name
                if st.session_state.striker == old_name: st.session_state.striker = name
                if st.session_state.non_striker == old_name: st.session_state.non_striker = name
                if st.session_state.current_bowler == old_name: st.session_state.current_bowler = name
        st.session_state.team_b_players = new_team_b

    # Captain Selectors
    st.write("---")
    st.write("#### 👑 Select Team Captains")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        c_a_idx = st.session_state.team_a_players.index(st.session_state.team_a_captain) if st.session_state.team_a_captain in st.session_state.team_a_players else 0
        st.session_state.team_a_captain = st.selectbox(f"{st.session_state.team_a_name} Captain", st.session_state.team_a_players, index=c_a_idx)

    with col_c2:
        c_b_idx = st.session_state.team_b_players.index(st.session_state.team_b_captain) if st.session_state.team_b_captain in st.session_state.team_b_players else 0
        st.session_state.team_b_captain = st.selectbox(f"{st.session_state.team_b_name} Captain", st.session_state.team_b_players, index=c_b_idx)

    # Joker Name Input if active
    if st.session_state.has_joker:
        st.write("---")
        old_joker = st.session_state.joker_name
        new_joker = st.text_input("🃏 Joker Player Name (Plays Both Sides)", value=old_joker)
        if new_joker != old_joker:
            if old_joker in st.session_state.player_stats:
                st.session_state.player_stats[new_joker] = st.session_state.player_stats.pop(old_joker)
            else:
                st.session_state.player_stats[new_joker] = {"runs": 0, "balls": 0, "4s": 0, "6s": 0, "b_balls": 0, "b_runs": 0, "wickets": 0, "out_how": "not out"}
            if st.session_state.striker == old_joker: st.session_state.striker = new_joker
            if st.session_state.non_striker == old_joker: st.session_state.non_striker = new_joker
            if st.session_state.current_bowler == old_joker: st.session_state.current_bowler = new_joker
            st.session_state.joker_name = new_joker

    st.write("---")
    st.write("#### 🎯 Active Players on Field")
    
    base_bat = st.session_state.team_a_players if st.session_state.innings == 1 else st.session_state.team_b_players
    base_bowl = st.session_state.team_b_players if st.session_state.innings == 1 else st.session_state.team_a_players
    
    batting_squad = base_bat + ([st.session_state.joker_name] if st.session_state.has_joker and st.session_state.joker_name not in base_bat else [])
    bowling_squad = base_bowl + ([st.session_state.joker_name] if st.session_state.has_joker and st.session_state.joker_name not in base_bowl else [])

    c1, c2, c3 = st.columns(3)
    st.session_state.striker = c1.selectbox("Striker", batting_squad, index=batting_squad.index(st.session_state.striker) if st.session_state.striker in batting_squad else 0, format_func=get_player_badge)
    st.session_state.non_striker = c2.selectbox("Non-Striker", batting_squad, index=batting_squad.index(st.session_state.non_striker) if st.session_state.non_striker in batting_squad else 1, format_func=get_player_badge)
    st.session_state.current_bowler = c3.selectbox("Bowler", bowling_squad, index=bowling_squad.index(st.session_state.current_bowler) if st.session_state.current_bowler in bowling_squad else 0, format_func=get_player_badge)

# --- SCORE DISPLAY ---
tot_runs = st.session_state.i1_runs if st.session_state.innings == 1 else st.session_state.i2_runs
tot_w = st.session_state.i1_wickets if st.session_state.innings == 1 else st.session_state.i2_wickets
tot_b = st.session_state.i1_balls if st.session_state.innings == 1 else st.session_state.i2_balls
max_b = st.session_state.max_overs * 6

batting_team_drs = st.session_state.i1_drs_left if st.session_state.innings == 1 else st.session_state.i2_drs_left
fielding_team_drs = st.session_state.i2_drs_left if st.session_state.innings == 1 else st.session_state.i1_drs_left

overs_fmt = f"{tot_b // 6}.{tot_b % 6}"
crr = (tot_runs / (tot_b / 6)) if tot_b > 0 else 0.0

if st.session_state.innings == 1:
    st.header(f"1st Innings — {st.session_state.team_a_name} (Capt: {st.session_state.team_a_captain})")
    st.metric(
        label="SCORECARD", 
        value=f"{tot_runs} / {tot_w}", 
        delta=f"Overs: {overs_fmt} / {st.session_state.max_overs} | CRR: {crr:.2f} | DRS Bat: {batting_team_drs}/3 | DRS Field: {fielding_team_drs}/3"
    )
else:
    st.header(f"2nd Innings — {st.session_state.team_b_name} (Capt: {st.session_state.team_b_captain})")
    target = st.session_state.i1_runs + 1
    runs_needed = target - st.session_state.i2_runs
    balls_left = max_b - st.session_state.i2_balls
    
    total_batters_count = len(st.session_state.team_b_players) + (1 if st.session_state.has_joker else 0)
    
    if runs_needed <= 0:
        st.balloons()
        st.success(f"🏆 {st.session_state.team_b_name} won by {total_batters_count - tot_w} wickets!")
    elif tot_w >= total_batters_count - 1 or balls_left <= 0:
        st.error(f"🏆 {st.session_state.team_a_name} won by {runs_needed - 1} runs!")
    else:
        st.info(f"🎯 Target: {target} runs | Need {runs_needed} runs off {balls_left} balls")
    
    st.metric(
        label="SCORECARD", 
        value=f"{tot_runs} / {tot_w}", 
        delta=f"Overs: {overs_fmt} / {st.session_state.max_overs} | CRR: {crr:.2f} | DRS Bat: {batting_team_drs}/3 | DRS Field: {fielding_team_drs}/3"
    )

# --- RECENT BALL TICKER ---
if st.session_state.history:
    st.write("Recent Deliveries: " + " | ".join([f"`{b}`" for b in st.session_state.history[-12:]]))

st.divider()

# --- LIVE PLAYER STATS CARDS ---
s_p = st.session_state.player_stats[st.session_state.striker]
ns_p = st.session_state.player_stats[st.session_state.non_striker]
bw_p = st.session_state.player_stats[st.session_state.current_bowler]

s_sr = (s_p["runs"] / s_p["balls"] * 100) if s_p["balls"] > 0 else 0.0
ns_sr = (ns_p["runs"] / ns_p["balls"] * 100) if ns_p["balls"] > 0 else 0.0
bw_ov = f"{bw_p['b_balls'] // 6}.{bw_p['b_balls'] % 6}"
bw_ec = (bw_p['b_runs'] / (bw_p['b_balls'] / 6)) if bw_p['b_balls'] > 0 else 0.0

col_b1, col_b2 = st.columns(2)
with col_b1:
    st.subheader(f"🏏 {get_player_badge(st.session_state.striker)} *")
    st.write(f"**{s_p['runs']}** ({s_p['balls']}) | 4s: {s_p['4s']} | 6s: {s_p['6s']} | SR: {s_sr:.1f}")

with col_b2:
    st.subheader(f"🏏 {get_player_badge(st.session_state.non_striker)}")
    st.write(f"**{ns_p['runs']}** ({ns_p['balls']}) | 4s: {ns_p['4s']} | 6s: {ns_p['6s']} | SR: {ns_sr:.1f}")

st.write(f"⚾ **Bowler: {get_player_badge(st.session_state.current_bowler)}** — Overs: {bw_ov} | Wkts: {bw_p['wickets']} | Runs: {bw_p['b_runs']} | Econ: {bw_ec:.2f}")

st.divider()

# --- DISMISSAL MODAL & DRS HAWKEYE ENGINE ---
if st.session_state.pending_wicket:
    st.warning("⚠️ Select Wicket Type or Initiate DRS Review:")
    
    drs_label = f"🔍 DRS Review (Bat: {batting_team_drs}/3 | Field: {fielding_team_drs}/3)"
    w_options = ["Bowled 🎳", "Caught 🖐️", "Run Out 🏃", "Hit Wicket 🪵", drs_label]
    
    w_type = st.radio("How Out / Option?", w_options, horizontal=True)
    st.session_state.drs_active = "DRS Review" in w_type

    if st.session_state.drs_active:
        st.subheader("📺 DRS REVIEW IN PROGRESS — PROFESSOR HAWKEYE")
        
        c_ump, c_rev = st.columns(2)
        umpire_call = c_ump.radio("On-Field Umpire Call:", ["OUT", "NOT OUT"], horizontal=True)
        
        bat_rev_label = f"Batting Team ({batting_team_drs}/3)"
        field_rev_label = f"Fielding Team ({fielding_team_drs}/3)"
        
        review_by_sel = c_rev.radio("Review Taken By:", [bat_rev_label, field_rev_label], horizontal=True)
        review_by = "Batting Team" if bat_rev_label in review_by_sel else "Fielding Team"
        
        reviewer_has_reviews = (batting_team_drs > 0) if review_by == "Batting Team" else (fielding_team_drs > 0)
        
        if not reviewer_has_reviews:
            st.error(f"🚫 {review_by} has NO DRS reviews remaining (0/3)!")

        drs_pitch = st.selectbox("1. Pitching Line", ["In Line", "Outside Off", "Outside Leg"])
        drs_impact = st.selectbox("2. Impact Line", ["In Line", "Outside Off"])
        drs_length = st.selectbox("3. Delivery Length", ["Yorker 🎯", "Full Length", "Good Length", "Short Ball"])
        drs_bounce = st.selectbox("4. Bounce Height", ["Low (Below Knee)", "Medium (At Knee)", "High (Thigh / Waist)"])
        drs_move = st.selectbox("5. Movement / Spin", ["Straight", "In-Swinger / Turn IN", "Out-Swinger / Turn OUT"])

        drs_is_out = True
        reasons = []

        if drs_pitch == "Outside Leg":
            drs_is_out = False
            reasons.append("Pitching Outside Leg")

        if drs_impact == "Outside Off":
            drs_is_out = False
            reasons.append("Impact Outside Off")

        if drs_length == "Yorker 🎯":
            if drs_pitch != "Outside Leg" and drs_impact != "Outside Off":
                drs_is_out = True
                reasons.append("Perfect Yorker (Hitting Base)")
        else:
            if drs_bounce == "High (Thigh / Waist)" or drs_length == "Short Ball":
                drs_is_out = False
                reasons.append("Bouncing Over Stumps")

        if drs_move == "Out-Swinger / Turn OUT" and drs_pitch == "Outside Off":
            drs_is_out = False
            reasons.append("Missing Off Stump")

        if drs_move == "In-Swinger / Turn IN" and drs_pitch == "In Line" and drs_impact == "In Line":
            drs_is_out = True
            reasons.append("Turning Into Stumps")

        final_verdict = "OUT" if drs_is_out else "NOT OUT"
        decision_overturned = (final_verdict != umpire_call)
        review_retained = decision_overturned

        st.subheader("📺 HAWKEYE PREDICTED TRAJECTORY")
        if drs_is_out:
            st.error(f"🔴 VERDICT: OUT (HITTING STUMPS) | Original Call: {umpire_call}")
        else:
            st.success(f"🟢 VERDICT: NOT OUT ({', '.join(reasons)}) | Original Call: {umpire_call}")

        if decision_overturned:
            st.info(f"🔄 DECISION OVERTURNED! Review Retained by {review_by}!")
        else:
            st.warning(f"❌ DECISION UPHELD! Review Lost by {review_by}!")

    base_bat = st.session_state.team_a_players if st.session_state.innings == 1 else st.session_state.team_b_players
    batting_squad = base_bat + ([st.session_state.joker_name] if st.session_state.has_joker and st.session_state.joker_name not in base_bat else [])
    
    next_batters = [p for p in batting_squad if p not in [st.session_state.striker, st.session_state.non_striker] and st.session_state.player_stats[p]["out_how"] == "not out"]
    
    new_batter = st.selectbox("Next Batter Coming In", next_batters if next_batters else ["No more batters"], format_func=lambda x: get_player_badge(x) if x != "No more batters" else x)

    c_confirm, c_cancel = st.columns(2)
    if c_confirm.button("Confirm Decision"):
        if st.session_state.drs_active and not reviewer_has_reviews:
            st.error("Cannot confirm: The reviewing team has 0 reviews remaining!")
        else:
            save_snapshot()
            out_player = st.session_state.striker
            st.session_state.player_stats[out_player]["balls"] += 1
            
            final_is_out = drs_is_out if st.session_state.drs_active else True
            
            if st.session_state.drs_active and not review_retained:
                if review_by == "Batting Team":
                    if st.session_state.innings == 1: st.session_state.i1_drs_left -= 1
                    else: st.session_state.i2_drs_left -= 1
                else:
                    if st.session_state.innings == 1: st.session_state.i2_drs_left -= 1
                    else: st.session_state.i1_drs_left -= 1

            if final_is_out:
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
            else:
                st.session_state.history.append("0")
                bw_p["b_balls"] += 1
                if st.session_state.innings == 1: st.session_state.i1_balls += 1
                else: st.session_state.i2_balls += 1

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
    
    total_batters_count = len(st.session_state.team_a_players) + (1 if st.session_state.has_joker else 0)
    if st.session_state.innings == 1 and (st.session_state.i1_wickets >= total_batters_count - 1 or st.session_state.i1_balls >= max_b):
        st.session_state.innings = 2
        st.session_state.striker = st.session_state.team_b_players[0]
        st.session_state.non_striker = st.session_state.team_b_players[1]
        st.session_state.current_bowler = st.session_state.team_a_players[0]
        
    st.rerun()

# --- SUMMARY, MVP & GAME CHANGER SECTION ---
with st.expander("📊 Full Match Scorecard & Performance Analytics"):
    st.write("### 🏏 Batting Performance")
    bat_data = []
    for p, s in st.session_state.player_stats.items():
        if s["balls"] > 0 or s["runs"] > 0 or s["out_how"] != "not out":
            sr = (s["runs"] / s["balls"] * 100) if s["balls"] > 0 else 0.0
            bat_data.append({
                "Player": get_player_badge(p), 
                "Status": s["out_how"], 
                "Runs": s["runs"], 
                "Balls": s["balls"], 
                "4s": s["4s"], 
                "6s": s["6s"], 
                "SR": f"{sr:.1f}"
            })
    if bat_data:
        st.table(bat_data)
    else:
        st.info("No batting data yet.")

    st.write("### ⚾ Bowling Performance")
    bowl_data = []
    for p, s in st.session_state.player_stats.items():
        if s["b_balls"] > 0:
            ov = f"{s['b_balls'] // 6}.{s['b_balls'] % 6}"
            econ = (s["b_runs"] / (s["b_balls"] / 6)) if s["b_balls"] > 0 else 0.0
            bowl_data.append({
                "Bowler": get_player_badge(p), 
                "Overs": ov, 
                "Runs Conceded": s["b_runs"], 
                "Wickets": s["wickets"], 
                "Economy": f"{econ:.2f}"
            })
    if bowl_data:
        st.table(bowl_data)
    else:
        st.info("No bowling data yet.")

    st.divider()

    # --- MVP & GAME CHANGER BUTTONS ---
    col_mvp, col_gc = st.columns(2)

    with col_mvp:
        st.write("### 🏆 Match MVP")
        if st.button("Calculate MVP Player"):
            best_player = None
            highest_pts = -1.0
            mvp_breakdown = {}

            for p, s in st.session_state.player_stats.items():
                pts = (s["runs"] * 1) + (s["4s"] * 1) + (s["6s"] * 2) + (s["wickets"] * 25)
                if pts > highest_pts and pts > 0:
                    highest_pts = pts
                    best_player = p
                    mvp_breakdown = s

            if best_player:
                st.success(f"🌟 **MVP: {get_player_badge(best_player)}** ({highest_pts:.0f} pts)")
                st.caption(f"{mvp_breakdown['runs']} runs ({mvp_breakdown['balls']}b), {mvp_breakdown['wickets']} wkts")
            else:
                st.warning("No performances recorded yet.")

    with col_gc:
        st.write("### ⚡ Game Changer")
        gc_type = st.radio("Category", ["Batting", "Bowling"], horizontal=True)
        if st.button("Find Game Changer"):
            gc_player = None
            gc_stat_desc = ""

            if gc_type == "Batting":
                best_impact = -1.0
                for p, s in st.session_state.player_stats.items():
                    if s["balls"] >= 3:
                        sr = (s["runs"] / s["balls"]) * 100
                        impact = s["runs"] * (sr / 100)
                        if impact > best_impact and s["runs"] > 0:
                            best_impact = impact
                            gc_player = p
                            gc_stat_desc = f"{s['runs']} runs off {s['balls']} balls (SR: {sr:.1f})"
            else:
                best_bowling_score = -1.0
                for p, s in st.session_state.player_stats.items():
                    if s["b_balls"] > 0:
                        econ = (s["b_runs"] / (s["b_balls"] / 6)) if s["b_balls"] > 0 else 0.0
                        b_score = (s["wickets"] * 30) - (econ * 2)
                        if b_score > best_bowling_score and (s["wickets"] > 0 or s["b_balls"] >= 6):
                            best_bowling_score = b_score
                            gc_player = p
                            ov = f"{s['b_balls'] // 6}.{s['b_balls'] % 6}"
                            gc_stat_desc = f"{s['wickets']} Wkts in {ov} Overs (Econ: {econ:.2f})"

            if gc_player:
                st.success(f"⚡ **{gc_type} Game Changer: {get_player_badge(gc_player)}**")
                st.caption(f"Impact: {gc_stat_desc}")
            else:
                st.warning("Not enough data to calculate Game Changer.")

    st.divider()

    def generate_pdf():
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = [Paragraph("Match Summary Report", styles['Title']), Spacer(1, 12)]
        
        summary_data = [
            ["Innings", "Team (Captain)", "Runs", "Wickets", "Overs", "DRS Remaining"],
            ["1st Innings", f"{st.session_state.team_a_name} ({st.session_state.team_a_captain})", str(st.session_state.i1_runs), str(st.session_state.i1_wickets), f"{st.session_state.i1_balls//6}.{st.session_state.i1_balls%6}", f"{st.session_state.i1_drs_left}/3"],
            ["2nd Innings", f"{st.session_state.team_b_name} ({st.session_state.team_b_captain})", str(st.session_state.i2_runs), str(st.session_state.i2_wickets), f"{st.session_state.i2_balls//6}.{st.session_state.i2_balls%6}", f"{st.session_state.i2_drs_left}/3"]
        ]
        t = Table(summary_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey), 
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke)
        ]))
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