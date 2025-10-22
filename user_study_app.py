# # app.py
# import streamlit as st
# import pandas as pd
# import os
# import time
# import re
# import json
# import cv2
# import math
# import gspread
# import random
# from google.oauth2.service_account import Credentials
# from streamlit_js_eval import streamlit_js_eval

# # --- Configuration ---
# INTRO_VIDEO_PATH = "media/start_video_slower.mp4"
# STUDY_DATA_PATH = "study_data.json"
# QUIZ_DATA_PATH = "quiz_data.json"
# INSTRUCTIONS_PATH = "instructions.json"
# QUESTIONS_DATA_PATH = "questions.json"
# LOCAL_BACKUP_FILE = "responses_backup.jsonl"

# # --- JAVASCRIPT FOR ANIMATION ---
# JS_ANIMATION_RESET = """
#     const elements = window.parent.document.querySelectorAll('.new-caption-highlight');
#     elements.forEach(el => {
#         el.style.animation = 'none';
#         el.offsetHeight; /* trigger reflow */
#         el.style.animation = null;
#     });
# """

# # --- GOOGLE SHEETS & HELPERS ---
# @st.cache_resource
# def connect_to_gsheet():
#     """Connects to the Google Sheet using Streamlit secrets."""
#     try:
#         creds = Credentials.from_service_account_info(
#             st.secrets["gcp_service_account"],
#             scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
#         )
#         client = gspread.authorize(creds)
#         spreadsheet = client.open("roadtones-streamlit-userstudy-responses")
#         return spreadsheet.sheet1
#     except Exception:
#         return None

# def save_response_locally(response_dict):
#     """Saves a response dictionary to a local JSONL file as a fallback."""
#     try:
#         with open(LOCAL_BACKUP_FILE, "a") as f:
#             f.write(json.dumps(response_dict) + "\n")
#         return True
#     except Exception as e:
#         st.error(f"Critical Error: Could not save response to local backup file. {e}")
#         return False

# def save_response(email, age, gender, video_data, caption_data, choice, study_phase, question_text, was_correct=None):
#     """Saves a response to Google Sheets, with a local JSONL fallback."""
#     timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
#     response_dict = {
#         'email': email, 'age': age, 'gender': str(gender), 'timestamp': timestamp,
#         'study_phase': study_phase, 'video_id': video_data.get('video_id', 'N/A'),
#         'sample_id': caption_data.get('caption_id') or caption_data.get('comparison_id') or caption_data.get('change_id') or caption_data.get('sample_id'),
#         'question_text': question_text, 'user_choice': str(choice),
#         'was_correct': str(was_correct) if was_correct is not None else 'N/A',
#         'attempts_taken': 1 if study_phase == 'quiz' else 'N/A'
#     }

#     worksheet = connect_to_gsheet()
#     if worksheet:
#         try:
#             if not worksheet.get_all_values():
#                  worksheet.append_row(list(response_dict.keys()))
#             worksheet.append_row(list(response_dict.values()))
#             return True
#         except Exception as e:
#             st.warning(f"Could not save to Google Sheets ({e}). Saving a local backup.")
#             return save_response_locally(response_dict)
#     else:
#         st.warning("Could not connect to Google Sheets. Saving a local backup.")
#         return save_response_locally(response_dict)


# @st.cache_data
# def get_video_metadata(path):
#     """Reads a video file and returns its orientation and duration."""
#     try:
#         cap = cv2.VideoCapture(path)
#         if not cap.isOpened():
#             return {"orientation": "landscape", "duration": 10}
#         width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
#         height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
#         fps = cap.get(cv2.CAP_PROP_FPS)
#         frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
#         cap.release()
#         orientation = "portrait" if height > width else "landscape"
#         duration = math.ceil(frame_count / fps) if fps > 0 and frame_count > 0 else 10
#         return {"orientation": orientation, "duration": duration}
#     except Exception:
#         return {"orientation": "landscape", "duration": 10}

# @st.cache_data
# def load_data():
#     """Loads all data from external JSON files and determines video metadata."""
#     data = {}
#     required_files = {
#         "instructions": INSTRUCTIONS_PATH, "quiz": QUIZ_DATA_PATH,
#         "study": STUDY_DATA_PATH, "questions": QUESTIONS_DATA_PATH
#     }
#     for key, path in required_files.items():
#         if not os.path.exists(path):
#             st.error(f"Error: Required data file not found at '{path}'.")
#             return None
#         with open(path, 'r', encoding='utf-8') as f: data[key] = json.load(f)

#     if not os.path.exists(INTRO_VIDEO_PATH):
#         st.error(f"Error: Intro video not found at '{INTRO_VIDEO_PATH}'.")
#         return None

#     for part_key in data['study']:
#         for item in data['study'][part_key]:
#             if 'video_path' in item and os.path.exists(item['video_path']):
#                 metadata = get_video_metadata(item['video_path'])
#                 item['orientation'] = metadata['orientation']
#                 item['duration'] = metadata['duration']
#             else:
#                 item['orientation'] = 'landscape'
#                 item['duration'] = 10

#     for part_key in data['quiz']:
#          for item in data['quiz'][part_key]:
#             if 'video_path' in item and os.path.exists(item['video_path']):
#                 metadata = get_video_metadata(item['video_path'])
#                 item['orientation'] = metadata['orientation']
#                 item['duration'] = metadata['duration']
#             else:
#                 item['orientation'] = 'landscape'
#                 item['duration'] = 10
#     return data

# # --- UI & STYLING ---
# st.set_page_config(layout="wide", page_title="Tone-controlled Video Captioning")
# st.markdown("""
# <style>
# @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600&display=swap');
# @keyframes highlight-new { 0% { border-color: transparent; box-shadow: none; } 25% { border-color: #facc15; box-shadow: 0 0 8px #facc15; } 75% { border-color: #facc15; box-shadow: 0 0 8px #facc15; } 100% { border-color: transparent; box-shadow: none; } }
# .part1-caption-box { border-radius: 10px; padding: 1rem 1.5rem; margin-bottom: 0.5rem; border: 2px solid transparent; transition: border-color 0.3s ease; }
# .new-caption-highlight { animation: highlight-new 1.5s ease-out forwards; }
# .slider-label { height: 80px; margin-bottom: 0; }
# .highlight-trait { color: #4f46e5; font-weight: 600; }
# .caption-text { font-family: 'Inter', sans-serif; font-weight: 500; font-size: 19px !important; line-height: 1.6; }
# .part1-caption-box strong { font-size: 18px; font-family: 'Inter', sans-serif; font-weight: 600; color: #111827 !important; }
# .part1-caption-box .caption-text { margin: 0.5em 0 0 0; color: #111827 !important; }
# .comparison-caption-box { background-color: var(--secondary-background-color); border-left: 5px solid #6366f1; padding: 1rem 1.5rem; margin: 1rem 0; border-radius: 0.25rem; }
# .comparison-caption-box strong { font-size: 18px; font-family: 'Inter', sans-serif; font-weight: 600; }
# .quiz-question-box { background-color: #F0F2F6; padding: 1rem 1.5rem; border: 1px solid var(--gray-300); border-bottom: none; border-radius: 0.5rem 0.5rem 0 0; }
# body[theme="dark"] .quiz-question-box { background-color: var(--secondary-background-color); }
# .quiz-question-box > strong { font-family: 'Inter', sans-serif; font-size: 18px; font-weight: 600; }
# .quiz-question-box .question-text-part { font-family: 'Inter', sans-serif; font-size: 19px; font-weight: 500; margin-left: 0.5em; }
# [data-testid="stForm"] { border: 1px solid var(--gray-300); border-top: none; border-radius: 0 0 0.5rem 0.5rem; padding: 0.5rem 1.5rem; margin-top: 0 !important; }
# .feedback-option { padding: 10px; border-radius: 8px; margin-bottom: 8px; border-width: 1px; border-style: solid; }
# .correct-answer { background-color: #d1fae5; border-color: #6ee7b7; color: #065f46; }
# .wrong-answer { background-color: #fee2e2; border-color: #fca5a5; color: #991b1b; }
# body[theme="dark"] .correct-answer { background-color: #064e3b; border-color: #10b981; color: #a7f3d0; }
# body[theme="dark"] .wrong-answer { background-color: #7f1d1d; border-color: #ef4444; color: #fecaca; }
# .normal-answer { background-color: white !important; border-color: #d1d5db !important; color: #111827 !important; }
# .stMultiSelect [data-baseweb="tag"] { background-color: #BDE0FE !important; color: #003366 !important; }
# div[data-testid="stSlider"] { max-width: 250px; }
# .reference-box { background-color: #FFFBEB; border: 1px solid #eab308; border-radius: 0.5rem; padding: 1rem 1.5rem; margin-top: 1.5rem; }
# body[theme="dark"] .reference-box { background-color: var(--secondary-background-color); }
# .reference-box h3 { margin-top: 0; padding-bottom: 0.5rem; font-size: 18px; font-weight: 600; }
# .reference-box ul { padding-left: 20px; margin: 0; }
# .reference-box li { margin-bottom: 0.5rem; }

# /* --- Title font consistency --- */
# h2 {
#     font-size: 1.75rem !important;
#     font-weight: 600 !important;
# }

# /* --- CUSTOM BUTTON STYLING --- */
# div[data-testid="stButton"] > button, .stForm [data-testid="stButton"] > button {
#     background-color: #FAFAFA; /* Very light grey */
#     color: #1F2937; /* Dark grey text for readability */
#     border: 1px solid #D1D5DB; /* Light grey border */
#     transition: background-color 0.2s ease, border-color 0.2s ease;
# }
# div[data-testid="stButton"] > button:hover, .stForm [data-testid="stButton"] > button:hover {
#     background-color: #F3F4F6; /* Slightly darker grey on hover */
#     border-color: #9CA3AF;
# }
# body[theme="dark"] div[data-testid="stButton"] > button, 
# body[theme="dark"] .stForm [data-testid="stButton"] > button {
#     background-color: #262730; /* Dark background */
#     color: #FAFAFA; /* Light text */
#     border: 1px solid #4B5563; /* Grey border for dark mode */
# }
# body[theme="dark"] div[data-testid="stButton"] > button:hover,
# body[theme="dark"] .stForm [data-testid="stButton"] > button:hover {
#     background-color: #374151; /* Lighter background on hover for dark mode */
#     border-color: #6B7280;
# }
# </style>
# """, unsafe_allow_html=True)

# # --- CENTRAL DICTIONARY ---
# DEFINITIONS = { 'Adventurous': 'Shows a willingness to take risks or try out new experiences.', 'Amusing': 'Causes lighthearted laughter or provides entertainment in a playful way.', 'Angry': 'Expresses strong annoyance, displeasure, or hostility towards an event.', 'Anxious': 'Shows a feeling of worry, nervousness, or unease about an uncertain outcome.', 'Appreciative': 'Expresses gratitude, admiration, or praise for an action or event.', 'Assertive': 'Expresses opinions or desires confidently and forcefully.', 'Caring': 'Displays kindness and concern for others.', 'Considerate': 'Shows careful thought and concern for the well-being or safety of others.', 'Critical': 'Expresses disapproving comments or judgments about an action or behavior.', 'Cynical (Doubtful, Skeptical)': "Shows a distrust of others' sincerity or integrity.", 'Emotional': 'Expresses feelings openly and strongly, such as happiness, sadness, or fear.', 'Energetic': 'Displays a high level of activity, excitement, or dynamism.', 'Enthusiastic': 'Shows intense and eager enjoyment or interest in an event.', 'Observant': 'States facts or details about an event in a neutral, notice-based way.', 'Objective (Detached, Impartial)': 'Presents information without personal feelings or bias.', 'Questioning': 'Raises questions or expresses uncertainty about a situation.', 'Reflective': 'Shows deep thought or contemplation about an event or idea.', 'Sarcastic': 'Uses irony or mockery to convey contempt, often by saying the opposite of what is meant.', 'Serious': 'Treats the subject with gravity and importance, without humor.', 'Advisory': 'Gives advice, suggestions, or warnings about a situation.', 'CallToAction': 'Encourages the reader to take a specific action.', 'Conversational': 'Uses an informal, personal, and chatty style, as if talking directly to a friend.', 'Exaggeration': 'Represents something as being larger, better, or worse than it really is for effect.', 'Factual': 'Presents information objectively and accurately, like a news report.', 'Instructional': 'Provides clear directions or information on how to do something.', 'Judgmental': 'Displays an overly critical or moralizing point of view on actions shown.', 'Metaphorical': 'Uses symbolic language or comparisons to describe something.', 'Persuasive': 'Aims to convince the reader to agree with a particular point of view.', 'Rhetorical Question': 'Asks a question not for an answer, but to make a point or create a dramatic effect.', 'Public Safety Alert': 'Intended to inform the public about potential dangers or safety issues.', 'Social Media Update': 'A casual post for sharing personal experiences or observations with friends and followers.', 'Driver Behavior Monitoring': 'Used in systems that track and analyze driving patterns for insurance or fleet management.', 'Law Enforcement Alert': 'A formal notification directed at police or traffic authorities to report violations.', 'Traffic Analysis': 'Data-driven content used for studying traffic flow, violations, and road conditions.', 'Community Road Safety Awareness': 'Aimed at educating the local community about road safety practices.', 'Public Safety Awareness': 'General information to raise public consciousness about safety.', 'Road Safety Education': 'Content designed to teach drivers or the public about safe road use.', 'Traffic Awareness': 'Information focused on current traffic conditions or general traffic issues.'}

