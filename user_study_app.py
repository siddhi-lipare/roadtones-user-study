# app.py
import streamlit as st
import pandas as pd
import os
import time
import re
import json
import base64
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
PORTRAIT_VIDEO_MAX_HEIGHT = 450 #  Adjust the max height of portrait videos in pixels

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def connect_to_gsheet():
    """Connects to the Google Sheet using Streamlit secrets."""
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
        st.error("Spreadsheet 'roadtones-streamlit-userstudy-responses' not found. Please check the name and sharing settings.")
        return None
    except Exception as e:
        st.error(f"Could not connect to Google Sheets: {e}")
        return None

WORKSHEET = connect_to_gsheet()

# --- Custom CSS and JavaScript ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&display=swap');
[data-testid="stTooltipContent"] { max-width: 300px; font-size: 14px; line-height: 1.5; }
.slider-label { min-height: 80px; margin-bottom: 0.5rem; }
.highlight-trait { color: #4f46e5; font-weight: 600; }
.caption-text { font-family: 'Inter', sans-serif; font-weight: 600; font-size: 21px !important; line-height: 1.6; color: #111827; }
.part1-caption-box { border-radius: 10px; padding: 15px 20px; margin-bottom: 20px; }
.part1-caption-box .caption-text { margin: 0; }
.comparison-caption-box { background-color: #f9fafb; border-left: 5px solid #6366f1; padding: 1rem 1.5rem; margin: 1rem 0; border-radius: 0.25rem; }
.comparison-caption-box strong { font-size: 18px; color: #111827; font-family: 'Inter', sans-serif; font-weight: 600; }
.comparison-caption-box .caption-text { margin: 0.5em 0 0 0; }
div[data-testid="stSlider"] { max-width: 250px; }
</style>
<script> window.parent.document.querySelector('section.main').scrollTo(0, 0); </script>
""", unsafe_allow_html=True)

# --- Central Dictionary for Definitions ---
DEFINITIONS = { 'Advisory': {'desc': 'Gives advice, suggestions, or warnings.'}, 'Sarcastic': {'desc': 'Uses irony or mockery.'}, 'Appreciative': {'desc': 'Expresses gratitude or praise.'}, 'Considerate': {'desc': 'Shows concern for others.'}, 'Critical': {'desc': 'Expresses disapproving comments.'}, 'Amusing': {'desc': 'Causes lighthearted laughter.'}, 'Angry': {'desc': 'Expresses strong annoyance or hostility.'}, 'Anxious': {'desc': 'Shows worry or nervousness.'}, 'Enthusiastic': {'desc': 'Shows intense enjoyment or interest.'}, 'Judgmental': {'desc': 'Displays a moralizing point of view.'}, 'Conversational': {'desc': 'Uses an informal, chatty style.'} }

# --- Helper Functions ---
@st.cache_data
def get_video_as_base64(path):
    try:
        with open(path, "rb") as f: data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError: st.error(f"Video file not found: {path}"); return None
@st.cache_data
def get_video_orientation(path):
    try:
        cap = cv2.VideoCapture(path);
        if not cap.isOpened(): return "landscape"
        w, h = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        cap.release(); return "portrait" if h > w else "landscape"
    except Exception: return "landscape"
@st.cache_data
def load_data():
    try:
        data = {}
        with open(INSTRUCTIONS_PATH, 'r', encoding='utf-8') as f: data['instructions'] = json.load(f)
        with open(QUIZ_DATA_PATH, 'r', encoding='utf-8') as f: data['quiz'] = json.load(f)
        with open(STUDY_DATA_PATH, 'r', encoding='utf-8') as f: study_data = json.load(f)
        with open(QUESTIONS_DATA_PATH, 'r', encoding='utf-8') as f: data['questions'] = json.load(f)
        for part in study_data.values():
            for item in part:
                if os.path.exists(item['video_path']): item['orientation'] = get_video_orientation(item['video_path'])
                else: st.warning(f"Media file not found: {item['video_path']}"); item['orientation'] = 'landscape'
        data['study'] = study_data; return data
    except FileNotFoundError as e: st.error(f"A required data file not found: {e}. App cannot continue."); return None

def save_response(email, age, gender, video_data, caption_data, choice, study_phase, question_text, was_correct=None):
    if WORKSHEET is None: st.error("Connection to response sheet failed. Data not saved."); return
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        response_data = [ email, age, gender, timestamp, study_phase, video_data.get('video_id', 'N/A'), caption_data.get('caption_id') or caption_data.get('comparison_id') or caption_data.get('change_id'), question_text, str(choice), str(was_correct) if was_correct is not None else 'N/A', 1 if study_phase == 'quiz' else 'N/A' ]
        if WORKSHEET.row_count == 0:
            header = ['email', 'age', 'gender', 'timestamp', 'study_phase', 'video_id', 'sample_id', 'question_text', 'user_choice', 'was_correct', 'attempts_taken']
            WORKSHEET.append_row(header)
        WORKSHEET.append_row(response_data)
    except Exception as e: st.error(f"Failed to write to Google Sheet: {e}")

def go_to_next_quiz_question():
    part_keys = list(st.session_state.all_data['quiz'].keys())
    current_part_key = part_keys[st.session_state.current_part_index]
    questions_for_part = st.session_state.all_data['quiz'][current_part_key]
    sample = questions_for_part[st.session_state.current_sample_index]
    was_correct, question_text = st.session_state.is_correct, "N/A"
    if "Tone Controllability" in current_part_key: question_text = f"Intensity of '{sample['tone_to_compare']}' has {sample['comparison_type']}"
    elif "Caption Quality" in current_part_key: question_text = sample["questions"][st.session_state.current_rating_question_index]["question_text"]
    else: question_text = "Tone Identification"
    dummy_video_data, dummy_caption_data = {'video_id': sample.get('sample_id')}, {'caption_id': sample.get('sample_id'), 'text': sample.get('caption', 'N/A')}
    save_response(st.session_state.email, st.session_state.age, st.session_state.gender, dummy_video_data, dummy_caption_data, st.session_state.last_choice, 'quiz', question_text, was_correct=was_correct)
    if "Caption Quality" in current_part_key:
        st.session_state.current_rating_question_index += 1
        if st.session_state.current_rating_question_index >= len(sample["questions"]): st.session_state.current_part_index += 1; st.session_state.current_rating_question_index = 0
    else:
        st.session_state.current_sample_index += 1
        if st.session_state.current_sample_index >= len(questions_for_part): st.session_state.current_part_index += 1; st.session_state.current_sample_index = 0
    st.session_state.show_feedback = False

def jump_to_part(part_index): st.session_state.current_part_index, st.session_state.current_sample_index, st.session_state.current_rating_question_index, st.session_state.show_feedback = part_index, 0, 0, False
def jump_to_study_part(part_number): st.session_state.study_part, st.session_state.current_video_index, st.session_state.current_caption_index, st.session_state.current_comparison_index, st.session_state.current_change_index = part_number, 0, 0, 0, 0
def restart_quiz(): st.session_state.page, st.session_state.current_part_index, st.session_state.current_sample_index, st.session_state.current_rating_question_index, st.session_state.show_feedback, st.session_state.score, st.session_state.score_saved = 'quiz', 0, 0, 0, False, 0, False
def format_options_with_info(option_name): return f"{option_name} ({DEFINITIONS[option_name]['desc']})" if option_name in DEFINITIONS else option_name

st.set_page_config(layout="wide", page_title="Tone-aware Captioning Study")

if 'page' not in st.session_state:
    st.session_state.page = 'demographics'; st.session_state.current_part_index = 0; st.session_state.current_sample_index = 0; st.session_state.show_feedback = False; st.session_state.current_rating_question_index = 0; st.session_state.score = 0; st.session_state.score_saved = False; st.session_state.study_part = 1; st.session_state.current_video_index = 0; st.session_state.current_caption_index = 0; st.session_state.current_comparison_index = 0; st.session_state.current_change_index = 0
    st.session_state.all_data = load_data()

if st.session_state.all_data is None: st.stop()

if st.session_state.page == 'demographics':
    st.title("Tone-aware Captioning Study 📝")
    if st.button("DEBUG: Skip to Main Study"):
        st.session_state.email, st.session_state.age, st.session_state.gender, st.session_state.page = "debug@test.com", 25, "Prefer not to say", 'user_study_main'; st.rerun()
    st.header("Welcome! Before you begin, please provide some basic information:")
    email = st.text_input("Please enter your email address:")
    age = st.selectbox("Age:", options=list(range(18, 61)), index=None, placeholder="Select your age...")
    gender = st.selectbox("Gender:", options=["Male", "Female", "Other / Prefer not to say"], index=None, placeholder="Select your gender...")
    if st.checkbox("I am over 18 and agree to participate in this study. I understand my responses will be recorded anonymously."):
        if st.button("Next"):
            if not all([email, age, gender]): st.error("Please fill in all fields to continue.")
            elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email): st.error("Please enter a valid email address.")
            else: st.session_state.email, st.session_state.age, st.session_state.gender, st.session_state.page = email, age, gender, 'intro_video'; st.rerun()

elif st.session_state.page == 'intro_video':
    st.title("Introductory Video"); st.info("Please watch this short video before proceeding.")
    _ , vid_col, _ = st.columns([1, 3, 1]); vid_col.video(INTRO_VIDEO_PATH, autoplay=True, muted=True)
    if st.button("Next"): st.session_state.page = 'quiz'; st.rerun()

elif st.session_state.page == 'quiz':
    part_keys = list(st.session_state.all_data['quiz'].keys())
    with st.sidebar:
        st.header("Quiz Sections"); [st.button(name, on_click=jump_to_part, args=(i,), use_container_width=True) for i, name in enumerate(part_keys)]
    if st.session_state.current_part_index >= len(part_keys): st.session_state.page = 'quiz_results'; st.rerun()
    current_part_key = part_keys[st.session_state.current_part_index]
    questions_for_part = st.session_state.all_data['quiz'][current_part_key]
    current_index = st.session_state.current_sample_index
    sample = questions_for_part[current_index]
    st.header(current_part_key)
    if "Caption Quality" in current_part_key:
        total_rating_questions = len(sample["questions"]); current_rating_q_index = st.session_state.current_rating_question_index
        st.progress((current_rating_q_index) / total_rating_questions, text=f"Question: {current_rating_q_index + 1}/{total_rating_questions}")
    else: st.progress(current_index / len(questions_for_part), text=f"Question: {current_index + 1}/{len(questions_for_part)}")
    col1, col2 = st.columns([1.2, 1.5])
    with col1:
        st.video(sample['video_path'], autoplay=True, muted=True); st.caption("Video is muted. You can unmute it.")
        if "Caption Quality" in current_part_key: st.subheader("Video Summary"); st.info(sample["video_summary"])
    with col2:
        question_data = sample["questions"][st.session_state.current_rating_question_index] if "Caption Quality" in current_part_key else sample
        if "Tone Controllability" in current_part_key:
            st.subheader(f"Do you think the intensity of '{sample['tone_to_compare']}' has {sample['comparison_type']} from Caption A to B?")
            st.markdown("""<style>.styled-caption-small{font-size:18px;background-color:#f0f2f6;border-radius:0.5rem;padding:1rem;line-height:1.4; margin-bottom: 10px;}</style>""", unsafe_allow_html=True)
            st.markdown("**Caption A:**"); st.markdown(f'<div class="styled-caption-small">{sample["caption_A"]}</div>', unsafe_allow_html=True)
            st.markdown("**Caption B:**"); st.markdown(f'<div class="styled-caption-small">{sample["caption_B"]}</div>', unsafe_allow_html=True)
        elif "Caption Quality" in current_part_key:
            st.subheader(question_data["heading"]); st.markdown(f'<p style="font-size: 22px; font-weight: 600;">{question_data["question_text"]}</p>', unsafe_allow_html=True)
            st.markdown("""<style>.styled-caption{font-size:20px;background-color:#f0f2f6;border-radius:0.5rem;padding:1rem;line-height:1.5}</style>""", unsafe_allow_html=True)
            st.markdown(f'<div class="styled-caption">{sample["caption"]}</div>', unsafe_allow_html=True)
        else:
            st.subheader("Which tone(s) are most dominant in the caption?")
            st.markdown("""<style>.styled-caption{font-size:20px;background-color:#f0f2f6;border-radius:0.5rem;padding:1rem;line-height:1.5} .stMultiSelect [data-baseweb="tag"] {background-color: #0d6efd !important;}</style>""", unsafe_allow_html=True)
            st.markdown(f'<div class="styled-caption">{sample["caption"]}</div>', unsafe_allow_html=True)
        st.markdown("""<style>.feedback-option { padding: 10px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #ddd;} .correct-answer { background-color: #d4edda; border-color: #c3e6cb; color: #155724; } .wrong-answer { background-color: #f8d7da; border-color: #f5c6cb; color: #721c24; } .normal-answer { background-color: #f0f2f6; }</style>""", unsafe_allow_html=True)
        if st.session_state.show_feedback:
            user_choice = st.session_state.last_choice; correct_answer = question_data.get('correct_answer')
            if not isinstance(user_choice, list): user_choice = [user_choice]
            if not isinstance(correct_answer, list): correct_answer = [correct_answer]
            st.write("**Your Answer vs Correct Answer:**")
            for option in question_data['options']:
                if option in correct_answer: st.markdown(f'<div class="feedback-option correct-answer"><strong>{option} (Correct)</strong></div>', unsafe_allow_html=True)
                elif option in user_choice: st.markdown(f'<div class="feedback-option wrong-answer">{option} (Your choice)</div>', unsafe_allow_html=True)
                else: st.markdown(f'<div class="feedback-option normal-answer">{option}</div>', unsafe_allow_html=True)
            st.info(f"**Explanation:** {question_data['explanation']}"); st.button("Next Question", on_click=go_to_next_quiz_question)
        else:
            with st.form("quiz_form"):
                choice = None; options_list = question_data['options']
                if "Tone Identification" in current_part_key:
                    if question_data.get("question_type") == "multi": choice = st.multiselect("Select all that apply:", options_list, key=f"ms_{current_index}", format_func=format_options_with_info)
                    else: choice = st.radio("Select one:", options_list, key=f"radio_{current_index}", index=None, format_func=format_options_with_info)
                else: choice = st.radio("Select one:", options_list, key=f"radio_{current_part_key}_{current_index}", index=None)
                if st.form_submit_button("Submit Answer"):
                    if not choice: st.error("Please select an option.")
                    else:
                        st.session_state.last_choice = choice; correct_answer = question_data.get('correct_answer')
                        is_correct = (set(choice) == set(correct_answer)) if isinstance(correct_answer, list) else (choice == correct_answer)
                        st.session_state.is_correct = is_correct
                        if is_correct: st.session_state.score += 1
                        st.session_state.show_feedback = True; st.rerun()

elif st.session_state.page == 'quiz_results':
    st.title("Quiz Completed! 🎉")
    total_scorable_questions = sum(len(item.get("questions", [item])) for part in st.session_state.all_data['quiz'].values() for item in part)
    passing_score = math.ceil(total_scorable_questions * 0.80) if total_scorable_questions > 0 else 1
    st.header(f"Your Final Score: {st.session_state.score} / {total_scorable_questions}")
    if st.session_state.score >= passing_score:
        st.success("**Status: Passed**"); st.markdown("Congratulations! You have qualified for the main user study.")
        if st.button("Proceed to User Study"): st.session_state.page = 'user_study_main'; st.rerun()
    else:
        st.error("**Status: Failed**"); st.markdown(f"Unfortunately, you did not meet the passing score of {passing_score}. You can try again.")
        st.button("Take Quiz Again", on_click=restart_quiz)
    st.info("Scoring is based on answering correctly on your first attempt.")

elif st.session_state.page == 'user_study_main':
    with st.sidebar:
        st.header("User Study Sections"); st.button("Part 1: Caption Rating", on_click=jump_to_study_part, args=(1,), use_container_width=True); st.button("Part 2: Caption Comparison", on_click=jump_to_study_part, args=(2,), use_container_width=True); st.button("Part 3: Tone Intensity Change", on_click=jump_to_study_part, args=(3,), use_container_width=True)
    
    if st.session_state.study_part == 1:
        st.header("User Study Part 1: Caption Quality Rating")
        all_videos = st.session_state.all_data['study']['part1_ratings']
        video_idx, caption_idx = st.session_state.current_video_index, st.session_state.current_caption_index
        if video_idx >= len(all_videos): st.session_state.study_part = 2; st.rerun()
            
        current_video = all_videos[video_idx]; current_caption = current_video['captions'][caption_idx]
        col1, col2 = st.columns([1, 1.8])
        with col1:
            if current_video.get("orientation") == "portrait":
                video_base64 = get_video_as_base64(current_video['video_path'])
                if video_base64: st.markdown(f'<video controls autoplay muted loop style="max-height:{PORTRAIT_VIDEO_MAX_HEIGHT}px; margin:0 auto; display:block; border-radius:10px;"><source src="data:video/mp4;base64,{video_base64}" type="video/mp4"></video>', unsafe_allow_html=True)
            else: st.video(current_video['video_path'], autoplay=True, muted=True)
            st.caption("Video is muted."); st.subheader("Video Summary"); st.info(current_video["video_summary"])
        with col2:
            colors = ["#FFEEEE", "#EBF5FF", "#E6F7EA"]; highlight_color = colors[caption_idx % len(colors)]
            st.markdown(f'<div class="part1-caption-box" style="background-color:{highlight_color};"><p class="caption-text">{current_caption["text"]}</p></div>', unsafe_allow_html=True)

            control_scores = current_caption.get("control_scores", {}); personality_traits = list(control_scores.get("personality", {}).keys()); style_traits = list(control_scores.get("writing_style", {}).keys()); application_text = current_caption.get("application", "the intended application")
            personality_str, style_str = ", ".join(personality_traits), ", ".join(style_traits)
            q_templates = st.session_state.all_data['questions']['part1_questions']
            
            questions_to_ask = sorted(q_templates, key=lambda x: x['id']) # Sort to ensure order
            
            formatted_questions = []
            for q in questions_to_ask:
                text = q['text']
                if q['id'] == 'persona_match': text = text.format(f'<b class="highlight-trait">{personality_str}</b>')
                elif q['id'] == 'style_match': text = text.format(f'<b class="highlight-trait">{style_str}</b>')
                elif q['id'] == 'usefulness': text = text.format(f'<b class="highlight-trait">{application_text}</b>')
                formatted_questions.append({"id": q['id'], "text": text})

            with st.form(key=f"study_form_rating_{video_idx}_{caption_idx}"):
                responses = {}
                row1_cols = st.columns(3)
                for i, q in enumerate(formatted_questions[:3]):
                    with row1_cols[i]: st.markdown(f"<div class='slider-label'><strong>{i+1}. {q['text']}</strong></div>", unsafe_allow_html=True); responses[q['id']] = st.slider(f"q_{i+1}", 1, 5, 3, key=f"{current_caption['caption_id']}_{q['id']}", label_visibility="collapsed")
                row2_cols = st.columns(3)
                for i, q in enumerate(formatted_questions[3:]):
                    q_num = i + 4
                    with row2_cols[i]:
                        st.markdown(f"<div class='slider-label'><strong>{q_num}. {q['text']}</strong></div>", unsafe_allow_html=True)
                        if q['id'] == 'shareability': responses[q['id']] = st.radio(f"q_{q_num}", ["Yes", "No"], index=None, horizontal=True, key=f"{current_caption['caption_id']}_{q['id']}", label_visibility="collapsed")
                        else: responses[q['id']] = st.slider(f"q_{q_num}", 1, 5, 3, key=f"{current_caption['caption_id']}_{q['id']}", label_visibility="collapsed")
                if st.form_submit_button("Submit Ratings"):
                    if responses.get('shareability') is None: st.error("Please answer all 6 questions.")
                    else:
                        for q_id, choice in responses.items(): save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_video, current_caption, choice, 'user_study_part1', next((q['text'] for q in formatted_questions if q['id'] == q_id), "N/A"))
                        if st.session_state.current_caption_index < len(current_video['captions']) - 1: st.session_state.current_caption_index += 1
                        else: st.session_state.current_video_index += 1; st.session_state.current_caption_index = 0
                        st.rerun()

    elif st.session_state.study_part == 2:
        st.header("User Study Part 2: Which one is better?")
        all_comparisons = st.session_state.all_data['study']['part2_comparisons']; comp_idx = st.session_state.current_comparison_index
        if comp_idx >= len(all_comparisons): st.session_state.study_part = 3; st.rerun()
        current_comp = all_comparisons[comp_idx]
        col1, col2 = st.columns([1, 1.8])
        with col1:
            if current_comp.get("orientation") == "portrait":
                video_base64 = get_video_as_base64(current_comp['video_path'])
                if video_base64: st.markdown(f'<video controls autoplay muted loop style="max-height:{PORTRAIT_VIDEO_MAX_HEIGHT}px; margin:0 auto; display:block; border-radius:10px;"><source src="data:video/mp4;base64,{video_base64}" type="video/mp4"></video>', unsafe_allow_html=True)
            else: st.video(current_comp['video_path'], autoplay=True, muted=True)
            st.caption("Video is muted."); st.subheader("Video Summary"); st.info(current_comp["video_summary"])
        with col2:
            st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_comp["caption_A"]}</p></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_comp["caption_B"]}</p></div>', unsafe_allow_html=True)
            with st.form(key=f"study_form_comparison_{comp_idx}"):
                control_scores = current_comp.get("control_scores", {}); personality_traits = list(control_scores.get("personality", {}).keys()); style_traits = list(control_scores.get("writing_style", {}).keys())
                personality_str, style_str = ", ".join(personality_traits), ", ".join(style_traits)
                q_templates = st.session_state.all_data['questions']['part2_questions']
                
                part2_questions = sorted(q_templates, key=lambda x: x['id']) # Sort to ensure order
                formatted_questions = []
                for q in part2_questions:
                    text = q['text']
                    if q['id'] == 'persona_better': text = text.format(f"<b class='highlight-trait'>{personality_str}</b>")
                    elif q['id'] == 'style_better': text = text.format(f"<b class='highlight-trait'>{style_str}</b>")
                    formatted_questions.append({"id": q['id'], "text": text})

                options, responses = ["Caption A", "Caption B", "Both A and B", "Neither A nor B"], {}
                question_cols = st.columns(4)
                for i, q in enumerate(formatted_questions):
                    with question_cols[i]: st.markdown(f"<div class='slider-label'><strong>{i+1}. {q['text']}</strong></div>", unsafe_allow_html=True); responses[q['id']] = st.radio(q['text'], options, index=None, label_visibility="collapsed", key=f"{current_comp['comparison_id']}_{q['id']}")
                if st.form_submit_button("Submit Comparison"):
                    if any(choice is None for choice in responses.values()): st.error("Please answer all four questions.")
                    else:
                        for q_id, choice in responses.items(): save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_comp, current_comp, choice, 'user_study_part2', next((q['text'] for q in formatted_questions if q['id'] == q_id), "N/A"))
                        st.session_state.current_comparison_index += 1; st.rerun()
    
    elif st.session_state.study_part == 3:
        st.header("User Study Part 3: Compare the intensities of author's personality/writing style")
        all_changes = st.session_state.all_data['study']['part3_intensity_change']; change_idx = st.session_state.current_change_index
        if change_idx >= len(all_changes): st.session_state.page = 'final_thank_you'; st.rerun()
        current_change = all_changes[change_idx]
        col1, col2 = st.columns([1, 1.8])
        with col1:
            if current_change.get("orientation") == "portrait":
                video_base64 = get_video_as_base64(current_change['video_path'])
                if video_base64: st.markdown(f'<video controls autoplay muted loop style="max-height:{PORTRAIT_VIDEO_MAX_HEIGHT}px; margin:0 auto; display:block; border-radius:10px;"><source src="data:video/mp4;base64,{video_base64}" type="video/mp4"></video>', unsafe_allow_html=True)
            else: st.video(current_change['video_path'], autoplay=True, muted=True)
            st.caption("Video is muted."); st.subheader("Video Summary"); st.info(current_change["video_summary"])
        with col2:
            st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_change["caption_A"]}</p></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_change["caption_B"]}</p></div>', unsafe_allow_html=True); st.write("---")
            with st.form(key=f"study_form_change_{change_idx}"):
                field_to_change, change_type = current_change['field_to_change'], current_change['change_type']
                field_type, trait = list(field_to_change.keys())[0], list(field_to_change.values())[0]
                q_template = st.session_state.all_data['questions']['part3_questions'][field_type]
                dynamic_question = q_template.format(f"<b class='highlight-trait'>{trait}</b>", change_type=change_type)
                q_cols = st.columns(2)
                with q_cols[0]: st.markdown(f"**1. {dynamic_question}**", unsafe_allow_html=True); choice1 = st.radio("q1_label", ["Yes", "No"], index=None, horizontal=True, key=f"{current_change['change_id']}_q1", label_visibility="collapsed")
                with q_cols[1]: q2_text = "Is the core factual content preserved across both captions?"; st.markdown(f"**2. {q2_text}**"); choice2 = st.radio("q2_label", ["Yes", "No"], index=None, horizontal=True, key=f"{current_change['change_id']}_q2", label_visibility="collapsed")
                if st.form_submit_button("Submit Answers"):
                    if choice1 is None or choice2 is None: st.error("Please answer both questions.")
                    else:
                        save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice1, 'user_study_part3', dynamic_question)
                        save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice2, 'user_study_part3', q2_text)
                        st.session_state.current_change_index += 1; st.rerun()

elif st.session_state.page == 'final_thank_you':
    st.title("Study Complete! Thank You! 🙏"); st.success("You have successfully completed all parts of the study. We sincerely appreciate your time and valuable contribution to our research!"); st.markdown("You may now close this browser tab.")

