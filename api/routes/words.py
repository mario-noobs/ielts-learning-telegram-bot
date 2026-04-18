from fastapi import APIRouter, Depends, HTTPException, status

import config
from api.auth import get_current_user
from api.models.vocabulary import Collocation, EnrichedExample, EnrichedWord
from services import word_service


def _to_collocation(item) -> Collocation:
    if isinstance(item, dict):
        return Collocation(phrase=item.get("phrase", ""), label=item.get("label", ""))
    return Collocation(phrase=str(item), label="")

router = APIRouter(prefix="/api/v1/words", tags=["words"])


@router.get("/{word}", response_model=EnrichedWord)
async def get_enriched_word(
    word: str,
    user: dict = Depends(get_current_user),
) -> EnrichedWord:
    """Return full enrichment for a word (IPA, examples, collocations, ...)."""
    normalized = word_service.normalize_word(word)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Word cannot be empty.",
        )

    band = float(user.get("target_band", config.DEFAULT_BAND_TARGET))
    data = await word_service.get_enriched_word(normalized, band)

    raw_examples = data.get("examples_by_band", {}) or {}
    examples = {
        tier: EnrichedExample(en=ex.get("en", ""), vi=ex.get("vi", ""))
        for tier, ex in raw_examples.items()
    }

    raw_collocations = data.get("collocations", []) or []
    collocations = [_to_collocation(c) for c in raw_collocations if c]

    return EnrichedWord(
        word=data.get("word", normalized),
        ipa=data.get("ipa", ""),
        syllable_stress=data.get("syllable_stress", ""),
        part_of_speech=data.get("part_of_speech", ""),
        definition_en=data.get("definition_en", ""),
        definition_vi=data.get("definition_vi", ""),
        word_family=data.get("word_family", []) or [],
        collocations=collocations,
        examples_by_band=examples,
        ielts_tip=data.get("ielts_tip", ""),
    )
