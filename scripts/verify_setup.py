#!/usr/bin/env python3
"""
Scribe Setup Verification Script

This script verifies that the Scribe project is properly set up and ready to use.
It checks dependencies, database connectivity, and basic functionality.

Usage:
    uv run python scripts/verify_setup.py
"""

import sys
import os
from pathlib import Path
import subprocess

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_status(status, message):
    """Print a status message with color."""
    if status == "OK":
        print(f"{GREEN}✓{RESET} {message}")
    elif status == "ERROR":
        print(f"{RED}✗{RESET} {message}")
    elif status == "WARNING":
        print(f"{YELLOW}!{RESET} {message}")
    elif status == "INFO":
        print(f"{BLUE}ℹ{RESET} {message}")

def check_python_version():
    """Check if Python version is 3.6+"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 6:
        print_status("OK", f"Python version: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_status("ERROR", f"Python 3.6+ required, found: {version.major}.{version.minor}")
        return False

def check_virtual_environment():
    """Check if we're in a virtual environment."""
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print_status("OK", f"Virtual environment active: {sys.prefix}")
        return True
    else:
        print_status("WARNING", "Not in a virtual environment (but UV handles this)")
        return True  # UV manages this automatically

def check_environment_variables():
    """Check if required environment variables are set."""
    env_file = project_root / '.env'
    if env_file.exists():
        print_status("OK", ".env file found")
        
        # Check for required API keys
        from dotenv import load_dotenv
        load_dotenv()
        
        required_keys = ['ELEVENLABS_API_KEY']
        optional_keys = ['DEEPL_API_KEY', 'MS_TRANSLATOR_KEY']
        
        all_good = True
        for key in required_keys:
            if os.getenv(key):
                print_status("OK", f"{key} is set")
            else:
                print_status("ERROR", f"{key} is not set (required)")
                all_good = False
        
        for key in optional_keys:
            if os.getenv(key):
                print_status("OK", f"{key} is set")
            else:
                print_status("INFO", f"{key} is not set (optional)")
        
        return all_good
    else:
        print_status("ERROR", ".env file not found - create one with your API keys")
        return False

def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        import requests
        import elevenlabs
        import moviepy
        import tqdm
        import yaml
        import deepl
        import google.cloud.translate
        import openai
        import langdetect
        
        print_status("OK", "All required Python packages are installed")
        return True
    except ImportError as e:
        print_status("ERROR", f"Missing dependency: {str(e)}")
        print_status("INFO", "Run: uv pip install -r requirements.txt")
        return False

def check_database():
    """Check database connectivity and status."""
    try:
        from core_modules.db_manager import DatabaseManager
        
        db_path = project_root / 'media_tracking.db'
        if db_path.exists():
            print_status("OK", f"Database found: {db_path}")
            
            # Try to connect and get stats
            db = DatabaseManager(str(db_path))
            stats = db.execute_query("""
                SELECT 
                    COUNT(*) as total_files,
                    SUM(CASE WHEN transcription_status = 'completed' THEN 1 ELSE 0 END) as transcribed,
                    SUM(CASE WHEN translation_en_status = 'completed' THEN 1 ELSE 0 END) as translated_en,
                    SUM(CASE WHEN translation_de_status = 'completed' THEN 1 ELSE 0 END) as translated_de,
                    SUM(CASE WHEN translation_he_status = 'completed' THEN 1 ELSE 0 END) as translated_he
                FROM processing_status
            """)
            
            if stats:
                s = stats[0]
                print_status("INFO", f"Database contains {s['total_files']} files:")
                print(f"    - Transcribed: {s['transcribed']}")
                print(f"    - Translated (EN): {s['translated_en']}")
                print(f"    - Translated (DE): {s['translated_de']}")
                print(f"    - Translated (HE): {s['translated_he']}")
            
            return True
        else:
            print_status("WARNING", "Database not found (will be created on first use)")
            return True
            
    except Exception as e:
        print_status("ERROR", f"Database error: {str(e)}")
        return False

def check_directories():
    """Check if required directories exist."""
    dirs = {
        'output': "Processed file outputs",
        'logs': "Log files",
        'core_modules': "Core functionality modules",
        'scripts': "Executable scripts"
    }
    
    all_good = True
    for dir_name, description in dirs.items():
        dir_path = project_root / dir_name
        if dir_path.exists():
            print_status("OK", f"{dir_name}/ - {description}")
        else:
            print_status("WARNING", f"{dir_name}/ not found - {description}")
            all_good = False
    
    return all_good

def test_basic_functionality():
    """Test basic script functionality."""
    print("\n" + "="*50)
    print("Testing Basic Functionality")
    print("="*50)
    
    # Test db_query.py
    try:
        result = subprocess.run(
            ['uv', 'run', 'python', 'scripts/db_query.py', 
             'SELECT COUNT(*) as count FROM processing_status'],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print_status("OK", "db_query.py works correctly")
        else:
            print_status("ERROR", f"db_query.py failed: {result.stderr}")
    except Exception as e:
        print_status("ERROR", f"Could not test db_query.py: {str(e)}")
    
    # Test help for main scripts
    test_scripts = [
        'scripts/parallel_transcription.py',
        'scripts/media_processor.py',
        'scripts/run_full_pipeline.py'
    ]
    
    for script in test_scripts:
        script_path = project_root / script
        if script_path.exists():
            try:
                result = subprocess.run(
                    ['uv', 'run', 'python', script, '--help'],
                    cwd=project_root,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print_status("OK", f"{script} --help works")
                else:
                    print_status("WARNING", f"{script} may have import issues")
            except Exception as e:
                print_status("ERROR", f"Could not test {script}: {str(e)}")

def main():
    """Run all verification checks."""
    print("="*50)
    print("Scribe Setup Verification")
    print("="*50)
    print()
    
    print(f"Project root: {project_root}")
    print()
    
    # Run all checks
    checks = [
        ("Python Version", check_python_version),
        ("Virtual Environment", check_virtual_environment),
        ("Dependencies", check_dependencies),
        ("Environment Variables", check_environment_variables),
        ("Database", check_database),
        ("Directories", check_directories)
    ]
    
    all_passed = True
    for name, check_func in checks:
        print(f"\n{name}:")
        if not check_func():
            all_passed = False
    
    # Test functionality
    test_basic_functionality()
    
    # Summary
    print("\n" + "="*50)
    if all_passed:
        print(f"{GREEN}✓ Setup verification PASSED{RESET}")
        print("\nYou can now use the Scribe system. Try:")
        print("  uv run python scripts/db_query.py --format table \"SELECT COUNT(*) FROM processing_status\"")
    else:
        print(f"{RED}✗ Setup verification FAILED{RESET}")
        print("\nPlease fix the issues above before using the system.")
        print("See docs/SETUP_AND_USAGE.md for detailed instructions.")
    print("="*50)

if __name__ == "__main__":
    main()