import os
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import importlib.metadata
import logging
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Stackdiac",
    description="Stackdiac is a tool to manage infrastructure as code",
    version=importlib.metadata.version("stackdiac"),
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    # openapi_tags=[
    #     {"name": "stackd", "description": "Stackdiac API"},
    # ],
    servers=[
        {
            "url": "http://127.0.0.1:8000",
            "description": "stackdiac dev server",
        },
    ],
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"], 
)

opd = os.path.dirname

# Mount the UI

app.mount("/ui/", StaticFiles(directory=os.path.join(opd(opd(__file__)), "ui"),
                        html=True), name="ui")

@app.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/ui/index.html")