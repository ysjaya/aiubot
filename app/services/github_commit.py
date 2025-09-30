# app/services/github_commit.py
import logging
import json
import os
from typing import List, Dict, Optional
from github import Github, GithubException, InputGitTreeElement
from sqlmodel import Session, select
from app.db import models
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_github_token(provided_token: Optional[str] = None) -> str:
    """
    Get GitHub token with proper fallback handling
    Priority: provided_token > env GITHUB_TOKEN > settings.GITHUB_TOKEN
    """
    if provided_token:
        return provided_token
    
    # Try environment variable first
    env_token = os.getenv("GITHUB_TOKEN")
    if env_token:
        logger.info("✅ Using GITHUB_TOKEN from environment")
        return env_token
    
    # Fallback to settings
    if settings.GITHUB_TOKEN:
        logger.info("✅ Using GITHUB_TOKEN from settings")
        return settings.GITHUB_TOKEN
    
    raise ValueError("GITHUB_TOKEN not found. Please set GITHUB_TOKEN environment variable.")


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
    Commit semua file LATEST dari percakapan ke GitHub.
    Hanya file dengan status LATEST yang di-commit.
    
    PENTING: File yang di-commit adalah file yang LENGKAP 100% dari sistem draft
    """
    try:
        # Get token with fallback
        token = get_github_token(github_token)
        g = Github(token)
        repo = g.get_repo(repo_fullname)

        # Ambil semua attachment dengan status LATEST
        attachments = session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == conversation_id)
            .where(models.Attachment.status == models.FileStatus.LATEST)
        ).all()

        if not attachments:
            logger.error("[GITHUB COMMIT] ❌ Tidak ada file dengan status LATEST untuk di-commit")
            logger.info("[GITHUB COMMIT] 💡 Tip: Import file dari GitHub atau promote draft ke LATEST terlebih dahulu")
            return {
                "success": False,
                "error": "Tidak ada file LATEST untuk di-commit. Import file dari GitHub atau buat draft terlebih dahulu."
            }

        logger.info(f"[GITHUB COMMIT] 📦 Menemukan {len(attachments)} file LATEST untuk di-commit")
        
        # Validasi semua file lengkap
        for att in attachments:
            if not att.content or len(att.content) < 10:
                logger.error(f"[GITHUB COMMIT] ❌ File {att.filename} terlalu pendek atau kosong")
                return {
                    "success": False,
                    "error": f"File {att.filename} tidak valid (terlalu pendek atau kosong)"
                }
            
            # Check for truncation markers
            if '...' in att.content or 'rest of code' in att.content.lower():
                logger.warning(f"[GITHUB COMMIT] ⚠️ File {att.filename} mungkin tidak lengkap (mengandung '...')")

        # Kumpulkan file yang akan di-commit
        tree_elements = []
        for att in attachments:
            filename = att.original_filename or att.filename
            file_path = f"{base_path}/{filename}".lstrip("/")

            try:
                content = att.content
                if isinstance(content, dict):
                    content = json.dumps(content, indent=2)
                elif not isinstance(content, str):
                    content = str(content)

                # Gunakan InputGitTreeElement untuk memastikan tipe benar
                element = InputGitTreeElement(
                    path=file_path,
                    mode='100644',
                    type='blob',
                    content=content
                )
                tree_elements.append(element)
                logger.info(f"[GITHUB COMMIT] ✅ Menambahkan file ke commit: {file_path} ({len(content)} chars)")

            except Exception as e:
                logger.error(f"[GITHUB COMMIT] ❌ Gagal memproses file {filename}: {e}")
                return {
                    "success": False,
                    "error": f"Error memproses file {filename}: {str(e)}"
                }

        if not tree_elements:
            return {
                "success": False,
                "error": "Tidak ada file valid untuk di-commit"
            }

        # Buat tree dan commit
        try:
            master_ref = repo.get_git_ref(f"heads/{branch}")
            base_tree = repo.get_git_tree(master_ref.object.sha)

            new_tree = repo.create_git_tree(tree_elements, base_tree)
            parent = repo.get_git_commit(master_ref.object.sha)
            
            if not commit_message:
                commit_message = f"✨ Update from AI Code Assistant - {len(tree_elements)} file(s) (LENGKAP 100%)"
            
            commit = repo.create_git_commit(commit_message, new_tree, [parent])

            # Update reference
            master_ref.edit(commit.sha)

            logger.info(f"[GITHUB COMMIT] ✅ Commit berhasil: {commit.sha}")
            logger.info(f"[GITHUB COMMIT] 📊 Total file: {len(tree_elements)}")
            logger.info(f"[GITHUB COMMIT] 📝 Message: {commit_message}")
            
            return {
                "success": True,
                "commit_sha": commit.sha,
                "commit_url": f"https://github.com/{repo_fullname}/commit/{commit.sha}",
                "message": commit_message,
                "file_count": len(tree_elements),
                "files": [f"{el.path} ({len(el.content)} chars)" for el in tree_elements]
            }
            
        except GithubException as e:
            logger.error(f"[GITHUB COMMIT] ❌ GitHub API error: {e}")
            return {
                "success": False,
                "error": f"GitHub API error: {e.data.get('message', str(e))}"
            }

    except ValueError as e:
        logger.error(f"[GITHUB COMMIT] ❌ Token error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"[GITHUB COMMIT] ❌ Gagal melakukan commit: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
