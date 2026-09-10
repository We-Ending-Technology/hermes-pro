from io import BytesIO


def export_pdf(markdown: str, title: str) -> bytes:
    """Gera um PDF simples sem depender de executáveis do sistema no Render."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("PDF exporter dependency is not installed") from exc
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    width, height = letter
    y = height - 48
    pdf.setTitle(title[:120])
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(48, y, title[:90])
    y -= 30
    pdf.setFont("Helvetica", 10)
    for raw_line in markdown.splitlines():
        line = raw_line.replace("#", "").strip()
        if not line:
            y -= 12
            continue
        for start in range(0, len(line), 95):
            if y < 48:
                pdf.showPage(); pdf.setFont("Helvetica", 10); y = height - 48
            pdf.drawString(48, y, line[start:start + 95])
            y -= 14
    pdf.save()
    return output.getvalue()
