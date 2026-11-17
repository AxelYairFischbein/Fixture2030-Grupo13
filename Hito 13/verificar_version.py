"""Comprueba archivos de la imagen en ejecución contra los blobs de un commit local."""

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path


def comando(*args):
    return subprocess.check_output(args, encoding="utf-8").strip()


def verificar(repo, contenedor):
    repo = Path(repo).resolve()
    sha = comando("git", "-C", str(repo), "rev-parse", "HEAD")
    cambios = comando("git", "-C", str(repo), "status", "--porcelain", "--", "Hito 10")
    if cambios:
        raise RuntimeError("El código de la API tiene cambios sin commit")
    inspeccion = json.loads(comando("docker", "inspect", contenedor))[0]
    if not inspeccion["State"]["Running"]:
        raise RuntimeError("La API no está iniciada")
    if inspeccion["Config"].get("Labels", {}).get("org.opencontainers.image.revision") != sha:
        raise RuntimeError("La etiqueta de la imagen no coincide con el checkout")
    if any(m["Destination"] == "/app" or m["Destination"].startswith("/app/") for m in inspeccion["Mounts"]):
        raise RuntimeError("Hay un montaje que reemplaza archivos de la imagen")
    script = """import pathlib,json,hashlib
p=pathlib.Path('/app')
print(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest() for f in p.rglob('*') if f.is_file() and '__pycache__' not in f.parts and '.pytest_cache' not in f.parts}))
"""
    reales = json.loads(comando("docker", "exec", contenedor, "python", "-c", script))
    archivos = comando("git", "-C", str(repo), "ls-files", "Hito 10").splitlines()
    esperados = {}
    for archivo in archivos:
        relativo = archivo.removeprefix("Hito 10/")
        if relativo.split("/")[0] not in {"app", "web", "scripts", "tests", "openapi", "requirements.txt", "pytest.ini"}:
            continue
        blob = subprocess.check_output(["git", "-C", str(repo), "show", f"{sha}:{archivo}"])
        esperados[relativo] = hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest()
    if esperados != reales:
        raise RuntimeError("Los archivos de /app no coinciden con el commit")
    imagen = json.loads(comando("docker", "image", "inspect", inspeccion["Image"]))[0]
    return {
        "fecha": datetime.now(timezone(timedelta(hours=-3))).isoformat(),
        "commit": sha, "contenedor": contenedor, "imagen": inspeccion["Config"]["Image"],
        "image_id": inspeccion["Image"], "repo_digests": imagen.get("RepoDigests", []),
        "inicio_contenedor": inspeccion["State"]["StartedAt"],
        "cambios_api": cambios, "archivos_coinciden": True,
        "metodo": "SHA256 de cada archivo copiado a /app contra git show del commit, normalizando CRLF a LF",
        "sha256_archivos": esperados,
        "montajes": [{"destino": m["Destination"], "solo_lectura": not m["RW"]} for m in inspeccion["Mounts"]],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--contenedor", default="grupo13-hito10-api-1")
    p.add_argument("--salida", type=Path, required=True)
    a = p.parse_args()
    resultado = verificar(a.repo, a.contenedor)
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    with a.salida.open("x", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("Versión comprobada:", resultado["commit"], "archivos:", len(resultado["sha256_archivos"]))
