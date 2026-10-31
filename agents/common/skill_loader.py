"""
Cargador y Registro Programático de Skills (`.agents/skills/<nombre>/SKILL.md`).

Este módulo implementa explícitamente cómo la aplicación descubre, valida y carga
las instrucciones de las skills desde sus archivos `SKILL.md`, vinculándolas con
la lista cerrada de agentes autorizados y sus herramientas Python.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_ROOT = PROJECT_ROOT / ".agents" / "skills"


class SkillLoadError(RuntimeError):
    """Error al cargar o validar un manifiesto SKILL.md."""
    pass


@dataclass
class SkillDefinition:
    """Representación en memoria de una Skill cargada desde `.agents/skills/`."""
    name: str
    description: str
    tool_name: str
    allowed_agents: List[str] = field(default_factory=list)
    instructions_markdown: str = ""
    file_path: str = ""


def _parse_frontmatter(raw_content: str, file_path: Path) -> Dict[str, object]:
    """
    Analiza de forma segura el bloque YAML frontmatter de un archivo SKILL.md
    sin ejecutar código arbitrario.
    """
    if not raw_content.startswith("---"):
        raise SkillLoadError(f"El archivo {file_path} no inicia con delimitador YAML '---'.")

    parts = raw_content.split("---", 2)
    if len(parts) < 3:
        raise SkillLoadError(f"El archivo {file_path} tiene un encabezado YAML incompleto.")

    yaml_text = parts[1].strip()
    body_text = parts[2].strip()

    meta: Dict[str, object] = {"_body": body_text}
    lines = yaml_text.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].rstrip()
        if not line or line.lstrip().startswith("#"):
            idx += 1
            continue

        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()

            if val in (">-", "|", ">"):
                idx += 1
                multiline_parts: List[str] = []
                while idx < len(lines) and (lines[idx].startswith("  ") or not lines[idx].strip()):
                    if lines[idx].strip():
                        multiline_parts.append(lines[idx].strip())
                    idx += 1
                meta[key] = " ".join(multiline_parts)
                continue
            elif val == "":
                idx += 1
                items: List[str] = []
                while idx < len(lines) and lines[idx].strip().startswith("-"):
                    item_val = lines[idx].strip().lstrip("-").strip()
                    if item_val:
                        items.append(item_val)
                    idx += 1
                meta[key] = items
                continue
            else:
                meta[key] = val.strip("\"'")
        idx += 1

    return meta


def load_skill(skill_name: str, skills_root: Optional[Path] = None) -> SkillDefinition:
    """
    Carga y valida una skill específica desde `.agents/skills/<skill_name>/SKILL.md`.
    """
    root = skills_root or SKILLS_ROOT
    # Validar que el nombre de la skill sea un identificador simple sin saltos de ruta
    if not skill_name or "/" in skill_name or "\\" in skill_name or ".." in skill_name:
        raise SkillLoadError(f"Nombre de skill inválido: '{skill_name}'")

    skill_file = (root / skill_name / "SKILL.md").resolve()
    if not skill_file.is_relative_to(root.resolve()) or not skill_file.is_file():
        raise SkillLoadError(f"No se encontró el manifiesto SKILL.md para '{skill_name}' en {skill_file}")

    raw_text = skill_file.read_text(encoding="utf-8")
    parsed = _parse_frontmatter(raw_text, skill_file)

    name = str(parsed.get("name", "")).strip()
    description = str(parsed.get("description", "")).strip()
    tool_name = str(parsed.get("tool_name", "")).strip()
    allowed_agents_raw = parsed.get("allowed_agents", [])
    allowed_agents = (
        [str(a).strip() for a in allowed_agents_raw]
        if isinstance(allowed_agents_raw, list)
        else []
    )
    body = str(parsed.get("_body", "")).strip()

    if name != skill_name:
        raise SkillLoadError(
            f"El campo 'name' ('{name}') en {skill_file} no coincide con la carpeta '{skill_name}'."
        )
    if not description:
        raise SkillLoadError(f"La skill '{skill_name}' no define 'description'.")
    if not body:
        raise SkillLoadError(f"La skill '{skill_name}' tiene el cuerpo de instrucciones vacío.")

    return SkillDefinition(
        name=name,
        description=description,
        tool_name=tool_name,
        allowed_agents=allowed_agents,
        instructions_markdown=body,
        file_path=str(skill_file),
    )


def load_skills_for_agent(
    agent_name: str,
    skill_names: List[str],
    skills_root: Optional[Path] = None,
) -> Dict[str, SkillDefinition]:
    """
    Carga un conjunto cerrado de skills verificando que el agente esté autorizado
    para utilizarlas según el manifiesto SKILL.md.
    """
    loaded: Dict[str, SkillDefinition] = {}
    for s_name in skill_names:
        skill_def = load_skill(s_name, skills_root=skills_root)
        if skill_def.allowed_agents and agent_name not in skill_def.allowed_agents:
            raise SkillLoadError(
                f"El agente '{agent_name}' no está autorizado para cargar la skill '{s_name}'. "
                f"Agentes permitidos: {skill_def.allowed_agents}"
            )
        loaded[s_name] = skill_def
    return loaded


def format_skills_prompt_section(skills: Dict[str, SkillDefinition]) -> str:
    """
    Construye el bloque de instrucciones de sistema con las skills cargadas para el agente.
    """
    if not skills:
        return ""
    blocks = ["=== SKILLS AUTORIZADAS CARGADAS ==="]
    for s_name, s_def in skills.items():
        blocks.append(
            f"\n--- SKILL: {s_def.name} (Herramienta Python: {s_def.tool_name}) ---\n"
            f"Descripción: {s_def.description}\n"
            f"{s_def.instructions_markdown}\n"
        )
    return "\n".join(blocks)
