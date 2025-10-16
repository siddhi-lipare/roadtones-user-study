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

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource
@st.cache_data
def get_video_duration(path):
    """Reads a video file and returns its duration in seconds."""
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return 10  # Return a default duration if video can't be opened
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        cap.release()
        return duration
    except Exception:
        return 10 # Default duration on error
    
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
        st.error("Deployment Error: Spreadsheet 'roadtones-streamlit-userstudy-responses' not found. Please check the name and ensure the service account has editor access.")
        return None
    except Exception as e:
        st.error(f"Could not connect to Google Sheets: {e}")
        return None

# WORKSHEET = connect_to_gsheet()

# --- Custom CSS and JavaScript for better UI/UX ---
st.markdown("""
<style>
/* Import Google Font 'Inter' for a more modern, prominent look */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&display=swap');

/* For help text tooltips */
[data-testid="stTooltipContent"] {
    max-width: 300px;
    font-size: 14px;
    line-height: 1.5;
}
/* For aligning slider question text */
.slider-label {
    min-height: 80px; /* Increased height to ensure alignment even with text wrapping */
    margin-bottom: 0.5rem;
}

/* Style for highlighting traits in questions - Kept as a brand color */
.highlight-trait {
    color: #4f46e5; 
    font-weight: 600;
}

/* Base style for all caption text */
.caption-text {
    font-family: 'Inter', sans-serif;
    font-weight: 500; 
    font-size: 19px !important; 
    line-height: 1.6;
    color: var(--text-color);
}

/* --- PART 1 CAPTION BOX (CORRECTED FOR DARK THEME) --- */
.part1-caption-box {
    border-radius: 10px;
    padding: 1rem 1.5rem;
    margin-bottom: 20px;
}
/* Force dark text color for the "Caption:" label */
.part1-caption-box strong {
    font-size: 18px;
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    color: #111827 !important; /* Force dark text */
}
/* Force dark text color for the caption text itself */
.part1-caption-box .caption-text {
    margin: 0.5em 0 0 0;
    color: #111827 !important; /* Force dark text */
}


/* Part 2 & 3 Caption Box (for comparisons) - NOW USED BY QUIZ */
.comparison-caption-box {
    background-color: var(--secondary-background-color);
    border-left: 5px solid #6366f1; /* Kept as brand color */
    padding: 1rem 1.5rem;
    margin: 1rem 0;
    border-radius: 0.25rem;
}
.comparison-caption-box strong {
    font-size: 18px;
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    color: var(--text-color);
}
.comparison-caption-box .caption-text {
    margin: 0.5em 0 0 0;
}

/* --- QUIZ QUESTION BOX STYLING (CORRECTED FOR LIGHT THEME) --- */
.quiz-question-box {
    background-color: #F0F2F6; /* Light Grey for Light Theme by default */
    padding: 1rem 1.5rem;
    border: 1px solid var(--gray-300);
    border-bottom: none; 
    border-radius: 0.5rem 0.5rem 0 0; 
}
/* Override for Dark Theme */
body[theme="dark"] .quiz-question-box {
    background-color: var(--secondary-background-color);
}

.quiz-question-box > strong {
    font-family: 'Inter', sans-serif;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
}

.quiz-question-box .question-text-part {
    font-family: 'Inter', sans-serif;
    font-size: 19px;
    font-weight: 500;
    color: var(--text-color);
    margin-left: 0.5em;
}

/* Target the form element directly to connect it to the question box */
[data-testid="stForm"] {
    border: 1px solid var(--gray-300);
    border-top: none; 
    border-radius: 0 0 0.5rem 0.5rem; 
    padding: 1.5rem 1.5rem 0.5rem 1.5rem; 
    margin-top: 0 !important; 
    background-color: var(--background-color);
}

/* --- THEME-AWARE FEEDBACK BOX STYLING (FINAL CORRECTION) --- */
.feedback-option {
    padding: 10px;
    border-radius: 8px;
    margin-bottom: 8px;
    border-width: 1px;
    border-style: solid;
}
/* Light Theme Colors (Default) */
.correct-answer { background-color: #d1fae5; border-color: #6ee7b7; color: #065f46; }
.wrong-answer { background-color: #fee2e2; border-color: #fca5a5; color: #991b1b; }

/* Dark Theme Overrides for Correct/Wrong */
body[theme="dark"] .correct-answer { background-color: #064e3b; border-color: #10b981; color: #a7f3d0; }
body[theme="dark"] .wrong-answer { background-color: #7f1d1d; border-color: #ef4444; color: #fecaca; }

/* NORMAL (Unselected) answer style. This is now fixed. */
.normal-answer {
    background-color: white !important;
    border-color: #d1d5db !important;    
    color: #111827 !important; /* Force dark grey/black text */
}


/* --- STYLE FOR MULTI-SELECT PILLS --- */
.stMultiSelect [data-baseweb="tag"] {
    background-color: #BDE0FE !important; 
    color: #003366 !important; 
}

/* Make sliders in part 1 smaller */
div[data-testid="stSlider"] {
    max-width: 250px;
}

/* --- THEME-AWARE REFERENCE BOX STYLE (CORRECTED) --- */
.reference-box {
    background-color: #FFFBEB; /* Light Yellow for Light Theme by default */
    border: 1px solid #eab308; /* A visible amber border for both themes */
    border-radius: 0.5rem;
    padding: 1rem 1.5rem;
    margin-top: 1.5rem;
}
/* Override for Dark Theme */
body[theme="dark"] .reference-box {
    background-color: var(--secondary-background-color);
}

.reference-box h3 {
    margin-top: 0;
    padding-bottom: 0.5rem;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
}
.reference-box ul {
    padding-left: 20px;
    margin: 0;
}
.reference-box li {
    margin-bottom: 0.5rem;
}

</style>

<script>
    // Automatically scroll to top on page rerun
    window.parent.document.querySelector('section.main').scrollTo(0, 0);
</script>
""", unsafe_allow_html=True)


