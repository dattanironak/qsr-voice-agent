from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.receipts import RECEIPTS_DIR
from app.routers import (
    admin,
    admin_auth,
    admin_orders,
    conversations,
    menu,
    orders,
    payments,
    session,
)
from app.storage import UPLOAD_DIR

app = FastAPI(title="QSR Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(menu.router)
app.include_router(session.router)
app.include_router(admin_auth.router)
app.include_router(admin.router)
app.include_router(admin_orders.router)
app.include_router(conversations.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/receipts", StaticFiles(directory=RECEIPTS_DIR), name="receipts")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
