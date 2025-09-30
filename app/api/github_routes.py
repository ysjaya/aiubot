from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from typing import List, Optional
import logging
import json
from datetime import datetime

from app.db.database import get_session
from app.db import models
from app.services import github_import, github_commit
from app.api.routers import get_github_token

logger = logging.getLogger(__name__)
router = APIRouter()

class GitHubImportRequest(BaseModel):
    repo_fullname: str
    file_paths: List[str]
    conversation_id: int
    project_id: int

class GitHubRepoListRequest(BaseModel):
    pass

class GitHubCommitRequest(BaseModel):
    repo_fullname: str
    conversation_id: int
    project_id: int
    branch: str = "main"
    commit_message: Optional[str] = None
    base_path: Optional[str] = ""

# ==================== GITHUB ROUTES ====================

@router.get("/repos")
async def list_github_repos(
    github_token: str = Depends(get_github_token)
):
    """List user's GitHub repositories"""
    try:
        repos = github_import.get_user_repos(github_token)
        return {"repos": repos, "count": len(repos)}
    except Exception as e:
        logger.error(f"Failed to list repos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/repo/{owner}/{repo}/files")
async def list_repo_files(
    owner: str,
    repo: str,
    github_token: str = Depends(get_github_token)
):
    """List files in a GitHub repository with import recommendations"""
    try:
        repo_fullname = f"{owner}/{repo}"
        files = github_import.list_repo_files(repo_fullname, github_token)
        
        # Separate importable and non-importable
        importable = [f for f in files if f['should_import']]
        non_importable = [f for f in files if not f['should_import']]
        
        return {
            "repo": repo_fullname,
            "total_files": len(files),
            "importable": importable,
            "non_importable": non_importable,
            "importable_count": len(importable),
            "total_size": sum(f['size'] for f in importable)
        }
        
    except Exception as e:
        logger.error(f"Failed to list repo files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import")
async def import_files_from_github(
    request: GitHubImportRequest,
    github_token: str = Depends(get_github_token),
    session: Session = Depends(get_session)
):
    """Import selected files from GitHub repository"""
    
    # Verify project exists
    project = session.get(models.Project, request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Verify conversation exists
    conv = session.get(models.Conversation, request.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    try:
        # Import files from GitHub
        logger.info(f"Importing {len(request.file_paths)} files from {request.repo_fullname}")
        
        imported_files = github_import.import_selected_files(
            request.repo_fullname,
            request.file_paths,
            github_token
        )
        
        if not imported_files:
            raise HTTPException(status_code=400, detail="No files could be imported")
        
        # Save as attachments
        attachments = []
        
        for file_data in imported_files:
            attachment = models.Attachment(
                conversation_id=request.conversation_id,
                filename=file_data['path'].split('/')[-1],
                original_filename=file_data['path'],
                content=file_data['content'],
                mime_type="text/plain",
                size_bytes=file_data['size'],
                status=models.FileStatus.ORIGINAL,
                version=1,
                import_source="github",
                import_metadata=json.dumps({
                    **file_data['metadata'],
                    'sha': file_data['sha'],
                    'full_path': file_data['path']
                })
            )
            
            session.add(attachment)
            attachments.append(attachment)
        
        session.commit()
        
        # Refresh to get IDs
        for att in attachments:
            session.refresh(att)
        
        logger.info(f"Successfully imported {len(attachments)} files")
        
        return {
            "success": True,
            "imported_count": len(attachments),
            "files": [
                {
                    "id": att.id,
                    "filename": att.filename,
                    "original_path": att.original_filename,
                    "size": att.size_bytes
                }
                for att in attachments
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to import files: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@router.get("/repo/{owner}/{repo}/import-preview")
async def preview_repo_import(
    owner: str,
    repo: str,
    github_token: str = Depends(get_github_token)
):
    """Preview what would be imported from a repository"""
    try:
        repo_fullname = f"{owner}/{repo}"
        files = github_import.list_repo_files(repo_fullname, github_token)
        
        importable = [f for f in files if f['should_import']]
        
        # Calculate statistics
        total_size = sum(f['size'] for f in importable)
        
        # Group by file type
        by_type = {}
        for f in importable:
            ext = f['path'].split('.')[-1] if '.' in f['path'] else 'no_ext'
            if ext not in by_type:
                by_type[ext] = []
            by_type[ext].append(f['path'])
        
        return {
            "repo": repo_fullname,
            "would_import": len(importable),
            "total_size": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "by_file_type": {k: len(v) for k, v in by_type.items()},
            "sample_files": [f['path'] for f in importable[:10]],
            "files": importable
        }
        
    except Exception as e:
        logger.error(f"Failed to preview import: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import-all/{owner}/{repo}")
async def import_all_from_repo(
    owner: str,
    repo: str,
    conversation_id: int,
    project_id: int,
    github_token: str = Depends(get_github_token),
    session: Session = Depends(get_session)
):
    """Import all valid files from a repository (quick import)"""
    
    # Verify project
    project = session.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        repo_fullname = f"{owner}/{repo}"
        
        # Get all importable files
        imported_files = github_import.get_all_repo_files(repo_fullname, github_token)
        
        if not imported_files:
            raise HTTPException(status_code=400, detail="No importable files found")
        
        # Save as attachments
        attachments = []
        
        for file_data in imported_files:
            attachment = models.Attachment(
                conversation_id=conversation_id,
                filename=file_data['path'].split('/')[-1],
                original_filename=file_data['path'],
                content=file_data['content'],
                mime_type="text/plain",
                size_bytes=file_data['size'],
                status=models.FileStatus.ORIGINAL,
                version=1,
                import_source="github",
                import_metadata=json.dumps(file_data['metadata'])
            )
            
            session.add(attachment)
            attachments.append(attachment)
        
        session.commit()
        
        for att in attachments:
            session.refresh(att)
        
        return {
            "success": True,
            "imported_count": len(attachments),
            "repo": repo_fullname,
            "message": f"Successfully imported {len(attachments)} files"
        }
        
    except Exception as e:
        logger.error(f"Failed to import all files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/commit-all")
async def commit_all_conversation_files(
    request: GitHubCommitRequest,
    github_token: str = Depends(get_github_token),
    session: Session = Depends(get_session)
):
    """Commit all LATEST files from a conversation to GitHub repository"""
    
    # Verify project
    project = session.get(models.Project, request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Verify conversation
    conv = session.get(models.Conversation, request.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    try:
        result = github_commit.commit_all_files(
            github_token=github_token,
            repo_fullname=request.repo_fullname,
            conversation_id=request.conversation_id,
            session=session,
            branch=request.branch,
            commit_message=request.commit_message,
            base_path=request.base_path
        )
        
        if result["success"]:
            logger.info(f"✅ Committed {result['files_count']} files to {request.repo_fullname}")
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Commit failed"))
            
    except Exception as e:
        logger.error(f"Failed to commit files: {e}")
        raise HTTPException(status_code=500, detail=str(e))
