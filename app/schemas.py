"""Week 2 Meeting Notes API schemas. Field names match the evaluation contract."""
from pydantic import BaseModel, Field

class MeetingNotesRequest(BaseModel):
    meeting_text: str = Field(min_length=1)

class MeetingAction(BaseModel):
    owner: str | None = None
    action: str = Field(min_length=1)
    due_date: str | None = None

class AnalyzeMeetingResponse(BaseModel):
    summary: str = Field(min_length=1)
    decisions: list[str]
    actions: list[MeetingAction]
