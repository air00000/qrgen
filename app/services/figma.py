import requests, logging
from app.config import CFG

log = logging.getLogger(__name__)

def get_headers():
    return {"X-FIGMA-TOKEN": CFG.FIGMA_PAT}

def get_template_json():
    url = f"{CFG.FIGMA_API_URL}/files/{CFG.TEMPLATE_FILE_KEY}"
    r = requests.get(url, headers=get_headers())
    r.raise_for_status()
    return r.json()

def find_node(file_json, page_name, node_name):
    for page in file_json["document"]["children"]:
        if page["name"] == page_name:
            def walk(node):
                if node.get("name") == node_name:
                    return node
                for ch in node.get("children", []):
                    f = walk(ch)
                    if f: return f
            return walk(page)
    return None

def export_frame_as_png(file_key, node_id, scale=CFG.SCALE_FACTOR):
    url = f'{CFG.FIGMA_API_URL}/images/{file_key}?ids={node_id}&format=png&scale={scale}'
    r = requests.get(url, headers=get_headers())
    r.raise_for_status()
    png_url = r.json()["images"][node_id]
    img = requests.get(png_url)
    img.raise_for_status()
    return img.content


def find_node_anywhere(file_json, node_name: str):
    """
    Глубокий рекурсивный поиск узла по имени во всём JSON-файле Figma.
    Возвращает первый найденный элемент с совпадающим 'name'.
    """
    def walk(node):
        if isinstance(node, dict):
            if node.get("name") == node_name:
                return node
            for child in node.get("children", []):
                res = walk(child)
                if res:
                    return res
        elif isinstance(node, list):
            for item in node:
                res = walk(item)
                if res:
                    return res
        return None

    return walk(file_json.get("document", {}))
