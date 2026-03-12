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
