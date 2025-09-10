import requests, logging
from config import CFG

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
