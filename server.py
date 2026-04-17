from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import subprocess
import os

app = FastAPI()

API_TOKEN = os.environ.get("API_TOKEN", "")
MAX_PROMPT_LENGTH = 4000

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["Authorization", "Content-Type"],
)

security = HTTPBearer(auto_error=False)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not API_TOKEN:
        return
    if not credentials or credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


class PromptRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PROMPT_LENGTH)


@app.post("/prompt")
async def prompt(req: PromptRequest, _=Depends(verify_token)):
    result = subprocess.run(
        ["claude", "-p", req.text],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail="Claude CLI returned an error")
    return {"response": result.stdout.strip()}


app.mount("/", StaticFiles(directory="pwa", html=True), name="pwa")
