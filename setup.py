#!/usr/bin/env python3
"""
Setup script for the AI bid application system.
"""
import os
import sys
import subprocess
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"Running: {description}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    """Main setup function."""
    print("AI Bid Application System Setup")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("✗ Python 3.8 or higher is required")
        sys.exit(1)
    else:
        print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Install dependencies
    if not run_command("pip install -r requirements.txt", "Installing Python dependencies"):
        print("Failed to install dependencies. Please check your Python environment.")
        sys.exit(1)
    
    # Create necessary directories
    directories = ["documents", "templates", "applications", "logs", "temp_uploads"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✓ Created directory: {directory}")
    
    # Check for .env file
    env_file = Path(".env")
    if not env_file.exists():
        print("\n⚠️  Configuration file not found!")
        print("Please copy config.env.example to .env and configure your settings:")
        print("  cp config.env.example .env")
        print("  # Edit .env with your API keys and company information")
    else:
        print("✓ Configuration file found")
    
    # Check for documents
    documents_dir = Path("documents")
    if not any(documents_dir.iterdir()):
        print("\n⚠️  No documents found in documents/ folder!")
        print("Please add your company documents to the documents/ folder:")
        print("  - Company profile/capability statements")
        print("  - Past performance documents")
        print("  - Team qualifications")
        print("  - Certifications")
        print("  - Any other relevant materials")
    else:
        print("✓ Documents found in documents/ folder")
    
    print("\n" + "=" * 40)
    print("Setup completed!")
    print("\nNext steps:")
    print("1. Configure your .env file with API keys and company information")
    print("2. Add your company documents to the documents/ folder")
    print("3. Run: python main.py --config-check")
    print("4. Run: python main.py (to start the system)")

if __name__ == "__main__":
    main()

