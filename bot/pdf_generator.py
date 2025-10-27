from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from num2words import num2words
from datetime import datetime
from typing import List, Dict, Any
import os


def _rub_text(amount: float) -> str:
	amount = round(float(amount), 2)
	rub = int(amount)
	kop = int(round((amount - rub) * 100))
	words = num2words(rub, lang="ru")
	return f"{words} рублей {kop:02d} копеек"


def _P(text: Any, style: ParagraphStyle) -> Paragraph:
	return Paragraph(str(text), style)


def _register_cyrillic_font():
	"""Register a Cyrillic-compatible font for PDF generation"""
	try:
		# Try to register Arial Unicode MS if available (common on Windows)
		pdfmetrics.registerFont(TTFont('ArialUnicode', 'arialuni.ttf'))
		return 'ArialUnicode'
	except:
		try:
			# Try to register Times New Roman if available
			pdfmetrics.registerFont(TTFont('TimesNewRoman', 'times.ttf'))
			return 'TimesNewRoman'
		except:
			try:
				# Try to register Arial if available
				pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
				return 'Arial'
			except:
				# Fallback to default fonts but with encoding specification
				return None


def _get_cyrillic_style(base_style, font_name=None):
	"""Get a style with Cyrillic support"""
	if font_name:
		style = ParagraphStyle(
			name=base_style.name + 'Cyrillic',
			parent=base_style,
			fontName=font_name,
			encoding='utf-8'
		)
	else:
		style = ParagraphStyle(
			name=base_style.name + 'Cyrillic',
			parent=base_style,
			encoding='utf-8'
		)
	return style


def _brand_logo_images() -> list:
	"""Try to load VAG brand logos from assets. Fallback to empty list if missing.

	Expected files (PNG/SVG converted to PNG) under assets directory:
	- audi.png, volkswagen.png, skoda.png, seat.png, porsche.png
	"""
	assets_candidates = [
		os.path.join(os.path.dirname(__file__), "assets"),
		os.path.join(os.getcwd(), "bot", "assets"),
		os.path.join(os.getcwd(), "assets"),
	]
	# Accept both correct and common misspelling for volkswagen
	logos = [
		("audi.png"),
		("volkswagen.png"),
		("valkswagen.png"),
		("skoda.png"),
		("seat.png"),
		("porsche.png"),
	]
	imgs = []
	for fname in logos:
		path = None
		for base in assets_candidates:
			cand = os.path.join(base, fname)
			if os.path.exists(cand):
				path = cand
				break
		if path:
			try:
				# Keep aspect ratio; set height to specified mm
				img = Image(path)
				# Uniform sizing: height 12mm, max width 28mm
				img._restrictSize(28*mm, 12*mm)
				imgs.append(img)
			except Exception:
				pass
	return imgs


