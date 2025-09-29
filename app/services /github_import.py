import os
from github import Github

def list_files(repo_fullname):
    g = Github(os.environ.get("GITHUB_TOKEN"))
    repo = g.get_repo(repo_fullname)
    files = []
    def walk(path=""):
        contents = repo.get_contents(path)
        for c in contents:
            if c.type == "dir":
                walk(c.path)
            else:
                files.append(c.path)
    walk()
    return files

def get_file_content(repo_fullname, file_path):
    g = Github(os.environ.get("GITHUB_TOKEN"))
    repo = g.get_repo(repo_fullname)
    file = repo.get_contents(file_path)
    return file.decoded_content.decode()
