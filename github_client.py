#!/usr/bin/env python3
"""
Cliente GitHub reutilizable para la flota Sud-Austral.

Extraido de propagar.py para que pueda ejecutarse en CI.

    propagar.py y reset_uat_branches.py siguen ignorados por git de forma
    permanente, porque llevan un token en claro en el codigo. Este modulo es
    la parte de esos scripts que SI puede versionarse: la clase cliente, sin
    token, sin main() y sin ninguna operacion destructiva.

El token NUNCA se escribe aqui. Se lee del entorno:

    Windows PowerShell:
        $env:GH_FLEET_TOKEN="..."

    Linux/macOS:
        export GH_FLEET_TOKEN="..."

    GitHub Actions:
        env:
          GH_FLEET_TOKEN: secrets.GH_FLEET_TOKEN
"""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests


# ============================================================
# CONFIGURACION
# ============================================================

GITHUB_API = "https://api.github.com"

ORGANIZATION = "Sud-Austral"

API_VERSION = "2026-03-10"

DEFAULT_BRANCH = "main"

USER_AGENT = "Sud-Austral-fleet-client"

TOKEN_ENV_VAR = "GH_FLEET_TOKEN"

# Alcance del proyecto: solo repositorios cuyo nombre empieza con esto.
# La comparacion es insensible a mayusculas, porque en la organizacion
# conviven coipo_* y COIPO_*.
SCOPE_PREFIX = "coipo"


# ============================================================
# MODELOS
# ============================================================

@dataclass
class Repository:
    name: str
    full_name: str
    default_branch: str
    archived: bool
    disabled: bool
    fork: bool
    private: bool

    # Campos que la API ya devuelve y que propagar.py descartaba.
    # pushed_at es lo que permite ordenar por repositorio dormido.
    pushed_at: str | None = None
    size: int = 0
    description: str | None = None
    language: str | None = None
    topics: list[str] = field(default_factory=list)
    html_url: str | None = None

    @property
    def in_scope(self) -> bool:
        """
        True si el repositorio pertenece al alcance del proyecto.
        """

        return self.name.lower().startswith(SCOPE_PREFIX)


# ============================================================
# TOKEN
# ============================================================

def read_token(required: bool = True) -> str | None:
    """
    Lee el token del entorno. Nunca de un literal en el codigo.
    """

    token = os.environ.get(TOKEN_ENV_VAR)

    if not token and required:
        raise RuntimeError(
            f"Falta la variable de entorno {TOKEN_ENV_VAR}. "
            f"El token no se escribe en el codigo."
        )

    return token


# ============================================================
# CLIENTE
# ============================================================

class GitHubClient:
    def __init__(self, token: str | None = None):

        if token is None:
            token = read_token()

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": USER_AGENT,
            }
        )

    # --------------------------------------------------------
    # REQUEST
    # --------------------------------------------------------

    def request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> requests.Response:

        url = f"{GITHUB_API}{endpoint}"

        response = self.session.request(
            method,
            url,
            timeout=30,
            **kwargs,
        )

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")

            wait = int(retry_after) if retry_after else 10

            print(
                f"      Rate limit. Esperando {wait}s...",
                flush=True,
            )

            time.sleep(wait)

            response = self.session.request(
                method,
                url,
                timeout=30,
                **kwargs,
            )

        return response

    # --------------------------------------------------------
    # LISTAR REPOSITORIOS
    # --------------------------------------------------------

    def list_organization_repositories(
        self,
        organization: str = ORGANIZATION,
        only_in_scope: bool = False,
    ) -> list[Repository]:

        repositories: list[Repository] = []

        page = 1

        while True:

            response = self.request(
                "GET",
                f"/orgs/{organization}/repos",
                params={
                    "per_page": 100,
                    "page": page,
                    "type": "all",
                },
            )

            if response.status_code != 200:
                raise RuntimeError(
                    self.format_error(
                        response,
                        f"No se pudieron obtener los repositorios "
                        f"de la organizacion {organization}",
                    )
                )

            data = response.json()

            if not data:
                break

            for item in data:

                repositories.append(
                    Repository(
                        name=item["name"],
                        full_name=item["full_name"],
                        default_branch=item.get(
                            "default_branch",
                            DEFAULT_BRANCH,
                        ),
                        archived=item.get("archived", False),
                        disabled=item.get("disabled", False),
                        fork=item.get("fork", False),
                        private=item.get("private", False),
                        pushed_at=item.get("pushed_at"),
                        size=item.get("size", 0),
                        description=item.get("description"),
                        language=item.get("language"),
                        topics=item.get("topics") or [],
                        html_url=item.get("html_url"),
                    )
                )

            page += 1

        if only_in_scope:
            repositories = [r for r in repositories if r.in_scope]

        return repositories

    # --------------------------------------------------------
    # OBTENER ARCHIVO
    # --------------------------------------------------------

    def get_file(
        self,
        repository: str,
        path: str,
        branch: str,
    ) -> tuple[str | None, str | None]:

        response = self.request(
            "GET",
            f"/repos/{repository}/contents/{path}",
            params={
                "ref": branch,
            },
        )

        if response.status_code == 404:
            return None, None

        if response.status_code != 200:
            raise RuntimeError(
                self.format_error(
                    response,
                    f"No se pudo consultar {path} en {repository}",
                )
            )

        data = response.json()

        if data.get("type") != "file":
            raise RuntimeError(
                f"{repository}/{path} no es un archivo."
            )

        encoded_content = data.get("content", "").replace("\n", "")

        content = base64.b64decode(
            encoded_content
        ).decode("utf-8")

        return content, data.get("sha")

    # --------------------------------------------------------
    # CREAR / ACTUALIZAR ARCHIVO
    # --------------------------------------------------------

    def put_file(
        self,
        repository: str,
        path: str,
        branch: str,
        content: str,
        sha: str | None,
        message: str,
    ) -> requests.Response:

        encoded = base64.b64encode(
            content.encode("utf-8")
        ).decode("ascii")

        payload: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }

        if sha:
            payload["sha"] = sha

        return self.request(
            "PUT",
            f"/repos/{repository}/contents/{path}",
            json=payload,
        )

    # --------------------------------------------------------
    # WORKFLOWS Y PULL REQUESTS (solo lectura)
    # --------------------------------------------------------

    def list_workflows(
        self,
        repository: str,
    ) -> list[dict[str, Any]]:

        response = self.request(
            "GET",
            f"/repos/{repository}/actions/workflows",
            params={"per_page": 100},
        )

        if response.status_code != 200:
            return []

        return response.json().get("workflows", [])

    def list_open_pull_requests(
        self,
        repository: str,
        head_branch: str | None = None,
    ) -> list[dict[str, Any]]:

        params: dict[str, Any] = {
            "state": "open",
            "per_page": 100,
        }

        if head_branch:
            owner = repository.split("/")[0]
            params["head"] = f"{owner}:{head_branch}"

        response = self.request(
            "GET",
            f"/repos/{repository}/pulls",
            params=params,
        )

        if response.status_code != 200:
            return []

        return response.json()

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    @staticmethod
    def format_error(
        response: requests.Response,
        prefix: str,
    ) -> str:

        try:
            message = response.json().get(
                "message",
                response.text,
            )

        except Exception:
            message = response.text

        return (
            f"{prefix}. "
            f"HTTP {response.status_code}: {message}"
        )


# ============================================================
# UTILIDAD
# ============================================================

def normalize_content(content: str) -> str:
    """
    Normaliza saltos de linea para evitar falsos cambios.
    """

    return content.replace("\r\n", "\n").strip() + "\n"
