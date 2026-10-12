"""Presentation-only geotechnical handoff; calculation provenance stays in the notebook."""
from pathlib import Path

from .output_labels import table_reference


def handoff_tables(data, result, ground):
    """Share the exact final rows between the notebook preview and Excel export."""
    tip = result.get('tip_elevation_ft') if result and data['selected'] else None
    # Required embedment in the calculation is before optional tip rounding.
    # The handoff length must reach the adopted (possibly rounded) elevation.
    embedment = ground - tip if ground is not None and tip is not None else None
    return [
        dict(reference='handoff_section', columns=[('item', 'Pile information'), ('value', 'Value')],
             rows=data['section']),
        dict(reference='handoff_tip', columns=[('criterion', 'Controlling criterion'),
             ('embedment_ft', 'Final embedment below design ground / scour (ft)'),
             ('tip_elevation_ft', 'Final tip elevation (ft)')],
             rows=[dict(criterion=result['controlling_criterion'] if tip is not None else 'Not calculated',
                        embedment_ft=embedment, tip_elevation_ft=tip)]),
        dict(reference='handoff_loads', columns=[('load', 'Pile-head design load'), ('fdl_tons', 'Final FDL (short tons)')],
             rows=[dict(load=r['load'], fdl_tons=r['short_tons']) for r in data['loads']]),
    ]


def handoff_qualification(data, result):
    """Keep an incomplete calculation from being presented as a final design."""
    if not data['selected'] or not result or result.get('tip_elevation_ft') is None:
        return 'Minimum tip not calculated.'
    if not result['comparison_complete']:
        return 'Minimum-tip comparison incomplete; reported values use available criteria only.'
    return ''


def write_handoff_xlsx(path, data, result, ground, notes=''):
    """Write a standalone, values-only workbook using the notebook's Excel dependency."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.page import PageMargins

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Geotech handoff'
    sheet.sheet_view.showGridLines = False
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.sheet_properties.outlinePr.summaryRight = False
    sheet.sheet_properties.tabColor = '213649'
    for col, width in [('A', 43), ('B', 40), ('C', 30)]:
        sheet.column_dimensions[col].width = width

    navy, ink, pale, line = '213649', '243746', 'EAF1F6', 'DDE3E8'

    def cell(row, col, value, *, bold=False, fill=None, color=ink, size=11, number_format=None):
        target = sheet.cell(row, col, 'Unavailable' if value is None else value)
        # User-entered section descriptions and notes are text, never Excel formulas.
        if isinstance(target.value, str):
            target.data_type = 's'
        target.font = Font(name='Calibri', size=size, bold=bold, color=color)
        target.alignment = Alignment(horizontal='right' if isinstance(value, (int, float)) else 'left',
                                     vertical='center', wrap_text=True)
        if fill:
            target.fill = PatternFill('solid', fgColor=fill)
        if number_format:
            target.number_format = number_format
        return target

    def wide_row(row, value, **style):
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
        cell(row, 1, value, **style)

    wide_row(1, 'Geotechnical handoff', bold=True, fill=navy, color='FFFFFF', size=20)
    sheet.row_dimensions[1].height = 40
    row = 3
    qualification = handoff_qualification(data, result)
    for table in handoff_tables(data, result, ground):
        wide_row(row, table_reference(table['reference']), bold=True, size=13)
        sheet.row_dimensions[row].height = 28
        row += 1
        for col, (_, label) in enumerate(table['columns'], 1):
            cell(row, col, label, bold=True, fill=pale)
        if len(table['columns']) == 2:
            sheet.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
        sheet.row_dimensions[row].height = 42 if len(table['columns']) == 3 else 27
        row += 1
        for index, values in enumerate(table['rows']):
            for col, (key, _) in enumerate(table['columns'], 1):
                value = values[key]
                fmt = ('0' if key == 'value' and isinstance(value, int) else '#,##0.000;-#,##0.000;0.000')
                target = cell(row, col, value, fill='F5F8FA' if index % 2 else 'FFFFFF',
                              number_format=fmt if isinstance(value, (int, float)) else None)
                target.border = Border(bottom=Side(style='hair', color=line))
            if len(table['columns']) == 2:
                sheet.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
            # Criterion ties and section descriptions need room at normal zoom.
            longest = max(len(str(v or '')) for v in values.values())
            sheet.row_dimensions[row].height = max(29, 15 * ((longest + 39) // 40) + 10)
            row += 1
        if table['reference'] == 'handoff_tip' and qualification:
            wide_row(row, qualification, color='805600', fill='FFF4D6')
            sheet.row_dimensions[row].height = 31
            row += 1
        if table['reference'] == 'handoff_loads':
            wide_row(row, 'FDL = factored design load. Compression and uplift are positive magnitudes. 1 short ton = 2 kip.', size=10)
            sheet.row_dimensions[row].height = 28
            row += 1
        row += 1

    if notes.strip():
        wide_row(row, 'Project notes', bold=True, size=13)
        sheet.row_dimensions[row].height = 28
        row += 1
        # Split long notes into ordinary rows so printing can continue on the next page.
        import textwrap
        for paragraph in notes.strip().splitlines():
            for part in textwrap.wrap(paragraph, width=110) or ['']:
                wide_row(row, part)
                sheet.row_dimensions[row].height = 30
                row += 1

    sheet.freeze_panes = 'B5'
    sheet.print_options.horizontalCentered = True
    sheet.page_setup.orientation = 'landscape'
    sheet.page_setup.paperSize = sheet.PAPERSIZE_LETTER
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.page_margins = PageMargins(left=.3, right=.3, top=.35, bottom=.35, header=.15, footer=.15)
    sheet.print_area = f'A1:C{row - 1}'
    sheet.oddFooter.center.text = 'Page &P of &N'
    path = Path(path)
    workbook.save(path)
    return path
