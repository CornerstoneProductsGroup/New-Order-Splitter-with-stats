
import streamlit as st
import os
import pandas as pd
import zipfile
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime
import io

# Set up folders
today = datetime.now().strftime("%Y-%m-%d")
output_dir = f"daily_output/{today}"
log_dir = "logs"
os.makedirs(output_dir, exist_ok=True)
os.makedirs(log_dir, exist_ok=True)

summary_records = []
error_log = []
log_path = os.path.join(log_dir, "sent_orders_log.csv")
error_log_path = os.path.join(log_dir, "error_log.txt")

def log_error(msg):
    error_log.append(f"{datetime.now().isoformat()} - {msg}")

def load_mapping(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()
    sku_col = [col for col in df.columns if 'sku' in col.lower()][0]
    vendor_col = [col for col in df.columns if 'vendor' in col.lower()][0]
    email_cols = [col for col in df.columns if 'email' in col.lower()]
    email_col = email_cols[0] if email_cols else None
    mapping = {}
    for _, row in df.iterrows():
        sku = str(row[sku_col]).strip()
        vendor = str(row[vendor_col]).strip()
        email = str(row[email_col]).strip() if email_col and not pd.isna(row[email_col]) else ''
        mapping[sku] = {'vendor': vendor, 'email': email}
    return mapping

def split_pdf_by_sku(pdf_file, sku_mapping):
    reader = PdfReader(pdf_file)
    vendor_pages = {}
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        matched = False
        for sku, data in sku_mapping.items():
            if sku in text:
                vendor = data['vendor']
                if vendor not in vendor_pages:
                    vendor_pages[vendor] = {'writer': PdfWriter(), 'count': 0}
                vendor_pages[vendor]['writer'].add_page(page)
                vendor_pages[vendor]['count'] += 1
                matched = True
                break
        if not matched:
            log_error(f"Page {i+1}: No matching SKU found.")
    return vendor_pages

def create_zip(vendor_pages):
    zip_path = os.path.join(output_dir, f"VendorOrders_{today}.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for vendor, data in vendor_pages.items():
            pdf_path = os.path.join(output_dir, f"{vendor.replace(' ', '_')}_{today}.pdf")
            with open(pdf_path, "wb") as f:
                data['writer'].write(f)
            zipf.write(pdf_path, os.path.basename(pdf_path))
            summary_records.append({
                'Vendor': vendor,
                'Pages': data['count'],
                'PDF': os.path.basename(pdf_path),
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Status': 'Prepared'
            })
    return zip_path

def update_logs():
    if summary_records:
        df = pd.DataFrame(summary_records)
        log_file = os.path.join(output_dir, "summary_report.csv")
        df.to_csv(log_file, index=False)
        if os.path.exists(log_path):
            df_existing = pd.read_csv(log_path)
            df_combined = pd.concat([df_existing, df], ignore_index=True)
        else:
            df_combined = df
        df_combined.to_csv(log_path, index=False)
    if error_log:
        with open(error_log_path, "a") as f:
            for e in error_log:
                f.write(e + "\n")

st.title("📄 Daily Order Splitter with Logs & Reports")

sku_file = st.file_uploader("Upload SKU to Vendor Mapping (Excel)", type=["xlsx"])
pdf_file = st.file_uploader("Upload Home Depot/Lowe's Orders PDF", type=["pdf"])

if sku_file and pdf_file:
    st.success("Files uploaded. Ready to process.")
    if st.button("🚀 Split Orders"):
        sku_mapping = load_mapping(sku_file)
        vendor_pages = split_pdf_by_sku(pdf_file, sku_mapping)
        if not vendor_pages:
            st.error("No pages matched any SKU.")
        else:
            zip_path = create_zip(vendor_pages)
            update_logs()
            with open(zip_path, "rb") as f:
                st.download_button("📦 Download Vendor ZIP", f, file_name=os.path.basename(zip_path))
            st.success("Order split completed!")

            st.subheader("📊 Summary")
            st.metric("Total Vendors", len(vendor_pages))
            st.metric("Total Pages Split", sum(p['count'] for p in vendor_pages.values()))
            st.metric("Errors Logged", len(error_log))

            if summary_records:
                st.dataframe(pd.DataFrame(summary_records))
else:
    st.info("Please upload both the SKU mapping file and the PDF.")
