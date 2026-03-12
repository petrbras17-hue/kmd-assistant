"""
Инструменты для создания диаграмм и визуализаций КМД.
"""

import os


def create_kmd_flowchart(output_path: str = "kmd_process.png"):
    """Создать блок-схему процесса проверки КМД."""
    import graphviz

    dot = graphviz.Digraph(comment="Процесс проверки КМД", format="png")
    dot.attr(rankdir="TB", fontname="Arial")
    dot.attr("node", shape="box", style="rounded,filled", fillcolor="#E8F0FE", fontname="Arial")

    dot.node("A", "Получение КМД\nот проектировщика")
    dot.node("B", "Проверка комплектности\nдокументации")
    dot.node("C", "Проверка чертежей\n(геометрия, размеры)")
    dot.node("D", "Проверка спецификаций\n(марки стали, болты)")
    dot.node("E", "Проверка узлов\nи соединений")
    dot.node("F", "Формирование\nзамечаний")
    dot.node("G", "Отчёт об ошибках", fillcolor="#FCE4EC")
    dot.node("H", "КМД утверждён", fillcolor="#E8F5E9")

    dot.edge("A", "B")
    dot.edge("B", "C")
    dot.edge("C", "D")
    dot.edge("D", "E")
    dot.edge("E", "F")
    dot.edge("F", "G", label="есть ошибки")
    dot.edge("F", "H", label="нет ошибок")
    dot.edge("G", "A", label="на доработку", style="dashed")

    dot.render(output_path.replace(".png", ""), cleanup=True)
    print(f"Диаграмма сохранена: {output_path}")


def create_error_chart(errors: dict, output_path: str = "errors_chart.png"):
    """Создать диаграмму распределения ошибок по типам.

    errors: {"Геометрия": 5, "Размеры": 3, "Спецификация": 2, ...}
    """
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.rcParams["font.family"] = "Arial"

    fig, ax = plt.subplots(figsize=(10, 6))
    categories = list(errors.keys())
    values = list(errors.values())

    colors = ["#4285F4", "#EA4335", "#FBBC05", "#34A853", "#FF6D01", "#46BDC6"]
    bars = ax.barh(categories, values, color=colors[:len(categories)])
    ax.set_xlabel("Количество ошибок")
    ax.set_title("Распределение ошибок КМД по типам")

    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontweight="bold")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"График сохранён: {output_path}")


def create_comparison_table(data: list, output_path: str = "comparison.png"):
    """Создать визуальную таблицу сравнения (ошибочный vs правильный).

    data: [{"параметр": "...", "ошибка": "...", "правильно": "..."}, ...]
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, max(3, len(data) * 0.6)))
    ax.axis("off")

    headers = ["Параметр", "Ошибочный вариант", "Правильный вариант"]
    cell_text = [[d.get("параметр", ""), d.get("ошибка", ""), d.get("правильно", "")] for d in data]

    table = ax.table(
        cellText=cell_text,
        colLabels=headers,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)

    # Цвета заголовков
    for j in range(3):
        table[0, j].set_facecolor("#4285F4")
        table[0, j].set_text_props(color="white", fontweight="bold")

    # Подсветка ошибок красным
    for i in range(1, len(cell_text) + 1):
        table[i, 1].set_facecolor("#FFCDD2")
        table[i, 2].set_facecolor("#C8E6C9")

    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Таблица сохранена: {output_path}")


if __name__ == "__main__":
    # Пример: создать все демо-диаграммы
    os.makedirs("output", exist_ok=True)

    create_kmd_flowchart("output/kmd_process.png")

    create_error_chart({
        "Геометрия": 8,
        "Размеры": 5,
        "Спецификация": 4,
        "Узлы/соединения": 3,
        "Штамп": 2,
        "Оформление": 1,
    }, "output/errors_chart.png")

    create_comparison_table([
        {"параметр": "Марка стали", "ошибка": "С245", "правильно": "С345"},
        {"параметр": "Толщина фасонки", "ошибка": "8 мм", "правильно": "10 мм"},
        {"параметр": "Диаметр болтов", "ошибка": "М16", "правильно": "М20"},
    ], "output/comparison.png")
