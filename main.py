"""
SCaaS Python Runner Microservice
Handles deploying and invoking sandboxed Python functions inside Docker containers.
"""

import os
import uuid
import shutil
import hashlib
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.models import (
    DeployRequest,
    DeployResponse,
    InvokeRequest,
    InvokeResponse,
    DeleteResponse,
    HealthResponse,
)
from app.docker_service import DockerService
from app.store import DeploymentStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

store = DeploymentStore()
docker_svc = DockerService()


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("SCaaS Runner starting up")
    yield
    logger.info("SCaaS Runner shutting down")


app = FastAPI(
    title="SCaaS Python Runner",
    description="Sandboxed Python function deployment and invocation service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint."""
    return HealthResponse(status="ok", docker_available=docker_svc.is_docker_available())


@app.post("/deploy", response_model=DeployResponse)
async def deploy(
    function_id: str,
    hash_code: str,
    entry_point: str = "main.handler",
    cpu_cores: float = 0.5,
    memory_mb: int = 256,
    pid_limit: int = 64,
    file: UploadFile = File(...),
):
    """
    Deploy a Python function file as a named Docker container.

    The Spring Boot backend calls this when the user triggers /functions/{id}/deploy.
    Returns a container name that becomes the invocation URL key.
    """
    if not file.filename or not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files are accepted")

    content = await file.read()

    # Validate hash integrity
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != hash_code:
        raise HTTPException(
            status_code=400,
            detail=f"Hash mismatch: expected {hash_code}, got {actual_hash}",
        )

    deployment_id = f"deployment_{function_id}_{hash_code}"

    # Write the uploaded file to a temp staging directory
    staging_dir = Path(f"/tmp/scaas/staging/{deployment_id}")
    staging_dir.mkdir(parents=True, exist_ok=True)
    code_path = staging_dir / "main.py"
    code_path.write_bytes(content)

    try:
        container_name = docker_svc.start_container(
            deployment_id=deployment_id,
            code_path=code_path,
            entry_point=entry_point,
            cpu_cores=cpu_cores,
            memory_mb=memory_mb,
            pid_limit=pid_limit,
        )
    except Exception as e:
        shutil.rmtree(staging_dir, ignore_errors=True)
        logger.error("Container start failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Deployment failed: {e}")

    store.put(deployment_id, {
        "container_name": container_name,
        "function_id": function_id,
        "hash_code": hash_code,
        "entry_point": entry_point,
        "staging_dir": str(staging_dir),
    })

    return DeployResponse(
        deployment_id=deployment_id,
        container_name=container_name,
        invocation_url=f"/invoke/{deployment_id}",
    )


@app.post("/invoke/{deployment_id}", response_model=InvokeResponse)
def invoke(deployment_id: str, request: InvokeRequest):
    """
    Invoke a deployed function by forwarding the JSON event to the running container.
    This is the endpoint the Spring Boot service exposes as the function's invocation URL.
    """
    record = store.get(deployment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    try:
        result = docker_svc.invoke_function(
            container_name=record["container_name"],
            entry_point=record["entry_point"],
            event=request.event,
            context=request.context,
        )
    except TimeoutError:
        raise HTTPException(status_code=408, detail="Function execution timed out")
    except Exception as e:
        logger.error("Invocation error for %s: %s", deployment_id, e)
        raise HTTPException(status_code=500, detail=f"Invocation failed: {e}")

    return InvokeResponse(**result)


@app.delete("/deployments/{deployment_id}", response_model=DeleteResponse)
def delete_deployment(deployment_id: str, background_tasks: BackgroundTasks):
    """
    Tear down a deployment — stops the container and cleans staging files.
    Called by Spring Boot when the user deletes a function.
    """
    record = store.get(deployment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    store.remove(deployment_id)

    background_tasks.add_task(
        _cleanup,
        container_name=record["container_name"],
        staging_dir=record["staging_dir"],
    )

    return DeleteResponse(deployment_id=deployment_id, message="Deployment deleted")


def _cleanup(container_name: str, staging_dir: str):
    try:
        docker_svc.stop_container(container_name)
    except Exception as e:
        logger.warning("Could not stop container %s: %s", container_name, e)
    shutil.rmtree(staging_dir, ignore_errors=True)
    logger.info("Cleaned up deployment %s", container_name)
