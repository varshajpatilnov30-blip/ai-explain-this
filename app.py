"""
Explain This - AI Web App for Simplifying Confusing Documents
Built with Streamlit and Google Gemini.
"""

import os
import io
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from PIL import Image

import extractor
import explainer

# Load environment variables (.env if present)
load_dotenv()

# App configuration
st.set_page_config(
    page_title="Explain This - Document Simplifier",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom student-friendly CSS
st.markdown("""
    <style>
    /* Main container styling */
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    
    /* Section card styles */
    .card-box {
        background-color: #F8FAFC;
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        border: 1px solid #E2E8F0;
    }
    
    .card-heading {
        font-size: 1.15rem;
        font-weight: 600;
        color: #1E293B;
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* Deadline badges */
    .deadline-urgent {
        background-color: #FEF2F2;
        border-left: 6px solid #DC2626;
        padding: 1rem 1.2rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    .deadline-urgent-text {
        color: #991B1B;
        font-size: 1.2rem;
        font-weight: 700;
        margin: 0;
    }
    .deadline-none {
        background-color: #F0FDF4;
        border-left: 6px solid #16A34A;
        padding: 1rem 1.2rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    .deadline-none-text {
        color: #166534;
        font-size: 1.1rem;
        font-weight: 600;
        margin: 0;
    }
    
    /* Warning box */
    .caution-box {
        background-color: #FFFBEB;
        border-left: 5px solid #F59E0B;
        padding: 1rem;
        border-radius: 6px;
        margin-top: 0.5rem;
    }
    
    .step-item {
        background: #FFFFFF;
        border-radius: 6px;
        padding: 0.6rem 0.8rem;
        margin-bottom: 0.4rem;
        border: 1px solid #E2E8F0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.markdown("### ⚙️ Settings & API Key")
    
    # Check default API key from environment
    default_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    
    api_key_input = st.text_input(
        "Gemini API Key",
        value=st.session_state.get("gemini_api_key", default_key),
        type="password",
        help="Free key from Google AI Studio (https://aistudio.google.com/)",
        placeholder="Enter your AI Studio API key...",
    )
    st.session_state["gemini_api_key"] = api_key_input

    if api_key_input:
        st.success("API Key configured! ✨")
    else:
        st.warning("Please enter your Gemini API key to run explanations.")
        st.caption("👉 Get a free key at [Google AI Studio](https://aistudio.google.com/)")

    st.markdown("---")
    
    model_choice = st.selectbox(
        "AI Model",
        options=["gemini-3.8-flash"],
        index=0,
        help="Gemini 2.5 Flash is recommended for fast, accurate multimodal document understanding.",
    )

    st.markdown("---")
    st.markdown("### 🧪 Quick Test Samples")
    st.caption("Try one of these sample documents without uploading your own file:")
    
    sample_options = {
        "None (Upload my own)": None,
        "📄 College Exam Fee Notice (has deadline)": "sample_docs/college_exam_fee_circular.txt",
        "📄 Scholarship Guidelines (NO deadline)": "sample_docs/scholarship_policy_no_deadline.txt",
        "📑 Hostel Electricity Bill (PDF)": "sample_docs/sample_hostel_bill.pdf",
        "🖼️ Broadband Bill Notice (PNG Image)": "sample_docs/sample_broadband_bill.png",
    }
    
    chosen_sample = st.selectbox("Load Sample Document:", list(sample_options.keys()))

    st.markdown("---")
    st.markdown("### 💡 What can I upload?")
    st.markdown(
        """
        - 🎓 **College circulars & fee notices**
        - 🏛️ **Government notifications**
        - 🏦 **Bank & insurance policies**
        - 💼 **Job descriptions & offer letters**
        - 📜 **Terms & conditions**
        - 💡 **Utility & electricity bills**
        """
    )


# ----------------- MAIN CONTENT -----------------
st.markdown('<div class="main-title">Explain This 📄💡</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">'
    'Upload confusing circulars, bills, or government notices. '
    'Get an instant, plain-English breakdown of what it is, what you need to do, and when it is due.'
    '</div>',
    unsafe_allow_html=True,
)

# --- MANAGE DOCUMENT SOURCE ---
file_bytes = None
file_name = None
extracted_text = ""
is_scanned_or_image = False
mime_type = "text/plain"

# Check if sample document selected
sample_path = sample_options.get(chosen_sample)

input_tab1, input_tab2 = st.tabs(["📁 Upload Document (PDF / Image / Text)", "✍️ Paste Document Text"])

with input_tab1:
    uploaded_file = st.file_uploader(
        "Upload your document",
        type=["pdf", "png", "jpg", "jpeg", "webp", "txt"],
        help="Upload a circular, notice, bill, or policy in PDF, image, or text format.",
        key="main_document_uploader"
    )
    
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_name = uploaded_file.name
    elif sample_path and Path(sample_path).exists():
        st.info(f"Loaded sample document: **{Path(sample_path).name}**")
        with open(sample_path, "rb") as f:
            file_bytes = f.read()
            file_name = Path(sample_path).name

with input_tab2:
    pasted_text = st.text_area(
        "Paste the raw text of the circular or document here:",
        height=180,
        placeholder="Paste circular or notice text here...",
        key="user_pasted_text_input"
    )
    if pasted_text.strip() and uploaded_file is None and not sample_path:
        file_bytes = pasted_text.encode("utf-8")
        file_name = "pasted_text_input.txt"
        extracted_text = pasted_text.strip()

    # Only prioritize pasted text if no physical file was explicitly uploaded
    if pasted_text.strip() and uploaded_file is None and not sample_path:
        file_bytes = pasted_text.encode("utf-8")
        file_name = "pasted_text_input.txt"
        extracted_text = pasted_text.strip()

# --- PROCESS DOCUMENT EXTRACTION ---
extracted_data = None
if file_bytes and file_name:
    # If it's a real file (not pasted text), run the extractor
    if file_name != "pasted_text_input.txt":
        extracted_data = extractor.extract_content(file_bytes, file_name)
        extracted_text = extracted_data.get("extracted_text", "")
        is_scanned_or_image = extracted_data.get("is_scanned_or_image", False)
        mime_type = extracted_data.get("mime_type", "text/plain")
        
        # Document preview UI elements
        col_info1, col_info2 = st.columns([3, 1])
        with col_info1:
            st.markdown(f"**Selected File:** `{file_name}` &nbsp;|&nbsp; {extracted_data['summary_info']}")
        
        if extracted_data.get("file_type") == "image":
            with st.expander("🖼️ View Uploaded Image", expanded=False):
                st.image(file_bytes, caption=file_name, use_container_width=True)
    else:
        # UI readout for pasted text
        st.markdown(f"**Selected Source:** `Pasted Raw Text Content` ({len(extracted_text)} characters)")

# Action button
st.markdown("---")
explain_clicked = st.button(
    "🔍 Explain This Document",
    type="primary",
    use_container_width=True
)

if explain_clicked:
    st.info("Button click detected!")
    if not file_bytes:
        st.warning("Please upload a file, select a sample document, or paste text first.")
    elif not api_key_input:
        st.error("Please enter your Gemini API Key in the left sidebar to analyze the document.")
    else:
        with st.spinner("Analyzing document and simplifying in plain English..."):
           st.write("⏳ Analyzing your document... Please wait.")
           try:
                res = explainer.explain_document(
                    file_bytes=file_bytes,
                    filename=file_name,
                    extracted_text=extracted_data.get("extracted_text", "") if extracted_data else "",
                    is_scanned_or_image=extracted_data.get("is_scanned_or_image", False) if extracted_data else False,
                    mime_type=extracted_data.get("mime_type", "text/plain") if extracted_data else "text/plain",
                    api_key=api_key_input.strip(),
                    model_name=model_choice,
                )
                st.session_state["explanation_result"] = res
                st.session_state["explained_doc_name"] = file_name
                st.success("Analysis complete!")
           except Exception as e:
                st.error(f"Failed to explain document: {str(e)}")

# ----------------- DISPLAY RESULT -----------------
if "explanation_result" in st.session_state:
    result = st.session_state["explanation_result"]
    current_doc = st.session_state.get("explained_doc_name", "Document")

    st.markdown("---")
    st.subheader(f"📑 Breakdown: {result.document_title}")
    st.caption(f"Simplified summary for: {current_doc}")

    # SECTION 1: WHAT IS THIS?
    st.markdown(
        f"""
        <div class="card-box">
            <div class="card-heading">💡 What is this?</div>
            <p style="font-size: 1.05rem; line-height: 1.6; margin: 0; color: #334155;">
                {result.what_is_this}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # SECTION 2: DEADLINE (Prominently styled to satisfy Requirements 4 & 5)
    if result.has_deadline:
        st.markdown(
            f"""
            <div class="deadline-urgent">
                <div style="font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: #DC2626; font-weight: 700; margin-bottom: 0.3rem;">
                    ⏰ Important Deadline
                </div>
                <div class="deadline-urgent-text">
                    {result.deadline}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="deadline-none">
                <div style="font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: #16A34A; font-weight: 700; margin-bottom: 0.3rem;">
                    🗓️ Deadline Status
                </div>
                <div class="deadline-none-text">
                    ✅ No deadline found in this document.
                </div>
                <div style="color: #166534; font-size: 0.9rem; margin-top: 0.2rem;">
                    This is an ongoing policy or informational notice without an expiry cutoff.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # TWO-COLUMN DISPLAY FOR ACTIONS & IMPORTANT POINTS
    col_actions, col_points = st.columns(2)

    with col_actions:
        st.markdown(
            """
            <div class="card-box" style="height: 100%;">
                <div class="card-heading">📋 What do I need to do?</div>
            """,
            unsafe_allow_html=True,
        )
        if result.what_do_i_need_to_do:
            for idx, action in enumerate(result.what_do_i_need_to_do, 1):
                st.markdown(
                    f"""
                    <div class="step-item">
                        <strong>Step {idx}:</strong> {action}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No action required from you — this document is for reference only.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_points:
        st.markdown(
            """
            <div class="card-box" style="height: 100%;">
                <div class="card-heading">📌 Important Points</div>
            """,
            unsafe_allow_html=True,
        )
        if result.important_points:
            for pt in result.important_points:
                st.markdown(f"- {pt}")
        else:
            st.write("No additional points noted.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("")
    
    # ACTION CHECKLIST
    st.markdown("---")
    st.subheader("✅ Action Checklist")
    st.caption("Tick each task when you complete it.")

    if result.what_do_i_need_to_do:
        for idx, action in enumerate(result.what_do_i_need_to_do):
            st.checkbox(
                action,
                key=f"checklist_{current_doc}_{idx}"
            )
    else:
        st.info("No specific actions found.")

    # SECTION 5: THINGS TO BE CAREFUL ABOUT
    st.markdown(
        """
        <div class="caution-box">
            <div class="card-heading" style="color: #92400E;">⚠️ Things to be careful about</div>
        """,
        unsafe_allow_html=True,
    )
    if result.things_to_be_careful_about:
        for warning in result.things_to_be_careful_about:
            st.markdown(f"- **Caution:** {warning}")
    else:
        st.markdown("- No critical traps or penalties identified in this document.")
    st.markdown("</div>", unsafe_allow_html=True)

    # Optional transcription if image/scanned was used
    if getattr(result, "extracted_text_snippet", None):
        with st.expander("🔍 Key Extracted Text from Document", expanded=False):
            st.write(result.extracted_text_snippet)
