import os
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import pandas as pd
import numpy as np
import PyPDF2
import pdfplumber
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import settings

class ReportExplainerService:
    """
    Service for parsing medical reports and generating AI-powered explanations.

    Features:
    - PDF text extraction
    - Medical data parsing
    - Abnormal value detection
    - Dual summary generation (patient-friendly + clinician-style)
    """

    def __init__(self):
        self.openai_client = None
        self.langchain_llm = None
        self._initialize_ai_clients()

        # Common medical test reference ranges
        self.reference_ranges = {
            # Blood Chemistry
            "glucose": {"min": 70, "max": 100, "unit": "mg/dL", "fasting": True},
            "cholesterol": {"min": 0, "max": 200, "unit": "mg/dL"},
            "hdl": {"min": 40, "max": 999, "unit": "mg/dL"},
            "ldl": {"min": 0, "max": 100, "unit": "mg/dL"},
            "triglycerides": {"min": 0, "max": 150, "unit": "mg/dL"},

            # Complete Blood Count
            "hemoglobin": {"min": 12.0, "max": 15.5, "unit": "g/dL"},
            "hematocrit": {"min": 36.0, "max": 46.0, "unit": "%"},
            "wbc": {"min": 4.5, "max": 11.0, "unit": "×10³/μL"},
            "rbc": {"min": 4.7, "max": 6.1, "unit": "×10⁶/μL"},
            "platelets": {"min": 150, "max": 450, "unit": "×10³/μL"},

            # Liver Function
            "alt": {"min": 7, "max": 56, "unit": "U/L"},
            "ast": {"min": 10, "max": 40, "unit": "U/L"},
            "bilirubin": {"min": 0.1, "max": 1.2, "unit": "mg/dL"},

            # Kidney Function
            "creatinine": {"min": 0.7, "max": 1.3, "unit": "mg/dL"},
            "bun": {"min": 7, "max": 20, "unit": "mg/dL"},

            # Thyroid Function
            "tsh": {"min": 0.27, "max": 4.2, "unit": "μIU/mL"},
            "t3": {"min": 2.3, "max": 4.2, "unit": "pg/mL"},
            "t4": {"min": 12.0, "max": 22.0, "unit": "pmol/L"},

            # Diabetes Markers
            "hba1c": {"min": 4.0, "max": 5.6, "unit": "%"},

            # Cardiac Markers
            "troponin": {"min": 0, "max": 0.04, "unit": "ng/mL"},
            "ck_mb": {"min": 0, "max": 6.3, "unit": "ng/mL"}
        }

    def _initialize_ai_clients(self):
        """Initialize OpenAI and LangChain clients."""
        openai_api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.getenv('OPENAI_API_KEY')

        if openai_api_key:
            self.openai_client = OpenAI(api_key=openai_api_key)
            self.langchain_llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                api_key=openai_api_key
            )

    def extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text from PDF using multiple methods for robustness.

        Args:
            file_path: Path to the PDF file

        Returns:
            Extracted text content
        """
        text = ""

        try:
            # Method 1: pdfplumber (better for structured data)
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"pdfplumber failed: {e}")

            try:
                # Method 2: PyPDF2 (fallback)
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except Exception as e2:
                print(f"PyPDF2 also failed: {e2}")
                raise Exception(f"Failed to extract text from PDF: {e2}")

        return text.strip()

    def parse_medical_values(self, text: str) -> Dict[str, Any]:
        """
        Parse medical test values from extracted text using regex patterns.

        Args:
            text: Extracted text from PDF

        Returns:
            Dictionary of parsed medical values
        """
        parsed_values = {}

        # Common patterns for medical values
        patterns = {
            # Blood glucose patterns
            "glucose": [
                r"glucose[:\s]*(\d+\.?\d*)\s*(mg/dl|mmol/l)?",
                r"blood\s*glucose[:\s]*(\d+\.?\d*)",
                r"fasting\s*glucose[:\s]*(\d+\.?\d*)"
            ],

            # Cholesterol patterns
            "cholesterol": [
                r"total\s*cholesterol[:\s]*(\d+\.?\d*)",
                r"cholesterol[:\s]*(\d+\.?\d*)\s*(mg/dl)?"
            ],

            "hdl": [
                r"hdl[:\s]*(\d+\.?\d*)",
                r"hdl\s*cholesterol[:\s]*(\d+\.?\d*)"
            ],

            "ldl": [
                r"ldl[:\s]*(\d+\.?\d*)",
                r"ldl\s*cholesterol[:\s]*(\d+\.?\d*)"
            ],

            # Blood count patterns
            "hemoglobin": [
                r"hemoglobin[:\s]*(\d+\.?\d*)",
                r"hb[:\s]*(\d+\.?\d*)\s*(g/dl)?"
            ],

            "wbc": [
                r"wbc[:\s]*(\d+\.?\d*)",
                r"white\s*blood\s*cell[:\s]*(\d+\.?\d*)"
            ],

            # Liver function patterns
            "alt": [
                r"alt[:\s]*(\d+\.?\d*)",
                r"alanine\s*aminotransferase[:\s]*(\d+\.?\d*)"
            ],

            "ast": [
                r"ast[:\s]*(\d+\.?\d*)",
                r"aspartate\s*aminotransferase[:\s]*(\d+\.?\d*)"
            ],

            # Kidney function patterns
            "creatinine": [
                r"creatinine[:\s]*(\d+\.?\d*)",
                r"serum\s*creatinine[:\s]*(\d+\.?\d*)"
            ],

            # Thyroid patterns
            "tsh": [
                r"tsh[:\s]*(\d+\.?\d*)",
                r"thyroid\s*stimulating\s*hormone[:\s]*(\d+\.?\d*)"
            ],

            # HbA1c patterns
            "hba1c": [
                r"hba1c[:\s]*(\d+\.?\d*)",
                r"hemoglobin\s*a1c[:\s]*(\d+\.?\d*)"
            ]
        }

        text_lower = text.lower()

        for test_name, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    try:
                        # Extract the numeric value
                        value = float(matches[0][0] if isinstance(matches[0], tuple) else matches[0])
                        parsed_values[test_name] = {
                            "value": value,
                            "unit": self.reference_ranges.get(test_name, {}).get("unit", ""),
                            "reference_range": self.reference_ranges.get(test_name, {})
                        }
                        break  # Stop after first match for this test
                    except (ValueError, IndexError):
                        continue

        return parsed_values

    def detect_abnormal_values(self, parsed_values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect abnormal values by comparing against reference ranges.

        Args:
            parsed_values: Dictionary of parsed medical values

        Returns:
            Dictionary with abnormality flags and severity levels
        """
        abnormal_findings = {}

        for test_name, test_data in parsed_values.items():
            value = test_data["value"]
            ref_range = test_data.get("reference_range", {})

            if not ref_range:
                continue

            min_val = ref_range.get("min", 0)
            max_val = ref_range.get("max", float('inf'))

            status = "normal"
            severity = "none"

            if value < min_val:
                status = "low"
                # Calculate severity based on how far below normal
                deviation = (min_val - value) / min_val
                if deviation > 0.5:
                    severity = "severe"
                elif deviation > 0.2:
                    severity = "moderate"
                else:
                    severity = "mild"

            elif value > max_val:
                status = "high"
                # Calculate severity based on how far above normal
                deviation = (value - max_val) / max_val
                if deviation > 0.5:
                    severity = "severe"
                elif deviation > 0.2:
                    severity = "moderate"
                else:
                    severity = "mild"

            abnormal_findings[test_name] = {
                "value": value,
                "status": status,
                "severity": severity,
                "reference_min": min_val,
                "reference_max": max_val,
                "unit": test_data.get("unit", "")
            }

        return abnormal_findings

    async def generate_ai_summary(self,
                                 parsed_values: Dict[str, Any],
                                 abnormal_findings: Dict[str, Any],
                                 original_text: str) -> Dict[str, str]:
        """
        Generate dual summaries using AI: patient-friendly and clinician-style.

        Args:
            parsed_values: Parsed medical values
            abnormal_findings: Detected abnormal values
            original_text: Original extracted text from PDF

        Returns:
            Dictionary containing both summary types
        """
        if not self.langchain_llm:
            return self._generate_basic_summary(parsed_values, abnormal_findings)

        try:
            # Prepare data for AI analysis
            abnormal_count = sum(1 for finding in abnormal_findings.values()
                               if finding["status"] != "normal")

            severe_abnormalities = [
                name for name, finding in abnormal_findings.items()
                if finding["severity"] == "severe"
            ]

            # Generate patient-friendly summary
            patient_summary = await self._generate_patient_summary(
                parsed_values, abnormal_findings, abnormal_count, severe_abnormalities
            )

            # Generate clinician summary
            clinician_summary = await self._generate_clinician_summary(
                parsed_values, abnormal_findings, original_text
            )

            return {
                "patient_summary": patient_summary,
                "clinician_summary": clinician_summary
            }

        except Exception as e:
            print(f"AI summary generation failed: {e}")
            return self._generate_basic_summary(parsed_values, abnormal_findings)

    async def _generate_patient_summary(self,
                                       parsed_values: Dict[str, Any],
                                       abnormal_findings: Dict[str, Any],
                                       abnormal_count: int,
                                       severe_abnormalities: List[str]) -> str:
        """Generate patient-friendly summary using AI."""

        system_prompt = """You are a medical communication specialist. Create a patient-friendly summary of lab results that:
1. Uses simple, non-technical language
2. Explains what each test measures in layman's terms
3. Clearly indicates if values are normal, slightly abnormal, or concerning
4. Provides reassurance where appropriate
5. Suggests when to follow up with a doctor
6. Avoids causing unnecessary anxiety while being truthful
7. Is warm, empathetic, and encouraging"""

        user_prompt = f"""
Please create a patient-friendly summary of these lab results:

PARSED VALUES:
{json.dumps(parsed_values, indent=2)}

ABNORMAL FINDINGS:
{json.dumps(abnormal_findings, indent=2)}

SUMMARY STATS:
- Total tests: {len(parsed_values)}
- Abnormal values: {abnormal_count}
- Severe abnormalities: {severe_abnormalities}

Guidelines:
- Start with an overall assessment
- Explain each abnormal finding in simple terms
- Mention what normal values look like
- End with actionable next steps
- Keep tone reassuring but honest
- Maximum 300 words
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = await self.langchain_llm.ainvoke(messages)
        return response.content

    async def _generate_clinician_summary(self,
                                         parsed_values: Dict[str, Any],
                                         abnormal_findings: Dict[str, Any],
                                         original_text: str) -> str:
        """Generate clinician-style summary using AI."""

        system_prompt = """You are a clinical pathologist. Create a professional medical summary that:
