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
    "net_m2",
    "building_age",
    "floor",
    "total_floors",
    "bathroom_count",
    "heating",
    "facade",
    "balcony",
    "in_complex",
    "near_metro",
    "furnished",
    "elevator",
    "parking",
    "security",
    "view",
    "outdoor_space",
    "kitchen_type",
    "deed_status",
    "credit_eligible",
    "usage_status",
    "dues",
    "amenities",
    "nearby_places",
    "technical_details",
    "building_features",
    "description",
    "highlight",
    "listing_url",
    "image_url",
    "status",
]
BOOLEAN_COLUMNS = [
    "balcony", "in_complex", "near_metro", "furnished", "elevator",
    "credit_eligible",
]
NUMERIC_COLUMNS = [
    "price", "gross_m2", "net_m2", "building_age", "total_floors",
    "bathroom_count", "dues",
]


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
        range=f"{LISTINGS_TAB}!A:AZ",
    ).execute()
    rows = response.get("values", [])

    if not rows:
        upload_initial_listings(service, spreadsheet_id, sample_listings)
        return sample_listings.copy()
    headers = rows[0]
    essential = {"listing_id", "title", "price", "description", "status"}
    if not essential.issubset(headers):
        raise ValueError(f"Listings zorunlu başlıkları eksik: {', '.join(sorted(essential - set(headers)))}")
    source_rows = [row + [""] * (len(headers) - len(row)) for row in rows[1:]]
    source = pd.DataFrame(source_rows, columns=headers)
    for column in LISTING_COLUMNS:
        if column not in source.columns:
            source[column] = ""
    listings = source[LISTING_COLUMNS].copy()
    if headers != LISTING_COLUMNS:
        upload_initial_listings(service, spreadsheet_id, listings)
    listings = listings[listings["listing_id"].str.strip().ne("")]
    for column in NUMERIC_COLUMNS:
        listings[column] = pd.to_numeric(listings[column], errors="coerce").fillna(0).astype(int)
    for column in BOOLEAN_COLUMNS:
        listings[column] = listings[column].astype(str).str.lower().isin({"true", "1", "evet", "yes"})
    listings = listings[listings["status"].astype(str).str.lower().eq("active")]
    return listings.reset_index(drop=True)
