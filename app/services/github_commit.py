# app/services/github_commit.py
import logging
from typing import List, Dict, Optional
from github import Github, GithubException, InputGitTreeElement
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
                # Branch doesn't exist, create it from default branch
                default_branch = repo.default_branch
                default_ref = repo.get_git_ref(f"heads/{default_branch}")
                repo.create_git_ref(f"refs/heads/{branch}", default_ref.object.sha)
                ref = repo.get_git_ref(f"heads/{branch}")
                base_commit = repo.get_git_commit(default_ref.object.sha)
                base_tree = base_commit.tree
                logger.info(f"[GITHUB COMMIT] Created new branch: {branch}")
            else:
                raise
        
        # Create blob for each file and build tree
        tree_elements = []
        
        for attachment in attachments:
            # Skip if no content
            if not attachment.content:
                logger.warning(f"Skipping empty file: {attachment.filename}")
                continue
                
            # Create blob
            blob = repo.create_git_blob(attachment.content, "utf-8")
            
            # Create proper InputGitTreeElement
            element = InputGitTreeElement(
                path=f"{base_path}/{attachment.filename}".lstrip('/'),  # Ensure proper path
                mode="100644",  # File mode
                type="blob",    # Object type
                sha=blob.sha    # SHA of the blob
            )
            
            tree_elements.append(element)
            logger.debug(f"Added file to commit: {attachment.filename}")
        
        # Create new tree with all files
        tree = repo.create_git_tree(tree_elements, base_tree)
        
        # Create commit
        if not commit_message:
            commit_message = f"Commit from AI Code Assistant - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        commit = repo.create_git_commit(
            commit_message,
            tree,
            [base_commit]
        )
        
        # Update reference to point to new commit
        ref.edit(commit.sha)
        
        logger.info(f"[GITHUB COMMIT] Successfully committed {len(tree_elements)} files to {repo_fullname} on branch {branch}")
        
        return {
            "success": True,
            "commit_sha": commit.sha,
            "branch": branch,
            "files_count": len(tree_elements),
            "message": commit_message
        }
        
    except Exception as e:
        logger.error(f"Failed to commit files: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
                }
