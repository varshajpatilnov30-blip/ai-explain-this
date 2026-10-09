"""
Unit and integration tests for "Explain This" components.
"""

import unittest
from pathlib import Path
import extractor
import explainer


class TestExplainThis(unittest.TestCase):
    def test_text_extraction(self):
        sample_path = Path("sample_docs/college_exam_fee_circular.txt")
        self.assertTrue(sample_path.exists())
        data = extractor.extract_content(sample_path.read_bytes(), sample_path.name)
        self.assertTrue(data["success"])
        self.assertEqual(data["file_type"], "text")
        self.assertIn("ATU/COE", data["extracted_text"])

    def test_pdf_extraction(self):
        sample_path = Path("sample_docs/sample_hostel_bill.pdf")
        self.assertTrue(sample_path.exists())
        data = extractor.extract_content(sample_path.read_bytes(), sample_path.name)
        self.assertTrue(data["success"])
        self.assertEqual(data["file_type"], "pdf")
        self.assertIn("HOSTEL ELECTRICITY BILL", data["extracted_text"])

    def test_image_extraction_metadata(self):
        sample_path = Path("sample_docs/sample_broadband_bill.png")
        self.assertTrue(sample_path.exists())
        data = extractor.extract_content(sample_path.read_bytes(), sample_path.name)
        self.assertTrue(data["success"])
        self.assertEqual(data["file_type"], "image")
        self.assertTrue(data["is_scanned_or_image"])

    def test_explanation_schema_with_deadline(self):
        sample_json = '''{
            "document_title": "End-Semester Exam Notice",
            "what_is_this": "This is a notice about registration fees for your college semester exams.",
            "what_do_i_need_to_do": ["Pay Rs. 250 per paper on ERP", "Submit receipt to HoD"],
            "has_deadline": true,
            "deadline": "October 24, 2026 without fine; October 28, 2026 with fine",
            "important_points": ["Minimum 75% attendance mandatory"],
            "things_to_be_careful_about": ["Ensure payment is verified within 24 hours"]
        }'''
        res = explainer.ExplanationResult.model_validate_json(sample_json)
        self.assertTrue(res.has_deadline)
        self.assertIn("October 24", res.deadline)
        self.assertEqual(len(res.what_do_i_need_to_do), 2)

    def test_explanation_schema_without_deadline(self):
        sample_json = '''{
            "document_title": "Scholarship Guidelines",
            "what_is_this": "Information regarding scholarship direct benefit transfer rules.",
            "what_do_i_need_to_do": ["Ensure bank account is NPCI mapped to Aadhaar"],
            "has_deadline": false,
            "deadline": "No deadline mentioned in this document",
            "important_points": ["Minimum 6.5 CGPA required"],
            "things_to_be_careful_about": ["Do not submit joint bank accounts"]
        }'''
        res = explainer.ExplanationResult.model_validate_json(sample_json)
        self.assertFalse(res.has_deadline)
        self.assertEqual(res.deadline, "No deadline mentioned in this document")

    def test_missing_api_key(self):
        with self.assertRaises(ValueError):
            explainer.explain_document(
                file_bytes=b"test",
                filename="test.txt",
                extracted_text="test",
                api_key="",
            )

    # ------------------------------------------------------------------
    # Deadline scanner unit tests
    # ------------------------------------------------------------------

    def test_sap_hackfest_deadline_detected(self):
        """Regression test: SAP Hackfest notice must yield '10 October 2026'."""
        sample_path = Path("sample_docs/sap_hackfest_notice.txt")
        self.assertTrue(sample_path.exists(), "SAP sample file must exist")

        text = sample_path.read_text(encoding="utf-8")
        hints = explainer._scan_deadline_hints(text)

        self.assertTrue(len(hints) > 0, "Deadline scanner returned no hints for SAP notice")
        # The exact phrase that appears in the document
        self.assertIn(
            "10 October 2026", hints,
            f"Expected '10 October 2026' in hints, got: {hints}"
        )

    def test_deadline_scanner_various_formats(self):
        """Scanner must detect deadlines written in common date formats."""
        cases = [
            ("submit by 20/10/2026",               "20/10/2026"),
            ("on or before October 20, 2026",       "October 20, 2026"),
            ("last date: 15-11-2026",               "15-11-2026"),
            ("due date is 5th December 2026",       "5th December 2026"),
            ("register by Nov 1, 2026",             "Nov 1, 2026"),
            ("The cutoff date is 2026-10-15",       "2026-10-15"),
        ]
        for text, expected_date in cases:
            with self.subTest(text=text):
                hints = explainer._scan_deadline_hints(text)
                self.assertIn(
                    expected_date, hints,
                    f"Scanner missed '{expected_date}' in: {text!r}  (got {hints})"
                )

    def test_deadline_scanner_no_false_positive(self):
        """Scanner must return [] for a document with no date-based deadline."""
        sample_path = Path("sample_docs/scholarship_policy_no_deadline.txt")
        self.assertTrue(sample_path.exists())
        text = sample_path.read_text(encoding="utf-8")
        hints = explainer._scan_deadline_hints(text)
        self.assertEqual(hints, [], f"False positive deadlines detected: {hints}")

    def test_deadline_schema_hint_forces_has_deadline_true(self):
        """Validate that hint-carrying JSON round-trips correctly in schema."""
        sample_json = '''{
            "document_title": "SAP Hackfest 2026 Notice",
            "what_is_this": "A hackathon notice from Apex Technical University.",
            "what_do_i_need_to_do": ["Register on industry.apexuniv.ac.in by 10 October 2026"],
            "has_deadline": true,
            "deadline": "Registration deadline: 10 October 2026",
            "important_points": ["Min CGPA 7.0 required", "Teams of 3-5 members"],
            "things_to_be_careful_about": ["Students with >2 backlogs are ineligible"]
        }'''
        res = explainer.ExplanationResult.model_validate_json(sample_json)
        self.assertTrue(res.has_deadline)
        self.assertIn("10 October 2026", res.deadline)


if __name__ == "__main__":
    unittest.main()
