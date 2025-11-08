from typing import Dict, Any
from datetime import datetime
import uuid


class TaskStorage:
    """Armazena status e resultados das tarefas em memória"""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def create_task(self, task_id: str = None) -> str:
        """Cria uma nova tarefa e retorna o ID"""
        if task_id is None:
            task_id = str(uuid.uuid4())

        self.tasks[task_id] = {
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "progress": 0,
            "total_questions": 0,
            "current_question": 0,
            "result": None,
            "error": None,
        }
        return task_id

    def update_task(self, task_id: str, **kwargs):
        """Atualiza informações da tarefa"""
        if task_id in self.tasks:
            self.tasks[task_id].update(kwargs)
            self.tasks[task_id]["updated_at"] = datetime.now().isoformat()

    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Retorna informações da tarefa"""
        return self.tasks.get(
            task_id, {"status": "not_found", "error": "Task ID não encontrado"}
        )

    def set_progress(self, task_id: str, current: int, total: int):
        """Atualiza progresso da tarefa"""
        progress = int((current / total) * 100) if total > 0 else 0
        self.update_task(
            task_id, current_question=current, total_questions=total, progress=progress
        )

    def complete_task(self, task_id: str, result: Any):
        """Marca tarefa como completa"""
        self.update_task(task_id, status="completed", result=result, progress=100)

    def fail_task(self, task_id: str, error: str):
        """Marca tarefa como falha"""
        self.update_task(task_id, status="failed", error=str(error))


task_storage = TaskStorage()
