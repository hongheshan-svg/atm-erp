"""
Performance monitoring and optimization utilities.
"""
import time
import logging
import functools
from django.db import connection, reset_queries
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def query_debugger(func):
    """
    Decorator to log database queries for a function.
    Only active when DEBUG=True.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not settings.DEBUG:
            return func(*args, **kwargs)
        
        reset_queries()
        start_time = time.time()
        
        result = func(*args, **kwargs)
        
        end_time = time.time()
        queries = connection.queries
        
        total_time = sum(float(q['time']) for q in queries)
        
        logger.debug(
            f'{func.__name__}: {len(queries)} queries in {total_time:.3f}s '
            f'(total: {end_time - start_time:.3f}s)'
        )
        
        # Log slow queries
        for query in queries:
            if float(query['time']) > 0.1:  # More than 100ms
                logger.warning(f"Slow query ({query['time']}s): {query['sql'][:200]}")
        
        return result
    return wrapper


def cache_result(timeout=300, key_prefix=''):
    """
    Decorator to cache function results.
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Prefix for cache key
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


class PerformanceMonitor:
    """
    Performance monitoring utilities.
    """
    
    @classmethod
    def get_database_stats(cls):
        """Get database connection statistics."""
        from django.db import connections
        
        stats = {}
        for alias in connections:
            conn = connections[alias]
            stats[alias] = {
                'queries_count': len(conn.queries) if settings.DEBUG else 'N/A (DEBUG=False)',
                'vendor': conn.vendor,
            }
        return stats
    
    @classmethod
    def get_cache_stats(cls):
        """Get cache statistics."""
        try:
            # Try to get Redis info
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            info = redis_conn.info()
            
            return {
                'used_memory': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 0),
                'total_commands': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': cls._calculate_hit_rate(
                    info.get('keyspace_hits', 0),
                    info.get('keyspace_misses', 0)
                ),
            }
        except Exception as e:
            return {'error': str(e)}
    
    @classmethod
    def _calculate_hit_rate(cls, hits, misses):
        total = hits + misses
        if total == 0:
            return 'N/A'
        return f"{(hits / total) * 100:.2f}%"
    
    @classmethod
    def get_celery_stats(cls):
        """Get Celery worker statistics."""
        try:
            from celery import current_app
            
            inspect = current_app.control.inspect()
            
            return {
                'active_workers': list(inspect.active().keys()) if inspect.active() else [],
                'active_tasks': sum(len(v) for v in (inspect.active() or {}).values()),
                'scheduled_tasks': sum(len(v) for v in (inspect.scheduled() or {}).values()),
                'reserved_tasks': sum(len(v) for v in (inspect.reserved() or {}).values()),
            }
        except Exception as e:
            return {'error': str(e)}
    
    @classmethod
    def get_system_health(cls):
        """Get overall system health status."""
        import psutil
        
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'percent': psutil.virtual_memory().percent,
            },
            'disk': {
                'total': psutil.disk_usage('/').total,
                'used': psutil.disk_usage('/').used,
                'percent': psutil.disk_usage('/').percent,
            },
        }


class QueryOptimizer:
    """
    Query optimization utilities.
    """
    
    @staticmethod
    def analyze_queryset(queryset):
        """
        Analyze a queryset for potential optimizations.
        
        Returns suggestions for improving query performance.
        """
        suggestions = []
        
        # Check for select_related opportunities
        model = queryset.model
        fk_fields = [
            f.name for f in model._meta.get_fields()
            if f.is_relation and f.many_to_one
        ]
        
        if fk_fields and not queryset.query.select_related:
            suggestions.append({
                'type': 'select_related',
                'message': f'Consider using select_related for: {", ".join(fk_fields)}',
                'severity': 'warning'
            })
        
        # Check for prefetch_related opportunities
        m2m_fields = [
            f.name for f in model._meta.get_fields()
            if f.is_relation and f.many_to_many
        ]
        
        if m2m_fields and not queryset._prefetch_related_lookups:
            suggestions.append({
                'type': 'prefetch_related',
                'message': f'Consider using prefetch_related for: {", ".join(m2m_fields)}',
                'severity': 'info'
            })
        
        # Check for missing indexes (basic check)
        if queryset.query.where:
            suggestions.append({
                'type': 'index',
                'message': 'Ensure filtered fields have database indexes',
                'severity': 'info'
            })
        
        return suggestions


# Performance check management command helper
def run_performance_check():
    """
    Run comprehensive performance check.
    Returns dict with all performance metrics.
    """
    monitor = PerformanceMonitor()
    
    results = {
        'database': monitor.get_database_stats(),
        'cache': monitor.get_cache_stats(),
        'celery': monitor.get_celery_stats(),
    }
    
    try:
        results['system'] = monitor.get_system_health()
    except ImportError:
        results['system'] = {'error': 'psutil not installed'}
    
    return results
