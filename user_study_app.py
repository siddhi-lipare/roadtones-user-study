# app.py
import streamlit as st
import pandas as pd
import os
import random
import time
import re # Import the regular expression module for email validation
import gspread

# --- Configuration ---
RESPONSES_PATH = 'responses/study_results.csv'
TOTAL_ATTEMPTS = 2
INTRO_VIDEO_PATH = "media/start_video_slower.mp4"

# --- Central Dictionary for Definitions ---
DEFINITIONS = {
    'Advisory': {'desc': 'Gives advice, suggestions, or warnings about a situation.'},
    'Sarcastic': {'desc': 'Uses irony or mockery to convey contempt, often by saying the opposite of what is meant.'},
    'Appreciative': {'desc': 'Expresses gratitude, admiration, or praise for an action or event.'},
    'Considerate': {'desc': 'Shows careful thought and concern for the well-being or safety of others.'},
    'Critical': {'desc': 'Expresses disapproving comments or judgments about an action or behavior.'},
    'Amusing': {'desc': 'Causes lighthearted laughter or provides entertainment in a playful way.'},
    'Angry': {'desc': 'Expresses strong annoyance, displeasure, or hostility towards an event.'},
    'Anxious': {'desc': 'Shows a feeling of worry, nervousness, or unease about an uncertain outcome.'},
    'Enthusiastic': {'desc': 'Shows intense and eager enjoyment or interest in an event.'},
    'Judgmental': {'desc': 'Displays an overly critical or moralizing point of view on actions shown.'},
    'Conversational': {'desc': 'Uses an informal, personal, and chatty style, as if talking directly to a friend.'}
}


