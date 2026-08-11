import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# ==========================================
# 0. FUNGSI GLOBAL & MAPPING TRAFFIC
# ==========================================
def bersihkan_angka_sakti(series):
    def konversi_nilai(val):
        if pd.isna(val): return 0.0
        if isinstance(val, (int, float)): return float(val)
        s = str(val).strip().replace('Rp', '').replace('%', '').replace('x', '').replace(' ', '')
        if not s or s.lower() in ['nan', '-', 'null']: return 0.0
        if ',' in s and '.' in s:
            if s.find('.') < s.find(','): s = s.replace('.', '').replace(',', '.')
            else: s = s.replace(',', '')
        elif ',' in s:
            parts = s.split(',')
            if len(parts[-1]) == 3 and len(parts) > 1: s = s.replace(',', '')
            else: s = s.replace(',', '.')
        elif '.' in s:
            parts = s.split('.')
            if len(parts[-1]) == 3 and len(parts[0]) <= 3: s = s.replace('.', '')
        try: return float(s)
        except: return 0.0
    return series.apply(konversi_nilai)

def map_sumber_traffic_click(val):
    if pd.isna(val) or str(val).strip() == '': return 'Lainnya / Direct'
    v = str(val).strip().lower()
    if 'shopeevideo' in v or 'shopee' in v: return 'Shopee Video'
    if 'facebook' in v: return 'Facebook'
    if 'instagram' in v: return 'Instagram'
    if 'youtube' in v: return 'YouTube'
    if 'tiktok' in v: return 'TikTok'
    return str(val).strip()

def map_sumber_traffic_sales(row, col_platform, col_content):
    content = str(row.get(col_content, '')).strip()
    platform = str(row.get(col_platform, '')).strip()
    
    if content and content.lower() not in ['nan', 'none', '']:
        return content  # Mengambil nilai spesifik seperti "Facebook Reels"
    if platform and platform.lower() not in ['nan', 'none', '']:
        p = platform.lower()
        if 'shopeevideo' in p or 'shopee video' in p: return 'Shopee Video'
        return platform
    return 'Organik / Lainnya'


# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI GOOGLE SHEETS
# ==========================================
st.set_page_config(page_title="Affiliate Paid & Meta Analytics", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { font-weight: 800; color: #1E1B4B; letter-spacing: -0.5px; }
    h2, h3, h4 { font-weight: 700; color: #312E81; }
    .stButton>button { border-radius: 8px; font-weight: 600; background-color: #4F46E5; color: white; border: none; transition: all 0.2s; }
    .stButton>button:hover { background-color: #4338CA; color: white; transform: translateY(-1px); box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.3); }
    .metric-card { background: #FFFFFF; border: 1px solid #E0E7FF; border-top: 4px solid #4F46E5; padding: 1.25rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(79, 70, 229, 0.05); }
    .metric-label { font-size: 0.875rem; color: #4338CA; font-weight: 600; margin-bottom: 0.25rem; }
    .metric-value { font-size: 1.625rem; font-weight: 800; color: #1E1B4B; }
    .meta-badge { display: inline-block; background-color: #EEF2FF; color: #3730A3; font-size: 0.8rem; font-weight: 700; padding: 4px 12px; border-radius: 20px; border: 1px solid #C7D2FE; margin-bottom: 10px; }
    div[data-testid="stExpander"] { background-color: #F5F3FF; border-radius: 10px; border: 1px solid #DDD6FE; }
    </style>
""", unsafe_allow_html=True)

BULAN_INDO = {1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"}

@st.cache_resource
def inisialisasi_gspread():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        raw_json_teks = st.secrets["google_credentials"]["json_teks"]
        kredensial_dict = json.loads(raw_json_teks)
        creds = Credentials.from_service_account_info(kredensial_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.sidebar.error(f"❌ Format JSON di Secrets salah: {str(e)}")
        st.stop()

try:
    gc = inisialisasi_gspread()
    spreadsheet_id = st.secrets["spreadsheet"]["id"]
    sheet_utama = gc.open_by_key(spreadsheet_id)
except Exception as e:
    st.sidebar.error(f"❌ Gagal tersambung ke Google Sheets: {str(e)}")
    st.stop()

def dapatkan_atau_buat_worksheet(nama_sheet, headers):
    try: return sheet_utama.worksheet(nama_sheet)
    except:
        ws = sheet_utama.add_worksheet(title=nama_sheet, rows="5000", cols=str(len(headers) + 2))
        ws.append_row(headers)
        return ws

worksheet_summary = dapatkan_atau_buat_worksheet("Riwayat_Summary", ["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"])
worksheet_tag = dapatkan_atau_buat_worksheet("Riwayat_Tag", ["Nama Laporan", "Tipe", "Clean_Tag", "Spend", "Klik_Meta", "Klik_Shopee", "Pesanan", "Kebocoran", "Komisi_Kotor", "Komisi_Bersih", "Profit_Rugi", "ROAS"])
worksheet_raw_sales = dapatkan_atau_buat_worksheet("Raw_Sales", ["Nama Laporan", "Clean_Tag", "Nama Produk", "Kategori", "Item Terjual", "Komisi"])
worksheet_traffic = dapatkan_atau_buat_worksheet("Riwayat_Traffic", ["Nama Laporan", "Sumber_Traffic", "Klik", "Pesanan", "Komisi_Bersih"])


# ==========================================
# 2. SINKRONISASI OTOMATIS & INTERNAL CACHE
# ==========================================
if 'riwayat_summary' not in st.session_state:
    with st.spinner("Sinkronisasi aman data cloud harian..."):
        try:
            records_summary = worksheet_summary.get_all_records(value_render_option='UNFORMATTED_VALUE')
            df_load_summary = pd.DataFrame(records_summary) if records_summary else pd.DataFrame(columns=["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"])
            
            records_tag = worksheet_tag.get_all_records(value_render_option='UNFORMATTED_VALUE')
            df_load_tag = pd.DataFrame(records_tag) if records_tag else pd.DataFrame()
            
            records_sales = worksheet_raw_sales.get_all_records(value_render_option='UNFORMATTED_VALUE')
            df_load_sales = pd.DataFrame(records_sales) if records_sales else pd.DataFrame()

            records_traffic = worksheet_traffic.get_all_records(value_render_option='UNFORMATTED_VALUE')
            df_load_traffic = pd.DataFrame(records_traffic) if records_traffic else pd.DataFrame()

            if not df_load_summary.empty:
                df_load_summary['Tanggal'] = pd.to_datetime(df_load_summary['Tanggal'], errors='coerce').dt.date
                for col in ["Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"]:
                    df_load_summary[col] = bersihkan_angka_sakti(df_load_summary[col])

            if not df_load_tag.empty:
                for col in ['Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Kebocoran', 'Komisi_Kotor', 'Komisi_Bersih', 'Profit_Rugi', 'ROAS']:
                    df_load_tag[col] = bersihkan_angka_sakti(df_load_tag[col])

            if not df_load_traffic.empty:
                for col in ['Klik', 'Pesanan', 'Komisi_Bersih']:
                    df_load_traffic[col] = bersihkan_angka_sakti(df_load_traffic[col])

            st.session_state['riwayat_summary'] = df_load_summary
            st.session_state['cache_tag'] = df_load_tag
            st.session_state['cache_sales'] = df_load_sales
            st.session_state['cache_traffic'] = df_load_traffic
        except Exception as e:
            st.error(f"Gagal memuat otomatis database internal: {str(e)}")
            st.stop()


# ==========================================
# 3. SIDEBAR PANEL (INPUT & UPLOAD)
# ==========================================
with st.sidebar:
    st.markdown("<div class='meta-badge'>📊 META & PAID ANALYTICS</div>", unsafe_allow_html=True)
    st.markdown("### 📥 Upload File Baru")
    st.write("Kelola pengeluaran iklan Meta dan optimalkan komisi bersih akun Shopee Anda.")
    
    tanggal_laporan = st.date_input("Tanggal Laporan:", value=datetime.now().date())
    nama_bulan = BULAN_INDO[tanggal_laporan.month]
    default_nama = f"Laporan {tanggal_laporan.day:02d} {nama_bulan}"
    
    with st.form("form_upload", clear_on_submit=True):
        nama_laporan = st.text_input("Nama / Catatan Laporan:", value=default_nama)
        uploaded_files = st.file_uploader("Pilih berkas CSV (Multi-upload):", type=["csv"], accept_multiple_files=True)
        tombol_proses = st.form_submit_button("🚀 Proses Laporan", use_container_width=True)

def bersihkan_tag(x):
    if pd.isna(x) or str(x).strip() == "" or str(x).lower() == "nan": return "Organik"
    s = str(x).strip()
    if s.startswith('#'): s = s[1:]
    if s.endswith('----'): s = s[:-4]
    return s

def cari_kolom(list_kolom, kata_kunci_list, default_name):
    for col in list_kolom:
        c = str(col).strip().lower()
        for kw in kata_kunci_list:
            if kw.lower() == c or kw.lower() in c: return col
    return default_name

def gaya_tabel_detail(row):
    gaya = [''] * len(row)
    if 'Kebocoran' in row.index:
        warna = 'background-color: #EEF2FF; color: #3730A3;' if row['Kebocoran'] < 0 else 'background-color: #FEF2F2; color: #991B1B;'
        gaya[row.index.get_loc('Kebocoran')] = warna
    return gaya

def gaya_tabel_summary(row):
    gaya = [''] * len(row)
    if 'Profit' in row.index:
        gaya[row.index.get_loc('Profit')] = 'color: #166534; font-weight: bold;' if row['Profit'] >= 0 else 'color: #991B1B; font-weight: bold;'
    if 'Komisi Iklan' in row.index and 'Spend' in row.index:
        gaya[row.index.get_loc('Komisi Iklan')] = 'color: #166534; font-weight: bold;' if row['Komisi Iklan'] > row['Spend'] else 'color: #991B1B; font-weight: bold;'
    return gaya

if tombol_proses:
    if len(uploaded_files) < 2:
        st.error("Silakan unggah minimal 2 file CSV (Data Meta & Data Penjualan Shopee) terlebih dahulu.")
    elif nama_laporan in st.session_state['riwayat_summary']['Nama Laporan'].values:
        st.warning("⚠️ Nama laporan sudah ada. Silakan hapus laporan lama terlebih dahulu.")
    else:
        list_df_meta, list_df_clicks, list_df_sales = [], [], []
        
        for file in uploaded_files:
            raw_bytes = file.read()
            file.seek(0)
            try: teks = raw_bytes.decode('utf-8-sig')
            except: teks = raw_bytes.decode('latin-1')
            baris_pertama = teks.split('\n')[0] if '\n' in teks else ""
            sep = ';' if ';' in baris_pertama and baris_pertama.count(';') > baris_pertama.count(',') else ('\t' if '\t' in baris_pertama else ',')
            df_temp = pd.read_csv(io.StringIO(teks), sep=sep)
            df_temp.columns = df_temp.columns.str.strip().str.replace('"', '').str.replace("'", "")
            
            if not df_temp.empty:
                if 'Jumlah yang dibelanjakan (IDR)' in df_temp.columns or 'Nama iklan' in df_temp.columns:
                    list_df_meta.append(df_temp)
                elif 'Klik ID' in df_temp.columns and 'Waktu Klik' in df_temp.columns:
                    list_df_clicks.append(df_temp)
                elif any(k in str(df_temp.columns).lower() for k in ['komisi per pesanan', 'komisi bersih', 'nama produk']):
                    list_df_sales.append(df_temp)

        if len(list_df_meta) > 0 and len(list_df_sales) > 0:
            df_meta = pd.concat(list_df_meta, ignore_index=True)
            df_sales = pd.concat(list_df_sales, ignore_index=True)
            df_clicks = pd.concat(list_df_clicks, ignore_index=True) if len(list_df_clicks) > 0 else pd.DataFrame(columns=['Klik ID', 'Tag_link', 'Clean_Tag'])

            # Identifikasi Kolom Utama
            kolom_pesanan = cari_kolom(df_sales.columns, ['id pesanan', 'order id', 'no pesanan'], df_sales.columns[0])
            kolom_tag_sales = cari_kolom(df_sales.columns, ['tag_link1', 'tag link', 'sub id', 'tag_link'], 'Tag_link1')
            kolom_komisi_kotor = cari_kolom(df_sales.columns, ['komisi kotor', 'gross commission', 'total komisi per pesanan'], df_sales.columns[-1])
            kolom_komisi_bersih = cari_kolom(df_sales.columns, ['komisi bersih', 'net commission', 'nett commission'], kolom_komisi_kotor)
            kolom_nama_produk = cari_kolom(df_sales.columns, ['nama produk', 'product name', 'info produk', 'nama barange'], 'Nama Produk')
            kolom_kategori_produk = cari_kolom(df_sales.columns, ['kategori', 'l1 kategori'], 'Kategori')
            kolom_jumlah_item = cari_kolom(df_sales.columns, ['item terjual', 'jumlah', 'qty'], 'Item Terjual')

            # Eksekusi Pembersihan Angka
            df_meta['Jumlah yang dibelanjakan (IDR)'] = bersihkan_angka_sakti(df_meta['Jumlah yang dibelanjakan (IDR)'])
            df_meta['Klik tautan'] = bersihkan_angka_sakti(df_meta['Klik tautan']).fillna(0).astype(int) if 'Klik tautan' in df_meta.columns else 0
            df_sales[kolom_komisi_kotor] = bersihkan_angka_sakti(df_sales[kolom_komisi_kotor])
            df_sales[kolom_komisi_bersih] = bersihkan_angka_sakti(df_sales[kolom_komisi_bersih])
            df_sales[kolom_jumlah_item] = pd.to_numeric(df_sales[kolom_jumlah_item], errors='coerce').fillna(1).astype(int)

            # Eksekusi Pembersihan Tag Link
            df_meta['Clean_Tag'] = df_meta['Nama iklan'].apply(bersihkan_tag)
            df_sales['Clean_Tag'] = df_sales[kolom_tag_sales].apply(bersihkan_tag)
            if not df_clicks.empty and 'Tag_link' in df_clicks.columns:
                df_clicks['Clean_Tag'] = df_clicks['Tag_link'].apply(bersihkan_tag)

            # === LOGIKA SUMBER TRAFFIC ===
            kolom_perujuk = cari_kolom(df_clicks.columns, ['perujuk', 'referrer'], 'Perujuk') if not df_clicks.empty else None
            kolom_platform = cari_kolom(df_sales.columns, ['platform'], 'Platform')
            kolom_content = cari_kolom(df_sales.columns, ['content type', 'tipe konten'], 'Content Type')

            if not df_clicks.empty and kolom_perujuk in df_clicks.columns:
                df_clicks['Sumber_Traffic'] = df_clicks[kolom_perujuk].apply(map_sumber_traffic_click)
            else:
                if not df_clicks.empty: df_clicks['Sumber_Traffic'] = 'Lainnya / Direct'

            df_sales['Sumber_Traffic'] = df_sales.apply(lambda r: map_sumber_traffic_sales(r, kolom_platform, kolom_content), axis=1)

            traffic_clicks = df_clicks.groupby('Sumber_Traffic').agg(Klik=('Klik ID', 'count')).reset_index() if not df_clicks.empty else pd.DataFrame(columns=['Sumber_Traffic', 'Klik'])
            traffic_sales = df_sales.groupby('Sumber_Traffic').agg(Pesanan=(kolom_pesanan, 'nunique'), Komisi_Bersih=(kolom_komisi_bersih, 'sum')).reset_index()
            df_traffic_sum = pd.merge(traffic_clicks, traffic_sales, on='Sumber_Traffic', how='outer').fillna(0)
            # ==============================

            ad_tags = set(df_meta[df_meta['Jumlah yang dibelanjakan (IDR)'] > 0]['Clean_Tag'].unique())
            meta_sum = df_meta.groupby('Clean_Tag').agg(Spend=('Jumlah yang dibelanjakan (IDR)', 'sum'), Klik_Meta=('Klik tautan', 'sum')).reset_index()
            click_sum = df_clicks.groupby('Clean_Tag').agg(Klik_Shopee=('Klik ID', 'count')).reset_index() if not df_clicks.empty else pd.DataFrame(columns=['Clean_Tag', 'Klik_Shopee'])
            sales_sum = df_sales.groupby('Clean_Tag').agg(Pesanan=(kolom_pesanan, 'nunique'), Komisi_Kotor=(kolom_komisi_kotor, 'sum'), Komisi_Bersih=(kolom_komisi_bersih, 'sum')).reset_index()

            merged = pd.merge(meta_sum, click_sum, on='Clean_Tag', how='outer')
            merged = pd.merge(merged, sales_sum, on='Clean_Tag', how='outer').fillna(0)

            merged['Tipe'] = merged.apply(lambda r: "IKLAN (AKTIF)" if r['Clean_Tag'] in ad_tags and r['Spend'] > 0 else "ORGANIK", axis=1)
            merged['Kebocoran'] = merged.apply(lambda r: ((r['Klik_Meta'] - r['Klik_Shopee']) / r['Klik_Meta']) * 100 if r['Klik_Meta'] > 0 else 0.0, axis=1)
            merged['Profit_Rugi'] = merged['Komisi_Bersih'] - merged['Spend']
            merged['ROAS'] = merged.apply(lambda r: r['Komisi_Bersih'] / r['Spend'] if r['Spend'] > 0 else 0.0, axis=1)
            
            total_spend = merged['Spend'].sum()
            komisi_iklan_nett = merged[merged['Tipe'] == "IKLAN (AKTIF)"]["Komisi_Bersih"].sum()
            komisi_organik_nett = merged[merged['Tipe'] == "ORGANIK"]["Komisi_Bersih"].sum()
            total_komisi_nett = df_sales[kolom_komisi_bersih].sum()
            total_profit = total_komisi_nett - total_spend

            try:
                worksheet_summary.append_row([str(tanggal_laporan), nama_laporan, float(total_spend), float(komisi_iklan_nett), float(komisi_organik_nett), float(total_komisi_nett), float(total_profit)], value_input_option='RAW')
                
                rows_tag_to_save, rows_to_save, rows_traffic_to_save = [], [], []
                
                for _, row in merged.iterrows():
                    rows_tag_to_save.append([nama_laporan, str(row['Tipe']), str(row['Clean_Tag']), float(row['Spend']), int(row['Klik_Meta']), int(row['Klik_Shopee']), int(row['Pesanan']), float(row['Kebocoran']), float(row['Komisi_Kotor']), float(row['Komisi_Bersih']), float(row['Profit_Rugi']), float(row['ROAS'])])
                if rows_tag_to_save: worksheet_tag.append_rows(rows_tag_to_save, value_input_option='RAW')
                
                for _, row in df_sales.iterrows():
                    nama_prod_val = str(row[kolom_nama_produk]).strip() if kolom_nama_produk in df_sales.columns else "Produk Tidak Diketahui"
                    kat_prod_val = str(row[kolom_kategori_produk]).strip() if kolom_kategori_produk in df_sales.columns else "Umum"
                    rows_to_save.append([nama_laporan, str(row['Clean_Tag']), nama_prod_val, kat_prod_val, int(row[kolom_jumlah_item]), float(row[kolom_komisi_bersih])])
                if rows_to_save: worksheet_raw_sales.append_rows(rows_to_save, value_input_option='RAW')

                for _, row in df_traffic_sum.iterrows():
                    rows_traffic_to_save.append([nama_laporan, str(row['Sumber_Traffic']), int(row['Klik']), int(row['Pesanan']), float(row['Komisi_Bersih'])])
                if rows_traffic_to_save: worksheet_traffic.append_rows(rows_traffic_to_save, value_input_option='RAW')
                
                if 'riwayat_summary' in st.session_state: del st.session_state['riwayat_summary']
                st.success(f"✅ Data '{nama_laporan}' Berhasil Tersimpan!")
                st.rerun()
            except Exception as sheet_err:
                st.error(f"Gagal menulis ke Cloud: {str(sheet_err)}")
        else:
            st.error("Gagal mendeteksi data! Pastikan minimal terdapat 1 file Meta dan 1 file Penjualan Shopee.")


# ==========================================
# 4. KONTEN UTAMA & FILTER RENTANG WAKTU DATA
# ==========================================
st.markdown("<div class='meta-badge'>📊 META ADS & PAID CAMPAIGN MODE</div>", unsafe_allow_html=True)
st.title("📊 Affiliate Advanced Analytics")

with st.container():
    st.markdown("<div style='background-color: #EEF2FF; padding: 1rem; border-radius: 10px; border: 1px solid #C7D2FE; margin-bottom: 1.5rem;'>", unsafe_allow_html=True)
    col_btn1, col_btn2, col_btn3, col_date = st.columns([1, 1, 1, 3])
    today = datetime.now().date()

    if 'start_filter' not in st.session_state: st.session_state['start_filter'] = today - timedelta(days=7)
    if 'end_filter' not in st.session_state: st.session_state['end_filter'] = today

    with col_btn1:
        if st.button("📅 Kemarin", use_container_width=True):
            st.session_state['start_filter'] = today - timedelta(days=1); st.session_state['end_filter'] = today - timedelta(days=1)
            st.rerun()
    with col_btn2:
        if st.button("📅 Bulan Ini", use_container_width=True):
            st.session_state['start_filter'] = today.replace(day=1); st.session_state['end_filter'] = today
            st.rerun()
    with col_btn3:
        if st.button("📅 Bulan Lalu", use_container_width=True):
            last_month_end = today.replace(day=1) - timedelta(days=1)
            st.session_state['start_filter'] = last_month_end.replace(day=1); st.session_state['end_filter'] = last_month_end
            st.rerun()

    with col_date:
        rentang_tanggal = st.date_input("Kustom Periode:", value=(st.session_state['start_filter'], st.session_state['end_filter']))

    filter_start, filter_end = rentang_tanggal if isinstance(rentang_tanggal, tuple) and len(rentang_tanggal) == 2 else (st.session_state['start_filter'], st.session_state['end_filter'])
    st.markdown("</div>", unsafe_allow_html=True)

df_filtered = st.session_state.get('riwayat_summary', pd.DataFrame())
if not df_filtered.empty: df_filtered = df_filtered[(df_filtered['Tanggal'] >= filter_start) & (df_filtered['Tanggal'] <= filter_end)]


# ==========================================
# 5. KOTAK METRIK SUMMARY UTAMA & TABEL
# ==========================================
val_spend = pd.to_numeric(df_filtered['Spend'], errors='coerce').sum() if not df_filtered.empty else 0
val_komisi_iklan = pd.to_numeric(df_filtered['Komisi Iklan'], errors='coerce').sum() if not df_filtered.empty else 0
val_komisi_organik = pd.to_numeric(df_filtered['Komisi Organik'], errors='coerce').sum() if not df_filtered.empty else 0
val_keuntungan_iklan = val_komisi_iklan - val_spend
val_total_keuntungan = pd.to_numeric(df_filtered['Profit'], errors='coerce').sum() if not df_filtered.empty else 0

col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
with col_m1: st.markdown(f"<div class='metric-card'><div class='metric-label'>💸 Pengeluaran Iklan</div><div class='metric-value' style='color: #475569;'>Rp {int(round(val_spend)):,}".replace(',', '.') + "</div></div>", unsafe_allow_html=True)
with col_m2: st.markdown(f"<div class='metric-card'><div class='metric-label'>🎯 Komisi Iklan (Meta)</div><div class='metric-value' style='color: #1E1B4B;'>Rp {int(round(val_komisi_iklan)):,}".replace(',', '.') + "</div></div>", unsafe_allow_html=True)
with col_m3: st.markdown(f"<div class='metric-card'><div class='metric-label'>📱 Komisi Organik</div><div class='metric-value' style='color: #1E1B4B;'>Rp {int(round(val_komisi_organik)):,}".replace(',', '.') + "</div></div>", unsafe_allow_html=True)
with col_m4: st.markdown(f"<div class='metric-card'><div class='metric-label'>💰 Keuntungan Iklan</div><div class='metric-value' style='color: {'#166534' if val_keuntungan_iklan >= 0 else '#991B1B'};'>Rp {int(round(val_keuntungan_iklan)):,}".replace(',', '.') + "</div></div>", unsafe_allow_html=True)
with col_m5: st.markdown(f"<div class='metric-card'><div class='metric-label'>📈 Keuntungan Bersih (Total)</div><div class='metric-value' style='color: {'#166534' if val_total_keuntungan >= 0 else '#991B1B'};'>Rp {int(round(val_total_keuntungan)):,}".replace(',', '.') + "</div></div>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

st.subheader("📋 Riwayat Laporan Harian")
if df_filtered.empty:
    st.info("Belum ada data terekam pada periode ini.")
else:
    df_styled_summary = df_filtered.style.format({
        'Spend': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'), 'Komisi Iklan': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
        'Komisi Organik': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'), 'Total Komisi (Nett)': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
        'Profit': lambda x: f"Rp {int(round(x)):,}".replace(',', '.')
    }).apply(gaya_tabel_summary, axis=1)
    
    event_pilih = st.dataframe(df_styled_summary, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="multi-row")

    if event_pilih and len(event_pilih["selection"]["rows"]) > 0:
        indeks_terpilih = event_pilih["selection"]["rows"]
        daftar_laporan_klik = df_filtered.iloc[indeks_terpilih]["Nama Laporan"].tolist()
        
        col_del, _ = st.columns([2, 8])
        with col_del:
            if st.button(f"🗑️ Hapus {len(daftar_laporan_klik)} Laporan Terpilih", type="primary", use_container_width=True):
                try:
                    def hapus_laporan_aman(worksheet, list_nama_lap, headers):
                        records = worksheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
                        if records:
                            df_temp = pd.DataFrame(records)
                            if "Nama Laporan" in df_temp.columns:
                                df_sisa = df_temp[~df_temp["Nama Laporan"].isin(list_nama_lap)]
                                worksheet.clear()
                                worksheet.append_row(headers)
                                if not df_sisa.empty:
                                    for col in df_sisa.columns:
                                        if pd.api.types.is_datetime64_any_dtype(df_sisa[col]) or df_sisa[col].dtype == 'object': df_sisa[col] = df_sisa[col].astype(str)
                                    worksheet.append_rows(df_sisa.values.tolist(), value_input_option='RAW')

                    with st.spinner("Menghapus data di Cloud..."):
                        hapus_laporan_aman(worksheet_summary, daftar_laporan_klik, ["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"])
                        hapus_laporan_aman(worksheet_tag, daftar_laporan_klik, ["Nama Laporan", "Tipe", "Clean_Tag", "Spend", "Klik_Meta", "Klik_Shopee", "Pesanan", "Kebocoran", "Komisi_Kotor", "Komisi_Bersih", "Profit_Rugi", "ROAS"])
                        hapus_laporan_aman(worksheet_raw_sales, daftar_laporan_klik, ["Nama Laporan", "Clean_Tag", "Nama Produk", "Kategori", "Item Terjual", "Komisi"])
                        hapus_laporan_aman(worksheet_traffic, daftar_laporan_klik, ["Nama Laporan", "Sumber_Traffic", "Klik", "Pesanan", "Komisi_Bersih"])
                        
                    if 'riwayat_summary' in st.session_state: del st.session_state['riwayat_summary']
                    st.rerun()
                except Exception as del_e: st.error(f"Gagal menghapus: {str(del_e)}")

        # ==========================================
        # 6. TAB DETAIL & DASHBOARD BAWAH
        # ==========================================
        st.markdown("<hr style='border: 1px solid #C7D2FE;'>", unsafe_allow_html=True)
        st.subheader(f"🔍 Hasil Bedah Data Rinci: {'Gabungan '+str(len(daftar_laporan_klik))+' Laporan' if len(daftar_laporan_klik) > 1 else daftar_laporan_klik[0]}")
        
        df_detail_tampil = st.session_state.get('cache_tag', pd.DataFrame())
        df_detail_tampil = df_detail_tampil[df_detail_tampil['Nama Laporan'].isin(daftar_laporan_klik)].copy() if not df_detail_tampil.empty and 'Nama Laporan' in df_detail_tampil.columns else pd.DataFrame()

        if not df_detail_tampil.empty:
            df_detail_tampil = df_detail_tampil.groupby(['Clean_Tag', 'Tipe']).agg({'Spend': 'sum', 'Klik_Meta': 'sum', 'Klik_Shopee': 'sum', 'Pesanan': 'sum', 'Komisi_Kotor': 'sum', 'Komisi_Bersih': 'sum', 'Profit_Rugi': 'sum'}).reset_index()
            df_detail_tampil['ROAS'] = df_detail_tampil.apply(lambda r: r['Komisi_Bersih'] / r['Spend'] if r['Spend'] > 0 else 0.0, axis=1)
            df_detail_tampil['Kebocoran'] = df_detail_tampil.apply(lambda r: ((r['Klik_Meta'] - r['Klik_Shopee']) / r['Klik_Meta']) * 100 if r['Klik_Meta'] > 0 else 0.0, axis=1)

            df_iklan_aktif = df_detail_tampil[df_detail_tampil['Tipe'] == "IKLAN (AKTIF)"].copy()
            
            # --- Pembagian Segmentasi Menggunakan Tab Baru ---
            tab_iklan, tab_organik, tab_traffic = st.tabs(["🎯 Kelompok Iklan Aktif", "📱 Kelompok Organik", "🚦 Analisis Sumber Traffic"])
            tag_terpilih = None

            with tab_iklan:
                if not df_iklan_aktif.empty:
                    df_styled_iklan = df_iklan_aktif[['Tipe', 'Clean_Tag', 'Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Kebocoran', 'Komisi_Kotor', 'Profit_Rugi', 'ROAS']].style.format({
                        'Spend': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'), 'Komisi_Kotor': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
                        'Profit_Rugi': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'), 'ROAS': '{:,.2f}x', 'Klik_Meta': lambda x: f"{int(x):,}".replace(',', '.'), 'Klik_Shopee': lambda x: f"{int(x):,}".replace(',', '.'), 'Pesanan': lambda x: f"{int(x):,}".replace(',', '.'), 'Kebocoran': '{:,.2f}%'
                    }).apply(gaya_tabel_detail, axis=1)
                    event_klik_iklan = st.dataframe(df_styled_iklan, use_container_width=True, hide_index=True, on_select="rerun", key="grid_iklan", selection_mode="single-row")
                    if event_klik_iklan and len(event_klik_iklan["selection"]["rows"]) > 0: tag_terpilih = df_iklan_aktif.iloc[event_klik_iklan["selection"]["rows"][0]]["Clean_Tag"]
                else: st.info("Tidak ada tracker dengan status Iklan Aktif.")

            with tab_organik:
                df_organik = df_detail_tampil[df_detail_tampil['Tipe'] != "IKLAN (AKTIF)"].copy().sort_values(by=['Pesanan', 'Komisi_Kotor'], ascending=[False, False])
                if not df_organik.empty:
                    df_styled_organik = df_organik[['Tipe', 'Clean_Tag', 'Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Kebocoran', 'Komisi_Kotor', 'Profit_Rugi', 'ROAS']].style.format({
                        'Spend': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'), 'Komisi_Kotor': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
                        'Profit_Rugi': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'), 'ROAS': '{:,.2f}x', 'Klik_Meta': lambda x: f"{int(x):,}".replace(',', '.'), 'Klik_Shopee': lambda x: f"{int(x):,}".replace(',', '.'), 'Pesanan': lambda x: f"{int(x):,}".replace(',', '.'), 'Kebocoran': '{:,.2f}%'
                    }).apply(gaya_tabel_detail, axis=1)
                    event_klik_organik = st.dataframe(df_styled_organik, use_container_width=True, hide_index=True, on_select="rerun", key="grid_org", selection_mode="single-row")
                    if event_klik_organik and len(event_klik_organik["selection"]["rows"]) > 0: tag_terpilih = df_organik.iloc[event_klik_organik["selection"]["rows"][0]]["Clean_Tag"]
                else: st.info("Tidak ada tracker dengan status Organik.")

            with tab_traffic:
                df_all_traffic = st.session_state.get('cache_traffic', pd.DataFrame())
                
                # Cek apakah sheet Riwayat_Traffic sudah ada isinya
                if not df_all_traffic.empty and 'Nama Laporan' in df_all_traffic.columns:
                    df_traffic_filtered = df_all_traffic[df_all_traffic['Nama Laporan'].isin(daftar_laporan_klik)].copy()
                    
                    if not df_traffic_filtered.empty:
                        df_traffic_tampil = df_traffic_filtered.groupby('Sumber_Traffic').agg({'Klik': 'sum', 'Pesanan': 'sum', 'Komisi_Bersih': 'sum'}).reset_index()
                        df_traffic_tampil = df_traffic_tampil.sort_values(by=['Komisi_Bersih', 'Klik'], ascending=[False, False])
                        
                        st.markdown("**Pemetaan Sumber Konversi (Platform & Konten)**")
                        st.dataframe(df_traffic_tampil.style.format({
                            'Klik': lambda x: f"{int(x):,}".replace(',', '.'),
                            'Pesanan': lambda x: f"{int(x):,}".replace(',', '.'),
                            'Komisi_Bersih': lambda x: f"Rp {int(round(x)):,}".replace(',', '.')
                        }), use_container_width=True, hide_index=True)
                    else:
                        st.info("⚠️ Data trafik untuk laporan ini kosong. Ini biasanya karena laporan diunggah sebelum fitur trafik ditambahkan.\n\n**Solusi:** Silakan hapus laporan ini melalui tabel di atas, lalu upload ulang file CSV-nya agar data trafik ikut terekstrak.")
                else:
                    st.warning("📭 Database sumber trafik (Riwayat_Traffic) masih kosong. Silakan upload dan proses file CSV baru agar data trafik mulai tersimpan ke dalam sistem.")

            if tag_terpilih:
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader(f"📦 Rincian Produk Terjual: #{tag_terpilih}")
                df_all_sales = st.session_state.get('cache_sales', pd.DataFrame())
                if not df_all_sales.empty:
                    df_product_selected = df_all_sales[(df_all_sales['Nama Laporan'].isin(daftar_laporan_klik)) & (df_all_sales['Clean_Tag'] == tag_terpilih)].copy()
                    if not df_product_selected.empty:
                        df_produk_tampil = df_product_selected.groupby(['Nama Produk', 'Kategori']).agg(Item_Terjual=('Item Terjual', 'sum'), Komisi_Diterima=('Komisi', 'sum')).reset_index()
                        st.dataframe(df_produk_tampil.style.format({'Item_Terjual': lambda x: f"{int(x):,}".replace(',', '.'), 'Komisi_Diterima': lambda x: f"Rp {int(round(x)):,}".replace(',', '.')}), use_container_width=True, hide_index=True)
