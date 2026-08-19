from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from config import settings
from database.models import AuthorizedPersonnel, Student


CARD_SIZE = (85.60 * 2.834645669, 53.98 * 2.834645669)  # CR80 en puntos PDF.
GREEN_DARK = HexColor("#0B2D26")
GREEN = HexColor("#1D6B59")
GOLD = HexColor("#D0A94C")
INK = HexColor("#17312B")
MUTED = HexColor("#687D75")
PALE = HexColor("#EDF5F1")


def _fit_text(value: str, limit: int) -> str:
    value = " ".join(str(value or "").split())
    return value if len(value) <= limit else value[:max(1, limit - 3)].rstrip() + "..."


def _identity_data(identity: Student | AuthorizedPersonnel) -> dict:
    if isinstance(identity, Student):
        return {
            "type": "ESTUDIANTE", "name": identity.nombre_completo,
            "number": identity.matricula, "primary": identity.carrera,
            "secondary": f"Grupo {identity.grupo} - {identity.turno}",
            "campus": identity.plantel, "expires": identity.fecha_vencimiento.strftime("%d/%m/%Y"),
            "public_id": identity.student_id, "photo": identity.foto,
        }
    return {
        "type": identity.tipo_personal, "name": identity.nombre_completo,
        "number": identity.numero_empleado, "primary": identity.area or identity.tipo_personal,
        "secondary": identity.turno, "campus": identity.plantel,
        "expires": identity.fecha_vencimiento.strftime("%d/%m/%Y"),
        "public_id": identity.personnel_id, "photo": identity.foto,
    }


def _draw_photo(pdf: canvas.Canvas, photo_name: str | None, x: float, y: float, width: float, height: float,
                initials: str) -> None:
    photo_path = settings.UPLOAD_DIR / photo_name if photo_name else None
    if photo_path and photo_path.exists():
        try:
            image = ImageReader(str(photo_path))
            image_width, image_height = image.getSize()
            scale = max(width / image_width, height / image_height)
            draw_width, draw_height = image_width * scale, image_height * scale
            pdf.saveState()
            path = pdf.beginPath()
            path.roundRect(x, y, width, height, 5)
            pdf.clipPath(path, stroke=0, fill=0)
            pdf.drawImage(image, x - (draw_width - width) / 2, y - (draw_height - height) / 2,
                          draw_width, draw_height, preserveAspectRatio=True, mask="auto")
            pdf.restoreState()
            return
        except Exception:
            pass
    pdf.setFillColor(PALE)
    pdf.roundRect(x, y, width, height, 5, fill=1, stroke=0)
    pdf.setFillColor(GREEN)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(x + width / 2, y + height / 2 - 6, initials[:2].upper())


def _front(pdf: canvas.Canvas, data: dict) -> None:
    width, height = CARD_SIZE
    pdf.setFillColor(white)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(GREEN_DARK)
    pdf.rect(0, height - 34, width, 34, fill=1, stroke=0)
    pdf.setFillColor(GOLD)
    pdf.rect(0, height - 37, width, 3, fill=1, stroke=0)
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(13, height - 21, _fit_text(settings.INSTITUTION_NAME.upper(), 32))
    pdf.setFont("Helvetica", 5.5)
    pdf.drawRightString(width - 13, height - 21, "CONTROL DE ACCESO")

    initials = "".join(part[0] for part in data["name"].split()[:2] if part)
    _draw_photo(pdf, data["photo"], 13, 22, 57, 78, initials or "SA")
    pdf.setFillColor(GREEN)
    pdf.setFont("Helvetica-Bold", 6.2)
    pdf.drawString(82, 92, data["type"])
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(82, 74, _fit_text(data["name"], 27))
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 6.2)
    pdf.drawString(82, 61, _fit_text(data["primary"], 45))
    pdf.drawString(82, 50, _fit_text(data["secondary"], 45))
    pdf.setFillColor(PALE)
    pdf.roundRect(82, 23, width - 95, 19, 5, fill=1, stroke=0)
    pdf.setFillColor(GREEN_DARK)
    pdf.setFont("Helvetica-Bold", 7.3)
    pdf.drawString(90, 31, data["number"])
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 5.5)
    pdf.drawRightString(width - 20, 31, f"VIGENCIA {data['expires']}")
    pdf.setFillColor(GOLD)
    pdf.circle(width - 16, 12, 3, fill=1, stroke=0)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 4.7)
    pdf.drawString(13, 8, _fit_text(data["campus"], 52))


def _back(pdf: canvas.Canvas, data: dict, qr_path: Path) -> None:
    width, height = CARD_SIZE
    pdf.setFillColor(GREEN_DARK)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(GOLD)
    pdf.rect(0, height - 4, width, 4, fill=1, stroke=0)
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(15, height - 28, "ACCESO SEGURO")
    pdf.setFillColor(HexColor("#B9CFC7"))
    pdf.setFont("Helvetica", 6)
    pdf.drawString(15, height - 40, "QR firmado, individual y revocable")
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(15, 84, data["number"])
    pdf.setFont("Helvetica", 5.2)
    pdf.setFillColor(HexColor("#B9CFC7"))
    pdf.drawString(15, 72, _fit_text(data["public_id"], 37))
    pdf.drawString(15, 56, "Esta credencial es personal e intransferible.")
    pdf.drawString(15, 47, "En caso de pérdida, solicita la regeneración del QR.")
    pdf.drawString(15, 27, f"Vigente hasta: {data['expires']}")
    pdf.setFont("Helvetica-Bold", 5.2)
    pdf.setFillColor(GOLD)
    pdf.drawString(15, 14, _fit_text(settings.INSTITUTION_NAME.upper(), 40))
    pdf.setFillColor(white)
    pdf.roundRect(width - 101, 20, 86, 86, 7, fill=1, stroke=0)
    pdf.drawImage(ImageReader(str(qr_path)), width - 96, 25, 76, 76,
                  preserveAspectRatio=True, mask="auto")


def create_credential_pdf(identity: Student | AuthorizedPersonnel, qr_path: Path) -> bytes:
    if not qr_path.exists():
        raise ValueError("No se encontró el QR de la credencial")
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=CARD_SIZE, pageCompression=1)
    pdf.setTitle(f"Credencial - {_identity_data(identity)['number']}")
    data = _identity_data(identity)
    _front(pdf, data)
    pdf.showPage()
    _back(pdf, data, qr_path)
    pdf.showPage()
    pdf.save()
    return output.getvalue()
