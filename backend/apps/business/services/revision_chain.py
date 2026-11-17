"""非标件的版本链：同图号的换版记录把旧版指向新版，沿链找到最新的在用版本。

只认同图号的换版（升版或同图号替换）；换成另一个型号是该项目自己的替代，不代表旧物料过时。
同一旧版在不同项目换版时取最近一次；改回旧版形成环时，以环里最近一次换版的新版为准。
"""

from ..models import Item, Project, RevisionChange


def drawing(value):
    return (value or '').strip().casefold()


def successors(item_ids):
    """{旧物料: (新物料, 换版记录 ID)}：沿链向后取全部同图号换版边，每个旧物料只留最近一次。"""
    edges, queried, frontier = {}, set(), {pk for pk in item_ids if pk}
    while frontier:
        queried |= frontier
        found = {}
        for old, new, pk, old_drawing, new_drawing in (
            RevisionChange.objects.filter(old_item_id__in=frontier)
            .values_list('old_item_id', 'new_item_id', 'pk', 'old_item__drawing_number', 'new_item__drawing_number')
            .order_by('pk')
        ):
            if old != new and drawing(old_drawing) and drawing(old_drawing) == drawing(new_drawing):
                found[old] = (new, pk)
        edges.update(found)
        frontier = {new for new, _ in found.values()} - queried
    return edges


def latest_ids(item_ids):
    """{物料: 最新版本物料}，只列确有更新版本的物料。"""
    edges = successors(item_ids)
    paths = {}
    for start in item_ids:
        path, node = [start], start
        while node in edges:
            following = edges[node][0]
            if following in path:
                # 改回旧版形成环：环里最近一次换版的新版是当前版本。
                cycle = path[path.index(following) :]
                path.append(max((edges[pk] for pk in cycle), key=lambda edge: edge[1])[0])
                break
            path.append(following)
            node = following
        if len(path) > 1:
            paths[start] = path
    if not paths:
        return {}
    active = set(
        Item.objects.filter(pk__in={pk for path in paths.values() for pk in path}, is_active=True).values_list(
            'pk', flat=True
        )
    )
    result = {}
    for start, path in paths.items():
        # 最新版本停用时退回链上最近的在用版本；退回到自己说明没有可用的新版。
        latest = next((pk for pk in reversed(path[1:]) if pk in active), None)
        if latest is not None and latest != start:
            result[start] = latest
    return result


def newer(item_ids):
    """{物料: 最新版本摘要}，供列表、BOM 和导入提示「该图已有新版」。"""
    ids = [pk for pk in dict.fromkeys(item_ids) if pk]
    latest = latest_ids(ids)
    if not latest:
        return {}
    items = Item.objects.in_bulk(set(latest.values()))
    return {
        pk: {
            'id': items[target].pk,
            'code': items[target].code,
            'name': items[target].name,
            'drawing_revision': items[target].drawing_revision,
        }
        for pk, target in latest.items()
    }


def label(row):
    revision = row['drawing_revision']
    return f'{revision} 版（{row["code"]}）' if revision else row['code']


def history(actor, item):
    """同图号的全部版本，以及当前用户可见项目里涉及这些版本的换版记录（最新在前）。"""
    from apps.core.permissions import OPERATION_ROLES, has_role, projects_for

    if not drawing(item.drawing_number):
        return {'drawing_number': '', 'versions': [], 'changes': []}
    versions = list(Item.objects.filter(drawing_number__iexact=item.drawing_number.strip()).order_by('pk'))
    ids = [version.pk for version in versions]
    latest = latest_ids(ids)
    current = set(latest.values())
    codes = {version.pk: version.code for version in versions}
    changes = RevisionChange.objects.none()
    if has_role(actor, OPERATION_ROLES):
        changes = (
            RevisionChange.objects.filter(old_item_id__in=ids, new_item_id__in=ids)
            .filter(project__in=projects_for(actor, Project.objects.all()))
            .select_related('project', 'old_item', 'new_item', 'created_by')
            .order_by('-pk')[:200]
        )
    return {
        'drawing_number': item.drawing_number,
        'versions': [
            {
                'id': version.pk,
                'code': version.code,
                'name': version.name,
                'specification': version.specification,
                'drawing_revision': version.drawing_revision,
                'is_active': version.is_active,
                'superseded_by': codes.get(latest[version.pk], '') if version.pk in latest else '',
                'latest': version.pk in current,
            }
            for version in versions
        ],
        'changes': [
            {
                'id': change.pk,
                'created_at': change.created_at,
                'created_by': (change.created_by.display_name or change.created_by.username)
                if change.created_by
                else '',
                'project': change.project_id,
                'project_code': change.project.code,
                'project_name': change.project.name,
                'assembly_unit': change.assembly_unit,
                'old_item_code': change.old_item.code,
                'old_revision': change.old_item.drawing_revision,
                'new_item_code': change.new_item.code,
                'new_revision': change.new_item.drawing_revision,
                'old_quantity': str(change.old_quantity),
                'new_quantity': str(change.new_quantity),
                'converted_quantity': str(change.converted_quantity),
                'reason': change.reason,
            }
            for change in changes
        ],
    }
