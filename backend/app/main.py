from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .routers import admin, guest

app = FastAPI(title="Parking Booking API")


class SinglePageAppFiles(StaticFiles):
    """Serve React's entry point when a client-side route has no file."""

    async def get_response(self, path: str, scope: dict) -> object:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(guest.router)
app.include_router(admin.router)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": {"code": "validation_error", "message": "The submitted data is invalid.", "errors": exc.errors()}
        },
    )


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", SinglePageAppFiles(directory=frontend_dist, html=True), name="frontend")
