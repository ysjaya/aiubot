from github import Github, Auth, GithubException
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Text file extensions to import
TEXT_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.r',
    '.html', '.css', '.scss', '.sass', '.less', '.vue', '.svelte',
    '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.conf', '.config',
    '.md', '.txt', '.rst', '.adoc',
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
    '.sql', '.prisma', '.graphql', '.proto', '.dockerfile',
    '.env.example', '.gitignore', '.dockerignore', '.editorconfig',
    'Dockerfile', 'Makefile', 'Rakefile', 'CMakeLists.txt', 'package.json',
    'requirements.txt', 'setup.py', 'pyproject.toml', 'Cargo.toml'
}

# Directories to skip
SKIP_DIRS = {
    'node_modules', '__pycache__', 'venv', 'env', '.venv', '.env',
    '.git', '.github', '.gitlab', '.svn',
    'dist', 'build', 'target', 'out', 'output',
    '.next', '.nuxt', '.cache', '.parcel-cache',
    'bin', 'obj', 'pkg',
    'vendor', 'deps', 'packages',
    '.pytest_cache', '.mypy_cache', '.ruff_cache',
    'coverage', '.nyc_output', 'htmlcov',
    '.idea', '.vscode', '.vs'
}

def get_user_repos(token: str):
    """Get user's GitHub repositories"""
    try:
        auth = Auth.Token(token)
        g = Github(auth=auth)
        user = g.get_user()
        
        repos = []
        for repo in user.get_repos(sort="updated", direction="desc"):
            repos.append({
                "full_name": repo.full_name,
                "name": repo.name,
                "description": repo.description,
                "language": repo.language,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                "private": repo.private,
                "size": repo.size,
                "stars": repo.stargazers_count
            })
        
        logger.info(f"Retrieved {len(repos)} repositories")
        return repos
        
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        raise Exception(f"GitHub API error: {e.data.get('message', str(e))}")
    except Exception as e:
        logger.error(f"Error getting repos: {e}")
        raise

def should_import_file(file_path: str, file_size: int) -> tuple[bool, str]:
    """
    Determine if a file should be imported
    Returns: (should_import: bool, reason: str)
    """
    # Check size (max 1MB)
    if file_size > 1_000_000:
        return False, "File too large (>1MB)"
    
    # Check if in skip directory
    path_parts = file_path.split('/')
    for part in path_parts[:-1]:  # Exclude filename
        if part in SKIP_DIRS:
            return False, f"In excluded directory: {part}"
    
    # Check extension
    filename = path_parts[-1]
    
    # Special files without extensions
    if filename in TEXT_EXTENSIONS:
        return True, "Special text file"
    
    # Check extension
    if '.' in filename:
        ext = '.' + filename.split('.')[-1]
        if ext.lower() in TEXT_EXTENSIONS:
            return True, f"Text file ({ext})"
    
    return False, "Not a recognized text file"

def list_repo_files(repo_fullname: str, token: str):
    """
    List all importable files in a GitHub repository with metadata
    """
    try:
        auth = Auth.Token(token)
        g = Github(auth=auth)
        repo = g.get_repo(repo_fullname)
        
        files = []
        contents_list = list(repo.get_contents(""))
        
        while contents_list:
            file_content = contents_list.pop(0)
            
            if file_content.type == "dir":
                # Skip excluded directories
                if file_content.name not in SKIP_DIRS:
                    try:
                        dir_contents = repo.get_contents(file_content.path)
                        contents_list.extend(list(dir_contents) if isinstance(dir_contents, list) else [dir_contents])
                    except GithubException as e:
                        logger.warning(f"Cannot access directory {file_content.path}: {e}")
            else:
                # Check if file should be imported
                should_import, reason = should_import_file(
                    file_content.path,
                    file_content.size
                )
                
                files.append({
                    'path': file_content.path,
                    'size': file_content.size,
                    'should_import': should_import,
                    'reason': reason,
                    'sha': file_content.sha
                })
        
        # Sort: importable first, then by path
        files.sort(key=lambda x: (not x['should_import'], x['path']))
        
        logger.info(f"Found {len([f for f in files if f['should_import']])} importable files in {repo_fullname}")
        return files
        
    except GithubException as e:
        logger.error(f"GitHub API error listing files: {e}")
        raise Exception(f"GitHub API error: {e.data.get('message', str(e))}")
    except Exception as e:
        logger.error(f"Error listing files for {repo_fullname}: {e}")
        raise

