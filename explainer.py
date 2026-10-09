"""
AI Explainer module for "Explain This".
Communicates with Google Gemini via the google-genai SDK.
Translates confusing circulars, notices, and bills into simple student-friendly breakdowns.

Reliability features:
  - Automatic retry with exponential backoff on 503 (overloaded) and 429 (rate limit).
  - Automatic model fallback: if the chosen model stays overloaded, the call is
    transparently retried on a lighter model before giving up.
"""

import json
import re
import time
from typing import Optional, List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.genai.errors import APIError, ServerError, ClientError


class ExplanationResult(BaseModel):
    document_title: str = Field(
        description="A concise student-friendly title of what this document is (e.g. 'College Exam Fee Circular', 'Broadband Bill', 'Scholarship Notice')."
    )
    what_is_this: str = Field(
        description="Plain, simple, jargon-free explanation of what this document is about and why it was issued. Write in friendly student language."
    )
    what_do_i_need_to_do: List[str] = Field(
        description="Actionable step-by-step instructions for what the user needs to do. If no action is needed, write 'No action required — this is for your information only'."
    )
    has_deadline: bool = Field(
        description=(
            "Set to TRUE only if the document explicitly states or clearly implies "
            "a deadline, due date, submission date, registration cutoff, or final date "
            "for completing an action. Look for dates associated with phrases such as "
            "'deadline', 'due date', 'last date', 'submit by', 'register by', "
            "'on or before', 'no later than', or 'applications close'. "
            "A date alone, a past event date, or a date unrelated to an action "
            "must NOT count as a deadline. Set to FALSE if no actual deadline is identified."
        )
    )

    deadline: str = Field(
        description=(
            "State the deadline clearly, including the exact date and any relevant context "
            "(e.g. 'Registration deadline: 10 October 2026'). "
            "If multiple deadlines exist, list all of them. "
            "Write exactly 'No deadline mentioned in this document' ONLY if no date-based deadline exists."
        )
    )
    important_points: List[str] = Field(
        description="Bullet points of key facts, fees, amounts, eligibility, or rules."
    )
    things_to_be_careful_about: List[str] = Field(
        description="List of warnings, penalties, late fines, attendance rules, or gotchas to avoid."
    )
    extracted_text_snippet: Optional[str] = Field(
        default="",
        description="If the input was an image or scanned document, provide a clean transcription of key readable text from the document."
    )


SYSTEM_INSTRUCTION = """You are "Explain This", an AI assistant designed to translate confusing, bureaucratic, academic, and legal documents into crystal clear, friendly, and practical English for students and regular people.

The user has uploaded a confusing document (such as a college circular, government notice, utility bill, job description, scholarship notice, insurance paper, or terms & conditions).

Your job is to analyze it carefully and break it down into simple, student-friendly terms.

Strict Guidelines:
1. "What is this?": Explain in 2-3 simple sentences without bureaucratic jargon or legalese.
2. "What do I need to do?": Give concrete, step-by-step actions the user needs to take right now. If no action is needed, clearly say so.
3. "Deadline" — READ THIS CAREFULLY:
   - You MUST scan every sentence for deadline-related phrases.
   - Deadline phrases include (but are not limited to):
       "deadline is", "deadline:", "submit by", "register by", "complete by",
       "on or before", "not later than", "no later than", "last date", "due date",
       "cutoff", "before [date]", "by [date]", "must be submitted by", "before the closing date".
   - If ANY such phrase appears next to a specific date, set has_deadline=true and report that date in the deadline field.
   - Examples that MUST be detected as deadlines:
       * "The SAP registration deadline is 10 October 2026" → has_deadline=true, deadline="10 October 2026"
       * "complete their registration by 10 October 2026" → has_deadline=true, deadline="10 October 2026"
       * "submit by 20/10/2026" → has_deadline=true, deadline="20 October 2026"
       * "on or before October 20, 2026" → has_deadline=true, deadline="20 October 2026"
   - ONLY set has_deadline=false and deadline="No deadline mentioned in this document" when the document contains ZERO date-based cutoffs.
4. "Important points": List key amounts, eligibility rules, locations, or requirements as bullet points.
5. "Things to be careful about": Highlight traps, penalties, late fees, minimum attendance, disqualification clauses, or common mistakes.
6. Keep the tone helpful, reassuring, and easy to read.
"""


