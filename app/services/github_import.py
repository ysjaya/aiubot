from github import Github, Auth

def get_user_repos(token: str):
    auth = Auth.Token(token)
    g = Github(auth=auth)
    user = g.get_user()
    repos = [{"full_name": repo.full_name} for repo in user.get_repos(sort="updated")]
    return repos

def list_files(repo_fullname: str, token: str):
    auth = Auth.Token(token)
    g = Github(auth=auth)
    repo = g.get_repo(repo_fullname)
    files = []
    
    try:
        contents = repo.get_contents("")
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path))
            else:
                files.append(file_content.path)
    except Exception as e:
        print(f"Error listing files for {repo_fullname}: {e}")
        return []
        
    return files

def get_file_content(repo_fullname: str, file_path: str, token: str):
    auth = Auth.Token(token)
    g = Github(auth=auth)
    repo = g.get_repo(repo_fullname)
    file_content = repo.get_contents(file_path)
    return file_content.decoded_content.decode()
