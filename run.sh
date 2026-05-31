#!/bin/bash

# Jinbocho Auth Service - Development Startup Script

set -e

echo "🚀 Starting Jinbocho Auth Service..."

# Check Python version
python_version=$(python --version | awk '{print $2}')
echo "✅ Python version: $python_version"

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
fi

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
else
    echo "✅ Dependencies already installed"
fi

# Start the server
echo "🎯 Starting server on http://localhost:8000"
echo "📚 Swagger UI: http://localhost:8000/docs"
echo "📖 ReDoc: http://localhost:8000/redoc"
echo ""
echo "Press Ctrl+C to stop"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
