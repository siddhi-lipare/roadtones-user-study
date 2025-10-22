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
import random
from google.oauth2.service_account import Credentials
from streamlit_js_eval import streamlit_js_eval

# --- Configuration ---
INTRO_VIDEO_PATH = "media/start_video_slower.mp4"
STUDY_DATA_PATH = "study_data.json" # Use the updated file if you saved it differently
QUIZ_DATA_PATH = "quiz_data.json"
INSTRUCTIONS_PATH = "instructions.json"
QUESTIONS_DATA_PATH = "questions.json" # Use the updated file
DEFINITIONS_PATH = "definitions.json"
LOCAL_BACKUP_FILE = "responses_backup.jsonl"

# --- JAVASCRIPT FOR ANIMATION ---
JS_ANIMATION_RESET = """
    const elements = window.parent.document.querySelectorAll('.new-caption-highlight');
    elements.forEach(el => {
        el.style.animation = 'none';
        el.offsetHeight; /* trigger reflow */
        el.style.animation = null;
    });
"""

# --- GOOGLE SHEETS & HELPERS ---
@st.cache_resource
def connect_to_gsheet():
    """Connects to the Google Sheet using Streamlit secrets."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https.www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open("roadtones-streamlit-userstudy-responses")
        return spreadsheet.sheet1
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}") # More specific error
        return None

def save_response_locally(response_dict):
    """Saves a response dictionary to a local JSONL file as a fallback."""
    try:
        with open(LOCAL_BACKUP_FILE, "a", encoding='utf-8') as f: # Added encoding
            f.write(json.dumps(response_dict) + "\n")
        return True
    except Exception as e:
        st.error(f"Critical Error: Could not save response to local backup file. {e}")
        return False

def save_response(email, age, gender, video_data, caption_data, choice, study_phase, question_text, was_correct=None):
    """Saves a response to Google Sheets, with a local JSONL fallback."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    # Clean question text for saving (remove HTML)
    cleaned_question_text = re.sub('<[^<]+?>', '', question_text)
    response_dict = {
        'email': email, 'age': age, 'gender': str(gender), 'timestamp': timestamp,
        'study_phase': study_phase, 'video_id': video_data.get('video_id', 'N/A'),
        'sample_id': caption_data.get('caption_id') or caption_data.get('comparison_id') or caption_data.get('change_id') or caption_data.get('sample_id'),
        'question_text': cleaned_question_text, 'user_choice': str(choice),
        'was_correct': str(was_correct) if was_correct is not None else 'N/A',
        'attempts_taken': 1 if study_phase == 'quiz' else 'N/A'
    }

    worksheet = connect_to_gsheet()
    if worksheet:
        try:
            # Check if worksheet is empty to add header row
            header = worksheet.row_values(1) if worksheet.row_count > 0 else []
            if not header:
                 worksheet.append_row(list(response_dict.keys()))
            worksheet.append_row(list(response_dict.values()))
            return True
        except Exception as e:
            st.warning(f"Could not save to Google Sheets ({e}). Saving a local backup.")
            return save_response_locally(response_dict)
    else:
        st.warning("Could not connect to Google Sheets. Saving a local backup.")
        return save_response_locally(response_dict)


@st.cache_data
def get_video_metadata(path):
    """Reads a video file and returns its orientation and duration."""
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            st.warning(f"Warning: Could not open video file {path}. Using defaults.")
            return {"orientation": "landscape", "duration": 10}
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        orientation = "portrait" if height > width else "landscape"
        duration = math.ceil(frame_count / fps) if fps and frame_count and fps > 0 and frame_count > 0 else 10 # Added checks
        return {"orientation": orientation, "duration": duration}
    except Exception as e:
        st.warning(f"Warning: Error getting metadata for {path}: {e}. Using defaults.")
        return {"orientation": "landscape", "duration": 10}

@st.cache_data
def load_data():
    """Loads all data from external JSON files and determines video metadata."""
    data = {}
    required_files = {
        "instructions": INSTRUCTIONS_PATH, "quiz": QUIZ_DATA_PATH,
        "study": STUDY_DATA_PATH, "questions": QUESTIONS_DATA_PATH,
        "definitions": DEFINITIONS_PATH
    }
    all_files_found = True
    for key, path in required_files.items():
        if not os.path.exists(path):
            st.error(f"Error: Required data file not found at '{path}'.")
            all_files_found = False
            continue # Continue checking other files
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data[key] = json.load(f)
        except json.JSONDecodeError as e:
            st.error(f"Error decoding JSON from {path}: {e}")
            all_files_found = False
        except Exception as e:
             st.error(f"Error loading {path}: {e}")
             all_files_found = False

    if not all_files_found:
         st.stop() # Stop execution if essential files are missing or corrupted

    if 'definitions' in data:
        nested_definitions = data.pop('definitions')
        flat_definitions = {}
        flat_definitions.update(nested_definitions.get('tones', {}))
        flat_definitions.update(nested_definitions.get('writing_styles', {})) # Keep original key
        flat_definitions.update(nested_definitions.get('applications', {}))
        data['definitions'] = flat_definitions
    else:
        st.warning("Definitions file might be missing or empty.")
        data['definitions'] = {}

    if not os.path.exists(INTRO_VIDEO_PATH):
        st.error(f"Error: Intro video not found at '{INTRO_VIDEO_PATH}'.")
        st.stop()

    # Add video metadata to study data
    if 'study' in data:
        for part_key in data['study']:
            if isinstance(data['study'][part_key], list):
                for item in data['study'][part_key]:
                    video_path = item.get('video_path')
                    if video_path and os.path.exists(video_path):
                        metadata = get_video_metadata(video_path)
                        item['orientation'] = metadata['orientation']
                        item['duration'] = metadata['duration']
                    else:
                        item['orientation'] = 'landscape'
                        item['duration'] = 10

    # Add video metadata to quiz data
    if 'quiz' in data:
        for part_key in data['quiz']:
            if isinstance(data['quiz'][part_key], list):
                for item in data['quiz'][part_key]:
                    video_path = item.get('video_path')
                    if video_path and os.path.exists(video_path):
                        metadata = get_video_metadata(video_path)
                        item['orientation'] = metadata['orientation']
                        item['duration'] = metadata['duration']
                    else:
                        item['orientation'] = 'landscape'
                        item['duration'] = 10
    return data

