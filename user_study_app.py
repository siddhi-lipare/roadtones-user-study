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
from streamlit_js_eval import streamlit_js_eval # <-- CORRECTED IMPORT

# --- Configuration ---
INTRO_VIDEO_PATH = "media/start_video_slower.mp4"
STUDY_DATA_PATH = "study_data.json"
QUIZ_DATA_PATH = "quiz_data.json"
INSTRUCTIONS_PATH = "instructions.json"
QUESTIONS_DATA_PATH = "questions.json"

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource
@st.cache_data
def get_video_duration(path):
    """Reads a video file and returns its duration in seconds."""
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return 10
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        cap.release()
        return duration
    except Exception:
        return 10
    
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
        st.error("Deployment Error: Spreadsheet 'roadtones-streamlit-userstudy-responses' not found.")
        return None
    except Exception as e:
        st.error(f"Could not connect to Google Sheets: {e}")
        return None

# --- Custom CSS ---
st.markdown("""
<style>
/* Import Google Font 'Inter' */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&display=swap');
/* (All your other CSS styles remain here...) */
.slider-label { min-height: 80px; margin-bottom: 0.5rem; }
.highlight-trait { color: #4f46e5; font-weight: 600; }
.caption-text { font-family: 'Inter', sans-serif; font-weight: 500; font-size: 19px !important; line-height: 1.6; }
.part1-caption-box { border-radius: 10px; padding: 1rem 1.5rem; margin-bottom: 20px; }
.part1-caption-box strong { font-size: 18px; font-family: 'Inter', sans-serif; font-weight: 600; color: #111827 !important; }
.part1-caption-box .caption-text { margin: 0.5em 0 0 0; color: #111827 !important; }
.comparison-caption-box { background-color: var(--secondary-background-color); border-left: 5px solid #6366f1; padding: 1rem 1.5rem; margin: 1rem 0; border-radius: 0.25rem; }
.comparison-caption-box strong { font-size: 18px; font-family: 'Inter', sans-serif; font-weight: 600; }
.quiz-question-box { background-color: #F0F2F6; padding: 1rem 1.5rem; border: 1px solid var(--gray-300); border-bottom: none; border-radius: 0.5rem 0.5rem 0 0; }
body[theme="dark"] .quiz-question-box { background-color: var(--secondary-background-color); }
.quiz-question-box > strong { font-family: 'Inter', sans-serif; font-size: 18px; font-weight: 600; }
.quiz-question-box .question-text-part { font-family: 'Inter', sans-serif; font-size: 19px; font-weight: 500; margin-left: 0.5em; }
[data-testid="stForm"] { border: 1px solid var(--gray-300); border-top: none; border-radius: 0 0 0.5rem 0.5rem; padding: 1.5rem 1.5rem 0.5rem 1.5rem; margin-top: 0 !important; }
.feedback-option { padding: 10px; border-radius: 8px; margin-bottom: 8px; border-width: 1px; border-style: solid; }
.correct-answer { background-color: #d1fae5; border-color: #6ee7b7; color: #065f46; }
.wrong-answer { background-color: #fee2e2; border-color: #fca5a5; color: #991b1b; }
body[theme="dark"] .correct-answer { background-color: #064e3b; border-color: #10b981; color: #a7f3d0; }
body[theme="dark"] .wrong-answer { background-color: #7f1d1d; border-color: #ef4444; color: #fecaca; }
.normal-answer { background-color: white !important; border-color: #d1d5db !important; color: #111827 !important; }
.stMultiSelect [data-baseweb="tag"] { background-color: #BDE0FE !important; color: #003366 !important; }
div[data-testid="stSlider"] { max-width: 250px; }
.reference-box { background-color: #FFFBEB; border: 1px solid #eab308; border-radius: 0.5rem; padding: 1rem 1.5rem; margin-top: 1.5rem; }
body[theme="dark"] .reference-box { background-color: var(--secondary-background-color); }
.reference-box h3 { margin-top: 0; padding-bottom: 0.5rem; font-size: 18px; font-weight: 600; }
.reference-box ul { padding-left: 20px; margin: 0; }
.reference-box li { margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)


# --- Central Dictionary for All Definitions ---
DEFINITIONS = {
    'Adventurous': 'Shows a willingness to take risks or try out new experiences.',
    'Amusing': 'Causes lighthearted laughter or provides entertainment in a playful way.',
    'Angry': 'Expresses strong annoyance, displeasure, or hostility towards an event.',
    'Anxious': 'Shows a feeling of worry, nervousness, or unease about an uncertain outcome.',
    'Appreciative': 'Expresses gratitude, admiration, or praise for an action or event.',
    'Assertive': 'Expresses opinions or desires confidently and forcefully.',
    'Caring': 'Displays kindness and concern for others.',
    'Considerate': 'Shows careful thought and concern for the well-being or safety of others.',
    'Critical': 'Expresses disapproving comments or judgments about an action or behavior.',
    'Cynical (Doubtful, Skeptical)': "Shows a distrust of others' sincerity or integrity.",
    'Emotional': 'Expresses feelings openly and strongly, such as happiness, sadness, or fear.',
    'Energetic': 'Displays a high level of activity, excitement, or dynamism.',
    'Enthusiastic': 'Shows intense and eager enjoyment or interest in an event.',
    'Observant': 'States facts or details about an event in a neutral, notice-based way.',
    'Objective (Detached, Impartial)': 'Presents information without personal feelings or bias.',
    'Questioning': 'Raises questions or expresses uncertainty about a situation.',
    'Reflective': 'Shows deep thought or contemplation about an event or idea.',
    'Sarcastic': 'Uses irony or mockery to convey contempt, often by saying the opposite of what is meant.',
    'Serious': 'Treats the subject with gravity and importance, without humor.',
    'Advisory': 'Gives advice, suggestions, or warnings about a situation.',
    'CallToAction': 'Encourages the reader to take a specific action.',
    'Conversational': 'Uses an informal, personal, and chatty style, as if talking directly to a friend.',
    'Exaggeration': 'Represents something as being larger, better, or worse than it really is for effect.',
    'Factual': 'Presents information objectively and accurately, like a news report.',
    'Instructional': 'Provides clear directions or information on how to do something.',
    'Judgmental': 'Displays an overly critical or moralizing point of view on actions shown.',
    'Metaphorical': 'Uses symbolic language or comparisons to describe something.',
    'Persuasive': 'Aims to convince the reader to agree with a particular point of view.',
    'Rhetorical Question': 'Asks a question not for an answer, but to make a point or create a dramatic effect.',
    'Public Safety Alert': 'Intended to inform the public about potential dangers or safety issues.',
    'Social Media Update': 'A casual post for sharing personal experiences or observations with friends and followers.',
    'Driver Behavior Monitoring': 'Used in systems that track and analyze driving patterns for insurance or fleet management.',
    'Law Enforcement Alert': 'A formal notification directed at police or traffic authorities to report violations.',
    'Traffic Analysis': 'Data-driven content used for studying traffic flow, violations, and road conditions.',
    'Community Road Safety Awareness': 'Aimed at educating the local community about road safety practices.',
    'Public Safety Awareness': 'General information to raise public consciousness about safety.',
    'Road Safety Education': 'Content designed to teach drivers or the public about safe road use.',
    'Traffic Awareness': 'Information focused on current traffic conditions or general traffic issues.'
}

# --- Helper Functions (No changes here) ---
@st.cache_data
def get_video_orientation(path):
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened(): return "landscape"
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        cap.release()
        return "portrait" if height > width else "landscape"
    except Exception:
        return "landscape"

@st.cache_data
def load_data():
    data = {}
    with open(INSTRUCTIONS_PATH, 'r', encoding='utf-8') as f: data['instructions'] = json.load(f)
    with open(QUIZ_DATA_PATH, 'r', encoding='utf-8') as f: data['quiz'] = json.load(f)
    with open(STUDY_DATA_PATH, 'r', encoding='utf-8') as f: study_data = json.load(f)
    with open(QUESTIONS_DATA_PATH, 'r', encoding='utf-8') as f: data['questions'] = json.load(f)
    for part in study_data.values():
        for item in part:
            item['orientation'] = get_video_orientation(item['video_path']) if os.path.exists(item['video_path']) else 'landscape'
    data['study'] = study_data
    return data

def save_response(email, age, gender, video_data, caption_data, choice, study_phase, question_text, was_correct=None):
    worksheet = connect_to_gsheet() 
    if worksheet is None: return
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        response_data = [email, age, str(gender), timestamp, study_phase, video_data.get('video_id', 'N/A'), caption_data.get('caption_id') or caption_data.get('comparison_id') or caption_data.get('change_id'), question_text, str(choice), str(was_correct) if was_correct is not None else 'N/A', 1 if study_phase == 'quiz' else 'N/A']
        if len(worksheet.get_all_values()) == 0:
             worksheet.append_row(['email', 'age', 'gender', 'timestamp', 'study_phase', 'video_id', 'sample_id', 'question_text', 'user_choice', 'was_correct', 'attempts_taken'])
        worksheet.append_row(response_data)
    except Exception as e:
        st.error(f"Failed to write to Google Sheet: {e}")

def go_to_next_quiz_question():
    with st.spinner("Saving your answer..."):
        part_keys = list(st.session_state.all_data['quiz'].keys())
        current_part_key = part_keys[st.session_state.current_part_index]
        questions_for_part = st.session_state.all_data['quiz'][current_part_key]
        sample = questions_for_part[st.session_state.current_sample_index]
        was_correct = st.session_state.is_correct
        question_text = "N/A"
        if "Tone Controllability" in current_part_key:
            question_text = f"Intensity of '{sample['tone_to_compare']}' has {sample['comparison_type']}"
        elif "Caption Quality" in current_part_key:
            rating_question = sample["questions"][st.session_state.current_rating_question_index]
            question_text = rating_question["question_text"]
        else:
            question_text = "Tone Identification"
        dummy_video_data = {'video_id': sample.get('sample_id')}
        dummy_caption_data = {'caption_id': sample.get('sample_id'), 'text': sample.get('caption', 'N/A')}
        
        save_response(st.session_state.email, st.session_state.age, st.session_state.gender, dummy_video_data, dummy_caption_data, st.session_state.last_choice, 'quiz', question_text, was_correct=was_correct)
        
        if "Caption Quality" in current_part_key:
            st.session_state.current_rating_question_index += 1
            if st.session_state.current_rating_question_index >= len(sample["questions"]):
                st.session_state.current_part_index += 1
                st.session_state.current_rating_question_index = 0
        else:
            st.session_state.current_sample_index += 1
            if st.session_state.current_sample_index >= len(questions_for_part):
                st.session_state.current_part_index += 1
                st.session_state.current_sample_index = 0
        st.session_state.show_feedback = False

def jump_to_part(part_index):
    st.session_state.current_part_index = part_index
    st.session_state.current_sample_index = 0
    st.session_state.current_rating_question_index = 0
    st.session_state.show_feedback = False

def jump_to_study_part(part_number):
    st.session_state.study_part = part_number
    st.session_state.current_video_index = 0
    st.session_state.current_caption_index = 0
    st.session_state.current_comparison_index = 0
    st.session_state.current_change_index = 0

def restart_quiz():
    st.session_state.page = 'quiz'
    st.session_state.current_part_index = 0
    st.session_state.current_sample_index = 0
    st.session_state.current_rating_question_index = 0
    st.session_state.show_feedback = False
    st.session_state.score = 0
    st.session_state.score_saved = False

def format_options_with_info(option_name):
    if option_name in DEFINITIONS:
        return f"{option_name} ({DEFINITIONS[option_name]})"
    return option_name

# --- Main App ---
st.set_page_config(layout="wide", page_title="Tone-controlled Video Captioning")

if 'page' not in st.session_state:
    st.session_state.page = 'demographics'
    st.session_state.current_part_index = 0
    st.session_state.current_sample_index = 0
    st.session_state.show_feedback = False
    st.session_state.current_rating_question_index = 0
    st.session_state.score = 0
    st.session_state.score_saved = False
    st.session_state.study_part = 1
    st.session_state.current_video_index = 0
    st.session_state.current_caption_index = 0
    st.session_state.current_comparison_index = 0
    st.session_state.current_change_index = 0
    st.session_state.all_data = load_data()

if st.session_state.all_data is None:
    st.stop()

# --- Page Rendering Logic (No changes here) ---
if st.session_state.page == 'demographics':
    st.title("Tone-controlled Video Captioning")
    if st.button("DEBUG: Skip to Main Study"):
        st.session_state.email = "debug@test.com"
        st.session_state.age = 25
        st.session_state.gender = "Prefer not to say"
        st.session_state.page = 'user_study_main'
        st.rerun()
    st.header("Welcome! Before you begin, please provide some basic information:")
    email = st.text_input("Please enter your email address:")
    age = st.selectbox("Age:", options=list(range(18, 61)), index=None, placeholder="Select your age...")
    gender = st.selectbox("Gender:", options=["Male", "Female", "Other / Prefer not to say"], index=None, placeholder="Select your gender...")
    st.write("---")
    if st.checkbox("I am over 18 and agree to participate in this study. I understand my responses will be recorded anonymously."):
        if st.button("Next"):
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not all([email, age, gender]):
                st.error("Please fill in all fields to continue.")
            elif not re.match(email_regex, email):
                st.error("Please enter a valid email address.")
            else:
                st.session_state.email = email
                st.session_state.age = age
                st.session_state.gender = gender
                st.session_state.page = 'intro_video'
                st.rerun()

elif st.session_state.page == 'intro_video':
    st.title("Introductory Video")
    _ , vid_col, _ = st.columns([1, 3, 1])
    with vid_col:
        st.video(INTRO_VIDEO_PATH, autoplay=True, muted=True)
        st.markdown("##### [Additional user study guide](https://docs.google.com/document/d/1TCGi_93Q-lfCAluVU5XglS86C3SBOL8VayXL1d6C_7I/edit?usp=sharing)")
    if st.button("Next"):
        st.session_state.page = 'quiz'
        st.rerun()

elif st.session_state.page == 'quiz':
    part_keys = list(st.session_state.all_data['quiz'].keys())
    with st.sidebar:
        st.header("Quiz Sections")
        for i, part_name in enumerate(part_keys):
            st.button(part_name, on_click=jump_to_part, args=(i,), use_container_width=True)
    if st.session_state.current_part_index >= len(part_keys):
        st.session_state.page = 'quiz_results'
        st.rerun()

    current_part_key = part_keys[st.session_state.current_part_index]
    questions_for_part = st.session_state.all_data['quiz'][current_part_key]
    current_index = st.session_state.current_sample_index
    sample = questions_for_part[current_index]
    sample_id = sample.get('sample_id', f'quiz_{current_index}')
    view_state_key = f'view_state_{sample_id}'
    if view_state_key not in st.session_state:
        st.session_state[view_state_key] = {'step': 1}
    current_step = st.session_state[view_state_key]['step']

    def stream_text(text):
        for word in text.split(" "): yield word + " "; time.sleep(0.05)
    
    display_title = re.sub(r'Part \d+: ', '', current_part_key)
    if "Tone Identification" in current_part_key: display_title = f"{sample.get('category', 'Tone').title()} Identification"
    elif "Tone Controllability" in current_part_key: display_title = f"{sample.get('category', 'Tone').title()} Comparison"
    st.header(display_title)
    st.progress(current_index / len(questions_for_part), text=f"Question: {current_index + 1}/{len(questions_for_part)}")
    col1, col2 = st.columns([1.2, 1.5])

    with col1:
        st.video(sample['video_path'], autoplay=False)
        if current_step == 1 and st.button("Proceed to Summary"): st.session_state[view_state_key]['step'] = 2; st.rerun()
        if current_step >= 2 and "video_summary" in sample:
            st.subheader("Video Summary")
            if st.session_state[view_state_key].get('summary_typed', False): st.info(sample["video_summary"])
            else:
                with st.empty(): st.write_stream(stream_text(sample["video_summary"]))
                st.session_state[view_state_key]['summary_typed'] = True
            if current_step == 2 and st.button("Proceed to Caption"): st.session_state[view_state_key]['step'] = 3; st.rerun()

    with col2:
        question_data = sample["questions"][st.session_state.current_rating_question_index] if "Caption Quality" in current_part_key else sample
        if current_step >= 3:
            if "Tone Controllability" in current_part_key:
                st.markdown(f"""<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{sample["caption_A"]}</p></div>""", unsafe_allow_html=True)
                st.markdown(f"""<div class="comparison-caption-box" style="margin-top:0.5rem;"><strong>Caption B</strong><p class="caption-text">{sample["caption_B"]}</p></div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="comparison-caption-box"><strong>Caption</strong><p class="caption-text">{sample["caption"]}</p></div>""", unsafe_allow_html=True)
            if current_step == 3 and st.button("Show Questions"): st.session_state[view_state_key]['step'] = 4; st.rerun()
        if current_step >= 4:
            if st.session_state.show_feedback:
                user_choice, correct_answer = st.session_state.last_choice, question_data.get('correct_answer')
                if not isinstance(user_choice, list): user_choice = [user_choice]
                if not isinstance(correct_answer, list): correct_answer = [correct_answer]
                st.write("**Your Answer vs Correct Answer:**")
                for option in question_data['options']:
                    if option in correct_answer: st.markdown(f'<div class="feedback-option correct-answer"><strong>{option} (Correct Answer)</strong></div>', unsafe_allow_html=True)
                    elif option in user_choice: st.markdown(f'<div class="feedback-option wrong-answer">{option} (Your selection)</div>', unsafe_allow_html=True)
                    else: st.markdown(f'<div class="feedback-option normal-answer">{option}</div>', unsafe_allow_html=True)
                st.info(f"**Explanation:** {question_data['explanation']}")
                if st.button("Next Question"): go_to_next_quiz_question(); st.session_state.pop(view_state_key, None); st.rerun()
            else:
                question_text = ""
                if "Tone Controllability" in current_part_key: question_text = f"Has the author's <b class='highlight-trait'>{sample['tone_to_compare']}</b> writing style <b class='highlight-trait'>{sample['comparison_type']}</b> from Caption A to B?"
                elif "Caption Quality" in current_part_key: question_text = question_data["question_text"]
                elif question_data.get("question_type") == "multi": question_text = "Identify 2 dominant personality traits projected by the captioner"
                else: question_text = f"Identify the most dominant {sample.get('category', 'tone').lower()} projected by the captioner"
                st.markdown(f'<div class="quiz-question-box"><strong>Question:</strong><span class="question-text-part">{question_text}</span></div>', unsafe_allow_html=True)
                with st.form("quiz_form"):
                    choice = None
                    if question_data.get("question_type") == "multi":
                        st.write("Select all that apply:")
                        choice = [opt for opt in question_data['options'] if st.checkbox(opt, key=f"cb_{current_index}_{opt}")]
                    else:
                        choice = st.radio("Select one option:", question_data['options'], key=f"radio_{current_index}", index=None, format_func=format_options_with_info)
                    if st.form_submit_button("Submit Answer"):
                        if not choice: st.error("Please select an option.")
                        else:
                            st.session_state.last_choice = choice
                            correct_answer = question_data.get('correct_answer')
                            is_correct = (set(choice) == set(correct_answer)) if isinstance(correct_answer, list) else (choice == correct_answer)
                            st.session_state.is_correct = is_correct
                            if is_correct: st.session_state.score += 1
                            st.session_state.show_feedback = True; st.rerun()

elif st.session_state.page == 'quiz_results':
    total_scorable_questions = 0
    for part_name, questions_list in st.session_state.all_data['quiz'].items():
        total_scorable_questions += sum(len(item.get("questions", [])) for item in questions_list) if "Caption Quality" in part_name else len(questions_list)
    passing_score = 5
    st.header(f"Your Final Score: {st.session_state.score} / {total_scorable_questions}")
    if st.session_state.score >= passing_score:
        st.success("**Status: Passed**")
        if st.button("Proceed to User Study"): st.session_state.page = 'user_study_main'; st.rerun()
    else:
        st.error("**Status: Failed**")
        st.markdown(f"Unfortunately, you did not meet the passing score of {passing_score}. You can try again.")
        st.button("Take Quiz Again", on_click=restart_quiz)

# --- Page 7: The Main User Study ---
elif st.session_state.page == 'user_study_main':
    if not st.session_state.all_data: st.error("Data could not be loaded."); st.stop()
    def stream_text(text):
        for word in text.split(" "): yield word + " "; time.sleep(0.05)
    with st.sidebar:
        st.header("Study Sections")
        st.button("Part 1: Caption Rating", on_click=jump_to_study_part, args=(1,), use_container_width=True)
        st.button("Part 2: Caption Comparison", on_click=jump_to_study_part, args=(2,), use_container_width=True)
        st.button("Part 3: Tone Intensity Change", on_click=jump_to_study_part, args=(3,), use_container_width=True)

    # =========================================================================
    # ==================== START: CORRECTED PART 1 CODE =======================
    # =========================================================================
    if st.session_state.study_part == 1:
        st.header("Caption Quality Rating")
        all_videos = st.session_state.all_data['study']['part1_ratings']
        video_idx, caption_idx = st.session_state.current_video_index, st.session_state.current_caption_index

        if video_idx >= len(all_videos):
            st.session_state.study_part = 2
            st.rerun()

        current_video = all_videos[video_idx]
        current_caption = current_video['captions'][caption_idx]
        
        view_state_key = f"view_state_p1_{current_caption['caption_id']}"
        summary_typed_key = f"summary_typed_{current_video['video_id']}"

        # Define all 5 questions structure beforehand for initialization
        q_templates = st.session_state.all_data['questions']['part1_questions']
        # Dummy formatting needed just to get the IDs correctly for init
        questions_to_ask_init = [
            {"id": "personality_relevance", "text": q_templates[0]["text"].format("")},
            {"id": "style_relevance", "text": q_templates[1]["text"].format("")},
            {"id": "factual_consistency", "text": q_templates[2]["text"]},
            {"id": "usefulness", "text": q_templates[3]["text"].format("")},
            {"id": "human_likeness", "text": q_templates[4]["text"]}
        ]
        question_ids = [q['id'] for q in questions_to_ask_init]

        # Initialize state: step 4 for subsequent captions, step 1 for the first
        if view_state_key not in st.session_state:
            initial_step = 4 if caption_idx > 0 else 1
            st.session_state[view_state_key] = {
                'step': initial_step,
                'responses': {},
                'interacted': {qid: False for qid in question_ids} # Initialize interaction tracker
            }
            if caption_idx == 0:
                st.session_state[summary_typed_key] = False # Reset typewriter for new video
        
        current_step = st.session_state[view_state_key]['step']
        
        # --- Callback Function ---
        def mark_interacted(q_id, view_key):
            """Marks a question slider as interacted."""
            if view_key in st.session_state and 'interacted' in st.session_state[view_key]:
                 st.session_state[view_key]['interacted'][q_id] = True
            # print(f"Slider {q_id} interacted: {st.session_state[view_key]['interacted']}") # Debug print

        col1, col2 = st.columns([1, 1.8])
        
        with col1:
            st.video(current_video['video_path'], autoplay=False)
            # Sequential reveal buttons (only for the first caption)
            if caption_idx == 0:
                if current_step == 1 and st.button("Proceed to Summary"):
                    st.session_state[view_state_key]['step'] = 2; st.rerun()
                if current_step >= 2:
                    st.subheader("Video Summary")
                    if st.session_state.get(summary_typed_key, False):
                        st.info(current_video["video_summary"])
                    else:
                        with st.empty(): st.write_stream(stream_text(current_video["video_summary"]))
                        st.session_state[summary_typed_key] = True
                    if current_step == 2 and st.button("Proceed to Caption"):
                        st.session_state[view_state_key]['step'] = 3; st.rerun()
            elif current_step >= 4:
                 st.subheader("Video Summary")
                 st.info(current_video["video_summary"])

        with col2:
            terms_to_define = set()
            
            if current_step >= 3:
                colors = ["#FFEEEE", "#EBF5FF", "#E6F7EA"]
                highlight_color = colors[caption_idx % len(colors)]
                st.markdown(f'''<div class="part1-caption-box" style="background-color: {highlight_color};"><strong>Caption:</strong><p class="caption-text">{current_caption["text"]}</p></div>''', unsafe_allow_html=True)
                
                if caption_idx == 0 and current_step == 3 and st.button("Show Questions"):
                    st.session_state[view_state_key]['step'] = 4; st.rerun()

            if current_step >= 4:
                control_scores = current_caption.get("control_scores", {})
                personality_traits = list(control_scores.get("personality", {}).keys())
                style_traits = list(control_scores.get("writing_style", {}).keys())
                application_text = current_caption.get("application", "the intended application")
                terms_to_define.update(personality_traits); terms_to_define.update(style_traits); terms_to_define.add(application_text)

                personality_str = ", ".join(f"<b class='highlight-trait'>{p}</b>" for p in personality_traits)
                style_str = ", ".join(f"<b class='highlight-trait'>{s}</b>" for s in style_traits)
                
                # Define all 5 questions with correct formatting
                questions_to_ask = [
                    {"id": "personality_relevance", "text": q_templates[0]["text"].format(personality_str)},
                    {"id": "style_relevance", "text": q_templates[1]["text"].format(style_str)},
                    {"id": "factual_consistency", "text": q_templates[2]["text"]},
                    {"id": "usefulness", "text": q_templates[3]["text"].format(f"<b class='highlight-trait'>{application_text}</b>")},
                    {"id": "human_likeness", "text": q_templates[4]["text"]}
                ]
                options_map = {"personality_relevance": ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"], "style_relevance": ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"],"factual_consistency": ["Contradicts", "Inaccurate", "Partially", "Mostly Accurate", "Accurate"], "usefulness": ["Not at all", "Slightly", "Moderately", "Very", "Extremely"], "human_likeness": ["Robotic", "Unnatural", "Moderate", "Very Human-like", "Natural"]}
                
                num_questions_to_show_now = len(questions_to_ask) if caption_idx > 0 else current_step - 3
                responses = st.session_state[view_state_key]['responses']
                interacted_state = st.session_state[view_state_key]['interacted']

                # --- GRID-BASED SEQUENTIAL RENDER (With Interaction Tracking) ---
                question_cols_row1 = st.columns(3)
                question_cols_row2 = st.columns(3)

                # Question 1 (Show if step >= 4)
                if num_questions_to_show_now >= 1:
                    with question_cols_row1[0]:
                        q = questions_to_ask[0]
                        slider_options = options_map[q['id']]
                        st.markdown(f"<div class='slider-label'><strong>1. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.select_slider(
                            q['id'], options=slider_options,
                            value=responses.get(q['id'], slider_options[2]),
                            key=f"ss_{q['id']}_cap{caption_idx}",
                            label_visibility="collapsed",
                            on_change=mark_interacted, # <-- ADD CALLBACK
                            args=(q['id'], view_state_key) # <-- PASS ARGS
                        )

                # Question 2 (Show if step >= 5 for first caption, or immediately otherwise)
                if num_questions_to_show_now >= 2:
                    with question_cols_row1[1]:
                        q = questions_to_ask[1]
                        slider_options = options_map[q['id']]
                        st.markdown(f"<div class='slider-label'><strong>2. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.select_slider(
                            q['id'], options=slider_options,
                            value=responses.get(q['id'], slider_options[2]),
                            key=f"ss_{q['id']}_cap{caption_idx}",
                            label_visibility="collapsed",
                            on_change=mark_interacted, # <-- ADD CALLBACK
                            args=(q['id'], view_state_key) # <-- PASS ARGS
                        )

                # Question 3 (Show if step >= 6 for first caption, or immediately otherwise)
                if num_questions_to_show_now >= 3:
                     with question_cols_row1[2]:
                        q = questions_to_ask[2]
                        slider_options = options_map[q['id']]
                        st.markdown(f"<div class='slider-label'><strong>3. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.select_slider(
                            q['id'], options=slider_options,
                            value=responses.get(q['id'], slider_options[2]),
                            key=f"ss_{q['id']}_cap{caption_idx}",
                            label_visibility="collapsed",
                            on_change=mark_interacted, # <-- ADD CALLBACK
                            args=(q['id'], view_state_key) # <-- PASS ARGS
                        )

                # Question 4 (Show if step >= 7 for first caption, or immediately otherwise)
                if num_questions_to_show_now >= 4:
                    with question_cols_row2[0]:
                        q = questions_to_ask[3]
                        slider_options = options_map[q['id']]
                        st.markdown(f"<div class='slider-label'><strong>4. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.select_slider(
                            q['id'], options=slider_options,
                            value=responses.get(q['id'], slider_options[2]),
                            key=f"ss_{q['id']}_cap{caption_idx}",
                            label_visibility="collapsed",
                            on_change=mark_interacted, # <-- ADD CALLBACK
                            args=(q['id'], view_state_key) # <-- PASS ARGS
                        )

                # Question 5 (Show if step >= 8 for first caption, or immediately otherwise)
                if num_questions_to_show_now >= 5:
                    with question_cols_row2[1]:
                        q = questions_to_ask[4]
                        slider_options = options_map[q['id']]
                        st.markdown(f"<div class='slider-label'><strong>5. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.select_slider(
                            q['id'], options=slider_options,
                            value=responses.get(q['id'], slider_options[2]),
                            key=f"ss_{q['id']}_cap{caption_idx}",
                            label_visibility="collapsed",
                            on_change=mark_interacted, # <-- ADD CALLBACK
                            args=(q['id'], view_state_key) # <-- PASS ARGS
                        )
                
                st.write("---")

                # --- Validation Placeholder ---
                validation_placeholder = st.empty()

                # --- Navigation Logic (With Validation) ---
                if caption_idx == 0 and num_questions_to_show_now < len(questions_to_ask):
                    # For the first caption, check interaction before showing "Next Question"
                    question_to_validate_index = num_questions_to_show_now - 1 # Index of the *last shown* question
                    question_id_to_validate = questions_to_ask[question_to_validate_index]['id']
                    
                    if st.button(f"Next Question ({num_questions_to_show_now + 1}/{len(questions_to_ask)})"):
                        if not interacted_state.get(question_id_to_validate, False):
                             validation_placeholder.warning("⚠️ Please select a value for the current question before proceeding.")
                        else:
                            st.session_state[view_state_key]['step'] += 1
                            validation_placeholder.empty() # Clear warning on success
                            st.rerun()
                            
                elif num_questions_to_show_now >= len(questions_to_ask):
                    # For the last question or subsequent captions, check all interactions before submitting
                    if st.button("Submit Ratings"):
                        all_interacted = all(interacted_state.get(qid, False) for qid in question_ids)
                        if not all_interacted:
                            validation_placeholder.warning("⚠️ Please select a value for **all** questions before submitting.")
                        else:
                            validation_placeholder.empty() # Clear warning on success
                            with st.spinner("Saving your ratings..."):
                                for q_id, choice_text in responses.items():
                                    full_q_text = next((q['text'] for q in questions_to_ask if q['id'] == q_id), "N/A")
                                    # save_response(...) # Intentionally commented out
                            
                            st.session_state.current_caption_index += 1
                            if st.session_state.current_caption_index >= len(current_video['captions']):
                                st.session_state.current_video_index += 1
                                st.session_state.current_caption_index = 0
                            
                            # Clean up current view state before rerun
                            st.session_state.pop(view_state_key, None) 
                            st.rerun()

                # --- Reference Box ---
                reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {DEFINITIONS.get(term)}</li>" for term in sorted(list(terms_to_define)) if DEFINITIONS.get(term)) + "</ul></div>"
                st.markdown(reference_html, unsafe_allow_html=True)
    # ====================== END: CORRECTED PART 1 CODE =======================
    
    elif st.session_state.study_part == 2:
        # ... (Your Part 2 code remains unchanged) ...
        st.header("Which caption is better?")
        all_comparisons = st.session_state.all_data['study']['part2_comparisons']
        comp_idx = st.session_state.current_comparison_index
        if comp_idx >= len(all_comparisons): st.session_state.study_part = 3; st.rerun()
        current_comp = all_comparisons[comp_idx]
        col1, col2 = st.columns([1, 1.8])
        terms_to_define = set()
        with col1:
            st.video(current_comp['video_path'], autoplay=True, muted=True)
            st.caption("Video is muted for autoplay.")
            st.subheader("Video Summary"); st.info(current_comp["video_summary"])
        with col2:
            st.markdown(f"""<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_comp["caption_A"]}</p></div>""", unsafe_allow_html=True)
            st.markdown(f"""<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_comp["caption_B"]}</p></div>""", unsafe_allow_html=True)
            control_scores = current_comp.get("control_scores", {})
            personality_traits = list(control_scores.get("personality", {}).keys())
            style_traits = list(control_scores.get("writing_style", {}).keys())
            terms_to_define.update(personality_traits); terms_to_define.update(style_traits)
            personality_str = ", ".join(f"<b class='highlight-trait'>{p}</b>" for p in personality_traits)
            style_str = ", ".join(f"<b class='highlight-trait'>{s}</b>" for s in style_traits)
            with st.form(key=f"study_form_comparison_{comp_idx}"):
                q_templates = st.session_state.all_data['questions']['part2_questions']
                part2_questions = [{"id": q["id"], "text": q["text"].format(personality_str if 'personality' in q['id'] else style_str if 'style' in q['id'] else '')} for q in q_templates]
                options = ["Caption A", "Caption B", "Both A and B", "Neither A nor B"]
                responses = {}
                question_cols = st.columns(4) # Keep 4 columns for layout consistency
                for i, q in enumerate(part2_questions):
                    with question_cols[i]: # Place each question in its column
                        st.markdown(f"<div class='slider-label'><strong>{i+1}. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.radio(q['text'], options, index=None, label_visibility="collapsed", key=f"{current_comp['comparison_id']}_{q['id']}")
                if st.form_submit_button("Submit Comparison"):
                    if any(choice is None for choice in responses.values()): st.error("Please answer all four questions.")
                    else:
                        with st.spinner("Saving your responses..."):
                            for q_id, choice in responses.items():
                                # save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_comp, current_comp, choice, 'user_study_part2', next((q['text'] for q in part2_questions if q['id'] == q_id), "N/A"))
                                pass # Intentionally commented out for brevity
                        st.session_state.current_comparison_index += 1; st.rerun()
            reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {DEFINITIONS.get(term)}</li>" for term in sorted(list(terms_to_define)) if DEFINITIONS.get(term)) + "</ul></div>"
            st.markdown(reference_html, unsafe_allow_html=True)


    elif st.session_state.study_part == 3:
        # ... (Your Part 3 code remains unchanged) ...
        all_changes = st.session_state.all_data['study']['part3_intensity_change']
        change_idx = st.session_state.current_change_index
        if change_idx >= len(all_changes): st.session_state.page = 'final_thank_you'; st.rerun()
        current_change = all_changes[change_idx]
        field_to_change = current_change['field_to_change']
        field_type = list(field_to_change.keys())[0]
        st.header(f"{field_type.replace('_', ' ').title()} Comparison")
        col1, col2 = st.columns([1, 1.8])
        terms_to_define = set()
        with col1:
            st.video(current_change['video_path'], autoplay=True, muted=True)
            st.caption("Video is muted for autoplay.")
            st.subheader("Video Summary"); st.info(current_change["video_summary"])
        with col2:
            st.markdown(f"""<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_change["caption_A"]}</p></div>""", unsafe_allow_html=True)
            st.markdown(f"""<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_change["caption_B"]}</p></div>""", unsafe_allow_html=True)
            trait = field_to_change[field_type]
            terms_to_define.add(trait)
            with st.form(key=f"study_form_change_{change_idx}"):
                q_template = st.session_state.all_data['questions']['part3_questions'][field_type.replace('_', ' ').title()]
                # Corrected formatting for dynamic question
                dynamic_question_raw = q_template.format(trait=f"<b class='highlight-trait'>{trait}</b>", change_type=current_change['change_type'])
                dynamic_question = dynamic_question_raw # Keep raw for saving
                
                q2_text = "Is the core factual content consistent across both captions?"
                
                col_q1, col_q2 = st.columns(2) # Place questions side-by-side

                with col_q1:
                    st.markdown(f'**1. {dynamic_question}**', unsafe_allow_html=True)
                    choice1 = st.radio("q1_label", ["Yes", "No"], index=None, horizontal=True, key=f"{current_change['change_id']}_q1", label_visibility="collapsed")
                
                with col_q2:
                    st.markdown(f"**2. {q2_text}**")
                    choice2 = st.radio("q2_label", ["Yes", "No"], index=None, horizontal=True, key=f"{current_change['change_id']}_q2", label_visibility="collapsed")

                if st.form_submit_button("Submit Answers"):
                    if choice1 is None or choice2 is None: st.error("Please answer both questions.")
                    else:
                        with st.spinner("Saving your responses..."):
                            # save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice1, 'user_study_part3', dynamic_question) # Save raw question
                            # save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice2, 'user_study_part3', q2_text)
                            pass # Intentionally commented out for brevity
                        st.session_state.current_change_index += 1; st.rerun()
            reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {DEFINITIONS.get(term)}</li>" for term in sorted(list(terms_to_define)) if DEFINITIONS.get(term)) + "</ul></div>"
            st.markdown(reference_html, unsafe_allow_html=True)


elif st.session_state.page == 'final_thank_you':
    # ... (Thank you page code remains unchanged) ...
    st.title("Study Complete! Thank You!")
    st.success("You have successfully completed all parts of the study. We sincerely appreciate your time and valuable contribution to our research!")

# =====================================================================================
# FINAL, WORKING JAVASCRIPT SOLUTION
# =====================================================================================
js_script = """
const parent_document = window.parent.document;
if (!parent_document.arrowRightListenerAttached) {
    console.log("Attaching ArrowRight key listener.");
    parent_document.addEventListener('keyup', function(event) {
        const activeElement = parent_document.activeElement;
        if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
            return;
        }
        if (event.key === 'ArrowRight') {
            event.preventDefault();
            const targetButtonLabels = [
                "Submit Ratings", "Submit Comparison", "Submit Answers", "Submit Answer",
                "Next Question", "Show Questions", "Proceed to Caption", 
                "Proceed to Summary", "Proceed to User Study", "Next"
            ];
            const allButtons = Array.from(parent_document.querySelectorAll('button'));
            const visibleButtons = allButtons.filter(btn => btn.offsetParent !== null);
            for (const label of targetButtonLabels) {
                // Find the *last* visible button matching the label (more robust for Streamlit)
                const targetButton = [...visibleButtons].reverse().find(btn => btn.textContent.trim().includes(label));
                if (targetButton) {
                    console.log('ArrowRight detected, clicking button:', targetButton.textContent);
                    targetButton.click();
                    break;
                }
            }
        }
    });
    parent_document.arrowRightListenerAttached = true;
}
"""
streamlit_js_eval(js_expressions=js_script, key="keyboard_listener")