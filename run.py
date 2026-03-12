#!/usr/bin/env python3
"""
Simple script to run the FastAPI application
Usage: python3 run.py
"""
import uvicorn

if __name__ == "__main__":
    print("🎓 Starting EduSecure Questionnaire Assistant...")
    print("📡 Server will be available at: http://localhost:8000")
    print("📚 API docs at: http://localhost:8000/docs")
    print("\nPress CTRL+C to stop\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
