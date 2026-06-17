from io import BytesIO

from django.http import HttpResponse
from django.template.loader import render_to_string
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def export_rows_xlsx(filename, title, headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append([title])
    ws.append(headers)
    for row in rows:
        ws.append(row)
    output = BytesIO()
    wb.save(output)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    return response


def export_rows_pdf(filename, title, headers, rows):
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    y = height - 40
    pdf.setFont('Helvetica-Bold', 14)
    pdf.drawString(40, y, title)
    y -= 28
    pdf.setFont('Helvetica-Bold', 8)
    pdf.drawString(40, y, ' | '.join(headers))
    y -= 18
    pdf.setFont('Helvetica', 8)
    for row in rows:
        if y < 40:
            pdf.showPage()
            y = height - 40
            pdf.setFont('Helvetica', 8)
        text = ' | '.join(str(value) for value in row)
        pdf.drawString(40, y, text[:130])
        y -= 14
    pdf.save()
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    return response


def format_number_id(value):
    if value in [None, '']:
        return ''
    try:
        amount = round(value)
    except TypeError:
        return value
    return f'{amount:,}'.replace(',', '.')


def financial_statement_xlsx(filename, company, title, period_label, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]

    thin_gray = Side(style='thin', color='CBD5E1')
    border = Border(bottom=thin_gray)
    header_fill = PatternFill('solid', fgColor='E2E8F0')

    ws['A1'] = company.name
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = company.legal_name or ''
    ws['A3'] = company.address or ''
    ws['A4'] = f'NPWP: {company.tax_number}' if company.tax_number else ''
    ws['A6'] = title
    ws['A6'].font = Font(bold=True, size=13)
    ws['A7'] = period_label

    ws['A9'] = 'Item'
    ws['B9'] = 'Nilai'
    for cell in ws[9]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.border = border

    row_number = 10
    for row in rows:
        if row.get('is_blank'):
            row_number += 1
            continue
        label_cell = ws.cell(row=row_number, column=1, value=row['label'])
        value_cell = ws.cell(row=row_number, column=2, value=row.get('value') if row.get('has_value') else None)
        label_cell.alignment = Alignment(indent=row.get('indent_level', 0))
        value_cell.alignment = Alignment(horizontal='right')
        value_cell.number_format = '#,##0'
        if row.get('is_bold'):
            label_cell.font = Font(bold=True)
            value_cell.font = Font(bold=True)
        label_cell.border = border
        value_cell.border = border
        row_number += 1

    ws.column_dimensions['A'].width = 48
    ws.column_dimensions['B'].width = 18

    output = BytesIO()
    wb.save(output)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    return response


def financial_statement_pdf(filename, company, title, period_label, rows):
    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        return HttpResponse(
            'PDF export requires WeasyPrint native dependencies on Windows '
            '(GTK/Pango, including libgobject-2.0-0). Excel export is available.',
            status=503,
            content_type='text/plain',
        )

    html = render_to_string(
        'accounting/exports/financial_statement_pdf.html',
        {
            'company': company,
            'title': title,
            'period_label': period_label,
            'rows': [
                {
                    **row,
                    'formatted_value': format_number_id(row.get('value')) if row.get('has_value') else '',
                }
                for row in rows
            ],
        },
    )
    output = BytesIO()
    HTML(string=html).write_pdf(output)
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    return response


def export_financial_statement(request, filename, company, title, period_label, rows):
    export_format = request.GET.get('export')
    if export_format == 'xlsx':
        return financial_statement_xlsx(filename, company, title, period_label, rows)
    if export_format == 'pdf':
        return financial_statement_pdf(filename, company, title, period_label, rows)
    return None