# # --- NAVIGATION & STATE HELPERS ---
# def handle_next_quiz_question(view_key_to_pop):
#     part_keys = list(st.session_state.all_data['quiz'].keys())
#     current_part_key = part_keys[st.session_state.current_part_index]
#     questions_for_part = st.session_state.all_data['quiz'][current_part_key]
#     sample = questions_for_part[st.session_state.current_sample_index]
#     question_text = "N/A"
#     if "Tone Controllability" in current_part_key:
#         question_text = f"Intensity of '{sample['tone_to_compare']}' has {sample['comparison_type']}"
#     elif "Caption Quality" in current_part_key:
#         question_text = sample["questions"][st.session_state.current_rating_question_index]["question_text"]
#     else:
#         question_text = "Tone Identification"
    
#     success = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, sample, sample, st.session_state.last_choice, 'quiz', question_text, was_correct=st.session_state.is_correct)
#     if not success:
#         st.error("Failed to save response. Please check your connection and try again.")
#         return

#     if "Caption Quality" in current_part_key:
#         st.session_state.current_rating_question_index += 1
#         if st.session_state.current_rating_question_index >= len(sample["questions"]):
#             st.session_state.current_sample_index += 1
#             if st.session_state.current_sample_index >= len(questions_for_part):
#                  st.session_state.current_part_index += 1
#                  st.session_state.current_sample_index = 0
#             st.session_state.current_rating_question_index = 0
#     else:
#         st.session_state.current_sample_index += 1
#         if st.session_state.current_sample_index >= len(questions_for_part):
#             st.session_state.current_part_index += 1
#             st.session_state.current_sample_index = 0
#     st.session_state.pop(view_key_to_pop, None)
#     st.session_state.show_feedback = False

# def jump_to_part(part_index):
#     st.session_state.current_part_index = part_index; st.session_state.current_sample_index = 0
#     st.session_state.current_rating_question_index = 0; st.session_state.show_feedback = False

# def jump_to_study_part(part_number):
#     st.session_state.study_part = part_number; st.session_state.current_video_index = 0
#     st.session_state.current_caption_index = 0; st.session_state.current_comparison_index = 0
#     st.session_state.current_change_index = 0

# def restart_quiz():
#     st.session_state.page = 'quiz'; st.session_state.current_part_index = 0
#     st.session_state.current_sample_index = 0; st.session_state.current_rating_question_index = 0
#     st.session_state.show_feedback = False; st.session_state.score = 0; st.session_state.score_saved = False

# def render_comprehension_quiz(sample, view_state_key, proceed_step):
#     options_key = f"{view_state_key}_comp_options"
#     if options_key not in st.session_state:
#         options = sample['distractor_answers'] + [sample['road_event_answer']]
#         random.shuffle(options)
#         st.session_state[options_key] = options
#     else:
#         options = st.session_state[options_key]
        
#     st.markdown("##### Describe what is happening in the video")

#     if st.session_state[view_state_key]['comp_feedback']:
#         user_choice = st.session_state[view_state_key]['comp_choice']
#         correct_answer = sample['road_event_answer']
        
#         for opt in options:
#             is_correct = (opt == correct_answer)
#             is_user_choice = (opt == user_choice)
#             if is_correct:
#                 display_text = f"<strong>{opt} (Correct Answer)</strong>"
#                 css_class = "correct-answer"
#             elif is_user_choice:
#                 display_text = f"{opt} (Your selection)"
#                 css_class = "wrong-answer"
#             else:
#                 display_text = opt
#                 css_class = "normal-answer"
#             st.markdown(f'<div class="feedback-option {css_class}">{display_text}</div>', unsafe_allow_html=True)
#         if st.button("Proceed to Caption(s)", key=f"proceed_to_captions_{sample.get('sample_id') or sample.get('video_id')}"):
#             st.session_state[view_state_key]['step'] = proceed_step
#             st.rerun()
#     else:
#         with st.form(key=f"comp_quiz_form_{sample.get('sample_id') or sample.get('video_id')}"):
#             choice = st.radio("Select one option:", options, key=f"comp_radio_{sample.get('sample_id') or sample.get('video_id')}", index=None, label_visibility="collapsed")
#             if st.form_submit_button("Submit"):
#                 if choice:
#                     st.session_state[view_state_key]['comp_choice'] = choice
#                     st.session_state[view_state_key]['comp_feedback'] = True
#                     st.rerun()
#                 else:
#                     st.error("Please select an answer.")

# # --- Main App ---
# if 'page' not in st.session_state:
#     st.session_state.page = 'demographics'
#     st.session_state.current_part_index = 0; st.session_state.current_sample_index = 0
#     st.session_state.show_feedback = False; st.session_state.current_rating_question_index = 0
#     st.session_state.score = 0; st.session_state.score_saved = False
#     st.session_state.study_part = 1; st.session_state.current_video_index = 0
#     st.session_state.current_caption_index = 0; st.session_state.current_comparison_index = 0
#     st.session_state.current_change_index = 0; st.session_state.all_data = load_data()

# if st.session_state.all_data is None: st.stop()

# # --- Page Rendering Logic ---
# if st.session_state.page == 'demographics':
#     st.title("Tone-controlled Video Captioning")
#     if st.button("DEBUG: Skip to Main Study"):
#         st.session_state.email = "debug@test.com"; st.session_state.age = 25
#         st.session_state.gender = "Prefer not to say"; st.session_state.page = 'user_study_main'; st.rerun()
#     st.header("Welcome! Before you begin, please provide some basic information:")
#     email = st.text_input("Please enter your email address:")
#     age = st.selectbox("Age:", options=list(range(18, 61)), index=None, placeholder="Select your age...")
#     gender = st.selectbox("Gender:", options=["Male", "Female", "Other / Prefer not to say"], index=None, placeholder="Select your gender...")
    
#     if st.checkbox("I am over 18 and agree to participate in this study. I understand my responses will be recorded anonymously."):
#         if st.button("Next"):
#             email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
#             if not all([email, age, gender]): st.error("Please fill in all fields to continue.")
#             elif not re.match(email_regex, email): st.error("Please enter a valid email address.")
#             else:
#                 st.session_state.email = email; st.session_state.age = age; st.session_state.gender = gender
#                 st.session_state.page = 'intro_video'; st.rerun()

# elif st.session_state.page == 'intro_video':
#     st.title("Introductory Video")
#     _ , vid_col, _ = st.columns([1, 3, 1])
#     with vid_col:
#         st.video(INTRO_VIDEO_PATH, autoplay=True, muted=True)
#     if st.button("Next >>"): 
#         st.session_state.page = 'what_is_tone'
#         st.rerun()

# elif st.session_state.page == 'what_is_tone':
#     st.markdown("<h1 style='text-align: center;'>Tone and Writing Style</h1>", unsafe_allow_html=True)
    
#     st.markdown("<p style='text-align: center; font-size: 1.1rem;'><b>Tone</b> refers to the author's attitude or feeling about a subject, reflecting their emotional character (e.g., Sarcastic, Angry, Caring).</p>", unsafe_allow_html=True)
#     st.markdown("<p style='text-align: center; font-size: 1.1rem;'><b>Writing Style</b> refers to the author's technique or method of writing (e.g., Advisory, Factual, Conversational).</p>", unsafe_allow_html=True)
    
#     # UPDATED: Using columns to shift the subheader to the right
#     spacer, title = st.columns([1, 15])
#     with title:
#         st.subheader("For example:")
    
#     # Use equal columns with a small gap
#     col1, col2 = st.columns(2, gap="small")
#     with col1:
#         # This nesting remains the same to keep the video small
#         _, vid_col, _ = st.columns([1.5, 1, 0.25]) 
#         with vid_col:
#             video_path = "media/v_1772082398257127647_PAjmPcDqmPNuvb6p.mp4"
#             if os.path.exists(video_path):
#                 st.video(video_path, autoplay=True, muted=True, loop=True)
#             else:
#                 st.warning(f"Video not found at {video_path}")
#     with col2:
#         # This nesting remains the same to keep the image size
#         _, img_col, _ = st.columns([0.25, 2, 1])
#         with img_col:
#             image_path = "media/tone_meaning.jpg"
#             if os.path.exists(image_path):
#                 st.image(image_path)
#             else:
#                 st.warning(f"Image not found at {image_path}")

#     if st.button("Next >>"):
#         st.session_state.page = 'factual_info'
#         st.rerun()


# elif st.session_state.page == 'factual_info':
#     st.markdown("<h1 style='text-align: center;'>How to measure a caption's <span style='color: #4F46E5;'>Factual Accuracy?</span></h1>", unsafe_allow_html=True)
    
#     # Use the same 2:3 ratio for consistency
#     col1, col2 = st.columns([2, 3])
#     with col1:
#         # Use IDENTICAL nested columns to ensure the video size is the same
#         _, vid_col, _ = st.columns([1, 1.5, 1]) 
#         with vid_col:
#             video_path = "media/v_1772082398257127647_PAjmPcDqmPNuvb6p.mp4"
#             if os.path.exists(video_path):
#                 st.video(video_path, autoplay=True, muted=True, loop=True)
#             else:
#                 st.warning(f"Video not found at {video_path}")
#     with col2:
#         # This image will fill the larger column. The ratio change makes it slightly smaller than before.
#         image_path = "media/factual_info_new.jpg"
#         if os.path.exists(image_path):
#             st.image(image_path)
#         else:
#             st.warning(f"Image not found at {image_path}")

#     if st.button("Start Quiz"):
#         st.session_state.page = 'quiz'
#         st.rerun()


# elif st.session_state.page == 'quiz':
#     part_keys = list(st.session_state.all_data['quiz'].keys())
#     with st.sidebar:
#         st.header("Quiz Sections")
#         for i, name in enumerate(part_keys):
#             st.button(name, on_click=jump_to_part, args=(i,), use_container_width=True)

#     if st.session_state.current_part_index >= len(part_keys):
#         st.session_state.page = 'quiz_results'
#         st.rerun()

#     current_part_key = part_keys[st.session_state.current_part_index]
#     questions_for_part = st.session_state.all_data['quiz'][current_part_key]
#     current_index = st.session_state.current_sample_index
#     sample = questions_for_part[current_index]
#     sample_id = sample.get('sample_id', f'quiz_{current_index}')

#     timer_finished_key = f"timer_finished_quiz_{sample_id}"
#     if not st.session_state.get(timer_finished_key, False):
#         st.subheader("Watch the video")
#         with st.spinner(""):
#             col1, _ = st.columns([1.2, 1.5])
#             with col1:
#                 if sample.get("orientation") == "portrait":
#                     _, vid_col, _ = st.columns([1, 3, 1])
#                     with vid_col:
#                         st.video(sample['video_path'], autoplay=True, muted=True)
#                 else:
#                     st.video(sample['video_path'], autoplay=True, muted=True)
#             duration = sample.get('duration', 10)
#             time.sleep(duration)
#         st.session_state[timer_finished_key] = True
#         st.rerun()
#     else:
#         view_state_key = f'view_state_{sample_id}'
#         if view_state_key not in st.session_state:
#             st.session_state[view_state_key] = {'step': 1, 'summary_typed': False, 'comp_feedback': False, 'comp_choice': None}
#         current_step = st.session_state[view_state_key]['step']

#         def stream_text(text):
#             for word in text.split(" "): yield word + " "; time.sleep(0.08)
        
#         col1, col2 = st.columns([1.2, 1.5])

#         with col1:
#             if current_step < 5:
#                 st.subheader("Watch the video")
#             else:
#                 st.subheader("Video")

#             if sample.get("orientation") == "portrait":
#                 _, vid_col, _ = st.columns([1, 3, 1])
#                 with vid_col:
#                     st.video(sample['video_path'], autoplay=True, muted=True)
#             else:
#                 st.video(sample['video_path'], autoplay=True, muted=True)

#             if current_step == 1:
#                 if st.button("Proceed to Summary", key=f"quiz_summary_{sample_id}"):
#                     st.session_state[view_state_key]['step'] = 2
#                     st.rerun()
#             if current_step >= 2 and "video_summary" in sample:
#                 st.subheader("Video Summary")
#                 if st.session_state[view_state_key].get('summary_typed', False):
#                     st.info(sample["video_summary"])
#                 else:
#                     with st.empty():
#                         st.write_stream(stream_text(sample["video_summary"]))
#                     st.session_state[view_state_key]['summary_typed'] = True
#                 if current_step == 2:
#                     if st.button("Proceed to Question", key=f"quiz_comp_q_{sample_id}"):
#                         st.session_state[view_state_key]['step'] = 3
#                         st.rerun()

