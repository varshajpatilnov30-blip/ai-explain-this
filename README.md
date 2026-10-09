# 📄 Explain This

A simple, student-friendly AI web application that translates confusing documents—such as college circulars, government notices, scholarship announcements, utility bills, terms & conditions, and bank/insurance policies—into plain, straightforward English.

---

## 🌟 Features

- **Multi-Format Upload:** Supports **PDF** (`.pdf`), **Image** (`.png`, `.jpg`, `.jpeg`, `.webp`), and **Text** (`.txt`) files, plus a direct text paste option.
- **Smart Text Extraction:** Extracts digital text directly from PDFs and text files; supports visual multimodal comprehension for scanned documents and images.
- **AI Document Breakdown:** Explains the document using Google Gemini into 5 crystal-clear sections:
  1. 💡 **What is this?** (Plain-English summary, free of bureaucratic jargon)
  2. 📋 **What do I need to do?** (Concrete action steps or reassurance that no action is required)
  3. ⏰ **Deadline** (Clear date & time, or an explicit badge when **no deadline is found**)
  4. 📌 **Important points** (Fees, criteria, conditions, and key facts)
  5. ⚠️ **Things to be careful about** (Penalties, late fees, attendance requirements, or traps)
- **Built-in Quick Test Samples:** Test the app with one click using preloaded sample documents (exam fee notices, scholarship policies without deadlines, bills, etc.).
- **Simple, Student-Friendly UI:** Clean, distraction-free interface built with Streamlit.

---

## 📁 Project Structure

```text
ai-explain-this/
│
├── app.py                  # Main Streamlit web application
├── extractor.py            # Text extraction & file handler (PDF, TXT, Images)
├── explainer.py            # AI explanation module using Google GenAI SDK
├── test_app.py             # Automated unit tests
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment variables template
├── sample_docs/            # Preloaded test circulars, bills, and notices
│   ├── college_exam_fee_circular.txt
│   ├── scholarship_policy_no_deadline.txt
│   ├── sample_hostel_bill.pdf
│   └── sample_broadband_bill.png
└── README.md               # Setup and usage guide
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.14 on Windows)
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/)

---

### 2. Install Dependencies

Open your terminal or PowerShell in the project directory (`c:\Users\USER\Documents\ai-explain-this`) and run:

**On Windows (PowerShell / Command Prompt):**
```powershell
py -m pip install -r requirements.txt
```
*(Or if using standard Python on PATH: `python -m pip install -r requirements.txt`)*

---

### 3. Configure API Key (Optional)

You can enter your API key directly in the web app's left sidebar, or save it to a `.env` file:

1. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Open `.env` and add your key:
   ```env
   GEMINI_API_KEY=AIzaSy...your_actual_key_here
   ```

---

### 4. Run the App

Start the Streamlit development server:

**On Windows:**
```powershell
py -m streamlit run app.py
```
*(Or `streamlit run app.py` if scripts are on your PATH)*

The application will automatically open in your default browser at:
👉 **`http://localhost:8501`**

---

### 5. Run Automated Tests

To verify that document parsing and schemas pass all checks:
```powershell
py -m unittest test_app.py
```

---

## 🎯 How to Use

1. Enter your **Gemini API Key** in the left sidebar (or let it auto-load from `.env`).
2. Upload a document (or choose one of the preloaded sample documents in the sidebar dropdown).
3. Click **🔍 Explain This Document**.
4. Review the 5 simplified sections with clear action items and deadline highlights!