# --- Data Structure with Difficulty Levels ---
STUDY_DATA_BY_PART = {
    "Part 1: Tone Identification": [
        {
            "sample_id": "770719942027145220", "video_path": "media/v_770719942027145220__IBpd70dJt7nNSop.mp4",
            "caption": "Guess I'll use my psychic powers, since that turn signal is clearly too complicated for you.",
            "options": ['Advisory', 'Sarcastic', 'Appreciative', 'Considerate'], "correct_answer": "Sarcastic",
            "explanation": "The caption uses irony to criticize the driver, which is a key element of sarcasm.", "question_type": "single"
        },
        {
            "sample_id": "988741606391009282", "video_path": "media/v_988741606391009282_aG9gbwBWJLQVFXT_.mp4",
            "caption": "A crucial reminder for all drivers: Always stop at red lights. This collision was caused by a single vehicle running a red light. #RoadSafety #DriveSafe",
            "options": ['Advisory', 'Critical', 'Amusing', 'Angry'], "correct_answer": "Advisory",
            "explanation": "The caption is directly giving advice and promoting safe driving practices.", "question_type": "single"
        },
        {
            "sample_id": "921439559250038784", "video_path": "media/v_921439559250038784_P14L18RmB2Nh7wA4.mp4",
            "caption": "Infuriating. The middle lane is for OVERTAKING, not cruising. If the left lane is empty, MOVE OVER. #LaneHogging",
            "options": ['Angry', 'Anxious', 'Considerate', 'Sarcastic'], "correct_answer": "Angry",
            "explanation": "The word 'Infuriating' and the commanding, all-caps text clearly express anger.", "question_type": "single"
        },
        {
            "sample_id": "823666846180118529", "video_path": "media/v_823666846180118529_R7TrcOlE3Uv202-r.mp4",
            "caption": "I’m training for the Cadel Road Race in Australia with @CadelRoadRace 🚴‍♂️ Staying safe on these open roads! #cyclinglife #Australia",
            "options": ['Appreciative', 'Sarcastic', 'Enthusiastic', 'Critical'], "correct_answer": ["Appreciative", "Enthusiastic"],
            "explanation": "The caption expresses positive excitement about training and gratitude for safety, making 'Appreciative' and 'Enthusiastic' the dominant tones.", "question_type": "multi"
        },
        {
            "sample_id": "1696360086518776040", "video_path": "media/v_1696360086518776040_DStI4BjOrtDhkLua.mp4",
            "caption": "So apparently, sunset is when Mercedes drivers test just how close they can get to my Tesla. Smooth move, @TeslaRoadWatch.",
            "options": ['Critical', 'Appreciative', 'Sarcastic', 'Advisory'], "correct_answer": ["Critical", "Sarcastic"],
            "explanation": "The phrase 'Smooth move' is used sarcastically to criticize the other driver's dangerous action.", "question_type": "multi"
        }
    ],
    "Part 2: Tone Controllability Evaluation": [
        {
            "sample_id": "intensity_001", "video_path": "media/v_770719942027145220__IBpd70dJt7nNSop.mp4",
            "caption_A": "That wasn't a very smart move by the other driver.", "caption_B": "It takes a special kind of genius to make a move that stupid.",
            "tone_to_compare": "Sarcastic", "comparison_type": "increased", "options": ["Yes", "No"], "correct_answer": "Yes",
            "explanation": "Yes, the intensity of sarcasm increases significantly from a simple statement to an exaggerated, ironic compliment."
        },
        {
            "sample_id": "intensity_002", "video_path": "media/v_988741606391009282_aG9gbwBWJLQVFXT_.mp4",
            "caption_A": "A crucial reminder for all drivers: Always stop at red lights to prevent collisions like this one.", "caption_B": "Drivers should be more careful at intersections.",
            "tone_to_compare": "Advisory", "comparison_type": "decreased", "options": ["Yes", "No"], "correct_answer": "Yes",
            "explanation": "Yes, the intensity decreases from a strong, direct command in Caption A to a more general suggestion in Caption B."
        }
    ],
    "Part 3: Caption Quality": [
        {
            "sample_id": "rating_001", "video_path": "media/v_1692102872706765068_GjAx5c9hRZP-JBsr.mp4",
            "caption": "I witnessed a cab attempt a dangerous overtake on a blind curve, nearly leading to a head-on collision with an oncoming vehicle. A bus also overtook unsafely. Overtaking without clear visibility is extremely risky—please drive with caution and patience. #RoadSafety #DriveResponsibly",
            "video_summary": "A dashcam captured an instance of unsafe driving behavior in India during daytime, likely afternoon. The key road event was an unsafe overtaking attempt by a cab that nearly resulted in a head-on collision with an oncoming vehicle. The cab attempted to overtake on a curve with limited visibility, forcing it to brake and swerve to avoid the collision. A bus was also involved, performing an unsafe overtake. The traffic violations included unsafe overtaking by both the cab and the bus, and the cab's overtaking on a curve with limited visibility.",
            "questions": [
                {"heading": "Tone Relevance", "question_text": "Is the tone of the caption relevant to the video?", "options": ["Yes", "No"], "correct_answer": "Yes", "explanation": "The caption's alarmed and advisory tone is highly relevant to the dangerous event shown in the video."},
                {"heading": "Factual Accuracy", "question_text": "As per the video summary, is the information provided in the caption factually accurate?", "options": ["Yes", "No"], "correct_answer": "Yes", "explanation": "The caption accurately describes the unsafe overtaking by a cab on a curve, which matches the video summary."},
                {"heading": "Human-likeness", "question_text": "Is the caption human-like?", "options": ["Yes", "No"], "correct_answer": "Yes", "explanation": "The caption uses natural language from a first-person perspective ('I witnessed') and includes relevant hashtags, making it very human-like."}
            ]
        }
    ]
}

# --- Helper Functions ---
@st.cache_data
def load_data():
    """Loads and validates the study data."""
    for part, questions in STUDY_DATA_BY_PART.items():
        for item in questions:
            if not os.path.exists(item["video_path"]):
                st.error(f"Error: Video file not found at '{item['video_path']}' in {part}.")
                return None
    if not os.path.exists(INTRO_VIDEO_PATH):
        st.error(f"Error: Intro video not found at '{INTRO_VIDEO_PATH}'.")
        return None
    return STUDY_DATA_BY_PART