#         with col2:
#             display_title = re.sub(r'Part \d+: ', '', current_part_key)
#             if "Tone Identification" in current_part_key: display_title = f"{sample.get('category', 'Tone').title()} Identification"
#             elif "Tone Controllability" in current_part_key: display_title = f"{sample.get('category', 'Tone').title()} Comparison"
            
#             if current_step >= 5:
#                 st.subheader(display_title)

#             if current_step == 3 or current_step == 4:
#                 st.markdown("<br><br>", unsafe_allow_html=True) 
#                 render_comprehension_quiz(sample, view_state_key, proceed_step=5)

#             question_data = sample["questions"][st.session_state.current_rating_question_index] if "Caption Quality" in current_part_key else sample
#             terms_to_define = set()
#             if current_step >= 5:
#                 if "Tone Controllability" in current_part_key:
#                     st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{sample["caption_A"]}</p></div>', unsafe_allow_html=True)
#                     st.markdown(f'<div class="comparison-caption-box" style="margin-top:0.5rem;"><strong>Caption B</strong><p class="caption-text">{sample["caption_B"]}</p></div>', unsafe_allow_html=True)
#                 else:
#                     st.markdown(f'<div class="comparison-caption-box"><strong>Caption</strong><p class="caption-text">{sample["caption"]}</p></div>', unsafe_allow_html=True)
#                 if current_step == 5 and st.button("Show Questions", key=f"quiz_show_q_{sample_id}"):
#                     st.session_state[view_state_key]['step'] = 6
#                     st.rerun()
#             if current_step >= 6:
#                 question_text_display = ""
#                 if "Tone Controllability" in current_part_key:
#                     trait = sample['tone_to_compare']
#                     change_type = sample['comparison_type']
#                     question_text_display = f"From Caption A to B, has the level of <b class='highlight-trait'>{trait}</b> {change_type}?"
#                     terms_to_define.add(trait)
#                 elif "Caption Quality" in current_part_key:
#                     raw_text = question_data["question_text"]
#                     app_trait = sample.get("application")
#                     if app_trait:
#                         terms_to_define.add(app_trait)
#                         if app_trait in raw_text:
#                             question_text_display = raw_text.replace(app_trait, f"<b class='highlight-trait'>{app_trait}</b>")
#                         else: 
#                             question_text_display = raw_text
#                     else:
#                         question_text_display = raw_text
#                 elif question_data.get("question_type") == "multi":
#                     question_text_display = "Identify the 2 dominant tones in the caption"
#                     terms_to_define.update(question_data['options'])
#                 else:
#                     category_text = sample.get('category', 'tone').lower()
#                     if category_text == "tone":
#                         question_text_display = "What is the most dominant tone in the caption?"
#                     elif category_text == "writing style":
#                         question_text_display = "What is the most dominant writing style in the caption?"
#                     else:
#                         question_text_display = f"Identify the most dominant {category_text} in the caption"
#                     terms_to_define.update(question_data['options'])

#                 st.markdown(f'<div class="quiz-question-box"><strong>Question:</strong><span class="question-text-part">{question_text_display}</span></div>', unsafe_allow_html=True)
#                 if st.session_state.show_feedback:
#                     user_choice, correct_answer = st.session_state.last_choice, question_data.get('correct_answer')
#                     if not isinstance(user_choice, list): user_choice = [user_choice]
#                     if not isinstance(correct_answer, list): correct_answer = [correct_answer]
#                     st.write(" ")
#                     for opt in question_data['options']:
#                         is_correct, is_user_choice = opt in correct_answer, opt in user_choice
#                         css_class = "correct-answer" if is_correct else "wrong-answer" if is_user_choice else "normal-answer"
#                         display_text = f"<strong>{opt} (Correct Answer)</strong>" if is_correct else f"{opt} (Your selection)" if is_user_choice else opt
#                         st.markdown(f'<div class="feedback-option {css_class}">{display_text}</div>', unsafe_allow_html=True)
#                     st.info(f"**Explanation:** {question_data['explanation']}")
#                     st.button("Next Question", key=f"quiz_next_q_{sample_id}", on_click=handle_next_quiz_question, args=(view_state_key,))
#                 else:
#                     with st.form("quiz_form"):
#                         choice = None
#                         if question_data.get("question_type") == "multi":
#                             st.write("Select all that apply:")
#                             choice = [opt for opt in question_data['options'] if st.checkbox(opt, key=f"cb_{sample_id}_{opt}")]
#                         else:
#                             choice = st.radio("Select one option:", question_data['options'], key=f"radio_{sample_id}", index=None)
#                         if st.form_submit_button("Submit Answer"):
#                             if not choice:
#                                 st.error("Please select an option.")
#                             elif question_data.get("question_type") == "multi" and len(choice) != 2:
#                                 st.error("Please select exactly 2 options.")
#                             else:
#                                 st.session_state.last_choice = choice
#                                 correct_answer = question_data.get('correct_answer')
#                                 is_correct = (set(choice) == set(correct_answer)) if isinstance(correct_answer, list) else (choice == correct_answer)
#                                 st.session_state.is_correct = is_correct
#                                 if is_correct: st.session_state.score += 1
#                                 st.session_state.show_feedback = True
#                                 st.rerun()
#                 if terms_to_define:
#                     reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {DEFINITIONS.get(term)}</li>" for term in sorted(list(terms_to_define)) if DEFINITIONS.get(term)) + "</ul></div>"
#                     st.markdown(reference_html, unsafe_allow_html=True)

# elif st.session_state.page == 'quiz_results':
#     total_scorable_questions = sum(sum(len(item.get("questions",[])) for item in q_list) if "Quality" in p_name else len(q_list) for p_name, q_list in st.session_state.all_data['quiz'].items())
#     passing_score = 5; st.header(f"Your Final Score: {st.session_state.score} / {total_scorable_questions}")
#     if st.session_state.score >= passing_score:
#         st.success("**Status: Passed**");
#         if st.button("Proceed to User Study"): st.session_state.page = 'user_study_main'; st.rerun()
#     else: st.error("**Status: Failed**"); st.markdown(f"Unfortunately, you did not meet the passing score of {passing_score}. You can try again."); st.button("Take Quiz Again", on_click=restart_quiz)

# elif st.session_state.page == 'user_study_main':
#     if not st.session_state.all_data: st.error("Data could not be loaded."); st.stop()
#     def stream_text(text):
#         for word in text.split(" "): yield word + " "; time.sleep(0.08)
#     with st.sidebar:
#         st.header("Study Sections")
#         st.button("Part 1: Caption Rating", on_click=jump_to_study_part, args=(1,), use_container_width=True)
#         st.button("Part 2: Caption Comparison", on_click=jump_to_study_part, args=(2,), use_container_width=True)
#         st.button("Part 3: Tone Intensity Change", on_click=jump_to_study_part, args=(3,), use_container_width=True)

#     if st.session_state.study_part == 1:
#         all_videos = st.session_state.all_data['study']['part1_ratings']
#         video_idx, caption_idx = st.session_state.current_video_index, st.session_state.current_caption_index
#         if video_idx >= len(all_videos):
#             st.session_state.study_part = 2; st.rerun()

#         current_video = all_videos[video_idx]
#         video_id = current_video['video_id']
#         timer_finished_key = f"timer_finished_{video_id}"
        
#         if not st.session_state.get(timer_finished_key, False) and caption_idx == 0:
#             st.subheader("Watch the video")
#             with st.spinner(""):
#                 main_col, _ = st.columns([1, 1.8]) 
#                 with main_col:
#                     if current_video.get("orientation") == "portrait":
#                         _, vid_col, _ = st.columns([1, 3, 1])
#                         with vid_col: st.video(current_video['video_path'], autoplay=True, muted=True)
#                     else:
#                         st.video(current_video['video_path'], autoplay=True, muted=True)
#                     duration = current_video.get('duration', 10)
#                     time.sleep(duration)
#             st.session_state[timer_finished_key] = True
#             st.rerun()
#         else:
#             current_caption = current_video['captions'][caption_idx]
#             view_state_key = f"view_state_p1_{current_caption['caption_id']}"; summary_typed_key = f"summary_typed_{current_video['video_id']}"
#             q_templates = st.session_state.all_data['questions']['part1_questions']
#             questions_to_ask_raw = [q for q in q_templates if q['id'] != 'overall_relevance']; question_ids = [q['id'] for q in questions_to_ask_raw]
#             options_map = {"tone_relevance": ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"], "style_relevance": ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"],"factual_consistency": ["Contradicts", "Inaccurate", "Partially", "Mostly Accurate", "Accurate"], "usefulness": ["Not at all", "Slightly", "Moderately", "Very", "Extremely"], "human_likeness": ["Robotic", "Unnatural", "Moderate", "Very Human-like", "Natural"]}
            
#             if view_state_key not in st.session_state:
#                 initial_step = 5 if caption_idx > 0 else 1
#                 st.session_state[view_state_key] = {'step': initial_step, 'interacted': {qid: False for qid in question_ids}, 'comp_feedback': False, 'comp_choice': None}
#                 if caption_idx == 0: st.session_state[summary_typed_key] = False
            
#             current_step = st.session_state[view_state_key]['step']

#             def mark_interacted(q_id, view_key, question_index):
#                 if view_key in st.session_state and 'interacted' in st.session_state[view_key]:
#                     if not st.session_state[view_key]['interacted'][q_id]:
#                         st.session_state[view_key]['interacted'][q_id] = True
#                         st.session_state[view_state_key]['step'] = 6 + question_index + 1
            
#             title_col1, title_col2 = st.columns([1, 1.8])
#             with title_col1:
#                 st.subheader("Video")
#             with title_col2:
#                 if current_step >= 5:
#                     st.subheader("Caption Quality Rating")

#             col1, col2 = st.columns([1, 1.8])
#             with col1:
#                 if current_video.get("orientation") == "portrait":
#                     _, vid_col, _ = st.columns([1, 3, 1])
#                     with vid_col: st.video(current_video['video_path'], autoplay=True, muted=True)
#                 else:
#                     st.video(current_video['video_path'], autoplay=True, muted=True)

#                 if caption_idx == 0:
#                     if current_step == 1:
#                         if st.button("Proceed to Summary", key=f"proceed_summary_{video_idx}"):
#                             st.session_state[view_state_key]['step'] = 2; st.rerun()
#                     elif current_step >= 2:
#                         st.subheader("Video Summary")
#                         if st.session_state.get(summary_typed_key, False): st.info(current_video["video_summary"])
#                         else:
#                             with st.empty(): st.write_stream(stream_text(current_video["video_summary"]))
#                             st.session_state[summary_typed_key] = True
#                         if current_step == 2 and st.button("Proceed to Question", key=f"p1_proceed_comp_q_{video_idx}"):
#                             st.session_state[view_state_key]['step'] = 3; st.rerun()
#                 else:
#                     st.subheader("Video Summary"); st.info(current_video["video_summary"])
            
#             with col2:
#                 validation_placeholder = st.empty()
#                 if (current_step == 3 or current_step == 4) and caption_idx == 0:
#                     render_comprehension_quiz(current_video, view_state_key, proceed_step=5)

#                 terms_to_define = set()
#                 if current_step >= 5:
#                     colors = ["#FFEEEE", "#EBF5FF", "#E6F7EA"]; highlight_color = colors[caption_idx % len(colors)]
#                     caption_box_class = "part1-caption-box new-caption-highlight"
#                     st.markdown(f'<div class="{caption_box_class}" style="background-color: {highlight_color};"><strong>Caption:</strong><p class="caption-text">{current_caption["text"]}</p></div>', unsafe_allow_html=True)
#                     streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_p1_{current_caption['caption_id']}")
#                     if current_step == 5 and st.button("Show Questions", key=f"show_q_{current_caption['caption_id']}"):
#                         st.session_state[view_state_key]['step'] = 6; st.rerun()
#                 if current_step >= 6:
#                     control_scores = current_caption.get("control_scores", {})
#                     tone_traits = list(control_scores.get("tone", {}).keys())[:2]
#                     style_traits = list(control_scores.get("writing_style", {}).keys())[:2]
#                     application_text = current_caption.get("application", "the intended application")
                    
#                     terms_to_define.update(tone_traits); terms_to_define.update(style_traits); terms_to_define.add(application_text)

#                     def format_traits(traits):
#                         highlighted = [f"<b class='highlight-trait'>{trait}</b>" for trait in traits]
#                         if len(highlighted) > 1: return " and ".join(highlighted)
#                         return highlighted[0] if highlighted else ""

#                     tone_str = format_traits(tone_traits)
#                     style_str = format_traits(style_traits)
                    
#                     tone_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'tone_relevance'), "How {} does the caption sound?")
#                     style_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'style_relevance'), "How {} is the caption's writing style?")
#                     fact_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'factual_consistency'), "How factually accurate is the caption?")
#                     useful_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'usefulness'), "How useful is this caption for {}?")
#                     human_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'human_likeness'), "How human-like does this caption sound?")

#                     questions_to_ask = [
#                         {"id": "tone_relevance", "text": tone_q_template.format(tone_str)},
#                         {"id": "style_relevance", "text": style_q_template.format(style_str)},
#                         {"id": "factual_consistency", "text": fact_q_template},
#                         {"id": "usefulness", "text": useful_q_template.format(f"<b class='highlight-trait'>{application_text}</b>")},
#                         {"id": "human_likeness", "text": human_q_template}
#                     ]

