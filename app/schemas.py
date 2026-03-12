from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
from datetime import datetime

# User schemas
class User(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Project schemas
class ProjectCreate(BaseModel):
    name: str

class Project(BaseModel):
    id: int
    user_id: int
    name: str
    questionnaire_filename: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Question schemas
class Question(BaseModel):
    id: int
    question_number: int
    question_text: str
    
    class Config:
        from_attributes = True

# Answer schemas
class AnswerUpdate(BaseModel):
    answer_text: str

class Citation(BaseModel):
    source: str
    snippet: str
    page: Optional[int] = None

class Answer(BaseModel):
    id: int
    question_id: int
    answer_text: str
    citations: List[Citation]
    confidence_score: Optional[float]
    is_edited: bool
    
    class Config:
        from_attributes = True

class QuestionWithAnswer(BaseModel):
    question: Question
    answer: Optional[Answer]
    
    class Config:
        from_attributes = True

# Document schemas
class Document(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    uploaded_at: datetime
    
    class Config:
        from_attributes = True
