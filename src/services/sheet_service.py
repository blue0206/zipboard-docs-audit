import json
import gspread
from typing import Dict, List, Literal
from ..core.config import env_settings


def update_google_sheets(
    flattened_data: List[Dict],
    sheet_name: Literal["Articles Catalogue", "Gap Analysis"],
) -> None:
    """
    This function updates the respective Google Sheets with the provided data.

    Args:
        flattened_data: List of dicts representing the data to be updated in Google Sheets.
        sheet_name: Name of the sheet/tab in Google Sheets where the data needs to be updated.

    Notes:
        - This function is only for updating the "Articles Catalogue" and "Gap Analysis" sheets as they have single table.
    """
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

        # Table
        headers = list(flattened_data[0].keys())
        rows.append(headers)

        for row in flattened_data:
            rows.append(list(row.values()))

        worksheet.update(rows)
        print(f"{sheet_name} sheet updated successfully.")
    except Exception as e:
        print(f"Error {sheet_name} sheet: {e}")
        raise e


def update_competitor_analysis_sheet(
    competitor_comparison_data: List[Dict],
    competitor_analysis_insights_data: List[Dict],
) -> None:
    """
    This function updates the "Competitor Analysis" Google Sheet with the provided data.

    Args:
        competitor_comparison_data: List of dicts representing the competitor comparison data to be updated in Google Sheets.
        competitor_analysis_insights_data: List of dicts representing the competitor analysis insights data to be updated in Google Sheets.

    Notes:
        - This function is only for updating the "Competitor Analysis" sheet as it has 2 tables and requires special handling for update.
    """
    try:
        # Auth
        auth_dict = json.loads(env_settings.GOOGLE_CREDS_JSON)
        gc = gspread.service_account_from_dict(auth_dict)
        sheet = gc.open_by_key(env_settings.SHEET_ID)

        # Get or create the worksheet.
        try:
            worksheet = sheet.worksheet("Competitor Analysis")
        except Exception:
            worksheet = sheet.add_worksheet(
                title="Competitor Analysis", rows=1000, cols=20
            )

        worksheet.clear()

        rows: List[List[str]] = []

        # Sheet Title
        rows.append(["Competitor Documentation Analysis - zipBoard"])
        rows.append([])

        # Table 1: Competitor Comparison
        rows.append(["Competitor Comparison"])

        comparison_headers = list(competitor_comparison_data[0].keys())
        rows.append(comparison_headers)

        for row in competitor_comparison_data:
            rows.append(list(row.values()))

        # Spacing
        rows.extend([[], [], []])

        # Table 2: Analysis Insights
        rows.append(["Strategic Insights & Recommendations"])

        insight_headers = list(competitor_analysis_insights_data[0].keys())
        rows.append(insight_headers)

        for row in competitor_analysis_insights_data:
            rows.append(list(row.values()))

        worksheet.update(rows)
        print("Competitor Analysis sheet updated successfully.")
    except Exception as e:
        print(f"Error updating Competitor Analysis sheet: {e}")
        raise e
