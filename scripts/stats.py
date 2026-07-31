import pandas as pd
import glob
import os
from collections import Counter

# inputFolder = "/Users/alessio/Desktop/valpal/data-sep-2023"
# fileList = glob.glob(os.path.join(inputFolder, "*.xlsx"))

outFolder = "/Users/alessio/Desktop/valpal/out-data-sep-2023"
if not os.path.exists(outFolder):
    os.makedirs(outFolder)

fileList = [
    "/Users/alessio/Dropbox/PaVeDa/New database PaVeDa/PaVeDa_Ancient Greek.xlsx",
    "/Users/alessio/Dropbox/PaVeDa/New database PaVeDa/PaVeDa_Classical Armenian_new.xlsx",
    "/Users/alessio/Dropbox/PaVeDa/New database PaVeDa/PaVeDa_Gothic_new.xlsx",
    "/Users/alessio/Dropbox/PaVeDa/New database PaVeDa/PaVeDa_Old English.xlsx",
    "/Users/alessio/Dropbox/PaVeDa/New database PaVeDa/PaVeDa_Old Latin.xlsx"
]

global_mappings = {}
global_majorities = {"R": [], "A": [], "D": [], "I": []}
for f in fileList:
    basename = os.path.basename(f)
    if basename.startswith("~"):
        continue

    print(f"Parsing file: {basename}")

    df = pd.read_excel(f, sheet_name="Alternations")
    ok_cols = df[["R/A/D/I", "Language-specific alternation"]]

    mappings = {}
    majorities = {"R": [], "A": [], "D": [], "I": []}

    for i in ok_cols.index:
        ls_alt = df["Language-specific alternation"][i]
        radi = df["R/A/D/I"][i]

        if pd.isna(ls_alt):
            continue
        if pd.isna(radi):
            continue

        ls_alt = ls_alt.strip()
        radi = radi.strip()
        if ls_alt == "na":
            continue
        if radi == "na":
            continue

        if radi not in ["R", "A", "D", "I"]:
            print("ERR: unknown value {radi}")
            continue

        if ls_alt not in mappings:
            mappings[ls_alt] = Counter()
        mappings[ls_alt].update([radi])

        if ls_alt not in global_mappings:
            global_mappings[ls_alt] = Counter()
        global_mappings[ls_alt].update([radi])

    with open(os.path.join(outFolder, basename + ".tsv"), "w") as fw:
        for key, value in sorted(mappings.items()):
            most_common = mappings[key].most_common(1)[0][0]
            majorities[most_common].append(key)
            fw.write(f"{key}\t{mappings[key]['R']}\t{mappings[key]['A']}\t{mappings[key]['D']}\t{mappings[key]['I']}\n")

    for radi in majorities:
        print(f"Majority {radi}")
        print(majorities[radi])

print("GLOBAL")
with open(os.path.join(outFolder, "GLOBAL.tsv"), "w") as fw:
    for key, value in sorted(global_mappings.items()):
        most_common = global_mappings[key].most_common(1)[0][0]
        global_majorities[most_common].append(key)
        fw.write(f"{key}\t{global_mappings[key]['R']}\t{global_mappings[key]['A']}\t{global_mappings[key]['D']}\t{global_mappings[key]['I']}\n")
for radi in global_majorities:
    print(f"Majority {radi}")
    print(global_majorities[radi])
