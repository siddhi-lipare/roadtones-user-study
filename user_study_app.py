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
# import traceback # No longer needed for standard operation

# --- Configuration ---
INTRO_VIDEO_PATH = "media/start_video_slower.mp4"
STUDY_DATA_PATH = "study_data.json" # Assumes this file now has swapped part2/part3 data
QUIZ_DATA_PATH = "quiz_data.json"
INSTRUCTIONS_PATH = "instructions.json"
QUESTIONS_DATA_PATH = "questions.json" # Assumes this file now has swapped part2/part3 questions
DEFINITIONS_PATH = "definitions.json"
LOCAL_BACKUP_FILE = "responses_backup.jsonl"

# --- JAVASCRIPT FOR ANIMATION ---
JS_ANIMATION_RESET = """
    // Reset caption highlight
    const elements = window.parent.document.querySelectorAll('.new-caption-highlight');
    elements.forEach(el => {
        el.style.animation = 'none';
        el.offsetHeight; /* trigger reflow */
        el.style.animation = null;
    });

    // Find and animate specific buttons
    const buttonLabelsToHighlight = [
        "Proceed to Summary",
        "Proceed to Question",
        "Proceed to Caption(s)",
        "Show Questions",
        "Next Question",
        "Finish Quiz"
    ];
    const allButtons = window.parent.document.querySelectorAll('div[data-testid="stButton"] > button');
    allButtons.forEach(btn => {
        const buttonText = btn.textContent.trim();
        if (buttonLabelsToHighlight.includes(buttonText)) {
            btn.style.animation = 'none';
            btn.offsetHeight; /* trigger reflow */
            btn.style.animation = 'highlight-button-new 1.5s ease-out forwards'; // Use the NEW button animation
        }
    });
"""

# --- GOOGLE SHEETS & HELPERS ---
@st.cache_resource # Re-enabled caching
def connect_to_gsheet():
    """Connects to the Google Sheet using Streamlit secrets."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open("roadtones-streamlit-userstudy-responses")
        return spreadsheet.sheet1
    except Exception as e:
        # Keep error for connection failure, but no traceback for user
        st.error(f"Failed to connect to Google Sheets: {e}")
        return None


def save_response_locally(response_dict):
    """Saves a response dictionary to a local JSONL file as a fallback."""
    try:
        with open(LOCAL_BACKUP_FILE, "a") as f:
            f.write(json.dumps(response_dict) + "\n")
        return True
    except Exception as e:
        st.error(f"Critical Error: Could not save response to local backup file. {e}")
        return False

def save_response(email, age, gender, video_data, caption_data, choice, study_phase, question_text, was_correct=None):
    """Saves a response to Google Sheets, with a local JSONL fallback."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    response_dict = {
        'email': email, 'age': age, 'gender': str(gender), 'timestamp': timestamp,
        'study_phase': study_phase, 'video_id': video_data.get('video_id', 'N/A'),
        'sample_id': caption_data.get('caption_id') or caption_data.get('comparison_id') or caption_data.get('change_id') or caption_data.get('sample_id'),
        'question_text': question_text, 'user_choice': str(choice),
        'was_correct': str(was_correct) if was_correct is not None else 'N/A',
        'attempts_taken': 1 if study_phase == 'quiz' else 'N/A'
    }

    worksheet = connect_to_gsheet() # Will show error if connection fails

    if worksheet:
        try:
            # Check if worksheet is empty to add header row
            header_needed = False
            try:
                # Use a more robust check for emptiness
                cell_list = worksheet.range('A1:A1')
                if not cell_list[0].value:
                    header_needed = True
            except gspread.exceptions.APIError as api_error:
                 st.warning(f"API Error checking sheet emptiness: {api_error}. Assuming header needed.") # Warning is okay here
                 header_needed = True
            except Exception as check_err:
                 st.warning(f"Error checking sheet emptiness: {check_err}. Assuming header needed.") # Warning is okay here
                 header_needed = True

            if header_needed:
                worksheet.append_row(list(response_dict.keys()))

            worksheet.append_row(list(response_dict.values()))
            return True
        except Exception as e:
            # Show error for append failure, but no traceback for user
            st.error(f"Could not save to Google Sheets (append error): {e}. Saving a local backup.")
            return save_response_locally(response_dict)
    else:
        # Error already shown in connect_to_gsheet if connection failed
        st.error("Connection to Google Sheets failed. Saving a local backup.")
        return save_response_locally(response_dict)

@st.cache_data
def get_video_metadata(path):
    """Reads a video file and returns its orientation and duration."""
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            # Default values if video can't be opened
            return {"orientation": "landscape", "duration": 10}
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        orientation = "portrait" if height > width else "landscape"
        duration = math.ceil(frame_count / fps) if fps > 0 and frame_count > 0 else 10 # Default duration if metadata is invalid
        return {"orientation": orientation, "duration": duration}
    except Exception:
        # Fallback in case of any error during processing
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
    for key, path in required_files.items():
        if not os.path.exists(path):
            st.error(f"Error: Required data file not found at '{path}'.")
            return None
        with open(path, 'r', encoding='utf-8') as f: data[key] = json.load(f)

    if not os.path.exists(INTRO_VIDEO_PATH):
        st.error(f"Error: Intro video not found at '{INTRO_VIDEO_PATH}'.")
        return None

    # Flatten definitions from JSON
    flat_definitions = {}
    flat_definitions.update(data['definitions'].get('tones', {}))
    flat_definitions.update(data['definitions'].get('writing_styles', {}))
    flat_definitions.update(data['definitions'].get('applications', {}))
    data['all_definitions'] = flat_definitions

    # Get metadata for study videos
    for part_key in data['study']:
        for item in data['study'][part_key]:
            if 'video_path' in item and os.path.exists(item['video_path']):
                metadata = get_video_metadata(item['video_path'])
                item['orientation'] = metadata['orientation']
                item['duration'] = metadata['duration']
            else:
                # Default values if path is missing or invalid
                item['orientation'] = 'landscape'
                item['duration'] = 10

    # Get metadata for quiz videos
    for part_key in data['quiz']:
         for item in data['quiz'][part_key]:
            if 'video_path' in item and os.path.exists(item['video_path']):
                metadata = get_video_metadata(item['video_path'])
                item['orientation'] = metadata['orientation']
                item['duration'] = metadata['duration']
            else:
                # Default values if path is missing or invalid
                item['orientation'] = 'landscape'
                item['duration'] = 10
    return data

