#!/bin/bash

# Setup script for EduSecure Questionnaire Assistant

echo "🎓 Setting up EduSecure Questionnaire Assistant..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Copy environment file
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and set your GROQ_API_KEY (free at https://console.groq.com)"
fi

# Create sample data
echo "Creating sample questionnaire..."
python create_sample_data.py

# Initialize database
echo "Initializing database..."
python -m app.init_db

echo ""
echo "✅ Setup complete!"
echo ""
