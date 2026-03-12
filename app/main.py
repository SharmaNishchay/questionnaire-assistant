from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
import threading
from pathlib import Path

from app.database import engine, get_db, Base
from app import models, schemas, auth
from app.rag import rag_engine
from app.utils import parse_questionnaire, export_questionnaire, extract_text_from_file

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="EduSecure Questionnaire Assistant")

# Add session middleware for OAuth (required by authlib)
app.add_middleware(
    SessionMiddleware, 
    secret_key=auth.SECRET_KEY
)

# Setup static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Ensure upload directory exists
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.on_event("startup")
def startup_load_rag():
    """Reload stored documents into the RAG index in a background thread.
    Running it off the main thread lets the server start immediately even
    when the embedding model needs to be downloaded for the first time.
    """
    def _load():
        db = next(get_db())
        try:
            documents = db.query(models.Document).all()
            for doc in documents:
                if Path(doc.file_path).exists():
                    text = extract_text_from_file(doc.file_path)
                    if text:
                        rag_engine.add_document(text, doc.filename, doc.id)
            print(f"✓ RAG index loaded with {len(documents)} document(s)")
        except Exception as e:
            print(f"Warning: could not reload RAG index on startup: {e}")
        finally:
            db.close()

    threading.Thread(target=_load, daemon=True).start()

# Dependency to get current user from session
def get_current_user_session(request: Request, db: Session = Depends(get_db)):
    """Get user from session - raises exception if not authenticated"""
    user_email = request.session.get('user_email')
    if not user_email:
        return None
    
    user = db.query(models.User).filter(models.User.email == user_email).first()
    return user

def require_auth(request: Request, db: Session = Depends(get_db)):
    """Require authentication - redirect to login if not authenticated"""
    user = get_current_user_session(request, db)
    if not user:
        return None
    return user