def save_response(email, age, gender, data_sample, choice, attempts_taken, was_correct, part, question_text="N/A"):
    """Saves a single response to your Google Sheet."""

    # Get the current time for the timestamp
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    # Create a dictionary of the response
    response_data = {
        'email': email, 'age': age, 'gender': gender, 'timestamp': timestamp, 'part': part,
        'sample_id': data_sample['sample_id'], 'question_text': question_text,
        'caption_shown': data_sample.get('caption', f"A:{data_sample.get('caption_A')}//B:{data_sample.get('caption_B')}"),
        'user_choice': str(choice), # Convert list to string for sheets
        'was_correct': was_correct,
        'attempts_taken': attempts_taken
    }

    try:
        # Connect to Google Sheets using the secrets
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        # Open the sheet by its name. Make sure this matches your sheet's name exactly.
        spreadsheet = gc.open("roadtones-streamlit-userstudy-responses")
        worksheet = spreadsheet.sheet1

        # If the sheet is empty, add the headers first
        if not worksheet.get_all_records():
            worksheet.append_row(list(response_data.keys()))

        # Append the new response as a new row
        worksheet.append_row(list(response_data.values()))

    except Exception as e:
        # If it fails, show an error on the app itself for debugging
        st.error(f"Failed to write to Google Sheet: {e}")

def go_to_next_question():
    """Saves response and advances state to the next question or part."""
    part_keys = list(st.session_state.all_data.keys())
    current_part_key = part_keys[st.session_state.current_part_index]
    questions_for_part = st.session_state.all_data[current_part_key]
    sample = questions_for_part[st.session_state.current_sample_index]

    was_correct = st.session_state.is_correct
    attempts_taken = TOTAL_ATTEMPTS - st.session_state.get('attempts_left', 0)
    question_text = "N/A"

    if "Tone Controllability" in current_part_key or "Caption Quality" in current_part_key:
        attempts_taken = 1

    if "Tone Controllability" in current_part_key:
        question_text = f"Intensity of '{sample['tone_to_compare']}' has {sample['comparison_type']}"
    elif "Caption Quality" in current_part_key:
        rating_question = sample["questions"][st.session_state.current_rating_question_index]
        question_text = rating_question["question_text"]

    save_response(
        st.session_state.email, st.session_state.age, st.session_state.gender,
        sample, st.session_state.last_choice, attempts_taken, was_correct, current_part_key, question_text
    )

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
    st.session_state.attempts_left = TOTAL_ATTEMPTS

def jump_to_part(part_index):
    """Resets state to the beginning of a specific part."""
    st.session_state.current_part_index = part_index
    st.session_state.current_sample_index = 0
    st.session_state.current_rating_question_index = 0
    st.session_state.attempts_left = TOTAL_ATTEMPTS
    st.session_state.show_feedback = False

def restart_quiz():
    """Resets the quiz to start again from Part 1, keeping user info."""
    st.session_state.page = 'study' # Jumps directly to the quiz
    st.session_state.current_part_index = 0
    st.session_state.current_sample_index = 0
    st.session_state.current_rating_question_index = 0
    st.session_state.attempts_left = TOTAL_ATTEMPTS
    st.session_state.show_feedback = False
    st.session_state.score = 0
    # Email, age, and gender are preserved from the session

def format_options_with_info(option_name):
    """Formats a string to include the definition for display in a widget."""
    if option_name in DEFINITIONS:
        info = DEFINITIONS[option_name]
        return f"{option_name} ({info['desc']})"
    return option_name

# --- Main App ---
st.set_page_config(layout="wide", page_title="Tone-aware Captioning")

if 'page' not in st.session_state:
    st.session_state.page = 'demographics'
    st.session_state.current_part_index = 0
    st.session_state.current_sample_index = 0
    st.session_state.attempts_left = TOTAL_ATTEMPTS
    st.session_state.show_feedback = False
    st.session_state.current_rating_question_index = 0
    st.session_state.score = 0
    st.session_state.all_data = load_data()

# --- Page 1: Demographics & Consent ---
if st.session_state.page == 'demographics':
    st.title("Tone-aware Captioning 📝")
    st.header("Before you begin, please provide some basic information:")

    email = st.text_input("Please enter your email address:")
    age = st.selectbox("Age:", options=list(range(18, 51)), index=None, placeholder="Select your age...")
    gender = st.selectbox("Gender:", options=["Male", "Female", "Other / Prefer not to say"], index=None, placeholder="Select your gender...")

    st.write("---")

    if st.checkbox("I am over 18 and I agree to participate in this study."):
        if st.button("Next"):
            # A simple regex for email validation
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

# --- Page 2: Introductory Video ---
elif st.session_state.page == 'intro_video':
    st.title("Introductory Video")
    st.info("Please watch this short video before proceeding to the instructions.")

    _ , vid_col, _ = st.columns([1, 3, 1])
    with vid_col:
        st.video(INTRO_VIDEO_PATH, autoplay=True, muted=True)

    if st.button("Next"):
        st.session_state.page = 'instructions'
        st.rerun()

