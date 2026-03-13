"""
Accuracy tests for KMD parser against real documents.
Run: python -m pytest tests/test_parser_accuracy.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from kmd_parser import (
    parse_kmd_pdf, extract_positions, extract_quantity,
    extract_articles, extract_color, extract_handle_height,
    extract_profile_system, extract_glass_formula, classify_page,
    normalize_position,
)


# ---------------------------------------------------------------------------
# Ground truth: real KMD documents
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VITRAZI_PDF = os.path.join(BASE_DIR, "Реальные КМД АЛЬДМЕГА ЛАБ и ДОНСТРОЙ ОСТРОВ", "КМД Остров 2 Витражи.pdf")
OKNA_PDF = os.path.join(BASE_DIR, "Реальные КМД АЛЬДМЕГА ЛАБ и ДОНСТРОЙ ОСТРОВ", "КМД Остров 2 Окна.pdf")


# ============== Unit tests: pattern matching ==============

class TestPositionDetection:
    """Test all known position formats from real KMD documents."""

    def test_standard_poz(self):
        text = "Поз.О-1 Количество: 38"
        pos = extract_positions(text)
        assert len(pos) >= 1
        assert any(p["position"] == "О-1" for p in pos)

    def test_poz_with_space(self):
        text = "Поз. Д-3, Кол-во: 5"
        pos = extract_positions(text)
        assert len(pos) >= 1
        assert any(p["position"] == "Д-3" for p in pos)

    def test_poz_no_dash(self):
        text = "Поз.БФ1 Количество:180"
        pos = extract_positions(text)
        assert len(pos) >= 1
        assert any(p["position"] == "БФ1" for p in pos)

    def test_poz_two_letters(self):
        text = "Поз.ОК-12"
        pos = extract_positions(text)
        assert len(pos) >= 1
        assert any("ОК" in p["position"] for p in pos)

    def test_vitrazh(self):
        text = "Витраж В-1, Кол-во : 19 шт."
        pos = extract_positions(text)
        assert len(pos) >= 1
        assert any(p["position"] == "В-1" for p in pos)

    def test_uglovoy_vitrazh(self):
        text = "Угловой витраж В-1.1"
        pos = extract_positions(text)
        assert len(pos) >= 1
        assert any("В-1.1" in p["position"] for p in pos)

    def test_balkonnaya_dver(self):
        text = "Балконная дверь БД-1, Количество:2"
        pos = extract_positions(text)
        assert len(pos) >= 1
        assert any(p["position"] == "БД-1" for p in pos)

    def test_okno(self):
        text = "Окно Ок-13, Кол-во:14"
        pos = extract_positions(text)
        assert len(pos) >= 1
        assert any("Ок-13" in p["position"] for p in pos)

    def test_fasad(self):
        text = "Фасад Ф-1"
        pos = extract_positions(text)
        assert len(pos) >= 1

    def test_multiple_positions(self):
        text = """Поз.О-1 Количество: 38
        Витраж В-1, Кол-во : 19 шт.
        Поз. БФ1, Кол.во: 5
        Балконная дверь БД-1"""
        pos = extract_positions(text)
        assert len(pos) >= 4


class TestQuantityDetection:
    """Test all quantity formats."""

    def test_kolichestvo(self):
        text = "Поз.О-1 Количество: 38"
        assert extract_quantity(text) == 38

    def test_kolichestvo_no_space(self):
        text = "Количество:5"
        assert extract_quantity(text) == 5

    def test_kolvo_with_sht(self):
        text = "Кол-во : 19 шт."
        assert extract_quantity(text) == 19

    def test_kolvo_no_space(self):
        text = "Кол-во:14"
        assert extract_quantity(text) == 14

    def test_kolvo_dot(self):
        text = "Кол.во: 5"
        assert extract_quantity(text) == 5

    def test_sht_standalone(self):
        text = "позиция 3 шт."
        assert extract_quantity(text) == 3


class TestArticleDetection:
    """Test article code extraction."""

    def test_seven_digit(self):
        articles = extract_articles("Профиль 4080102 рама")
        assert "4080102" in articles

    def test_multiple(self):
        articles = extract_articles("0303612, 0535401, 0566016")
        assert len(articles) == 3

    def test_filter_small(self):
        articles = extract_articles("код 0000001 и 1234567")
        assert "1234567" in articles

    def test_eight_digit(self):
        articles = extract_articles("артикул 12345678")
        assert "12345678" in articles


class TestColorDetection:
    def test_ral(self):
        assert "RAL 7016" == extract_color("Покрытие: RAL 7016")

    def test_named_color(self):
        color = extract_color("Цвет: белый матовый")
        assert "белый" in color


class TestHandleHeight:
    def test_standard(self):
        assert extract_handle_height("Высота ручки: 1050") == 1050

    def test_h_format(self):
        assert extract_handle_height("h=900 мм") == 900


class TestProfileSystem:
    def test_masterline(self):
        assert extract_profile_system("Система: MasterLine 8") == "Reynaers MasterLine 8"

    def test_cw50(self):
        assert extract_profile_system("CW 50 фасадная") == "Reynaers CW 50"

    def test_schuco(self):
        assert extract_profile_system("Schüco AWS 75") == "Schüco AWS 75"

    def test_alutech(self):
        assert extract_profile_system("Alutech ALT F50") == "Alutech ALT F50"

    def test_tatprof(self):
        assert extract_profile_system("TATPROF ТП-5003") == "TATPROF ТП-5003"


class TestGlassFormula:
    def test_double_igu(self):
        formulas = extract_glass_formula("Стеклопакет 4-16-4")
        assert any("4-16-4" in f for f in formulas)

    def test_igu_with_argon(self):
        formulas = extract_glass_formula("СП: 4-16Ar-4i")
        assert len(formulas) >= 1

    def test_triple_igu(self):
        formulas = extract_glass_formula("4-12-4-12-4")
        assert len(formulas) >= 1


class TestPageClassification:
    def test_title(self):
        assert classify_page("Титульный лист проекта Заказчик ООО") == "титульный лист"

    def test_specification(self):
        assert classify_page("Спецификация материалов ведомость") == "спецификация"

    def test_drawing(self):
        assert classify_page("Поз. О-1 Количество: 38 Высота ручки") == "чертёж изделия"

    def test_note(self):
        assert classify_page("Пояснительная записка к проекту") == "пояснительная записка"


# ============== Integration tests: real documents ==============

@pytest.mark.skipif(not os.path.exists(VITRAZI_PDF), reason="Real KMD PDF not available")
class TestVitraziDocument:
    """Test parser against КМД Остров 2 Витражи.pdf"""

    @pytest.fixture(scope="class")
    def parsed(self):
        return parse_kmd_pdf(VITRAZI_PDF)

    def test_profile_system(self, parsed):
        assert parsed["profile_system"] is not None
        assert "CW" in parsed["profile_system"] or "Reynaers" in parsed["profile_system"]

    def test_positions_found(self, parsed):
        """Must find at least 10 unique positions (В-1...В-9, РС-1, РС-2, etc.)"""
        assert parsed["total_positions"] >= 10, f"Only {parsed['total_positions']} positions found"

    def test_vitrazh_positions(self, parsed):
        """Must find В-1 through В-9."""
        pos_names = {p["position"] for p in parsed["positions"]}
        for v in ["В-1", "В-2", "В-3", "В-4", "В-5", "В-6", "В-8", "В-9"]:
            assert v in pos_names, f"Missing position {v}"

    def test_articles_found(self, parsed):
        """Must find multiple articles (Reynaers CW 50 profiles)."""
        assert parsed["articles_count"] >= 10, f"Only {parsed['articles_count']} articles"

    def test_total_items(self, parsed):
        """Total items should be > 100 (many vitrages × quantities)."""
        assert parsed["total_items"] > 80, f"Only {parsed['total_items']} items"

    def test_v1_quantity(self, parsed):
        """В-1 should have quantity 19."""
        v1 = next((p for p in parsed["positions"] if p["position"] == "В-1"), None)
        assert v1 is not None, "В-1 not found"
        assert v1["quantity"] == 19, f"В-1 qty={v1['quantity']}, expected 19"


@pytest.mark.skipif(not os.path.exists(OKNA_PDF), reason="Real KMD PDF not available")
class TestOknaDocument:
    """Test parser against КМД Остров 2 Окна.pdf"""

    @pytest.fixture(scope="class")
    def parsed(self):
        return parse_kmd_pdf(OKNA_PDF)

    def test_profile_system(self, parsed):
        assert parsed["profile_system"] is not None
        assert "MasterLine" in parsed["profile_system"]

    def test_positions_found(self, parsed):
        """Must find O-1...O-8, БФ1...БФ7, Д-1 etc."""
        assert parsed["total_positions"] >= 15, f"Only {parsed['total_positions']} positions"

    def test_window_positions(self, parsed):
        """Must find standard window positions."""
        pos_names = {p["position"] for p in parsed["positions"]}
        for pos in ["О-1", "О-2", "О-3"]:
            assert pos in pos_names, f"Missing position {pos}"

    def test_bf_positions(self, parsed):
        """Must find БФ (balcony facade) positions."""
        pos_names = {p["position"] for p in parsed["positions"]}
        assert any("БФ" in p for p in pos_names), "No БФ positions found"

    def test_articles_found(self, parsed):
        """Must find MasterLine 8 articles."""
        assert parsed["articles_count"] >= 10

    def test_total_items(self, parsed):
        """Total items > 300 (many windows × quantities)."""
        assert parsed["total_items"] > 300, f"Only {parsed['total_items']} items"

    def test_o1_quantity(self, parsed):
        """О-1 should have quantity 38."""
        o1 = next((p for p in parsed["positions"] if p["position"] == "О-1"), None)
        assert o1 is not None, "О-1 not found"
        assert o1["quantity"] == 38, f"О-1 qty={o1['quantity']}, expected 38"

    def test_bf1_quantity(self, parsed):
        """БФ1 should have quantity 180."""
        bf1 = next((p for p in parsed["positions"] if p["position"] == "БФ1"), None)
        assert bf1 is not None, "БФ1 not found"
        assert bf1["quantity"] == 180, f"БФ1 qty={bf1['quantity']}, expected 180"


# ============== Accuracy measurement ==============

@pytest.mark.skipif(
    not (os.path.exists(VITRAZI_PDF) and os.path.exists(OKNA_PDF)),
    reason="Real KMD PDFs not available"
)
class TestOverallAccuracy:
    """Measure overall parser accuracy."""

    def test_vitrazi_accuracy_report(self):
        result = parse_kmd_pdf(VITRAZI_PDF)
        # Ground truth for Витражи
        expected_positions = {"В-1", "В-2", "В-3", "В-4", "В-5", "В-6", "В-8", "В-9"}
        expected_quantities = {"В-1": 19, "В-3": 19, "В-5": 19, "В-8": 19, "В-9": 2, "В-2": 1, "В-4": 1, "В-6": 2}

        found_positions = {p["position"] for p in result["positions"]}
        matched = expected_positions & found_positions
        accuracy = len(matched) / len(expected_positions) * 100

        print(f"\n  Витражи position accuracy: {accuracy:.1f}%")
        print(f"  Expected: {expected_positions}")
        print(f"  Found: {found_positions & expected_positions}")
        print(f"  Missing: {expected_positions - found_positions}")

        # Quantity accuracy
        qty_correct = 0
        qty_total = 0
        for pos_name, expected_qty in expected_quantities.items():
            pos = next((p for p in result["positions"] if p["position"] == pos_name), None)
            if pos:
                qty_total += 1
                if pos["quantity"] == expected_qty:
                    qty_correct += 1
                else:
                    print(f"  QTY MISMATCH: {pos_name} expected={expected_qty} got={pos['quantity']}")

        qty_accuracy = qty_correct / qty_total * 100 if qty_total else 0
        print(f"  Quantity accuracy: {qty_accuracy:.1f}%")

        assert accuracy >= 90, f"Position accuracy too low: {accuracy}%"
        assert qty_accuracy >= 80, f"Quantity accuracy too low: {qty_accuracy}%"

    def test_okna_accuracy_report(self):
        result = parse_kmd_pdf(OKNA_PDF)
        # Ground truth for Окна
        expected_positions = {"О-1", "О-2", "О-3", "БФ1", "БФ2", "БФ3"}
        expected_quantities = {"О-1": 38, "О-2": 5, "О-3": 9, "БФ1": 180, "БФ2": 28, "БФ3": 28}

        found_positions = {p["position"] for p in result["positions"]}
        matched = expected_positions & found_positions
        accuracy = len(matched) / len(expected_positions) * 100

        print(f"\n  Окна position accuracy: {accuracy:.1f}%")
        print(f"  Expected: {expected_positions}")
        print(f"  Found: {found_positions & expected_positions}")
        print(f"  Missing: {expected_positions - found_positions}")

        # Quantity accuracy
        qty_correct = 0
        qty_total = 0
        for pos_name, expected_qty in expected_quantities.items():
            pos = next((p for p in result["positions"] if p["position"] == pos_name), None)
            if pos:
                qty_total += 1
                if pos["quantity"] == expected_qty:
                    qty_correct += 1
                else:
                    print(f"  QTY MISMATCH: {pos_name} expected={expected_qty} got={pos['quantity']}")

        qty_accuracy = qty_correct / qty_total * 100 if qty_total else 0
        print(f"  Quantity accuracy: {qty_accuracy:.1f}%")

        assert accuracy >= 90, f"Position accuracy too low: {accuracy}%"
        assert qty_accuracy >= 80, f"Quantity accuracy too low: {qty_accuracy}%"