# --- Central Dictionary for All Definitions ---
DEFINITIONS = {
    # Personalities
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

    # Writing Styles
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
    
    # Applications
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


# --- Helper Functions ---
@st.cache_data
def get_video_orientation(path):
    """
    Reads a video file and returns its orientation ('portrait' or 'landscape').
    """
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return "landscape"
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        cap.release()
        if height > width:
            return "portrait"
        else:
            return "landscape"
    except Exception:
        return "landscape"

@st.cache_data

def listen_for_keyboard():
    """Renders a JavaScript component to listen for Enter/ArrowRight and trigger a rerun."""
    st.components.v1.html(
        """
        <script>
        // Set a flag to ensure the event listener is only attached once.
        if (!window.keyboardListenerAttached) {
            window.addEventListener('keydown', function(event) {
                // Check if the pressed key is Enter or ArrowRight.
                if (event.key === 'Enter' || event.key === 'ArrowRight') {
                    // Send a message to the Streamlit app to signal a key press.
                    window.parent.postMessage({
                        isStreamlitMessage: true,
                        type: 'SET_QUERY_PARAMS',
                        queryParams: {'key_press': Date.now()}
                    }, '*');
                }
            });
            window.keyboardListenerAttached = true;
        }
        </script>
        """,
        height=0,
        width=0,
    )

def load_data():
    """Loads all data from external JSON files."""
    data = {}
    if not os.path.exists(INSTRUCTIONS_PATH):
        st.error(f"Error: Instructions file not found at '{INSTRUCTIONS_PATH}'.")
        return None
    with open(INSTRUCTIONS_PATH, 'r', encoding='utf-8') as f:
        data['instructions'] = json.load(f)
    if not os.path.exists(QUIZ_DATA_PATH):
        st.error(f"Error: Quiz data file not found at '{QUIZ_DATA_PATH}'.")
        return None
    with open(QUIZ_DATA_PATH, 'r', encoding='utf-8') as f:
        data['quiz'] = json.load(f)
    if not os.path.exists(STUDY_DATA_PATH):
        st.error(f"Error: Study data file not found at '{STUDY_DATA_PATH}'.")
        return None
    with open(STUDY_DATA_PATH, 'r', encoding='utf-8') as f:
        study_data = json.load(f)
    if not os.path.exists(QUESTIONS_DATA_PATH):
        st.error(f"Error: Questions file not found at '{QUESTIONS_DATA_PATH}'.")
        return None
    with open(QUESTIONS_DATA_PATH, 'r', encoding='utf-8') as f:
        data['questions'] = json.load(f)
    for part in study_data.values():
        for item in part:
            if os.path.exists(item['video_path']):
                item['orientation'] = get_video_orientation(item['video_path'])
            else:
                item['orientation'] = 'landscape'
    data['study'] = study_data
    for item in data['quiz'].values():
        for video_item in item:
            if not os.path.exists(video_item["video_path"]):
                st.error(f"Error: Quiz video file not found at '{video_item['video_path']}'.")
                return None
    for part in data['study'].values():
        for item in part:
            if not os.path.exists(item["video_path"]):
                st.error(f"Error: Study video file not found at '{item['video_path']}'.")
                return None
    if not os.path.exists(INTRO_VIDEO_PATH):
        st.error(f"Error: Intro video not found at '{INTRO_VIDEO_PATH}'.")
        return None
    return data

def save_response(email, age, gender, video_data, caption_data, choice, study_phase, question_text, was_correct=None):
    """Saves a single response to the connected Google Sheet."""
    # The connection is now established only when it's first needed.
    worksheet = connect_to_gsheet() 
    if worksheet is None:
        st.error("Connection to response sheet failed. Data not saved.")
        return
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        response_data = [email, age, str(gender), timestamp, study_phase, video_data.get('video_id', 'N/A'), caption_data.get('caption_id') or caption_data.get('comparison_id') or caption_data.get('change_id'), question_text, str(choice), str(was_correct) if was_correct is not None else 'N/A', 1 if study_phase == 'quiz' else 'N/A']
        if len(worksheet.get_all_values()) == 0:
             header = ['email', 'age', 'gender', 'timestamp', 'study_phase', 'video_id', 'sample_id', 'question_text', 'user_choice', 'was_correct', 'attempts_taken']
             worksheet.append_row(header)
        worksheet.append_row(response_data)
    except Exception as e:
        st.error(f"Failed to write to Google Sheet: {e}")


def go_to_next_quiz_question():
    with st.spinner("Saving your answer..."): # SPINNER ADDED TO MANAGE LAG
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
        
        # REVERTED to original save_response function
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
        desc = DEFINITIONS[option_name]
        return f"{option_name} ({desc})"
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

# --- Page 1-6 (Demographics, Quiz, Instructions) ---
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
        # NEW: Added the hyperlinked guide below the info box
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

    # --- State Management for Sequential Reveal ---
    view_state_key = f'view_state_{sample_id}'
    if view_state_key not in st.session_state:
        st.session_state[view_state_key] = {'step': 1}
    
    current_step = st.session_state[view_state_key]['step']

    def stream_text(text):
        for word in text.split(" "):
            yield word + " "
            time.sleep(0.05)

    # --- DYNAMIC QUIZ TITLE LOGIC ---
    if "Tone Identification" in current_part_key:
        display_title = f"{sample.get('category', 'Tone').title()} Identification"
    elif "Tone Controllability" in current_part_key:
        display_title = f"{sample.get('category', 'Tone').title()} Comparison"
    else:
        display_title = re.sub(r'Part \d+: ', '', current_part_key)
    st.header(display_title)
    
    st.progress(current_index / len(questions_for_part), text=f"Question: {current_index + 1}/{len(questions_for_part)}")

    col1, col2 = st.columns([1.2, 1.5])

    with col1:
        st.video(sample['video_path'], autoplay=False)
        
        if current_step == 1:
            if st.button("Proceed to Summary"):
                st.session_state[view_state_key]['step'] = 2
                st.rerun()
        
        if current_step >= 2 and "video_summary" in sample:
            st.subheader("Video Summary")
            if st.session_state[view_state_key].get('summary_typed', False):
                st.info(sample["video_summary"])
            else:
                with st.empty():
                    st.write_stream(stream_text(sample["video_summary"]))
                st.session_state[view_state_key]['summary_typed'] = True
            
            if current_step == 2:
                if st.button("Proceed to Caption"):
                    st.session_state[view_state_key]['step'] = 3
                    st.rerun()

    with col2:
        question_data = sample["questions"][st.session_state.current_rating_question_index] if "Caption Quality" in current_part_key else sample
        
        if current_step >= 3:
            if "Tone Controllability" in current_part_key:
                st.markdown(f"""<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{sample["caption_A"]}</p></div>""", unsafe_allow_html=True)
                st.markdown(f"""<div class="comparison-caption-box" style="margin-top:0.5rem;"><strong>Caption B</strong><p class="caption-text">{sample["caption_B"]}</p></div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="comparison-caption-box"><strong>Caption</strong><p class="caption-text">{sample["caption"]}</p></div>""", unsafe_allow_html=True)
            
            if current_step == 3:
                if st.button("Show Questions"):
                    st.session_state[view_state_key]['step'] = 4
                    st.rerun()

        if current_step >= 4:
            if st.session_state.show_feedback:
                user_choice = st.session_state.last_choice
                correct_answer = question_data.get('correct_answer')
                if not isinstance(user_choice, list): user_choice = [user_choice]
                if not isinstance(correct_answer, list): correct_answer = [correct_answer]
                st.write("**Your Answer vs Correct Answer:**")
                for option in question_data['options']:
                    is_correct_option = option in correct_answer
                    is_selected_option = option in user_choice
                    if is_correct_option: st.markdown(f'<div class="feedback-option correct-answer"><strong>{option} (Correct Answer)</strong></div>', unsafe_allow_html=True)
                    elif is_selected_option: st.markdown(f'<div class="feedback-option wrong-answer">{option} (Your selection)</div>', unsafe_allow_html=True)
                    else: st.markdown(f'<div class="feedback-option normal-answer">{option}</div>', unsafe_allow_html=True)
                st.info(f"**Explanation:** {question_data['explanation']}")
                
                if st.button("Next Question"):
                    go_to_next_quiz_question()
                    st.session_state.pop(view_state_key, None) 
                    st.rerun()
            else:
                # --- CORRECTED QUESTION LOGIC ---
                question_text = ""
                if "Tone Controllability" in current_part_key:
                     question_text = f"Has the author's <b class='highlight-trait'>{sample['tone_to_compare']}</b> writing style <b class='highlight-trait'>{sample['comparison_type']}</b> from Caption A to B?"
                elif "Caption Quality" in current_part_key:
                    # This new condition fixes the bug for Part 3
                    question_text = question_data["question_text"]
                elif question_data.get("question_type") == "multi":
                    question_text = "Identify 2 dominant personality traits projected by the captioner"
                else:
                    question_text = f"Identify the most dominant {sample.get('category', 'tone').lower()} projected by the captioner"

                st.markdown(f'<div class="quiz-question-box"><strong>Question:</strong><span class="question-text-part">{question_text}</span></div>', unsafe_allow_html=True)
                
                with st.form("quiz_form"):
                    choice = None
                    if question_data.get("question_type") == "multi":
                        st.write("Select all that apply:")
                        selected_options = []
                        for option in question_data['options']:
                            if st.checkbox(option, key=f"cb_{current_index}_{option}"):
                                selected_options.append(option)
                        choice = selected_options
                    else:
                        choice = st.radio("Select one option:", question_data['options'], key=f"radio_{current_index}", index=None, format_func=format_options_with_info)

                    if st.form_submit_button("Submit Answer"):
                        if not choice: 
                            st.error("Please select an option.")
                        else:
                            st.session_state.last_choice = choice
                            correct_answer = question_data.get('correct_answer')
                            is_correct = (set(choice) == set(correct_answer)) if isinstance(correct_answer, list) else (choice == correct_answer)
                            st.session_state.is_correct = is_correct
                            if is_correct: st.session_state.score += 1
                            st.session_state.show_feedback = True
                            st.rerun()


elif st.session_state.page == 'quiz_results':
    total_scorable_questions = 0
    quiz_data = st.session_state.all_data['quiz']
    for part_name, questions_list in quiz_data.items():
        if "Caption Quality" in part_name:
            for item in questions_list:
                total_scorable_questions += len(item.get("questions", []))
        else:
            total_scorable_questions += len(questions_list)
    passing_score = 5
    st.header(f"Your Final Score: {st.session_state.score} / {total_scorable_questions}")
    if st.session_state.score >= passing_score:
        st.success("**Status: Passed**")
        if st.button("Proceed to User Study"):
            st.session_state.page = 'user_study_main'
            st.rerun()
    else:
        st.error("**Status: Failed**")
        st.markdown(f"Unfortunately, you did not meet the passing score of {passing_score}. You can try again.")
        st.button("Take Quiz Again", on_click=restart_quiz)

# --- Page 7: The Main User Study ---
elif st.session_state.page == 'user_study_main':
    if not st.session_state.all_data:
        st.error("Data could not be loaded. Please check file paths and permissions.")
        st.stop()

    # Initialize a key press tracker in session state
    if 'last_key_press' not in st.session_state:
        st.session_state.last_key_press = None

    listen_for_keyboard() # Call the new keyboard listener function

    # Helper function for typewriter effect
    def stream_text(text):
        for word in text.split(" "):
            yield word + " "
            time.sleep(0.05)

    with st.sidebar:
        st.header("Study Sections")
        st.button("Part 1: Caption Rating", on_click=jump_to_study_part, args=(1,), use_container_width=True)
        st.button("Part 2: Caption Comparison", on_click=jump_to_study_part, args=(2,), use_container_width=True)
        st.button("Part 3: Tone Intensity Change", on_click=jump_to_study_part, args=(3,), use_container_width=True)

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
        if view_state_key not in st.session_state:
            st.session_state[view_state_key] = {'step': 1, 'responses': {}}
        
        current_step = st.session_state[view_state_key]['step']

        # --- Keyboard Navigation Logic ---
        query_params = st.query_params
        if "key_press" in query_params:
            press_time = query_params.get("key_press")
            if press_time and press_time != st.session_state.last_key_press:
                st.session_state.last_key_press = press_time
                # Advance to the next step if we are not at the final question
                if st.session_state[view_state_key]['step'] < 8: # 3 setup steps + 5 questions
                    st.session_state[view_state_key]['step'] += 1
                    st.rerun()

        col1, col2 = st.columns([1, 1.8])
        
        with col1:
            st.video(current_video['video_path'], autoplay=False)
            if current_step == 1:
                st.info("Watch the video, then press Enter or → to continue.")

            if current_step >= 2:
                st.subheader("Video Summary")
                if st.session_state[view_state_key].get('summary_typed', False):
                    st.info(current_video["video_summary"])
                else:
                    with st.empty():
                        st.write_stream(stream_text(current_video["video_summary"]))
                    st.session_state[view_state_key]['summary_typed'] = True
                
                if current_step == 2:
                    st.info("Read the summary, then press Enter or → to continue.")

        with col2:
            terms_to_define = set()
            
            if current_step >= 3:
                colors = ["#FFEEEE", "#EBF5FF", "#E6F7EA"]
                highlight_color = colors[caption_idx % len(colors)]
                caption_box_style = f"background-color: {highlight_color};"
                caption_text_html = f'''<div class="part1-caption-box" style="{caption_box_style}"><strong>Caption:</strong><p class="caption-text">{current_caption["text"]}</p></div>'''
                st.markdown(caption_text_html, unsafe_allow_html=True)
                
                if current_step == 3:
                    st.info("Read the caption, then press Enter or → to see the questions.")

            if current_step >= 4:
                control_scores = current_caption.get("control_scores", {})
                personality_traits = list(control_scores.get("personality", {}).keys())
                style_traits = list(control_scores.get("writing_style", {}).keys())
                application_text = current_caption.get("application", "the intended application")
                
                terms_to_define.update(personality_traits)
                terms_to_define.update(style_traits)
                terms_to_define.add(application_text)

                personality_str = ", ".join(f"<b class='highlight-trait'>{p}</b>" for p in personality_traits)
                style_str = ", ".join(f"<b class='highlight-trait'>{s}</b>" for s in style_traits)
                
                q_templates = st.session_state.all_data['questions']['part1_questions']
                questions_to_ask_raw = [q for q in q_templates if q['id'] != 'overall_relevance']
                questions_to_ask = [
                    {"id": questions_to_ask_raw[0]["id"], "text": questions_to_ask_raw[0]["text"].format(personality_str)},
                    {"id": questions_to_ask_raw[1]["id"], "text": questions_to_ask_raw[1]["text"].format(style_str)},
                    {"id": questions_to_ask_raw[2]["id"], "text": questions_to_ask_raw[2]["text"]},
                    {"id": questions_to_ask_raw[3]["id"], "text": questions_to_ask_raw[3]["text"].format(f"<b class='highlight-trait'>{application_text}</b>")},
                    {"id": questions_to_ask_raw[4]["id"], "text": questions_to_ask_raw[4]["text"]}
                ]

                options_map = {
                    "personality_relevance": ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"],
                    "style_relevance": ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"],
                    "factual_consistency": ["Contradicts", "Inaccurate", "Partially", "Mostly Accurate", "Accurate"],
                    "usefulness": ["Not at all", "Slightly", "Moderately", "Very", "Extremely"],
                    "human_likeness": ["Robotic", "Unnatural", "Moderate", "Very Human-like", "Natural"]
                }
                
                num_questions_to_show = current_step - 3
                responses = st.session_state[view_state_key]['responses']

                row1_cols = st.columns(3)
                with row1_cols[0]:
                    if num_questions_to_show >= 1:
                        q = questions_to_ask[0]
                        slider_options = options_map[q['id']]
                        st.markdown(f"<div class='slider-label'><strong>1. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.select_slider(q['id'], options=slider_options, value=responses.get(q['id'], slider_options[2]), key=f"ss_{q['id']}_{view_state_key}", label_visibility="collapsed")
                
                with row1_cols[1]:
                    if num_questions_to_show >= 2:
                        q = questions_to_ask[1]
                        slider_options = options_map[q['id']]
                        st.markdown(f"<div class='slider-label'><strong>2. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.select_slider(q['id'], options=slider_options, value=responses.get(q['id'], slider_options[2]), key=f"ss_{q['id']}_{view_state_key}", label_visibility="collapsed")
                
                with row1_cols[2]:
                    if num_questions_to_show >= 3:
                        q = questions_to_ask[2]
                        slider_options = options_map[q['id']]
                        st.markdown(f"<div class='slider-label'><strong>3. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.select_slider(q['id'], options=slider_options, value=responses.get(q['id'], slider_options[2]), key=f"ss_{q['id']}_{view_state_key}", label_visibility="collapsed")

                row2_cols = st.columns(3)
                with row2_cols[0]:
                    if num_questions_to_show >= 4:
                        q = questions_to_ask[3]
                        slider_options = options_map[q['id']]
                        st.markdown(f"<div class='slider-label'><strong>4. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.select_slider(q['id'], options=slider_options, value=responses.get(q['id'], slider_options[2]), key=f"ss_{q['id']}_{view_state_key}", label_visibility="collapsed")
                
                with row2_cols[1]:
                    if num_questions_to_show >= 5:
                        q = questions_to_ask[4]
                        slider_options = options_map[q['id']]
                        st.markdown(f"<div class='slider-label'><strong>5. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.select_slider(q['id'], options=slider_options, value=responses.get(q['id'], slider_options[2]), key=f"ss_{q['id']}_{view_state_key}", label_visibility="collapsed")
                
                if num_questions_to_show < len(questions_to_ask):
                    st.info(f"Press Enter or → to show the next question ({num_questions_to_show + 1}/{len(questions_to_ask)})")
                else: 
                    if st.button("Submit Ratings"):
                        with st.spinner("Saving your ratings..."):
                            for q_id, choice_text in responses.items():
                                full_q_text = next((q['text'] for q in questions_to_ask if q['id'] == q_id), "N/A")
                                save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_video, current_caption, choice_text, 'user_study_part1', full_q_text)
                        
                        st.session_state.pop(view_state_key, None)
                        
                        if st.session_state.current_caption_index < len(current_video['captions']) - 1:
                            st.session_state.current_caption_index += 1
                        else:
                            st.session_state.current_video_index += 1
                            st.session_state.current_caption_index = 0
                        st.rerun()

                reference_html = '<div class="reference-box">'
                reference_html += "<h3>Reference</h3><ul>"
                for term in sorted(list(terms_to_define)):
                    desc = DEFINITIONS.get(term)
                    if desc:
                        reference_html += f"<li><strong>{term}:</strong> {desc}</li>"
                reference_html += "</ul></div>"
                st.markdown(reference_html, unsafe_allow_html=True)

                
                                
    elif st.session_state.study_part == 2:
        st.header("Which caption is better?")
        all_comparisons = st.session_state.all_data['study']['part2_comparisons']
        comp_idx = st.session_state.current_comparison_index
        if comp_idx >= len(all_comparisons):
            st.session_state.study_part = 3; st.rerun()
        current_comp = all_comparisons[comp_idx]
        col1, col2 = st.columns([1, 1.8])
        
        terms_to_define = set()

        with col1:
            if current_comp.get("orientation") == "portrait":
                _ , vid_col, _ = st.columns([1, 3, 1])
                with vid_col:
                    st.video(current_comp['video_path'], autoplay=True, muted=True)
            else:
                st.video(current_comp['video_path'], autoplay=True, muted=True)
            st.caption("Video is muted for autoplay.")
            st.subheader("Video Summary"); st.info(current_comp["video_summary"])
        with col2:
            caption_a_html = f"""<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_comp["caption_A"]}</p></div>"""
            caption_b_html = f"""<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_comp["caption_B"]}</p></div>"""
            st.markdown(caption_a_html, unsafe_allow_html=True)
            st.markdown(caption_b_html, unsafe_allow_html=True)
            
            control_scores = current_comp.get("control_scores", {})
            personality_traits = list(control_scores.get("personality", {}).keys())
            style_traits = list(control_scores.get("writing_style", {}).keys())
            
            terms_to_define.update(personality_traits)
            terms_to_define.update(style_traits)

            personality_str = ", ".join(f"<b class='highlight-trait'>{p}</b>" for p in personality_traits)
            style_str = ", ".join(f"<b class='highlight-trait'>{s}</b>" for s in style_traits)

            with st.form(key=f"study_form_comparison_{comp_idx}"):
                q_templates = st.session_state.all_data['questions']['part2_questions']
                part2_questions = [
                    {"id": q_templates[0]["id"], "text": q_templates[0]["text"].format(personality_str)},
                    {"id": q_templates[1]["id"], "text": q_templates[1]["text"].format(style_str)},
                    {"id": q_templates[2]["id"], "text": q_templates[2]["text"]},
                    {"id": q_templates[3]["id"], "text": q_templates[3]["text"]}
                ]
                options = ["Caption A", "Caption B", "Both A and B", "Neither A nor B"]
                responses = {}
                question_cols = st.columns(4)
                for i, q in enumerate(part2_questions):
                    with question_cols[i]:
                        st.markdown(f"<div class='slider-label'><strong>{i+1}. {q['text']}</strong></div>", unsafe_allow_html=True)
                        responses[q['id']] = st.radio(q['text'], options, index=None, label_visibility="collapsed", key=f"{current_comp['comparison_id']}_{q['id']}")
                
                submitted = st.form_submit_button("Submit Comparison")

            if submitted:
                if any(choice is None for choice in responses.values()):
                    st.error("Please answer all four questions.")
                else:
                    with st.spinner("Saving your responses..."):
                        for q_id, choice in responses.items():
                            question_text = next((q['text'] for q in part2_questions if q['id'] == q_id), "N/A")
                            save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_comp, current_comp, choice, 'user_study_part2', question_text)
                    st.session_state.current_comparison_index += 1
                    st.rerun()
            
            reference_html = '<div class="reference-box">'
            reference_html += "<h3>Reference</h3><ul>"
            for term in sorted(list(terms_to_define)):
                desc = DEFINITIONS.get(term)
                if desc:
                    reference_html += f"<li><strong>{term}:</strong> {desc}</li>"
            reference_html += "</ul></div>"
            st.markdown(reference_html, unsafe_allow_html=True)

    elif st.session_state.study_part == 3:
        all_changes = st.session_state.all_data['study']['part3_intensity_change']
        change_idx = st.session_state.current_change_index
        if change_idx >= len(all_changes):
            st.session_state.page = 'final_thank_you'; st.rerun()
        current_change = all_changes[change_idx]
        field_to_change = current_change['field_to_change']
        field_type = list(field_to_change.keys())[0]
        dynamic_title = f"{field_type.replace('_', ' ').title()} Comparison"
        st.header(dynamic_title)
        col1, col2 = st.columns([1, 1.8])

        terms_to_define = set()

        with col1:
            if current_change.get("orientation") == "portrait":
                _ , vid_col, _ = st.columns([1, 3, 1])
                with vid_col:
                    st.video(current_change['video_path'], autoplay=True, muted=True)
            else:
                st.video(current_change['video_path'], autoplay=True, muted=True)
            st.caption("Video is muted for autoplay.")
            st.subheader("Video Summary"); st.info(current_change["video_summary"])
        with col2:
            caption_a_html = f"""<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_change["caption_A"]}</p></div>"""
            caption_b_html = f"""<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_change["caption_B"]}</p></div>"""
            st.markdown(caption_a_html, unsafe_allow_html=True)
            st.markdown(caption_b_html, unsafe_allow_html=True)
            
            trait = field_to_change[field_type]
            terms_to_define.add(trait)
            
            with st.form(key=f"study_form_change_{change_idx}"):
                change_type = current_change['change_type']
                highlighted_trait = f"<b class='highlight-trait'>{trait}</b>"
                if field_type == 'personality':
                    dynamic_question = f"Has the author's {highlighted_trait} personality {change_type} from Caption A to B?"
                elif field_type == 'writing_style':
                    dynamic_question = f"Has the author's {highlighted_trait} writing style {change_type} from Caption A to B?"
                else:
                    st.error(f"FATAL DATA ERROR: An invalid 'field_type' of '{field_type}' was found in study_data.json. It must be 'personality' or 'writing_style'.")
                    st.stop()
                q_cols = st.columns(2)
                with q_cols[0]:
                    st.markdown(f"**1. {dynamic_question}**", unsafe_allow_html=True)
                    choice1 = st.radio("q1_label", ["Yes", "No"], index=None, horizontal=True, key=f"{current_change['change_id']}_q1", label_visibility="collapsed")
                with q_cols[1]:
                    q2_text = "Is the core factual content consistent across both captions?"
                    st.markdown(f"**2. {q2_text}**")
                    choice2 = st.radio("q2_label", ["Yes", "No"], index=None, horizontal=True, key=f"{current_change['change_id']}_q2", label_visibility="collapsed")
                
                submitted = st.form_submit_button("Submit Answers")
            
            if submitted:
                if choice1 is None or choice2 is None:
                    st.error("Please answer both questions.")
                else:
                    with st.spinner("Saving your responses..."):
                        save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice1, 'user_study_part3', dynamic_question)
                        save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice2, 'user_study_part3', q2_text)
                    st.session_state.current_change_index += 1
                    st.rerun()

            reference_html = '<div class="reference-box">'
            reference_html += "<h3>Reference</h3><ul>"
            for term in sorted(list(terms_to_define)):
                desc = DEFINITIONS.get(term)
                if desc:
                    reference_html += f"<li><strong>{term}:</strong> {desc}</li>"
            reference_html += "</ul></div>"
            st.markdown(reference_html, unsafe_allow_html=True)

elif st.session_state.page == 'final_thank_you':
    st.title("Study Complete! Thank You! ")
    st.success("You have successfully completed all parts of the study. We sincerely appreciate your time and valuable contribution to our research!")