# --- UI & STYLING ---
# (Keep the CSS styling block exactly as it was in the previous version)
st.set_page_config(layout="wide", page_title="Tone-controlled Video Captioning")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&display=swap');
@keyframes highlight-new { 0% { border-color: transparent; box-shadow: none; } 25% { border-color: #facc15; box-shadow: 0 0 8px #facc15; } 75% { border-color: #facc15; box-shadow: 0 0 8px #facc15; } 100% { border-color: transparent; box-shadow: none; } }
.part1-caption-box { border-radius: 10px; padding: 1rem 1.5rem; margin-bottom: 0.5rem; border: 2px solid transparent; transition: border-color 0.3s ease; }
.new-caption-highlight { animation: highlight-new 1.5s ease-out forwards; }
.slider-label {
    height: 80px;
    margin-bottom: 0.5rem; /* MODIFIED: Was 0 */
    font-size: 1.05rem;
    font-weight: 600; /* Semi-bold */
    font-family: 'Inter', sans-serif; /* Explicitly use Inter */
}
.highlight-trait { color: #4f46e5; font-weight: 600; }
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

.part3-question-text {
    font-size: 1.05rem;
    font-weight: 600; /* Semi-bold */
    margin-bottom: 0.5rem;
    font-family: 'Inter', sans-serif; /* Explicitly use Inter */
    height: 70px; /* ADDED: To ensure alignment of radio buttons below */
}

/* --- Title font consistency --- */
h2 {
    font-size: 1.75rem !important;
    font-weight: 600 !important;
}

/* --- ADDED FOR BUTTON HIGHLIGHT --- */
@keyframes highlight-button-new {
  0% {
    border-color: #D1D5DB; /* Start with default border */
    box-shadow: none;
  }
  25% {
    border-color: #facc15; /* Golden highlight border */
    box-shadow: 0 0 8px #facc15; /* Golden glow */
  }
  75% {
    border-color: #facc15;
    box-shadow: 0 0 8px #facc15;
  }
  100% {
    border-color: #D1D5DB; /* End with default border */
    box-shadow: none;
  }
}
body[theme="dark"] @keyframes highlight-button-new {
    0% {
        border-color: #4B5563; /* Start with default dark border */
        box-shadow: none;
    }
    25% {
        border-color: #facc15;
        box-shadow: 0 0 8px #facc15;
    }
    75% {
        border-color: #facc15;
        box-shadow: 0 0 8px #facc15;
    }
    100% {
        border-color: #4B5563; /* End with default dark border */
        box-shadow: none;
    }
}
/* --- END ADDED BLOCK --- */

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
# (Keep handle_next_quiz_question, jump_to_part, jump_to_study_part, jump_to_study_item, restart_quiz functions exactly as they were)
def handle_next_quiz_question(view_key_to_pop):
    part_keys = list(st.session_state.all_data['quiz'].keys())
    current_part_key = part_keys[st.session_state.current_part_index]
    questions_for_part = st.session_state.all_data['quiz'][current_part_key]
    sample = questions_for_part[st.session_state.current_sample_index]
    question_text = "N/A"
    if "Tone Controllability" in current_part_key:
        question_text = f"Intensity of '{sample['tone_to_compare']}' has {sample['comparison_type']}"
    elif "Caption Quality" in current_part_key:
        # Construct the question text based on the current sub-question index
        question_index = st.session_state.current_rating_question_index
        question_text = sample["questions"][question_index]["question_text"]
    else: # Tone Identification
        question_text = "Tone Identification" # Or more specific if needed

    # --- MOVED SAVE RESPONSE OUTSIDE SPINNER ---
    # success = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, sample, sample, st.session_state.last_choice, 'quiz', question_text, was_correct=st.session_state.is_correct)
    # if not success:
    #    st.error("Failed to save response. Please check your connection and try again.")
    #    return # Don't proceed if save fails

    # --- Logic to advance quiz state ---
    if "Caption Quality" in current_part_key:
        st.session_state.current_rating_question_index += 1
        # Check if we finished all questions for the current sample
        if st.session_state.current_rating_question_index >= len(sample["questions"]):
            st.session_state.current_sample_index += 1 # Move to next sample
            st.session_state.current_rating_question_index = 0 # Reset sub-question index
            # Check if we finished all samples in the current part
            if st.session_state.current_sample_index >= len(questions_for_part):
                 st.session_state.current_part_index += 1 # Move to next part
                 st.session_state.current_sample_index = 0 # Reset sample index
    else: # For other quiz parts (Tone ID, Controllability)
        st.session_state.current_sample_index += 1
        # Check if we finished all samples in the current part
        if st.session_state.current_sample_index >= len(questions_for_part):
            st.session_state.current_part_index += 1 # Move to next part
            st.session_state.current_sample_index = 0 # Reset sample index

    # Clear state specific to the previous question view
    st.session_state.pop(view_key_to_pop, None)
    st.session_state.show_feedback = False # Hide feedback for the next question

def jump_to_part(part_index):
    st.session_state.current_part_index = part_index
    st.session_state.current_sample_index = 0
    st.session_state.current_rating_question_index = 0 # Reset for Caption Quality part
    st.session_state.show_feedback = False

def jump_to_study_part(part_number):
    st.session_state.study_part = part_number
    # Reset all study indices when jumping between main parts
    st.session_state.current_video_index = 0
    st.session_state.current_caption_index = 0
    st.session_state.current_comparison_index = 0
    st.session_state.current_change_index = 0

# --- MODIFIED --- Swap logic in jump_to_study_item
def jump_to_study_item(part_number, item_index):
    """Jumps to a specific item index within a study part."""
    st.session_state.study_part = part_number

    # Set target part's index
    if part_number == 1:
        st.session_state.current_video_index = item_index
        st.session_state.current_caption_index = 0 # Always start at first caption
    elif part_number == 2: # Part 2 is now Intensity Change
        st.session_state.current_change_index = item_index
    elif part_number == 3: # Part 3 is now Comparison
        st.session_state.current_comparison_index = item_index

    # Reset other parts' indices to avoid confusion
    if part_number != 1:
        st.session_state.current_video_index = 0
        st.session_state.current_caption_index = 0
    if part_number != 2: # Reset Intensity Change if not Part 2
        st.session_state.current_change_index = 0
    if part_number != 3: # Reset Comparison if not Part 3
        st.session_state.current_comparison_index = 0
# --- END MODIFIED ---

def restart_quiz():
    st.session_state.page = 'quiz'
    st.session_state.current_part_index = 0
    st.session_state.current_sample_index = 0
    st.session_state.current_rating_question_index = 0
    st.session_state.show_feedback = False
    st.session_state.score = 0
    st.session_state.score_saved = False # Reset score saved flag if implemented

def render_comprehension_quiz(sample, view_state_key, proceed_step):
    options_key = f"{view_state_key}_comp_options"
    if options_key not in st.session_state:
        options = sample['distractor_answers'] + [sample['road_event_answer']]
        random.shuffle(options)
        st.session_state[options_key] = options
    else:
        options = st.session_state[options_key]

    st.markdown("##### Based on the video and summary, describe what is happening in the video")

    if st.session_state[view_state_key]['comp_feedback']:
        user_choice = st.session_state[view_state_key]['comp_choice']
        correct_answer = sample['road_event_answer']

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
        # Use a unique key for the button based on sample_id
        unique_key = f"proceed_to_captions_{sample.get('sample_id', 'unknown')}"
        if st.button("Proceed to Caption(s)", key=unique_key):
            st.session_state[view_state_key]['step'] = proceed_step
            # --- ADDED: Mark video as watched ---
            video_id = sample.get('video_id')
            if video_id:
                st.session_state.comprehension_passed_video_ids.add(video_id)
            # --- END ADDED ---
            st.rerun()
        # --- ADDED LINE ---
        streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_comp_{sample.get('sample_id', 'unknown')}")
        # --- END ADDED LINE ---
    else:
        # Use a unique key for the form based on sample_id
        form_key = f"comp_quiz_form_{sample.get('sample_id', 'unknown')}"
        with st.form(key=form_key):
             # Use a unique key for the radio button based on sample_id
            radio_key = f"comp_radio_{sample.get('sample_id', 'unknown')}"
            choice = st.radio("Select one option:", options, key=radio_key, index=None, label_visibility="collapsed")
            if st.form_submit_button("Submit"):
                if choice:
                    st.session_state[view_state_key]['comp_choice'] = choice
                    st.session_state[view_state_key]['comp_feedback'] = True
                    st.rerun()
                else:
                    st.error("Please select an answer.")

# --- Main App ---
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
    st.session_state.comprehension_passed_video_ids = set() # --- ADDED ---
    st.session_state.all_data = load_data() # Load data once at the start

if st.session_state.all_data is None:
    st.error("Failed to load application data. Please check file paths and ensure JSON files are valid.")
    st.stop() # Stop execution if essential data is missing

# --- Page Rendering Logic ---
# (Keep demographics, intro_video, what_is_tone, factual_info pages exactly as they were)
if st.session_state.page == 'demographics':
    st.title("Tone-controlled Video Captioning")
    # Debug skip button
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

    if st.checkbox("I am over 18 and agree to participate in this study. I understand my responses will be recorded anonymously."):
        if st.button("Next"):
            # Basic email validation
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not all([email, age, gender]):
                st.error("Please fill in all fields to continue.")
            elif not re.match(email_regex, email):
                st.error("Please enter a valid email address.")
            else:
                st.session_state.email = email
                st.session_state.age = age
                st.session_state.gender = gender
                st.session_state.page = 'intro_video' # Proceed to next page
                st.rerun()

elif st.session_state.page == 'intro_video':
    st.title("Introductory Video")
    _ , vid_col, _ = st.columns([1, 3, 1]) # Center the video column
    with vid_col:
        st.video(INTRO_VIDEO_PATH, autoplay=True, muted=True)
    if st.button("Next >>"):
        st.session_state.page = 'what_is_tone'
        st.rerun()

elif st.session_state.page == 'what_is_tone':
    st.markdown("<h1 style='text-align: center;'>Tone and Writing Style</h1>", unsafe_allow_html=True)

    st.markdown("<p style='text-align: center; font-size: 1.1rem;'><b>Tone</b> refers to the author's attitude or feeling about a subject, reflecting their emotional character (e.g., Sarcastic, Angry, Caring).</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.1rem;'><b>Writing Style</b> refers to the author's technique or method of writing (e.g., Advisory, Factual, Conversational).</p>", unsafe_allow_html=True)

    spacer, title = st.columns([1, 15]) # Adjust column ratio if needed
    with title:
        st.subheader("For example:")

    # --- MODIFIED: Added gap="small" ---
    col1, col2 = st.columns([2, 3], gap="small")
    with col1:
        _, vid_col, _ = st.columns([1, 1.5, 1])
        with vid_col:
            video_path = "media/v_1772082398257127647_PAjmPcDqmPNuvb6p.mp4"
            if os.path.exists(video_path):
                st.video(video_path, autoplay=True, muted=True, loop=True)
            else:
                st.warning(f"Video not found at {video_path}")
    with col2:
        image_path = "media/tone_meaning2.jpg"
        if os.path.exists(image_path):
            st.image(image_path)
        else:
            st.warning(f"Image not found at {image_path}")

    # --- MODIFIED BUTTONS: Bottom Left & Right ---
    st.markdown("<br>", unsafe_allow_html=True) # Add a little space
    prev_col, _, next_col = st.columns([1, 5, 1]) # Adjust ratios for left/right placement

    with prev_col:
        if st.button("Prev <<"): # Small button on the left
            st.session_state.page = 'intro_video' # Go back to intro video
            st.rerun()

    with next_col:
        if st.button("Next >>"): # Small button on the right
            st.session_state.page = 'factual_info' # Go to factual info
            st.rerun()
    # --- END MODIFIED BUTTONS ---


elif st.session_state.page == 'factual_info':
    st.markdown("<h1 style='text-align: center;'>How to measure a caption's <span style='color: #4F46E5;'>Factual Accuracy?</span></h1>", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 3], gap="small")
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
            # --- ADDED THIS LINE ---
            st.markdown("<br>", unsafe_allow_html=True) # Add vertical space
            # --- END ADDED LINE ---
            st.image(image_path)
        else:
            st.warning(f"Image not found at {image_path}")

    # --- MODIFIED BUTTONS: Bottom Left & Right ---
    st.markdown("<br>", unsafe_allow_html=True) # Add a little space
    prev_col, _, next_col = st.columns([1, 5, 1]) # Adjust ratios for left/right placement

    with prev_col:
        if st.button("Prev <<"): # Small button on the left
            st.session_state.page = 'what_is_tone' # Go back to what_is_tone
            st.rerun()

    with next_col:
        if st.button("Start Quiz >>"): # Small button on the right
            st.session_state.page = 'quiz'
            st.rerun()


elif st.session_state.page == 'quiz':
    part_keys = list(st.session_state.all_data['quiz'].keys())
    with st.sidebar:
        st.header("Quiz Sections")
        for i, name in enumerate(part_keys):
            st.button(name, on_click=jump_to_part, args=(i,), use_container_width=True)

    # Check if quiz is completed
    if st.session_state.current_part_index >= len(part_keys):
        st.session_state.page = 'quiz_results'
        st.rerun()

    ALL_DEFINITIONS = st.session_state.all_data['all_definitions']

    current_part_key = part_keys[st.session_state.current_part_index]
    questions_for_part = st.session_state.all_data['quiz'][current_part_key]
    current_sample_index = st.session_state.current_sample_index # Renamed for clarity
    sample = questions_for_part[current_sample_index]
    sample_id = sample.get('sample_id', f'quiz_{current_sample_index}') # Unique ID for state keys

    # --- ADDED BLOCK: Check for specific quiz question to skip steps ---
    is_part2_first_question = (current_part_key == "Part 2: Tone Controllability Evaluation" and current_sample_index == 0)
    # --- END ADDED BLOCK ---

    # --- Initial video play timer ---
    timer_finished_key = f"timer_finished_quiz_{sample_id}"
    # --- Check if it's Caption Quality and NOT the first question for this sample ---
    is_second_quality_question = ("Caption Quality" in current_part_key and st.session_state.current_rating_question_index > 0)

    # Only play video initially if timer isn't finished AND it's not the second quality question
    # --- MODIFIED: Added check for is_part2_first_question ---
    if not st.session_state.get(timer_finished_key, False) and not is_second_quality_question and not is_part2_first_question:
    # --- END MODIFIED ---
        st.subheader("Watch the video")
        with st.spinner(" "): # Added spinner text
            col1, _ = st.columns([1.2, 1.5])
            with col1:
                if sample.get("orientation") == "portrait":
                    _, vid_col, _ = st.columns([1, 3, 1])
                    with vid_col:
                        st.video(sample['video_path'], autoplay=True, muted=True)
                else:
                    st.video(sample['video_path'], autoplay=True, muted=True)
            duration = sample.get('duration', 10) # Get duration from metadata
            time.sleep(duration) # Pause execution for video duration
        st.session_state[timer_finished_key] = True # Mark timer as finished
        st.rerun() # Rerun to proceed to the next step
    else: # Video finished playing or skipped (second quality question)
        # --- State management for steps within a question ---
        view_state_key = f'view_state_{sample_id}'
        if view_state_key not in st.session_state:
            # If it's the second quality question, jump directly to showing questions (step 6)
            initial_step = 6 if is_second_quality_question else 1
            # --- ADDED BLOCK: Override initial_step for the specific quiz question ---
            if is_part2_first_question:
                initial_step = 5 # Jump directly to showing summary/captions
            # --- END ADDED BLOCK ---
            st.session_state[view_state_key] = {'step': initial_step, 'summary_typed': False, 'comp_feedback': False, 'comp_choice': None}
        current_step = st.session_state[view_state_key]['step']

        def stream_text(text):
            for word in text.split(" "): yield word + " "; time.sleep(0.08)

        col1, col2 = st.columns([1.2, 1.5])

        # --- MODIFIED BLOCK ---
        with col1:
            # --- Conditionally display video and summary ---

            # Show "Watch the video" title only if it's the first question and before step 5
            # --- MODIFIED: Added check for is_part2_first_question ---
            if not is_second_quality_question and not is_part2_first_question and current_step < 5:
            # --- END MODIFIED ---
                st.subheader("Watch the video")
            else:
                st.subheader("Video")

            # Always show the video player
            if sample.get("orientation") == "portrait":
                _, vid_col, _ = st.columns([1, 3, 1])
                with vid_col:
                    st.video(sample['video_path'], autoplay=True, muted=True)
            else:
                st.video(sample['video_path'], autoplay=True, muted=True)

            # Show "Proceed to Summary" button only on step 1
            if current_step == 1:
                if st.button("Proceed to Summary", key=f"quiz_summary_{sample_id}"):
                    st.session_state[view_state_key]['step'] = 2
                    st.rerun()
                # --- ADDED LINE ---
                streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_quiz_1_{sample_id}")
                # --- END ADDED LINE ---

            # Show Video Summary if step >= 2 (this now includes step 6 for the second question)
            if current_step >= 2 and "video_summary" in sample:
                st.subheader("Video Summary")
                summary_typed_key = f"{view_state_key}_summary_typed"

                # If summary is already typed (i.e., first question done), just show it
                # --- MODIFIED: Don't stream for part 2 first question ---
                if st.session_state.get(summary_typed_key, False) or is_part2_first_question:
                    st.info(sample["video_summary"])
                    if is_part2_first_question: # Ensure it's marked as typed if we skipped to it
                         st.session_state[summary_typed_key] = True
                # --- END MODIFIED ---
                else:
                    # Otherwise, stream it for the first time
                    with st.empty(): # Use empty container for streaming
                        st.write_stream(stream_text(sample["video_summary"]))
                    st.session_state[summary_typed_key] = True # Mark as typed

                # Show "Proceed to Question" button only on step 2
                if current_step == 2:
                    if st.button("Proceed to Question", key=f"quiz_comp_q_{sample_id}"):
                        st.session_state[view_state_key]['step'] = 3
                        st.rerun()
                    # --- ADDED LINE ---
                    streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_quiz_2_{sample_id}")
                    # --- END ADDED LINE ---
        # --- END MODIFIED BLOCK ---


        with col2:
            display_title = re.sub(r'Part \d+: ', '', current_part_key)
            if "Tone Identification" in current_part_key: display_title = f"{sample.get('category', 'Tone').title()} Identification"
            elif "Tone Controllability" in current_part_key: display_title = f"{sample.get('category', 'Tone').title()} Comparison"

            if current_step >= 5:
                st.subheader(display_title)

            # --- Conditionally render comprehension quiz ---
            # Only show if NOT (Caption Quality part AND second question index > 0)
            # --- MODIFIED: Added check for is_part2_first_question ---
            if not is_second_quality_question and not is_part2_first_question and (current_step == 3 or current_step == 4):
            # --- END MODIFIED ---
                st.markdown("<br><br>", unsafe_allow_html=True)
                render_comprehension_quiz(sample, view_state_key, proceed_step=5)

            # Get the specific question data for Caption Quality part
            question_data = sample["questions"][st.session_state.current_rating_question_index] if "Caption Quality" in current_part_key else sample
            terms_to_define = set()

            # --- Display Caption(s) ---
            if current_step >= 5: # Show captions from step 5 onwards
                if "Tone Controllability" in current_part_key:
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{sample["caption_A"]}</p></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="comparison-caption-box" style="margin-top:0.5rem;"><strong>Caption B</strong><p class="caption-text">{sample["caption_B"]}</p></div>', unsafe_allow_html=True)
                else: # Tone ID and Caption Quality
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption</strong><p class="caption-text">{sample["caption"]}</p></div>', unsafe_allow_html=True)

                # Button to proceed to questions (only relevant if comprehension quiz was shown or if it's the first step)
                if current_step == 5 and not is_second_quality_question:
                     if st.button("Show Questions", key=f"quiz_show_q_{sample_id}"):
                        st.session_state[view_state_key]['step'] = 6
                        st.rerun()
                     # --- ADDED LINE ---
                     streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_quiz_5_{sample_id}")
                     # --- END ADDED LINE ---
                elif current_step == 5 and is_second_quality_question:
                    # Automatically advance if skipping to questions for 2nd quality item
                    st.session_state[view_state_key]['step'] = 6
                    st.rerun()


            # --- Display Question and Handle Submission ---
            if current_step >= 6:
                question_text_display = ""
                # --- Determine Question Text ---
                if "Tone Controllability" in current_part_key:
                    trait = sample['tone_to_compare']
                    change_type = sample['comparison_type']
                    question_text_display = f"From Caption A to B, has the level of <b class='highlight-trait'>{trait}</b> {change_type}?"
                    terms_to_define.add(trait)
                elif "Caption Quality" in current_part_key:
                    raw_text = question_data["question_text"]
                    app_trait = sample.get("application") # Get application from the main sample data
                    if app_trait:
                        terms_to_define.add(app_trait)
                        # Highlight if present in the question text
                        if app_trait in raw_text:
                            question_text_display = raw_text.replace(app_trait, f"<b class='highlight-trait'>{app_trait}</b>")
                        else:
                            question_text_display = raw_text # Use raw text if trait not mentioned
                    else:
                        question_text_display = raw_text # Use raw text if no application trait
                elif question_data.get("question_type") == "multi": # Tone ID Multi-select
                    # --- MODIFIED LINE ---
                    question_text_display = "Identify the <span style='color: #4f46e5;'>2 most dominant</span> tones in the caption"
                    # --- END MODIFIED LINE ---
                    terms_to_define.update(question_data['options'])
                else: # Tone ID Single-select
                    category_text = sample.get('category', 'tone').lower()
                    if category_text == "tone":
                        question_text_display = "What is the most dominant tone in the caption?"
                    elif category_text == "writing style":
                        question_text_display = "What is the most dominant writing style in the caption?"
                    else: # Fallback for other categories
                        question_text_display = f"Identify the most dominant {category_text} in the caption"
                    terms_to_define.update(question_data['options'])

                # Display the question text in a box
                st.markdown(f'<div class="quiz-question-box"><strong>Question {st.session_state.current_rating_question_index + 1 if "Caption Quality" in current_part_key else ""}:</strong><span class="question-text-part">{question_text_display}</span></div>', unsafe_allow_html=True)

                # --- Handle Feedback or Answer Submission ---
                if st.session_state.show_feedback:
                    # Display feedback after submission
                    user_choice, correct_answer = st.session_state.last_choice, question_data.get('correct_answer')
                    # Ensure choices are lists for comparison consistency
                    if not isinstance(user_choice, list): user_choice = [user_choice]
                    if not isinstance(correct_answer, list): correct_answer = [correct_answer]

                    st.write(" ") # Spacer
                    # Iterate through options to show correct/incorrect styling
                    for opt in question_data['options']:
                        is_correct = opt in correct_answer
                        is_user_choice = opt in user_choice
                        css_class = "correct-answer" if is_correct else ("wrong-answer" if is_user_choice else "normal-answer")
                        display_text = f"<strong>{opt} (Correct Answer)</strong>" if is_correct else (f"{opt} (Your selection)" if is_user_choice else opt)
                        st.markdown(f'<div class="feedback-option {css_class}">{display_text}</div>', unsafe_allow_html=True)

                    st.info(f"**Explanation:** {question_data['explanation']}")

                    # --- MODIFICATION: Check if it's the last question ---
                    is_last_part = st.session_state.current_part_index == (len(part_keys) - 1)
                    is_last_sample_in_part = st.session_state.current_sample_index == (len(questions_for_part) - 1)

                    is_last_question = False
                    if "Caption Quality" in current_part_key:
                        is_last_sub_question = st.session_state.current_rating_question_index == (len(sample["questions"]) - 1)
                        if is_last_part and is_last_sample_in_part and is_last_sub_question:
                            is_last_question = True
                    else:
                        if is_last_part and is_last_sample_in_part:
                            is_last_question = True

                    button_text = "Finish Quiz" if is_last_question else "Next Question"
                    # --- END MODIFICATION ---

                    st.button(button_text, key=f"quiz_next_q_{sample_id}_{st.session_state.current_rating_question_index}", on_click=handle_next_quiz_question, args=(view_state_key,)) # Unique key per question
                    # --- ADDED LINE ---
                    streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_quiz_next_{sample_id}")
                    # --- END ADDED LINE ---
                else:
                    # Display answer options form
                    # Use unique key including sample_id and question index if applicable
                    form_key = f"quiz_form_{sample_id}_{st.session_state.current_rating_question_index if 'Caption Quality' in current_part_key else ''}"
                    with st.form(form_key):
                        choice = None
                        radio_key = f"radio_{sample_id}_{st.session_state.current_rating_question_index if 'Caption Quality' in current_part_key else ''}" # Unique key
                        if question_data.get("question_type") == "multi":
                            st.write("Select exactly 2 options:")
                            # Use unique keys for checkboxes
                            choice = [opt for opt in question_data['options'] if st.checkbox(opt, key=f"cb_{sample_id}_{opt}_{st.session_state.current_rating_question_index if 'Caption Quality' in current_part_key else ''}")]
                        else: # Single choice radio
                            choice = st.radio("Select one option:", question_data['options'], key=radio_key, index=None, label_visibility="collapsed")

                        submitted = st.form_submit_button("Submit Answer")

                    # --- MODIFIED: Add spinner around processing ---
                    if submitted:
                        # Validation
                        valid_submission = True
                        if not choice:
                            st.error("Please select an option.")
                            valid_submission = False
                        elif question_data.get("question_type") == "multi" and len(choice) != 2:
                            st.error("Please select exactly 2 options.")
                            valid_submission = False

                        if valid_submission:
                            with st.spinner("Saving response..."): # Spinner added here
                                # Process correct submission
                                st.session_state.last_choice = choice
                                correct_answer = question_data.get('correct_answer')
                                # Check correctness (handle list or single answer)
                                is_correct = (set(choice) == set(correct_answer)) if isinstance(correct_answer, list) else (choice == correct_answer)
                                st.session_state.is_correct = is_correct
                                if is_correct: st.session_state.score += 1 # Increment score

                                # --- Save response INSIDE spinner ---
                                question_text_for_save = "N/A"
                                if "Tone Controllability" in current_part_key:
                                    question_text_for_save = f"Intensity of '{sample['tone_to_compare']}' has {sample['comparison_type']}"
                                elif "Caption Quality" in current_part_key:
                                    question_text_for_save = question_data["question_text"]
                                else: # Tone Identification
                                     question_text_for_save = f"Identify dominant {'/'.join(sample.get('category','tone').split())}" # More specific default


                                success = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, sample, sample, choice, 'quiz', question_text_for_save, was_correct=is_correct)
                                # --- End save response ---

                                if success:
                                    st.session_state.show_feedback = True # Set flag to show feedback AFTER saving
                                else:
                                     st.error("Failed to save response. Please check connection/permissions and try again.")
                                     # Optionally reset state or prevent rerun if save fails critically
                            st.rerun() # Rerun to display feedback or keep form if save failed
                    # --- END MODIFIED ---

                # --- Display Reference Box ---
                if terms_to_define:
                    reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {ALL_DEFINITIONS.get(term, 'Definition not found.')}</li>" for term in sorted(list(terms_to_define)) if ALL_DEFINITIONS.get(term)) + "</ul></div>" # Added fallback text
                    st.markdown(reference_html, unsafe_allow_html=True)


elif st.session_state.page == 'quiz_results':
    # Calculate total scorable questions accurately
    total_scorable_questions = 0
    for p_name, q_list in st.session_state.all_data['quiz'].items():
        if "Caption Quality" in p_name:
            # For Caption Quality, count sub-questions within each sample
            total_scorable_questions += sum(len(item.get("questions", [])) for item in q_list)
        else:
            # For other parts, count the number of samples (each sample is one question)
            total_scorable_questions += len(q_list)

    passing_score = 5 # Define passing score
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

elif st.session_state.page == 'user_study_main':
    # (Keep user_study_main page logic exactly as it was, including the skip logic for repeated videos)
    if not st.session_state.all_data: st.error("Data could not be loaded."); st.stop()

    ALL_DEFINITIONS = st.session_state.all_data['all_definitions']

    def stream_text(text):
        for word in text.split(" "): yield word + " "; time.sleep(0.08)

    # --- MODIFIED: Sidebar logic reflects new Part 2/3 order ---
    with st.sidebar:
        st.header("Study Sections")
        st.button("Part 1: Caption Rating", on_click=jump_to_study_part, args=(1,), use_container_width=True)
        # Button label says "Part 2", jumps to part 2 (Intensity Change)
        st.button("Part 2: Tone Intensity Change", on_click=jump_to_study_part, args=(2,), use_container_width=True)
        # Button label says "Part 3", jumps to part 3 (Comparison)
        st.button("Part 3: Caption Comparison", on_click=jump_to_study_part, args=(3,), use_container_width=True)

        st.divider()

        with st.expander("Jump to Item", expanded=True):
            if st.session_state.study_part == 1:
                all_videos = st.session_state.all_data['study']['part1_ratings']
                for i, video in enumerate(all_videos):
                    video_id = video['video_id']
                    st.button(f"`{video_id}`", key=f"jump_vid_{video_id}", use_container_width=True,
                              on_click=jump_to_study_item, args=(1, i))

            # Show Intensity Change items when study_part is 2
            elif st.session_state.study_part == 2:
                # Use the correct key for Intensity Change data (now part2)
                all_changes = st.session_state.all_data['study']['part2_intensity_change']
                for i, change in enumerate(all_changes):
                    change_id = change['change_id']
                    st.button(f"`{change_id}`", key=f"jump_chg_{change_id}", use_container_width=True,
                              on_click=jump_to_study_item, args=(2, i)) # Jumps to part 2

            # Show Comparison items when study_part is 3
            elif st.session_state.study_part == 3:
                # Use the correct key for Comparison data (now part3)
                all_comparisons = st.session_state.all_data['study']['part3_comparisons']
                for i, comp in enumerate(all_comparisons):
                    comp_id = comp['comparison_id']
                    st.button(f"`{comp_id}`", key=f"jump_comp_{comp_id}", use_container_width=True,
                              on_click=jump_to_study_item, args=(3, i)) # Jumps to part 3
    # --- END MODIFIED ---

    # --- MODIFIED: Main content logic swapped ---

    # Part 1: Caption Rating (Remains mostly the same)
    if st.session_state.study_part == 1:
        all_videos = st.session_state.all_data['study']['part1_ratings']
        video_idx, caption_idx = st.session_state.current_video_index, st.session_state.current_caption_index
        # --- Progression updated ---
        if video_idx >= len(all_videos):
            st.session_state.study_part = 2 # Go to Intensity Change (now Part 2) next
            st.rerun()
        # --- End Progression update ---

        current_video = all_videos[video_idx]
        video_id = current_video['video_id']
        timer_finished_key = f"timer_finished_{video_id}"
        # --- ADDED ---
        has_been_watched = video_id in st.session_state.comprehension_passed_video_ids
        # --- END ADDED ---

        # --- MODIFIED: Added 'and not has_been_watched' ---
        if not st.session_state.get(timer_finished_key, False) and caption_idx == 0 and not has_been_watched:
        # --- END MODIFIED ---
            st.subheader("Watch the video")
            with st.spinner(""):
                main_col, _ = st.columns([1, 1.8])
                with main_col:
                    if current_video.get("orientation") == "portrait":
                        _, vid_col, _ = st.columns([1, 3, 1])
                        with vid_col: st.video(current_video['video_path'], autoplay=True, muted=True)
                    else:
                        st.video(current_video['video_path'], autoplay=True, muted=True)
                    duration = current_video.get('duration', 10)
                    time.sleep(duration)
            st.session_state[timer_finished_key] = True
            st.rerun()
        else:
            current_caption = current_video['captions'][caption_idx]
            view_state_key = f"view_state_p1_{current_caption['caption_id']}"; summary_typed_key = f"summary_typed_{current_video['video_id']}"
            q_templates = st.session_state.all_data['questions']['part1_questions'] # Part 1 questions
            questions_to_ask_raw = [q for q in q_templates if q['id'] != 'overall_relevance']; question_ids = [q['id'] for q in questions_to_ask_raw]
            options_map = {"tone_relevance": ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"], "style_relevance": ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"],"factual_consistency": ["Contradicts", "Inaccurate", "Partially", "Mostly Accurate", "Accurate"], "usefulness": ["Not at all", "Slightly", "Moderately", "Very", "Extremely"], "human_likeness": ["Robotic", "Unnatural", "Moderate", "Very Human-like", "Natural"]}

            if view_state_key not in st.session_state:
                initial_step = 5 if caption_idx > 0 else 1
                # --- ADDED: Skip logic ---
                if has_been_watched and caption_idx == 0:
                    initial_step = 5 # Skip to showing captions
                    st.session_state[summary_typed_key] = True # Mark summary as "typed"
                # --- END ADDED ---
                st.session_state[view_state_key] = {'step': initial_step, 'interacted': {qid: False for qid in question_ids}, 'comp_feedback': False, 'comp_choice': None}
                # --- MODIFIED: Only set to false if not watched ---
                if caption_idx == 0 and not has_been_watched:
                    st.session_state[summary_typed_key] = False
                # --- END MODIFIED ---

            current_step = st.session_state[view_state_key]['step']

            def mark_interacted(q_id, view_key, question_index):
                if view_key in st.session_state and 'interacted' in st.session_state[view_key]:
                    if not st.session_state[view_key]['interacted'][q_id]:
                        st.session_state[view_key]['interacted'][q_id] = True
                        st.session_state[view_state_key]['step'] = 6 + question_index + 1

            title_col1, title_col2 = st.columns([1, 1.8])
            with title_col1:
                st.subheader("Video")
            with title_col2:
                if current_step >= 5:
                    st.subheader("Caption Quality Rating")

            col1, col2 = st.columns([1, 1.8])
            with col1:
                if current_video.get("orientation") == "portrait":
                    _, vid_col, _ = st.columns([1, 3, 1])
                    with vid_col: st.video(current_video['video_path'], autoplay=True, muted=True)
                else:
                    st.video(current_video['video_path'], autoplay=True, muted=True)

                if caption_idx == 0:
                    if current_step == 1:
                        if st.button("Proceed to Summary", key=f"proceed_summary_{video_idx}"):
                            st.session_state[view_state_key]['step'] = 2; st.rerun()
                        # --- ADDED LINE ---
                        streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_study_1_1_{video_idx}")
                        # --- END ADDED LINE ---
                    elif current_step >= 2:
                        st.subheader("Video Summary")
                        if st.session_state.get(summary_typed_key, False): st.info(current_video["video_summary"])
                        else:
                            with st.empty(): st.write_stream(stream_text(current_video["video_summary"]))
                            st.session_state[summary_typed_key] = True
                        if current_step == 2 and st.button("Proceed to Question", key=f"p1_proceed_comp_q_{video_idx}"):
                            st.session_state[view_state_key]['step'] = 3; st.rerun()
                        # --- ADDED LINE (for step 2) ---
                        if current_step == 2:
                            streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_study_1_2_{video_idx}")
                        # --- END ADDED LINE ---
                else:
                    st.subheader("Video Summary"); st.info(current_video["video_summary"])

            with col2:
                validation_placeholder = st.empty()
                if (current_step == 3 or current_step == 4) and caption_idx == 0:
                    render_comprehension_quiz(current_video, view_state_key, proceed_step=5)

                terms_to_define = set()
                if current_step >= 5:
                    colors = ["#FFEEEE", "#EBF5FF", "#E6F7EA"]; highlight_color = colors[caption_idx % len(colors)]
                    caption_box_class = "part1-caption-box new-caption-highlight"
                    st.markdown(f'<div class="{caption_box_class}" style="background-color: {highlight_color};"><strong>Caption:</strong><p class="caption-text">{current_caption["text"]}</p></div>', unsafe_allow_html=True)
                    streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_p1_{current_caption['caption_id']}")
                    if current_step == 5 and st.button("Show Questions", key=f"show_q_{current_caption['caption_id']}"):
                        st.session_state[view_state_key]['step'] = 6; st.rerun()
                if current_step >= 6:
                    control_scores = current_caption.get("control_scores", {})
                    tone_traits = list(control_scores.get("tone", {}).keys())[:2]
                    style_traits = list(control_scores.get("writing_style", {}).keys())[:2]
                    application_text = current_caption.get("application", "the intended application")

                    terms_to_define.update(tone_traits)
                    terms_to_define.add(application_text)

                    def format_traits(traits):
                        highlighted = [f"<b class='highlight-trait'>{trait}</b>" for trait in traits]
                        if len(highlighted) > 1: return " and ".join(highlighted)
                        return highlighted[0] if highlighted else ""

                    tone_str = format_traits(tone_traits)

                    # --- Handle Style Relevance Overrides ---
                    style_q_template_obj = next((q for q in questions_to_ask_raw if q['id'] == 'style_relevance'), None)
                    style_overrides = style_q_template_obj.get('overrides', {}) if style_q_template_obj else {}
                    found_override = False
                    style_q_text_final = ""
                    style_q_options_final = []

                    for trait in style_traits:
                        if trait in style_overrides:
                            style_q_text_final = style_overrides[trait]['text']
                            style_q_options_final = style_overrides[trait]['options']
                            terms_to_define.add(trait)
                            found_override = True
                            break

                    if not found_override:
                        style_str = format_traits(style_traits)
                        default_text = "How {} is the caption's style?"
                        default_options = ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"]
                        if style_q_template_obj:
                            default_text = style_q_template_obj.get('default_text', default_text)
                            default_options = style_q_template_obj.get('default_options', default_options)
                        style_q_text_final = default_text.format(style_str)
                        style_q_options_final = default_options
                        terms_to_define.update(style_traits)

                    options_map['style_relevance'] = style_q_options_final # Update the options map
                    # --- End Handle Style Relevance Overrides ---

                    tone_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'tone_relevance'), "How {} does the caption sound?")
                    fact_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'factual_consistency'), "How factually accurate is the caption?")
                    useful_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'usefulness'), "How useful is this caption for {}?")
                    human_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'human_likeness'), "How human-like does this caption sound?")

                    questions_to_ask = [
                        {"id": "tone_relevance", "text": tone_q_template.format(tone_str)},
                        {"id": "style_relevance", "text": style_q_text_final},
                        {"id": "factual_consistency", "text": fact_q_template},
                        {"id": "usefulness", "text": useful_q_template.format(f"<b class='highlight-trait'>{application_text}</b>")},
                        {"id": "human_likeness", "text": human_q_template}
                    ]

                    interacted_state = st.session_state.get(view_state_key, {}).get('interacted', {})
                    question_cols_row1 = st.columns(3); question_cols_row2 = st.columns(3)

                    def render_slider(q, col, q_index, view_key_arg):
                        with col:
                            slider_key = f"ss_{q['id']}_cap{caption_idx}"
                            st.markdown(f"<div class='slider-label'><strong>{q_index + 1}. {q['text']}</strong></div>", unsafe_allow_html=True)
                            st.select_slider(q['id'], options=options_map[q['id']], key=slider_key, label_visibility="collapsed", on_change=mark_interacted, args=(q['id'], view_key_arg, q_index), value=options_map[q['id']][0])

                    num_interacted = sum(1 for flag in interacted_state.values() if flag)
                    questions_to_show = num_interacted + 1

                    if questions_to_show >= 1: render_slider(questions_to_ask[0], question_cols_row1[0], 0, view_state_key)
                    if questions_to_show >= 2: render_slider(questions_to_ask[1], question_cols_row1[1], 1, view_state_key)
                    if questions_to_show >= 3: render_slider(questions_to_ask[2], question_cols_row1[2], 2, view_state_key)
                    if questions_to_show >= 4: render_slider(questions_to_ask[3], question_cols_row2[0], 3, view_state_key)
                    if questions_to_show >= 5: render_slider(questions_to_ask[4], question_cols_row2[1], 4, view_state_key)

                    if questions_to_show > len(questions_to_ask):
                        if st.button("Submit Ratings", key=f"submit_cap{caption_idx}"):
                            all_interacted = all(interacted_state.get(qid, False) for qid in question_ids)
                            if not all_interacted:
                                missing_qs = [i+1 for i, qid in enumerate(question_ids) if not interacted_state.get(qid, False)]
                                validation_placeholder.warning(f"⚠️ Please move the slider for question(s): {', '.join(map(str, missing_qs))}")
                            else:
                                with st.spinner("Saving response..."): # Spinner added
                                    all_saved = True
                                    responses_to_save = {qid: st.session_state.get(f"ss_{qid}_cap{caption_idx}") for qid in question_ids}
                                    for q_id, choice_text in responses_to_save.items():
                                        full_q_text = next((q['text'] for q in questions_to_ask if q['id'] == q_id), "N.A.")
                                        # Use correct study phase string
                                        if not save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_video, current_caption, choice_text, 'user_study_part1', full_q_text):
                                            all_saved = False
                                            break
                                if all_saved:
                                    st.session_state.current_caption_index += 1
                                    if st.session_state.current_caption_index >= len(current_video['captions']):
                                        st.session_state.current_video_index += 1; st.session_state.current_caption_index = 0
                                    st.session_state.pop(view_state_key, None); st.rerun()

                    # Use definitions from session state
                    reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {ALL_DEFINITIONS.get(term, 'Definition not found.')}</li>" for term in sorted(list(terms_to_define)) if ALL_DEFINITIONS.get(term)) + "</ul></div>"
                    st.markdown(reference_html, unsafe_allow_html=True)

    # --- MODIFIED: Part 2 (Intensity Change) ---
    elif st.session_state.study_part == 2:
        # --- DATA KEY SWAPPED ---
        all_changes = st.session_state.all_data['study']['part2_intensity_change'] # Changed key
        change_idx = st.session_state.current_change_index
        # --- Progression updated ---
        if change_idx >= len(all_changes):
            st.session_state.study_part = 3 # Go to Comparison (now Part 3) next
            st.rerun()
        # --- End Progression update ---

        current_change = all_changes[change_idx]; change_id = current_change['change_id']
        video_id = current_change.get('video_id') # --- ADDED ---
        field_to_change = current_change['field_to_change']; field_type = list(field_to_change.keys())[0]
        timer_finished_key = f"timer_finished_{change_id}" # Keep timer key based on unique change_id
        # --- ADDED ---
        has_been_watched = video_id in st.session_state.comprehension_passed_video_ids
        # --- END ADDED ---

        # --- MODIFIED: Added 'and not has_been_watched' ---
        if not st.session_state.get(timer_finished_key, False) and not has_been_watched:
        # --- END MODIFIED ---
            st.subheader("Watch the video")
            with st.spinner(""):
                main_col, _ = st.columns([1, 1.8])
                with main_col:
                    if current_change.get("orientation") == "portrait":
                        _, vid_col, _ = st.columns([1, 3, 1])
                        with vid_col: st.video(current_change['video_path'], autoplay=True, muted=True)
                    else:
                        st.video(current_change['video_path'], autoplay=True, muted=True)
                    duration = current_change.get('duration', 10)
                    time.sleep(duration)
            st.session_state[timer_finished_key] = True
            st.rerun()
        else:
            # --- State keys use 'p2' now ---
            view_state_key = f"view_state_p2_{change_id}"; summary_typed_key = f"summary_typed_p2_{change_id}"
            if view_state_key not in st.session_state:
                # --- ADDED: Skip logic ---
                initial_step = 1
                if has_been_watched:
                    initial_step = 5 # Skip to showing captions
                    st.session_state[summary_typed_key] = True
                # --- END ADDED ---
                st.session_state[view_state_key] = {'step': initial_step, 'summary_typed': False, 'comp_feedback': False, 'comp_choice': None}
                # --- ADDED ---
                if not has_been_watched:
                    st.session_state[summary_typed_key] = False
                # --- END ADDED ---
            current_step = st.session_state[view_state_key]['step']

            title_col1, title_col2 = st.columns([1, 1.8])
            with title_col1:
                st.subheader("Video")
            with title_col2:
                if current_step >= 5:
                     # --- Title updated ---
                    st.subheader(f"Tone Intensity Change") # Simpler title

            col1, col2 = st.columns([1, 1.8])
            with col1:
                if current_change.get("orientation") == "portrait":
                    _, vid_col, _ = st.columns([1, 3, 1])
                    with vid_col: st.video(current_change['video_path'], autoplay=True, muted=True)
                else:
                    st.video(current_change['video_path'], autoplay=True, muted=True)

                if current_step == 1:
                    # --- Key updated ---
                    if st.button("Proceed to Summary", key=f"p2_proceed_summary_{change_id}"):
                        st.session_state[view_state_key]['step'] = 2; st.rerun()
                    # --- ADDED LINE ---
                    streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_study_2_1_{change_id}")
                    # --- END ADDED LINE ---
                if current_step >= 2:
                    st.subheader("Video Summary")
                    if st.session_state.get(summary_typed_key, False): st.info(current_change["video_summary"])
                    else:
                        with st.empty(): st.write_stream(stream_text(current_change["video_summary"]))
                        st.session_state[summary_typed_key] = True
                    # --- Key updated ---
                    if current_step == 2 and st.button("Proceed to Question", key=f"p2_proceed_captions_{change_id}"):
                        st.session_state[view_state_key]['step'] = 3; st.rerun()
                    # --- ADDED LINE (for step 2) ---
                    if current_step == 2:
                        streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_study_2_2_{change_id}")
                    # --- END ADDED LINE ---
            with col2:
                if current_step == 3 or current_step == 4:
                    render_comprehension_quiz(current_change, view_state_key, proceed_step=5)

                if current_step >= 5:
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_change["caption_A"]}</p></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_change["caption_B"]}</p></div>', unsafe_allow_html=True)
                    # --- ADDED LINE ---
                    streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_p2_{change_id}")
                    # --- END ADDED LINE ---
                    # --- Key updated ---
                    if current_step == 5 and st.button("Show Questions", key=f"p2_show_q_{change_id}"):
                        st.session_state[view_state_key]['step'] = 6; st.rerun()
                if current_step >= 6:
                    terms_to_define = set()
                    trait = field_to_change[field_type]
                    terms_to_define.add(trait)

                    q_template = None
                    if field_type == 'writing_style':
                        q_template_key = 'Writing Style'
                    elif field_type == 'tone':
                        q_template_key = 'Tone'
                    else:
                        st.error(f"Unknown field type for question template: {field_type}")
                        q_template_key = None

                    if q_template_key:
                        # --- QUESTION KEY SWAPPED ---
                        if q_template_key not in st.session_state.all_data['questions']['part2_questions']: # Changed key
                            st.error(f"Question template key '{q_template_key}' not found in questions.json")
                        else:
                            # --- QUESTION KEY SWAPPED ---
                            q_template = st.session_state.all_data['questions']['part2_questions'][q_template_key] # Changed key

                    if q_template:
                        # --- Form key updated ---
                        with st.form(key=f"study_form_p2_{change_idx}"):
                            highlighted_trait = f"<b class='highlight-trait'>{trait}</b>"
                            dynamic_question_raw = q_template.format(highlighted_trait, change_type=current_change['change_type'])
                            dynamic_question_save = re.sub('<[^<]+?>', '', dynamic_question_raw)
                            q2_text = "Is the core factual content consistent across both captions?"
                            col_q1, col_q2 = st.columns(2)
                            with col_q1:
                                st.markdown(f'<div class="part3-question-text">1. {dynamic_question_raw}</div>', unsafe_allow_html=True) # Kept class name for styling
                                # --- Radio key updated ---
                                choice1 = st.radio("q1_label", ["Yes", "No"], index=None, horizontal=True, key=f"p2_{current_change['change_id']}_q1", label_visibility="collapsed")
                            with col_q2:
                                st.markdown(f'<div class="part3-question-text">2. {q2_text}</div>', unsafe_allow_html=True) # Kept class name for styling
                                # --- Radio key updated ---
                                choice2 = st.radio("q2_label", ["Yes", "No"], index=None, horizontal=True, key=f"p2_{current_change['change_id']}_q2", label_visibility="collapsed")

                            if st.form_submit_button("Submit Answers"):
                                if choice1 is None or choice2 is None:
                                    st.error("Please answer both questions.")
                                else:
                                    with st.spinner("Saving response..."): # Spinner added
                                        # --- STUDY PHASE SWAPPED ---
                                        success1 = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice1, 'user_study_part2', dynamic_question_save) # Changed phase
                                        success2 = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice2, 'user_study_part2', q2_text) # Changed phase
                                    if success1 and success2:
                                        st.session_state.current_change_index += 1
                                        st.session_state.pop(view_state_key, None)
                                        st.rerun()

                    if terms_to_define:
                        reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {ALL_DEFINITIONS.get(term, 'Definition not found.')}</li>" for term in sorted(list(terms_to_define)) if ALL_DEFINITIONS.get(term)) + "</ul></div>"
                        st.markdown(reference_html, unsafe_allow_html=True)


    # --- MODIFIED: Part 3 (Comparison) ---
    elif st.session_state.study_part == 3: # Changed condition to == 3
        # --- DATA KEY SWAPPED ---
        all_comparisons = st.session_state.all_data['study']['part3_comparisons'] # Changed key
        comp_idx = st.session_state.current_comparison_index
        # --- Progression updated ---
        if comp_idx >= len(all_comparisons):
            st.session_state.page = 'final_thank_you' # Go to end after this part
            st.rerun()
        # --- End Progression update ---

        current_comp = all_comparisons[comp_idx]; comparison_id = current_comp['comparison_id']
        video_id = current_comp.get('video_id') # --- ADDED ---
        timer_finished_key = f"timer_finished_{comparison_id}" # Keep timer key based on unique comparison_id
        # --- ADDED ---
        has_been_watched = video_id in st.session_state.comprehension_passed_video_ids
        # --- END ADDED ---

        # --- MODIFIED: Added 'and not has_been_watched' ---
        if not st.session_state.get(timer_finished_key, False) and not has_been_watched:
        # --- END MODIFIED ---
            st.subheader("Watch the video")
            with st.spinner(""):
                main_col, _ = st.columns([1, 1.8])
                with main_col:
                    if current_comp.get("orientation") == "portrait":
                        _, vid_col, _ = st.columns([1, 3, 1])
                        with vid_col: st.video(current_comp['video_path'], autoplay=True, muted=True)
                    else:
                        st.video(current_comp['video_path'], autoplay=True, muted=True)
                    duration = current_comp.get('duration', 10)
                    time.sleep(duration)
            st.session_state[timer_finished_key] = True
            st.rerun()
        else:
            # --- State keys use 'p3' now ---
            view_state_key = f"view_state_p3_{comparison_id}"; summary_typed_key = f"summary_typed_p3_{comparison_id}"
            # --- QUESTION KEY SWAPPED ---
            q_templates = st.session_state.all_data['questions']['part3_questions'] # Changed key
            question_ids = [q['id'] for q in q_templates]

            if view_state_key not in st.session_state:
                # --- ADDED: Skip logic ---
                initial_step = 1
                if has_been_watched:
                    initial_step = 5 # Skip to showing captions
                    st.session_state[summary_typed_key] = True
                # --- END ADDED ---
                st.session_state[view_state_key] = {'step': initial_step, 'interacted': {qid: False for qid in question_ids}, 'comp_feedback': False, 'comp_choice': None}
                # --- ADDED ---
                if not has_been_watched:
                    st.session_state[summary_typed_key] = False
                # --- END ADDED ---

            current_step = st.session_state[view_state_key]['step']

            # --- Function name updated for clarity ---
            def mark_p3_interacted(q_id, view_key):
                if view_key in st.session_state and 'interacted' in st.session_state[view_key]:
                    if not st.session_state[view_key]['interacted'][q_id]:
                        st.session_state[view_key]['interacted'][q_id] = True

            title_col1, title_col2 = st.columns([1, 1.8])
            with title_col1:
                st.subheader("Video")
            with title_col2:
                if current_step >= 5:
                     # --- Title updated ---
                    st.subheader("Caption Comparison")

            col1, col2 = st.columns([1, 1.8])
            with col1:
                if current_comp.get("orientation") == "portrait":
                    _, vid_col, _ = st.columns([1, 3, 1])
                    with vid_col: st.video(current_comp['video_path'], autoplay=True, muted=True)
                else:
                    st.video(current_comp['video_path'], autoplay=True, muted=True)

                if current_step == 1:
                     # --- Key updated ---
                    if st.button("Proceed to Summary", key=f"p3_proceed_summary_{comparison_id}"):
                        st.session_state[view_state_key]['step'] = 2; st.rerun()
                    # --- ADDED LINE ---
                    streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_study_3_1_{comparison_id}")
                    # --- END ADDED LINE ---
                if current_step >= 2:
                    st.subheader("Video Summary")
                    if st.session_state.get(summary_typed_key, False): st.info(current_comp["video_summary"])
                    else:
                        with st.empty(): st.write_stream(stream_text(current_comp["video_summary"]))
                        st.session_state[summary_typed_key] = True
                    # --- Key updated ---
                    if current_step == 2 and st.button("Proceed to Question", key=f"p3_proceed_captions_{comparison_id}"):
                        st.session_state[view_state_key]['step'] = 3; st.rerun()
                    # --- ADDED LINE (for step 2) ---
                    if current_step == 2:
                        streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_study_3_2_{comparison_id}")
                    # --- END ADDED LINE ---

            with col2:
                if current_step == 3 or current_step == 4:
                    render_comprehension_quiz(current_comp, view_state_key, proceed_step=5)

                validation_placeholder = st.empty()
                terms_to_define = set()
                if current_step >= 5:
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_comp["caption_A"]}</p></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_comp["caption_B"]}</p></div>', unsafe_allow_html=True)
                    # --- ADDED LINE ---
                    streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_p3_{comparison_id}")
                    # --- END ADDED LINE ---
                    # --- Key updated ---
                    if current_step == 5 and st.button("Show Questions", key=f"p3_show_q_{comparison_id}"):
                        st.session_state[view_state_key]['step'] = 6; st.rerun()
                if current_step >= 6:
                    control_scores = current_comp.get("control_scores", {}); tone_traits = list(control_scores.get("tone", {}).keys()); style_traits = list(control_scores.get("writing_style", {}).keys())
                    terms_to_define.update(tone_traits)

                    # --- Function name updated for clarity ---
                    def format_part3_traits(traits):
                        highlighted = [f"<b class='highlight-trait'>{trait}</b>" for trait in traits]
                        if len(highlighted) > 1: return " and ".join(highlighted)
                        return highlighted[0] if highlighted else ""

                    # --- Function name updated for clarity ---
                    tone_str = format_part3_traits(tone_traits)

                    part3_questions = [] # Renamed variable
                    for q in q_templates: # q_templates now holds part3 questions
                        q_id = q['id']
                        if q_id == 'q2_style': # This ID remains the same based on questions.json structure
                            style_overrides = q.get('overrides', {})
                            found_override = False
                            style_q_text_final = ""
                            for trait in style_traits:
                                if trait in style_overrides:
                                    style_q_text_final = style_overrides[trait]['text']
                                    terms_to_define.add(trait)
                                    found_override = True
                                    break
                            if not found_override:
                                # --- Function name updated ---
                                style_str = format_part3_traits(style_traits)
                                style_q_text_final = q.get('default_text', "Which caption's style is more {}?").format(style_str)
                                terms_to_define.update(style_traits)
                            part3_questions.append({"id": q_id, "text": style_q_text_final})
                        elif q_id == 'q1_tone': # This ID remains the same
                            part3_questions.append({"id": q_id, "text": q['text'].format(tone_str)})
                        else:
                            part3_questions.append({"id": q_id, "text": q.get('text', '')})

                    options = ["Caption A", "Caption B", "Both A and B", "Neither A nor B"]

                    interacted_state = st.session_state.get(view_state_key, {}).get('interacted', {})
                    num_interacted = sum(1 for flag in interacted_state.values() if flag)
                    questions_to_show = num_interacted + 1

                    question_cols = st.columns(4)

                    # --- Function name updated for clarity ---
                    def render_p3_radio(q, col, q_index, view_key_arg):
                        with col:
                            st.markdown(f"<div class='slider-label'><strong>{q_index + 1}. {q['text']}</strong></div>", unsafe_allow_html=True)
                            # --- Radio key updated ---
                            st.radio(q['text'], options, index=None, label_visibility="collapsed", key=f"p3_{comparison_id}_{q['id']}", on_change=mark_p3_interacted, args=(q['id'], view_key_arg))

                    # --- Function name and variable updated ---
                    if questions_to_show >= 1: render_p3_radio(part3_questions[0], question_cols[0], 0, view_state_key)
                    if questions_to_show >= 2: render_p3_radio(part3_questions[1], question_cols[1], 1, view_state_key)
                    if questions_to_show >= 3: render_p3_radio(part3_questions[2], question_cols[2], 2, view_state_key)
                    if questions_to_show >= 4: render_p3_radio(part3_questions[3], question_cols[3], 3, view_state_key)

                    # --- Variable updated ---
                    if questions_to_show > len(part3_questions):
                         # --- Button key updated ---
                        if st.button("Submit Comparison", key=f"submit_comp_p3_{comparison_id}"):
                            # --- Radio key and variable updated ---
                            responses = {q['id']: st.session_state.get(f"p3_{comparison_id}_{q['id']}") for q in part3_questions}
                            if any(choice is None for choice in responses.values()):
                                validation_placeholder.warning("⚠️ Please answer all four questions before submitting.")
                            else:
                                with st.spinner("Saving response..."): # Spinner added
                                    all_saved = True
                                    for q_id, choice in responses.items():
                                        # --- Variable updated ---
                                        full_q_text = next((q['text'] for q in part3_questions if q['id'] == q_id), "N.A.")
                                        # --- STUDY PHASE SWAPPED ---
                                        if not save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_comp, current_comp, choice, 'user_study_part3', full_q_text): # Changed phase
                                            all_saved = False
                                            break
                                if all_saved:
                                    st.session_state.current_comparison_index += 1; st.session_state.pop(view_state_key, None); st.rerun()

                    # Use definitions from session state
                    reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {ALL_DEFINITIONS.get(term, 'Definition not found.')}</li>" for term in sorted(list(terms_to_define)) if ALL_DEFINITIONS.get(term)) + "</ul></div>"
                    st.markdown(reference_html, unsafe_allow_html=True)

    # --- END MODIFIED ---

