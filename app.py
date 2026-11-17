import random

import streamlit as st

from agents.tutor_basic import write_lesson
from agents.orchestrator import choose_next
from core import db
from core.game import play_round
from core.models import WARNING_SIGNS
from core.scoring import Response

OPTIONS_PER_ROUND = 6

st.set_page_config(page_title="PhishGuard Arena", layout="centered")

conn = db.connect()          # cheap, and avoids SQLite thread errors
db.init_db(conn)

state = st.session_state
if "learner_id" not in state:
    state.learner_id = db.create_learner(conn)
if "scenario_id" not in state:
    with st.spinner("Choosing your next message..."):
        scenario_id, reason, from_agent = choose_next(conn, state.learner_id)
    state.scenario_id = scenario_id
    state.pick_reason = reason
    state.pick_from_agent = from_agent
    state.result = None
    state.lesson = None
    state.round = state.get("round", 0) + 1

scenario = db.get_scenario(conn, state.scenario_id)


def sign_options(s):
    """Real signs plus decoys plus fillers, so every round shows 6."""
    rng = random.Random(s.scenario_id)     # same order on every rerun
    chosen = list(dict.fromkeys(s.warning_signs + s.decoy_signs))
    fillers = [x for x in WARNING_SIGNS if x not in chosen]
    rng.shuffle(fillers)
    chosen += fillers[: max(0, OPTIONS_PER_ROUND - len(chosen))]
    rng.shuffle(chosen)
    return chosen


def label(sign):
    return sign.replace("_", " ").capitalize()


# Sidebar: progress
learner = db.get_learner(conn, state.learner_id)
with st.sidebar:
    st.header("Your progress")
    st.write(f"Round {state.round}")
    st.write(f"Difficulty level: {learner['level']} of 5")
    total = conn.execute(
        "SELECT COALESCE(SUM(points), 0) FROM attempts WHERE learner_id = ?",
        (state.learner_id,),
    ).fetchone()[0]
    st.write(f"Total points: {total:g}")
    mastery = db.get_mastery(conn, state.learner_id)
    if mastery:
        st.subheader("Mastery by warning sign")
        for sign, value in sorted(mastery.items(), key=lambda kv: kv[1]):
            st.progress(value, text=f"{label(sign)}: {value:.2f}")
        st.divider()
    if st.checkbox("Show agent notes"):
        source = "Orchestrator" if state.pick_from_agent else "Python picker"
        st.caption(f"Chosen by: {source}")
        st.caption(state.pick_reason)

# Main: the message
st.title("PhishGuard Arena")
st.caption(f"{scenario.channel.upper()}  |  Difficulty {scenario.difficulty}")
st.subheader(scenario.subject)
st.text(scenario.body)       # plain text on purpose, so links show their real URL

# Answer form
if state.result is None:
    with st.form("answer"):
        verdict = st.radio("Is this message safe or phishing?",
                           ["Safe", "Phishing"], index=None, horizontal=True)
        selected = st.multiselect("Which warning signs do you see?",
                                  sign_options(scenario), format_func=label)
        confidence = st.slider("How confident are you?", 1, 5, 3)
        submitted = st.form_submit_button("Submit answer")

    if submitted:
        if verdict is None:
            st.warning("Choose Safe or Phishing first.")
        else:
            response = Response(verdict_phishing=(verdict == "Phishing"),
                                selected=selected, confidence=confidence)
            attempt_id, result = play_round(conn, state.learner_id,
                                            scenario.scenario_id, response)
            state.result = result
            if result.has_errors:
                with st.spinner("The Tutor is writing your lesson..."):
                    lesson, from_model = write_lesson(scenario, result)
                state.lesson = lesson
                db.log_agent(conn, state.learner_id, "tutor_basic", "lesson",
                             {"attempt_id": attempt_id,
                              "from_model": from_model})
            st.rerun()

# Feedback
else:
    result = state.result
    answer = "phishing" if scenario.is_phishing else "legitimate"
    if result.correct and not result.has_errors:
        st.success(f"Correct. This message is {answer}. +{result.points:g} points")
    elif result.correct:
        st.info(f"Right verdict, this message is {answer}, but check the "
                f"warning signs. {result.points:+g} points")
    else:
        st.error(f"Not quite. This message is {answer}. "
                 f"{result.points:+g} points")

    if result.missed:
        st.write("Missed: " + ", ".join(label(s) for s in result.missed))
    if result.false_hits:
        st.write("Not present: " + ", ".join(label(s) for s in result.false_hits))
    if state.lesson:
        st.subheader("Tutor")
        st.write(state.lesson)

    if st.button("Next message"):
        del state["scenario_id"]
        st.rerun()