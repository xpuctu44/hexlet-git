from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from num2words import num2words
from datetime import datetime
from typing import List, Dict, Any
import os


_DEF_FONT = "DejaVuSans"
_DEF_FONT_BOLD = "DejaVuSans-Bold"


def _register_cyr_fonts() -> None:
	if _DEF_FONT in pdfmetrics.getRegisteredFontNames():
		return
	# Try common paths for DejaVuSans
	candidates = [
		"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
		"/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
	]
	regular_path = None
	bold_path = None
	for path in candidates:
		if path.endswith("DejaVuSans.ttf") and os.path.exists(path):
			regular_path = path
		if path.endswith("DejaVuSans-Bold.ttf") and os.path.exists(path):
			bold_path = path
	# Fallback: look in same dir (if user provided fonts there)
	local_reg = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
	local_bold = os.path.join(os.path.dirname(__file__), "DejaVuSans-Bold.ttf")
	if not regular_path and os.path.exists(local_reg):
		regular_path = local_reg
	if not bold_path and os.path.exists(local_bold):
		bold_path = local_bold
	# Register at least regular
	if regular_path:
		pdfmetrics.registerFont(TTFont(_DEF_FONT, regular_path))
	else:
		# As a last resort, try to register FreeSans if present
		free_sans = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
		if os.path.exists(free_sans):
			pdfmetrics.registerFont(TTFont(_DEF_FONT, free_sans))
		else:
			# If we cannot register, keep defaults; but Cyrillic may still fail
			return
	if bold_path:
		pdfmetrics.registerFont(TTFont(_DEF_FONT_BOLD, bold_path))
	else:
		# If bold missing, alias bold to regular
		pdfmetrics.registerFont(TTFont(_DEF_FONT_BOLD, regular_path))


def _rub_text(amount: float) -> str:
	amount = round(float(amount), 2)
	rub = int(amount)
	kop = int(round((amount - rub) * 100))
	words = num2words(rub, lang="ru")
	return f"{words} рублей {kop:02d} копеек"


def _P(text: Any, style: ParagraphStyle) -> Paragraph:
	return Paragraph(str(text), style)