elif st.session_state.page == 'final_thank_you':
    st.title("Study Complete! Thank You!")
    st.success("You have successfully completed all parts of the study. We sincerely appreciate your time and valuable contribution to our research!")

# --- JavaScript ---
# (Keep js_script and streamlit_js_eval call exactly as they were)
js_script = """
const parent_document = window.parent.document;

console.log("Attaching Arrow key listener.");
parent_document.addEventListener('keyup', function(event) {
    const activeElement = parent_document.activeElement;
    // PREVENT ACTION IF USER IS TYPING OR FOCUSED ON A SLIDER/INPUT/TEXTAREA
    if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA' || activeElement.getAttribute('role') === 'slider')) {
        return;
    }

    if (event.key === 'ArrowRight') {
        event.preventDefault();
        const targetButtonLabels = [
            "Submit Ratings", "Submit Comparison", "Submit Answers",
            "Submit Answer", "Next Question", "Show Questions", "Finish Quiz",
            "Proceed to Caption(s)", "Proceed to Captions", "Proceed to Caption",
            "Proceed to Summary", "Proceed to Question", "Proceed to User Study",
            "Take Quiz Again", "Submit", "Next >>", "Start Quiz >>", "Next" // Added "Start Quiz >>"
        ];
        const allButtons = Array.from(parent_document.querySelectorAll('button'));
        const visibleButtons = allButtons.filter(btn => btn.offsetParent !== null); // Check if button is visible

        for (const label of targetButtonLabels) {
            // Find the LAST visible button on the page that matches the label
            const targetButton = [...visibleButtons].reverse().find(btn => btn.textContent.trim().includes(label));
            if (targetButton) {
                console.log('ArrowRight detected, clicking button:', targetButton.textContent);
                targetButton.click();
                break; // Exit loop once a button is clicked
            }
        }
    } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        const targetButtonLabels = [
            "Prev <<"
        ];
        const allButtons = Array.from(parent_document.querySelectorAll('button'));
        const visibleButtons = allButtons.filter(btn => btn.offsetParent !== null); // Check if button is visible

        for (const label of targetButtonLabels) {
            // Find the LAST visible button on the page that matches the label
            const targetButton = [...visibleButtons].reverse().find(btn => btn.textContent.trim().includes(label));
            if (targetButton) {
                console.log('ArrowLeft detected, clicking button:', targetButton.textContent);
                targetButton.click();
                break; // Exit loop once a button is clicked
            }
        }
    }
});
"""
streamlit_js_eval(js_expressions=js_script, key="keyboard_listener_v4") # Incremented key