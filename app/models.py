from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    projects = relationship("Project", back_populates="user")
    documents = relationship("Document", back_populates="user")

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    questionnaire_filename = Column(String(255))
    status = Column(String(50), default="draft")  # draft, generated, reviewed, exported
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="projects")
    questions = relationship("Question", back_populates="project", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    original_row_data = Column(JSON)  # Store original Excel row for export
    
    project = relationship("Project", back_populates="questions")
    answer = relationship("Answer", back_populates="question", uselist=False)

class Answer(Base):
    __tablename__ = "answers"
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, unique=True)
    answer_text = Column(Text, nullable=False)
    citations = Column(JSON)  # List of {source: str, snippet: str, page: int}
    confidence_score = Column(Float)  # 0.0 to 1.0
    is_edited = Column(Integer, default=0)  # 0 = generated, 1 = user edited
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    question = relationship("Question", back_populates="answer")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50))  # txt, pdf
    file_size = Column(Integer)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding_json = Column(JSON)
    
    document = relationship("Document", back_populates="chunks")
