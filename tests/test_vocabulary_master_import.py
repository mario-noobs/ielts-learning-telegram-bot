from __future__ import annotations

from scripts.import_vocabulary_master import (
    SOURCE,
    build_upsert_statement,
    candidate_id,
    normalize_word,
    parse_wordlevel_rows,
    split_csv_list,
)


def test_normalize_word_matches_user_vocab_dedupe_shape():
    assert normalize_word("  Carbon Footprint! ") == "carbon footprint"
    assert normalize_word("Don’t") == "dont"


def test_split_csv_list_drops_empty_items():
    assert split_csv_list("shortfall, shortage, ") == ["shortfall", "shortage"]


def test_parse_wordlevel_rows_builds_candidate_payload():
    csv_text = "\n".join(
        [
            "word,pos,difficulty,theme,synonyms,definition_en,example_sentence",
            "deficit,noun,5,Economics,\"shortfall, shortage\",A shortfall.,A deficit grew.",
            "deficit,noun,5,Economics,\"duplicate\",Duplicate.,Duplicate.",
            "photosynthesis,noun,4,Biology,conversion,A process.,Plants use light.",
        ]
    )

    candidates = parse_wordlevel_rows(csv_text, {"economy": 2, "science": 9})

    assert len(candidates) == 2
    first = candidates[0]
    assert first.id == candidate_id("deficit")
    assert first.word == "deficit"
    assert first.normalized_word == "deficit"
    assert first.difficulty == 5
    assert first.topic_id == 2
    assert first.synonyms == ["shortfall", "shortage"]

    values = first.to_insert_values()
    assert values["source"] == SOURCE
    assert values["source_ref"] == "deficit"
    assert values["status"] == "candidate"
    assert values["metadata"]["source_dataset"] == "toefl_essential_vocabulary.csv"

    assert candidates[1].topic_id == 9


def test_build_upsert_statement_handles_metadata_column_name():
    csv_text = "\n".join(
        [
            "word,pos,difficulty,theme,synonyms,definition_en,example_sentence",
            "deficit,noun,5,Economics,\"shortfall, shortage\",A shortfall.,A deficit grew.",
        ]
    )
    values = [parse_wordlevel_rows(csv_text, {"economy": 2})[0].to_insert_values()]

    statement = build_upsert_statement(values)

    compiled = str(statement.compile())
    assert "vocabulary_master" in compiled
    assert "metadata" in compiled
