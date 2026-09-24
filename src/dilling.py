import re
from typing import Literal
import pandas as pd

from src.utility import read_excel_sheet


SAMPLE_COLUMNS = [
    "A",
    "EJ",
    "EK",
    "EL",
    "EM",
    "FC",
    "FD",
    "FE",
    "FI",
    "FJ",
    "FL",
    "FM",
    "FN",
]
DATING_COLUMNS: list[str] = ["A", "FW", "FX", "FY"]
COORDINATE_COLUMNS: list[str] = ["A", "FF", "FG", "FH", "FO", "FP"]
ECOCODE_COLUMNS: list[str] = ["A", "EP", "EQ", "ER", "ES", "ET", "EU"]
TAXON_COLUMNS: list[str] = ["A", "B", "C", "D", "E", "F", "G", "H"]
RAW_DATA_SHEETS = [
    "ID216873",
    "Area_6",
    "Area_5",
    "Area_4",
    "Last_Batch",
    "17_0043&57",
    "18_0011",
]

MAIN_SHEET = "Dilling_macro_GIS"


def excel_column_name(n: int) -> str:
    """Convert a zero-indexed column number to an Excel column."""
    letters: str = ""
    while n >= 0:
        n, remainder = divmod(n, 26)
        letters = chr(65 + remainder) + letters
        n -= 1
    return letters



def load_dilling_data(filename: str, sheetname: str) -> pd.DataFrame:
    """Load Dilling data from an Excel file. Return transposed data with Excel column names."""

    raw_data: pd.DataFrame = read_excel_sheet(filename, sheetname, fillna="")

    data = raw_data.transpose().reset_index()

    data.columns = ["category"] + [x for x in data.iloc[0][1:].tolist()]

    data["column"] = [excel_column_name(row) for row in data.index]

    data = data[["column"] + [x for x in data.columns if x not in ("column", "")]]

    return raw_data, data


def extract_taxa_counts(
    data: pd.DataFrame, taxonomy_data: pd.DataFrame
) -> pd.DataFrame:
    """Extract taxa counts from Dilling data and return data in columnar format."""
    taxa_counts: pd.DataFrame = data[(data.column >= "B") & (data.column <= "DE")]

    taxa_counts = taxa_counts[[x for x in taxa_counts.columns if x not in ("column")]]

    taxa_counts = taxa_counts.melt(
        id_vars="category", var_name="sample", value_name="count"
    )

    taxa_counts.columns = ["taxa_name", "sample_name", "count"]
    taxa_counts["count"] = taxa_counts["count"].astype(int)
    taxa_counts = taxa_counts[taxa_counts["count"] > 0]

    taxa_counts = taxa_counts.merge(
        taxonomy_data, left_on="taxa_name", right_on="taxon"
    )

    taxa_counts = taxa_counts.drop(columns=["taxon", "taxa_name"], axis=1)

    taxa_counts = taxa_counts[
        [
            "sample_name",
            "taxon_name",
            "count",
            "genus_uncertainty",
            "species_uncertainty",
            "modifications",
            "element",
        ]
    ]

    return taxa_counts


def is_integer(x: str) -> bool:
    try:
        int(x)
        return True
    except ValueError:
        return False


def is_float(x: str) -> bool:
    try:
        float(x.replace(",", "."))
        return True
    except ValueError:
        return False


def is_digit(x: str) -> bool:
    return x.isdigit()


