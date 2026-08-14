from pydantic import BaseModel, Field


class NaturalLanguageDetail(BaseModel):
    purpose: str = ""
    how_it_works: str = ""
    input_desc: str = ""
    output_desc: str = ""
    important_behavior: str = ""
    technical_detail: str = ""

    def to_summary(self) -> str:
        """Legacy flat summary for backward compatibility."""
        parts = []
        if self.purpose:
            parts.append(self.purpose)
        if self.how_it_works:
            parts.append(self.how_it_works)
        return " ".join(parts)
