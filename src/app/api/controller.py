from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from pydantic import BaseModel
from src.app.services.service import Service, task_storage
import asyncio
import os
import tempfile


router = APIRouter()
service = Service()


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


@router.post("/extract", response_model=TaskResponse)
async def start_extraction(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    task_id = task_storage.create_task()

    background_tasks.add_task(process_extraction, task_id, tmp_path)

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Processamento iniciado. Use o task_id para verificar o progresso.",
    }


def process_extraction(task_id: str, file_path: str):
    try:
        asyncio.run(service.extract_response(file_path, task_id=task_id))
        print(f"✅ Task {task_id} completada com sucesso")
    except Exception as e:
        print(f"❌ Task {task_id} falhou: {str(e)}")
        task_storage.fail_task(task_id, str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@router.get("/extract/{task_id}")
async def get_extraction_status(task_id: str):
    task_info = task_storage.get_task(task_id)

    if task_info.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Task ID não encontrado")

    return task_info


@router.get("/extract")
async def list_all_tasks():
    return {"tasks": task_storage.tasks, "total": len(task_storage.tasks)}
