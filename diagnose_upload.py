"""
M-Flow Upload Diagnosis Script

Quick diagnostic tool to identify common causes of file upload failures.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_env_file():
    """Check if .env file exists and has required settings."""
    print("=" * 60)
    print("1. Environment File Check")
    print("=" * 60)
    
    env_file = project_root / ".env"
    if not env_file.exists():
        print("❌ .env file not found")
        print(f"   Expected location: {env_file}")
        print("   Solution: Copy .env.template to .env and configure")
        return False
    
    print(f"✅ .env file exists: {env_file}")
    return True


def check_llm_config():
    """Check LLM configuration."""
    print("\n" + "=" * 60)
    print("2. LLM Configuration Check")
    print("=" * 60)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    provider = os.getenv("LLM_PROVIDER", "NOT SET")
    model = os.getenv("LLM_MODEL", "NOT SET")
    api_key = os.getenv("LLM_API_KEY", "")
    api_base = os.getenv("LLM_API_BASE", "NOT SET")
    
    issues = []
    
    if not api_key:
        print("❌ LLM_API_KEY is not set")
        issues.append("LLM_API_KEY missing - pipeline will fail")
    else:
        print(f"✅ LLM_API_KEY is set ({len(api_key)} chars)")
    
    if provider == "NOT SET":
        print("⚠️  LLM_PROVIDER not set (defaulting to 'openai')")
    else:
        print(f"✅ LLM_PROVIDER: {provider}")
    
    if model == "NOT SET":
        print("⚠️  LLM_MODEL not set (using default)")
    else:
        print(f"✅ LLM_MODEL: {model}")
    
    if api_base != "NOT SET":
        print(f"ℹ️  LLM_API_BASE: {api_base}")
    
    if issues:
        print("\n⚠️  Issues found:")
        for issue in issues:
            print(f"   - {issue}")
        print("\nSolution: Add to .env file:")
        print('   LLM_API_KEY=your_api_key_here')
        print('   LLM_PROVIDER=openai')
        print('   LLM_MODEL=gpt-4o')
        return False
    
    print("\n✅ LLM configuration looks good")
    return True


def check_database_config():
    """Check database configuration."""
    print("\n" + "=" * 60)
    print("3. Database Configuration Check")
    print("=" * 60)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    db_url = os.getenv("DATABASE_URL", "")
    graph_provider = os.getenv("GRAPH_DATABASE_PROVIDER", "networkx")
    vector_provider = os.getenv("VECTOR_DB_PROVIDER", "lancedb")
    
    if not db_url or "sqlite" in db_url.lower():
        print("⚠️  Using SQLite database")
        print("   - Limited concurrency support (serial execution)")
        print("   - May cause 'database is locked' errors")
        print("   - OK for development, not recommended for production")
        print("\n   Recommendation for production:")
        print("   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mflow")
    else:
        print(f"✅ Using external database: {db_url.split('://')[0]}")
    
    print(f"\nℹ️  Graph DB: {graph_provider}")
    print(f"ℹ️  Vector DB: {vector_provider}")
    
    # Check if SQLite file exists
    if "sqlite" in db_url.lower() or not db_url:
        sqlite_path = project_root / "m_flow.db"
        if sqlite_path.exists():
            print(f"✅ SQLite database exists: {sqlite_path}")
            size_mb = sqlite_path.stat().st_size / 1024 / 1024
            print(f"   Size: {size_mb:.2f} MB")
        else:
            print("ℹ️  SQLite database will be created on first run")
    
    return True


def check_python_environment():
    """Check Python environment."""
    print("\n" + "=" * 60)
    print("4. Python Environment Check")
    print("=" * 60)
    
    print(f"✅ Python version: {sys.version}")
    print(f"✅ Platform: {sys.platform}")
    print(f"✅ Project root: {project_root}")
    
    # Check if running in virtual environment
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        print(f"✅ Virtual environment: {sys.prefix}")
    else:
        print("⚠️  Not in virtual environment")
        print("   Recommendation: Use 'uv' for dependency management")
    
    # Check key dependencies
    print("\nChecking key packages...")
    try:
        import fastapi
        print(f"✅ fastapi: {fastapi.__version__}")
    except ImportError:
        print("❌ fastapi not installed")
    
    try:
        import sqlalchemy
        print(f"✅ sqlalchemy: {sqlalchemy.__version__}")
    except ImportError:
        print("❌ sqlalchemy not installed")
    
    try:
        import openai
        print(f"✅ openai: {openai.__version__}")
    except ImportError:
        print("⚠️  openai not installed (may use other LLM providers)")


def check_file_permissions():
    """Check file permissions for common directories."""
    print("\n" + "=" * 60)
    print("5. File Permissions Check")
    print("=" * 60)
    
    dirs_to_check = [
        project_root / "m_flow" / ".data_storage",
        project_root / "m_flow" / ".m_flow_system",
        project_root / "logs",
    ]
    
    all_ok = True
    for dir_path in dirs_to_check:
        if dir_path.exists():
            if os.access(dir_path, os.W_OK):
                print(f"✅ Writable: {dir_path}")
            else:
                print(f"❌ Not writable: {dir_path}")
                all_ok = False
        else:
            print(f"ℹ️  Not exists (will be created): {dir_path}")
    
    if not all_ok:
        print("\n⚠️  Some directories are not writable")
        print("   Solution: Check file permissions or run as administrator")


def check_running_processes():
    """Check if backend service is running."""
    print("\n" + "=" * 60)
    print("6. Service Status Check")
    print("=" * 60)
    
    import socket
    
    # Check if port 8000 is in use
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 8000))
    sock.close()
    
    if result == 0:
        print("✅ Backend service appears to be running (port 8000)")
    else:
        print("⚠️  Backend service not detected on port 8000")
        print("   Start it with: uv run python -m m_flow.api.client")


def run_diagnostics():
    """Run all diagnostic checks."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "M-Flow Upload Diagnosis Tool" + " " * 18 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    checks = [
        check_env_file,
        check_llm_config,
        check_database_config,
        check_python_environment,
        check_file_permissions,
        check_running_processes,
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Check failed with error: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("DIAGNOSIS SUMMARY")
    print("=" * 60)
    
    if all(r is not False for r in results):
        print("\n✅ All checks passed!")
        print("\nIf uploads are still failing:")
        print("1. Check backend logs for detailed error messages")
        print("2. Try uploading a single small .txt file")
        print("3. Enable DEBUG logging: LOG_LEVEL=DEBUG in .env")
        print("4. See UPLOAD_TROUBLESHOOTING.md for more help")
    else:
        print("\n⚠️  Issues detected! Please review the output above.")
        print("\nCommon fixes:")
        print("1. Add LLM_API_KEY to .env file")
        print("2. Restart backend service after config changes")
        print("3. Check file formats are supported")
        print("4. Upload files one at a time (SQLite limitation)")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    run_diagnostics()
