"""
System test script to verify all components are working correctly

Run this after setup to ensure everything is configured properly.

Usage:
    python scripts/test_system.py
"""

import sys
sys.path.append('.')

import asyncio
from app.core.config import settings
from app.db.database import engine, init_main_database
from sqlmodel import Session, select
from app.db import models
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database():
    """Test database connection"""
    print("\n🧪 Testing Database Connection...")
    try:
        with Session(engine) as session:
            # Try a simple query
            result = session.exec(select(models.Project)).first()
            print("  ✅ Database connection successful")
            return True
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        return False

def test_api_keys():
    """Test API keys are configured"""
    print("\n🧪 Testing API Keys...")
    
    tests = [
        ("CEREBRAS_API_KEY", settings.CEREBRAS_API_KEY),
        ("DATABASE_URL", settings.DATABASE_URL),
        ("SECRET_KEY", settings.SECRET_KEY),
    ]
    
    all_good = True
    for name, value in tests:
        if value and len(str(value)) > 10:
            print(f"  ✅ {name} configured")
        else:
            print(f"  ❌ {name} missing or invalid")
            all_good = False
    
    return all_good

async def test_ai_connection():
    """Test AI API connection"""
    print("\n🧪 Testing AI Connection...")
    try:
        from cerebras.cloud.sdk import Cerebras
        
        client = Cerebras(api_key=settings.CEREBRAS_API_KEY)
        
        # Simple test call
        response = await asyncio.to_thread(
            client.chat.completions.create,
            messages=[{"role": "user", "content": "Say 'test ok'"}],
            model="llama-4-maverick-17b-128e-instruct",
            max_tokens=10
        )
        
        if response.choices[0].message.content:
            print("  ✅ AI connection successful")
            return True
        else:
            print("  ❌ AI returned empty response")
            return False
            
    except Exception as e:
        print(f"  ❌ AI connection failed: {e}")
        return False

def test_file_operations():
    """Test file attachment operations"""
    print("\n🧪 Testing File Operations...")
    try:
        from app.db.database import create_project_database, delete_project_database
        
        # Create test database
        test_db = create_project_database("test_project_delete_me")
        print(f"  ✅ Created test database: {test_db}")
        
        # Delete test database
        delete_project_database(test_db)
        print(f"  ✅ Deleted test database: {test_db}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ File operations failed: {e}")
        return False

def test_imports():
    """Test all required imports"""
    print("\n🧪 Testing Python Imports...")
    
    imports = [
        ("fastapi", "FastAPI"),
        ("sqlmodel", "SQLModel"),
        ("cerebras.cloud.sdk", "Cerebras"),
        ("app.db.models", "Project"),
        ("app.services.cerebras_chain", "ai_chain_stream"),
    ]
    
    all_good = True
    for module, item in imports:
        try:
            exec(f"from {module} import {item}")
            print(f"  ✅ {module}.{item}")
        except Exception as e:
            print(f"  ❌ {module}.{item} - {e}")
            all_good = False
    
    return all_good

async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🚀 AI CODE ASSISTANT - SYSTEM TEST")
    print("="*60)
    
    # Initialize database
    print("\n📦 Initializing database...")
    try:
        init_main_database()
        print("  ✅ Database initialized")
    except Exception as e:
        print(f"  ❌ Database initialization failed: {e}")
        return
    
    # Run tests
    results = {
        "Imports": test_imports(),
        "Database": test_database(),
        "API Keys": test_api_keys(),
        "File Operations": test_file_operations(),
        "AI Connection": await test_ai_connection(),
    }
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED - System is ready!")
        print("\nNext steps:")
        print("  1. Run backend: python main.py")
        print("  2. Run frontend: cd frontend && npm run dev")
        print("  3. Open browser: http://localhost:5173")
    else:
        print("❌ SOME TESTS FAILED - Please fix issues above")
        print("\nCommon fixes:")
        print("  - Install missing packages: pip install -r requirements.txt")
        print("  - Check .env file has correct API keys")
        print("  - Ensure PostgreSQL is running")
        print("  - Verify database permissions")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
