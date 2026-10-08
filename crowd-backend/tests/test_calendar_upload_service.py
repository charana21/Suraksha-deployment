import pandas as pd
from services.calendar_upload_service import CalendarUploadService

def test_normalize_columns_handles_flexible_excel_headers():
    df = pd.DataFrame(
        columns=["Scheduled _Date", "Train Number", "Boarding Count", "Deboarding Count"]
    )

    mapping = {
        "schedule_date": ["schedule_date", "date", "schedule date", "scheduled date"],
        "train_number": ["train_number", "train", "train no", "train number"],
        "boarding_count": ["boarding_count", "boarding", "boarding count"],
        "deboarding_count": ["deboarding_count", "deboarding", "deboarding count"],
    }

    col_map = CalendarUploadService._normalize_columns(df, mapping)

    assert col_map["schedule_date"] == "Scheduled _Date"
    assert col_map["train_number"] == "Train Number"
    assert col_map["boarding_count"] == "Boarding Count"
    assert col_map["deboarding_count"] == "Deboarding Count"


def test_read_upload_dataframe_supports_csv():
    csv_bytes = b"Scheduled Date,Train Number,Boarding Count,Deboarding Count\n2024-01-01,12345,10,2\n"

    df = CalendarUploadService._read_upload_dataframe(csv_bytes, "sample.csv")

    assert list(df.columns) == ["Scheduled Date", "Train Number", "Boarding Count", "Deboarding Count"]
    assert df.iloc[0]["Train Number"] == 12345
