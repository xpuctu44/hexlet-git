from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from num2words import num2words
from datetime import datetime
from typing import List, Dict


def _rub_text(amount: float) -> str:
	amount = round(float(amount), 2)
	rub = int(amount)
	kop = int(round((amount - rub) * 100))
	words = num2words(rub, lang="ru")
	return f"{words} рублей {kop:02d} копеек"


def generate_order_pdf(
	output_path: str,
	order_number: int,
	customer: Dict[str, str],
	vehicle: Dict[str, str],
	works: List[Dict[str, str]],
	parts: List[Dict[str, str]],
	station_phone: str = "+79782091007",
	executor_name: str = "Даниил",
) -> None:
	styles = getSampleStyleSheet()
	styleN = styles["Normal"]
	styleH = styles["Heading1"]

	doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
	story = []

	# Header with VAG logos placeholder
	header = Paragraph("VAG Group: Audi · Volkswagen · Skoda · SEAT · Porsche", styles["Title"])
	story.append(header)
	story.append(Spacer(1, 4*mm))

	# Station info and order meta
	meta_table = Table([
		[
			Paragraph(f"Станция тех. обслуживания<br/>Телефон: {station_phone}", styleN),
			Paragraph("Вид ремонта: техническое обслуживание", styleN),
		],
		[
			Paragraph(f"Заказ-наряд № {order_number}", styleH),
			Paragraph(datetime.now().strftime("%d.%m.%Y"), styleN),
		],
	])
	meta_table.setStyle(TableStyle([
		("VALIGN", (0,0), (-1,-1), "TOP"),
	]))
	story.append(meta_table)
	story.append(Spacer(1, 4*mm))

	# Customer and vehicle block
	cust_lines = [
		f"Заказчик: {customer.get('full_name','')}",
		f"Телефон: {customer.get('phone','')}",
		f"Авто: {vehicle.get('car_make_model','')} {vehicle.get('year','')}",
		f"VIN: {vehicle.get('vin','')}",
		f"Гос. номер: {vehicle.get('plate','')}",
	]
	story.append(Paragraph("<b>Данные заказчика и автомобиля</b>", styles["Heading2"]))
	for ln in cust_lines:
		story.append(Paragraph(ln, styleN))
	story.append(Spacer(1, 3*mm))

	# Works table
	story.append(Paragraph("<b>Перечень выполненных работ</b>", styles["Heading2"]))
	works_rows = [["Работа", "Исполнитель", "Цена, ₽"]]
	total_works = 0.0
	for w in works:
		name = w.get("name", "")
		price = float(w.get("price", 0))
		total_works += price
		works_rows.append([name, executor_name, f"{price:,.2f}".replace(",", " ")])
	works_rows.append(["Итого", "", f"{total_works:,.2f}".replace(",", " ")])
	wt = Table(works_rows, colWidths=[100*mm, 40*mm, 30*mm])
	wt.setStyle(TableStyle([
		("GRID", (0,0), (-1,-1), 0.5, colors.black),
		("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
		("ALIGN", (-1,0), (-1,-1), "RIGHT"),
	]))
	story.append(wt)
	story.append(Spacer(1, 3*mm))

	# Parts table
	story.append(Paragraph("<b>Используемые запасные части (материалы)</b>", styles["Heading2"]))
	parts_rows = [["Артикул", "Наименование", "Кол-во", "Цена, ₽", "Сумма, ₽"]]
	total_parts = 0.0
	for p in parts:
		article = p.get("article", "-")
		name = p.get("name", "")
		qty = float(p.get("qty", 1))
		price = float(p.get("price", 0))
		sum_price = qty * price
		total_parts += sum_price
		parts_rows.append([
			article,
			name,
			f"{qty:g}",
			f"{price:,.2f}".replace(",", " "),
			f"{sum_price:,.2f}".replace(",", " "),
		])
	parts_rows.append(["", "Итого", "", "", f"{total_parts:,.2f}".replace(",", " ")])
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
	story.append(Paragraph(f"<b>Общая стоимость (работы + запчасти): {total_all:,.2f} ₽</b>".replace(",", " "), styleN))
	story.append(Paragraph(f"Всего к оплате (прописью): {_rub_text(total_all)}", styleN))
	story.append(Spacer(1, 6*mm))

	# Signatures
	sig = Table([
		[Paragraph("Исполнитель: ____________ / Даниил", styleN), Paragraph("Заказчик: ____________ / ", styleN)],
	])
	sig.setStyle(TableStyle([
		("VALIGN", (0,0), (-1,-1), "TOP"),
		("ALIGN", (0,0), (-1,-1), "LEFT"),
	]))
	story.append(sig)

	doc.build(story)