def generate_order_pdf(
	output_path: str,
	order_number: int,
	customer: Dict[str, str],
	vehicle: Dict[str, str],
	works: List[Dict[str, Any]],
	parts: List[Dict[str, Any]],
	accepted_at_iso: str | None = None,
	station_phone: str = "+79782091007",
	executor_name: str = "Даниил",
) -> None:
	# Register Cyrillic font
	cyrillic_font = _register_cyrillic_font()

	# Get base styles
	styles = getSampleStyleSheet()

	# Create Cyrillic-compatible styles
	if cyrillic_font:
		styleN = _get_cyrillic_style(styles["Normal"], cyrillic_font)
		styleB = _get_cyrillic_style(styles["Heading3"], cyrillic_font)
		styleTitle = _get_cyrillic_style(styles["Title"], cyrillic_font)
		styleH1 = _get_cyrillic_style(styles["Heading1"], cyrillic_font)
		styleH2 = _get_cyrillic_style(styles["Heading2"], cyrillic_font)
	else:
		# Fallback to default styles with UTF-8 encoding
		styleN = _get_cyrillic_style(styles["Normal"])
		styleB = _get_cyrillic_style(styles["Heading3"])
		styleTitle = _get_cyrillic_style(styles["Title"])
		styleH1 = _get_cyrillic_style(styles["Heading1"])
		styleH2 = _get_cyrillic_style(styles["Heading2"])

	doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
	story = []

	try:
		# Header with VAG logos (images if available, fallback to text)
		logo_imgs = _brand_logo_images()
		if logo_imgs:
			# arrange in a single-row table
			cells = [[img for img in logo_imgs]]
			logo_table = Table(cells)
			logo_table.setStyle(TableStyle([
				("ALIGN", (0,0), (-1,-1), "CENTER"),
				("VALIGN", (0,0), (-1,-1), "MIDDLE"),
				("LEFTPADDING", (0,0), (-1,-1), 2),
				("RIGHTPADDING", (0,0), (-1,-1), 2),
			]))
			story.append(logo_table)
		else:
			header = _P("VAG Group: Audi · Volkswagen · Skoda · SEAT · Porsche", styleTitle)
			story.append(header)
		story.append(Spacer(1, 4*mm))
	except Exception as logo_error:
		print(f"Logo loading failed: {logo_error}, skipping logos")
		header = _P("VAG Service Station", styleTitle)
		story.append(header)
		story.append(Spacer(1, 4*mm))

	# Station info and order meta
	accepted_dt_text = ""
	if accepted_at_iso:
		try:
			acc = datetime.fromisoformat(accepted_at_iso)
			accepted_dt_text = acc.strftime("%d.%m.%Y %H:%M")
		except Exception:
			accepted_dt_text = ""
	right_meta_html = "Вид ремонта: техническое обслуживание"
	right_meta_html += f"<br/>заказ принял: {executor_name}"
	if accepted_dt_text:
		right_meta_html += f"<br/>Принят: {accepted_dt_text}"
	meta_table = Table([
		[
			_P(f"Станция тех. обслуживания<br/>Телефон: {station_phone}<br/>Адрес: г.Севастополь, Камышовое шоссе 6", styleN),
			_P(right_meta_html, styleN),
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

	# Customer and vehicle block (extended, two columns)
	story.append(_P("<b>Данные заказчика и автомобиля</b>", styleH2))
	left_col = [
		_P(f"Заказчик: {customer.get('full_name','')}", styleN),
		_P(f"Телефон: {customer.get('phone','')}", styleN),
		_P(f"Авто: {vehicle.get('car_make_model','')} {vehicle.get('year','')}", styleN),
		_P(f"Кузов: {vehicle.get('body_type','')}", styleN),
		_P(f"Цвет: {vehicle.get('color','')}", styleN),
		_P(f"Пробег: {vehicle.get('mileage','')}", styleN),
	]
	right_col = [
		_P(f"VIN: {vehicle.get('vin','')}", styleN),
		_P(f"Гос. номер: {vehicle.get('plate','')}", styleN),
		_P(f"№ двигателя: {vehicle.get('engine_number','')}", styleN),
		_P(f"Класс: {vehicle.get('car_class','')}", styleN),
		_P(f"СТС: {vehicle.get('sts','')}", styleN),
		_P(f"ПТС: {vehicle.get('pts','')}", styleN),
	]
	# Align heights by padding with empty paragraphs to equal length
	max_len = max(len(left_col), len(right_col))
	while len(left_col) < max_len:
		left_col.append(_P("", styleN))
	while len(right_col) < max_len:
		right_col.append(_P("", styleN))
	info_table = Table(list(zip(left_col, right_col)), colWidths=[85*mm, 85*mm])
	info_table.setStyle(TableStyle([
		("VALIGN", (0,0), (-1,-1), "TOP"),
	]))
	story.append(info_table)
	# Reason below two-column block
	reason_txt = vehicle.get('reason', '')
	if reason_txt:
		story.append(_P(f"Причина обращения: {reason_txt}", styleN))
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

	# Signatures with additional texts
	# Swap notes per request: above Executor -> "принял", above Customer -> "сдал ..."
	left_note = _P("Транспортное средство принял от ", styleN)
	right_note = _P(
		"Транспортное средство сдал, с условиями выполнения заказа, инструкциями касательно правил поведения на территории СТО ознакомлен и обязуюсь их выполнять",
		styleN,
	)
	left_sig = _P("Исполнитель: ____________ / Даниил", styleN)
	right_sig = _P(f"Заказчик: ____________ / {customer.get('full_name','')}", styleN)
	sig = Table([
		[left_note, right_note],
		[left_sig, right_sig],
	])
	sig.setStyle(TableStyle([
		("VALIGN", (0,0), (-1,-1), "TOP"),
		("ALIGN", (0,0), (-1,-1), "LEFT"),
	]))
	story.append(sig)

	try:
		doc.build(story)
		print(f"PDF generated successfully: {output_path}")
	except Exception as build_error:
		print(f"PDF build failed: {build_error}")
		# Try to create a simple PDF as fallback
		try:
			simple_doc = SimpleDocTemplate(output_path, pagesize=A4)
			simple_styles = getSampleStyleSheet()
			simple_story = []

			simple_story.append(Paragraph(f"Order #{order_number}", simple_styles['Title']))
			simple_story.append(Paragraph(f"Customer: {customer.get('full_name', 'N/A')}", simple_styles['Normal']))
			simple_story.append(Paragraph(f"Phone: {customer.get('phone', 'N/A')}", simple_styles['Normal']))
			simple_story.append(Paragraph(f"Vehicle: {vehicle.get('car_make_model', 'N/A')}", simple_styles['Normal']))

			if works:
				simple_story.append(Paragraph("Works:", simple_styles['Heading2']))
				for work in works:
					simple_story.append(Paragraph(f"- {work.get('name', '')}: {work.get('price', 0)} RUB", simple_styles['Normal']))

			if parts:
				simple_story.append(Paragraph("Parts:", simple_styles['Heading2']))
				for part in parts:
					simple_story.append(Paragraph(f"- {part.get('name', '')}: {part.get('price', 0)} RUB", simple_styles['Normal']))

			simple_doc.build(simple_story)
			print("Created simple fallback PDF")
		except Exception as fallback_error:
			print(f"Even fallback PDF failed: {fallback_error}")
			raise build_error