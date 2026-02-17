"""
Generate a test PDF with Sri Sai Properties data for RAG testing.
Run this script to create test_data/sri_sai_properties.pdf
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "sri_sai_properties.pdf")


def create_test_pdf():
    doc = SimpleDocTemplate(OUTPUT_PATH, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph("Sri Sai Properties — Property Catalog 2025", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))

    # Company Info
    story.append(Paragraph("About Sri Sai Properties", styles["Heading2"]))
    story.append(Paragraph(
        "Sri Sai Properties is a leading real estate company based in Hyderabad, Telangana. "
        "Founded in 2010 by Mr. Vara Prasad, we specialize in residential and commercial "
        "properties across prime locations in Hyderabad. Our mission is to provide quality "
        "housing at affordable prices. Contact: +91 98765 43210, Email: info@srisaiprops.com, "
        "Office: Plot 42, Financial District, Nanakramguda, Hyderabad - 500032.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ----- KOKAPET PROPERTIES -----
    story.append(Paragraph("Kokapet Properties", styles["Heading2"]))

    story.append(Paragraph("1. Sri Sai Lotus Residency — Kokapet", styles["Heading3"]))
    story.append(Paragraph(
        "Premium 2BHK and 3BHK apartments in Kokapet. East-facing flats with modern amenities. "
        "2BHK: 1200 sq.ft starting at Rs. 85 Lakhs. 3BHK: 1650 sq.ft starting at Rs. 1.2 Crores. "
        "Amenities include swimming pool, gym, children play area, club house, 24/7 security, "
        "power backup, covered parking, landscaped gardens. "
        "RERA Number: P02400005678. Possession: December 2025. "
        "Located 5 minutes from Financial District, 10 minutes from Gachibowli IT Hub.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("2. Sri Sai Green Valley Villas — Kokapet", styles["Heading3"]))
    story.append(Paragraph(
        "Independent villas in gated community at Kokapet. 3BHK duplex villas: 2400 sq.ft "
        "at Rs. 2.5 Crores. 4BHK triplex villas: 3200 sq.ft at Rs. 3.8 Crores. "
        "Each villa has private garden, car parking for 2 cars, modular kitchen, "
        "Italian marble flooring, VRV air conditioning. Community amenities: "
        "tennis court, jogging track, mini theater, banquet hall. "
        "RERA Number: P02400006789. Ready to move in. Only 12 villas remaining.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ----- NARSINGI PROPERTIES -----
    story.append(Paragraph("Narsingi Properties", styles["Heading2"]))

    story.append(Paragraph("3. Sri Sai Heights — Narsingi", styles["Heading3"]))
    story.append(Paragraph(
        "Affordable 2BHK and 3BHK flats in Narsingi near Wipro Circle. "
        "2BHK: 1050 sq.ft at Rs. 55 Lakhs. 3BHK: 1400 sq.ft at Rs. 72 Lakhs. "
        "Vastu compliant design. Amenities: lift, intercom, CCTV, rain water harvesting, "
        "solar water heater, earthquake resistant structure. "
        "RERA Number: P02400003456. Under construction, possession by March 2026. "
        "EMI starting at Rs. 42,000 per month. Home loan tie-up with SBI, HDFC, ICICI.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ----- PUPPALGUDA PROPERTIES -----
    story.append(Paragraph("Puppalguda Properties", styles["Heading2"]))

    story.append(Paragraph("4. Sri Sai Royal Towers — Puppalguda", styles["Heading3"]))
    story.append(Paragraph(
        "Luxury 3BHK flats in Puppalguda near Rajiv Gandhi International Airport road. "
        "1800 sq.ft, price: Rs. 1.05 Crores. Premium location with excellent connectivity "
        "to ORR (Outer Ring Road). Features: granite countertops, wooden flooring in bedrooms, "
        "branded CP fittings (Jaquar/Kohler), double-glazed windows. "
        "RERA Number: P02400007890. Possession: June 2025. "
        "Special offer: Free modular kitchen worth Rs. 5 Lakhs for bookings before March 2025.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ----- TELLAPUR PROPERTIES -----
    story.append(Paragraph("Tellapur Properties", styles["Heading2"]))

    story.append(Paragraph("5. Sri Sai Paradise — Tellapur", styles["Heading3"]))
    story.append(Paragraph(
        "Budget-friendly 1BHK and 2BHK apartments in Tellapur. "
        "1BHK: 650 sq.ft at Rs. 28 Lakhs. 2BHK: 950 sq.ft at Rs. 42 Lakhs. "
        "Ideal for first-time home buyers and IT professionals. "
        "Near proposed Metro station. Close to Nallagandla and Chandanagar markets. "
        "Amenities: security, parking, lift, generator backup. "
        "RERA Number: P02400009012. Under construction, possession by September 2026. "
        "No EMI till possession scheme available.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ----- OPEN PLOTS -----
    story.append(Paragraph("Open Plots & Land", styles["Heading2"]))

    story.append(Paragraph("6. Sri Sai Meadows — Shadnagar (Plots)", styles["Heading3"]))
    story.append(Paragraph(
        "HMDA approved open plots at Shadnagar, on National Highway 44. "
        "Plot sizes: 150 sq.yards at Rs. 18 Lakhs, 200 sq.yards at Rs. 24 Lakhs, "
        "267 sq.yards at Rs. 32 Lakhs. Clear title, all legal documents ready. "
        "Infrastructure: 30 feet and 40 feet roads, underground drainage, "
        "electricity connections, avenue plantation, community park. "
        "LP Number: LP0024000345. Near Rajiv Gandhi International Airport (15 km). "
        "Installment plan available: 50% down payment, rest in 12 monthly installments.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ----- COMMERCIAL -----
    story.append(Paragraph("Commercial Properties", styles["Heading2"]))

    story.append(Paragraph("7. Sri Sai Business Hub — Madhapur", styles["Heading3"]))
    story.append(Paragraph(
        "Commercial office spaces in the heart of Madhapur IT corridor. "
        "Office sizes from 800 sq.ft to 5000 sq.ft. Price: Rs. 8,500 per sq.ft. "
        "Pre-leased options available with 7% annual rental yield. "
        "Facilities: centralized AC, high-speed elevators, 100% power backup, "
        "food court, conference rooms, ample parking. "
        "Ideal for IT companies, startups, and co-working spaces. "
        "RERA Number: P02400004567. Ready for fit-out.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ----- PRICING TABLE -----
    story.append(Paragraph("Price Summary (All Properties)", styles["Heading2"]))

    data = [
        ["Project", "Type", "Size (sq.ft)", "Price", "Location", "Status"],
        ["Lotus Residency", "2BHK Flat", "1200", "Rs. 85 Lakhs", "Kokapet", "Dec 2025"],
        ["Lotus Residency", "3BHK Flat", "1650", "Rs. 1.2 Cr", "Kokapet", "Dec 2025"],
        ["Green Valley", "3BHK Villa", "2400", "Rs. 2.5 Cr", "Kokapet", "Ready"],
        ["Green Valley", "4BHK Villa", "3200", "Rs. 3.8 Cr", "Kokapet", "Ready"],
        ["Heights", "2BHK Flat", "1050", "Rs. 55 Lakhs", "Narsingi", "Mar 2026"],
        ["Heights", "3BHK Flat", "1400", "Rs. 72 Lakhs", "Narsingi", "Mar 2026"],
        ["Royal Towers", "3BHK Flat", "1800", "Rs. 1.05 Cr", "Puppalguda", "Jun 2025"],
        ["Paradise", "1BHK Flat", "650", "Rs. 28 Lakhs", "Tellapur", "Sep 2026"],
        ["Paradise", "2BHK Flat", "950", "Rs. 42 Lakhs", "Tellapur", "Sep 2026"],
        ["Business Hub", "Office", "800-5000", "Rs. 8500/sqft", "Madhapur", "Ready"],
    ]

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.2 * inch))

    # ----- PAYMENT PLANS -----
    story.append(Paragraph("Payment Plans & Offers", styles["Heading2"]))
    story.append(Paragraph(
        "1. Construction Linked Plan: 10% booking amount, rest as per construction milestones. "
        "2. Down Payment Plan: 90% upfront — get 5% discount on total price. "
        "3. Flexi Plan: 30% booking, 30% at slab, 40% at possession. "
        "4. Special NRI Plan: Connect with our NRI desk at +91 40 6789 0123. "
        "5. Current festival offer: Gold coin worth Rs. 50,000 for bookings in February 2025. "
        "6. Referral bonus: Rs. 1 Lakh cash reward for every successful referral.",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ----- CONTACT -----
    story.append(Paragraph("Contact Information", styles["Heading2"]))
    story.append(Paragraph(
        "Head Office: Plot 42, Financial District, Nanakramguda, Hyderabad — 500032. "
        "Phone: +91 98765 43210. WhatsApp: +91 98765 43210. "
        "Email: info@srisaiprops.com. Website: www.srisaiproperties.com. "
        "Branch offices: Kokapet (Beside SBI ATM), Narsingi (Near Wipro Circle), "
        "Madhapur (Cyber Towers). Working hours: 9 AM to 7 PM, all days including Sunday. "
        "Site visits available on appointment. Free pickup from Hyderabad airport/railway station.",
        styles["Normal"]
    ))

    doc.build(story)
    print(f"✅ Test PDF created: {OUTPUT_PATH}")
    print(f"   Size: {os.path.getsize(OUTPUT_PATH)} bytes")
    return OUTPUT_PATH


if __name__ == "__main__":
    create_test_pdf()
