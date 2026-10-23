from pydantic import BaseModel, Field, field_validator


class AnalyticsQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A non-empty question is required.")
        return value.strip()
