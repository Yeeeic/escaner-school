from __future__ import annotations

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Student
from security import validate_csrf
from services.access_service import get_people_inside, grouped_people_inside, process_access, recent_access, today_stats
from services.day_service import ensure_today_operation, operation_summary


router = APIRouter(prefix="/api")


class ScanPayload(BaseModel):
    qr_data: str = Field(min_length=1, max_length=512)


def _csrf(request: Request) -> None:
    validate_csrf(request, request.headers.get("X-CSRF-Token"))


@router.get("/student/{matricula}")
def student_by_matricula(matricula: str, db: Session = Depends(get_db)):
    student = db.scalar(select(Student).where(
        Student.matricula == matricula[:32], Student.eliminado.is_(False)))
    if not student:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")
    return {
        "student_id": student.student_id, "matricula": student.matricula, "name": student.nombre_completo,
        "career": student.carrera, "group": student.grupo, "campus": student.plantel, "shift": student.turno,
        "active": student.activo, "expires": student.fecha_vencimiento.isoformat(),
    }


@router.post("/access/scan")
def scan_access(payload: ScanPayload, request: Request, db: Session = Depends(get_db)):
    _csrf(request)
    return process_access(payload.qr_data, db)


@router.post("/access/decode-frame")
async def decode_frame(request: Request, frame: UploadFile = File(...)):
    _csrf(request)
    content = await frame.read(2_000_001)
    if len(content) > 2_000_000:
        raise HTTPException(status_code=413, detail="Imagen demasiado grande")
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=422, detail="Imagen inválida")
    value, points, _ = cv2.QRCodeDetector().detectAndDecode(image)
    return {"detected": bool(value), "qr_data": value if value else None, "points": points.tolist() if points is not None else None}


@router.get("/access/recent")
def access_recent(limit: int = 8, db: Session = Depends(get_db)):
    return recent_access(db, limit)


@router.get("/stats/today")
def stats_today(db: Session = Depends(get_db)):
    return today_stats(db)


@router.get("/inside")
def people_inside(db: Session = Depends(get_db)):
    return get_people_inside(db)


@router.get("/inside/grouped")
def people_inside_grouped(db: Session = Depends(get_db)):
    return grouped_people_inside(db)


@router.get("/day/status")
def day_status(db: Session = Depends(get_db)):
    return operation_summary(db, ensure_today_operation(db))
