import csv
import re
import os

def map_with_suffix(value, mapping):
    # if value is not a string (NaN, int, etc.), return it unchanged
    if not isinstance(value, str):
        return value

    # Match things like "STRING (2)" or just "STRING"
    match = re.match(r"^(.*?)(\s*\(\d+\))?$", value)
    if not match:
        return value  # if it doesn’t match, keep as-is
    
    base, suffix = match.groups()
    base = base.strip()
    suffix = suffix or ""  # keep empty string if no "(n)"
    
    # Replace base if in mapping
    new_base = mapping.get(base, base)
    
    return f"{new_base}{suffix}"

def convertCS(cs):
    cs = re.sub(r" +/ +", "/", cs)
    cs = re.sub(r"(pass)?V.[^ ]+", "", cs)
    cs = cs.strip()
    cs = cs.replace(" ", "+")
    cs = re.sub(r"\++", "+", cs)
    cs = re.sub(r"[0-9]+-", "NP-", cs)
    return cs

def cleanApostrophe(text):
    return re.sub(r"ʹ", "'", text)

def getVerbMeaning(s):
    verbMeaning = re.sub(r"[0-9\(\)\.]+", "", s).strip()
    verbMeaning = re.sub(r"/", "_", verbMeaning)
    verbMeaning = verbMeaning.lower().replace(' ', '-')
    return verbMeaning

def getMeaningOrdinal(rawMeaning):
    # Homonyms are distinguished in the "Meaning" column with a "(N)" suffix,
    # e.g. "PLAY (1)" vs "PLAY (2)"; this mirrors the "-N" suffix on the
    # corresponding Form ID (e.g. "russ1263-play-2") in the CLDF DB.
    match = re.search(r"\((\d+)\)", rawMeaning)
    return match.group(1) if match else "1"

def resolveExistingForm(candidates, ordinal):
    # `candidates` are existing forms sharing the same (meaning, verb text) key.
    # Usually there is only one; when several homonyms happen to have the exact
    # same spelling, use the meaning's "(N)" ordinal to pick the right one.
    if len(candidates) == 1:
        return candidates[0]
    for candidate in candidates:
        if candidate.rsplit("-", 1)[-1] == ordinal:
            return candidate
    return candidates[0]

def findForm(verbMeaning, parametersDB, formsDB, langCode, loopLimit, formMap):
    if verbMeaning not in parametersDB:
        return None
        # print("Meaning not present:", verbMeaning)
        # continue
    i = 1
    thisForm = None
    limitReached = False

    while thisForm is None or thisForm in formsDB or thisForm in formMap.values():
        thisForm = langCode + "-" + verbMeaning + "-" + str(i)
        if thisForm in formsDB:
            if formsDB[thisForm]['Value'] == "no verbal counterpart":
                return thisForm
        i += 1
        if i >= loopLimit:
            limitReached = True

    if limitReached:
        return None
        # print("Limit reached for term:", verbMeaning)
        # continue
    return thisForm

def saveFile(outFolder, fileName, data, labels):
    outFile = os.path.join(outFolder, fileName)

    with open(outFile, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(labels)
        for k in data:
            row = data[k]
            rowToWrite = []
            for l in labels:
                if l in row:
                    rowToWrite.append(row[l])
                else:
                    rowToWrite.append("")
            writer.writerow(rowToWrite)

def addField(labels, data, labelName, after=None, default=""):
    if after:
        i = labels.index(after)
        labels.insert(i + 1, labelName)
    else:
        labels.append(labelName)

    newData = {}
    for k in data:
        record = data[k]
        record[labelName] = default
        newData[k] = record

    return labels, newData

def addToDB(db, data, labels, IDlabel="ID", addID=True, mainKey=None):
    ret = {}

    m = 0
    if addID:
        ids = set()
        for dbID in db:
            ids.add(int(dbID))
        m = max(ids)

    for d in data:
        if IDlabel is not None and IDlabel not in d:
            m += 1
            d[IDlabel] = str(m)
            for l in labels:
                if l not in d:
                    d[l] = ""
        key = d[IDlabel]
        db[key] = d
        if mainKey is not None and mainKey in d:
            ret[d[mainKey]] = key
    return ret

def readFile(filename, skipFirstLine=False, useFirstLine=True, delimiter=",", tableID=None):
    if tableID is None:
        ret = []
    else:
        ret = {}

    labels = []
    firstLine = False
    if skipFirstLine or useFirstLine:
        firstLine = True
    with open(filename, "r", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter, quotechar='"')
        for line in reader:
            if firstLine:
                if useFirstLine and not skipFirstLine:
                    labels = list(map(lambda x: x.strip(), line))
                firstLine = False
                continue

            line = list(map(lambda x: x.strip(), line))
            if len(labels) > 0:
                d = {}
                for i in range(len(labels)):
                    d[labels[i]] = line[i]
                if tableID == None:
                    ret.append(d)
                else:
                    ret[d[tableID]] = d
            else:
                ret.append(line)
    return labels, ret

def sanitizeFrame(frame):
    frame = frame.strip()
    frame = re.sub(' +', ' ', frame)
    return frame

def cleanCell(cellText):
    cellText = str(cellText)
    cellText = cellText.strip()
    if cellText == "na":
        cellText = ""
    if cellText == "_":
        cellText = ""
    return cellText

def cleanText(cellText):
    cellText = cellText.replace("<", "⟨")
    cellText = cellText.replace(">", "⟩")
    return cellText
    
def cleanRole(r):
    r = r.lower()
    r = re.sub(r"\s*/\s*", "-or-", r)
    r = re.sub(r"\s+", "-", r)
    r = re.sub(r"\.", "", r)
    r = re.sub(r"-[0-9]$", "", r) # BAD, but dresser-2
    r = re.sub(r"[\(\)]", "", r)
    return r

def mergeData(db, labels, df, fieldName, okFKs=None, FKName=None):
    added = 0
    newRecords = []
    record_ids = db.keys()
    newKeys = set()
    for index in df.index:
        m = {}
        thisID = df["ID"][index]
        if FKName and okFKs and not df[FKName][index] in okFKs:
                print(f"ERR: {fieldName} ID {thisID} has wrong FK {df[FKName][index]}")
                continue
        if thisID in record_ids:
            print(f"ERR: {fieldName} ID {thisID} already present in ValPaL")
            continue
        if thisID in newKeys:
            print(f"ERR: duplicated {fieldName} ID {thisID}")
            continue
        newKeys.add(thisID)
        for k in labels:
            try:
                m[k] = df[k][index]
            except KeyError:
                m[k] = ""
        newRecords.append(m)
        added += 1
    addToDB(db, newRecords, labels, addID=False)
    return added
