#!/usr/bin/env python3
"""
Simple test script to validate the Report Explainer feature.

This script demonstrates how to use the Report Explainer service
without requiring a full OpenAI API key for basic functionality.
"""

import asyncio
import tempfile
import os
from app.services.report_explainer_service import report_explainer_service

# Sample medical report content for testing
SAMPLE_REPORT_TEXT = """
VITACHECKLABS MEDICAL REPORT
Patient: John Doe
Date: 2024-01-15

BLOOD CHEMISTRY PANEL:
Glucose (Fasting): 95 mg/dL
Total Cholesterol: 250 mg/dL
HDL Cholesterol: 35 mg/dL
LDL Cholesterol: 160 mg/dL
Triglycerides: 180 mg/dL

COMPLETE BLOOD COUNT:
Hemoglobin: 14.2 g/dL
Hematocrit: 42.0 %
WBC: 7.5 ×10³/μL
RBC: 4.8 ×10⁶/μL
Platelets: 320 ×10³/μL

LIVER FUNCTION:
ALT: 45 U/L
AST: 35 U/L
Bilirubin: 0.8 mg/dL

THYROID FUNCTION:
TSH: 2.1 μIU/mL
T4: 16.0 pmol/L

All tests performed at VitaCheckLabs certified facility.
Results reviewed by Dr. Smith, MD.
"""

def create_sample_pdf(content: str) -> str:
    """Create a sample PDF file with the given content."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import io

        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')

        # Create PDF with reportlab
        c = canvas.Canvas(temp_file.name, pagesize=letter)

        # Add content line by line
        y_position = 750
        for line in content.split('\n'):
            if line.strip():
                c.drawString(50, y_position, line.strip())
                y_position -= 20
                if y_position < 50:  # Start new page if needed
                    c.showPage()
                    y_position = 750

        c.save()
        return temp_file.name

    except ImportError:
        # Fallback: create a simple text file if reportlab not available
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w')
        temp_file.write(content)
        temp_file.close()
        return temp_file.name

async def test_text_extraction():
    """Test PDF text extraction functionality."""
    print("🔍 Testing text extraction...")

    # Create sample file
    pdf_path = create_sample_pdf(SAMPLE_REPORT_TEXT)

    try:
        # Test text extraction
        extracted_text = report_explainer_service.extract_text_from_pdf(pdf_path)

        print(f"✅ Text extraction successful!")
        print(f"📄 Extracted {len(extracted_text)} characters")
        print(f"📝 Preview: {extracted_text[:200]}...")

        return extracted_text

    except Exception as e:
        print(f"❌ Text extraction failed: {e}")
        return None

    finally:
        # Clean up
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)

async def test_medical_parsing():
    """Test medical value parsing functionality."""
    print("\n🧬 Testing medical value parsing...")

    try:
        # Test parsing
        parsed_values = report_explainer_service.parse_medical_values(SAMPLE_REPORT_TEXT)

        print(f"✅ Medical parsing successful!")
        print(f"🔬 Found {len(parsed_values)} medical values:")

        for test_name, test_data in parsed_values.items():
            print(f"  • {test_name}: {test_data['value']} {test_data['unit']}")

        return parsed_values

    except Exception as e:
        print(f"❌ Medical parsing failed: {e}")
        return None

async def test_abnormal_detection():
    """Test abnormal value detection functionality."""
    print("\n⚠️ Testing abnormal value detection...")

    try:
        # First parse the values
        parsed_values = report_explainer_service.parse_medical_values(SAMPLE_REPORT_TEXT)

        if not parsed_values:
            print("❌ No parsed values to analyze")
            return None

        # Detect abnormalities
        abnormal_findings = report_explainer_service.detect_abnormal_values(parsed_values)

        print(f"✅ Abnormal detection successful!")

        normal_count = sum(1 for finding in abnormal_findings.values() if finding['status'] == 'normal')
        abnormal_count = len(abnormal_findings) - normal_count

        print(f"📊 Analysis results:")
        print(f"  • Normal values: {normal_count}")
        print(f"  • Abnormal values: {abnormal_count}")

        # Show abnormal findings
        if abnormal_count > 0:
            print(f"🚨 Abnormal findings:")
            for test_name, finding in abnormal_findings.items():
                if finding['status'] != 'normal':
                    status = finding['status']
                    severity = finding['severity']
                    value = finding['value']
                    unit = finding['unit']
                    ref_min = finding['reference_min']
                    ref_max = finding['reference_max']
                    print(f"  • {test_name}: {value} {unit} ({status}, {severity}) - Normal: {ref_min}-{ref_max} {unit}")

        return abnormal_findings

    except Exception as e:
        print(f"❌ Abnormal detection failed: {e}")
        return None

async def test_basic_summary():
    """Test basic summary generation (without AI)."""
    print("\n📝 Testing basic summary generation...")

    try:
        # Parse values and detect abnormalities
        parsed_values = report_explainer_service.parse_medical_values(SAMPLE_REPORT_TEXT)
        abnormal_findings = report_explainer_service.detect_abnormal_values(parsed_values)

        # Generate basic summary (fallback method)
        summaries = report_explainer_service._generate_basic_summary(parsed_values, abnormal_findings)

        print(f"✅ Basic summary generation successful!")
        print(f"\n👥 Patient Summary:")
        print(f"   {summaries['patient_summary']}")
        print(f"\n🏥 Clinician Summary:")
        print(f"   {summaries['clinician_summary']}")

        return summaries

    except Exception as e:
        print(f"❌ Summary generation failed: {e}")
        return None

async def test_full_processing():
    """Test the complete processing pipeline."""
    print("\n🔄 Testing complete processing pipeline...")

    # Create sample PDF
    pdf_path = create_sample_pdf(SAMPLE_REPORT_TEXT)

    try:
        # Process the report
        result = await report_explainer_service.process_report(pdf_path)

        print(f"✅ Complete processing successful!")
        print(f"\n📊 Processing Results:")
        print(f"  • Tests parsed: {result['analysis_metadata']['total_tests']}")
        print(f"  • Abnormal values: {result['analysis_metadata']['abnormal_count']}")
        print(f"  • AI enabled: {result['analysis_metadata']['ai_enabled']}")
        print(f"  • Processed at: {result['analysis_metadata']['processed_at']}")

        return result

    except Exception as e:
        print(f"❌ Complete processing failed: {e}")
        return None

    finally:
        # Clean up
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)

async def main():
    """Run all tests."""
    print("🚀 Starting Report Explainer Feature Tests")
    print("=" * 50)

    # Run individual tests
    await test_text_extraction()
    await test_medical_parsing()
    await test_abnormal_detection()
    await test_basic_summary()
    await test_full_processing()

    print("\n" + "=" * 50)
    print("✨ Report Explainer Feature Test Complete!")
    print("\n📋 Next Steps:")
    print("  1. Install dependencies: pip install -r requirements.txt")
    print("  2. Run database migration: alembic upgrade head")
    print("  3. Set OPENAI_API_KEY in .env for AI summaries")
    print("  4. Start the API server: uvicorn main:app --reload")
    print("  5. Test API endpoints at http://localhost:8000/docs")

if __name__ == "__main__":
    asyncio.run(main())