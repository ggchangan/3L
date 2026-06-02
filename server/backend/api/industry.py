"""行业板块路由"""
from . import parse_query
from backend.services.market_service import (
    get_industry_boards, get_concept_boards, get_industry_map,
    get_sector_chart,
)
from backend.services.knowledge_service import get_kb_list, get_kb_content


def _handle_industry_boards(h, path):
    h.send_json(get_industry_boards())


def _handle_concept_boards(h, path):
    h.send_json(get_concept_boards())


def _handle_industry_map(h, path):
    h.send_json(get_industry_map())


def _handle_industry_list(h, path):
    h.send_json(get_kb_list('industry'))


def _handle_industry_content(h, path):
    file_name = parse_query(path).get('file', [''])[0]
    if not file_name:
        h.send_json({'error': 'missing file param'})
        return
    h.send_json(get_kb_content(file_name, 'industry'))


def _handle_sector_chart(h, path):
    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(path).query)
    name = qs.get('name', [None])[0]
    board_type = qs.get('type', ['industry'])[0]  # industry | concept
    if not name:
        h.send_json({'error': 'missing name param'})
        return
    svg_path, err = get_sector_chart(name, board_type)
    if err:
        h.send_json({'error': err})
        return
    h._serve_file(svg_path, 'image/svg+xml')


def register_routes(routes):
    routes.exact('/api/industry-boards', func=_handle_industry_boards)
    routes.exact('/api/concept-boards', func=_handle_concept_boards)
    routes.exact('/api/industry-map', func=_handle_industry_map)
    routes.exact('/api/industry/list', func=_handle_industry_list)
    routes.exact('/api/industry/content', func=_handle_industry_content)
    routes.exact('/api/sector-chart', func=_handle_sector_chart)
    return routes
