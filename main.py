from vending_machine.main import app

__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("vending_machine.main:app", host="0.0.0.0", port=8000, reload=True)
