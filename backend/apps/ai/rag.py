"""Database-backed retrieval for the AI gateway."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _db_retrieve(query: str, top_k: int) -> list[dict]:
    """Retrieve matching material and project context using database indexes."""
    results: list[dict] = []
    try:
        from apps.masterdata.models import Item

        for item in Item.objects.filter(name__icontains=query)[:top_k]:
            results.append(
                {
                    'source': 'items',
                    'id': item.id,
                    'title': item.name,
                    'text': getattr(item, 'specification', '') or item.name,
                    'score': None,
                }
            )
    except Exception:  # pragma: no cover - retrieval must not break the AI endpoint
        logger.exception('RAG 数据库物料检索失败')

    remaining = top_k - len(results)
    if remaining > 0:
        try:
            from apps.projects.models import Project

            for project in Project.objects.filter(name__icontains=query)[:remaining]:
                results.append(
                    {
                        'source': 'projects',
                        'id': project.id,
                        'title': project.name,
                        'text': getattr(project, 'description', '') or project.name,
                        'score': None,
                    }
                )
        except Exception:  # pragma: no cover - retrieval must not break the AI endpoint
            logger.exception('RAG 数据库项目检索失败')

    return results[:top_k]


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """Return related context snippets in a stable source/id/title/text/score shape."""
    query = (query or '').strip()
    if not query:
        return []
    if top_k is None:
        top_k = getattr(settings, 'AI_RAG_TOP_K', 5)
    return _db_retrieve(query, max(1, top_k))
