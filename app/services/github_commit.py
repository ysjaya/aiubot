# app/services/github_commit.py
import logging
from typing import List, Dict, Optional
from github import Github, GithubException
from sqlmodel import Session, select
from app.db import models

logger = logging.getLogger(__name__)

def commit_all_files(
    github_token: str,
    repo_fullname: str,
    conversation_id: int,
    session: Session,
    branch: str = "main",
    commit_message: str = None,
    base_path: str = ""
) -> Dict:
    """
    Commit all files from a conversation to a GitHub repository
    
    Args:
        github_token: GitHub access token
        repo_fullname: Full repository name (owner/repo)
        conversation_id: Conversation ID containing files
        session: Database session
        branch: Target branch (default: main)
        commit_message: Custom commit message
        base_path: Base path in repo to place files
        
    Returns:
        Dict with commit details or error
    """
    try:
        # Initialize GitHub client
        g = Github(github_token)
        repo = g.get_repo(repo_fullname)
        
        # Get all LATEST files from conversation
        attachments = session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == conversation_id)
            .where(models.Attachment.status == models.FileStatus.LATEST)
        ).all()
        
        if not attachments:
            return {
                "success": False,
                "error": "No files to commit"
            }
        
        logger.info(f"[GITHUB COMMIT] Found {len(attachments)} files to commit")
        
        # Get the latest commit SHA from the branch
        try:
            ref = repo.get_git_ref(f"heads/{branch}")
            base_commit = repo.get_git_commit(ref.object.sha)
            base_tree = base_commit.tree
        except GithubException as e:
            if e.status == 404:
                # Branch doesn't exist, create it
                logger.info(f"[GITHUB COMMIT] Branch {branch} doesn't exist, will create it")
                master_ref = repo.get_git_ref("heads/main")
                base_commit = repo.get_git_commit(master_ref.object.sha)
                base_tree = base_commit.tree
            else:
                raise
        
        # Prepare tree elements for all files
        tree_elements = []
        
        for att in attachments:
            # Determine file path
            if base_path:
                file_path = f"{base_path.rstrip('/')}/{att.original_filename or att.filename}"
            else:
                file_path = att.original_filename or att.filename
            
            logger.info(f"[GITHUB COMMIT] Adding file: {file_path}")
            
            # Create blob for file content
            blob = repo.create_git_blob(att.content, "utf-8")
            
            tree_elements.append({
                "path": file_path,
                "mode": "100644",  # Regular file
                "type": "blob",
                "sha": blob.sha
            })
        
        # Create new tree
        new_tree = repo.create_git_tree(tree_elements, base_tree)
        
        # Create commit message
        if not commit_message:
            commit_message = f"Update {len(attachments)} file(s) from AI Code Assistant"
        
        # Create commit
        new_commit = repo.create_git_commit(
            message=commit_message,
            tree=new_tree,
            parents=[base_commit]
        )
        
        # Update branch reference
        try:
            ref = repo.get_git_ref(f"heads/{branch}")
            ref.edit(new_commit.sha)
        except GithubException as e:
            if e.status == 404:
                # Create new branch
                repo.create_git_ref(f"refs/heads/{branch}", new_commit.sha)
                logger.info(f"[GITHUB COMMIT] Created new branch: {branch}")
        
        commit_url = f"https://github.com/{repo_fullname}/commit/{new_commit.sha}"
        
        logger.info(f"[GITHUB COMMIT] ✅ Successfully committed {len(attachments)} files")
        logger.info(f"[GITHUB COMMIT] Commit URL: {commit_url}")
        
        return {
            "success": True,
            "commit_sha": new_commit.sha,
            "commit_url": commit_url,
            "files_count": len(attachments),
            "branch": branch,
            "message": commit_message
        }
        
    except GithubException as e:
        logger.error(f"[GITHUB COMMIT] GitHub API error: {e}")
        return {
            "success": False,
            "error": f"GitHub API error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"[GITHUB COMMIT] Error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
