from github import Github, Auth, GithubException
import logging

logger = logging.getLogger(__name__)

def get_user_repos(token: str):
    """Get user's GitHub repositories"""
    try:
        auth = Auth.Token(token)
        g = Github(auth=auth)
        user = g.get_user()
        
        repos = []
        for repo in user.get_repos(sort="updated"):
            repos.append({"full_name": repo.full_name})
        
        logger.info(f"Retrieved {len(repos)} repositories")
        return repos
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        raise Exception(f"GitHub API error: {e.data.get('message', str(e))}")
    except Exception as e:
        logger.error(f"Error getting repos: {e}")
        raise

def list_files(repo_fullname: str, token: str):
    """List all files in a GitHub repository"""
    try:
        auth = Auth.Token(token)
        g = Github(auth=auth)
        repo = g.get_repo(repo_fullname)
        
        files = []
        contents = repo.get_contents("")
        
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path))
            else:
                files.append(file_content.path)
        
        logger.info(f"Listed {len(files)} files from {repo_fullname}")
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
        
        file_content = repo.get_contents(file_path)
        content = file_content.decoded_content.decode('utf-8')
        
        logger.info(f"Retrieved file: {file_path} from {repo_fullname}")
        return content
    except UnicodeDecodeError:
        logger.error(f"File is not UTF-8 encoded: {file_path}")
        raise Exception("File is not a valid text file (UTF-8 encoding required)")
    except GithubException as e:
        logger.error(f"GitHub API error getting file: {e}")
        raise Exception(f"GitHub API error: {e.data.get('message', str(e))}")
    except Exception as e:
        logger.error(f"Error getting file {file_path} from {repo_fullname}: {e}")
        raise

def get_all_repo_files(repo_fullname: str, token: str):
    """Get all text files from a repository"""
    try:
        auth = Auth.Token(token)
        g = Github(auth=auth)
        repo = g.get_repo(repo_fullname)
        
        files_data = []
        contents = repo.get_contents("")
        
        # Extensions to import
        text_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
            '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.r',
            '.html', '.css', '.scss', '.sass', '.less', '.vue', '.svelte',
            '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.conf',
            '.md', '.txt', '.rst', '.adoc',
            '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
            '.sql', '.prisma', '.graphql', '.proto',
            '.env.example', '.gitignore', '.dockerignore',
            'Dockerfile', 'Makefile', 'Rakefile', 'CMakeLists.txt'
        }
        
        while contents:
            file_content = contents.pop(0)
            
            if file_content.type == "dir":
                # Skip common non-source directories
                skip_dirs = {'node_modules', '__pycache__', 'venv', 'env', '.git', 
                           'dist', 'build', '.next', '.nuxt', 'target', 'bin', 'obj'}
                if file_content.name not in skip_dirs:
                    contents.extend(repo.get_contents(file_content.path))
            else:
                # Check if file should be imported
                file_ext = '.' + file_content.name.split('.')[-1] if '.' in file_content.name else ''
                
                if (file_ext.lower() in text_extensions or 
                    file_content.name in text_extensions or
                    file_content.size < 100000):  # Max 100KB per file
                    
                    try:
                        content = file_content.decoded_content.decode('utf-8')
                        files_data.append({
                            'path': file_content.path,
                            'content': content
                        })
                        logger.info(f"Imported: {file_content.path}")
                    except (UnicodeDecodeError, Exception) as e:
                        logger.warning(f"Skipped {file_content.path}: {str(e)}")
                        continue
        
        logger.info(f"Imported {len(files_data)} files from {repo_fullname}")
        return files_data
        
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        raise Exception(f"GitHub API error: {e.data.get('message', str(e))}")
    except Exception as e:
        logger.error(f"Error importing repo {repo_fullname}: {e}")
        raise
