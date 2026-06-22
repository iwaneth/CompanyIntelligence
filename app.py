from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
import httpx
from nocodb_client import fetch_table, list_projects, list_project_tables

app = FastAPI()


@app.get("/")
async def root():
    return {"status": "ok", "source": "CompanyIntelligence backend"}


@app.get("/nocodb/projects")
async def get_projects():
    try:
        return await list_projects()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/nocodb/projects/{project_id}/tables")
async def get_project_tables(project_id: str):
    try:
        return await run_in_threadpool(list_project_tables, project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/nocodb/{project}/{table}")
async def get_table(project: str, table: str, limit: int = 100):
    try:
        return await fetch_table(project, table, limit)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
