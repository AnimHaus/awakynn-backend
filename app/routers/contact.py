from datetime import datetime
from typing import List, Literal, Optional
from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.core.deps import require_admin
from app.models.contact import ContactMessage, TestimonialSubmission
from app.models.user import User

router = APIRouter(prefix="/contact", tags=["contact"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ContactPayload(BaseModel):
    name: str
    email: EmailStr
    phone: str = ""
    interest: str = ""
    message: str

class TestimonialPayload(BaseModel):
    name: str
    age: Optional[int] = None
    note: str = ""
    message: str

class ContactMessageOut(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    interest: str
    message: str
    status: str
    created_at: datetime

class TestimonialOut(BaseModel):
    id: str
    name: str
    age: Optional[int]
    note: str
    message: str
    approved: bool
    created_at: datetime


def _msg_out(m: ContactMessage) -> dict:
    return {
        "id": str(m.id),
        "name": m.name,
        "email": m.email,
        "phone": m.phone,
        "interest": m.interest,
        "message": m.message,
        "status": m.status,
        "created_at": m.created_at,
    }

def _test_out(t: TestimonialSubmission) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "age": t.age,
        "note": t.note,
        "message": t.message,
        "approved": t.approved,
        "created_at": t.created_at,
    }


# ── Public: submit contact message ───────────────────────────────────────────

@router.post("/messages", status_code=status.HTTP_201_CREATED)
async def submit_message(body: ContactPayload):
    msg = ContactMessage(**body.model_dump())
    await msg.insert()
    return {"ok": True}


# ── Public: submit testimonial ───────────────────────────────────────────────

@router.post("/testimonials", status_code=status.HTTP_201_CREATED)
async def submit_testimonial(body: TestimonialPayload):
    t = TestimonialSubmission(**body.model_dump())
    await t.insert()
    return {"ok": True}


# ── Admin: list contact messages ─────────────────────────────────────────────

@router.get("/messages", response_model=List[ContactMessageOut])
async def list_messages(_admin: User = Depends(require_admin)):
    msgs = await ContactMessage.find().sort(-ContactMessage.created_at).to_list()
    return [_msg_out(m) for m in msgs]


# ── Admin: update message status ─────────────────────────────────────────────

@router.patch("/messages/{msg_id}", response_model=ContactMessageOut)
async def update_message_status(
    msg_id: str,
    body: dict,
    _admin: User = Depends(require_admin),
):
    msg = await ContactMessage.get(PydanticObjectId(msg_id))
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if "status" in body and body["status"] in ("new", "read", "replied"):
        msg.status = body["status"]
        await msg.save()
    return _msg_out(msg)


# ── Admin: delete message ─────────────────────────────────────────────────────

@router.delete("/messages/{msg_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(msg_id: str, _admin: User = Depends(require_admin)):
    msg = await ContactMessage.get(PydanticObjectId(msg_id))
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    await msg.delete()


# ── Admin: list testimonials ─────────────────────────────────────────────────

@router.get("/testimonials", response_model=List[TestimonialOut])
async def list_testimonials(_admin: User = Depends(require_admin)):
    items = await TestimonialSubmission.find().sort(-TestimonialSubmission.created_at).to_list()
    return [_test_out(t) for t in items]


# ── Admin: approve / reject testimonial ──────────────────────────────────────

@router.patch("/testimonials/{tid}", response_model=TestimonialOut)
async def update_testimonial(
    tid: str,
    body: dict,
    _admin: User = Depends(require_admin),
):
    t = await TestimonialSubmission.get(PydanticObjectId(tid))
    if not t:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    if "approved" in body:
        t.approved = bool(body["approved"])
        await t.save()
    return _test_out(t)


# ── Admin: delete testimonial ─────────────────────────────────────────────────

@router.delete("/testimonials/{tid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_testimonial(tid: str, _admin: User = Depends(require_admin)):
    t = await TestimonialSubmission.get(PydanticObjectId(tid))
    if not t:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    await t.delete()