# --- UI & STYLING ---
st.set_page_config(layout="wide", page_title="Tone-controlled Video Captioning")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&display=swap');
@keyframes highlight-new { 0% { border-color: transparent; box-shadow: none; } 25% { border-color: #facc15; box-shadow: 0 0 8px #facc15; } 75% { border-color: #facc15; box-shadow: 0 0 8px #facc15; } 100% { border-color: transparent; box-shadow: none; } }
.part1-caption-box { border-radius: 10px; padding: 1rem 1.5rem; margin-bottom: 0.5rem; border: 2px solid transparent; transition: border-color 0.3s ease; }
.new-caption-highlight { animation: highlight-new 1.5s ease-out forwards; } /* This is the yellow highlight */
.slider-label { min-height: 80px; margin-bottom: 0; display: flex; align-items: center;} /* Use min-height and flex for alignment */
.highlight-trait { color: #4f46e5; font-weight: 600; } /* This is the indigo blue highlight */
.caption-text { font-family: 'Inter', sans-serif; font-weight: 500; font-size: 19px !important; line-height: 1.6; }
.part1-caption-box strong { font-size: 18px; font-family: 'Inter', sans-serif; font-weight: 600; color: #111827 !important; }
.part1-caption-box .caption-text { margin: 0.5em 0 0 0; color: #111827 !important; }
.comparison-caption-box { background-color: var(--secondary-background-color); border-left: 5px solid #6366f1; padding: 1rem 1.5rem; margin: 1rem 0; border-radius: 0.25rem; }
.comparison-caption-box strong { font-size: 18px; font-family: 'Inter', sans-serif; font-weight: 600; }
.quiz-question-box { background-color: #F0F2F6; padding: 1rem 1.5rem; border: 1px solid var(--gray-300); border-bottom: none; border-radius: 0.5rem 0.5rem 0 0; }
body[theme="dark"] .quiz-question-box { background-color: var(--secondary-background-color); }
.quiz-question-box > strong { font-family: 'Inter', sans-serif; font-size: 18px; font-weight: 600; }
.quiz-question-box .question-text-part { font-family: 'Inter', sans-serif; font-size: 19px; font-weight: 500; margin-left: 0.5em; }
[data-testid="stForm"] { border: 1px solid var(--gray-300); border-top: none; border-radius: 0 0 0.5rem 0.5rem; padding: 0.5rem 1.5rem; margin-top: 0 !important; }
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

/* --- Title font consistency --- */
h2 {
    font-size: 1.75rem !important;
    font-weight: 600 !important;
}

/* --- User Study Question Font Size --- */
.slider-label strong, [data-testid="stRadio"] label span {
    font-size: 1.1rem !important;
    font-weight: 600 !important; /* Make radio labels bold too */
}
.part3-question-text {
    font-size: 1.1rem !important;
    font-weight: 600;
    padding-bottom: 0.5rem;
}

/* --- CUSTOM BUTTON STYLING --- */
div[data-testid="stButton"] > button, .stForm [data-testid="stButton"] > button {
    background-color: #FAFAFA; /* Very light grey */
    color: #1F2937; /* Dark grey text for readability */
    border: 1px solid #D1D5DB; /* Light grey border */
    transition: background-color 0.2s ease, border-color 0.2s ease;
}
div[data-testid="stButton"] > button:hover, .stForm [data-testid="stButton"] > button:hover {
    background-color: #F3F4F6; /* Slightly darker grey on hover */
    border-color: #9CA3AF;
}
body[theme="dark"] div[data-testid="stButton"] > button,
body[theme="dark"] .stForm [data-testid="stButton"] > button {
    background-color: #262730; /* Dark background */
    color: #FAFAFA; /* Light text */
    border: 1px solid #4B5563; /* Grey border for dark mode */
}
body[theme="dark"] div[data-testid="stButton"] > button:hover,
body[theme="dark"] .stForm [data-testid="stButton"] > button:hover {
    background-color: #374151; /* Lighter background on hover for dark mode */
    border-color: #6B7280;
}
</style>
""", unsafe_allow_html=True)

# --- NAVIGATION & STATE HELPERS ---
def go_to_previous_step(view_key, decrement=1):
    if view_key in st.session_state:
        current_step = st.session_state[view_key].get('step', 1)
        st.session_state[view_key]['step'] = max(1, current_step - decrement) # Ensure step doesn't go below 1
        st.session_state[view_key].pop('comp_feedback', None)
        st.session_state[view_key].pop('comp_choice', None)
        st.session_state.pop('show_feedback', None) # Clear quiz feedback flag
        # Reset interaction state only if going back significantly (e.g., before questions)
        if st.session_state[view_key]['step'] < 6:
            st.session_state[view_key]['interacted'] = {qid: False for qid in st.session_state[view_key].get('interacted', {})}
        st.rerun()

def go_to_previous_page(target_page):
    st.session_state.page = target_page
    st.rerun()

def go_to_previous_item(part_key, view_key_to_pop):
    """Navigates to the previous item (caption/comparison) in the main study."""
    st.session_state.pop(view_key_to_pop, None) # Pop current view state

    if part_key == 'part1':
        if st.session_state.current_caption_index > 0:
            st.session_state.current_caption_index -= 1
        elif st.session_state.current_video_index > 0:
            st.session_state.current_video_index -= 1
            prev_video_captions = st.session_state.all_data['study']['part1_ratings'][st.session_state.current_video_index]['captions']
            st.session_state.current_caption_index = len(prev_video_captions) - 1
    elif part_key == 'part2':
        if st.session_state.current_comparison_index > 0:
            st.session_state.current_comparison_index -= 1
    elif part_key == 'part3':
        if st.session_state.current_change_index > 0:
            st.session_state.current_change_index -= 1
    st.rerun()

def skip_to_questions(view_key, summary_key=None):
    """Skips video, summary, and comprehension quiz, jumping directly to questions."""
    if view_key in st.session_state:
        st.session_state[view_key]['step'] = 6
        st.session_state[view_key]['summary_typed'] = True
        if summary_key:
            st.session_state[summary_key] = True
        st.session_state[view_key]['comp_feedback'] = False

        view_id_parts = view_key.split('_')
        view_id = view_id_parts[-1] if len(view_id_parts) > 1 else view_key # Handle different key formats

        # Clear relevant timer flags
        st.session_state.pop(f"timer_finished_{view_id}", None)
        st.session_state.pop(f"timer_finished_quiz_{view_id}", None)
        st.session_state.pop(f"timer_finished_p1_{view_id}", None)
        st.session_state.pop(f"timer_finished_p2_{view_id}", None)
        st.session_state.pop(f"timer_finished_p3_{view_id}", None)

        st.rerun()

def handle_next_quiz_question(view_key_to_pop):
    part_keys = list(st.session_state.all_data['quiz'].keys())
    # Ensure current indices are valid
    if st.session_state.current_part_index >= len(part_keys):
        st.error("Quiz navigation error: Invalid part index.")
        return
    current_part_key = part_keys[st.session_state.current_part_index]
    questions_for_part = st.session_state.all_data['quiz'][current_part_key]
    if st.session_state.current_sample_index >= len(questions_for_part):
         st.error("Quiz navigation error: Invalid sample index.")
         return
    sample = questions_for_part[st.session_state.current_sample_index]

    question_text = "N/A"
    try:
        if "Tone Controllability" in current_part_key:
            question_text = f"Intensity of '{sample['tone_to_compare']}' has {sample['comparison_type']}"
        elif "Caption Quality" in current_part_key:
            if st.session_state.current_rating_question_index < len(sample.get("questions",[])):
                question_text = sample["questions"][st.session_state.current_rating_question_index].get("question_text", "N/A")
            else:
                 st.error("Quiz navigation error: Invalid rating question index.")
                 return
        else: # Identification
            category = sample.get('category', 'tone').title()
            question_text = f"Identify dominant {category}" # Simplified for saving
    except KeyError as e:
         st.error(f"Data error in quiz sample {sample.get('sample_id', 'Unknown')}: Missing key {e}")
         return


    success = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, sample, sample, st.session_state.last_choice, 'quiz', question_text, was_correct=st.session_state.is_correct)
    if not success:
        st.error("Failed to save response. Please check your connection and try again.")
        return

    # Advance quiz state
    if "Caption Quality" in current_part_key:
        st.session_state.current_rating_question_index += 1
        # Check if we finished questions for the current sample
        if st.session_state.current_rating_question_index >= len(sample.get("questions", [])):
            st.session_state.current_sample_index += 1
            st.session_state.current_rating_question_index = 0 # Reset for next sample
            # Check if we finished samples for the current part
            if st.session_state.current_sample_index >= len(questions_for_part):
                 st.session_state.current_part_index += 1
                 st.session_state.current_sample_index = 0 # Reset for next part
    else: # Controllability or Identification (one question per sample)
        st.session_state.current_sample_index += 1
        # Check if we finished samples for the current part
        if st.session_state.current_sample_index >= len(questions_for_part):
            st.session_state.current_part_index += 1
            st.session_state.current_sample_index = 0 # Reset for next part

    st.session_state.pop(view_key_to_pop, None) # Clean up view state
    st.session_state.show_feedback = False # Reset feedback flag
    st.rerun() # Rerun to display the next question/part or results


def jump_to_part(part_index):
    st.session_state.current_part_index = part_index
    st.session_state.current_sample_index = 0
    st.session_state.current_rating_question_index = 0
    st.session_state.show_feedback = False
    # Clean up potentially leftover view states when jumping
    for key in list(st.session_state.keys()):
        if key.startswith('view_state_quiz_'): # Adjusted prefix
            st.session_state.pop(key, None)
    st.rerun()

def jump_to_study_part(part_number):
    st.session_state.study_part = part_number
    # Reset indices for the target part
    st.session_state.current_video_index = 0
    st.session_state.current_caption_index = 0
    st.session_state.current_comparison_index = 0
    st.session_state.current_change_index = 0
     # Clean up potentially leftover view states when jumping
    for key in list(st.session_state.keys()):
        if key.startswith('view_state_p1_') or key.startswith('view_state_p2_') or key.startswith('view_state_p3_'):
            st.session_state.pop(key, None)
    st.rerun()


def restart_quiz():
    st.session_state.page = 'quiz'
    st.session_state.current_part_index = 0
    st.session_state.current_sample_index = 0
    st.session_state.current_rating_question_index = 0
    st.session_state.show_feedback = False
    st.session_state.score = 0
    st.session_state.score_saved = False # Reset if you have logic based on score saving
    # Clean up potentially leftover view states
    for key in list(st.session_state.keys()):
        if key.startswith('view_state_quiz_'): # Adjusted prefix
            st.session_state.pop(key, None)
    st.rerun()

def render_comprehension_quiz(sample, view_state_key, proceed_step):
    options_key = f"{view_state_key}_comp_options"
    # Safely get distractors and answer
    distractors = sample.get('distractor_answers', [])
    correct = sample.get('road_event_answer', 'Correct Answer Missing') # Provide default
    if not distractors or correct == 'Correct Answer Missing':
         st.warning("Comprehension question data missing, cannot render quiz.")
         # Automatically proceed if data is missing? Or just show a message?
         # Option: Auto-proceed
         st.session_state[view_state_key]['step'] = proceed_step
         st.rerun()
         return # Stop rendering this component

    if options_key not in st.session_state:
        options = distractors + [correct]
        random.shuffle(options)
        st.session_state[options_key] = options
    else:
        options = st.session_state[options_key]

    st.markdown("##### Describe what is happening in the video")

    # Use .get() for safer access to view_state
    if st.session_state[view_state_key].get('comp_feedback', False):
        user_choice = st.session_state[view_state_key].get('comp_choice')
        correct_answer = sample.get('road_event_answer')

        for opt in options:
            is_correct = (opt == correct_answer)
            is_user_choice = (opt == user_choice)
            if is_correct:
                display_text = f"<strong>{opt} (Correct Answer)</strong>"
                css_class = "correct-answer"
            elif is_user_choice:
                display_text = f"{opt} (Your selection)"
                css_class = "wrong-answer"
            else:
                display_text = opt
                css_class = "normal-answer"
            st.markdown(f'<div class="feedback-option {css_class}">{display_text}</div>', unsafe_allow_html=True)

        # Unique key using sample_id
        proceed_key = f"proceed_to_captions_{sample.get('sample_id', sample.get('video_id', 'unknown'))}"
        if st.button("Proceed to Caption(s)", key=proceed_key):
            st.session_state[view_state_key]['step'] = proceed_step
            st.rerun()
    else:
        # Use more unique keys based on sample_id
        form_key = f"comp_quiz_form_{sample.get('sample_id', sample.get('video_id', 'unknown'))}"
        radio_key = f"comp_radio_{sample.get('sample_id', sample.get('video_id', 'unknown'))}"
        with st.form(key=form_key):
            choice = st.radio("Select one option:", options, key=radio_key, index=None, label_visibility="collapsed")
            if st.form_submit_button("Submit"):
                if choice:
                    st.session_state[view_state_key]['comp_choice'] = choice
                    st.session_state[view_state_key]['comp_feedback'] = True
                    st.rerun()
                else:
                    st.error("Please select an answer.")
        # prev_key = f"prev_from_comp_form_{sample.get('sample_id', sample.get('video_id', 'unknown'))}"
        # st.button("<< Previous", on_click=go_to_previous_step, args=(view_state_key,), key=prev_key) # REMOVED

# --- Main App ---
if 'page' not in st.session_state:
    st.session_state.page = 'demographics'
    st.session_state.current_part_index = 0; st.session_state.current_sample_index = 0
    st.session_state.show_feedback = False; st.session_state.current_rating_question_index = 0
    st.session_state.score = 0; st.session_state.score_saved = False
    st.session_state.study_part = 1; st.session_state.current_video_index = 0
    st.session_state.current_caption_index = 0; st.session_state.current_comparison_index = 0
    st.session_state.current_change_index = 0; st.session_state.all_data = load_data()

if st.session_state.all_data is None:
    st.error("Failed to load application data. Please check file paths and formats.")
    st.stop() # Stop if data loading failed critically

# --- Page Rendering Logic ---
if st.session_state.page == 'demographics':
    st.title("Tone-controlled Video Captioning")
    # Debug skip button at the top
    if st.button("DEBUG: Skip to Main Study"):
        st.session_state.email = "debug@test.com"; st.session_state.age = 25
        st.session_state.gender = "Prefer not to say"; st.session_state.page = 'user_study_main'; st.rerun()

    st.header("Welcome! Before you begin, please provide some basic information:")
    email = st.text_input("Please enter your email address:")
    # --- CORRECTED SELECTBOXES ---
    age = st.selectbox(
        "Age:",
        options=list(range(18, 61)),  # Options are just the numbers
        index=None,                  # Nothing selected by default
        placeholder="Select your age..." # Display text for default
    )
    gender = st.selectbox(
        "Gender:",
        options=["Male", "Female", "Other / Prefer not to say"], # Options are just the strings
        index=None,                         # Nothing selected by default
        placeholder="Select your gender..." # Display text for default
    )
    # --- END CORRECTION ---

    if st.checkbox("I am over 18 and agree to participate in this study. I understand my responses will be recorded anonymously."):
        nav_cols = st.columns([1, 6]) # Next, Spacer
        with nav_cols[0]:
            if st.button("Next", use_container_width=True, key="demographics_next"):
                email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                # Check for None selections explicitly
                if not all([email, age is not None, gender is not None]): st.error("Please fill in all fields to continue.")
                elif not re.match(email_regex, email): st.error("Please enter a valid email address.")
                # Removed age < 18 check as options handle it
                else:
                    st.session_state.email = email; st.session_state.age = age; st.session_state.gender = gender
                    st.session_state.page = 'intro_video'; st.rerun()

elif st.session_state.page == 'intro_video':
    st.title("Introductory Video")
    _ , vid_col, _ = st.columns([1, 3, 1])
    with vid_col:
        st.video(INTRO_VIDEO_PATH, autoplay=True, muted=True)

    nav_cols = st.columns([1, 1, 5]) # Prev, Next, Spacer
    # with nav_cols[0]: # REMOVED
    #     st.button("<< Previous", on_click=go_to_previous_page, args=('demographics',), key="prev_intro", use_container_width=True)
    with nav_cols[1]:
        if st.button("Next >>", key="next_intro", use_container_width=True):
            st.session_state.page = 'what_is_tone'
            st.rerun()

elif st.session_state.page == 'what_is_tone':
    st.markdown("<h1 style='text-align: center;'>Tone and Style</h1>", unsafe_allow_html=True) # Changed "Writing Style"

    st.markdown("<p style='text-align: center; font-size: 1.1rem;'><b>Tone</b> refers to the author's attitude or feeling about a subject, reflecting their emotional character (e.g., Sarcastic, Angry, Caring).</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.1rem;'><b>Style</b> refers to the author's technique or method of writing (e.g., Advisory, Factual, Conversational).</p>", unsafe_allow_html=True) # Changed "Writing Style"

    spacer, title = st.columns([1, 15])
    with title:
        st.subheader("For example:")

    col1, col2 = st.columns(2, gap="small")
    with col1:
        _, vid_col, _ = st.columns([1.5, 1, 0.25])
        with vid_col:
            video_path = "media/v_1772082398257127647_PAjmPcDqmPNuvb6p.mp4"
            if os.path.exists(video_path):
                st.video(video_path, autoplay=True, muted=True, loop=True)
            else:
                st.warning(f"Video not found at {video_path}")
    with col2:
        _, img_col, _ = st.columns([0.25, 2, 1])
        with img_col:
            image_path = "media/tone_meaning.jpg" # Consider updating if image mentions "Writing Style"
            if os.path.exists(image_path):
                st.image(image_path)
            else:
                st.warning(f"Image not found at {image_path}")

    nav_cols = st.columns([1, 1, 5]) # Prev, Next, Spacer
    # with nav_cols[0]: # REMOVED
    #     st.button("<< Previous", on_click=go_to_previous_page, args=('intro_video',), key="prev_tone", use_container_width=True)
    with nav_cols[1]:
        if st.button("Next >>", key="next_tone", use_container_width=True):
            st.session_state.page = 'factual_info'
            st.rerun()

elif st.session_state.page == 'factual_info':
    st.markdown("<h1 style='text-align: center;'>How to measure a caption's <span style='color: #4F46E5;'>Factual Accuracy?</span></h1>", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 3])
    with col1:
        _, vid_col, _ = st.columns([1, 1.5, 1])
        with vid_col:
            video_path = "media/v_1772082398257127647_PAjmPcDqmPNuvb6p.mp4"
            if os.path.exists(video_path):
                st.video(video_path, autoplay=True, muted=True, loop=True)
            else:
                st.warning(f"Video not found at {video_path}")
    with col2:
        image_path = "media/factual_info_new.jpg"
        if os.path.exists(image_path):
            st.image(image_path)
        else:
            st.warning(f"Image not found at {image_path}")

    # --- MODIFIED BUTTON LAYOUT ---
    nav_col, _ = st.columns([1, 4]) # Narrow column for buttons
    with nav_col:
        if st.button("Start Quiz", key="start_quiz", use_container_width=True):
            st.session_state.page = 'quiz'
            st.rerun()
        st.button("<< Previous", on_click=go_to_previous_page, args=('what_is_tone',), key="prev_factual", use_container_width=True)
    # --- END MODIFICATION ---

# --- Quiz Page ---
elif st.session_state.page == 'quiz':
    # --- Start Quiz Logic ---
    part_keys = list(st.session_state.all_data.get('quiz', {}).keys())
    if not part_keys:
        st.error("Quiz data is missing or empty.")
        st.stop()

    with st.sidebar:
        st.header("Quiz Sections")
        for i, name in enumerate(part_keys):
            st.button(name, on_click=jump_to_part, args=(i,), use_container_width=True, key=f"jump_part_{i}")

    if st.session_state.current_part_index >= len(part_keys):
        st.session_state.page = 'quiz_results'
        st.rerun()

    current_part_key = part_keys[st.session_state.current_part_index]
    questions_for_part = st.session_state.all_data['quiz'][current_part_key]
    if not questions_for_part: # Check if part has questions
         st.warning(f"No questions found for {current_part_key}. Skipping.")
         st.session_state.current_part_index += 1
         st.rerun()


    current_index = st.session_state.current_sample_index
    if current_index >= len(questions_for_part): # Should not happen with corrected logic, but safe check
        st.warning(f"Reached end of samples for {current_part_key}. Moving to next part.")
        st.session_state.current_part_index += 1
        st.session_state.current_sample_index = 0
        st.rerun()

    sample = questions_for_part[current_index]
    sample_id = sample.get('sample_id', f'quiz_{current_part_key}_{current_index}') # More unique ID

    timer_finished_key = f"timer_finished_quiz_{sample_id}"

    # --- Video Watching Step ---
    if not st.session_state.get(timer_finished_key, False):
        st.subheader("Watch the video")
        st.button("DEBUG: Skip Video >>", on_click=lambda k=timer_finished_key: st.session_state.update({k: True}) or st.rerun(), key=f"skip_video_quiz_{sample_id}")

        with st.spinner("Video playing..."):
            col1, _ = st.columns([1.2, 1.5]) # Layout
            with col1:
                video_path = sample.get('video_path')
                if video_path and os.path.exists(video_path):
                    if sample.get("orientation") == "portrait":
                        _, vid_col, _ = st.columns([1, 3, 1])
                        with vid_col: st.video(video_path, autoplay=True, muted=True)
                    else: st.video(video_path, autoplay=True, muted=True)
                else:
                     st.warning(f"Video not found for sample {sample_id}")

            duration = sample.get('duration', 1) # Short default if metadata failed
            time.sleep(duration) # Simulate watching

        # Automatically advance after timer if not already marked as finished
        if not st.session_state.get(timer_finished_key, False):
            st.session_state[timer_finished_key] = True
            st.rerun() # Rerun to proceed to the next step
    else: # --- Post-Video Steps (Summary, Comprehension, Questions) ---
        view_state_key = f'view_state_{sample_id}'
        if view_state_key not in st.session_state:
            # Initialize state: step 1 is showing summary/comp quiz prompt
            st.session_state[view_state_key] = {'step': 1, 'summary_typed': False, 'comp_feedback': False, 'comp_choice': None}
        current_step = st.session_state[view_state_key]['step']

        def stream_text(text):
            for word in text.split(" "): yield word + " "; time.sleep(0.05) # Slightly faster

        col1, col2 = st.columns([1.2, 1.5]) # Main layout columns

        with col1: # Video and Summary column
            st.subheader("Video") # Keep video visible
            video_path = sample.get('video_path')
            if video_path and os.path.exists(video_path):
                 if sample.get("orientation") == "portrait":
                     _, vid_col, _ = st.columns([1, 3, 1])
                     with vid_col: st.video(video_path, autoplay=True, muted=True, loop=True) # Loop video now
                 else: st.video(video_path, autoplay=True, muted=True, loop=True)
            else: st.warning(f"Video not found for sample {sample_id}")

            # --- MODIFIED FLOW ---
            # Show summary ONLY if step >= 2
            if current_step >= 2 and "video_summary" in sample:
                 st.subheader("Video Summary")
                 if st.session_state[view_state_key].get('summary_typed', False):
                     st.info(sample["video_summary"])
                 else: # Typewriter effect only once
                     with st.empty(): st.write_stream(stream_text(sample["video_summary"]))
                     st.session_state[view_state_key]['summary_typed'] = True

            # Step 1: After video, before summary
            if current_step == 1:
                if st.button("Proceed to Summary", key=f"quiz_summary_{sample_id}"):
                    st.session_state[view_state_key]['step'] = 2 # Go to step 2 (show summary)
                    st.rerun()
                st.button("Skip to Questions >>", on_click=skip_to_questions, args=(view_state_key, None), key=f"skip_to_q_quiz_{sample_id}")

            # Step 2: After summary is shown
            if current_step == 2:
                if sample.get('distractor_answers'): # Only proceed to comp quiz if distractors exist
                    if st.button("Proceed to Comprehension Question", key=f"quiz_comp_q_{sample_id}"):
                        st.session_state[view_state_key]['step'] = 3; st.rerun() # Step 3 is comp quiz
                else: # Skip comprehension
                     if st.button("Proceed to Caption(s)", key=f"quiz_skip_comp_{sample_id}"):
                         st.session_state[view_state_key]['step'] = 4; st.rerun() # Step 4 is show captions
            # --- END MODIFIED FLOW ---


        with col2: # Questions column
            display_title = re.sub(r'Part \d+: ', '', current_part_key)
            if "Tone Identification" in current_part_key: display_title = f"{sample.get('category', 'Tone').title()} Identification"
            elif "Tone Controllability" in current_part_key: display_title = f"{sample.get('category', 'Tone').title()} Comparison"
            elif "Caption Quality" in current_part_key: display_title = "Caption Quality Rating"

            # --- MODIFIED STEP ---
            # Step 3: Comprehension Quiz
            if current_step == 3 and sample.get('distractor_answers'):
                 st.markdown("<br><br>", unsafe_allow_html=True)
                 render_comprehension_quiz(sample, view_state_key, proceed_step=4) # Proceed to step 4 (show captions)

            # --- MODIFIED STEP ---
            # Step 4: Show Captions
            if current_step >= 4:
                 st.subheader(display_title)
                 if "Tone Controllability" in current_part_key:
                     st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{sample["caption_A"]}</p></div>', unsafe_allow_html=True)
                     st.markdown(f'<div class="comparison-caption-box" style="margin-top:0.5rem;"><strong>Caption B</strong><p class="caption-text">{sample["caption_B"]}</p></div>', unsafe_allow_html=True)
                 else: # Identification or Quality
                     st.markdown(f'<div class="comparison-caption-box"><strong>Caption</strong><p class="caption-text">{sample["caption"]}</p></div>', unsafe_allow_html=True)

                 # --- MODIFIED STEP ---
                 if current_step == 4: # Buttons after showing captions
                      # st.button("<< Previous", ...) # REMOVED
                      if st.button("Show Questions", key=f"quiz_show_q_{sample_id}"):
                          st.session_state[view_state_key]['step'] = 6 # Jump to question step
                          st.rerun()

            # Step 6: Show Questions and Handle Submission/Feedback
            if current_step >= 6:
                # Determine the specific question data based on quiz part type
                question_data = {}
                options_list = []
                question_text_display = ""
                terms_to_define = set() # Define here to be accessible later

                if "Caption Quality" in current_part_key:
                    if st.session_state.current_rating_question_index < len(sample.get("questions", [])):
                        question_data = sample["questions"][st.session_state.current_rating_question_index]
                        options_list = question_data.get('options', [])
                        raw_text = question_data.get("question_text", "")
                        app_trait = sample.get("application")
                        if app_trait:
                             terms_to_define.add(app_trait)
                             question_text_display = raw_text.replace("{}", f"<b class='highlight-trait'>{app_trait}</b>")
                        else: question_text_display = raw_text
                    else: # Safety check
                        st.warning("Reached end of quality questions unexpectedly.")
                        handle_next_quiz_question(view_state_key) # Try to advance
                        st.stop()
                elif "Tone Controllability" in current_part_key:
                    question_data = sample # Data is at the sample level
                    options_list = question_data.get('options', ["Yes", "No"])
                    trait = sample.get('tone_to_compare') # Use .get()
                    if trait: terms_to_define.add(trait)
                    change_type = sample.get('comparison_type','changed')
                    question_text_display = f"From Caption A to B, has the level of <b class='highlight-trait'>{trait}</b> {change_type}?"

                else: # Identification
                    question_data = sample # Data is at the sample level
                    options_list = question_data.get('options', [])
                    category_text = sample.get('category', 'tone').lower()
                    if category_text == "tone": question_text_display = "What is the most dominant tone in the caption?"
                    elif category_text == "style": question_text_display = "What is the most dominant style in the caption?"
                    else: question_text_display = f"Identify the most dominant {category_text} in the caption"
                    terms_to_define.update(o for o in options_list if isinstance(o, str)) # Add options if they are strings

                # --- Display Question and Handle Feedback/Form ---
                st.markdown(f'<div class="quiz-question-box"><strong>Question:</strong><span class="question-text-part">{question_text_display}</span></div>', unsafe_allow_html=True)
                if st.session_state.get('show_feedback', False): # Use .get for safety
                    # Feedback display logic
                    user_choice = st.session_state.get('last_choice')
                    correct_answer = question_data.get('correct_answer')
                    if user_choice is None: # Handle case where user hasn't chosen yet (shouldn't happen here)
                         st.warning("Cannot show feedback without a user choice.")
                    else:
                        if not isinstance(user_choice, list): user_choice = [user_choice]
                        if not isinstance(correct_answer, list): correct_answer = [correct_answer]

                        st.write(" ")
                        for opt in options_list:
                            is_correct = opt in correct_answer
                            is_user_choice = opt in user_choice
                            css_class = "correct-answer" if is_correct else ("wrong-answer" if is_user_choice else "normal-answer")
                            display_text = f"<strong>{opt} (Correct Answer)</strong>" if is_correct else (f"{opt} (Your selection)" if is_user_choice else opt)
                            st.markdown(f'<div class="feedback-option {css_class}">{display_text}</div>', unsafe_allow_html=True)

                        st.info(f"**Explanation:** {question_data.get('explanation', 'No explanation provided.')}")
                        st.button("Next Question", key=f"quiz_next_q_{sample_id}", on_click=handle_next_quiz_question, args=(view_state_key,))
                else:
                    # Form for answering
                    with st.form(f"quiz_form_{sample_id}"):
                        choice = None
                        q_type = question_data.get("question_type") # Get type from specific question if Quality, else from sample
                        if q_type == "multi":
                            st.write("Select all that apply (exactly 2):")
                            choice = [opt for opt in options_list if st.checkbox(opt, key=f"cb_{sample_id}_{opt}")]
                        else: # Single choice (default)
                            choice = st.radio("Select one option:", options_list, key=f"radio_{sample_id}", index=None, label_visibility="collapsed")

                        if st.form_submit_button("Submit Answer"):
                            valid = True
                            if not choice:
                                st.error("Please select an option.")
                                valid = False
                            elif q_type == "multi" and len(choice) != 2:
                                st.error("Please select exactly 2 options.")
                                valid = False

                            if valid:
                                st.session_state.last_choice = choice
                                correct_ans = question_data.get('correct_answer')
                                is_correct = False # Default
                                try: # Comparison logic
                                    if isinstance(correct_ans, list): is_correct = (set(choice) == set(correct_ans))
                                    else: is_correct = (choice == correct_ans)
                                except TypeError: # Handle potential comparison errors (e.g., list vs non-list)
                                     st.warning("Could not determine correctness due to data mismatch.")

                                st.session_state.is_correct = is_correct
                                if is_correct: st.session_state.score += 1
                                st.session_state.show_feedback = True
                                st.rerun() # Rerun to show feedback

                    # Previous button outside the form
                    # st.button("<< Previous", ...) # REMOVED

                # Reference Box
                if terms_to_define:
                    definitions = st.session_state.all_data.get('definitions', {})
                    reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {definitions.get(term, 'Definition not found.')}</li>" for term in sorted(list(terms_to_define)) if term) + "</ul></div>"
                    st.markdown(reference_html, unsafe_allow_html=True)
    # --- End Quiz Logic ---

elif st.session_state.page == 'quiz_results':
    total_scorable_questions = 0
    try: # Robust calculation
        for pname, q_list in st.session_state.all_data.get('quiz', {}).items():
            if isinstance(q_list, list): # Ensure it's a list
                if "Quality" in pname:
                     total_scorable_questions += sum(len(item.get("questions",[])) for item in q_list if isinstance(item.get("questions"), list))
                else: # Identification, Controllability (1 scorable question per item)
                     total_scorable_questions += len(q_list)
    except Exception as e:
        st.error(f"Error calculating total questions: {e}")

    passing_score = 5 # Adjust as needed
    st.header(f"Your Final Score: {st.session_state.score} / {total_scorable_questions}")
    if st.session_state.score >= passing_score:
        st.success("**Status: Passed**");
        if st.button("Proceed to User Study"): st.session_state.page = 'user_study_main'; st.rerun()
    else: st.error("**Status: Failed**"); st.markdown(f"Unfortunately, you did not meet the passing score of {passing_score}. You can try again."); st.button("Take Quiz Again", on_click=restart_quiz)

elif st.session_state.page == 'user_study_main':
    # --- Start Main Study Logic ---
    if not st.session_state.all_data: st.error("Data could not be loaded."); st.stop()
    def stream_text(text):
        for word in text.split(" "): yield word + " "; time.sleep(0.05) # Slightly faster
    with st.sidebar:
        st.header("Study Sections")
        st.button("Part 1: Caption Rating", on_click=jump_to_study_part, args=(1,), use_container_width=True)
        st.button("Part 2: Caption Comparison", on_click=jump_to_study_part, args=(2,), use_container_width=True)
        st.button("Part 3: Style Intensity Change", on_click=jump_to_study_part, args=(3,), use_container_width=True) # Changed Name

    # --- Part 1 ---
    if st.session_state.study_part == 1:
        all_videos = st.session_state.all_data['study'].get('part1_ratings', [])
        video_idx, caption_idx = st.session_state.current_video_index, st.session_state.current_caption_index
        if video_idx >= len(all_videos):
            st.session_state.study_part = 2; st.rerun() # Move to next part

        current_video = all_videos[video_idx]
        if caption_idx >= len(current_video.get('captions',[])): # Safety check
             st.session_state.current_video_index += 1
             st.session_state.current_caption_index = 0
             st.rerun()

        video_id = current_video['video_id']
        timer_finished_key = f"timer_finished_p1_{video_id}"

        # Video watching step (only for first caption)
        if not st.session_state.get(timer_finished_key, False) and caption_idx == 0:
            st.subheader("Watch the video")
            st.button("DEBUG: Skip Video >>", on_click=lambda k=timer_finished_key: st.session_state.update({k: True}) or st.rerun(), key=f"skip_video_p1_{video_id}")
            with st.spinner("Video playing..."):
                main_col, _ = st.columns([1, 1.8])
                with main_col:
                    video_path = current_video.get('video_path')
                    if video_path and os.path.exists(video_path):
                         if current_video.get("orientation") == "portrait":
                             _, vid_col, _ = st.columns([1, 3, 1])
                             with vid_col: st.video(video_path, autoplay=True, muted=True)
                         else: st.video(video_path, autoplay=True, muted=True)
                    else: st.warning(f"Video not found for {video_id}")
                    duration = current_video.get('duration', 1); time.sleep(duration)
            if not st.session_state.get(timer_finished_key, False):
                st.session_state[timer_finished_key] = True; st.rerun()
        else: # Post-video steps
            current_caption = current_video['captions'][caption_idx]
            view_state_key = f"view_state_p1_{current_caption['caption_id']}"; summary_typed_key = f"summary_typed_p1_{current_video['video_id']}"
            q_templates = st.session_state.all_data['questions']['part1_questions']
            questions_to_ask_raw = [q for q in q_templates if q['id'] != 'overall_relevance']; question_ids = [q['id'] for q in questions_to_ask_raw]

            base_options_map = {"tone_relevance": ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"], "factual_consistency": ["Contradicts", "Inaccurate", "Partially", "Mostly Accurate", "Accurate"], "usefulness": ["Not at all", "Slightly", "Moderately", "Very", "Extremely"], "human_likeness": ["Robotic", "Unnatural", "Moderate", "Very Human-like", "Natural"]}

            if view_state_key not in st.session_state:
                initial_step = 5 if caption_idx > 0 else 1 # Start at caption display if not first caption
                st.session_state[view_state_key] = {'step': initial_step, 'interacted': {qid: False for qid in question_ids}, 'comp_feedback': False, 'comp_choice': None}
                if caption_idx == 0: st.session_state[summary_typed_key] = False

            current_step = st.session_state[view_state_key]['step']

            def mark_interacted(q_id, view_key, question_index):
                if view_key in st.session_state and 'interacted' in st.session_state[view_key]:
                    if not st.session_state[view_key]['interacted'][q_id]:
                        st.session_state[view_key]['interacted'][q_id] = True
                        # Ensure step doesn't exceed max needed for questions + 1
                        st.session_state[view_state_key]['step'] = min(6 + len(question_ids), 6 + question_index + 1)

            title_col1, title_col2 = st.columns([1, 1.8])
            with title_col1: st.subheader("Video")
            with title_col2:
                if current_step >= 5: st.subheader("Caption Quality Rating")

            col1, col2 = st.columns([1, 1.8])
            with col1: # Video and Summary column
                video_path = current_video.get('video_path')
                if video_path and os.path.exists(video_path):
                    if current_video.get("orientation") == "portrait":
                        _, vid_col, _ = st.columns([1, 3, 1])
                        with vid_col: st.video(video_path, autoplay=True, muted=True, loop=True)
                    else: st.video(video_path, autoplay=True, muted=True, loop=True)
                else: st.warning(f"Video not found for {video_id}")

                if caption_idx == 0: # Only show summary steps for the first caption
                    if current_step == 1:
                        if st.button("Proceed to Summary", key=f"proceed_summary_{video_idx}"):
                            st.session_state[view_state_key]['step'] = 2; st.rerun()
                    elif current_step >= 2:
                        st.subheader("Video Summary")
                        if st.session_state.get(summary_typed_key, False): st.info(current_video["video_summary"])
                        else:
                            with st.empty(): st.write_stream(stream_text(current_video["video_summary"]))
                            st.session_state[summary_typed_key] = True

                        if current_step == 2: # Only show these buttons at step 2
                           # st.button("<< Previous", ...) # REMOVED
                           if current_video.get('distractor_answers'): # Check if comp quiz exists
                                if st.button("Proceed to Comprehension Question", key=f"p1_proceed_comp_q_{video_idx}"):
                                    st.session_state[view_state_key]['step'] = 3; st.rerun()
                           else: # Skip comp quiz
                                if st.button("Proceed to Caption", key=f"p1_skip_comp_{video_idx}"):
                                     st.session_state[view_state_key]['step'] = 5; st.rerun() # Go directly to caption display
                else: # Subsequent captions
                    st.subheader("Video Summary"); st.info(current_video["video_summary"])

                if current_step < 6: # Show skip before questions
                    st.button("DEBUG: Skip to Questions >>", on_click=skip_to_questions, args=(view_state_key, summary_typed_key), key=f"skip_to_q_p1_{video_id}")

            with col2: # Rating column
                validation_placeholder = st.empty()
                # Step 3/4: Comprehension Quiz (only if distractors exist and first caption)
                if (current_step == 3 or current_step == 4) and caption_idx == 0 and current_video.get('distractor_answers'):
                    render_comprehension_quiz(current_video, view_state_key, proceed_step=5) # Go to step 5 after quiz

                # Step 5: Show Caption
                if current_step >= 5:
                    colors = ["#FFEEEE", "#EBF5FF", "#E6F7EA"]; highlight_color = colors[caption_idx % len(colors)]
                    # Apply yellow highlight animation class
                    caption_box_class = "part1-caption-box new-caption-highlight"
                    st.markdown(f'<div class="{caption_box_class}" style="background-color: {highlight_color};"><strong>Caption {caption_idx + 1}:</strong><p class="caption-text">{current_caption["text"]}</p></div>', unsafe_allow_html=True)
                    streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_p1_{current_caption['caption_id']}") # Reset animation

                    if current_step == 5: # Buttons after showing caption
                        # st.button("<< Previous", ...) # REMOVED
                        if st.button("Show Questions", key=f"show_q_{current_caption['caption_id']}"):
                            st.session_state[view_state_key]['step'] = 6; st.rerun()

                # Step 6 onwards: Show Questions
                if current_step >= 6:
                    terms_to_define = set()
                    control_scores = current_caption.get("control_scores", {})
                    tone_traits = list(control_scores.get("tone", {}).keys())[:2]
                    application_text = current_caption.get("application", "the intended application")
                    style_traits_data = list(control_scores.get("writing_style", {}).keys()) # Still use 'writing_style' key for data access
                    main_style_trait = style_traits_data[0] if style_traits_data else None

                    terms_to_define.update(tone_traits); terms_to_define.add(application_text)
                    if main_style_trait: terms_to_define.add(main_style_trait)

                    style_q_config = next((q for q in q_templates if q['id'] == 'style_relevance'), {})
                    default_text_template = style_q_config.get("default_text", "How {} is the caption's style?")
                    default_options = style_q_config.get("default_options", ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"])
                    style_override = style_q_config.get("overrides", {}).get(main_style_trait, {})
                    style_q_text_template = style_override.get("text", default_text_template)
                    style_q_options = style_override.get("options", default_options)
                    dynamic_options_map = {**base_options_map, "style_relevance": style_q_options}

                    def format_traits(traits):
                        hl = [f"<b class='highlight-trait'>{t}</b>" for t in traits if t]
                        return " and ".join(hl) if hl else ""

                    tone_str = format_traits(tone_traits)
                    style_str_highlighted = format_traits([main_style_trait])

                    tone_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'tone_relevance'), "How {} does the caption sound?")
                    fact_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'factual_consistency'), "How factually accurate is the caption?")
                    useful_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'usefulness'), "How useful is this caption for {}?")
                    human_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'human_likeness'), "How human-like does this caption sound?")

                    # Determine final style question text (with highlighting)
                    if main_style_trait in style_q_config.get("overrides", {}) and "{}" not in style_q_text_template:
                         final_style_q_text = style_q_text_template # Use override text directly (already has highlight)
                    else: # Use default template with highlighted style name
                         final_style_q_text = default_text_template.format(style_str_highlighted)


                    questions_to_ask = [
                        {"id": "tone_relevance", "text": tone_q_template.format(tone_str)},
                        {"id": "style_relevance", "text": final_style_q_text},
                        {"id": "factual_consistency", "text": fact_q_template},
                        {"id": "usefulness", "text": useful_q_template.format(f"<b class='highlight-trait'>{application_text}</b>")},
                        {"id": "human_likeness", "text": human_q_template}
                    ]

                    interacted_state = st.session_state[view_state_key].get('interacted', {})
                    question_cols_row1 = st.columns(3); question_cols_row2 = st.columns(3) # Layout for 5 sliders

                    def render_slider(q, col, q_index, view_key_arg):
                        with col:
                            slider_key = f"ss_{q['id']}_cap{caption_idx}"
                            st.markdown(f"<div class='slider-label'><strong>{q_index + 1}. {q['text']}</strong></div>", unsafe_allow_html=True)
                            q_options = dynamic_options_map.get(q['id'], default_options) # Use correct options
                            st.select_slider(q['id'], options=q_options, key=slider_key, label_visibility="collapsed", on_change=mark_interacted, args=(q['id'], view_key_arg, q_index), value=q_options[0])

                    num_interacted = sum(1 for flag in interacted_state.values() if flag)
                    questions_to_show = num_interacted + 1

                    # Render sliders progressively
                    if questions_to_show >= 1: render_slider(questions_to_ask[0], question_cols_row1[0], 0, view_state_key)
                    if questions_to_show >= 2: render_slider(questions_to_ask[1], question_cols_row1[1], 1, view_state_key)
                    if questions_to_show >= 3: render_slider(questions_to_ask[2], question_cols_row1[2], 2, view_state_key)
                    if questions_to_show >= 4: render_slider(questions_to_ask[3], question_cols_row2[0], 3, view_state_key)
                    if questions_to_show >= 5: render_slider(questions_to_ask[4], question_cols_row2[1], 4, view_state_key)

                    # Show submit button only after all sliders are potentially visible
                    if questions_to_show > len(questions_to_ask):
                        # st.button("<< Previous", ...) # REMOVED

                        if st.button("Submit Ratings", key=f"submit_cap{caption_idx}"):
                            all_interacted = all(interacted_state.get(qid, False) for qid in question_ids)
                            if not all_interacted:
                                missing_qs = [i+1 for i, qid in enumerate(question_ids) if not interacted_state.get(qid, False)]
                                validation_placeholder.warning(f"⚠️ Please move the slider for question(s): {', '.join(map(str, missing_qs))}")
                            else:
                                with st.spinner("Saving response..."):
                                    all_saved = True
                                    responses_to_save = {qid: st.session_state.get(f"ss_{qid}_cap{caption_idx}") for qid in question_ids}
                                    for q_id, choice_text in responses_to_save.items():
                                        # Use the exact question text shown to the user for saving
                                        full_q_text = next((q['text'] for q in questions_to_ask if q['id'] == q_id), "N/A")
                                        if not save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_video, current_caption, choice_text, 'user_study_part1', full_q_text):
                                            all_saved = False; break
                                    if all_saved:
                                        st.session_state.current_caption_index += 1
                                        if st.session_state.current_caption_index >= len(current_video['captions']):
                                            st.session_state.current_video_index += 1; st.session_state.current_caption_index = 0
                                        st.session_state.pop(view_state_key, None); st.rerun()
                                    else:
                                        st.error("Failed to save all responses. Please try again.")


                    definitions = st.session_state.all_data.get('definitions', {})
                    reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {definitions.get(term, 'Definition not found.')}</li>" for term in sorted(list(terms_to_define)) if term) + "</ul></div>"
                    st.markdown(reference_html, unsafe_allow_html=True)
    # --- End Part 1 ---

    # --- Part 2 ---
    elif st.session_state.study_part == 2:
        all_comparisons = st.session_state.all_data['study'].get('part2_comparisons', [])
        comp_idx = st.session_state.current_comparison_index
        if comp_idx >= len(all_comparisons): st.session_state.study_part = 3; st.rerun()

        current_comp = all_comparisons[comp_idx]; comparison_id = current_comp['comparison_id']
        timer_finished_key = f"timer_finished_p2_{comparison_id}"

        if not st.session_state.get(timer_finished_key, False):
            st.subheader("Watch the video")
            st.button("DEBUG: Skip Video >>", on_click=lambda k=timer_finished_key: st.session_state.update({k: True}) or st.rerun(), key=f"skip_video_p2_{comparison_id}")
            with st.spinner("Video playing..."):
                main_col, _ = st.columns([1, 1.8])
                with main_col:
                    video_path = current_comp.get('video_path')
                    if video_path and os.path.exists(video_path):
                        if current_comp.get("orientation") == "portrait":
                            _, vid_col, _ = st.columns([1, 3, 1])
                            with vid_col: st.video(video_path, autoplay=True, muted=True)
                        else: st.video(video_path, autoplay=True, muted=True)
                    else: st.warning(f"Video not found for {comparison_id}")
                    duration = current_comp.get('duration', 1); time.sleep(duration)
            if not st.session_state.get(timer_finished_key, False):
                st.session_state[timer_finished_key] = True; st.rerun()
        else:
            view_state_key = f"view_state_p2_{comparison_id}"; summary_typed_key = f"summary_typed_p2_{comparison_id}"
            q_templates = st.session_state.all_data['questions']['part2_questions']
            question_ids = [q['id'] for q in q_templates]

            if view_state_key not in st.session_state:
                st.session_state[view_state_key] = {'step': 1, 'interacted': {qid: False for qid in question_ids}, 'comp_feedback': False, 'comp_choice': None}
                st.session_state[summary_typed_key] = False

            current_step = st.session_state[view_state_key]['step']

            def mark_p2_interacted(q_id, view_key):
                if view_key in st.session_state and 'interacted' in st.session_state[view_key]:
                    if not st.session_state[view_key]['interacted'][q_id]:
                        st.session_state[view_key]['interacted'][q_id] = True
                        # Advance step based on question index
                        q_index = question_ids.index(q_id)
                        st.session_state[view_state_key]['step'] = min(6 + len(question_ids), 6 + q_index + 1)


            title_col1, title_col2 = st.columns([1, 1.8])
            with title_col1: st.subheader("Video")
            with title_col2:
                if current_step >= 5: st.subheader("Caption Comparison")

            col1, col2 = st.columns([1, 1.8])
            with col1: # Video and Summary
                video_path = current_comp.get('video_path')
                if video_path and os.path.exists(video_path):
                     if current_comp.get("orientation") == "portrait":
                         _, vid_col, _ = st.columns([1, 3, 1])
                         with vid_col: st.video(video_path, autoplay=True, muted=True, loop=True)
                     else: st.video(video_path, autoplay=True, muted=True, loop=True)
                else: st.warning(f"Video not found for {comparison_id}")


                if current_step == 1:
                    if st.button("Proceed to Summary", key=f"p2_proceed_summary_{comparison_id}"):
                        st.session_state[view_state_key]['step'] = 2; st.rerun()
                if current_step >= 2:
                    st.subheader("Video Summary")
                    if st.session_state.get(summary_typed_key, False): st.info(current_comp["video_summary"])
                    else:
                        with st.empty(): st.write_stream(stream_text(current_comp["video_summary"]))
                        st.session_state[summary_typed_key] = True

                    if current_step == 2:
                       # st.button("<< Previous", ...) # REMOVED
                       if current_comp.get('distractor_answers'): # Check if comp quiz exists
                           if st.button("Proceed to Comprehension Question", key=f"p2_proceed_captions_{comparison_id}"):
                               st.session_state[view_state_key]['step'] = 3; st.rerun()
                       else: # Skip comp quiz
                            if st.button("Proceed to Captions", key=f"p2_skip_comp_{comparison_id}"):
                                st.session_state[view_state_key]['step'] = 5; st.rerun() # Go directly to caption display

                if current_step < 6:
                    st.button("DEBUG: Skip to Questions >>", on_click=skip_to_questions, args=(view_state_key, summary_typed_key), key=f"skip_to_q_p2_{comparison_id}")

            with col2: # Captions and Questions
                # Step 3/4: Comp Quiz
                if (current_step == 3 or current_step == 4) and current_comp.get('distractor_answers'):
                    render_comprehension_quiz(current_comp, view_state_key, proceed_step=5) # Go to step 5 after quiz

                validation_placeholder = st.empty()
                terms_to_define = set()
                # Step 5: Show Captions
                if current_step >= 5:
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_comp["caption_A"]}</p></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_comp["caption_B"]}</p></div>', unsafe_allow_html=True)
                    if current_step == 5:
                        # st.button("<< Previous", ...) # REMOVED
                        if st.button("Show Questions", key=f"p2_show_q_{comparison_id}"):
                            st.session_state[view_state_key]['step'] = 6; st.rerun()

                # Step 6+: Show Questions
                if current_step >= 6:
                    control_scores = current_comp.get("control_scores", {});
                    # Still use 'writing_style' to access data from study_data.json
                    tone_traits = list(control_scores.get("tone", {}).keys())
                    style_traits = list(control_scores.get("writing_style", {}).keys())
                    main_style_trait = style_traits[0] if style_traits else None

                    terms_to_define.update(tone_traits); terms_to_define.update(style_traits)

                    def format_part2_traits(traits):
                        hl = [f"<b class='highlight-trait'>{t}</b>" for t in traits if t]
                        return " and ".join(hl) if hl else ""

                    tone_str = format_part2_traits(tone_traits)
                    style_str = format_part2_traits(style_traits) # Format all styles identified in data

                    # --- Generate questions list dynamically for Part 2 ---
                    part2_questions = []
                    for q_template in q_templates:
                        q_id = q_template['id']
                        q_text = ""
                        if q_id == 'q2_style':
                            style_q_config = q_template # q_template is the config for q2_style
                            default_text = style_q_config.get("default_text", "Which caption's style is more {}?")
                            override = style_q_config.get("overrides", {}).get(main_style_trait, {})
                            text_template = override.get("text", default_text)
                            # Use style_str (all styles) if formatting needed, else use override directly
                            q_text = text_template.format(style_str) if "{}" in text_template else text_template
                        elif q_id == 'q1_tone':
                             q_text = q_template['text'].format(tone_str)
                        else: # q3_accuracy, q4_preference don't need formatting
                             q_text = q_template['text']
                        part2_questions.append({"id": q_id, "text": q_text})
                    # --- End dynamic generation ---

                    options = ["Caption A", "Caption B", "Both Equal / Neither", "Cannot Determine"] # Adjusted options

                    interacted_state = st.session_state[view_state_key].get('interacted', {})
                    num_interacted = sum(1 for flag in interacted_state.values() if flag)
                    questions_to_show = num_interacted + 1

                    question_cols = st.columns(len(part2_questions)) # Dynamic columns based on number of questions

                    def render_radio(q, col, q_index, view_key_arg):
                        with col:
                            st.markdown(f"<div class='slider-label'><strong>{q_index + 1}. {q['text']}</strong></div>", unsafe_allow_html=True)
                            st.radio(q['text'], options, index=None, label_visibility="collapsed", key=f"p2_{comparison_id}_{q['id']}", on_change=mark_p2_interacted, args=(q['id'], view_key_arg))

                    # Render questions progressively
                    for i, q in enumerate(part2_questions):
                         if questions_to_show > i:
                              render_radio(q, question_cols[i], i, view_key_arg)


                    # Show submit button only when all questions are potentially visible
                    if questions_to_show > len(part2_questions):
                        # st.button("<< Previous", ...) # REMOVED

                        if st.button("Submit Comparison", key=f"submit_comp_{comparison_id}"):
                            responses = {q['id']: st.session_state.get(f"p2_{comparison_id}_{q['id']}") for q in part2_questions}
                            if any(choice is None for choice in responses.values()):
                                validation_placeholder.warning("⚠️ Please answer all questions before submitting.")
                            else:
                                with st.spinner("Saving response..."):
                                    all_saved = True
                                    for q_id, choice in responses.items():
                                        # Use the dynamically generated question text for saving
                                        full_q_text = next((q['text'] for q in part2_questions if q['id'] == q_id), "N/A")
                                        if not save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_comp, current_comp, choice, 'user_study_part2', full_q_text):
                                            all_saved = False; break
                                    if all_saved:
                                        st.session_state.current_comparison_index += 1; st.session_state.pop(view_state_key, None); st.rerun()
                                    else:
                                         st.error("Failed to save all responses. Please try again.")

                    definitions = st.session_state.all_data.get('definitions', {})
                    reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {definitions.get(term, 'Definition not found.')}</li>" for term in sorted(list(terms_to_define)) if term) + "</ul></div>"
                    st.markdown(reference_html, unsafe_allow_html=True)
    # --- End Part 2 ---

    # --- Part 3 ---
    elif st.session_state.study_part == 3:
        all_changes = st.session_state.all_data['study'].get('part3_intensity_change', [])
        change_idx = st.session_state.current_change_index
        if change_idx >= len(all_changes): st.session_state.page = 'final_thank_you'; st.rerun()

        current_change = all_changes[change_idx]; change_id = current_change['change_id']
        field_to_change = current_change.get('field_to_change', {});
        field_type = list(field_to_change.keys())[0] if field_to_change else None
        timer_finished_key = f"timer_finished_p3_{change_id}"

        if not field_type: # Skip item if data is malformed
            st.warning(f"Skipping item {change_id} due to missing 'field_to_change'.")
            st.session_state.current_change_index += 1
            st.rerun()

        # Video watching step
        if not st.session_state.get(timer_finished_key, False):
            st.subheader("Watch the video")
            st.button("DEBUG: Skip Video >>", on_click=lambda k=timer_finished_key: st.session_state.update({k: True}) or st.rerun(), key=f"skip_video_p3_{change_id}")
            with st.spinner("Video playing..."):
                main_col, _ = st.columns([1, 1.8])
                with main_col:
                    video_path = current_change.get('video_path')
                    if video_path and os.path.exists(video_path):
                         if current_change.get("orientation") == "portrait":
                             _, vid_col, _ = st.columns([1, 3, 1])
                             with vid_col: st.video(video_path, autoplay=True, muted=True)
                         else: st.video(video_path, autoplay=True, muted=True)
                    else: st.warning(f"Video not found for {change_id}")
                    duration = current_change.get('duration', 1); time.sleep(duration)
            if not st.session_state.get(timer_finished_key, False):
                st.session_state[timer_finished_key] = True; st.rerun()
        else: # Post-video steps
            view_state_key = f"view_state_p3_{change_id}"; summary_typed_key = f"summary_typed_p3_{change_id}"
            if view_state_key not in st.session_state:
                st.session_state[view_state_key] = {'step': 1, 'summary_typed': False, 'comp_feedback': False, 'comp_choice': None}
            current_step = st.session_state[view_state_key]['step']

            title_col1, title_col2 = st.columns([1, 1.8])
            with title_col1: st.subheader("Video")
            with title_col2:
                if current_step >= 5:
                    display_field = "Style" if field_type == 'writing_style' else field_type.title()
                    st.subheader(f"{display_field} Intensity Change") # Changed Title


            col1, col2 = st.columns([1, 1.8])
            with col1: # Video and Summary
                video_path = current_change.get('video_path')
                if video_path and os.path.exists(video_path):
                    if current_change.get("orientation") == "portrait":
                        _, vid_col, _ = st.columns([1, 3, 1])
                        with vid_col: st.video(video_path, autoplay=True, muted=True, loop=True)
                    else: st.video(video_path, autoplay=True, muted=True, loop=True)
                else: st.warning(f"Video not found for {change_id}")

                if current_step == 1:
                    if st.button("Proceed to Summary", key=f"p3_proceed_summary_{change_id}"):
                        st.session_state[view_state_key]['step'] = 2; st.rerun()
                if current_step >= 2:
                    st.subheader("Video Summary")
                    if st.session_state.get(summary_typed_key, False): st.info(current_change["video_summary"])
                    else:
                        with st.empty(): st.write_stream(stream_text(current_change["video_summary"]))
                        st.session_state[summary_typed_key] = True

                    if current_step == 2:
                       # st.button("<< Previous", ...) # REMOVED
                       if current_change.get('distractor_answers'): # Check if comp quiz exists
                           if st.button("Proceed to Comprehension Question", key=f"p3_proceed_captions_{change_id}"):
                               st.session_state[view_state_key]['step'] = 3; st.rerun()
                       else: # Skip comp quiz
                            if st.button("Proceed to Captions", key=f"p3_skip_comp_{change_id}"):
                                st.session_state[view_state_key]['step'] = 5; st.rerun() # Go directly to caption display

                if current_step < 6:
                    st.button("DEBUG: Skip to Questions >>", on_click=skip_to_questions, args=(view_state_key, summary_typed_key), key=f"skip_to_q_p3_{change_id}")

            with col2: # Captions and Questions
                # Step 3/4: Comp Quiz
                if (current_step == 3 or current_step == 4) and current_change.get('distractor_answers'):
                    render_comprehension_quiz(current_change, view_state_key, proceed_step=5) # Go to step 5 after quiz

                # Step 5: Show Captions
                if current_step >= 5:
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_change["caption_A"]}</p></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_change["caption_B"]}</p></div>', unsafe_allow_html=True)
                    if current_step == 5:
                        # st.button("<< Previous", ...) # REMOVED
                        if st.button("Show Questions", key=f"p3_show_q_{change_id}"):
                            st.session_state[view_state_key]['step'] = 6; st.rerun()

                # Step 6+: Show Questions
                if current_step >= 6:
                    terms_to_define = set()
                    trait = field_to_change.get(field_type)
                    if trait: terms_to_define.add(trait)

                    form_submitted_key = f"form_submitted_{change_idx}"
                    if form_submitted_key not in st.session_state:
                         st.session_state[form_submitted_key] = False

                    with st.form(key=f"study_form_change_{change_idx}"):
                        # Use correct key "Style"
                        q_template_key = "Style" if field_type == 'writing_style' else field_type.title()
                        q_template = st.session_state.all_data['questions']['part3_questions'].get(q_template_key, "Question template not found for {}")

                        highlighted_trait = f"<b class='highlight-trait'>{trait}</b>" if trait else "the trait"
                        dynamic_question_raw = q_template.format(highlighted_trait, change_type=current_change.get('change_type', 'changed'))
                        dynamic_question_save = re.sub('<[^<]+?>', '', dynamic_question_raw) # Save cleaned text
                        q2_text = "Is the core factual content consistent across both captions?"

                        col_q1, col_q2 = st.columns(2)
                        with col_q1:
                            st.markdown(f'<div class="part3-question-text">1. {dynamic_question_raw}</div>', unsafe_allow_html=True)
                            choice1 = st.radio("q1_label", ["Yes", "No"], index=None, horizontal=True, key=f"{change_id}_q1", label_visibility="collapsed")
                        with col_q2:
                            st.markdown(f"<div class='part3-question-text'>2. {q2_text}</div>", unsafe_allow_html=True)
                            choice2 = st.radio("q2_label", ["Yes", "No"], index=None, horizontal=True, key=f"{change_id}_q2", label_visibility="collapsed")

                        # --- MODIFIED BUTTON ---
                        submitted = st.form_submit_button("Submit Answers") # Removed use_container_width=True
                        if submitted: st.session_state[form_submitted_key] = True

                    # Previous button outside form
                    # st.button("<< Previous", ...) # REMOVED


                    # Process submission *after* rendering the Previous button
                    if st.session_state.get(form_submitted_key, False): # Check if form was submitted
                        choice1 = st.session_state.get(f"{change_id}_q1")
                        choice2 = st.session_state.get(f"{change_id}_q2")
                        if choice1 is None or choice2 is None:
                            st.error("Please answer both questions.")
                            st.session_state[form_submitted_key] = False # Reset flag if invalid
                        else:
                            with st.spinner("Saving response..."):
                                success1 = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice1, 'user_study_part3', dynamic_question_save)
                                success2 = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice2, 'user_study_part3', q2_text)
                            st.session_state.pop(form_submitted_key, None) # Remove flag after processing
                            if success1 and success2:
                                st.session_state.current_change_index += 1; st.session_state.pop(view_state_key, None); st.rerun()
                            else:
                                st.error("Failed to save response. Please try again.")


                    definitions = st.session_state.all_data.get('definitions', {})
                    reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {definitions.get(term, 'Definition not found.')}</li>" for term in sorted(list(terms_to_define)) if term) + "</ul></div>"
                    st.markdown(reference_html, unsafe_allow_html=True)
    # --- End Part 3 ---

elif st.session_state.page == 'final_thank_you':
    st.title("Study Complete! Thank You!")
    st.success("You have successfully completed all parts of the study. We sincerely appreciate your time and valuable contribution to our research!")

# --- JavaScript for Keyboard Navigation ---
js_script = """
const parent_document = window.parent.document;

// Ensure listener isn't added multiple times by checking for a flag
if (!parent_document.arrowKeyListenerAttached) {
    console.log("Attaching ArrowRight key listener.");
    parent_document.addEventListener('keyup', function(event) {
        const activeElement = parent_document.activeElement;
        // Check if focus is inside an input, textarea, or slider
        if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA' || activeElement.getAttribute('role') === 'slider')) {
            return; // Don't trigger button clicks if typing or sliding
        }

        if (event.key === 'ArrowRight') {
            event.preventDefault(); // Prevent default browser behavior if any
            const targetButtonLabels = [
                "Submit Ratings", "Submit Comparison", "Submit Answers",
                "Submit Answer", "Next Question", "Show Questions",
                "Proceed to Caption(s)", // Covers variations
                "Proceed to Summary", "Proceed to Question", "Proceed to User Study",
                "Take Quiz Again", "Submit", "Next >>", "Start Quiz", "Next",
                "DEBUG: Skip Video >>", "DEBUG: Skip to Questions >>", "Skip to Questions >>" // Include new skip button
            ];
            const allButtons = Array.from(parent_document.querySelectorAll('button'));
            // Filter only visible buttons to avoid clicking hidden ones
            const visibleButtons = allButtons.filter(btn => btn.offsetParent !== null);

            // Find the *last* visible button matching any label (most likely the primary action)
            let buttonToClick = null;
            for (const label of targetButtonLabels) {
                 const foundButton = [...visibleButtons].reverse().find(btn => btn.textContent.trim().includes(label));
                 if (foundButton) {
                     buttonToClick = foundButton;
                     break; // Stop searching once a suitable button is found
                 }
            }

            if (buttonToClick) {
                console.log('ArrowRight detected, clicking button:', buttonToClick.textContent);
                buttonToClick.click();
            } else {
                 console.log('ArrowRight detected, but no target button found.');
            }
        }
    });
    parent_document.arrowKeyListenerAttached = true; // Set flag
} else {
     console.log("ArrowRight key listener already attached.");
}
"""
# Use a unique key to ensure JS re-runs if the script changes
streamlit_js_eval(js_expressions=js_script, key="keyboard_listener_v6") # Incremented key