def _parse_fallback_json(raw_text: str) -> ExplanationResult:
    """Fallback parser in case the raw output needs markdown stripping."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)
    return ExplanationResult(**data)


# ---------------------------------------------------------------------------
# Regex-based deadline pre-scanner
# ---------------------------------------------------------------------------
_MONTHS_RE = (
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December|"
    r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
)
_DATE_PATTERNS = [
    # "10 October 2026"  /  "10th October 2026"
    rf"\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTHS_RE}\s+\d{{4}}",
    # "October 20, 2026"  /  "Oct 20 2026"
    rf"{_MONTHS_RE}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}",
    # "20/10/2026"  or  "20-10-2026"
    r"\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}",
    # "2026-10-20" (ISO)
    r"\d{4}-\d{2}-\d{2}",
]
_DATE_RE = re.compile("|".join(_DATE_PATTERNS), re.IGNORECASE)

_DEADLINE_TRIGGERS = (
    r"(?:deadline|due date|last date|cutoff|cut-off|"
    r"on or before|submit by|register by|complete by|registration by|"
    r"apply by|payment by|must be submitted|must be completed|"
    r"not later than|no later than|before)"
)

# Primary pattern: trigger phrase + optional connector + date
_DEADLINE_PRIMARY_RE = re.compile(
    rf"(?:{_DEADLINE_TRIGGERS})\s*(?:is|:)?\s*({_DATE_RE.pattern})",
    re.IGNORECASE,
)
# Secondary pattern: date + "is the deadline / last date" (reversed order)
_DEADLINE_SECONDARY_RE = re.compile(
    rf"({_DATE_RE.pattern})\s+(?:is the|as the)?\s*(?:deadline|due date|last date|cutoff)",
    re.IGNORECASE,
)


def _scan_deadline_hints(text: str) -> List[str]:
    """
    Regex pre-scan of document text for deadline phrases.

    Returns a deduplicated list of date strings found near deadline trigger
    words, e.g. ['10 October 2026'].  Returns [] if nothing is found.

    This output is injected into the AI prompt as a hard hint so the model
    cannot miss an explicit deadline that plain text contains.
    """
    hits: List[str] = []

    # Pass 1: trigger phrase immediately before a date
    for m in _DEADLINE_PRIMARY_RE.finditer(text):
        for g in m.groups():
            if g:
                hits.append(g.strip())
                break

    # Pass 2: date immediately before a deadline noun
    for m in _DEADLINE_SECONDARY_RE.finditer(text):
        for g in m.groups():
            if g:
                hits.append(g.strip())
                break

    # Pass 3: fallback — trigger keyword with a date anywhere in the next 80 chars
    if not hits:
        for m in re.finditer(_DEADLINE_TRIGGERS, text, re.IGNORECASE):
            snippet = text[m.start(): m.start() + 80]
            date_m = _DATE_RE.search(snippet)
            if date_m:
                hits.append(date_m.group().strip())

    # Deduplicate while preserving order
    seen: set = set()
    unique: List[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            unique.append(h)
    return unique


# Models tried in order when the primary model is overloaded.
# The first entry is always overridden by whatever the user picks in the UI.
_FALLBACK_CHAIN = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

# Retry config: up to MAX_RETRIES attempts, doubling the wait each time.
_MAX_RETRIES = 4
_BASE_WAIT_SEC = 2.0   # 2 s → 4 s → 8 s → 16 s


def _is_retryable(err: APIError) -> bool:
    """Return True for errors that are worth retrying (overloaded / rate-limited)."""
    # 503 = model overloaded, 429 = quota / rate limit
    if err.code in (503, 429):
        return True
    # Some SDKs surface these via status strings
    status = (err.status or "").upper()
    return status in ("UNAVAILABLE", "RESOURCE_EXHAUSTED")




def _call_model(client: genai.Client, model: str, contents: list, config) -> ExplanationResult:
    """
    Call a single model with retry + exponential backoff.
    Raises the last APIError if all retries are exhausted.
    """
    last_err = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            if not response or not response.text:
                raise RuntimeError("Empty response from model. Please try again.")

            try:
                return ExplanationResult.model_validate_json(response.text)
            except Exception:
                return _parse_fallback_json(response.text)

        except (ServerError, ClientError) as e:
            last_err = e
            if not _is_retryable(e):
                raise  # non-retryable (e.g. 400 bad request, 401 auth) — fail fast
            wait = _BASE_WAIT_SEC * (2 ** (attempt - 1))
            time.sleep(wait)

        except APIError as e:
            last_err = e
            if not _is_retryable(e):
                raise
            wait = _BASE_WAIT_SEC * (2 ** (attempt - 1))
            time.sleep(wait)

    raise last_err  # all retries exhausted


def explain_document(
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
    extracted_text: Optional[str] = None,
    is_scanned_or_image: bool = False,
    mime_type: str = "text/plain",
    api_key: str = "",
    model_name: str = "gemini-3.8-flash",
) -> ExplanationResult:
    """
    Calls the Gemini API to analyze and explain the document.

    On 503/429 errors the call is automatically retried with exponential backoff.
    If the primary model stays overloaded after all retries, the call is
    transparently rerouted through _FALLBACK_CHAIN before raising to the caller.
    """
    if not api_key:
        raise ValueError("Please provide a valid Gemini API Key to explain documents.")

    client = genai.Client(api_key=api_key)

    # Build the prompt contents
    contents: list = []
    if is_scanned_or_image and file_bytes:
        contents.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))
        contents.append(
            "Please examine this uploaded document image/file. "
            "Transcribe key text if possible, and explain it clearly following the schema."
        )
    else:
        text_content = extracted_text or ""
        if not text_content.strip():
            raise ValueError("No text could be extracted from this document to explain.")

        # Pre-scan the text for deadline phrases — inject as a hard hint to the model
        deadline_hints = _scan_deadline_hints(text_content)
        if deadline_hints:
            hint_block = (
                "\n\n[SYSTEM HINT — DEADLINE DETECTED BY PRE-SCAN]\n"
                "The following deadline date(s) were found in the document text by a regex scanner. "
                "You MUST set has_deadline=true and include these dates in the deadline field:\n"
                + "\n".join(f"  • {d}" for d in deadline_hints)
                + "\n[END HINT]\n"
            )
        else:
            hint_block = ""

        contents.append(
            f"Here is the text extracted from the document ({filename or 'User Document'}):\n\n"
            f"--- BEGIN DOCUMENT ---\n{text_content}\n--- END DOCUMENT ---"
            f"{hint_block}\n\n"
            "Please analyze and explain this document according to the required sections."
        )


    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=ExplanationResult,
        temperature=0.2,
    )

    # Build the ordered list of models to try: chosen model first, then fallbacks.
    models_to_try = [model_name] + [m for m in _FALLBACK_CHAIN if m != model_name]

    last_error: Optional[Exception] = None
    for model in models_to_try:
        try:
            return _call_model(client, model, contents, config)
        except (ServerError, APIError) as e:
            if _is_retryable(e):
                last_error = e
                continue  # try the next model in the chain
            # Non-retryable (auth, bad request, etc.) — surface immediately
            raise RuntimeError(f"Gemini API Error ({model}): {e.message or str(e)}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error with model {model}: {str(e)}")

    # All models exhausted
    raise RuntimeError(
        "The Gemini API is currently overloaded. All models were tried. "
        "Please wait a moment and try again.\n\n"
        f"Details: {last_error}"
    )

