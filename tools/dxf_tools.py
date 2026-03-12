"""
Инструменты для работы с DXF чертежами (AutoCAD) — КМД, узлы, детали.
"""

import sys


def read_dxf_info(file_path: str) -> dict:
    """Получить информацию о DXF файле."""
    import ezdxf
    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    entities = {}
    for entity in msp:
        etype = entity.dxftype()
        entities[etype] = entities.get(etype, 0) + 1

    layers = [layer.dxf.name for layer in doc.layers]

    return {
        "version": doc.dxfversion,
        "layers": layers,
        "entities": entities,
        "total_entities": sum(entities.values()),
    }


def extract_text_from_dxf(file_path: str) -> list:
    """Извлечь все текстовые элементы из DXF."""
    import ezdxf
    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    texts = []
    for entity in msp.query("TEXT MTEXT"):
        if entity.dxftype() == "TEXT":
            texts.append({
                "text": entity.dxf.text,
                "position": list(entity.dxf.insert),
                "height": entity.dxf.height,
                "layer": entity.dxf.layer,
            })
        elif entity.dxftype() == "MTEXT":
            texts.append({
                "text": entity.text,
                "position": list(entity.dxf.insert),
                "layer": entity.dxf.layer,
            })
    return texts


def extract_dimensions_from_dxf(file_path: str) -> list:
    """Извлечь размеры из DXF чертежа."""
    import ezdxf
    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    dims = []
    for entity in msp.query("DIMENSION"):
        dims.append({
            "type": entity.dxf.dimtype if hasattr(entity.dxf, "dimtype") else "unknown",
            "layer": entity.dxf.layer,
            "text": getattr(entity.dxf, "text", ""),
        })
    return dims


def dxf_to_image(file_path: str, output_path: str):
    """Экспортировать DXF в PNG изображение."""
    import ezdxf
    from ezdxf.addons.drawing import matplotlib as draw_mpl

    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    import matplotlib.pyplot as plt
    fig = plt.figure(dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = draw_mpl.MatplotlibBackend(ax)

    from ezdxf.addons.drawing import Frontend, RenderContext
    frontend = Frontend(RenderContext(doc), ctx)
    frontend.draw_layout(msp)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    print(f"Сохранено: {output_path}")


def parse_dxf_for_web(file_path: str) -> dict:
    """Полный разбор DXF для веб-интерфейса: тексты, размеры, блоки, слои, КМД-данные."""
    import re
    import ezdxf

    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    # --- Слои ---
    layer_entity_counts: dict[str, int] = {}
    for entity in msp:
        layer = entity.dxf.layer
        layer_entity_counts[layer] = layer_entity_counts.get(layer, 0) + 1

    layers = [
        {"name": layer.dxf.name, "entity_count": layer_entity_counts.get(layer.dxf.name, 0)}
        for layer in doc.layers
    ]

    # --- Тексты (TEXT + MTEXT) ---
    texts = []
    for entity in msp.query("TEXT MTEXT"):
        if entity.dxftype() == "TEXT":
            content = entity.dxf.text
            position = list(entity.dxf.insert)
        else:
            content = entity.text
            position = list(entity.dxf.insert)
        texts.append({
            "layer": entity.dxf.layer,
            "content": content,
            "position": [round(c, 2) for c in position],
        })

    # --- Размеры (DIMENSION) ---
    dimensions = []
    for entity in msp.query("DIMENSION"):
        dim_text = getattr(entity.dxf, "text", "")
        # Попробуем получить measurement (реальное значение)
        measurement = getattr(entity, "measurement", None)
        if measurement is not None:
            value = round(measurement, 2)
        elif dim_text:
            # Попробуем извлечь число из текста
            m = re.search(r'[\d]+[,\.]?\d*', dim_text.replace(",", "."))
            value = float(m.group()) if m else None
        else:
            value = None
        dimensions.append({
            "layer": entity.dxf.layer,
            "value": value,
            "unit": "mm",
        })

    # --- Блоки (INSERT) ---
    block_counts: dict[str, int] = {}
    for entity in msp.query("INSERT"):
        name = entity.dxf.name
        block_counts[name] = block_counts.get(name, 0) + 1
    blocks = [{"name": n, "count": c} for n, c in sorted(block_counts.items())]

    # --- КМД-данные: позиции, артикулы, профили ---
    all_content = [t["content"] for t in texts]

    positions = []
    articles = []
    profiles = []

    for text in all_content:
        # Позиции: Поз.О-1, Поз.1, Поз.A2, поз 5 и т.д.
        for m in re.finditer(r'[Пп]оз\.?\s*([А-Яа-яA-Za-z]?\-?\d+[\-\.\w]*)', text):
            val = m.group(1).strip()
            if val and val not in positions:
                positions.append(val)

        # Артикулы: 7-8 цифр или формат XXXX.XXXX
        for m in re.finditer(r'\b(\d{7,8})\b', text):
            art = m.group(1)
            if int(art) > 100000 and art not in articles:
                articles.append(art)
        for m in re.finditer(r'\b(\d{4,5}\.\d{3,5})\b', text):
            art = m.group(1)
            if art not in articles:
                articles.append(art)

        # Профили: типичные обозначения КМД
        for m in re.finditer(
            r'(?:профиль|проф\.?|труба|швеллер|уголок|двутавр|лист)\s*[А-Яа-яA-Za-z0-9\.\-\×xх\s]{2,30}',
            text, re.IGNORECASE
        ):
            val = m.group(0).strip()
            if val not in profiles:
                profiles.append(val)

    kmd_data = {
        "positions": positions,
        "articles": articles,
        "profiles": profiles,
    }

    return {
        "layers": layers,
        "texts": texts,
        "dimensions": dimensions,
        "blocks": blocks,
        "kmd_data": kmd_data,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python dxf_tools.py <команда> <файл>")
        print("Команды: info, text, dims, image")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "info":
        import json
        print(json.dumps(read_dxf_info(sys.argv[2]), ensure_ascii=False, indent=2))
    elif cmd == "text":
        import json
        print(json.dumps(extract_text_from_dxf(sys.argv[2]), ensure_ascii=False, indent=2))
    elif cmd == "dims":
        import json
        print(json.dumps(extract_dimensions_from_dxf(sys.argv[2]), ensure_ascii=False, indent=2))
    elif cmd == "image":
        out = sys.argv[3] if len(sys.argv) > 3 else "output.png"
        dxf_to_image(sys.argv[2], out)
