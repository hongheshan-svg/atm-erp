"""
Performance check management command.
Analyzes system performance and provides optimization suggestions.
"""
import time

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Run comprehensive performance check on the system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== ERP System Performance Check ===\n'))

        # 1. Database Performance
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Database Performance ---'))
        self.check_database_performance()

        # 2. Cache Performance
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Cache Performance ---'))
        self.check_cache_performance()

        # 3. Query Analysis
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Query Analysis ---'))
        self.analyze_common_queries()

        # 4. Index Check
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Index Analysis ---'))
        self.check_indexes()

        # 5. Celery Status
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Celery Status ---'))
        self.check_celery_status()

        # 6. System Resources
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- System Resources ---'))
        self.check_system_resources()

        # 7. Optimization Suggestions
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Optimization Suggestions ---'))
        self.provide_suggestions()

    def check_database_performance(self):
        """Check database connection and basic performance."""
        try:
            # Test connection speed
            start = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            latency = (time.time() - start) * 1000

            self.stdout.write(f'  Database latency: {latency:.2f}ms')

            if latency > 100:
                self.stdout.write(self.style.WARNING('  ⚠ High database latency'))
            else:
                self.stdout.write(self.style.SUCCESS('  ✓ Database latency is good'))

            # Check table sizes
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
                    FROM pg_catalog.pg_statio_user_tables
                    ORDER BY pg_total_relation_size(relid) DESC
                    LIMIT 10
                """)
                tables = cursor.fetchall()

            self.stdout.write('\n  Top 10 largest tables:')
            for table, size in tables:
                self.stdout.write(f'    - {table}: {size}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error checking database: {e}'))

    def check_cache_performance(self):
        """Check Redis cache performance."""
        try:
            from django.core.cache import cache

            # Test cache speed
            start = time.time()
            cache.set('perf_test', 'test_value', 10)
            cache.get('perf_test')
            cache.delete('perf_test')
            latency = (time.time() - start) * 1000

            self.stdout.write(f'  Cache latency: {latency:.2f}ms')

            if latency > 50:
                self.stdout.write(self.style.WARNING('  ⚠ High cache latency'))
            else:
                self.stdout.write(self.style.SUCCESS('  ✓ Cache latency is good'))

            # Get Redis stats
            try:
                from django_redis import get_redis_connection
                redis_conn = get_redis_connection("default")
                info = redis_conn.info()

                self.stdout.write(f'\n  Redis memory: {info.get("used_memory_human", "N/A")}')
                self.stdout.write(f'  Connected clients: {info.get("connected_clients", "N/A")}')

                hits = info.get('keyspace_hits', 0)
                misses = info.get('keyspace_misses', 0)
                total = hits + misses
                if total > 0:
                    hit_rate = (hits / total) * 100
                    self.stdout.write(f'  Cache hit rate: {hit_rate:.1f}%')

                    if hit_rate < 80:
                        self.stdout.write(self.style.WARNING('  ⚠ Low cache hit rate'))
                    else:
                        self.stdout.write(self.style.SUCCESS('  ✓ Good cache hit rate'))

            except Exception as e:
                self.stdout.write(f'  Could not get Redis stats: {e}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error checking cache: {e}'))

    def analyze_common_queries(self):
        """Analyze common query patterns."""
        try:
            with connection.cursor() as cursor:
                # Check for slow queries (PostgreSQL)
                cursor.execute("""
                    SELECT query, calls, mean_time, total_time
                    FROM pg_stat_statements
                    ORDER BY mean_time DESC
                    LIMIT 5
                """)
                slow_queries = cursor.fetchall()

                if slow_queries:
                    self.stdout.write('\n  Top 5 slowest queries (avg time):')
                    for query, calls, mean_time, total_time in slow_queries:
                        self.stdout.write(f'    - {mean_time:.2f}ms avg ({calls} calls)')
                        self.stdout.write(f'      {query[:100]}...')
                else:
                    self.stdout.write('  No query statistics available')
                    self.stdout.write('  (Enable pg_stat_statements extension for query analysis)')

        except Exception as e:
            self.stdout.write(f'  Query analysis not available: {e}')
            self.stdout.write('  Tip: Enable pg_stat_statements for query analysis')

    def check_indexes(self):
        """Check for missing or unused indexes."""
        try:
            with connection.cursor() as cursor:
                # Check for missing indexes
                cursor.execute("""
                    SELECT schemaname, relname, seq_scan, seq_tup_read,
                           idx_scan, idx_tup_fetch
                    FROM pg_stat_user_tables
                    WHERE seq_scan > idx_scan
                    AND seq_tup_read > 10000
                    ORDER BY seq_tup_read DESC
                    LIMIT 10
                """)
                missing_indexes = cursor.fetchall()

                if missing_indexes:
                    self.stdout.write(self.style.WARNING('\n  Tables that may need indexes:'))
                    for schema, table, seq_scan, seq_read, idx_scan, idx_fetch in missing_indexes:
                        self.stdout.write(
                            f'    - {table}: {seq_scan} seq scans vs {idx_scan} idx scans'
                        )
                else:
                    self.stdout.write(self.style.SUCCESS('  ✓ No obvious missing indexes'))

                # Check for unused indexes
                cursor.execute("""
                    SELECT schemaname, relname, indexrelname, idx_scan
                    FROM pg_stat_user_indexes
                    WHERE idx_scan = 0
                    AND indexrelname NOT LIKE '%_pkey'
                    LIMIT 10
                """)
                unused_indexes = cursor.fetchall()

                if unused_indexes:
                    self.stdout.write(self.style.WARNING('\n  Potentially unused indexes:'))
                    for schema, table, index, scans in unused_indexes:
                        self.stdout.write(f'    - {index} on {table}')
                else:
                    self.stdout.write(self.style.SUCCESS('  ✓ No unused indexes found'))

        except Exception as e:
            self.stdout.write(f'  Index analysis error: {e}')

    def check_celery_status(self):
        """Check Celery worker status."""
        try:
            from celery import current_app

            inspect = current_app.control.inspect()

            # Check active workers
            active = inspect.active()
            if active:
                self.stdout.write(f'  Active workers: {len(active)}')
                for worker, tasks in active.items():
                    self.stdout.write(f'    - {worker}: {len(tasks)} active tasks')
            else:
                self.stdout.write(self.style.WARNING('  ⚠ No active Celery workers'))

            # Check scheduled tasks
            scheduled = inspect.scheduled()
            if scheduled:
                total_scheduled = sum(len(v) for v in scheduled.values())
                self.stdout.write(f'  Scheduled tasks: {total_scheduled}')

            # Check reserved tasks
            reserved = inspect.reserved()
            if reserved:
                total_reserved = sum(len(v) for v in reserved.values())
                self.stdout.write(f'  Reserved tasks: {total_reserved}')

        except Exception as e:
            self.stdout.write(f'  Celery status unavailable: {e}')

    def check_system_resources(self):
        """Check system resource usage."""
        try:
            import psutil

            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            self.stdout.write(f'  CPU usage: {cpu_percent}%')
            if cpu_percent > 80:
                self.stdout.write(self.style.WARNING('  ⚠ High CPU usage'))

            # Memory
            memory = psutil.virtual_memory()
            self.stdout.write(f'  Memory usage: {memory.percent}%')
            self.stdout.write(f'  Memory available: {memory.available / (1024**3):.1f} GB')
            if memory.percent > 85:
                self.stdout.write(self.style.WARNING('  ⚠ High memory usage'))

            # Disk
            disk = psutil.disk_usage('/')
            self.stdout.write(f'  Disk usage: {disk.percent}%')
            if disk.percent > 90:
                self.stdout.write(self.style.WARNING('  ⚠ High disk usage'))

        except ImportError:
            self.stdout.write('  psutil not installed - install for system metrics')
        except Exception as e:
            self.stdout.write(f'  System resource check error: {e}')

    def provide_suggestions(self):
        """Provide optimization suggestions."""
        suggestions = [
            '1. Enable database connection pooling (pgbouncer)',
            '2. Use select_related() and prefetch_related() for related objects',
            '3. Add database indexes for frequently filtered fields',
            '4. Implement pagination for large querysets',
            '5. Use caching for expensive computations',
            '6. Enable query result caching for read-heavy endpoints',
            '7. Use async tasks (Celery) for long-running operations',
            '8. Optimize N+1 queries using Django Debug Toolbar',
            '9. Consider read replicas for read-heavy workloads',
            '10. Monitor slow queries and optimize them',
        ]

        for suggestion in suggestions:
            self.stdout.write(f'  {suggestion}')
