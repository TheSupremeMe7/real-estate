from pathlib import Path

import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
LISTINGS_TAB = "Listings"
LISTING_COLUMNS = [
    "listing_id",
    "title",
    "city",
    "district",
    "neighborhood",
    "property_type",
    "room_count",
    "price",
    "gross_m2",
    "balcony",
    "in_complex",
    "near_metro",
    "description",
    "highlight",
    "listing_url",
    "image_url",
    "status",
]
BOOLEAN_COLUMNS = ["balcony", "in_complex", "near_metro"]


def create_service(credentials_source: Path | dict):
    if isinstance(credentials_source, dict):
        credentials = Credentials.from_service_account_info(
            credentials_source, scopes=[SHEETS_SCOPE]
        )
    else:
        credentials = Credentials.from_service_account_file(
            credentials_source, scopes=[SHEETS_SCOPE]
        )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def ensure_listings_tab(service, spreadsheet_id: str) -> None:
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    titles = {sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])}
    if LISTINGS_TAB not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": LISTINGS_TAB}}}]},
        ).execute()


def upload_initial_listings(
    service,
    spreadsheet_id: str,
    listings: pd.DataFrame,
) -> None:
    values = [LISTING_COLUMNS]
    values.extend(listings[LISTING_COLUMNS].astype(object).where(pd.notna(listings), "").values.tolist())
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{LISTINGS_TAB}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


def load_sheet_listings(
    spreadsheet_id: str,
    credentials_file: Path | dict,
    sample_listings: pd.DataFrame,
) -> pd.DataFrame:
    service = create_service(credentials_file)
    ensure_listings_tab(service, spreadsheet_id)
    response = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{LISTINGS_TAB}!A:Q",
    ).execute()
    rows = response.get("values", [])

    if not rows:
        upload_initial_listings(service, spreadsheet_id, sample_listings)
        return sample_listings.copy()
    if rows[0] != LISTING_COLUMNS:
        if rows[0] == [column for column in LISTING_COLUMNS if column != "highlight"]:
            rows[0].insert(13, "highlight")
            for row in rows[1:]:
                row.insert(13, "")
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{LISTINGS_TAB}!A1",
                valueInputOption="RAW",
                body={"values": rows},
            ).execute()
        else:
            raise ValueError(f"Listings başlıkları şu sırada olmalı: {', '.join(LISTING_COLUMNS)}")

    normalized_rows = [row + [""] * (len(LISTING_COLUMNS) - len(row)) for row in rows[1:]]
    listings = pd.DataFrame(normalized_rows, columns=LISTING_COLUMNS)
    listings = listings[listings["listing_id"].str.strip().ne("")]
    listings["price"] = pd.to_numeric(listings["price"], errors="coerce").fillna(0).astype(int)
    listings["gross_m2"] = pd.to_numeric(listings["gross_m2"], errors="coerce").fillna(0).astype(int)
    for column in BOOLEAN_COLUMNS:
        listings[column] = listings[column].astype(str).str.lower().isin({"true", "1", "evet", "yes"})
    listings = listings[listings["status"].astype(str).str.lower().eq("active")]
    return listings.reset_index(drop=True)
