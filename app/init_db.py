# Initialize database tables
from app.database import engine, Base
from app.models import User, Project, Question, Answer, Document, DocumentChunk

def init_database():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_database()