def extract_other_stuff_count_by_sample(data: pd.DataFrame) -> pd.DataFrame:

    other_counts: pd.DataFrame = data[(data.column >= "DF") & (data.column <= "EI")]
    other_counts = other_counts[
        [x for x in other_counts.columns if x not in ("column")]
    ]
    other_counts = other_counts.melt(
        id_vars="category", var_name="sample", value_name="count"
    )

    other_counts.columns = ["category", "sample_name", "value"]
    other_counts = other_counts[~other_counts.value.isin([""])]
    other_counts = other_counts[["sample_name", "category", "value"]]
    # categories: dict[str, list[str]] = other_counts.groupby(['category']).agg({'value': lambda x: list(set(x))})
    categories_values = (
        other_counts[["category", "value"]].drop_duplicates().reset_index(drop=True)
    )

    categories = (
        other_counts.groupby("category")
        .agg(
            {
                "value": [
                    ("values", lambda x: list(sorted(set(x)))),
                    ("n_count", "count"),
                    ("n_unique", lambda x: len(set(x))),
                    ("n_is_integer", lambda x: sum(is_integer(w) for w in x)),
                    ("n_is_float", lambda x: sum(is_float(w) for w in x)),
                    ("n_zero", lambda x: sum(w == "0" for w in list(set(x)))),
                    (
                        "is_integer",
                        lambda x: len(list(x)) == sum(is_integer(w) for w in x),
                    ),
                ]
            }
        )
        .reset_index()
    )
    categories.columns = [x[0] if not x[1] else x[1] for x in categories.columns.values]

    other_counts = other_counts[~other_counts.value.isin(["0"])]

    category_unique_values = categories.set_index("category", drop=True)[
        "values"
    ].to_dict()

    max_count = max(len(v) for _, v in category_unique_values.items())

    category_unique_values = {
        k: v + [""] * (max_count - len(v)) for k, v in category_unique_values.items()
    }
    category_matrix = pd.DataFrame(category_unique_values)

    return other_counts, categories, categories_values, category_matrix


def extract_data(data: pd.DataFrame, columns: list[str]) -> pd.DataFrame:

    sample_data: pd.DataFrame = (
        data[data.column.isin(columns)]
        .drop("column", axis=1)
        .set_index("category")
        .T.set_index("MALno", drop=True)
        .rename_axis("sample_name")
        .reset_index()
    )

    return sample_data


def listofdicts_to_dictoflists(listofdicts: dict[str, list]) -> dict[str, list]:
    return {k: [d[k] for d in listofdicts] for k in listofdicts[0]}


def decode_taxon(taxon: str) -> dict[str]:
    data: dict[str, str] = {
        "Taxon": taxon,
    }
    for column in ["Genus", "Species"]:
        taxon = taxon.strip()
        if taxon.startswith("cf."):
            data[f"{column} uncertainty"] = "cf."
            taxon = taxon[3:].strip()
        else:
            data[f"{column} uncertainty"] = ""
        data[column] = taxon.split(" ")[0]
        taxon = taxon[len(data[column]) :]
    return data


def decode_taxa(taxa: list[str]) -> dict[str, list[str]]:
    return listofdicts_to_dictoflists([decode_taxon(taxon) for taxon in taxa])


def extract_taxa_and_element_data(filename: str, skip_names: set[str]) -> pd.DataFrame:

    skip_names = skip_names | {"Sum"}
    all_taxa_data: list[pd.DataFrame] = []
    only_taxon: set[str] = set()

    TAXON_COLUMN_NAMES: str = [
        "Taxon",
        "Genus uncertainty",
        "Genus",
        "Species uncertainty",
        "Species",
        "Subspecies",
        "Modifications",
        "Element",
    ]

    for sheetname in RAW_DATA_SHEETS:
        sheet_data: pd.DataFrame = read_excel_sheet(filename, sheetname, fillna="")
        sheet_data.columns = [x.strip() for x in sheet_data.columns]
        column_names: list[str] = sheet_data.columns.tolist()[: len(TAXON_COLUMN_NAMES)]

        if column_names == TAXON_COLUMN_NAMES:
            all_taxa_data.append(sheet_data[TAXON_COLUMN_NAMES])
        elif column_names[0] == "Taxon":
            only_taxon.update(set(sheet_data["Taxon"]))

        else:
            print("skipping sheet", sheetname, "with column names", column_names)
            continue

    data: pd.DataFrame = pd.concat(all_taxa_data, ignore_index=True).reset_index(
        drop=True
    )

    if only_taxon:
        only_taxa: list[str] = list(only_taxon - skip_names - set(data.Taxon))
        decoded_taxa = pd.DataFrame(
            decode_taxa(only_taxa)
            | {"Subspecies": "", "Modifications": "", "Element": ""},
        )
        data = pd.concat([data, decoded_taxa])

    data = data[~data["Taxon"].isin(skip_names)]

    data = data.drop_duplicates(ignore_index=True)

    data["taxon_name"] = data.apply(merge_taxon, axis=1)

    data.columns = [x.lower().replace(" ", "_") for x in data.columns]
    # taxon_mapping = data[["taxon", "taxon_name"]].set_index("taxon_name").to_dict()
    # property_mapping = data[["taxon", "modification", "element"]].set_index("taxon_name").to_dict()
    # taxonymy = data[["taxon", "genus", "species", "subspecies"]].set_index("taxon_name").to_dict()

    return data


