from pydantic import BaseModel
from typing import List, Optional

class PrereqResponse(BaseModel):
    course_id: str
    direct: List[str]
    transitive: List[str]

class EligibilityResponse(BaseModel):
    student_id: str
    course_id: str
    eligible: bool
    missing: List[str]
    completed: List[str]

class CycleResponse(BaseModel):
    cycles: List[List[str]]

class SequenceResponse(BaseModel):
    student_id: str
    target: List[str]
    sequence: List[str]
    remaining: List[str]

class GraduationPathsResponse(BaseModel):
    student_id: str
    targets: List[str]
    paths: List[List[str]]

class SkillsResponse(BaseModel):
    course_id: str
    skills: List[str]
