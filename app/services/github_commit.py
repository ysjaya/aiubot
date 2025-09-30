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
    Commit semua file LATEST dari percakapan ke GitHub.
    Hanya file dengan status LATEST yang di-commit.
    """
    try:
        g = Github(github_token)
        repo = g.get_repo(repo_fullname)

        # Ambil semua attachment dengan status LATEST
        attachments = session.exec(
            select(models.Attachment)
            .where(models.Attachment.conversation_id == conversation_id)
            .where(models.Attachment.status == models.FileStatus.LATEST)
        ).all()

        if not attachments:
            return {
                "success": False,
                "error": "Tidak ada file LATEST untuk di-commit"
            }

        logger.info(f"[GITHUB COMMIT] Menemukan {len(attachments)} file LATEST untuk di-commit")

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
                logger.info(f"✅ Menambahkan file ke commit: {file_path}")

            except Exception as e:
                logger.error(f"❌ Gagal memproses file {filename}: {e}")
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
        master_ref = repo.get_git_ref(f"heads/{branch}")
        base_tree = repo.get_git_tree(master_ref.object.sha)

        new_tree = repo.create_git_tree(tree_elements, base_tree)
        parent = repo.get_git_commit(master_ref.object.sha)
        commit_message = commit_message or f"Commit dari AI Code Assistant - {len(tree_elements)} file"
        commit = repo.create_git_commit(commit_message, new_tree, [parent])

        # Update reference
        master_ref.edit(commit.sha)

        logger.info(f"✅ Commit berhasil: {commit.sha}")
        return {
            "success": True,
            "commit_sha": commit.sha,
            "message": commit_message,
            "file_count": len(tree_elements)
        }

    except Exception as e:
        logger.error(f"❌ Gagal melakukan commit: {e}")
        return {
            "success": False,
            "error": str(e)
    }
