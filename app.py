import os
from pathlib import Path
import streamlit as st
from google import genai
from google.genai import types

# ==============================================================================
# 1. PAGE CONFIGURATION & EMBED OPTIMIZATION
# ==============================================================================
st.set_page_config(
    page_title="BBMB 4050 Quiz Bot",
    page_icon="🧬",
    layout="wide"
)

# Hide Streamlit UI elements (header, footer, menu) for seamless Canvas iframe embedding
st.markdown("""
    
""", unsafe_allow_html=True)

# ==============================================================================
# 2. GEMINI CLIENT INITIALIZATION
# ==============================================================================
# Retrieves key from Streamlit Secrets (Cloud) or local environment variable
api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))

if not api_key:
    st.error("Missing Gemini API Key. Please configure GEMINI_API_KEY in your Streamlit Secrets.")
    st.stop()

client = genai.Client(api_key=api_key)

# ==============================================================================
# 3. SYLLABUS ORDER & FILE DISCOVERY (NO LECTURE NUMBERS)
# ==============================================================================
QUIZ_DIR = Path("quizzes")
SYSTEM_PROMPT_PATH = Path("system_prompt.txt")

# Strict chronological order of syllabus topics
SYLLABUS_ORDER = [
    "Light Reactions of Photosynthesis I",
    "Light Reactions of Photosynthesis II",
    "The Calvin Cycle",
    "The Pentose Phosphate Pathway",
    "Glycogen Metabolism I",
    "Glycogen Metabolism II",
    "Fatty Acid Metabolism I",
    "Fatty Acid Metabolism II",
    "Protein Catabolism I",
    "Protein Catabolism II",
    "Integration of Metabolism I",
    "Integration of Metabolism II",
    "Biosynthesis of Membrane Lipids and Sterols I",
    "Biosynthesis of Membrane Lipids and Sterols II",
    "Biosynthesis of Membrane Lipids and Sterols III",
    "Biosynthesis of Amino Acids I",
    "Biosynthesis of Amino Acids II",
    "Nucleotide Metabolism I",
    "Nucleotide Metabolism II",
    "DNA Replication, Recombination, and Repair I",
    "DNA Replication, Recombination, and Repair II",
    "DNA Replication, Recombination, and Repair III",
    "RNA Synthesis and Processing I",
    "RNA Synthesis and Processing II",
    "RNA Synthesis and Processing III",
    "Protein Synthesis and Processing I",
    "Protein Synthesis and Processing II",
    "Protein Synthesis and Processing III",
    "Control of Gene Expression I",
    "Control of Gene Expression II",
    "Control of Gene Expression III",
    "Viruses and Transposons I",
    "Viruses and Transposons II",
    "The Immune System I",
    "The Immune System II",
    "Drug Development",
    "Exploring Evolution and Bioinformatics",
    "Molecular Motors",
    "Sensory Systems",
]

if not QUIZ_DIR.exists():
    st.error("The 'quizzes/' folder does not exist. Please create it in your repository root.")
    st.stop()

if not SYSTEM_PROMPT_PATH.exists():
    st.error("Missing 'system_prompt.txt'. Please ensure it is present in the repository root.")
    st.stop()

# Build mapping: "Topic Name" -> Path("quizzes/Quiz - Topic Name.md")
topic_options = {}
for topic in SYLLABUS_ORDER:
    target_file = QUIZ_DIR / f"Quiz - {topic}.md"
    if target_file.exists():
        topic_options[topic] = target_file

# Fallback: if files exist in /quizzes that aren't explicitly listed above, append them
for extra_file in sorted(QUIZ_DIR.glob("Quiz - *.md")):
    clean_title = extra_file.stem.replace("Quiz - ", "").strip()
    if clean_title not in topic_options:
        topic_options[clean_title] = extra_file

if not topic_options:
    st.warning("No quiz files found in 'quizzes/'. Please upload files named 'Quiz - [Topic].md'.")
    st.stop()

# ==============================================================================
# 4. SIDEBAR NAVIGATION & SESSION CONTROLS
# ==============================================================================
st.sidebar.title("🧬 BBMB 4050")
st.sidebar.markdown("**Quiz Bot**")

selected_topic = st.sidebar.selectbox(
    "Choose Course Topic:",
    options=list(topic_options.keys())
)

selected_file_path = topic_options[selected_topic]

# Reset button for students who want to restart the oral check from scratch
if st.sidebar.button("🔄 Restart Active Topic"):
    st.session_state.current_topic = None
    st.session_state.messages = []
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(
    "💡 **Tips:**\n"
    "- Type `'Start Mastery Check'` to take the formal 5-question quiz.\n"
    "- Or ask open questions in **Office Hours Mode** to explore mechanisms.\n"
    "- Bullet points and chemical fragments are welcome!"
)

# ==============================================================================
# 5. STATE MANAGEMENT & GEMINI CHAT INITIALIZATION
# ==============================================================================
# Reinitialize chat whenever a new topic is chosen or session is reset
if "current_topic" not in st.session_state or st.session_state.current_topic != selected_topic:
    st.session_state.current_topic = selected_topic
    st.session_state.messages = []

    # Read base prompt and the isolated rubric for the selected topic
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        base_instructions = f.read()

    with open(selected_file_path, "r", encoding="utf-8") as f:
        active_quiz_content = f.read()

    full_system_instruction = f"""
{base_instructions}

==================================================
CURRENT ACTIVE LECTURE QUIZ & RUBRIC:
{active_quiz_content}
==================================================
"""

    # Create fresh chat instance using Gemini 2.5 Flash
    st.session_state.chat = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=full_system_instruction,
            temperature=0.2,  # Low temperature ensures adherence to the rubric
        )
    )

# ==============================================================================
# 6. MAIN CHAT DISPLAY & EXECUTION
# ==============================================================================
st.subheader(f"{selected_topic}")

# Render chat history for current topic
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Capture student input
if user_input := st.chat_input("Enter your response or say 'Start Mastery Check'..."):
    # Append & render user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Stream model response
    with st.chat_message("assistant"):
        response_box = st.empty()
        accumulated_text = ""

        try:
            stream = st.session_state.chat.send_message_stream(user_input)
            for chunk in stream:
                if chunk.text:
                    accumulated_text += chunk.text
                    response_box.markdown(accumulated_text + "▌")

            response_box.markdown(accumulated_text)
            st.session_state.messages.append({"role": "assistant", "content": accumulated_text})

        except Exception as e:
            st.error(f"Error communicating with Gemini: {str(e)}")