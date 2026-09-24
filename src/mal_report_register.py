import os
import re
from typing import Literal
import pandas as pd
from sqlalchemy.engine.base import Engine

from src.utility import read_excel_sheet
from sqlalchemy import create_engine


def load_report_register(filename: str) -> dict[str, pd.DataFrame]:

    reports: pd.DataFrame = read_excel_sheet(filename, "MAL-reports", fillna="")
    authors: pd.DataFrame = read_excel_sheet(filename, "Authors", fillna="")

    reports["authors"] = (
        reports.authors.str.replace("\(.*\)", "", regex=True)
        .str.replace("[\.\&\s]", ",", regex=True)
        .str.replace(",+", ",", regex=True)
        .str.strip(",")
        .str.strip()
        .str.upper()
    )

    authors["fullname"] = authors["first_name"] + " " + authors["surname"]

    initials_map: dict[str,str] = authors.set_index('initials')['fullname'].to_dict()

    reports["authors_fullname"] = reports["authors"].str.split(",").apply(lambda x: [initials_map.get(i, i) for i in x]).str.join(", ")

    reports = reports.drop(columns=[c for c in reports.columns if re.match(r"Unnamed: \d+", c)])
    
    return {"reports": reports, "authors": authors}


if __name__ == "__main__":

    filename: str = "./mal_report_register_20240116_prepped.xlsx"

    data: dict[str, pd.DataFrame] = load_report_register(filename)

    uri: str = open(f"{os.environ['HOME']}/vault/uri@sead_staging@staging_cluster", "r", encoding="utf8").read().strip()

    engine: Engine =  create_engine(uri)
    data["reports"].to_sql('temp_mal_report_register', con=engine, if_exists='replace', index=False)
    data["authors"].to_sql('temp_mal_report_register_authors', con=engine, if_exists='replace', index=False)
    engine.dispose()

    assert data is not None
