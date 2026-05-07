from datetime import date

from fastapi import FastAPI

app = FastAPI()


def days_before_new_year(today: date | None = None) -> int:
    current = today or date.today()
    next_new_year = date(current.year + 1, 1, 1)
    return (next_new_year - current).days


@app.get("/info")
def get_info() -> dict[str, int]:
    return {"days_before_new_year": days_before_new_year()}