1. Uses proper medical terminology
2. Highlights clinically significant findings
3. Suggests differential diagnoses where appropriate
4. Recommends follow-up tests if needed
5. Notes any critical values requiring immediate attention
6. Follows standard medical reporting format
7. Is concise but comprehensive"""

        user_prompt = f"""
Please create a clinical summary of these lab results:

PARSED VALUES:
{json.dumps(parsed_values, indent=2)}

ABNORMAL FINDINGS:
{json.dumps(abnormal_findings, indent=2)}

ORIGINAL REPORT EXCERPT:
{original_text[:1000]}...

Please provide:
1. Clinical impression
2. Significant abnormalities with clinical context
3. Recommended follow-up or additional testing
4. Critical values flagged for immediate attention
5. Maximum 250 words
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = await self.langchain_llm.ainvoke(messages)
        return response.content

    def _generate_basic_summary(self,
                               parsed_values: Dict[str, Any],
                               abnormal_findings: Dict[str, Any]) -> Dict[str, str]:
        """Generate basic summaries when AI is not available."""

        abnormal_count = sum(1 for finding in abnormal_findings.values()
                           if finding["status"] != "normal")

        # Patient summary
        if abnormal_count == 0:
            patient_summary = f"""
Your lab results look good! All {len(parsed_values)} tests came back within normal ranges.
This suggests your overall health is on track. Continue maintaining your current healthy lifestyle
and follow up with your doctor as scheduled for routine care.
"""
        else:
            patient_summary = f"""
Your lab results show {abnormal_count} out of {len(parsed_values)} values outside the normal range.
Don't be alarmed - many factors can affect lab values. Please discuss these results with your doctor
who can explain what they mean for your specific situation and recommend any necessary next steps.
"""

        # Clinician summary
        abnormal_list = [name for name, finding in abnormal_findings.items()
                        if finding["status"] != "normal"]

        clinician_summary = f"""
CLINICAL SUMMARY:
- Total parameters analyzed: {len(parsed_values)}
- Abnormal values: {abnormal_count}
- Abnormal parameters: {', '.join(abnormal_list) if abnormal_list else 'None'}

Recommend clinical correlation and follow-up as appropriate.
"""

        return {
            "patient_summary": patient_summary.strip(),
            "clinician_summary": clinician_summary.strip()
        }

    async def process_report(self, file_path: str) -> Dict[str, Any]:
        """
        Main method to process a medical report PDF and generate explanations.

        Args:
            file_path: Path to the PDF file

        Returns:
            Complete analysis including parsed values, abnormalities, and summaries
        """
        try:
            # Step 1: Extract text from PDF
            extracted_text = self.extract_text_from_pdf(file_path)

            if not extracted_text:
                raise ValueError("No text could be extracted from the PDF")

            # Step 2: Parse medical values
            parsed_values = self.parse_medical_values(extracted_text)

            # Step 3: Detect abnormal values
            abnormal_findings = self.detect_abnormal_values(parsed_values)

            # Step 4: Generate AI summaries
            summaries = await self.generate_ai_summary(
                parsed_values, abnormal_findings, extracted_text
            )

            # Step 5: Compile results
            result = {
                "extracted_text": extracted_text,
                "parsed_values": parsed_values,
                "abnormal_findings": abnormal_findings,
                "summaries": summaries,
                "analysis_metadata": {
                    "total_tests": len(parsed_values),
                    "abnormal_count": sum(1 for finding in abnormal_findings.values()
                                        if finding["status"] != "normal"),
                    "processed_at": datetime.utcnow().isoformat(),
                    "ai_enabled": self.langchain_llm is not None
                }
            }

            return result

        except Exception as e:
            raise Exception(f"Report processing failed: {str(e)}")

# Create singleton instance
report_explainer_service = ReportExplainerService()