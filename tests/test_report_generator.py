"""
Tests for ReportGenerator.
"""


from app.reporting.generator import (
    ReportGenerator,
)



def test_generate_report():

    generator = ReportGenerator()


    report = generator.generate(
        {
            "title":
                "OSINT Case",

            "summary":
                "Test summary",

            "findings":
                [
                    {
                        "type":
                            "entity",

                        "value":
                            "John",
                    }
                ],

            "evidence":
                [
                    {
                        "source":
                            "telegram",
                    }
                ],

            "ai_insights":
                [
                    {
                        "risk":
                            "low",
                    }
                ],

            "metadata":
                {
                    "case":
                        "001"
                },
        }
    )


    assert (
        report.title
        ==
        "OSINT Case"
    )


    assert len(
        report.findings
    ) == 1


    assert len(
        report.evidence
    ) == 1


    assert len(
        report.ai_insights
    ) == 1



def test_generator_metadata():

    generator = ReportGenerator()


    metadata = (
        generator.metadata()
    )


    assert (
        metadata["type"]
        ==
        "report_generator"
    )


    assert (
        metadata["version"]
        ==
        "1.0"
    )