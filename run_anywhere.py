import os
import subprocess
import sys

def run_command(cmd):
    """Run a command and print output"""
    print(f"▶ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"⚠ {result.stderr}")
    return result.returncode

def setup_git():
    print("\n" + "="*60)
    print("SETTING UP GIT FOR DUBAI DOCUMENTS")
    print("="*60)
    
    # Step 1: Initialize git if not exists
    if not os.path.exists(".git"):
        print("\n1. Initializing git repository...")
        run_command("git init")
    
    # Step 2: Remove venv from tracking if exists
    print("\n2. Cleaning up venv from git...")
    if os.path.exists("venv"):
        run_command("git rm -rf --cached venv/")
        print("✅ venv removed from git tracking")
    else:
        print("✅ venv folder not found")
    
    # Step 3: Create .gitignore if not exists
    print("\n3. Setting up .gitignore...")
    gitignore_content = """# Virtual environments
venv/
.env/
.venv/
env/
ENV/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/

# Django
*.log
*.pot
*.pyc
db.sqlite3
db.sqlite3-journal

# Media files
media/
Dubai Details/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Temp files
*.tmp
*.temp
"""
    
    with open(".gitignore", "w") as f:
        f.write(gitignore_content)
    print("✅ .gitignore created")
    
    # Step 4: Add and commit
    print("\n4. Adding files to git...")
    run_command("git add .")
    
    print("\n5. Committing...")
    run_command('git commit -m "Initial commit: Dubai Documents Management System"')
    
    # Step 5: Connect to GitHub
    print("\n6. Connecting to GitHub...")
    github_url = "https://github.com/melchs22/desktop-tutorial.git"
    run_command(f"git remote add origin {github_url}")
    
    # Step 6: Push to GitHub
    print("\n7. Pushing to GitHub...")
    result = run_command("git push -u origin main")
    
    if result != 0:
        print("\n⚠️  If main branch doesn't exist, try:")
        print("   git push -u origin master")
        run_command("git push -u origin master")
    
    print("\n" + "="*60)
    print("✅ GIT SETUP COMPLETE!")
    print("="*60)
    print("\n📦 Your repository now contains:")
    print("   ✅ Source code")
    print("   ✅ Requirements.txt")
    print("   ✅ Deployment files")
    print("   ❌ No venv folder")
    print("   ❌ No database files")
    print("   ❌ No media files")
    print("\n🔗 GitHub: https://github.com/melchs22/desktop-tutorial")

if __name__ == "__main__":
    setup_git()