@app.post("/auth/signup")
async def email_signup(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    db: Session = Depends(get_db)
):
    """Create a new account with email + password."""
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        return RedirectResponse(url="/login?error=email_exists", status_code=302)
    user = models.User(
        email=email,
        hashed_password=auth.hash_password(password),
        full_name=full_name or email.split("@")[0]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_email"] = user.email
    return RedirectResponse(url="/dashboard", status_code=302)

@app.post("/auth/login")
async def email_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Authenticate with email + password."""
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not user.hashed_password or not auth.verify_password(password, user.hashed_password):
        return RedirectResponse(url="/login?error=invalid_credentials", status_code=302)
    request.session["user_email"] = user.email
    return RedirectResponse(url="/dashboard", status_code=302)

# HTML Routes
@app.get("/", response_class=HTMLResponse)
def root_page(request: Request):
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    error = request.query_params.get("error", "")
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    # Redirect to unified login page
    return RedirectResponse(url="/login")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_session(request, db)
    if not current_user:
        return RedirectResponse(url="/login")
    
    # Get user's projects with question counts
    projects = db.query(models.Project).filter(models.Project.user_id == current_user.id).order_by(models.Project.created_at.desc()).all()
    for project in projects:
        project.question_count = db.query(models.Question).filter(models.Question.project_id == project.id).count()
    
    # Get user's documents
    documents = db.query(models.Document).filter(models.Document.user_id == current_user.id).order_by(models.Document.uploaded_at.desc()).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "projects": projects,
        "documents": documents,
        "project_count": len(projects),
        "document_count": len(documents)
    })

@app.post("/projects/create")
async def create_project(
    request: Request,
    project_name: str = Form(...),
    questionnaire_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_session(request, db)
    if not current_user:
        return RedirectResponse(url="/login")
    
    # Save uploaded questionnaire
    file_path = UPLOAD_DIR / f"{current_user.id}_{questionnaire_file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(questionnaire_file.file, buffer)
    
    # Create project
    project = models.Project(
        user_id=current_user.id,
        name=project_name,
        questionnaire_filename=questionnaire_file.filename,
        status="draft"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Parse questionnaire and extract questions
    parse_error = None
    try:
        questions_data = parse_questionnaire(str(file_path))
        for q_data in questions_data:
            question = models.Question(
                project_id=project.id,
                question_number=q_data['number'],
                question_text=q_data['text'],
                original_row_data=q_data.get('row_data', {})
            )
            db.add(question)
        db.commit()
        if not questions_data:
            parse_error = "No questions found. Check the file has a 'Question' header column with question text below it."
    except Exception as e:
        parse_error = str(e)
        print(f"Error parsing questionnaire: {e}")

    redirect_url = f"/projects/{project.id}"
    if parse_error:
        import urllib.parse
        redirect_url += "?parse_error=" + urllib.parse.quote(parse_error)
    return RedirectResponse(url=redirect_url, status_code=302)

@app.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail(request: Request, project_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user_session(request, db)
    if not current_user:
        return RedirectResponse(url="/login")
    
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    questions = db.query(models.Question).filter(models.Question.project_id == project_id).order_by(models.Question.question_number).all()
    
    # Load answers for each question
    for question in questions:
        question.answer = db.query(models.Answer).filter(models.Answer.question_id == question.id).first()
    
    answered_count = sum(1 for q in questions if q.answer and "not found" not in q.answer.answer_text.lower())
    not_found_count = sum(1 for q in questions if q.answer and "not found" in q.answer.answer_text.lower())
    parse_error = request.query_params.get("parse_error", "")

    return templates.TemplateResponse("project_detail.html", {
        "request": request,
        "project": project,
        "questions": questions,
        "answered_count": answered_count,
        "not_found_count": not_found_count,
        "parse_error": parse_error,
    })

@app.post("/projects/{project_id}/reupload")
async def reupload_questionnaire(
    request: Request,
    project_id: int,
    questionnaire_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Re-upload a questionnaire file for a project (replaces existing questions)."""
    current_user = get_current_user_session(request, db)
    if not current_user:
        return RedirectResponse(url="/login")

    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Save new file
    file_path = UPLOAD_DIR / f"{current_user.id}_{questionnaire_file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(questionnaire_file.file, buffer)

    # Remove old questions + answers
    old_questions = db.query(models.Question).filter(models.Question.project_id == project_id).all()
    for q in old_questions:
        db.query(models.Answer).filter(models.Answer.question_id == q.id).delete()
    db.query(models.Question).filter(models.Question.project_id == project_id).delete()
    db.commit()

    # Update project filename
    project.questionnaire_filename = questionnaire_file.filename
    project.status = "draft"

    # Re-parse
    parse_error = None
    try:
        questions_data = parse_questionnaire(str(file_path))
        for q_data in questions_data:
            question = models.Question(
                project_id=project.id,
                question_number=q_data['number'],
                question_text=q_data['text'],
                original_row_data=q_data.get('row_data', {})
            )
            db.add(question)
        db.commit()
        if not questions_data:
            parse_error = "No questions found. Check the file has a 'Question' header column."
    except Exception as e:
        parse_error = str(e)
        print(f"Error re-parsing questionnaire: {e}")

    db.commit()
    redirect_url = f"/projects/{project_id}"
    if parse_error:
        import urllib.parse
        redirect_url += "?parse_error=" + urllib.parse.quote(parse_error)
    return RedirectResponse(url=redirect_url, status_code=302)

@app.post("/projects/{project_id}/generate")
async def generate_answers(request: Request, project_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user_session(request, db)
    if not current_user:
        return RedirectResponse(url="/login")
    
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all questions
    questions = db.query(models.Question).filter(models.Question.project_id == project_id).all()
    
    # Generate answers for each question
    for question in questions:
        try:
            result = rag_engine.query(question.question_text)
            
            # Create or update answer
            answer = db.query(models.Answer).filter(models.Answer.question_id == question.id).first()
            if answer:
                answer.answer_text = result['answer']
                answer.citations = result['citations']
                answer.confidence_score = result.get('confidence', 0.0)
                answer.is_edited = 0
            else:
                answer = models.Answer(
                    question_id=question.id,
                    answer_text=result['answer'],
                    citations=result['citations'],
                    confidence_score=result.get('confidence', 0.0)
                )
                db.add(answer)
        except Exception as e:
            print(f"Error generating answer for question {question.id}: {e}")
            # Create "not found" answer
            answer = models.Answer(
                question_id=question.id,
                answer_text="Not found in references.",
                citations=[]
            )
            db.add(answer)
    
    db.commit()
    project.status = "generated"
    db.commit()
    
    return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

@app.post("/projects/{project_id}/questions/{question_id}/regenerate")
async def regenerate_single_answer(
    request: Request,
    project_id: int,
    question_id: int,
    db: Session = Depends(get_db)
):
    """Regenerate the answer for a single question."""
    current_user = get_current_user_session(request, db)
    if not current_user:
        return RedirectResponse(url="/login")

    question = db.query(models.Question).filter(
        models.Question.id == question_id,
        models.Question.project_id == project_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        result = rag_engine.query(question.question_text)
        answer = db.query(models.Answer).filter(models.Answer.question_id == question_id).first()
        if answer:
            answer.answer_text = result['answer']
            answer.citations = result['citations']
            answer.confidence_score = result.get('confidence', 0.0)
            answer.is_edited = 0
        else:
            answer = models.Answer(
                question_id=question_id,
                answer_text=result['answer'],
                citations=result['citations'],
                confidence_score=result.get('confidence', 0.0)
            )
            db.add(answer)
        db.commit()
    except Exception as e:
        print(f"Error regenerating answer: {e}")

    return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

@app.post("/projects/{project_id}/questions/{question_id}/update")
async def update_answer(
    request: Request,
    project_id: int,
    question_id: int,
    answer_text: str = Form(...),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_session(request, db)
    if not current_user:
        return RedirectResponse(url="/login")
    
    answer = db.query(models.Answer).filter(models.Answer.question_id == question_id).first()
    if answer:
        answer.answer_text = answer_text
        answer.is_edited = 1
        db.commit()
    
    return RedirectResponse(url=f"/projects/{project_id}", status_code=302)

@app.post("/projects/{project_id}/export")
async def export_project(request: Request, project_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user_session(request, db)
    if not current_user:
        return RedirectResponse(url="/login")
    
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get original questionnaire file
    original_file = UPLOAD_DIR / f"{current_user.id}_{project.questionnaire_filename}"
    
    # Get all questions and answers
    questions = db.query(models.Question).filter(models.Question.project_id == project_id).order_by(models.Question.question_number).all()
    
    qa_data = []
    for question in questions:
        answer = db.query(models.Answer).filter(models.Answer.question_id == question.id).first()
        qa_data.append({
            'question_number': question.question_number,
            'question_text': question.question_text,
            'answer_text': answer.answer_text if answer else "",
            'citations': answer.citations if answer else [],
            'confidence_score': answer.confidence_score if answer else None,
            'original_data': question.original_row_data
        })
    
    # Export questionnaire
    output_file = export_questionnaire(project.name, qa_data)
    
    project.status = "exported"
    db.commit()
    
    return FileResponse(
        output_file,
        filename=f"{project.name}_completed.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.post("/documents/upload")
async def upload_document_form(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    current_user = get_current_user_session(request, db)
    if not current_user:
        return RedirectResponse(url="/login")
    
    # Validate file type
    allowed_types = [".txt", ".pdf"]
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_types:
        raise HTTPException(status_code=400, detail=f"File type {file_ext} not allowed. Only .txt and .pdf are supported.")
    
    # Save file
    file_path = UPLOAD_DIR / f"doc_{current_user.id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Extract text
    text_content = extract_text_from_file(str(file_path))
    
    # Create document record
    document = models.Document(
        user_id=current_user.id,
        filename=file.filename,
        file_path=str(file_path),
        file_type=file_ext.replace(".", ""),
        file_size=Path(file_path).stat().st_size
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Add to RAG index (non-fatal: document is saved to DB even if indexing fails)
    try:
        rag_engine.add_document(text_content, document.filename, document.id)
    except Exception as e:
        print(f"Warning: could not index document '{document.filename}': {e}")

    return RedirectResponse(url="/dashboard", status_code=302)

@app.post("/documents/{doc_id}/delete")
async def delete_document_form(request: Request, doc_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user_session(request, db)
    if not current_user:
        return RedirectResponse(url="/login")
    
    document = db.query(models.Document).filter(
        models.Document.id == doc_id,
        models.Document.user_id == current_user.id
    ).first()
    
    if document:
        # Delete file
        if Path(document.file_path).exists():
            Path(document.file_path).unlink()
        
        # Delete from database
        db.delete(document)
        db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=302)

# API root
@app.get("/api")
def api_root():
    return {"message": "EduSecure Questionnaire Assistant API", "docs": "/docs"}