def merge_taxon_with_uncertainty(row: pd.Series) -> str:
    genus_uncertainty: str = row["Genus uncertainty"]
    genus: str = row["Genus"]
    species_uncertainty: str = row["Species uncertainty"]
    species: str = row["Species"]
    subspecies: str = row["Subspecies"]

    taxon: str = re.sub(
        " +",
        " ",
        f"{genus_uncertainty} {genus} {species_uncertainty} {species} {subspecies}",
    ).strip()
    return taxon


def merge_taxon(row: pd.Series) -> str:
    genus: str = row["Genus"]
    species: str = row["Species"]
    subspecies: str = row["Subspecies"]
    taxon: str = re.sub(" +", " ", f"{genus} {species} {subspecies}").strip()
    return taxon


if __name__ == "__main__":

    filename: str = "data_dilling_taxa.xlsm"
    sheetname: str = MAIN_SHEET

    raw_data, data = load_dilling_data(filename, sheetname)

    other_counts, other_categories, other_category_values, category_matrix = (
        extract_other_stuff_count_by_sample(data)
    )
    taxonomy_data = extract_taxa_and_element_data(
        filename, set(category_matrix.columns)
    )

    samples: pd.DataFrame = extract_data(data, SAMPLE_COLUMNS + COORDINATE_COLUMNS)
    ecocodes: pd.DataFrame = extract_data(data, ECOCODE_COLUMNS)
    datings: pd.DataFrame = extract_data(data, DATING_COLUMNS)

    taxa_counts: pd.DataFrame = extract_taxa_counts(data, taxonomy_data)
    taxa: pd.DataFrame = (
        taxonomy_data[["taxon_name", "genus", "species", "subspecies"]]
        .drop_duplicates(ignore_index=True)
        .reset_index(drop=True)
        .rename_axis("taxon_id")
    )


    # Write all dataframes to a new Excel file, each dataframe in a seperate sheet
    with pd.ExcelWriter("dilling_prepared_data.xlsx") as writer:
        raw_data.to_excel(writer, sheet_name="raw_data", index=False)
        data.to_excel(writer, sheet_name="data", index=False)
        taxa.to_excel(writer, sheet_name="taxa", index=False)
        samples.to_excel(writer, sheet_name="samples", index=False)
        taxa_counts.to_excel(writer, sheet_name="taxa_counts", index=False)
        datings.to_excel(writer, sheet_name="dating", index=False)
        ecocodes.to_excel(writer, sheet_name="ecocode", index=False)
        other_counts.to_excel(writer, sheet_name="other_counts", index=False)
        other_categories.to_excel(writer, sheet_name="other_categories", index=False)
        other_category_values.to_excel(
            writer, sheet_name="helper_category_values", index=False
        )
        category_matrix.to_excel(
            writer, sheet_name="helper_category_matrix", index=False
        )
        taxonomy_data.to_excel(writer, sheet_name="helper_taxa_data", index=False)

    assert data is not None