#                     interacted_state = st.session_state.get(view_state_key, {}).get('interacted', {})
#                     question_cols_row1 = st.columns(3); question_cols_row2 = st.columns(3)

#                     def render_slider(q, col, q_index, view_key_arg):
#                         with col:
#                             slider_key = f"ss_{q['id']}_cap{caption_idx}"
#                             st.markdown(f"<div class='slider-label'><strong>{q_index + 1}. {q['text']}</strong></div>", unsafe_allow_html=True)
#                             st.select_slider(q['id'], options=options_map[q['id']], key=slider_key, label_visibility="collapsed", on_change=mark_interacted, args=(q['id'], view_key_arg, q_index), value=options_map[q['id']][0])
                    
#                     num_interacted = sum(1 for flag in interacted_state.values() if flag)
#                     questions_to_show = num_interacted + 1
                    
#                     if questions_to_show >= 1: render_slider(questions_to_ask[0], question_cols_row1[0], 0, view_state_key)
#                     if questions_to_show >= 2: render_slider(questions_to_ask[1], question_cols_row1[1], 1, view_state_key)
#                     if questions_to_show >= 3: render_slider(questions_to_ask[2], question_cols_row1[2], 2, view_state_key)
#                     if questions_to_show >= 4: render_slider(questions_to_ask[3], question_cols_row2[0], 3, view_state_key)
#                     if questions_to_show >= 5: render_slider(questions_to_ask[4], question_cols_row2[1], 4, view_state_key)
                    
#                     if questions_to_show > len(questions_to_ask):
#                         if st.button("Submit Ratings", key=f"submit_cap{caption_idx}"):
#                             all_interacted = all(interacted_state.get(qid, False) for qid in question_ids)
#                             if not all_interacted:
#                                 missing_qs = [i+1 for i, qid in enumerate(question_ids) if not interacted_state.get(qid, False)]
#                                 validation_placeholder.warning(f"⚠️ Please move the slider for question(s): {', '.join(map(str, missing_qs))}")
#                             else:
#                                 with st.spinner(""):
#                                     all_saved = True
#                                     responses_to_save = {qid: st.session_state.get(f"ss_{qid}_cap{caption_idx}") for qid in question_ids}
#                                     for q_id, choice_text in responses_to_save.items():
#                                         full_q_text = next((q['text'] for q in questions_to_ask if q['id'] == q_id), "N.A.")
#                                         if not save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_video, current_caption, choice_text, 'user_study_part1', full_q_text):
#                                             all_saved = False
#                                             break
#                                 if all_saved:
#                                     st.session_state.current_caption_index += 1
#                                     if st.session_state.current_caption_index >= len(current_video['captions']):
#                                         st.session_state.current_video_index += 1; st.session_state.current_caption_index = 0
#                                     st.session_state.pop(view_state_key, None); st.rerun()

#                     reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {DEFINITIONS.get(term)}</li>" for term in sorted(list(terms_to_define)) if DEFINITIONS.get(term)) + "</ul></div>"
#                     st.markdown(reference_html, unsafe_allow_html=True)

#     elif st.session_state.study_part == 2:
#         all_comparisons = st.session_state.all_data['study']['part2_comparisons']; comp_idx = st.session_state.current_comparison_index
#         if comp_idx >= len(all_comparisons): st.session_state.study_part = 3; st.rerun()

#         current_comp = all_comparisons[comp_idx]; comparison_id = current_comp['comparison_id']
#         timer_finished_key = f"timer_finished_{comparison_id}"
        
#         if not st.session_state.get(timer_finished_key, False):
#             st.subheader("Watch the video")
#             with st.spinner(""):
#                 main_col, _ = st.columns([1, 1.8])
#                 with main_col:
#                     if current_comp.get("orientation") == "portrait":
#                         _, vid_col, _ = st.columns([1, 3, 1])
#                         with vid_col: st.video(current_comp['video_path'], autoplay=True, muted=True)
#                     else:
#                         st.video(current_comp['video_path'], autoplay=True, muted=True)
#                     duration = current_comp.get('duration', 10)
#                     time.sleep(duration)
#             st.session_state[timer_finished_key] = True
#             st.rerun()
#         else:
#             view_state_key = f"view_state_p2_{comparison_id}"; summary_typed_key = f"summary_typed_p2_{comparison_id}"
#             q_templates = st.session_state.all_data['questions']['part2_questions']
#             question_ids = [q['id'] for q in q_templates]

#             if view_state_key not in st.session_state:
#                 st.session_state[view_state_key] = {'step': 1, 'interacted': {qid: False for qid in question_ids}, 'comp_feedback': False, 'comp_choice': None}
#                 st.session_state[summary_typed_key] = False

#             current_step = st.session_state[view_state_key]['step']
            
#             def mark_p2_interacted(q_id, view_key):
#                 if view_key in st.session_state and 'interacted' in st.session_state[view_key]:
#                     if not st.session_state[view_key]['interacted'][q_id]:
#                         st.session_state[view_key]['interacted'][q_id] = True
            
#             title_col1, title_col2 = st.columns([1, 1.8])
#             with title_col1:
#                 st.subheader("Video")
#             with title_col2:
#                 if current_step >= 5:
#                     st.subheader("Caption Comparison")

#             col1, col2 = st.columns([1, 1.8])
#             with col1:
#                 if current_comp.get("orientation") == "portrait":
#                     _, vid_col, _ = st.columns([1, 3, 1])
#                     with vid_col: st.video(current_comp['video_path'], autoplay=True, muted=True)
#                 else:
#                     st.video(current_comp['video_path'], autoplay=True, muted=True)

#                 if current_step == 1:
#                     if st.button("Proceed to Summary", key=f"p2_proceed_summary_{comparison_id}"):
#                         st.session_state[view_state_key]['step'] = 2; st.rerun()
#                 if current_step >= 2:
#                     st.subheader("Video Summary")
#                     if st.session_state.get(summary_typed_key, False): st.info(current_comp["video_summary"])
#                     else:
#                         with st.empty(): st.write_stream(stream_text(current_comp["video_summary"]))
#                         st.session_state[summary_typed_key] = True
#                     if current_step == 2 and st.button("Proceed to Question", key=f"p2_proceed_captions_{comparison_id}"):
#                         st.session_state[view_state_key]['step'] = 3; st.rerun()

#             with col2:
#                 if current_step == 3 or current_step == 4:
#                     render_comprehension_quiz(current_comp, view_state_key, proceed_step=5)

#                 validation_placeholder = st.empty()
#                 terms_to_define = set()
#                 if current_step >= 5:
#                     st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_comp["caption_A"]}</p></div>', unsafe_allow_html=True)
#                     st.markdown(f'<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_comp["caption_B"]}</p></div>', unsafe_allow_html=True)
#                     if current_step == 5 and st.button("Show Questions", key=f"p2_show_q_{comparison_id}"): st.session_state[view_state_key]['step'] = 6; st.rerun()
#                 if current_step >= 6:
#                     control_scores = current_comp.get("control_scores", {}); tone_traits = list(control_scores.get("tone", {}).keys()); style_traits = list(control_scores.get("writing_style", {}).keys())
#                     terms_to_define.update(tone_traits); terms_to_define.update(style_traits)
                    
#                     def format_part2_traits(traits):
#                         highlighted = [f"<b class='highlight-trait'>{trait}</b>" for trait in traits]
#                         if len(highlighted) > 1: return " and ".join(highlighted)
#                         return highlighted[0] if highlighted else ""

#                     tone_str = format_part2_traits(tone_traits)
#                     style_str = format_part2_traits(style_traits)
                    
#                     part2_questions = [{"id": q["id"], "text": q["text"].format(tone_str if 'tone' in q['id'] else style_str if 'style' in q['id'] else '')} for q in q_templates]
#                     options = ["Caption A", "Caption B", "Both A and B", "Neither A nor B"]
                    
#                     interacted_state = st.session_state.get(view_state_key, {}).get('interacted', {})
#                     num_interacted = sum(1 for flag in interacted_state.values() if flag)
#                     questions_to_show = num_interacted + 1
                    
#                     question_cols = st.columns(4)

#                     def render_radio(q, col, q_index, view_key_arg):
#                         with col:
#                             st.markdown(f"<div class='slider-label'><strong>{q_index + 1}. {q['text']}</strong></div>", unsafe_allow_html=True)
#                             st.radio(q['text'], options, index=None, label_visibility="collapsed", key=f"p2_{comparison_id}_{q['id']}", on_change=mark_p2_interacted, args=(q['id'], view_key_arg))

#                     if questions_to_show >= 1: render_radio(part2_questions[0], question_cols[0], 0, view_state_key)
#                     if questions_to_show >= 2: render_radio(part2_questions[1], question_cols[1], 1, view_state_key)
#                     if questions_to_show >= 3: render_radio(part2_questions[2], question_cols[2], 2, view_state_key)
#                     if questions_to_show >= 4: render_radio(part2_questions[3], question_cols[3], 3, view_state_key)

#                     if questions_to_show > len(part2_questions):
#                         if st.button("Submit Comparison", key=f"submit_comp_{comparison_id}"):
#                             responses = {q['id']: st.session_state.get(f"p2_{comparison_id}_{q['id']}") for q in part2_questions}
#                             if any(choice is None for choice in responses.values()):
#                                 validation_placeholder.warning("⚠️ Please answer all four questions before submitting.")
#                             else:
#                                 with st.spinner(""):
#                                     all_saved = True
#                                     for q_id, choice in responses.items():
#                                         full_q_text = next((q['text'] for q in part2_questions if q['id'] == q_id), "N.A.")
#                                         if not save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_comp, current_comp, choice, 'user_study_part2', full_q_text):
#                                             all_saved = False
#                                             break
#                                 if all_saved:
#                                     st.session_state.current_comparison_index += 1; st.session_state.pop(view_state_key, None); st.rerun()

#                     reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {DEFINITIONS.get(term)}</li>" for term in sorted(list(terms_to_define)) if DEFINITIONS.get(term)) + "</ul></div>"
#                     st.markdown(reference_html, unsafe_allow_html=True)

#     elif st.session_state.study_part == 3:
#         all_changes = st.session_state.all_data['study']['part3_intensity_change']
#         change_idx = st.session_state.current_change_index
#         if change_idx >= len(all_changes): st.session_state.page = 'final_thank_you'; st.rerun()
        
#         current_change = all_changes[change_idx]; change_id = current_change['change_id']
#         field_to_change = current_change['field_to_change']; field_type = list(field_to_change.keys())[0]
#         timer_finished_key = f"timer_finished_{change_id}"
        
#         if not st.session_state.get(timer_finished_key, False):
#             st.subheader("Watch the video")
#             with st.spinner(""):
#                 main_col, _ = st.columns([1, 1.8])
#                 with main_col:
#                     if current_change.get("orientation") == "portrait":
#                         _, vid_col, _ = st.columns([1, 3, 1])
#                         with vid_col: st.video(current_change['video_path'], autoplay=True, muted=True)
#                     else:
#                         st.video(current_change['video_path'], autoplay=True, muted=True)
#                     duration = current_change.get('duration', 10)
#                     time.sleep(duration)
#             st.session_state[timer_finished_key] = True
#             st.rerun()
#         else:
#             view_state_key = f"view_state_p3_{change_id}"; summary_typed_key = f"summary_typed_p3_{change_id}"
#             if view_state_key not in st.session_state:
#                 st.session_state[view_state_key] = {'step': 1, 'summary_typed': False, 'comp_feedback': False, 'comp_choice': None}
#             current_step = st.session_state[view_state_key]['step']
            
#             title_col1, title_col2 = st.columns([1, 1.8])
#             with title_col1:
#                 st.subheader("Video")
#             with title_col2:
#                 if current_step >= 5:
#                     st.subheader(f"{field_type.replace('_', ' ').title()} Comparison")

#             col1, col2 = st.columns([1, 1.8])
#             with col1:
#                 if current_change.get("orientation") == "portrait":
#                     _, vid_col, _ = st.columns([1, 3, 1])
#                     with vid_col: st.video(current_change['video_path'], autoplay=True, muted=True)
#                 else:
#                     st.video(current_change['video_path'], autoplay=True, muted=True)

#                 if current_step == 1:
#                     if st.button("Proceed to Summary", key=f"p3_proceed_summary_{change_id}"):
#                         st.session_state[view_state_key]['step'] = 2; st.rerun()
#                 if current_step >= 2:
#                     st.subheader("Video Summary")
#                     if st.session_state.get(summary_typed_key, False): st.info(current_change["video_summary"])
#                     else:
#                         with st.empty(): st.write_stream(stream_text(current_change["video_summary"]))
#                         st.session_state[summary_typed_key] = True
#                     if current_step == 2 and st.button("Proceed to Question", key=f"p3_proceed_captions_{change_id}"):
#                         st.session_state[view_state_key]['step'] = 3; st.rerun()
#             with col2:
#                 if current_step == 3 or current_step == 4:
#                     render_comprehension_quiz(current_change, view_state_key, proceed_step=5)

