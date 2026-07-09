"""RAG 检索基础脚手架:retrieve(query) 返回可作为 LLM 上下文的片段列表。

这是走向 RAG 的“真实第一步”:优先复用既有的 Elasticsearch 全局搜索
(见 apps/core/search_views.py 的索引与字段约定);未部署 ES 或查询失败时,
回落到数据库 icontains 查询(物料/项目)。二者都返回统一结构的片段,供
views 层拼接进对话上下文。

完整 RAG(文档切分、向量化 embedding、向量检索、重排序、引用回链)为后续里程碑。
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _es_retrieve(query: str, top_k: int) -> list[dict]:
    """通过 Elasticsearch 检索(复用全局搜索的索引/字段约定)。失败即抛出交由上层回落。"""
    from elasticsearch import Elasticsearch
    from elasticsearch_dsl import Search

    es_config = settings.ELASTICSEARCH_DSL['default']
    es = Elasticsearch([es_config['hosts']])

    # 与 core/search_views.py 保持一致的索引与检索字段。
    indexes = {
        'items': ['sku^3', 'name^2', 'specification', 'barcode^3'],
        'projects': ['code^3', 'name^2'],
    }
    results: list[dict] = []
    for index_name, fields in indexes.items():
        search = Search(using=es, index=index_name)
        search = search.query('multi_match', query=query, fields=fields, fuzziness='AUTO')
        response = search[0:top_k].execute()
        for hit in response:
            results.append(
                {
                    'source': index_name,
                    'id': hit.meta.id,
                    'title': getattr(hit, 'name', '') or getattr(hit, 'code', ''),
                    'text': getattr(hit, 'specification', '') or getattr(hit, 'name', ''),
                    'score': hit.meta.score,
                }
            )
    return results[:top_k]


def _db_retrieve(query: str, top_k: int) -> list[dict]:
    """数据库 icontains 回落检索(无 ES 时的降级实现)。"""
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
    except Exception:  # pragma: no cover - 降级检索不应影响主流程
        logger.exception('RAG DB 回落检索(物料)失败')

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
        except Exception:  # pragma: no cover - 降级检索不应影响主流程
            logger.exception('RAG DB 回落检索(项目)失败')

    return results[:top_k]


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """检索与 query 相关的上下文片段。

    返回统一结构: [{source, id, title, text, score}, ...]。
    先尝试 ES(若已部署),失败/未部署则回落到数据库 icontains。空 query 返回空列表。
    """
    query = (query or '').strip()
    if not query:
        return []
    if top_k is None:
        top_k = getattr(settings, 'AI_RAG_TOP_K', 5)

    # 仅当配置了 ES 主机时才尝试 ES,避免在未部署 ES 的环境反复连接超时。
    es_host = None
    try:
        es_host = settings.ELASTICSEARCH_DSL['default'].get('hosts')
    except Exception:  # pragma: no cover
        es_host = None

    if es_host:
        try:
            hits = _es_retrieve(query, top_k)
            if hits:
                return hits
        except Exception:
            logger.warning('RAG ES 检索失败,回落到数据库 icontains', exc_info=True)

    return _db_retrieve(query, top_k)
