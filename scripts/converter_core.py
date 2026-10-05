import glob
import json
import os
import pprint
import re
import shutil
from copy import deepcopy

import pandas as pd

try:
    from .utils import (
        addField,
        addToDB,
        cleanApostrophe,
        cleanCell,
        cleanRole,
        cleanText,
        convertCS,
        findForm,
        getMeaningOrdinal,
        getVerbMeaning,
        map_with_suffix,
        mergeData,
        readFile,
        resolveExistingForm,
        sanitizeFrame,
        saveFile,
    )
except ImportError:  # pragma: no cover - standalone script compatibility
    from utils import (
        addField,
        addToDB,
        cleanApostrophe,
        cleanCell,
        cleanRole,
        cleanText,
        convertCS,
        findForm,
        getMeaningOrdinal,
        getVerbMeaning,
        map_with_suffix,
        mergeData,
        readFile,
        resolveExistingForm,
        sanitizeFrame,
        saveFile,
    )


DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config(config_path=None):
    config_path = config_path or DEFAULT_CONFIG_PATH
    with open(config_path) as f:
        return json.load(f)


def normalize_config(config):
    config_data = deepcopy(config)
    base_folder = config_data.get("base_folder", "")

    for key in ("input_folder", "output_folder", "excel_folder", "alt_classes_folder"):
        value = config_data.get(key)
        if isinstance(value, str) and "$BASE" in value:
            config_data[key] = value.replace("$BASE", base_folder)

    return config_data


def resolve_languages_to_run(config_data, languages_to_run=None):
    available_languages = config_data["languages"]
    possible_sets = dict(config_data.get("sets", {}))
    possible_sets["all"] = list(available_languages.keys())

    requested = list(languages_to_run if languages_to_run is not None else config_data.get("languages_to_run", []))
    if not requested:
        return list(available_languages.keys())

    resolved = []
    for item in requested:
        if item in possible_sets:
            resolved.extend(possible_sets[item])
        else:
            resolved.append(item)

    deduped = []
    seen = set()
    for item in resolved:
        if item not in seen:
            deduped.append(item)
            seen.add(item)

    return deduped


def build_runtime_config(
    base_config,
    *,
    input_folder=None,
    output_folder=None,
    excel_folder=None,
    languages=None,
    languages_to_run=None,
):
    config_data = normalize_config(base_config)
    if input_folder is not None:
        config_data["input_folder"] = input_folder
    if output_folder is not None:
        config_data["output_folder"] = output_folder
    if excel_folder is not None:
        config_data["excel_folder"] = excel_folder
        if config_data.get("perform_alt_classes"):
            config_data["alt_classes_folder"] = os.path.join(excel_folder, "alt-classes")
    if languages is not None:
        config_data["languages"] = deepcopy(languages)
    if languages_to_run is not None:
        config_data["languages_to_run"] = list(languages_to_run)
    return config_data