def get_file_content(repo_fullname: str, file_path: str, token: str):
    """Get content of a specific file from GitHub repository"""
    try:
        auth = Auth.Token(token)
        g = Github(auth=auth)
        repo = g.get_repo(repo_fullname)
        
        file_content_obj = repo.get_contents(file_path)
        # Handle both single file and list return types
        if isinstance(file_content_obj, list):
            file_content_obj = file_content_obj[0]
        
        content = file_content_obj.decoded_content.decode('utf-8')
        
        logger.info(f"Retrieved file: {file_path} from {repo_fullname}")
        return {
            'content': content,
            'sha': file_content_obj.sha,
            'size': file_content_obj.size
        }
        
    except UnicodeDecodeError:
        logger.error(f"File is not UTF-8 encoded: {file_path}")
        raise Exception("File is not a valid text file (UTF-8 encoding required)")
    except GithubException as e:
        logger.error(f"GitHub API error getting file: {e}")
        raise Exception(f"GitHub API error: {e.data.get('message', str(e))}")
    except Exception as e:
        logger.error(f"Error getting file {file_path} from {repo_fullname}: {e}")
        raise

def import_selected_files(
    repo_fullname: str,
    file_paths: list[str],
    token: str,
    progress_callback=None
):
    """
    Import selected files from repository
    Returns list of file data with content
    """
    try:
        auth = Auth.Token(token)
        g = Github(auth=auth)
        repo = g.get_repo(repo_fullname)
        
        imported_files = []
        total = len(file_paths)
        
        for idx, file_path in enumerate(file_paths):
            try:
                if progress_callback:
                    progress_callback(idx + 1, total, file_path)
                
                file_content_obj = repo.get_contents(file_path)
                # Handle both single file and list return types
                if isinstance(file_content_obj, list):
                    file_content_obj = file_content_obj[0]
                
                # Verify it's not too large
                if file_content_obj.size > 1_000_000:
                    logger.warning(f"Skipping large file: {file_path} ({file_content_obj.size} bytes)")
                    continue
                
                # Try to decode as UTF-8
                try:
                    content = file_content_obj.decoded_content.decode('utf-8')
                except UnicodeDecodeError:
                    logger.warning(f"Skipping non-UTF-8 file: {file_path}")
                    continue
                
                imported_files.append({
                    'path': file_path,
                    'content': content,
                    'size': file_content_obj.size,
                    'sha': file_content_obj.sha,
                    'metadata': {
                        'repo': repo_fullname,
                        'imported_at': datetime.utcnow().isoformat(),
                        'github_url': f"https://github.com/{repo_fullname}/blob/main/{file_path}"
                    }
                })
                
                logger.info(f"Imported: {file_path} ({file_content_obj.size} bytes)")
                
            except Exception as e:
                logger.error(f"Failed to import {file_path}: {e}")
                continue
        
        logger.info(f"Successfully imported {len(imported_files)}/{total} files from {repo_fullname}")
        return imported_files
        
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        raise Exception(f"GitHub API error: {e.data.get('message', str(e))}")
    except Exception as e:
        logger.error(f"Error importing files from {repo_fullname}: {e}")
        raise

def get_all_repo_files(repo_fullname: str, token: str):
    """
    Automatically import all valid text files from a repository
    Legacy function - use import_selected_files for better control
    """
    try:
        # Get list of all files
        files = list_repo_files(repo_fullname, token)
        
        # Filter only importable files
        importable = [f['path'] for f in files if f['should_import']]
        
        # Import them
        return import_selected_files(repo_fullname, importable, token)
        
    except Exception as e:
        logger.error(f"Error in get_all_repo_files: {e}")
        raise