#                 if current_step >= 5:
#                     st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_change["caption_A"]}</p></div>', unsafe_allow_html=True)
#                     st.markdown(f'<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_change["caption_B"]}</p></div>', unsafe_allow_html=True)
#                     if current_step == 5 and st.button("Show Questions", key=f"p3_show_q_{change_id}"): st.session_state[view_state_key]['step'] = 6; st.rerun()
#                 if current_step >= 6:
#                     terms_to_define = set()
#                     trait = field_to_change[field_type]; terms_to_define.add(trait)
#                     with st.form(key=f"study_form_change_{change_idx}"):
#                         q_template_key = field_type.replace('_', ' ').title()
#                         q_template = st.session_state.all_data['questions']['part3_questions'][q_template_key]
#                         highlighted_trait = f"<b class='highlight-trait'>{trait}</b>"
#                         dynamic_question_raw = q_template.format(highlighted_trait, change_type=current_change['change_type'])
#                         dynamic_question_save = re.sub('<[^<]+?>', '', dynamic_question_raw)
#                         q2_text = "Is the core factual content consistent across both captions?"
#                         col_q1, col_q2 = st.columns(2)
#                         with col_q1:
#                             st.markdown(f'**1. {dynamic_question_raw}**', unsafe_allow_html=True)
#                             choice1 = st.radio("q1_label", ["Yes", "No"], index=None, horizontal=True, key=f"{current_change['change_id']}_q1", label_visibility="collapsed")
#                         with col_q2:
#                             st.markdown(f"**2. {q2_text}**")
#                             choice2 = st.radio("q2_label", ["Yes", "No"], index=None, horizontal=True, key=f"{current_change['change_id']}_q2", label_visibility="collapsed")
#                         if st.form_submit_button("Submit Answers"):
#                             if choice1 is None or choice2 is None: st.error("Please answer both questions.")
#                             else:
#                                 with st.spinner(""): 
#                                     success1 = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice1, 'user_study_part3', dynamic_question_save)
#                                     success2 = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice2, 'user_study_part3', q2_text)
#                                 if success1 and success2:
#                                     st.session_state.current_change_index += 1; st.session_state.pop(view_state_key, None); st.rerun()
#                     reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {DEFINITIONS.get(term)}</li>" for term in sorted(list(terms_to_define)) if DEFINITIONS.get(term)) + "</ul></div>"
#                     st.markdown(reference_html, unsafe_allow_html=True)

# elif st.session_state.page == 'final_thank_you':
#     st.title("Study Complete! Thank You!")
#     st.success("You have successfully completed all parts of the study. We sincerely appreciate your time and valuable contribution to our research!")

# # --- JavaScript ---
# js_script = """
# const parent_document = window.parent.document;

# // We always want the listener active, so we remove the check that prevents re-adding it.
# console.log("Attaching ArrowRight key listener.");
# parent_document.addEventListener('keyup', function(event) {
#     const activeElement = parent_document.activeElement;
#     // PREVENT ACTION IF USER IS TYPING OR FOCUSED ON A SLIDER
#     if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA' || activeElement.getAttribute('role') === 'slider')) {
#         return;
#     }

#     if (event.key === 'ArrowRight') {
#         event.preventDefault();
#         const targetButtonLabels = [
#             "Submit Ratings", "Submit Comparison", "Submit Answers", 
#             "Submit Answer", "Next Question", "Show Questions", 
#             "Proceed to Caption(s)", "Proceed to Captions", "Proceed to Caption",
#             "Proceed to Summary", "Proceed to Question", "Proceed to User Study", 
#             "Take Quiz Again", "Submit", "Next >>", "Start Quiz", "Next"
#         ];
#         const allButtons = Array.from(parent_document.querySelectorAll('button'));
#         const visibleButtons = allButtons.filter(btn => btn.offsetParent !== null); // Check if button is visible
        
#         for (const label of targetButtonLabels) {
#             // Find the LAST visible button on the page that matches the label
#             const targetButton = [...visibleButtons].reverse().find(btn => btn.textContent.trim().includes(label));
#             if (targetButton) {
#                 console.log('ArrowRight detected, clicking button:', targetButton.textContent);
#                 targetButton.click();
#                 break; // Exit loop once a button is clicked
#             }
#         }
#     }
# });
# """
# streamlit_js_eval(js_expressions=js_script, key="keyboard_listener_v2") # Changed key to ensure re-run

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
        # Check if secrets are loaded correctly
        if "gcp_service_account" not in st.secrets:
            st.error("GCP Service Account secret not found. Cannot connect to Google Sheets.")
            return None
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
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
    cleaned_question_text = re.sub('<[^<]+?>', '', question_text) if isinstance(question_text, str) else question_text
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
            if not header or list(response_dict.keys()) != header: # Also check if header matches
                 # Clear sheet and add new header if empty or mismatched
                 worksheet.clear()
                 worksheet.append_row(list(response_dict.keys()), value_input_option='USER_ENTERED')
            worksheet.append_row(list(response_dict.values()), value_input_option='USER_ENTERED')
            return True
        except gspread.exceptions.APIError as e:
             st.warning(f"Google Sheets API Error ({e}). Saving a local backup.")
             return save_response_locally(response_dict)
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
                    elif video_path: # Path exists but file doesn't
                        st.warning(f"Video file not found at path: {video_path}")
                        item['orientation'] = 'landscape'
                        item['duration'] = 10
                    else: # No video path provided
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
                    elif video_path:
                        st.warning(f"Video file not found at path: {video_path}")
                        item['orientation'] = 'landscape'
                        item['duration'] = 10
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
    border-radius: 0.5rem; /* Consistent rounded corners */
    padding: 0.5rem 1rem; /* Adjust padding */
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

# --- REMOVED go_to_previous_item function ---

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


# --- Sidebar Navigation Functions ---
def jump_to_quiz_sample(part_idx, sample_idx):
    st.session_state.page = 'quiz' # Ensure we are on the quiz page
    st.session_state.current_part_index = part_idx
    st.session_state.current_sample_index = sample_idx
    st.session_state.current_rating_question_index = 0 # Reset question index within sample
    st.session_state.show_feedback = False
    # Clean up potentially leftover view states when jumping
    for key in list(st.session_state.keys()):
        if key.startswith('view_state_'): # Clear all view states
            st.session_state.pop(key, None)
    st.rerun()

def jump_to_study_item(part_num, video_idx=None, caption_idx=None, comp_idx=None, change_idx=None):
    st.session_state.page = 'user_study_main' # Ensure we are on the study page
    st.session_state.study_part = part_num
    # Reset indices based on target part
    if part_num == 1:
        st.session_state.current_video_index = video_idx if video_idx is not None else 0
        st.session_state.current_caption_index = caption_idx if caption_idx is not None else 0
        st.session_state.current_comparison_index = 0
        st.session_state.current_change_index = 0
    elif part_num == 2:
        st.session_state.current_video_index = 0
        st.session_state.current_caption_index = 0
        st.session_state.current_comparison_index = comp_idx if comp_idx is not None else 0
        st.session_state.current_change_index = 0
    elif part_num == 3:
        st.session_state.current_video_index = 0
        st.session_state.current_caption_index = 0
        st.session_state.current_comparison_index = 0
        st.session_state.current_change_index = change_idx if change_idx is not None else 0
    # Clean up potentially leftover view states
    for key in list(st.session_state.keys()):
        if key.startswith('view_state_'): # Clear all view states
            st.session_state.pop(key, None)
    st.rerun()
# --- End Sidebar Navigation ---

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
        if key.startswith('view_state_'): # Clear all view states
            st.session_state.pop(key, None)
    st.rerun()

def render_comprehension_quiz(sample, view_state_key, proceed_step):
    options_key = f"{view_state_key}_comp_options"
    # Safely get distractors and answer
    distractors = sample.get('distractor_answers', [])
    correct = sample.get('road_event_answer', 'Correct Answer Missing') # Provide default
    if not distractors or correct == 'Correct Answer Missing':
         st.warning("Comprehension question data missing, cannot render quiz.")
         st.session_state[view_state_key]['step'] = proceed_step # Auto-proceed
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
            css_class = "correct-answer" if is_correct else ("wrong-answer" if is_user_choice else "normal-answer")
            display_text = f"<strong>{opt} (Correct Answer)</strong>" if is_correct else (f"{opt} (Your selection)" if is_user_choice else opt)
            st.markdown(f'<div class="feedback-option {css_class}">{display_text}</div>', unsafe_allow_html=True)

        proceed_key = f"proceed_to_captions_{sample.get('sample_id', sample.get('video_id', 'unknown'))}"
        # Button aligned right
        _, btn_col = st.columns([4, 1])
        with btn_col:
            if st.button("Next >>", key=proceed_key, use_container_width=True):
                st.session_state[view_state_key]['step'] = proceed_step
                st.rerun()
    else:
        form_key = f"comp_quiz_form_{sample.get('sample_id', sample.get('video_id', 'unknown'))}"
        radio_key = f"comp_radio_{sample.get('sample_id', sample.get('video_id', 'unknown'))}"
        with st.form(key=form_key):
            choice = st.radio("Select one option:", options, key=radio_key, index=None, label_visibility="collapsed")
            # Submit button inside form, default width
            if st.form_submit_button("Submit"): # Removed use_container_width
                if choice:
                    st.session_state[view_state_key]['comp_choice'] = choice
                    st.session_state[view_state_key]['comp_feedback'] = True
                    st.rerun()
                else:
                    st.error("Please select an answer.")
        # --- REMOVED Previous button ---

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
    age = st.selectbox(
        "Age:", options=list(range(18, 61)), index=None, placeholder="Select your age..."
    )
    gender = st.selectbox(
        "Gender:", options=["Male", "Female", "Other / Prefer not to say"], index=None, placeholder="Select your gender..."
    )

    if st.checkbox("I am over 18 and agree to participate in this study. I understand my responses will be recorded anonymously."):
        # Button aligned left
        nav_cols = st.columns([1, 6]) # Next, Spacer
        with nav_cols[0]:
            if st.button("Next", use_container_width=True, key="demographics_next"):
                email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not all([email, age is not None, gender is not None]): st.error("Please fill in all fields to continue.")
                elif not re.match(email_regex, email): st.error("Please enter a valid email address.")
                else:
                    st.session_state.email = email; st.session_state.age = age; st.session_state.gender = gender
                    st.session_state.page = 'intro_video'; st.rerun()

elif st.session_state.page == 'intro_video':
    st.title("Introductory Video")
    _ , vid_col, _ = st.columns([1, 3, 1])
    with vid_col:
        st.video(INTRO_VIDEO_PATH, autoplay=True, muted=True)

    # Buttons Prev (left), Next (left)
    nav_cols = st.columns([1, 1, 5])
    with nav_cols[0]:
        st.button("<< Previous", on_click=go_to_previous_page, args=('demographics',), key="prev_intro", use_container_width=True)
    with nav_cols[1]:
        if st.button("Next >>", key="next_intro", use_container_width=True):
            st.session_state.page = 'what_is_tone'
            st.rerun()

elif st.session_state.page == 'what_is_tone':
    st.markdown("<h1 style='text-align: center;'>Tone and Style</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.1rem;'><b>Tone</b> refers to the author's attitude or feeling about a subject, reflecting their emotional character (e.g., Sarcastic, Angry, Caring).</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.1rem;'><b>Style</b> refers to the author's technique or method of writing (e.g., Advisory, Factual, Conversational).</p>", unsafe_allow_html=True)
    spacer, title = st.columns([1, 15]); title.subheader("For example:")
    col1, col2 = st.columns(2, gap="small")
    with col1:
        _, vid_col, _ = st.columns([1.5, 1, 0.25])
        with vid_col:
            video_path = "media/v_1772082398257127647_PAjmPcDqmPNuvb6p.mp4"
            if os.path.exists(video_path):
                st.video(video_path, autoplay=True, muted=True, loop=True)
            else:
                st.warning(f"Video not found: {video_path}")
    with col2:
        _, img_col, _ = st.columns([0.25, 2, 1])
        with img_col:
            image_path = "media/tone_meaning.jpg"
            if os.path.exists(image_path):
                st.image(image_path)
            else:
                st.warning(f"Image not found: {image_path}")

    # Buttons Prev (left), Next (left)
    nav_cols = st.columns([1, 1, 5])
    with nav_cols[0]:
        st.button("<< Previous", on_click=go_to_previous_page, args=('intro_video',), key="prev_tone", use_container_width=True)
    with nav_cols[1]:
        if st.button("Next >>", key="next_tone", use_container_width=True):
            st.session_state.page = 'factual_info'; st.rerun()

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
                st.warning(f"Video not found: {video_path}")
    with col2:
        image_path = "media/factual_info_new.jpg"
        if os.path.exists(image_path):
            st.image(image_path)
        else:
            st.warning(f"Image not found: {image_path}")

    # Buttons Prev (left), Start (left)
    nav_cols = st.columns([1, 1, 5])
    with nav_cols[0]:
        st.button("<< Previous", on_click=go_to_previous_page, args=('what_is_tone',), key="prev_factual", use_container_width=True)
    with nav_cols[1]:
        if st.button("Start Quiz", key="start_quiz", use_container_width=True):
            st.session_state.page = 'quiz'; st.rerun()

