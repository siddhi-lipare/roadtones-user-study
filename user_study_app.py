# app.py
import streamlit as st
import pandas as pd
import os
import time
import re
import json
import cv2
import math
import gspread
from google.oauth2.service_account import Credentials

# --- Configuration ---
INTRO_VIDEO_PATH = "media/start_video_slower.mp4"
STUDY_DATA_PATH = "study_data.json"
QUIZ_DATA_PATH = "quiz_data.json"
INSTRUCTIONS_PATH = "instructions.json"
QUESTIONS_DATA_PATH = "questions.json"
PORTRAIT_VIDEO_MAX_HEIGHT = 450  # Adjust portrait video height

# --- Google Sheets Connection ---
@st.cache_resource
def connect_to_gsheet():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open("roadtones-streamlit-userstudy-responses")
        worksheet = spreadsheet.sheet1
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("Spreadsheet not found or access denied.")
        return None
    except Exception as e:
        st.error(f"Could not connect to Google Sheets: {e}")
        return None

WORKSHEET = connect_to_gsheet()

# --- Global CSS Fixes ---
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&display=swap');

video {{
    object-fit: contain !important;
    max-height: {PORTRAIT_VIDEO_MAX_HEIGHT}px !important;
    width: 100% !important;
    border-radius: 10px;
    display: block;
    margin: 0 auto;
}}

.caption-text {{
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 19px !important;
    line-height: 1.6;
    color: #111827;
}}

.part1-caption-box {{
    border-radius: 10px;
    padding: 1rem 1.5rem;
    margin-bottom: 20px;
}}
.part1-caption-box strong {{
    font-size: 18px;
    color: #111827;
    font-family: 'Inter', sans-serif;
    font-weight: 600;
}}

.comparison-caption-box {{
    background-color: #f9fafb;
    border-left: 5px solid #6366f1;
    padding: 1rem 1.5rem;
    margin: 1rem 0;
    border-radius: 0.25rem;
}}

.comparison-caption-box strong {{
    font-size: 18px;
    color: #111827;
    font-family: 'Inter', sans-serif;
    font-weight: 600;
}}

.slider-label {{
    min-height: 80px;
    margin-bottom: 0.5rem;
}}

.highlight-trait {{
    color: #4f46e5;
    font-weight: 600;
}}

