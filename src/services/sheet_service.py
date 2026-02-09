import json
import gspread
from typing import Dict, List, Literal
from gspread.utils import ValueInputOption
from ..core.config import env_settings
from gspread_formatting import (
    set_frozen,
    set_column_width,
    set_row_height,
    format_cell_range,
    CellFormat,
    TextFormat,
)

HEADER_FORMAT = CellFormat(
    backgroundColor={"red": 0.93, "green": 0.94, "blue": 0.96},
    textFormat=TextFormat(bold=True, fontSize=13),
    horizontalAlignment="CENTER",
    wrapStrategy="WRAP",
)

TITLE_FORMAT = CellFormat(
    textFormat=TextFormat(bold=True, fontSize=16),
    horizontalAlignment="CENTER",
    wrapStrategy="WRAP",
)

BODY_FORMAT = CellFormat(
    verticalAlignment="MIDDLE", wrapStrategy="WRAP"
)

COLUMN_WIDTHS_ARTICLES_CATALOGUE = {
    "A": 132,
    "B": 250,
    "C": 150,
    "D": 150,
    "E": 240,
    "F": 180,
    "G": 440,
    "H": 500,
    "I": 150,
    "J": 150,
    "K": 150,
    "L": 150,
    "M": 150,
    "N": 150,
    "O": 150,
}

COLUMN_WIDTHS_GAP_ANALYSIS = {
    "A": 108,
    "B": 280,
    "C": 380,
    "D": 208,
    "E": 150,
    "F": 108,
    "G": 150,
    "H": 480,
    "I": 520,
    "J": 280,
    "K": 350,
    "L": 350,
}

COLUMN_WIDTHS_COMP_COMPARISON = {
    "A": 150,
    "B": 240,
    "C": 380,
    "D": 380,
    "E": 165,
    "F": 280,
    "G": 165,
    "H": 220,
    "I": 140,
}

COLUMN_WIDTHS_INSIGHTS = {
    "A": 150,
    "B": 280,
    "C": 380,
    "D": 380,
    "E": 150,
    "F": 380,
    "G": 150,
}


def update_google_sheets(
    flattened_data: List[Dict],
    sheet_name: Literal[
        "Articles Catalogue",
        "Gap Analysis",
        "Competitor Comparison",
        "Strategic Insights & Recommendations",
        "test sheet"
    ],
) -> None:
    """
    This function updates the respective Google Sheets with the provided data.

    Args:
        flattened_data: List of dicts representing the data to be updated in Google Sheets.
        sheet_name: Name of the sheet/tab in Google Sheets where the data needs to be updated.

    Notes:
        - This function is only for updating the "Articles Catalogue" and "Gap Analysis" sheets as they have single table.
    """

    if len(flattened_data) == 0:
        print(f"No data available for {sheet_name}, nothing updated")
        return

    try:
        # Auth
        auth_dict = json.loads(env_settings.GOOGLE_CREDS_JSON)
        gc = gspread.service_account_from_dict(auth_dict)
        sheet = gc.open_by_key(env_settings.SHEET_ID)

        # Get or create the worksheet.
        try:
            worksheet = sheet.worksheet(sheet_name)
        except Exception:
            worksheet = sheet.add_worksheet(title=sheet_name, rows=1000, cols=20)

        worksheet.clear()

        rows: List[List[str]] = []

        # Sheet Title
        rows.append([sheet_name])
        format_cell_range(worksheet, "A1:Z1", TITLE_FORMAT)
        set_row_height(worksheet, "1", 50)

        # Table
        headers = list(flattened_data[0].keys())
        rows.append(headers)

        for row in flattened_data:
            rows.append(list(row.values()))

        # Style header
        format_cell_range(worksheet, "A2:Z2", HEADER_FORMAT)
        set_row_height(worksheet, "2", 45)
        set_frozen(worksheet, rows=2)

        # Style body
        format_cell_range(worksheet, "A3: Z1000", BODY_FORMAT)
        set_row_height(worksheet, "3:1000", 140)

        # Set col width.
        if sheet_name == "Articles Catalogue":
            update_worksheet_cols(worksheet, COLUMN_WIDTHS_ARTICLES_CATALOGUE)
        elif sheet_name == "Gap Analysis":
            update_worksheet_cols(worksheet, COLUMN_WIDTHS_GAP_ANALYSIS)
        elif sheet_name == "Competitor Comparison":
            update_worksheet_cols(worksheet, COLUMN_WIDTHS_COMP_COMPARISON)
        elif sheet_name == "Strategic Insights & Recommendations":
            update_worksheet_cols(worksheet, COLUMN_WIDTHS_INSIGHTS)
        else:
            update_worksheet_cols(worksheet, COLUMN_WIDTHS_ARTICLES_CATALOGUE)

        worksheet.update(rows, value_input_option=ValueInputOption.user_entered)
        print(f"{sheet_name} sheet updated successfully.")
    except Exception as e:
        print(f"Error {sheet_name} sheet: {e}")
        raise e


def update_worksheet_cols(
    worksheet: gspread.Worksheet, col_widths: Dict[str, int]
) -> None:
    """
    This function applies accepts a worksheet instance and column widths rules
    and applies them on the sheet.
    """

    for col, width in col_widths.items():
        set_column_width(worksheet, col, width)