# --- Quiz Page ---
elif st.session_state.page == 'quiz':
    part_keys = list(st.session_state.all_data.get('quiz', {}).keys())
    if not part_keys: st.error("Quiz data is missing."); st.stop()

    # --- Sidebar Navigation for Quiz ---
    with st.sidebar:
        st.header("Quiz Navigation")
        for i, name in enumerate(part_keys):
            with st.expander(f"{name}", expanded=(i == st.session_state.current_part_index)):
                questions_in_part = st.session_state.all_data['quiz'][name]
                for j, sample_item in enumerate(questions_in_part):
                    sample_id_display = sample_item.get('sample_id', f"Q {j+1}")
                    is_current = (i == st.session_state.current_part_index and j == st.session_state.current_sample_index)
                    button_label = f"➡️ {sample_id_display}" if is_current else sample_id_display
                    st.button(button_label, key=f"quiz_nav_{i}_{j}", on_click=jump_to_quiz_sample, args=(i, j), use_container_width=True)
    # --- End Sidebar ---

    if st.session_state.current_part_index >= len(part_keys):
        st.session_state.page = 'quiz_results'; st.rerun()

    current_part_key = part_keys[st.session_state.current_part_index]
    questions_for_part = st.session_state.all_data['quiz'][current_part_key]
    if not questions_for_part:
         st.warning(f"No questions for {current_part_key}. Skipping."); st.session_state.current_part_index += 1; st.rerun()

    current_index = st.session_state.current_sample_index
    if current_index >= len(questions_for_part):
        st.warning(f"End of samples for {current_part_key}."); st.session_state.current_part_index += 1; st.session_state.current_sample_index = 0; st.rerun()

    sample = questions_for_part[current_index]
    sample_id = sample.get('sample_id', f'quiz_{current_part_key}_{current_index}')
    timer_finished_key = f"timer_finished_quiz_{sample_id}"

    # --- Video Step ---
    if not st.session_state.get(timer_finished_key, False):
        st.subheader("Watch the video")
        st.button("DEBUG: Skip Video >>", on_click=lambda k=timer_finished_key: st.session_state.update({k: True}) or st.rerun(), key=f"skip_video_quiz_{sample_id}")
        with st.spinner("Video playing..."):
            col1, _ = st.columns([1.2, 1.5])
            with col1:
                video_path = sample.get('video_path');
                if video_path and os.path.exists(video_path): st.video(video_path, autoplay=True, muted=True)
                else: st.warning(f"Video not found for {sample_id}")
            duration = sample.get('duration', 1); time.sleep(duration)
        if not st.session_state.get(timer_finished_key, False):
            st.session_state[timer_finished_key] = True; st.rerun()
    else: # --- Post-Video Steps ---
        view_state_key = f'view_state_{sample_id}'
        if view_state_key not in st.session_state:
            st.session_state[view_state_key] = {'step': 1, 'summary_typed': False, 'comp_feedback': False, 'comp_choice': None}
        current_step = st.session_state[view_state_key]['step']

        def stream_text(text):
            for word in text.split(" "): yield word + " "; time.sleep(0.05)

        col1, col2 = st.columns([1.2, 1.5])
        with col1: # Video & Summary
            st.subheader("Video")
            video_path = sample.get('video_path');
            if video_path and os.path.exists(video_path): st.video(video_path, autoplay=True, muted=True, loop=True)
            else: st.warning(f"Video not found for {sample_id}")

            if "video_summary" in sample:
                 st.subheader("Video Summary")
                 if st.session_state[view_state_key].get('summary_typed', False): st.info(sample["video_summary"])
                 else:
                     with st.empty(): st.write_stream(stream_text(sample["video_summary"]))
                     st.session_state[view_state_key]['summary_typed'] = True

            # Buttons appear based on step
            if current_step == 1:
                # --- REMOVED "Watch Video Again" Button ---
                if sample.get('distractor_answers'):
                    if st.button("Proceed to Comprehension Question", key=f"quiz_comp_q_{sample_id}"):
                        st.session_state[view_state_key]['step'] = 2; st.rerun()
                else:
                     if st.button("Proceed to Caption(s)", key=f"quiz_skip_comp_{sample_id}"):
                         st.session_state[view_state_key]['step'] = 3; st.rerun()

            if current_step < 6:
                st.button("DEBUG: Skip to Questions >>", on_click=skip_to_questions, args=(view_state_key, None), key=f"skip_to_q_quiz_{sample_id}")

        with col2: # Questions
            display_title = re.sub(r'Part \d+: ', '', current_part_key) # Clean title
            if "Tone Identification" in current_part_key: display_title = f"{sample.get('category', 'Tone').title()} Identification"
            elif "Tone Controllability" in current_part_key: display_title = f"{sample.get('category', 'Tone').title()} Comparison"
            elif "Caption Quality" in current_part_key: display_title = "Caption Quality Rating"


            if current_step == 2 and sample.get('distractor_answers'): # Step 2: Comp Quiz
                 st.markdown("<br><br>", unsafe_allow_html=True)
                 render_comprehension_quiz(sample, view_state_key, proceed_step=3)

            if current_step >= 3: # Step 3+: Show Captions
                 if current_step >= 5: st.subheader(display_title) # Show title only from step 5
                 if "Tone Controllability" in current_part_key:
                     st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{sample.get("caption_A","")}</p></div>', unsafe_allow_html=True)
                     st.markdown(f'<div class="comparison-caption-box" style="margin-top:0.5rem;"><strong>Caption B</strong><p class="caption-text">{sample.get("caption_B","")}</p></div>', unsafe_allow_html=True)
                 else:
                     st.markdown(f'<div class="comparison-caption-box"><strong>Caption</strong><p class="caption-text">{sample.get("caption","")}</p></div>', unsafe_allow_html=True)

                 if current_step == 3: # Buttons after showing captions
                      # --- REMOVED Previous Button ---
                      # Show Questions button aligned right
                      _, btn_col_sq = st.columns([4,1])
                      with btn_col_sq:
                          if st.button("Show Questions", key=f"quiz_show_q_{sample_id}", use_container_width=True):
                              st.session_state[view_state_key]['step'] = 6; st.rerun()

            if current_step >= 6: # Step 6+: Show Questions
                question_data = {}
                options_list = []
                question_text_display = ""
                terms_to_define = set()

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
                    else: st.warning("End of quality questions."); handle_next_quiz_question(view_state_key); st.stop()
                elif "Tone Controllability" in current_part_key:
                    question_data = sample; options_list = question_data.get('options', ["Yes", "No"])
                    trait = sample.get('tone_to_compare'); change_type = sample.get('comparison_type','changed')
                    if trait: terms_to_define.add(trait)
                    question_text_display = f"From Caption A to B, has the level of <b class='highlight-trait'>{trait}</b> {change_type}?"
                else: # Identification
                    question_data = sample; options_list = question_data.get('options', [])
                    category_text = sample.get('category', 'tone').lower()
                    if category_text == "tone": question_text_display = "What is the most dominant tone in the caption?"
                    elif category_text == "style": question_text_display = "What is the most dominant style in the caption?"
                    else: question_text_display = f"Identify the most dominant {category_text} in the caption"
                    terms_to_define.update(o for o in options_list if isinstance(o, str))

                st.markdown(f'<div class="quiz-question-box"><strong>Question:</strong><span class="question-text-part">{question_text_display}</span></div>', unsafe_allow_html=True)
                if st.session_state.get('show_feedback', False):
                    user_choice = st.session_state.get('last_choice')
                    correct_answer = question_data.get('correct_answer')
                    if user_choice is not None:
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
                        # Next button aligned right
                        _, btn_col_nextq = st.columns([4,1])
                        with btn_col_nextq:
                            st.button("Next Question >>", key=f"quiz_next_q_{sample_id}", on_click=handle_next_quiz_question, args=(view_state_key,), use_container_width=True)
                    else: st.warning("Cannot show feedback.")
                else:
                    with st.form(f"quiz_form_{sample_id}"):
                        choice = None
                        q_type = question_data.get("question_type")
                        if q_type == "multi":
                            st.write("Select all that apply (exactly 2):")
                            choice = [opt for opt in options_list if st.checkbox(opt, key=f"cb_{sample_id}_{opt}")]
                        else:
                            choice = st.radio("Select one option:", options_list, key=f"radio_{sample_id}", index=None, label_visibility="collapsed")

                        # Smaller Submit button inside form
                        if st.form_submit_button("Submit Answer"): # Removed use_container_width
                            valid = True
                            if not choice: st.error("Please select an option."); valid = False
                            elif q_type == "multi" and len(choice) != 2: st.error("Please select exactly 2 options."); valid = False
                            if valid:
                                st.session_state.last_choice = choice
                                correct_ans = question_data.get('correct_answer')
                                is_correct = False
                                try:
                                    if isinstance(correct_ans, list): is_correct = (set(choice) == set(correct_ans))
                                    else: is_correct = (choice == correct_ans)
                                except TypeError: st.warning("Data mismatch.")
                                st.session_state.is_correct = is_correct
                                if is_correct: st.session_state.score += 1
                                st.session_state.show_feedback = True; st.rerun()
                    # --- REMOVED Previous button ---

                if terms_to_define:
                    definitions = st.session_state.all_data.get('definitions', {})
                    reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {definitions.get(term, 'Definition not found.')}</li>" for term in sorted(list(terms_to_define)) if term) + "</ul></div>"
                    st.markdown(reference_html, unsafe_allow_html=True)

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
    if not st.session_state.all_data: st.error("Data could not be loaded."); st.stop()
    def stream_text(text):
        for word in text.split(" "): yield word + " "; time.sleep(0.05)

    # --- Sidebar Navigation for Study ---
    with st.sidebar:
        st.header("Study Navigation")
        study_parts = st.session_state.all_data.get('study', {})

        # Part 1 Navigation
        with st.expander("Part 1: Caption Rating", expanded=(st.session_state.study_part == 1)):
            part1_data = study_parts.get('part1_ratings', [])
            for v_idx, video_item in enumerate(part1_data):
                video_id_disp = video_item.get('video_id', f"Video {v_idx+1}")
                captions = video_item.get('captions', [])
                for c_idx, caption_item in enumerate(captions):
                    caption_id_disp = caption_item.get('caption_id', f"{video_id_disp}_Cap{c_idx+1}")
                    is_current = (st.session_state.study_part == 1 and v_idx == st.session_state.current_video_index and c_idx == st.session_state.current_caption_index)
                    button_label = f"➡️ {caption_id_disp}" if is_current else caption_id_disp
                    st.button(button_label, key=f"study_nav_p1_{v_idx}_{c_idx}", on_click=jump_to_study_item, args=(1,), kwargs={'video_idx': v_idx, 'caption_idx': c_idx}, use_container_width=True)

        # Part 2 Navigation
        with st.expander("Part 2: Caption Comparison", expanded=(st.session_state.study_part == 2)):
            part2_data = study_parts.get('part2_comparisons', [])
            for comp_idx, comp_item in enumerate(part2_data):
                comp_id_disp = comp_item.get('comparison_id', f"Comp {comp_idx+1}")
                is_current = (st.session_state.study_part == 2 and comp_idx == st.session_state.current_comparison_index)
                button_label = f"➡️ {comp_id_disp}" if is_current else comp_id_disp
                st.button(button_label, key=f"study_nav_p2_{comp_idx}", on_click=jump_to_study_item, args=(2,), kwargs={'comp_idx': comp_idx}, use_container_width=True)

        # Part 3 Navigation
        with st.expander("Part 3: Style Intensity Change", expanded=(st.session_state.study_part == 3)):
            part3_data = study_parts.get('part3_intensity_change', [])
            for change_idx, change_item in enumerate(part3_data):
                change_id_disp = change_item.get('change_id', f"Change {change_idx+1}")
                is_current = (st.session_state.study_part == 3 and change_idx == st.session_state.current_change_index)
                button_label = f"➡️ {change_id_disp}" if is_current else change_id_disp
                st.button(button_label, key=f"study_nav_p3_{change_idx}", on_click=jump_to_study_item, args=(3,), kwargs={'change_idx': change_idx}, use_container_width=True)
    # --- End Sidebar ---

    # --- Part 1 ---
    if st.session_state.study_part == 1:
        all_videos = st.session_state.all_data['study'].get('part1_ratings', [])
        video_idx, caption_idx = st.session_state.current_video_index, st.session_state.current_caption_index
        if video_idx >= len(all_videos):
            st.session_state.study_part = 2; st.rerun()

        current_video = all_videos[video_idx]
        if caption_idx >= len(current_video.get('captions',[])):
             st.session_state.current_video_index += 1; st.session_state.current_caption_index = 0; st.rerun()

        video_id = current_video['video_id']
        timer_finished_key = f"timer_finished_p1_{video_id}"

        if not st.session_state.get(timer_finished_key, False) and caption_idx == 0:
            st.subheader("Watch the video")
            st.button("DEBUG: Skip Video >>", on_click=lambda k=timer_finished_key: st.session_state.update({k: True}) or st.rerun(), key=f"skip_video_p1_{video_id}")
            with st.spinner("Video playing..."):
                main_col, _ = st.columns([1, 1.8])
                with main_col:
                    video_path = current_video.get('video_path');
                    if video_path and os.path.exists(video_path): st.video(video_path, autoplay=True, muted=True)
                    else: st.warning(f"Video not found for {video_id}")
                    duration = current_video.get('duration', 1); time.sleep(duration)
            if not st.session_state.get(timer_finished_key, False):
                st.session_state[timer_finished_key] = True; st.rerun()
        else:
            current_caption = current_video['captions'][caption_idx]
            view_state_key = f"view_state_p1_{current_caption['caption_id']}"; summary_typed_key = f"summary_typed_p1_{current_video['video_id']}"
            q_templates = st.session_state.all_data['questions']['part1_questions']
            questions_to_ask_raw = [q for q in q_templates if q['id'] != 'overall_relevance']; question_ids = [q['id'] for q in questions_to_ask_raw]
            base_options_map = {"tone_relevance": ["Not at all", "Weak", "Moderate", "Strong", "Very Strong"], "factual_consistency": ["Contradicts", "Inaccurate", "Partially", "Mostly Accurate", "Accurate"], "usefulness": ["Not at all", "Slightly", "Moderately", "Very", "Extremely"], "human_likeness": ["Robotic", "Unnatural", "Moderate", "Very Human-like", "Natural"]}

            if view_state_key not in st.session_state:
                initial_step = 5 if caption_idx > 0 else 1
                st.session_state[view_state_key] = {'step': initial_step, 'interacted': {qid: False for qid in question_ids}, 'comp_feedback': False, 'comp_choice': None}
                if caption_idx == 0: st.session_state[summary_typed_key] = False
            current_step = st.session_state[view_state_key]['step']

            def mark_interacted(q_id, view_key, question_index):
                if view_key in st.session_state and 'interacted' in st.session_state[view_state_key]:
                    if not st.session_state[view_state_key]['interacted'][q_id]:
                        st.session_state[view_state_key]['interacted'][q_id] = True
                        st.session_state[view_state_key]['step'] = min(6 + len(question_ids), 6 + question_index + 1)

            title_col1, title_col2 = st.columns([1, 1.8]); title_col1.subheader("Video")
            if current_step >= 5: title_col2.subheader("Caption Quality Rating")

            col1, col2 = st.columns([1, 1.8])
            with col1:
                video_path = current_video.get('video_path');
                if video_path and os.path.exists(video_path): st.video(video_path, autoplay=True, muted=True, loop=True)
                else: st.warning(f"Video not found for {video_id}")

                if caption_idx == 0:
                    if current_step == 1:
                        if st.button("Proceed to Summary", key=f"proceed_summary_{video_idx}"): st.session_state[view_state_key]['step'] = 2; st.rerun()
                    elif current_step >= 2:
                        st.subheader("Video Summary")
                        if st.session_state.get(summary_typed_key, False): st.info(current_video["video_summary"])
                        else: 
                            with st.empty(): st.write_stream(stream_text(current_video["video_summary"])); st.session_state[summary_typed_key] = True
                        if current_step == 2:
                           # --- REMOVED Previous Button ---
                           if current_video.get('distractor_answers'):
                                if st.button("Proceed to Comprehension Question", key=f"p1_proceed_comp_q_{video_idx}"): st.session_state[view_state_key]['step'] = 3; st.rerun()
                           else:
                                if st.button("Proceed to Caption", key=f"p1_skip_comp_{video_idx}"): st.session_state[view_state_key]['step'] = 5; st.rerun()
                else:
                    st.subheader("Video Summary"); st.info(current_video["video_summary"])
                if current_step < 6:
                    st.button("DEBUG: Skip to Questions >>", on_click=skip_to_questions, args=(view_state_key, summary_typed_key), key=f"skip_to_q_p1_{video_id}")

            with col2:
                validation_placeholder = st.empty()
                if (current_step == 3 or current_step == 4) and caption_idx == 0 and current_video.get('distractor_answers'):
                    render_comprehension_quiz(current_video, view_state_key, proceed_step=5)

                if current_step >= 5:
                    colors = ["#FFEEEE", "#EBF5FF", "#E6F7EA"]; highlight_color = colors[caption_idx % len(colors)]
                    caption_box_class = "part1-caption-box new-caption-highlight"
                    st.markdown(f'<div class="{caption_box_class}" style="background-color: {highlight_color};"><strong>Caption {caption_idx + 1}:</strong><p class="caption-text">{current_caption["text"]}</p></div>', unsafe_allow_html=True)
                    streamlit_js_eval(js_expressions=JS_ANIMATION_RESET, key=f"anim_reset_p1_{current_caption['caption_id']}")
                    if current_step == 5:
                         # --- REMOVED Previous Button ---
                         _, btn_col_sq = st.columns([4,1])
                         with btn_col_sq:
                             if st.button("Show Questions", key=f"show_q_{current_caption['caption_id']}", use_container_width=True): st.session_state[view_state_key]['step'] = 6; st.rerun()

                if current_step >= 6:
                    terms_to_define = set()
                    control_scores = current_caption.get("control_scores", {})
                    tone_traits = list(control_scores.get("tone", {}).keys())[:2]
                    application_text = current_caption.get("application", "the intended application")
                    style_traits_data = list(control_scores.get("writing_style", {}).keys())
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
                    def format_traits(traits): hl = [f"<b class='highlight-trait'>{t}</b>" for t in traits if t]; return " and ".join(hl) if hl else ""
                    tone_str = format_traits(tone_traits)
                    style_str_highlighted = format_traits([main_style_trait])
                    tone_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'tone_relevance'), "How {} does the caption sound?")
                    fact_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'factual_consistency'), "How factually accurate is the caption?")
                    useful_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'usefulness'), "How useful is this caption for {}?")
                    human_q_template = next((q['text'] for q in questions_to_ask_raw if q['id'] == 'human_likeness'), "How human-like does this caption sound?")
                    if main_style_trait in style_q_config.get("overrides", {}) and "{}" not in style_q_text_template: final_style_q_text = style_q_text_template
                    else: final_style_q_text = default_text_template.format(style_str_highlighted)
                    questions_to_ask = [{"id": "tone_relevance", "text": tone_q_template.format(tone_str)}, {"id": "style_relevance", "text": final_style_q_text}, {"id": "factual_consistency", "text": fact_q_template}, {"id": "usefulness", "text": useful_q_template.format(f"<b class='highlight-trait'>{application_text}</b>")}, {"id": "human_likeness", "text": human_q_template}]
                    interacted_state = st.session_state[view_state_key].get('interacted', {}); question_cols_row1 = st.columns(3); question_cols_row2 = st.columns(3)
                    def render_slider(q, col, q_index, view_key_arg):
                        with col: slider_key = f"ss_{q['id']}_cap{caption_idx}"; st.markdown(f"<div class='slider-label'><strong>{q_index + 1}. {q['text']}</strong></div>", unsafe_allow_html=True); q_options = dynamic_options_map.get(q['id'], default_options); st.select_slider(q['id'], options=q_options, key=slider_key, label_visibility="collapsed", on_change=mark_interacted, args=(q['id'], view_key_arg, q_index), value=q_options[0])
                    num_interacted = sum(1 for flag in interacted_state.values() if flag); questions_to_show = num_interacted + 1
                    if questions_to_show >= 1: render_slider(questions_to_ask[0], question_cols_row1[0], 0, view_state_key)
                    if questions_to_show >= 2: render_slider(questions_to_ask[1], question_cols_row1[1], 1, view_state_key)
                    if questions_to_show >= 3: render_slider(questions_to_ask[2], question_cols_row1[2], 2, view_state_key)
                    if questions_to_show >= 4: render_slider(questions_to_ask[3], question_cols_row2[0], 3, view_state_key)
                    if questions_to_show >= 5: render_slider(questions_to_ask[4], question_cols_row2[1], 4, view_state_key)
                    if questions_to_show > len(questions_to_ask):
                        # --- REMOVED Previous Button ---
                        _, btn_col_submit = st.columns([5,1]) # Submit button aligned right
                        with btn_col_submit:
                            if st.button("Submit Ratings", key=f"submit_cap{caption_idx}", use_container_width=True):
                                all_interacted = all(interacted_state.get(qid, False) for qid in question_ids)
                                if not all_interacted: missing_qs = [i+1 for i, qid in enumerate(question_ids) if not interacted_state.get(qid, False)]; validation_placeholder.warning(f"⚠️ Please move the slider for question(s): {', '.join(map(str, missing_qs))}")
                                else:
                                    with st.spinner("Saving response..."):
                                        all_saved = True; responses_to_save = {qid: st.session_state.get(f"ss_{qid}_cap{caption_idx}") for qid in question_ids}
                                        for q_id, choice_text in responses_to_save.items(): full_q_text = next((q['text'] for q in questions_to_ask if q['id'] == q_id), "N/A");
                                        if not save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_video, current_caption, choice_text, 'user_study_part1', full_q_text): 
                                            all_saved = False; 
                                        
                                        if all_saved:
                                            st.session_state.current_caption_index += 1
                                            if st.session_state.current_caption_index >= len(current_video['captions']): st.session_state.current_video_index += 1; st.session_state.current_caption_index = 0
                                            st.session_state.pop(view_state_key, None); st.rerun()
                                        else: st.error("Failed to save all responses.")
                    definitions = st.session_state.all_data.get('definitions', {}); reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {definitions.get(term, 'Def not found.')}</li>" for term in sorted(list(terms_to_define)) if term) + "</ul></div>"; st.markdown(reference_html, unsafe_allow_html=True)
    # --- End Part 1 ---

    # --- Part 2 ---
    elif st.session_state.study_part == 2:
        all_comparisons = st.session_state.all_data['study'].get('part2_comparisons', [])
        comp_idx = st.session_state.current_comparison_index
        if comp_idx >= len(all_comparisons): st.session_state.study_part = 3; st.rerun()
        current_comp = all_comparisons[comp_idx]; comparison_id = current_comp['comparison_id']
        timer_finished_key = f"timer_finished_p2_{comparison_id}"
        if not st.session_state.get(timer_finished_key, False):
            st.subheader("Watch the video"); st.button("DEBUG: Skip Video >>", on_click=lambda k=timer_finished_key: st.session_state.update({k: True}) or st.rerun(), key=f"skip_video_p2_{comparison_id}")
            with st.spinner("Video playing..."):
                main_col, _ = st.columns([1, 1.8]);
                with main_col: video_path = current_comp.get('video_path'); st.video(video_path, autoplay=True, muted=True) if video_path and os.path.exists(video_path) else st.warning(f"Video not found: {comparison_id}")
                duration = current_comp.get('duration', 1); time.sleep(duration)
            if not st.session_state.get(timer_finished_key, False): st.session_state[timer_finished_key] = True; st.rerun()
        else:
            view_state_key = f"view_state_p2_{comparison_id}"; summary_typed_key = f"summary_typed_p2_{comparison_id}"
            q_templates = st.session_state.all_data['questions']['part2_questions']; question_ids = [q['id'] for q in q_templates]
            if view_state_key not in st.session_state: st.session_state[view_state_key] = {'step': 1, 'interacted': {qid: False for qid in question_ids}, 'comp_feedback': False, 'comp_choice': None}; st.session_state[summary_typed_key] = False
            current_step = st.session_state[view_state_key]['step']
            def mark_p2_interacted(q_id, view_key):
                if view_key in st.session_state and 'interacted' in st.session_state[view_state_key]:
                    if not st.session_state[view_state_key]['interacted'][q_id]: st.session_state[view_state_key]['interacted'][q_id] = True; q_index = question_ids.index(q_id); st.session_state[view_state_key]['step'] = min(6 + len(question_ids), 6 + q_index + 1)
            title_col1, title_col2 = st.columns([1, 1.8]); title_col1.subheader("Video")
            if current_step >= 5: title_col2.subheader("Caption Comparison")
            col1, col2 = st.columns([1, 1.8])
            with col1:
                video_path = current_comp.get('video_path'); st.video(video_path, autoplay=True, muted=True, loop=True) if video_path and os.path.exists(video_path) else st.warning(f"Video not found: {comparison_id}")
                if current_step == 1:
                    if st.button("Proceed to Summary", key=f"p2_proceed_summary_{comparison_id}"): st.session_state[view_state_key]['step'] = 2; st.rerun()
                if current_step >= 2:
                    st.subheader("Video Summary"); st.info(current_comp["video_summary"]) if st.session_state.get(summary_typed_key, False) else stream_text(current_comp["video_summary"]); st.session_state[summary_typed_key] = True
                    if current_step == 2:
                       # --- REMOVED Previous Button ---
                       if current_comp.get('distractor_answers'):
                           if st.button("Proceed to Comprehension Question", key=f"p2_proceed_captions_{comparison_id}"): st.session_state[view_state_key]['step'] = 3; st.rerun()
                       else:
                            if st.button("Proceed to Captions", key=f"p2_skip_comp_{comparison_id}"): st.session_state[view_state_key]['step'] = 5; st.rerun()
                if current_step < 6: st.button("DEBUG: Skip to Questions >>", on_click=skip_to_questions, args=(view_state_key, summary_typed_key), key=f"skip_to_q_p2_{comparison_id}")
            with col2:
                if (current_step == 3 or current_step == 4) and current_comp.get('distractor_answers'): render_comprehension_quiz(current_comp, view_state_key, proceed_step=5)
                validation_placeholder = st.empty(); terms_to_define = set()
                if current_step >= 5:
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_comp["caption_A"]}</p></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_comp["caption_B"]}</p></div>', unsafe_allow_html=True)
                    if current_step == 5:
                         # --- REMOVED Previous Button ---
                         _, btn_col_sq = st.columns([4,1])
                         with btn_col_sq:
                             if st.button("Show Questions", key=f"p2_show_q_{comparison_id}", use_container_width=True): st.session_state[view_state_key]['step'] = 6; st.rerun()
                if current_step >= 6:
                    control_scores = current_comp.get("control_scores", {}); tone_traits = list(control_scores.get("tone", {}).keys()); style_traits = list(control_scores.get("writing_style", {}).keys()); main_style_trait = style_traits[0] if style_traits else None
                    terms_to_define.update(tone_traits); terms_to_define.update(style_traits)
                    def format_part2_traits(traits): hl = [f"<b class='highlight-trait'>{t}</b>" for t in traits if t]; return " and ".join(hl) if hl else ""
                    tone_str = format_part2_traits(tone_traits); style_str = format_part2_traits(style_traits)
                    part2_questions = []
                    for q_template in q_templates:
                        q_id = q_template['id']; q_text = ""
                        if q_id == 'q2_style': style_q_config = q_template; default_text = style_q_config.get("default_text", "Which caption's style is more {}?"); override = style_q_config.get("overrides", {}).get(main_style_trait, {}); text_template = override.get("text", default_text); q_text = text_template.format(style_str) if "{}" in text_template else text_template
                        elif q_id == 'q1_tone': q_text = q_template['text'].format(tone_str)
                        else: q_text = q_template['text']
                        part2_questions.append({"id": q_id, "text": q_text})
                    options = ["Caption A", "Caption B", "Both Equal / Neither", "Cannot Determine"]
                    interacted_state = st.session_state[view_state_key].get('interacted', {}); num_interacted = sum(1 for flag in interacted_state.values() if flag); questions_to_show = num_interacted + 1
                    question_cols = st.columns(len(part2_questions))
                    def render_radio(q, col, q_index, view_key_arg):
                        with col: st.markdown(f"<div class='slider-label'><strong>{q_index + 1}. {q['text']}</strong></div>", unsafe_allow_html=True); st.radio(q['text'], options, index=None, label_visibility="collapsed", key=f"p2_{comparison_id}_{q['id']}", on_change=mark_p2_interacted, args=(q['id'], view_key_arg))
                    for i, q in enumerate(part2_questions):
                         if questions_to_show > i: render_radio(q, question_cols[i], i, view_state_key)
                    if questions_to_show > len(part2_questions):
                        # --- REMOVED Previous Button ---
                        _, btn_col_submit = st.columns([5,1])
                        with btn_col_submit:
                            if st.button("Submit Comparison", key=f"submit_comp_{comparison_id}", use_container_width=True):
                                responses = {q['id']: st.session_state.get(f"p2_{comparison_id}_{q['id']}") for q in part2_questions}
                                if any(choice is None for choice in responses.values()): validation_placeholder.warning("⚠️ Please answer all questions before submitting.")
                                else:
                                    with st.spinner("Saving response..."):
                                        all_saved = True
                                        for q_id, choice in responses.items(): full_q_text = next((q['text'] for q in part2_questions if q['id'] == q_id), "N/A");
                                        if not save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_comp, current_comp, choice, 'user_study_part2', full_q_text): all_saved = False; 
                                        if all_saved: st.session_state.current_comparison_index += 1; st.session_state.pop(view_state_key, None); st.rerun()
                                        else: st.error("Failed to save all responses.")
                    definitions = st.session_state.all_data.get('definitions', {}); reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {definitions.get(term, 'Def not found.')}</li>" for term in sorted(list(terms_to_define)) if term) + "</ul></div>"; st.markdown(reference_html, unsafe_allow_html=True)
    # --- End Part 2 ---

    # --- Part 3 ---
    elif st.session_state.study_part == 3:
        all_changes = st.session_state.all_data['study'].get('part3_intensity_change', [])
        change_idx = st.session_state.current_change_index
        if change_idx >= len(all_changes): st.session_state.page = 'final_thank_you'; st.rerun()
        current_change = all_changes[change_idx]; change_id = current_change['change_id']
        field_to_change = current_change.get('field_to_change', {}); field_type = list(field_to_change.keys())[0] if field_to_change else None
        timer_finished_key = f"timer_finished_p3_{change_id}"
        if not field_type: st.warning(f"Skipping {change_id}: missing 'field_to_change'."); st.session_state.current_change_index += 1; st.rerun()
        if not st.session_state.get(timer_finished_key, False):
            st.subheader("Watch the video"); st.button("DEBUG: Skip Video >>", on_click=lambda k=timer_finished_key: st.session_state.update({k: True}) or st.rerun(), key=f"skip_video_p3_{change_id}")
            with st.spinner("Video playing..."):
                main_col, _ = st.columns([1, 1.8]);
                with main_col: video_path = current_change.get('video_path'); st.video(video_path, autoplay=True, muted=True) if video_path and os.path.exists(video_path) else st.warning(f"Video not found: {change_id}")
                duration = current_change.get('duration', 1); time.sleep(duration)
            if not st.session_state.get(timer_finished_key, False): st.session_state[timer_finished_key] = True; st.rerun()
        else:
            view_state_key = f"view_state_p3_{change_id}"; summary_typed_key = f"summary_typed_p3_{change_id}"
            if view_state_key not in st.session_state: st.session_state[view_state_key] = {'step': 1, 'summary_typed': False, 'comp_feedback': False, 'comp_choice': None}
            current_step = st.session_state[view_state_key]['step']
            title_col1, title_col2 = st.columns([1, 1.8]); title_col1.subheader("Video")
            if current_step >= 5: display_field = "Style" if field_type == 'writing_style' else field_type.title(); title_col2.subheader(f"{display_field} Intensity Change")
            col1, col2 = st.columns([1, 1.8])
            with col1:
                video_path = current_change.get('video_path'); st.video(video_path, autoplay=True, muted=True, loop=True) if video_path and os.path.exists(video_path) else st.warning(f"Video not found: {change_id}")
                if current_step == 1:
                    if st.button("Proceed to Summary", key=f"p3_proceed_summary_{change_id}"): st.session_state[view_state_key]['step'] = 2; st.rerun()
                if current_step >= 2:
                    st.subheader("Video Summary"); st.info(current_change["video_summary"]) if st.session_state.get(summary_typed_key, False) else stream_text(current_change["video_summary"]); st.session_state[summary_typed_key] = True
                    if current_step == 2:
                       # --- REMOVED Previous Button ---
                       if current_change.get('distractor_answers'):
                           if st.button("Proceed to Comprehension Question", key=f"p3_proceed_captions_{change_id}"): st.session_state[view_state_key]['step'] = 3; st.rerun()
                       else:
                            if st.button("Proceed to Captions", key=f"p3_skip_comp_{change_id}"): st.session_state[view_state_key]['step'] = 5; st.rerun()
                if current_step < 6: st.button("DEBUG: Skip to Questions >>", on_click=skip_to_questions, args=(view_state_key, summary_typed_key), key=f"skip_to_q_p3_{change_id}")
            with col2:
                if (current_step == 3 or current_step == 4) and current_change.get('distractor_answers'): render_comprehension_quiz(current_change, view_state_key, proceed_step=5)
                if current_step >= 5:
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption A</strong><p class="caption-text">{current_change["caption_A"]}</p></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="comparison-caption-box"><strong>Caption B</strong><p class="caption-text">{current_change["caption_B"]}</p></div>', unsafe_allow_html=True)
                    if current_step == 5:
                         # --- REMOVED Previous Button ---
                         _, btn_col_sq = st.columns([4,1])
                         with btn_col_sq:
                             if st.button("Show Questions", key=f"p3_show_q_{change_id}", use_container_width=True): st.session_state[view_state_key]['step'] = 6; st.rerun()
                if current_step >= 6:
                    terms_to_define = set(); trait = field_to_change.get(field_type);
                    if trait: terms_to_define.add(trait)
                    form_submitted_key = f"form_submitted_{change_idx}"
                    if form_submitted_key not in st.session_state: st.session_state[form_submitted_key] = False
                    with st.form(key=f"study_form_change_{change_idx}"):
                        q_template_key = "Style" if field_type == 'writing_style' else field_type.title()
                        q_template = st.session_state.all_data['questions']['part3_questions'].get(q_template_key, "Q template missing for {}")
                        highlighted_trait = f"<b class='highlight-trait'>{trait}</b>" if trait else "trait"
                        dynamic_question_raw = q_template.format(highlighted_trait, change_type=current_change.get('change_type', 'changed'))
                        dynamic_question_save = re.sub('<[^<]+?>', '', dynamic_question_raw)
                        q2_text = "Is the core factual content consistent across both captions?"
                        col_q1, col_q2 = st.columns(2)
                        with col_q1: st.markdown(f'<div class="part3-question-text">1. {dynamic_question_raw}</div>', unsafe_allow_html=True); choice1 = st.radio("q1_label", ["Yes", "No"], index=None, horizontal=True, key=f"{change_id}_q1", label_visibility="collapsed")
                        with col_q2: st.markdown(f"<div class='part3-question-text'>2. {q2_text}</div>", unsafe_allow_html=True); choice2 = st.radio("q2_label", ["Yes", "No"], index=None, horizontal=True, key=f"{change_id}_q2", label_visibility="collapsed")
                        # Smaller Submit button
                        submitted = st.form_submit_button("Submit Answers") # Removed use_container_width
                        if submitted: st.session_state[form_submitted_key] = True
                    # --- REMOVED Previous Button ---
                    if st.session_state.get(form_submitted_key, False):
                        choice1 = st.session_state.get(f"{change_id}_q1"); choice2 = st.session_state.get(f"{change_id}_q2")
                        if choice1 is None or choice2 is None: st.error("Please answer both questions."); st.session_state[form_submitted_key] = False
                        else:
                            with st.spinner("Saving response..."): success1 = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice1, 'user_study_part3', dynamic_question_save); success2 = save_response(st.session_state.email, st.session_state.age, st.session_state.gender, current_change, current_change, choice2, 'user_study_part3', q2_text)
                            st.session_state.pop(form_submitted_key, None)
                            if success1 and success2: st.session_state.current_change_index += 1; st.session_state.pop(view_state_key, None); st.rerun()
                            else: st.error("Failed to save response.")
                    definitions = st.session_state.all_data.get('definitions', {}); reference_html = '<div class="reference-box"><h3>Reference</h3><ul>' + "".join(f"<li><strong>{term}:</strong> {definitions.get(term, 'Def not found.')}</li>" for term in sorted(list(terms_to_define)) if term) + "</ul></div>"; st.markdown(reference_html, unsafe_allow_html=True)
    # --- End Part 3 ---