# --- Page 3: Instructions ---
elif st.session_state.page == 'instructions':
    st.title("Instructions")
    st.markdown("""
    - **Purpose:** To assess the tonal content and quality of the generated video captions.
    - You will be provided with a total of 10 questions across 3 sections.
    - **Steps to Follow:**
        1. **Watch the video** and **read the caption carefully** to understand the context before answering the questions.
        2. **Read the explanation carefully** after submitting every answer.
    - **Look for specific wording, phrasings, hashtags, emojis, and other expressive markers** to deduce the tone from the caption.
    - **Scoring:**
        - For quiz sections, you get **1 point** for each question answered correctly on the **first attempt**.
        - You are required to obtain a score of **8 or above** out of 10 to proceed for the user study.
    - **Time:** The study will take approximately 5-7 minutes.
    - **Confidentiality:** Your responses will be kept anonymous.
    """)
    if st.button("Start Test"):
        st.session_state.page = 'study'
        st.rerun()

# --- Page 4: The Study ---
elif st.session_state.page == 'study':
    part_keys = list(st.session_state.all_data.keys())

    with st.sidebar:
        st.header("Quiz Sections")
        for i, part_name in enumerate(part_keys):
            st.button(part_name, on_click=jump_to_part, args=(i,), use_container_width=True)

    if st.session_state.current_part_index >= len(part_keys):
        st.session_state.page = 'thank_you'
        st.rerun()

    current_part_key = part_keys[st.session_state.current_part_index]
    questions_for_part = st.session_state.all_data[current_part_key]
    current_index = st.session_state.current_sample_index
    sample = questions_for_part[current_index]

    st.header(current_part_key)

    if "Caption Quality" in current_part_key:
        total_rating_questions = len(sample["questions"])
        current_rating_q_index = st.session_state.current_rating_question_index
        st.progress(current_rating_q_index / total_rating_questions, text=f"Question: {current_rating_q_index + 1}/{total_rating_questions}")
    else:
        st.progress(current_index / len(questions_for_part), text=f"Question: {current_index + 1}/{len(questions_for_part)}")

    col1, col2 = st.columns([1.2, 1.5])
    with col1:
        st.header("Watch the Video")
        st.video(sample['video_path'], autoplay=True, muted=True)
        st.caption("Video is muted for autoplay. You can unmute it using the controls.")
        if "Caption Quality" in current_part_key:
            st.subheader("Video Summary")
            st.info(sample["video_summary"])

    with col2:
        question_data = {}
        if "Caption Quality" in current_part_key:
            question_data = sample["questions"][st.session_state.current_rating_question_index]
        else:
            question_data = sample

        is_single_attempt_level = "Tone Controllability" in current_part_key or "Caption Quality" in current_part_key

        if "Tone Controllability" in current_part_key:
            st.subheader(f"Do you think the intensity of '{sample['tone_to_compare']}' has {sample['comparison_type']} from Caption A to B?")
            st.markdown("""<style>.styled-caption-small{font-size:18px;background-color:#f0f2f6;border-radius:0.5rem;padding:1rem;line-height:1.4; margin-bottom: 10px;}</style>""", unsafe_allow_html=True)
            st.markdown("**Caption A:**")
            st.markdown(f'<div class="styled-caption-small">{sample["caption_A"]}</div>', unsafe_allow_html=True)
            st.markdown("**Caption B:**")
            st.markdown(f'<div class="styled-caption-small">{sample["caption_B"]}</div>', unsafe_allow_html=True)
        elif "Caption Quality" in current_part_key:
            st.subheader(question_data["heading"])
            st.markdown(f'<p style="font-size: 22px; font-weight: 600;">{question_data["question_text"]}</p>', unsafe_allow_html=True)
            st.markdown("""<style>.styled-caption{font-size:20px;background-color:#f0f2f6;border-radius:0.5rem;padding:1rem;line-height:1.5}</style>""", unsafe_allow_html=True)
            st.markdown(f'<div class="styled-caption">{sample["caption"]}</div>', unsafe_allow_html=True)
        else:
            st.subheader("Which tone(s) are most dominant in the caption?")
            st.markdown("""<style>.styled-caption{font-size:20px;background-color:#f0f2f6;border-radius:0.5rem;padding:1rem;line-height:1.5} .stMultiSelect [data-baseweb="tag"] {background-color: #0d6efd !important;}</style>""", unsafe_allow_html=True)
            st.markdown(f'<div class="styled-caption">{sample["caption"]}</div>', unsafe_allow_html=True)

        st.write("")
        st.markdown("""<style>
            .feedback-option { padding: 10px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #ddd;}
            .correct-answer { background-color: #d4edda; border-color: #c3e6cb; color: #155724; }
            .wrong-answer { background-color: #f8d7da; border-color: #f5c6cb; color: #721c24; }
            .normal-answer { background-color: #f0f2f6; }
        </style>""", unsafe_allow_html=True)

        if st.session_state.show_feedback:
            # --- FEEDBACK VIEW ---
            user_choice = st.session_state.last_choice
            correct_answer = question_data.get('correct_answer')
            if not isinstance(user_choice, list): user_choice = [user_choice]
            if not isinstance(correct_answer, list): correct_answer = [correct_answer]

            st.write("**Your Answer vs Correct Answer:**")
            for option in question_data['options']:
                is_correct_option = option in correct_answer
                is_selected_option = option in user_choice

                if is_correct_option:
                    st.markdown(f'<div class="feedback-option correct-answer"><strong>{option} (Correct Answer)</strong></div>', unsafe_allow_html=True)
                elif is_selected_option and not is_correct_option:
                    st.markdown(f'<div class="feedback-option wrong-answer">{option} (Your selection)</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="feedback-option normal-answer">{option}</div>', unsafe_allow_html=True)

            st.write("---")
            st.info(f"**Explanation:** {question_data['explanation']}")

            is_last_question_of_quiz = (st.session_state.current_part_index == len(part_keys) - 1) and \
                                       ("Caption Quality" in current_part_key and st.session_state.current_rating_question_index == len(sample["questions"]) - 1 or \
                                        "Caption Quality" not in current_part_key and current_index == len(questions_for_part) - 1)
            button_label = "Finish Quiz" if is_last_question_of_quiz else "Next Question"
            st.button(button_label, on_click=go_to_next_question)

        else:
            # --- QUESTION FORM VIEW ---
            with st.form("quiz_form"):
                choice = None
                options_list = question_data['options']

                if "Tone Identification" in current_part_key:
                    if question_data.get("question_type") == "multi":
                        choice = st.multiselect("Select all that apply:", options_list, key=f"ms_{current_index}", format_func=format_options_with_info)
                    else:
                        choice = st.radio("Select one option:", options_list, key=f"radio_{current_index}", index=None, format_func=format_options_with_info)
                else: # For Parts 2 and 3, no special formatting
                    choice = st.radio("Select one option:", options_list, key=f"radio_{current_part_key}_{current_index}", index=None)

                submitted = st.form_submit_button("Submit Answer")

                if submitted:
                    if not choice:
                        st.error("Please select an option.")
                    else:
                        st.session_state.last_choice = choice
                        correct_answer = question_data.get('correct_answer')

                        if isinstance(correct_answer, list):
                            is_correct = (set(choice) == set(correct_answer))
                        else:
                            is_correct = (choice == correct_answer)

                        st.session_state.is_correct = is_correct

                        if st.session_state.attempts_left == TOTAL_ATTEMPTS and is_correct:
                            st.session_state.score += 1

                        if not is_correct:
                            st.session_state.attempts_left -= 1

                        st.session_state.show_feedback = True
                        st.rerun()

# --- Page 5: Thank You ---
elif st.session_state.page == 'thank_you':
    st.title("Thank You! 🎉")
    st.markdown("You have completed the study. We sincerely appreciate your time and contribution!")

    total_scorable_questions = 0
    for part, questions in STUDY_DATA_BY_PART.items():
        if "Caption Quality" in part:
            total_scorable_questions += len(questions[0]["questions"])
        else:
            total_scorable_questions += len(questions)

    passing_score = 8

    st.header(f"Your Final Score: {st.session_state.score} / {total_scorable_questions}")

    if st.session_state.score >= passing_score:
        st.success("**Status: Passed**")
    else:
        st.error("**Status: Failed**")
        st.button("Take Test Again", on_click=restart_quiz)

    st.info("Scoring is based on answering correctly on your first attempt for each question.")