def generate_order_pdf(
	output_path: str,
	order_number: int,
	customer: Dict[str, str],
	vehicle: Dict[str, str],
	works: List[Dict[str, Any]],
	parts: List[Dict[str, Any]],
	station_phone: str = "+79782091007",
	executor_name: str = "Даниил",
) -> None:
	_register_cyr_fonts()
	styles = getSampleStyleSheet()
	# Clone and set Cyrillic-capable fonts
	styleN = ParagraphStyle("CyrNormal", parent=styles["Normal"], fontName=_DEF_FONT, fontSize=10, leading=12)
	styleB = ParagraphStyle("CyrBold", parent=styles["Heading3"], fontName=_DEF_FONT_BOLD, fontSize=11, leading=13)
	styleTitle = ParagraphStyle("CyrTitle", parent=styles["Title"], fontName=_DEF_FONT_BOLD)
	styleH1 = ParagraphStyle("CyrH1", parent=styles["Heading1"], fontName=_DEF_FONT_BOLD)
	styleH2 = ParagraphStyle("CyrH2", parent=styles["Heading2"], fontName=_DEF_FONT_BOLD)

	doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
	story = []

	# Header with VAG logos placeholder (text header for now)
	header = _P("VAG Group: Audi · Volkswagen · Skoda · SEAT · Porsche", styleTitle)
	story.append(header)
	story.append(Spacer(1, 4*mm))

	# Station info and order meta
	meta_table = Table([
		[
			_P(f"Станция тех. обслуживания<br/>Телефон: {station_phone}", styleN),
			_P("Вид ремонта: техническое обслуживание", styleN),
		],
		[
			_P(f"Заказ-наряд № {order_number}", styleH1),
			_P(datetime.now().strftime("%d.%m.%Y"), styleN),
		],
	])
	meta_table.setStyle(TableStyle([
		("VALIGN", (0,0), (-1,-1), "TOP"),
	]))
	story.append(meta_table)
	story.append(Spacer(1, 4*mm))

	# Customer and vehicle block
	story.append(_P("<b>Данные заказчика и автомобиля</b>", styleH2))
	cust_lines = [
		f"Заказчик: {customer.get('full_name','')}",
		f"Телефон: {customer.get('phone','')}",
		f"Авто: {vehicle.get('car_make_model','')} {vehicle.get('year','')}",
		f"VIN: {vehicle.get('vin','')}",
		f"Гос. номер: {vehicle.get('plate','')}",
	]
	for ln in cust_lines:
		story.append(_P(ln, styleN))
	story.append(Spacer(1, 3*mm))

	# Works table
	story.append(_P("<b>Перечень выполненных работ</b>", styleH2))
	works_rows = [[_P("Работа", styleB), _P("Исполнитель", styleB), _P("Цена, ₽", styleB)]]
	total_works = 0.0
	for w in works:
		name = w.get("name", "")
		price = float(w.get("price", 0))
		total_works += price
		works_rows.append([_P(name, styleN), _P(executor_name, styleN), _P(f"{price:,.2f}".replace(",", " "), styleN)])
	works_rows.append([_P("Итого", styleB), _P("", styleB), _P(f"{total_works:,.2f}".replace(",", " "), styleB)])
	wt = Table(works_rows, colWidths=[100*mm, 40*mm, 30*mm])
	wt.setStyle(TableStyle([
		("GRID", (0,0), (-1,-1), 0.5, colors.black),
		("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
		("ALIGN", (-1,0), (-1,-1), "RIGHT"),
	]))
	story.append(wt)
	story.append(Spacer(1, 3*mm))

	# Parts table
	story.append(_P("<b>Используемые запасные части (материалы)</b>", styleH2))
	parts_rows = [[_P("Артикул", styleB), _P("Наименование", styleB), _P("Кол-во", styleB), _P("Цена, ₽", styleB), _P("Сумма, ₽", styleB)]]
	total_parts = 0.0
	for p in parts:
		article = p.get("article", "-")
		name = p.get("name", "")
		qty = float(p.get("qty", 1))
		price = float(p.get("price", 0))
		sum_price = qty * price
		total_parts += sum_price
		parts_rows.append([
			_P(article, styleN),
			_P(name, styleN),
			_P(f"{qty:g}", styleN),
			_P(f"{price:,.2f}".replace(",", " "), styleN),
			_P(f"{sum_price:,.2f}".replace(",", " "), styleN),
		])
	parts_rows.append([_P("", styleN), _P("Итого", styleB), _P("", styleN), _P("", styleN), _P(f"{total_parts:,.2f}".replace(",", " "), styleB)])
	pt = Table(parts_rows, colWidths=[30*mm, 80*mm, 15*mm, 25*mm, 25*mm])
	pt.setStyle(TableStyle([
		("GRID", (0,0), (-1,-1), 0.5, colors.black),
		("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
		("ALIGN", (-3,1), (-1,-1), "RIGHT"),
	]))
	story.append(pt)
	story.append(Spacer(1, 4*mm))

	# Totals
	total_all = total_works + total_parts
	story.append(_P(f"<b>Общая стоимость (работы + запчасти): {total_all:,.2f} ₽</b>".replace(",", " "), styleN))
	story.append(_P(f"Всего к оплате (прописью): {_rub_text(total_all)}", styleN))
	story.append(Spacer(1, 6*mm))

	# Signatures
	sig = Table([
		[_P("Исполнитель: ____________ / Даниил", styleN), _P("Заказчик: ____________ / ", styleN)],
	])
	sig.setStyle(TableStyle([
		("VALIGN", (0,0), (-1,-1), "TOP"),
		("ALIGN", (0,0), (-1,-1), "LEFT"),
	]))
	story.append(sig)

	doc.build(story)