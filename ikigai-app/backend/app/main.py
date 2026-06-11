from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import os
from .ikigai import build_reflection

app = FastAPI(title="Ikigai API", version="1.0.0")

allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class IkigaiRequest(BaseModel):
    answers: List[str]
    lang: str = "en"


class Section(BaseModel):
    title: str
    body: str
    domain: str


class IkigaiResponse(BaseModel):
    eyebrow: str
    centre_intro: str
    centre: str
    sections: List[Section]
    closing: str


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ikigai"}


@app.post("/api/ikigai", response_model=IkigaiResponse)
async def ikigai(req: IkigaiRequest):
    if len(req.answers) != 8:
        raise HTTPException(status_code=422, detail="Exactly 8 answers required.")
    return await build_reflection(req.answers, req.lang)