elif st.session_state.page == 'final_thank_you':
    st.title("Study Complete! Thank You!")
    st.success("You have successfully completed all parts of the study. We sincerely appreciate your time and valuable contribution to our research!")

# --- JavaScript ---
js_script = """
const parent_document = window.parent.document;
if (!parent_document.arrowKeyListenerAttached) {
    console.log("Attaching ArrowRight key listener.");
    parent_document.addEventListener('keyup', function(event) {
        const activeElement = parent_document.activeElement;
        if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA' || activeElement.getAttribute('role') === 'slider')) { return; }
        if (event.key === 'ArrowRight') {
            event.preventDefault();
            const targetButtonLabels = ["Submit Ratings", "Submit Comparison", "Submit Answers", "Submit Answer", "Next Question", "Show Questions", "Proceed to Caption(s)", "Proceed to Summary", "Proceed to Question", "Proceed to User Study", "Take Quiz Again", "Submit", "Next >>", "Start Quiz", "Next", "DEBUG: Skip Video >>", "DEBUG: Skip to Questions >>"];
            const allButtons = Array.from(parent_document.querySelectorAll('button'));
            const visibleButtons = allButtons.filter(btn => btn.offsetParent !== null);
            let buttonToClick = null;
            for (const label of targetButtonLabels) { const foundButton = [...visibleButtons].reverse().find(btn => btn.textContent.trim().includes(label)); if (foundButton) { buttonToClick = foundButton; break; } }
            if (buttonToClick) { console.log('ArrowRight clicking:', buttonToClick.textContent); buttonToClick.click(); }
            else { console.log('ArrowRight no target button.'); }
        }
    });
    parent_document.arrowKeyListenerAttached = true;
} else { console.log("ArrowRight listener already attached."); }
"""
streamlit_js_eval(js_expressions=js_script, key="keyboard_listener_v6")