div[data-testid="stSlider"] {{
    max-width: 250px;
}}
</style>
""", unsafe_allow_html=True)

# --- Definitions ---
DEFINITIONS = {
    'Advisory': {'desc': 'Gives advice, suggestions, or warnings.'},
    'Sarcastic': {'desc': 'Uses irony or mockery to convey contempt.'},
    'Appreciative': {'desc': 'Expresses gratitude or praise.'},
    'Considerate': {'desc': 'Shows care for others.'},
    'Critical': {'desc': 'Expresses disapproval or judgment.'},
    'Amusing': {'desc': 'Provides lighthearted entertainment.'},
    'Angry': {'desc': 'Shows hostility or annoyance.'},
    'Anxious': {'desc': 'Displays worry or unease.'},
    'Enthusiastic': {'desc': 'Shows eager enjoyment.'},
    'Judgmental': {'desc': 'Overly critical or moralizing.'},
    'Conversational': {'desc': 'Informal and chatty tone.'},
}

# --- Helpers ---
@st.cache_data
def get_video_orientation(path):
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return "landscape"
        w, h = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        cap.release()
        return "portrait" if h > w else "landscape"
    except Exception:
        return "landscape"

@st.cache_data
def load_data():
    data = {}
    for key, path in {
        "instructions": INSTRUCTIONS_PATH,
        "quiz": QUIZ_DATA_PATH,
        "study": STUDY_DATA_PATH,
        "questions": QUESTIONS_DATA_PATH,
    }.items():
        if not os.path.exists(path):
            st.error(f"Missing file: {path}")
            return None
        with open(path, 'r', encoding='utf-8') as f:
            data[key] = json.load(f)

    # add orientations
    for part in data["study"].values():
        for item in part:
            item["orientation"] = get_video_orientation(item["video_path"]) if os.path.exists(item["video_path"]) else "landscape"
    return data

def save_response(email, age, gender, video_data, caption_data, choice, phase, q_text, was_correct=None):
    if WORKSHEET is None: return
    try:
        row = [
            email, age, gender, time.strftime("%Y-%m-%d %H:%M:%S"), phase,
            video_data.get("video_id", "N/A"),
            caption_data.get("caption_id") or caption_data.get("comparison_id") or caption_data.get("change_id"),
            q_text, str(choice),
            str(was_correct) if was_correct is not None else "N/A",
            1 if phase == "quiz" else "N/A"
        ]
        if len(WORKSHEET.get_all_values()) == 0:
            WORKSHEET.append_row(['email','age','gender','timestamp','phase','video_id','sample_id','question','choice','correct','attempts'])
        WORKSHEET.append_row(row)
    except Exception as e:
        st.error(f"Error writing to sheet: {e}")

def format_options_with_info(opt):
    return f"{opt} ({DEFINITIONS[opt]['desc']})" if opt in DEFINITIONS else opt

# --- Page Setup ---
st.set_page_config(layout="wide", page_title="Tone-aware Captioning Study")

# --- Session defaults ---
if 'page' not in st.session_state:
    st.session_state.update({
        'page': 'demographics',
        'study_part': 1,
        'current_part_index': 0,
        'current_sample_index': 0,
        'current_video_index': 0,
        'current_caption_index': 0,
        'current_comparison_index': 0,
        'current_change_index': 0,
        'score': 0,
        'score_saved': False,
        'show_feedback': False,
        'all_data': load_data()
    })

if st.session_state.all_data is None:
    st.stop()

# --- DEMOGRAPHICS ---
if st.session_state.page == 'demographics':
    st.title("Tone-aware Captioning Study 📝")
    email = st.text_input("Email:")
    age = st.selectbox("Age:", list(range(18, 61)))
    gender = st.selectbox("Gender:", ["Male", "Female", "Other / Prefer not to say"])
    if st.checkbox("I am over 18 and agree to participate."):
        if st.button("Next"):
            if not email or not age or not gender:
                st.error("Please fill all fields.")
            elif not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
                st.error("Invalid email format.")
            else:
                st.session_state.update({'email': email, 'age': age, 'gender': gender, 'page': 'intro_video'})
                st.rerun()

elif st.session_state.page == 'intro_video':
    st.title("Introductory Video")
    _, vid_col, _ = st.columns([1,3,1])
    with vid_col: st.video(INTRO_VIDEO_PATH, autoplay=True, muted=True)
    if st.button("Next"): st.session_state.page = 'quiz'; st.rerun()

# --- QUIZ ---
elif st.session_state.page == 'quiz':
    quiz = st.session_state.all_data["quiz"]
    part_keys = list(quiz.keys())
    with st.sidebar:
        for i, pk in enumerate(part_keys):
            st.button(pk, on_click=lambda i=i: st.session_state.update(current_part_index=i), use_container_width=True)
    if st.session_state.current_part_index >= len(part_keys):
        st.session_state.page = 'user_study_main'; st.rerun()
    current_key = part_keys[st.session_state.current_part_index]
    questions = quiz[current_key]
    idx = st.session_state.current_sample_index
    sample = questions[idx]
    st.header(current_key)
    col1, col2 = st.columns([1.2,1.5])
    with col1:
        st.video(sample["video_path"], autoplay=True, muted=True)
        st.caption("Muted for autoplay. You can unmute manually.")
    with col2:
        st.subheader("Question")
        q = sample if "questions" not in sample else sample["questions"][0]
        st.markdown(f"**{q['question_text']}**")
        choice = st.radio("Select:", q["options"], index=None)
        if st.button("Submit"):
            if not choice:
                st.error("Select an answer.")
            else:
                save_response(st.session_state.email, st.session_state.age, st.session_state.gender, sample, sample, choice, "quiz", q["question_text"])
                st.session_state.current_sample_index += 1
                st.rerun()

# --- USER STUDY ---
elif st.session_state.page == 'user_study_main':
    study = st.session_state.all_data["study"]
    st.sidebar.header("Study Parts")
    st.sidebar.button("Part 1", on_click=lambda: st.session_state.update(study_part=1))
    st.sidebar.button("Part 2", on_click=lambda: st.session_state.update(study_part=2))
    st.sidebar.button("Part 3", on_click=lambda: st.session_state.update(study_part=3))

    # === Part 1 ===
    if st.session_state.study_part == 1:
        part = study["part1_ratings"]
        vi, ci = st.session_state.current_video_index, st.session_state.current_caption_index
        if vi >= len(part): st.session_state.study_part = 2; st.rerun()
        vid = part[vi]
        cap = vid["captions"][ci]
        col1, col2 = st.columns([1,1.8])
        with col1:
            st.video(vid["video_path"], autoplay=True, muted=True)
            st.caption("Muted for autoplay.")
            st.info(vid["video_summary"])
        with col2:
            st.markdown(f"<div class='part1-caption-box'><strong>Caption:</strong><p class='caption-text'>{cap['text']}</p></div>", unsafe_allow_html=True)
            with st.form(key=f"rating_{vi}_{ci}"):
                scores = {q["id"]: st.slider(q["text"],1,5,3) for q in st.session_state.all_data["questions"]["part1_questions"]}
                if st.form_submit_button("Submit"):
                    for q_id, val in scores.items():
                        qtext = next((x["text"] for x in st.session_state.all_data["questions"]["part1_questions"] if x["id"]==q_id),"")
                        save_response(st.session_state.email, st.session_state.age, st.session_state.gender, vid, cap, val, "user_study_part1", qtext)
                    st.session_state.current_caption_index += 1
                    if st.session_state.current_caption_index >= len(vid["captions"]):
                        st.session_state.current_video_index += 1
                        st.session_state.current_caption_index = 0
                    st.rerun()

# --- Thank You ---
elif st.session_state.page == 'final_thank_you':
    st.title("Thank You 🙏")
    st.success("You have completed the study! We appreciate your contribution.")

# --- FFmpeg Command for Shrinking MP4s ---
# for f in media/*.mp4; do
#   ffmpeg -i "$f" -vf "scale='min(720,iw)':-2" -c:v libx264 -preset veryfast -crf 28 -c:a aac -b:a 96k -movflags +faststart "media/compressed_${f##*/}";
# done
