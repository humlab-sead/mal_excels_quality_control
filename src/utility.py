import pandas as pd


def read_excel_sheet(
    filename: str, sheetname: str, fillna: str | None = None, nrows: int | None = None
) -> pd.DataFrame:
    """Read an Excel sheet and return a DataFrame."""
    xls = pd.ExcelFile(filename)
    data: pd.DataFrame = pd.read_excel(
        xls, sheetname, dtype=str, index_col=None, nrows=nrows
    )
    if fillna is not None:
        data.fillna(fillna, inplace=True)
    return data

