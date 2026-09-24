# Loop over all XLS files in all subolders in data folder
from collections import defaultdict
import os
from typing import Any, Generator
from loguru import logger
import pandas as pd


def list_files(
    path: str = "data", extensions: list[str] = None
) -> Generator[tuple[str, str], Any, None]:
    for folder, _, files in os.walk(path):
        for filename in files:
            if extensions and not any(filename.endswith(ext) for ext in extensions):
                continue
            yield (folder, filename)


data_folder: str = "data"


def process_files(
    data_folder: str, extensions: list[str] = None
) -> Generator[tuple[str, str, str, list[str], pd.DataFrame], Any, None]:

    for folder, filename in list_files(data_folder, ["xls", "xlsx"]):

        if folder == data_folder:
            continue

        parts: list[str] = folder.strip(data_folder + "/").split("/")

        if any(x in parts for x in ["help", "helps", "Help", "Helps"]):
            logger.info(f"SKIPPED (help): {os.path.join(folder, filename)}")
            continue

        if any(p.startswith("Rådata") for p in parts):
            logger.info(f"SKIPPED (rådata): {os.path.join(folder, filename)}")
            continue

        # if len(parts) != 2:
        #     if not filename.lower().startswith('data') and not filename.lower().startswith('metadata'):
        #         logger.error(f"SKIPPED (parts): {os.path.join(folder, filename)}")
        #         continue

        if filename.lower().startswith("dates"):
            logger.info(f"SKIPPED (dates): {os.path.join(folder, filename)}")
            continue

        if "metadata" in filename.lower():
            logger.info(f"SKIPPED (metadata): {os.path.join(folder, filename)}")
            continue

        try:
            xls = pd.ExcelFile(os.path.join(folder, filename))

            for sheet_name in xls.sheet_names:

                if sheet_name in ("n.d", "n.d.", "no data"):
                    logger.error(f"SKIPPED (no data): {os.path.join(folder, filename)}")
                    continue

                df: pd.DataFrame = load_data(xls, sheet_name)

                if df is None:
                    logger.info(f"SKIPPED (empty): {os.path.join(folder, filename)}")
                    continue

                if len(df.columns) > 100:
                    logger.error(
                        f"SKIPPED (too many columns): {os.path.join(folder, filename)}"
                    )
                    continue

                column_names: list[str] = (
                    df.columns.astype(str)
                    .str.replace("\t", " ")
                    .str.replace("\n", "")
                    .tolist()
                )
                yield (folder, filename, sheet_name, column_names, df)

        except Exception as ex:
            logger.error(f"FAILED: {os.path.join(folder, filename) + ' ' + str(ex)}")
            continue


def load_data(xls: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    df: pd.DataFrame = pd.read_excel(xls, sheet_name)

    if len(df) == 0:
        return None

    if len(df.columns) > 0:

        if df.columns[0].startswith("Unnamed"):
            if len(df) > 2:
                for i in (1, 2):
                    if df.iloc[i][0] == "Taxon":
                        # do a cellwise merge of df.columns and the first two rows
                        columns: list[str] = [
                            "" if x.startswith("Unnamed") else x for x in df.columns
                        ]
                        df.columns = [
                            (" ".join([str(c), str(a), str(b)])).strip()
                            for c, a, b in zip(
                                columns, df.iloc[0].fillna(""), df.iloc[1].fillna("")
                            )
                        ]
                        df = df.iloc[i:]
                        break

        elif df.columns[0].startswith("Område:"):
            df = pd.read_excel(xls, sheet_name, skiprows=1)

        elif df.columns[0] == "Projektuppgifter":
            df = df[df.columns[2:]]

    return df


def store_excel_sheet_columns() -> None:

    unique_column_names: dict[str, int] = defaultdict(int)
    with open("excel_sheet_columns.txt", "w") as f:
        for folder, filename, sheet_name, column_names, df in process_files(
            data_folder, ["xls", "xlsx"]
        ):
            f.write("\t".join([folder, filename, sheet_name] + column_names) + "\n")

            if not 'Taxon' in column_names[0]:
                for column in column_names:
                    unique_column_names[column] += 1

    column_names_of_interest = [x[0] for x in sorted([
            (k, v)
            for k, v in unique_column_names.items()
            if v > 5
            # and not k.startswith("Unnamed")
            # and not k.startswith("Sample")
            # and not k.startswith("Fält")
            # and not k.startswith("Batch")
            # and not k.startswith("Anm")
            # and not k.startswith("LABnr")
            # and not k.startswith("Lab. not.")
            # and not k.startswith("Lab.löp")
            # and not k.startswith("Labnot")
            # and not k.isdigit()
        ], key=lambda x: x[1], reverse=True)]


    with open("unique_column_names.txt", "w") as f:
        f.write(
            "\n".join(column_names_of_interest )
        )


if __name__ == "__main__":
    store_excel_sheet_columns()
