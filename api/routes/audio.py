import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from api.auth import get_current_user
from services import tts_service, word_service

router = APIRouter(prefix="/api/v1/audio", tags=["audio"])


@router.get("/{word}")
async def get_audio(
    word: str,
    _user: dict = Depends(get_current_user),
) -> FileResponse:
    normalized = word_service.normalize_word(word)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Word cannot be empty.",
        )

    path = await asyncio.to_thread(tts_service.generate_audio, normalized)
    if not path:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS unavailable.",
        )

    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=f"{normalized}.mp3",
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )
