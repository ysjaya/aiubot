# app/api/draft_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from datetime import datetime

from app.db.database import get_session
from app.db import models
from app.services.cerebras_chain import promote_draft_to_attachment

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/drafts")
async def list_drafts(
    conversation_id: int,
    session: Session = Depends(get_session)
):
    """List all drafts for a conversation"""
    try:
        drafts = session.exec(
            select(models.DraftVersion)
            .where(models.DraftVersion.conversation_id == conversation_id)
            .order_by(models.DraftVersion.created_at.desc())
        ).all()
        
        return {
            "success": True,
            "drafts": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "version_number": d.version_number,
                    "status": d.status.value,
                    "display_status": d.get_display_status(),
                    "is_complete": d.is_complete,
                    "completeness_score": d.completeness_score,
                    "content_length": d.content_length,
                    "change_summary": d.change_summary,
                    "created_at": d.created_at.isoformat(),
                    "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
                    "promoted_at": d.promoted_at.isoformat() if d.promoted_at else None,
                }
                for d in drafts
            ]
        }
    except Exception as e:
        logger.error(f"Error listing drafts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/draft/{draft_id}")
async def get_draft(
    draft_id: int,
    session: Session = Depends(get_session)
):
    """Get full content of a specific draft"""
    try:
        draft = session.get(models.DraftVersion, draft_id)
        
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        return {
            "success": True,
            "draft": {
                "id": draft.id,
                "filename": draft.filename,
                "original_filename": draft.original_filename,
                "version_number": draft.version_number,
                "status": draft.status.value,
                "display_status": draft.get_display_status(),
                "is_complete": draft.is_complete,
                "has_syntax_errors": draft.has_syntax_errors,
                "completeness_score": draft.completeness_score,
                "content": draft.content,  # FULL CONTENT - 100% LENGKAP
                "content_hash": draft.content_hash,
                "content_length": draft.content_length,
                "change_summary": draft.change_summary,
                "change_details": draft.change_details,
                "ai_model": draft.ai_model,
                "generation_metadata": draft.generation_metadata,
                "created_at": draft.created_at.isoformat(),
                "reviewed_at": draft.reviewed_at.isoformat() if draft.reviewed_at else None,
                "promoted_at": draft.promoted_at.isoformat() if draft.promoted_at else None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/draft/{draft_id}/approve")
async def approve_draft(
    draft_id: int,
    session: Session = Depends(get_session)
):
    """Approve a draft"""
    try:
        draft = session.get(models.DraftVersion, draft_id)
        
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        if not draft.is_complete:
            raise HTTPException(status_code=400, detail="Cannot approve incomplete draft")
        
        draft.status = models.DraftStatus.APPROVED
        draft.reviewed_at = datetime.utcnow()
        session.add(draft)
        session.commit()
        
        return {
            "success": True,
            "message": f"Draft {draft_id} approved",
            "draft_id": draft_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/draft/{draft_id}/reject")
async def reject_draft(
    draft_id: int,
    session: Session = Depends(get_session)
):
    """Reject a draft"""
    try:
        draft = session.get(models.DraftVersion, draft_id)
        
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        draft.status = models.DraftStatus.REJECTED
        draft.reviewed_at = datetime.utcnow()
        session.add(draft)
        session.commit()
        
        return {
            "success": True,
            "message": f"Draft {draft_id} rejected",
            "draft_id": draft_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/draft/{draft_id}/promote")
async def promote_draft(
    draft_id: int,
    session: Session = Depends(get_session)
):
    """Promote approved draft to LATEST Attachment"""
    try:
        draft = session.get(models.DraftVersion, draft_id)
        
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        if draft.status != models.DraftStatus.APPROVED:
            raise HTTPException(status_code=400, detail="Draft must be approved before promotion")
        
        if not draft.is_complete:
            raise HTTPException(status_code=400, detail="Cannot promote incomplete draft")
        
        # Promote to Attachment
        new_attachment = await promote_draft_to_attachment(draft, session)
        
        if not new_attachment:
            raise HTTPException(status_code=500, detail="Failed to promote draft")
        
        return {
            "success": True,
            "message": f"Draft promoted to Attachment v{new_attachment.version}",
            "attachment_id": new_attachment.id,
            "version": new_attachment.version
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error promoting draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/drafts/pending")
async def list_pending_drafts(
    conversation_id: int,
    session: Session = Depends(get_session)
):
    """List all pending drafts awaiting review"""
    try:
        drafts = session.exec(
            select(models.DraftVersion)
            .where(models.DraftVersion.conversation_id == conversation_id)
            .where(models.DraftVersion.status == models.DraftStatus.PENDING)
            .order_by(models.DraftVersion.created_at.desc())
        ).all()
        
        return {
            "success": True,
            "count": len(drafts),
            "drafts": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "version_number": d.version_number,
                    "is_complete": d.is_complete,
                    "completeness_score": d.completeness_score,
                    "change_summary": d.change_summary,
                    "created_at": d.created_at.isoformat(),
                }
                for d in drafts
            ]
        }
    except Exception as e:
        logger.error(f"Error listing pending drafts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