def run_conversion(config):
    config_data = normalize_config(config)

    frame_mappings = config_data["frame_map"]
    input_folder = config_data["input_folder"]
    output_folder = config_data["output_folder"]
    excel_folder = config_data["excel_folder"]

    alt_folder = None
    if config_data.get("perform_alt_classes") and config_data.get("alt_classes_folder"):
        alt_folder = config_data["alt_classes_folder"]

    new_mm_file = config_data["new_mm_file"]
    radi_map = config_data["radi_map"]
    new_languages = config_data["languages"]
    languages_to_run = resolve_languages_to_run(config_data)
    possible_sets = dict(config_data.get("sets", {}))
    possible_sets["all"] = list(new_languages.keys())
    loop_limit = config_data["loop_limit"]
    error_reporting = config_data["error_reporting"]
    debug = config_data["debug"]
    show_stats = config_data["show_stats"]

    unknown_languages = [lang for lang in languages_to_run if lang not in new_languages]
    if unknown_languages:
        raise ValueError(f"Unknown languages requested: {', '.join(unknown_languages)}")

    statistics = {
        "new_meanings": 0,
        "new_microroles": 0,
        "langs": {},
        "_total": {},
        "updated_langs": {},
        "available_sets": list(possible_sets.keys()),
        "languages_to_run": languages_to_run,
    }

    os.makedirs(output_folder, exist_ok=True)

    for file in os.listdir(input_folder):
        input_file = os.path.join(input_folder, file)
        if os.path.isfile(input_file):
            output_file = os.path.join(output_folder, file)
            if os.path.exists(output_file):
                os.remove(output_file)

    languages_labels, languages_db = readFile(os.path.join(input_folder, "languages.csv"), tableID="ID")
    forms_labels, forms_db = readFile(os.path.join(input_folder, "forms.csv"), tableID="ID")
    frames_labels, frames_db = readFile(os.path.join(input_folder, "coding-frames.csv"), tableID="ID")
    alternations_labels, alternations_db = readFile(os.path.join(input_folder, "alternations.csv"), tableID="ID")
    alternation_values_labels, alternation_values_db = readFile(
        os.path.join(input_folder, "alternation-values.csv"), tableID="ID"
    )
    coding_sets_labels, coding_sets_db = readFile(os.path.join(input_folder, "coding-sets.csv"), tableID="ID")
    coding_frame_index_numbers_labels, coding_frame_index_numbers_db = readFile(
        os.path.join(input_folder, "coding-frame-index-numbers.csv"), tableID="ID"
    )
    examples_labels, examples_db = readFile(os.path.join(input_folder, "examples.csv"), tableID="ID")
    coding_frame_examples_labels, coding_frame_examples_db = readFile(
        os.path.join(input_folder, "coding-frame-examples.csv"), tableID="ID"
    )
    form_coding_frame_microroles_labels, form_coding_frame_microroles_db = readFile(
        os.path.join(input_folder, "form-coding-frame-microroles.csv"), tableID="ID"
    )
    parameters_labels, parameters_db = readFile(os.path.join(input_folder, "parameters.csv"), tableID="ID")
    microroles_labels, microroles_db = readFile(os.path.join(input_folder, "microroles.csv"), tableID="ID")

    alternations_labels, alternations_db = addField(
        alternations_labels, alternations_db, "Radi", after="Language_ID"
    )
    examples_labels, examples_db = addField(examples_labels, examples_db, "Link", after="Translated_Text")
    examples_labels, examples_db = addField(examples_labels, examples_db, "SourceText", after="Source")

    new_mm_file_name = os.path.join(excel_folder, new_mm_file)

    df_meanings = pd.read_excel(new_mm_file_name, sheet_name="meanings")
    df_meanings = df_meanings.fillna("")
    df_meanings["label_for_url"] = df_meanings.loc[:, "ID"]
    statistics["new_meanings"] += mergeData(parameters_db, parameters_labels, df_meanings, "meaning")

    df_microroles = pd.read_excel(new_mm_file_name, sheet_name="microroles")
    df_microroles = df_microroles.fillna("")
    df_microroles["Name_For_URL"] = df_microroles.loc[:, "ID"]
    statistics["new_microroles"] += mergeData(
        microroles_db,
        microroles_labels,
        df_microroles,
        "microrole",
        okFKs=parameters_db.keys(),
        FKName="Parameter_ID",
    )

    microroles = {}
    for record_id in microroles_db:
        parameter_id = microroles_db[record_id]["Parameter_ID"]
        clean_record_id = cleanRole(record_id)
        microroles[f"{clean_record_id}-{parameter_id}"] = clean_record_id

    statistics["_total"] = {
        "basic_coding_frames": 0,
        "derived_coding_frames": 0,
        "alternations": 0,
        "coding_sets": 0,
        "coding_frame_index_numbers": 0,
        "microroles": 0,
        "examples": 0,
        "alternation_classes": {"total": 0, "no_classes": 0},
    }
    for class_name in ["R", "A", "D", "I"]:
        statistics["_total"]["alternation_classes"][class_name] = 0

    for excel_file_name in languages_to_run:
        statistics["langs"][excel_file_name] = {
            "basic_coding_frames": 0,
            "derived_coding_frames": 0,
            "alternations": 0,
            "coding_sets": 0,
            "coding_frame_index_numbers": 0,
            "microroles": 0,
            "examples": 0,
            "alternation_classes": {"total": 0, "no_classes": 0},
        }
        for class_name in ["R", "A", "D", "I"]:
            statistics["langs"][excel_file_name]["alternation_classes"][class_name] = 0

        file_name = os.path.join(excel_folder, excel_file_name)
        lang_code = new_languages[excel_file_name]["ID"]

        language_to_update = False
        if new_languages[excel_file_name]["ID"] in languages_db:
            language_to_update = True
            print(f"\n### {new_languages[excel_file_name]['Name']} (update)\n")
        else:
            print(f"\n### {new_languages[excel_file_name]['Name']}\n")

        if language_to_update:
            if debug:
                print("Languages needs to be updated:", new_languages[excel_file_name])
        else:
            addToDB(languages_db, [new_languages[excel_file_name]], languages_labels, addID=False)
            if debug:
                print("Added to languages:", new_languages[excel_file_name])

        df_basic = pd.read_excel(file_name, sheet_name="Basic usages")
        df_alternations = pd.read_excel(file_name, sheet_name="Alternations")
        df_mr = pd.read_excel(file_name, sheet_name="Meanings and microroles")
        df_examples = pd.read_excel(file_name, sheet_name="Examples")

        df_basic["Meaning"] = df_basic["Meaning"].apply(lambda x: map_with_suffix(x, frame_mappings))
        df_alternations["Meaning"] = df_alternations["Meaning"].apply(lambda x: map_with_suffix(x, frame_mappings))
        df_mr["Meaning"] = df_mr["Meaning"].apply(lambda x: map_with_suffix(x, frame_mappings))
        df_examples["Meaning"] = df_examples["Meaning"].apply(lambda x: map_with_suffix(x, frame_mappings))

        needs_alt_deletion = False
        try:
            df_alternations_remove = pd.read_excel(file_name, sheet_name="Alternations_deleted")
            needs_alt_deletion = True
        except Exception:
            pass

        if needs_alt_deletion:
            df_alternations_remove = df_alternations_remove.fillna("")

            form_map_for_delete = {}
            for index in forms_db:
                if forms_db[index]["Language_ID"] == lang_code:
                    frame = forms_db[index]["Parameter_ID"]
                    if frame not in form_map_for_delete:
                        form_map_for_delete[frame] = []
                    form_map_for_delete[frame].append(forms_db[index])

            alternation_map_for_delete = {}
            for index in alternations_db:
                if alternations_db[index]["Language_ID"] == lang_code:
                    alt_name = alternations_db[index]["Name"]
                    if alt_name not in alternation_map_for_delete:
                        alternation_map_for_delete[alt_name] = []
                    alternation_map_for_delete[alt_name].append(alternations_db[index])

            for index in df_alternations_remove.index:
                raw_meaning = sanitizeFrame(df_alternations_remove["Meaning"][index])
                if not raw_meaning:
                    continue

                verb_meaning = getVerbMeaning(raw_meaning)
                if verb_meaning not in form_map_for_delete:
                    print(f"ERR: meaning not found (delete) [row {index + 2}]:", verb_meaning)
                    continue

                found_form = None
                for form in form_map_for_delete[verb_meaning]:
                    if cleanApostrophe(form["Form"]) == cleanApostrophe(df_alternations_remove["Verb"][index]):
                        found_form = form
                        break
                if not found_form:
                    print(f"ERR: verb not found (delete) [row {index + 2}]:", df_alternations_remove["Verb"][index])
                    continue

                ls_alt = df_alternations_remove["Language-specific alternation"][index]
                if ls_alt not in alternation_map_for_delete:
                    print(f"ERR: alternation not found (delete) [row {index + 2}]:", ls_alt)
                    continue
                if len(alternation_map_for_delete[ls_alt]) > 1:
                    print(f"ERR: Too many alternations (delete) [row {index + 2}]:", ls_alt)
                    continue

                form_id = found_form["ID"]
                alt_id = alternation_map_for_delete[ls_alt][0]["ID"]

                found = None
                for alt_value_index in alternation_values_db:
                    this_form_id = alternation_values_db[alt_value_index]["Form_ID"]
                    this_alt_id = alternation_values_db[alt_value_index]["Alternation_ID"]
                    if this_form_id == form_id and this_alt_id == alt_id:
                        found = alt_value_index
                        break

                if found is None:
                    print(f"ERR: Alternation not found (delete) [row {index + 2}]:", form_id, alt_id)
                    continue

                del alternation_values_db[found]

        for dataframe in [df_basic, df_alternations, df_mr, df_examples]:
            dataframe.columns = dataframe.columns.str.strip()

        rename_columns = config_data["rename_columns"]
        df_alternations = df_alternations.rename(columns=rename_columns["a"])
        df_examples = df_examples.rename(columns=rename_columns["e"])
        df_mr = df_mr.rename(columns=rename_columns["mr"])

        df_alternations = df_alternations.fillna("")
        df_basic = df_basic.fillna("")
        df_mr = df_mr.fillna("")
        df_examples = df_examples.fillna("")

        frames = set()
        for index in df_basic.index:
            frame = sanitizeFrame(df_basic["Coding frame"][index])
            if frame:
                frames.add(frame)

        statistics["langs"][excel_file_name]["basic_coding_frames"] = len(frames)
        statistics["_total"]["basic_coding_frames"] += len(frames)

        alt_frames = set()
        alt_set = {}
        for index in df_alternations.index:
            frame = sanitizeFrame(df_alternations["Derived coding frame"][index])
            lsa = cleanCell(df_alternations["Language-specific alternation"][index])
            if not lsa:
                continue

            alt_type = df_alternations["Type"][index]
            if alt_type:
                alt_type = alt_type[0].upper() + alt_type[1:]

            alt_frames.add(frame)
            radi_value = df_alternations["R/A/D/I"][index]
            if radi_value in radi_map:
                radi_value = radi_map[radi_value]
            else:
                radi_value = ""

            statistics["langs"][excel_file_name]["alternation_classes"]["total"] += 1
            statistics["_total"]["alternation_classes"]["total"] += 1
            if radi_value:
                statistics["langs"][excel_file_name]["alternation_classes"][radi_value[0]] += 1
                statistics["_total"]["alternation_classes"][radi_value[0]] += 1
            else:
                statistics["langs"][excel_file_name]["alternation_classes"]["no_classes"] += 1
                statistics["_total"]["alternation_classes"]["no_classes"] += 1

            alt_set[lsa] = {
                "Alternation_Type": alt_type,
                "Description": df_alternations["Alternation description"][index],
                "Radi": radi_value,
                "Coding_Frames_Text": df_alternations["Derived coding frame"][index],
            }

        statistics["langs"][excel_file_name]["derived_coding_frames"] = len(alt_frames)
        statistics["langs"][excel_file_name]["alternations"] = len(alt_set)
        statistics["_total"]["derived_coding_frames"] += len(alt_frames)
        statistics["_total"]["alternations"] += len(alt_set)

        new_alternations = []
        alternation_map = {}
        for name in alt_set:
            already_present = False
            if language_to_update:
                for index in alternations_db:
                    this_name = alternations_db[index]["Name"]
                    if this_name == name and alternations_db[index]["Language_ID"] == lang_code:
                        alternation_map[name] = index
                        already_present = True
                        if debug:
                            print(f"Alternation {name} already exists [id = {index}]")
                        break
            if not already_present:
                new_alternation = {"Language_ID": lang_code, "Name": name}
                for key in alt_set[name]:
                    new_alternation[key] = alt_set[name][key]
                new_alternations.append(new_alternation)

        alternation_map |= addToDB(alternations_db, new_alternations, alternations_labels, mainKey="Name")
        if debug and new_alternations:
            print("Added to alternations")
            for row in new_alternations:
                print(row)

        new_frames = []
        frame_map = {}
        if language_to_update:
            for index in frames_db:
                this_name = frames_db[index]["Coding_Frame_Schema"]
                if frames_db[index]["Language_ID"] == lang_code and frames_db[index]["Derived"] == "Basic":
                    frame_map[this_name] = index

        for frame in frames:
            frame = cleanCell(frame)
            if not frame or frame == "no":
                continue
            already_present = False
            if language_to_update and frame in frame_map:
                already_present = True
                if debug:
                    print(f"Basic frame {frame} already exists")
            if not already_present:
                new_frames.append(
                    {
                        "Language_ID": lang_code,
                        "Coding_Frame_Schema": frame,
                        "Derived": "Basic",
                    }
                )

        frame_map |= addToDB(frames_db, new_frames, frames_labels, mainKey="Coding_Frame_Schema")
        if debug and new_frames:
            print("Added to frames (1)")
            for row in new_frames:
                print(row)

        new_frames = []
        derived_frame_map = {}
        for index in frames_db:
            this_name = frames_db[index]["Coding_Frame_Schema"]
            if frames_db[index]["Language_ID"] == lang_code and frames_db[index]["Derived"] == "Derived":
                derived_frame_map[this_name] = index

        for frame in alt_frames:
            frame = cleanCell(frame)
            if not frame or frame == "no":
                continue
            already_present = False
            if language_to_update and frame in derived_frame_map:
                already_present = True
                if debug:
                    print(f"Derived frame {frame} already exists")
            if not already_present:
                new_frames.append(
                    {
                        "Language_ID": lang_code,
                        "Coding_Frame_Schema": frame,
                        "Derived": "Derived",
                    }
                )

        derived_frame_map |= addToDB(frames_db, new_frames, frames_labels, mainKey="Coding_Frame_Schema")
        if debug and new_frames:
            print("Added to frames (2)")
            for row in new_frames:
                print(row)

        form_map = {}
        verb_map = {}

        already_included_forms = {}
        if language_to_update:
            for form_index in forms_db:
                if forms_db[form_index]["Language_ID"] == lang_code:
                    clean_form = cleanApostrophe(forms_db[form_index]["Form"])
                    new_index = f"{forms_db[form_index]['Parameter_ID']}-{clean_form}"
                    if new_index in already_included_forms:
                        print(f"WARN: {new_index} already exists as a homonym with identical spelling [lang = {lang_code}], disambiguating by meaning ordinal")
                    already_included_forms.setdefault(new_index, []).append(form_index)

                    raw_meaning = parameters_db[forms_db[form_index]["Parameter_ID"]]["Name"]
                    form_map[raw_meaning] = form_index
                    verb_map[raw_meaning] = getVerbMeaning(raw_meaning)

        new_forms = []
        for index in df_basic.index:
            raw_meaning = sanitizeFrame(df_basic["Meaning"][index])
            if not raw_meaning:
                continue

            frame = df_basic["Coding frame"][index]
            verb = cleanApostrophe(df_basic["Verb"][index])
            sc = df_basic["S/C"][index]

            sc_text = "Unknown"
            if sc.lower() == "s":
                sc_text = "Simplex"
            if sc.lower() == "c":
                sc_text = "Complex"

            verb_meaning = getVerbMeaning(raw_meaning)
            this_form = findForm(verb_meaning, parameters_db, forms_db, lang_code, loop_limit, form_map)
            if this_form is None:
                if error_reporting["meanings"]:
                    print(f"ERR: unable to find meaning (basic) [row {index + 2}]:", verb_meaning)
                continue

            form_map[raw_meaning] = this_form
            verb_map[raw_meaning] = verb_meaning
            frame = sanitizeFrame(frame)

            already_present = False
            if language_to_update:
                this_index = f"{verb_meaning}-{verb}"
                if this_index in already_included_forms:
                    already_present = True
                    matched_form_id = resolveExistingForm(
                        already_included_forms[this_index], getMeaningOrdinal(raw_meaning)
                    )
                    form_map[raw_meaning] = forms_db[matched_form_id]["ID"]
                    verb_map[raw_meaning] = forms_db[matched_form_id]["Parameter_ID"]

                    if sc_text != "Unknown":
                        if debug:
                            print(f"Updated {verb_map[raw_meaning]}, simplex_or_complex = {sc_text}")
                        forms_db[matched_form_id]["simplex_or_complex"] = sc_text
                    if frame:
                        if debug:
                            print(f"Updated {verb_map[raw_meaning]}, Basic_Coding_Frame_ID = {frame_map[frame]}")
                        forms_db[matched_form_id]["Basic_Coding_Frame_ID"] = frame_map[frame]
                    if df_basic["notes-lemma"][index]:
                        if debug:
                            print(f"Updated {verb_map[raw_meaning]}, Comment = {df_basic['notes-lemma'][index]}")
                        forms_db[matched_form_id]["Comment"] = df_basic["notes-lemma"][index]
                    continue

            if not frame or frame == "na":
                continue

            this_comment = df_basic["notes-lemma"][index] + "\n" + df_basic["notes-cf"][index]
            this_comment = this_comment.strip().replace("\n", "<br />\n")

            new_forms.append(
                {
                    "ID": this_form,
                    "Language_ID": lang_code,
                    "Parameter_ID": verb_meaning,
                    "Value": verb,
                    "Form": verb,
                    "simplex_or_complex": sc_text,
                    "Basic_Coding_Frame_ID": frame_map[frame],
                    "Comment": this_comment,
                }
            )

        addToDB(forms_db, new_forms, forms_labels, addID=False)
        if debug and new_forms:
            print("Added to forms")
            for row in new_forms:
                print(row)

        new_alternation_values = []
        for index in df_alternations.index:
            lsa = cleanCell(df_alternations["Language-specific alternation"][index])
            if not lsa:
                continue

            raw_meaning = sanitizeFrame(df_alternations["Meaning"][index])
            raw_meaning_ok = getVerbMeaning(raw_meaning)

            this_form = None
            if raw_meaning not in form_map:
                this_verb = cleanApostrophe(df_alternations["Verb"][index])
                new_index = f"{raw_meaning_ok}-{this_verb}"
                if new_index in already_included_forms:
                    this_form = resolveExistingForm(
                        already_included_forms[new_index], getMeaningOrdinal(raw_meaning)
                    )
                    form_map[raw_meaning] = this_form
                    verb_map[raw_meaning] = raw_meaning_ok
                else:
                    if error_reporting["meanings"]:
                        print(
                            f"ERR: unable to find meaning (alternations) [row {index + 2}]: "
                            f"{raw_meaning} ({raw_meaning_ok})"
                        )
                    continue
            else:
                this_form = form_map[raw_meaning]

            frame = sanitizeFrame(df_alternations["Derived coding frame"][index])
            if frame in {"na", ""}:
                continue

            mrnd = df_alternations["M/R/N/D"][index]
            mrnd_text = "No data"
            if mrnd.lower() == "m":
                mrnd_text = "Marginally"
            if mrnd.lower() == "r":
                mrnd_text = "Regularly"
            if mrnd.lower() == "n":
                mrnd_text = "Never"

            new_alternation_values.append(
                {
                    "Form_ID": this_form,
                    "Alternation_ID": alternation_map[lsa],
                    "Alternation_Occurs": mrnd_text,
                    "Derived_Code_Frame_ID": derived_frame_map[frame],
                    "Comment": df_alternations["Comment"][index],
                }
            )

        existing_alternation_values = []
        for index in alternation_values_db:
            if alternation_values_db[index]["Form_ID"].startswith(lang_code):
                existing_alternation_values.append(alternation_values_db[index])

        cs_map = {}
        existing_cs = set()
        if language_to_update:
            for index in coding_sets_db:
                if coding_sets_db[index]["Language_ID"] in lang_code:
                    existing_cs.add(coding_sets_db[index]["Name"])
                    cs_map[coding_sets_db[index]["Name"]] = index

        skip_indexes = set()
        cs_set = set()
        for index in df_mr.index:
            raw_meaning = sanitizeFrame(df_mr["Meaning"][index])
            if raw_meaning not in form_map:
                print(f"ERR: unable to find meaning (microroles) [row {index + 2}]: {raw_meaning}")
                continue

            for i in range(6):
                j = i + 1
                cs = cleanCell(df_mr[f"{j}-cs"][index])
                mr = cleanCell(df_mr[f"{j}-mr"][index])
                if cs:
                    if config_data["convert_cs"]:
                        cs = convertCS(cs)
                    cs_set.add(cs)
                if mr:
                    mr_search = f"{cleanRole(mr)}-{verb_map[raw_meaning]}"
                    if mr_search not in microroles:
                        if error_reporting["microroles"]:
                            print(
                                f"ERR: missing microrole (microroles) [row {index + 2}]:",
                                raw_meaning,
                                mr,
                                mr_search,
                            )
                        skip_indexes.add(index)

        new_coding_sets = []
        cs_set = cs_set.difference(existing_cs)
        for cs in cs_set:
            new_coding_sets.append({"Language_ID": lang_code, "Name": cs})

        statistics["langs"][excel_file_name]["coding_sets"] = len(new_coding_sets)
        statistics["_total"]["coding_sets"] += len(new_coding_sets)

        cs_map |= addToDB(coding_sets_db, new_coding_sets, coding_sets_labels, mainKey="Name")
        if debug and new_coding_sets:
            print("Added to coding sets")
            for row in new_coding_sets:
                print(row)

        rows = {}
        fcrmr_rows = {}
        for index in df_mr.index:
            if index in skip_indexes:
                continue

            raw_meaning = sanitizeFrame(df_mr["Meaning"][index])
            if raw_meaning not in form_map:
                if error_reporting["meanings"]:
                    print(f"ERR: unable to find meaning (microroles) [row {index + 2}]:", raw_meaning)
                continue

            frame = cleanCell(sanitizeFrame(df_mr["Coding frame"][index]))
            if not frame:
                continue

            ba = df_mr["B/A"][index].strip()
            frame_id = None
            if ba.lower() == "a":
                if frame not in derived_frame_map:
                    if error_reporting["frames"]:
                        print(f"ERR: missing frame (microroles) [row {index + 2}]:", ba, raw_meaning, frame)
                    continue
                frame_id = derived_frame_map[frame]
            if ba.lower() == "b":
                if frame not in frame_map:
                    if error_reporting["frames"]:
                        print(f"ERR: missing frame (microroles) [row {index + 2}]:", ba, raw_meaning, frame)
                    continue
                frame_id = frame_map[frame]

            if not frame_id:
                if error_reporting["frames"]:
                    print(f"ERR: missing frameID (microroles) [row {index + 2}]:", raw_meaning, ba)
                continue

            for i in range(6):
                j = i + 1
                mr = cleanCell(df_mr[f"{j}-mr"][index])
                cs = cleanCell(df_mr[f"{j}-cs"][index])
                at = cleanCell(df_mr[f"{j}-at"][index])
                notes = cleanCell(df_mr[f"{j}-notes"][index])

                if not mr or not cs:
                    if mr and error_reporting["microroles"]:
                        print(
                            f"ERR: microrole is present, coding-set is not (microroles) [row {index + 2}]: ",
                            j,
                            mr,
                            cs,
                            at,
                            notes,
                        )
                    if cs and error_reporting["microroles"]:
                        print(
                            f"ERR: coding-set is present, microrole is not (microroles) [row {index + 2}]: ",
                            j,
                            mr,
                            cs,
                            at,
                            notes,
                        )
                    continue

                if config_data["convert_cs"]:
                    cs = convertCS(cs)
                mr_search = f"{cleanRole(mr)}-{verb_map[raw_meaning]}"

                fcrmr_row_id = f"{form_map[raw_meaning]}-{frame_id}"
                if fcrmr_row_id in fcrmr_rows:
                    mr_set = set(fcrmr_rows[fcrmr_row_id]["Microrole_IDs"].split(";"))
                    mr_set.add(microroles[mr_search])
                    fcrmr_rows[fcrmr_row_id]["Microrole_IDs"] = ";".join(mr_set)
                else:
                    fcrmr_rows[fcrmr_row_id] = {
                        "ID": fcrmr_row_id,
                        "Form_ID": form_map[raw_meaning],
                        "Coding_Frame_ID": frame_id,
                        "Microrole_IDs": microroles[mr_search],
                    }

                this_id = f"{frame_id}-{j}"
                if this_id in rows:
                    mr_set = set(rows[this_id]["Microrole_IDs"].split(";"))
                    mr_set.add(microroles[mr_search])
                    rows[this_id]["Microrole_IDs"] = ";".join(mr_set)
                else:
                    rows[this_id] = {
                        "ID": this_id,
                        "Coding_Frame_ID": frame_id,
                        "Index_Number": j,
                        "Coding_Set_ID": cs_map[cs],
                        "Argument_Type": at,
                        "Microrole_IDs": microroles[mr_search],
                    }

        final_rows = list(rows.values())
        addToDB(coding_frame_index_numbers_db, final_rows, coding_frame_index_numbers_labels, addID=False)
        statistics["langs"][excel_file_name]["coding_frame_index_numbers"] = len(final_rows)
        statistics["_total"]["coding_frame_index_numbers"] += len(final_rows)
        if debug and final_rows:
            print("Added to coding frame index numbers")
            for row in final_rows:
                print(row)

        final_rows = list(fcrmr_rows.values())
        addToDB(form_coding_frame_microroles_db, final_rows, form_coding_frame_microroles_labels, addID=False)
        statistics["langs"][excel_file_name]["microroles"] = len(final_rows)
        statistics["_total"]["microroles"] += len(final_rows)
        if debug and final_rows:
            print("Added to coding frame microroles")
            for row in final_rows:
                print(row)

        example_index = 0
        if language_to_update:
            for existing_example in examples_db.values():
                if existing_example["Language_ID"] == lang_code:
                    try:
                        existing_number = int(existing_example["Number"])
                    except (TypeError, ValueError):
                        existing_number = 0
                    example_index = max(example_index, existing_number)

        new_examples = []
        new_frame_examples = {}
        for index in df_examples.index:
            raw_meaning = sanitizeFrame(df_examples["Meaning"][index])
            if not raw_meaning:
                continue
            if raw_meaning not in form_map:
                if error_reporting["meanings"]:
                    print(f"ERR: unable to find meaning (examples) [row {index + 2}]:", raw_meaning)
                continue

            form_ids = form_map[raw_meaning]
            frame = sanitizeFrame(df_examples["Coding frame"][index])
            ba = df_examples["B/A"][index].strip()
            is_alternation = False
            frame_id = None
            if ba.lower() == "a":
                if frame not in derived_frame_map:
                    if error_reporting["frames"]:
                        print(f"ERR: missing frame (examples) [row {index + 2}]:", ba, raw_meaning, frame)
                    continue
                frame_id = derived_frame_map[frame]
                is_alternation = True
            if ba.lower() == "b":
                if frame not in frame_map:
                    if error_reporting["frames"]:
                        print(f"ERR: missing frame (examples) [row {index + 2}]:", ba, raw_meaning, frame)
                    continue
                frame_id = frame_map[frame]

            if not frame_id:
                if error_reporting["frames"]:
                    print(f"ERR: missing frameID (examples) [row {index + 2}]:", raw_meaning, ba)
                continue

            primary_text = cleanText(cleanCell(df_examples["Primary text"][index]))
            if not primary_text:
                continue

            example_index += 1
            example_id = f"{lang_code}-{example_index}"

            analyzed_text = re.sub(r"\s+", "\\\\t", cleanCell(df_examples["Analyzed text"][index]))
            analyzed_text = cleanText(analyzed_text)
            gloss_text = cleanCell(df_examples["Gloss"][index])
            gloss_text = re.sub(r"\\", "&bsol;", gloss_text)
            gloss_text = re.sub(r"\s+", "\\\\t", gloss_text)
            gloss_text = cleanText(gloss_text)

            if not analyzed_text:
                analyzed_text = re.sub(r"\s+", "\\\\t", primary_text)
            new_example = {
                "ID": example_id,
                "Language_ID": lang_code,
                "Primary_Text": primary_text,
                "Analyzed_Word": analyzed_text,
                "Gloss": gloss_text,
                "Translated_Text": cleanCell(df_examples["Translation"][index]),
                "Number": example_index,
                "Comment": cleanCell(df_examples["Comment"][index]),
                "Link": cleanCell(df_examples["Link"][index]),
                "Form_IDs": form_ids,
                "Example_Type": "Corpus-illustrated example",
                "SourceText": cleanCell(df_examples["Source"][index]),
            }
            new_examples.append(new_example)

            if is_alternation:
                alt_ex_added = False
                for alt_value in new_alternation_values + existing_alternation_values:
                    if alt_value["Derived_Code_Frame_ID"] == frame_id and alt_value["Form_ID"] == form_ids:
                        if "Example_IDs" not in alt_value:
                            alt_value["Example_IDs"] = ""
                        if alt_value["Example_IDs"]:
                            alt_value["Example_IDs"] += ";"
                        alt_value["Example_IDs"] += example_id
                        alt_ex_added = True
                if not alt_ex_added:
                    print(f"ERR: missing derived coding frame (examples) [row {index + 2}]:", raw_meaning, ba)
            else:
                fe_id = f"{form_ids}-{frame_id}"
                if forms_db[form_ids]["Basic_Coding_Frame_ID"] != frame_id:
                    print(f"ERR: inconsistency in basic coding frame (examples) [row {index + 2}]", raw_meaning)
                if fe_id in new_frame_examples:
                    new_frame_examples[fe_id]["Example_IDs"] += f";{example_id}"
                else:
                    new_frame_examples[fe_id] = {
                        "Form_ID": form_ids,
                        "Coding_Frame_ID": frame_id,
                        "Example_IDs": example_id,
                    }

        addToDB(alternation_values_db, new_alternation_values, alternation_values_labels)
        if debug and new_alternation_values:
            print("Added to alternation values")
            for row in new_alternation_values:
                print(row)

        addToDB(examples_db, new_examples, examples_labels, addID=False)
        statistics["langs"][excel_file_name]["examples"] = len(new_examples)
        statistics["_total"]["examples"] += len(new_examples)
        if debug and new_examples:
            print("Added to examples")
            for row in new_examples:
                print(row)

        def_frame_examples = list(new_frame_examples.values())
        addToDB(coding_frame_examples_db, def_frame_examples, coding_frame_examples_labels)
        if debug and def_frame_examples:
            print("Added to coding frame examples")
            for row in def_frame_examples:
                print(row)

    print("\n### Adding alternation classes\n")

    if alt_folder and os.path.exists(alt_folder) and os.path.isdir(alt_folder):
        for add_file in glob.glob(os.path.join(alt_folder, "*.xlsx")):
            basename = os.path.basename(add_file)
            statistics["updated_langs"][basename] = {"alternation_classes": {"in_file": 0, "skipped": 0}}
            for class_name in ["R", "A", "D", "I"]:
                statistics["updated_langs"][basename]["alternation_classes"][class_name] = 0

            if basename.startswith("~"):
                continue
            df_newclasses = pd.read_excel(add_file)
            for index in df_newclasses.index:
                alternation_id = str(df_newclasses["ID"][index])
                alternation_class = df_newclasses["Alternation_Class"][index].upper()
                statistics["updated_langs"][basename]["alternation_classes"]["in_file"] += 1
                if alternation_class not in radi_map:
                    print(f"ERR: Unknown value {alternation_class} for RADI")
                    statistics["updated_langs"][basename]["alternation_classes"]["skipped"] += 1
                    continue
                if alternation_id not in alternations_db:
                    print(f"ERR: ID {alternation_id} not found in alternations DB")
                    statistics["updated_langs"][basename]["alternation_classes"]["skipped"] += 1
                    continue
                alternations_db[alternation_id]["Radi"] = radi_map[alternation_class]
                statistics["updated_langs"][basename]["alternation_classes"][alternation_class] += 1

    saveFile(output_folder, "coding-frames.csv", frames_db, frames_labels)
    saveFile(output_folder, "languages.csv", languages_db, languages_labels)
    saveFile(output_folder, "forms.csv", forms_db, forms_labels)
    saveFile(output_folder, "alternations.csv", alternations_db, alternations_labels)
    saveFile(output_folder, "alternation-values.csv", alternation_values_db, alternation_values_labels)
    saveFile(output_folder, "coding-sets.csv", coding_sets_db, coding_sets_labels)
    saveFile(
        output_folder,
        "coding-frame-index-numbers.csv",
        coding_frame_index_numbers_db,
        coding_frame_index_numbers_labels,
    )
    saveFile(output_folder, "examples.csv", examples_db, examples_labels)
    saveFile(output_folder, "coding-frame-examples.csv", coding_frame_examples_db, coding_frame_examples_labels)
    saveFile(
        output_folder,
        "form-coding-frame-microroles.csv",
        form_coding_frame_microroles_db,
        form_coding_frame_microroles_labels,
    )
    saveFile(output_folder, "parameters.csv", parameters_db, parameters_labels)
    saveFile(output_folder, "microroles.csv", microroles_db, microroles_labels)

    for file in os.listdir(input_folder):
        input_file = os.path.join(input_folder, file)
        if os.path.isfile(input_file):
            output_file = os.path.join(output_folder, file)
            if not os.path.exists(output_file):
                shutil.copyfile(input_file, output_file)

    if show_stats:
        pprint.pprint(statistics)

    return {
        "statistics": statistics,
        "output_folder": output_folder,
        "languages_to_run": languages_to_run,
    }
