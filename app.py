import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI GOOGLE SHEETS
# ==========================================
st.set_page_config(page_title="Affiliate Advanced Analytics", layout="wide")

st.title("📊 Dashboard Evaluasi & Performa Affiliate")
st.write("Kelola pengeluaran iklan Meta dan optimalkan komisi bersih Shopee Anda dalam satu layar (Terintegrasi Google Sheets).")

BULAN_INDO = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

# Fungsi menghubungkan ke Google Sheets menggunakan trik Raw JSON Secrets
@st.cache_resource
def inisialisasi_gspread():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        raw_json_teks = st.secrets["google_credentials"]["json_teks"]
        kredensial_dict = json.loads(raw_json_teks)
        creds = Credentials.from_service_account_info(kredensial_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Format JSON di Secrets salah atau tidak terbaca: {str(e)}")
        st.stop()

try:
    gc = inisialisasi_gspread()
    spreadsheet_id = st.secrets["spreadsheet"]["id"]
    sheet_utama = gc.open_by_key(spreadsheet_id)
except Exception as e:
    st.error(f"❌ Gagal tersambung ke Google Sheets. Periksa konfigurasi Secrets Anda. Error: {str(e)}")
    st.stop()

# Membuat tab otomatis jika belum ada di Google Sheets
def dapatkan_atau_buat_worksheet(nama_sheet, headers):
    try:
        return sheet_utama.worksheet(nama_sheet)
    except:
        ws = sheet_utama.add_worksheet(title=nama_sheet, rows="2000", cols=str(len(headers) + 2))
        ws.append_row(headers)
        return ws

worksheet_summary = dapatkan_atau_buat_worksheet("Riwayat_Summary", ["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"])
worksheet_tag = dapatkan_atau_buat_worksheet("Riwayat_Tag", ["Nama Laporan", "Tipe", "Clean_Tag", "Spend", "Klik_Meta", "Klik_Shopee", "Pesanan", "Kebocoran", "Komisi_Kotor", "Komisi_Bersih", "Profit_Rugi", "ROAS"])
worksheet_raw_sales = dapatkan_atau_buat_worksheet("Raw_Sales", ["Nama Laporan", "Clean_Tag", "Nama Produk", "Kategori", "Item Terjual", "Komisi"])

# ==========================================
# 2. LOAD DATA DARI GOOGLE SHEETS KE SYSTEM
# ==========================================
try:
    records_summary = worksheet_summary.get_all_records()
    if records_summary:
        df_load_summary = pd.DataFrame(records_summary)
        df_load_summary['Tanggal'] = pd.to_datetime(df_load_summary['Tanggal'], errors='coerce').dt.date
        # Pastikan tipe data numeric aman saat dibaca dari Cloud
        for col in ["Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"]:
            if col in df_load_summary.columns:
                df_load_summary[col] = pd.to_numeric(df_load_summary[col], errors='coerce').fillna(0.0)
    else:
        df_load_summary = pd.DataFrame(columns=["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"])
except Exception as e:
    st.error(f"Gagal memuat database internal: {str(e)}")
    st.stop()

st.session_state['riwayat_summary'] = df_load_summary

# Fungsi pembantu untuk membersihkan tag video/iklan
def bersihkan_tag(x):
    if pd.isna(x) or str(x).strip() == "" or str(x).lower() == "nan":
        return "Organik"
    s = str(x).strip()
    if s.startswith('#'): s = s[1:]
    if s.endswith('----'): s = s[:-4]
    return s

# Fungsi Pencarian Kolom Cerdas & Sensitif
def cari_kolom(list_kolom, kata_kunci_list, default_name):
    for col in list_kolom:
        c = str(col).strip().lower()
        for kw in kata_kunci_list:
            if kw.lower() == c:
                return col
    for col in list_kolom:
        c = str(col).strip().lower()
        for kw in kata_kunci_list:
            if kw.lower() in c:
                return col
    return default_name

# 🔥 Fungsi Cerdas Pembaca CSV: Anti-Karakter Rusak & Kebal Salah Pembatas Kolom
def baca_csv_sakti(file):
    raw_bytes = file.read()
    file.seek(0)
    # Gunakan utf-8-sig untuk membuang penanda BOM \ufeff bawaan Shopee secara paksa
    try: teks = raw_bytes.decode('utf-8-sig')
    except: teks = raw_bytes.decode('latin-1')
    
    baris_pertama = teks.split('\n')[0] if '\n' in teks else ""
    if ';' in baris_pertama and baris_pertama.count(';') > baris_pertama.count(','):
        sep = ';'
    elif '\t' in baris_pertama:
        sep = '\t'
    else:
        sep = ','
        
    df = pd.read_csv(io.StringIO(teks), sep=sep)
    df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
    return df

def gaya_tabel_summary(row):
    gaya = [''] * len(row)
    if 'Komisi Iklan' in row.index and 'Spend' in row.index:
        profit_iklan = row['Komisi Iklan'] - row['Spend']
        warna_iklan = 'green' if profit_iklan >= 0 else 'red'
        gaya[row.index.get_loc('Komisi Iklan')] = f'color: {warna_iklan}; font-weight: bold;'
    
    if 'Profit' in row.index:
        warna_total = 'green' if row['Profit'] >= 0 else 'red'
        gaya[row.index.get_loc('Total Komisi (Nett)')] = f'color: {warna_total}; font-weight: bold;'
        gaya[row.index.get_loc('Profit')] = f'color: {warna_total}; font-weight: bold;'
    return gaya

def gaya_tabel_detail(row):
    gaya = [''] * len(row)
    if 'Tipe' in row.index and row['Tipe'] == "IKLAN (AKTIF)":
        gaya = ['background-color: #f0f4f8; border-left: 4px solid #1f77b4;'] * len(row)
    return gaya

# ==========================================
# 3. AREA UPLOAD FILE DI BAGIAN ATAS
# ==========================================
with st.expander("📤 AREA UPLOAD FILE BARU (Drop 3 File CSV Mentah Anda Sekaligus)", expanded=True):
    tanggal_laporan = st.date_input("Tanggal Laporan:", value=datetime.now().date())
    nama_bulan = BULAN_INDO[tanggal_laporan.month]
    default_nama = f"Laporan {tanggal_laporan.day:02d} {nama_bulan}"
    
    with st.form("form_upload", clear_on_submit=True):
        col_input1, col_input2 = st.columns([2, 4])
        with col_input1:
            nama_laporan = st.text_input("Nama / Catatan Laporan:", value=default_nama)
        with col_input2:
            uploaded_files = st.file_uploader("Pilih berkas CSV iklan, klik, dan penjualan:", type=["csv"], accept_multiple_files=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        tombol_proses = st.form_submit_button("🚀 Proses & Bedah Laporan", use_container_width=True)

if tombol_proses:
    if len(uploaded_files) < 3:
        st.error("Silakan unggah minimal 3 file CSV terlebih dahulu.")
    elif nama_laporan in st.session_state['riwayat_summary']['Nama Laporan'].values:
        st.warning("⚠️ Nama laporan sudah ada di Google Sheets. Silakan hapus laporan lama terlebih dahulu.")
    else:
        df_meta, df_clicks, df_sales = None, None, None
        for file in uploaded_files:
            df_temp = baca_csv_sakti(file)
            if df_temp is not None:
                if 'Jumlah yang dibelanjakan (IDR)' in df_temp.columns or 'Nama iklan' in df_temp.columns:
                    df_meta = df_temp
                elif 'Klik ID' in df_temp.columns and 'Tag_link' in df_temp.columns:
                    df_clicks = df_temp
                elif any(k dalam str(df_temp.columns).lower() for k in ['komisi per pesanan', 'komisi bersih', 'nama produk', 'product name', 'info produk']):
                    df_sales = df_temp

        if df_meta is not None and df_clicks is not None and df_sales is not None:
            # Perluasan Logika Deteksi Kata Kunci
            kolom_pesanan = cari_kolom(df_sales.columns, ['id pesanan', 'order id', 'no pesanan', 'no. pesanan', 'id pemesanan'], df_sales.columns[0])
            kolom_tag_sales = cari_kolom(df_sales.columns, ['tag_link1', 'tag link', 'sub id', 'tag_link', 'tag'], 'Tag_link1')
            kolom_komisi_kotor = cari_kolom(df_sales.columns, ['total komisi per pesanan', 'komisi kotor', 'gross commission'], df_sales.columns[-1])
            kolom_komisi_bersih = cari_kolom(df_sales.columns, ['komisi bersih affiliate', 'komisi bersih', 'net commission', 'nett commission'], kolom_komisi_kotor)
            kolom_nama_produk = cari_kolom(df_sales.columns, ['nama produk', 'product name', 'info produk', 'judul', 'item', 'nama barang', 'product'], 'Nama Produk')
            kolom_kategori_produk = cari_kolom(df_sales.columns, ['kategori kunci', 'kategori', 'category', 'kategori produk'], 'Kategori')
            kolom_jumlah_item = cari_kolom(df_sales.columns, ['item terjual', 'jumlah', 'quantity', 'qty', 'jumlah produk'], 'Item Terjual')

            # Pembersih Format Angka Rupiah
            def bersihkan_angka_sakti(series):
                def konversi_nilai(val):
                    val = str(val).strip().replace('Rp', '').replace(' ', '').replace(' ', '')
                    if not val or val.lower() == 'nan' or val == '-': return 0.0
                    if ',' in val and '.' in val:
                        if val.find('.') < val.find(','): val = val.replace('.', '').replace(',', '.')
                        else: val = val.replace(',', '')
                    elif ',' in val:
                        parts = val.split(',')
                        if len(parts[-1]) == 3: val = val.replace(',', '')
                        else: val = val.replace(',', '.')
                    elif '.' in val:
                        parts = val.split('.')
                        if len(parts[-1]) == 3: val = val.replace('.', '')
                    try: return float(val)
                    except: return 0.0
                return series.apply(konversi_nilai)

            df_meta['Jumlah yang dibelanjakan (IDR)'] = bersihkan_angka_sakti(df_meta['Jumlah yang dibelanjakan (IDR)'])
            if 'Klik tautan' in df_meta.columns:
                df_meta['Klik tautan'] = bersihkan_angka_sakti(df_meta['Klik tautan']).fillna(0).astype(int)
                
            df_sales[kolom_komisi_kotor] = bersihkan_angka_sakti(df_sales[kolom_komisi_kotor])
            df_sales[kolom_komisi_bersih] = bersihkan_angka_sakti(df_sales[kolom_komisi_bersih])
            df_sales[kolom_jumlah_item] = bersihkan_angka_sakti(df_sales[kolom_jumlah_item]).fillna(1).astype(int)

            df_meta['Clean_Tag'] = df_meta['Nama iklan'].apply(bersihkan_tag)
            df_clicks['Clean_Tag'] = df_clicks['Tag_link'].apply(bersihkan_tag)
            df_sales['Clean_Tag'] = df_sales[kolom_tag_sales].apply(bersihkan_tag)

            ad_tags = set(df_meta[df_meta['Jumlah yang dibelanjakan (IDR)'] > 0]['Clean_Tag'].unique())

            meta_sum = df_meta.groupby('Clean_Tag').agg(Spend=('Jumlah yang dibelanjakan (IDR)', 'sum'), Klik_Meta=('Klik tautan', 'sum')).reset_index()
            click_sum = df_clicks.groupby('Clean_Tag').agg(Klik_Shopee=('Klik ID', 'count')).reset_index()
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
                # 1. Simpan Utama
                worksheet_summary.append_row([str(tanggal_laporan), nama_laporan, float(total_spend), float(komisi_iklan_nett), float(komisi_organik_nett), float(total_komisi_nett), float(total_profit)])
                
                # 2. Simpan Per Tag
                rows_tag_to_save = []
                for _, row in merged.iterrows():
                    rows_tag_to_save.append([nama_laporan, str(row['Tipe']), str(row['Clean_Tag']), float(row['Spend']), int(row['Klik_Meta']), int(row['Klik_Shopee']), int(row['Pesanan']), float(row['Kebocoran']), float(row['Komisi_Kotor']), float(row['Komisi_Bersih']), float(row['Profit_Rugi']), float(row['ROAS'])])
                if rows_tag_to_save: worksheet_tag.append_rows(rows_tag_to_save)
                
                # 3. Simpan Item Penjualan Raw
                rows_to_save = []
                for _, row in df_sales.iterrows():
                    nama_prod_val = str(row[kolom_nama_produk]).strip() if kolom_nama_produk in df_sales.columns else "Produk Tidak Diketahui"
                    kat_prod_val = str(row[kolom_kategori_produk]).strip() if kolom_kategori_produk in df_sales.columns else "Umum"
                    rows_to_save.append([nama_laporan, str(row['Clean_Tag']), nama_prod_val, kat_prod_val, int(row[kolom_jumlah_item]), float(row[kolom_komisi_bersih])])
                if rows_to_save: worksheet_raw_sales.append_rows(rows_to_save)
                
                st.success(f"✅ Data '{nama_laporan}' Sukses Terkunci!")
                st.rerun()
            except Exception as sheet_err:
                st.error(f"Gagal menulis data ke Google Sheets: {str(sheet_err)}")
        else:
            st.error("Gagal mendeteksi kecocokan struktur file. Pastikan Anda mengunggah 3 file yang benar.")

st.markdown("---")

# ==========================================
# 4. FILTER RENTANG WAKTU DATA
# ==========================================
st.subheader("🔍 Filter Rentang Waktu Data")
col_btn1, col_btn2, col_btn3, col_date = st.columns([1, 1, 1, 3])
today = datetime.now().date()

if 'start_filter' not in st.session_state: st.session_state['start_filter'] = today - timedelta(days=7)
if 'end_filter' not in st.session_state: st.session_state['end_filter'] = today

with col_btn1:
    if st.button("📅 Kemarin", use_container_width=True):
        st.session_state['start_filter'] = today - timedelta(days=1); st.session_state['end_filter'] = today - timedelta(days=1)
with col_btn2:
    if st.button("📅 Bulan Ini", use_container_width=True):
        st.session_state['start_filter'] = today.replace(day=1); st.session_state['end_filter'] = today
with col_btn3:
    if st.button("📅 Bulan Lalu", use_container_width=True):
        last_month_end = today.replace(day=1) - timedelta(days=1)
        st.session_state['start_filter'] = last_month_end.replace(day=1); st.session_state['end_filter'] = last_month_end

with col_date:
    rentang_tanggal = st.date_input("Atau Pilih Kustom Kalender:", value=(st.session_state['start_filter'], st.session_state['end_filter']))

if isinstance(rentang_tanggal, tuple) and len(rentang_tanggal) == 2:
    filter_start, filter_end = rentang_tanggal
else:
    filter_start, filter_end = st.session_state['start_filter'], st.session_state['end_filter']

df_filtered = st.session_state['riwayat_summary']
if not df_filtered.empty:
    df_filtered = df_filtered[(df_filtered['Tanggal'] >= filter_start) & (df_filtered['Tanggal'] <= filter_end)]

# ==========================================
# 5. KOTAK METRIK SUMMARY (KPI)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
col_m1, col_m2, col_m3 = st.columns(3)
val_spend = pd.to_numeric(df_filtered['Spend'], errors='coerce').sum() if not df_filtered.empty else 0
val_komisi = pd.to_numeric(df_filtered['Total Komisi (Nett)'], errors='coerce').sum() if not df_filtered.empty else 0
val_profit = pd.to_numeric(df_filtered['Profit'], errors='coerce').sum() if not df_filtered.empty else 0

with col_m1: st.metric(label="💸 Total Pengeluaran Iklan", value=f"Rp {val_spend:,.0f}")
with col_m2: st.metric(label="💰 Total Komisi Masuk (Nett)", value=f"Rp {val_komisi:,.0f}")
with col_m3: st.metric(label="📈 Keuntungan Bersih (Profit)", value=f"Rp {val_profit:,.0f}")

# ==========================================
# 6. TABEL UTAMA & ACTION HAPUS DATA
# ==========================================
st.subheader("📋 Riwayat Laporan Harian")
if df_filtered.empty:
    st.info("Belum ada data terekam.")
else:
    df_styled_summary = df_filtered.style.format({'Spend': 'Rp{:,.0f}', 'Komisi Iklan': 'Rp{:,.0f}', 'Komisi Organik': 'Rp{:,.0f}', 'Total Komisi (Nett)': 'Rp{:,.0f}', 'Profit': 'Rp{:,.0f}'}).apply(gaya_tabel_summary, axis=1)
    event_pilih = st.dataframe(df_styled_summary, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

    if event_pilih and len(event_pilih["selection"]["rows"]) > 0:
        indeks_terpilih = event_pilih["selection"]["rows"][0]
        laporan_terpilih = df_filtered.iloc[indeks_terpilih]
        nama_laporan_klik = laporan_terpilih["Nama Laporan"]
        
        if st.button(f"🗑️ Hapus Laporan dari Cloud: {nama_laporan_klik}", type="secondary"):
            try:
                cell = worksheet_summary.find(nama_laporan_klik)
                worksheet_summary.delete_rows(cell.row)
                
                cells_raw = worksheet_raw_sales.findall(nama_laporan_klik)
                for r in sorted(list(set([c.row for c in cells_raw])), reverse=True): worksheet_raw_sales.delete_rows(r)
                
                cells_tag = worksheet_tag.findall(nama_laporan_klik)
                for r in sorted(list(set([c.row for c in cells_tag])), reverse=True): worksheet_tag.delete_rows(r)
                    
                st.toast("Sukses menghapus data lama!")
                st.rerun()
            except Exception as del_e:
                st.error(f"Gagal menghapus: {str(del_e)}")

        # ==========================================
        # 7. HASIL BEDAH DATA DETIL PER VIDEO (TAG)
        # ==========================================
        st.markdown("---")
        st.subheader(f"🔍 Hasil Bedah Data Rinci: {nama_laporan_klik}")
        
        try:
            all_tag_records = worksheet_tag.get_all_records()
            df_detail_tampil = pd.DataFrame(all_tag_records) if all_tag_records else pd.DataFrame()
            if not df_detail_tampil.empty:
                df_detail_tampil = df_detail_tampil[df_detail_tampil['Nama Laporan'] == nama_laporan_klik]
        except:
            df_detail_tampil = pd.DataFrame()

        if not df_detail_tampil.empty:
            # Paksa konversi tipe data numerik agar kalkulasi detail presisi
            for col in ['Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Kebocoran', 'Komisi_Kotor', 'Komisi_Bersih', 'Profit_Rugi', 'ROAS']:
                if col in df_detail_tampil.columns:
                    df_detail_tampil[col] = pd.to_numeric(df_detail_tampil[col], errors='coerce').fillna(0.0)

            df_iklan_aktif = df_detail_tampil[df_detail_tampil['Tipe'] == "IKLAN (AKTIF)"]
            total_spend_iklan = df_iklan_aktif['Spend'].sum()
            roas_iklan_gabungan = (df_iklan_aktif['Komisi_Bersih'].sum() / total_spend_iklan) if total_spend_iklan > 0 else 0.0
            
            col_ad1, col_ad2 = st.columns(2)
            with col_ad1: st.metric(label="💳 Total Spend Iklan Video", value=f"Rp {total_spend_iklan:,.0f}")
            with col_ad2: st.metric(label="📊 ROAS Gabungan Iklan (Nett)", value=f"{roas_iklan_gabungan:,.2f}x")
            
            st.write("💡 *Klik salah satu baris di bawah ini untuk mengurai item produk spesifiknya:*")

            df_styled_detail = df_detail_tampil[['Tipe', 'Clean_Tag', 'Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Kebocoran', 'Komisi_Kotor', 'Komisi_Bersih', 'Profit_Rugi', 'ROAS']].style.format({
                'Spend': 'Rp{:,.0f}', 'Komisi_Kotor': 'Rp{:,.0f}', 'Komisi_Bersih': 'Rp{:,.0f}', 'Profit_Rugi': 'Rp{:,.0f}', 
                'ROAS': '{:,.2f}x', 'Klik_Meta': '{:,.0f}', 'Klik_Shopee': '{:,.0f}', 'Pesanan': '{:,.0f}', 'Kebocoran': '{:,.2f}%'
            }).apply(gaya_tabel_detail, axis=1)
            
            event_klik_detail = st.dataframe(df_styled_detail, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

            # ==========================================
            # 8. RINCIAN ITEM PRODUK YANG TERJUAL
            # ==========================================
            if event_klik_detail and len(event_klik_detail["selection"]["rows"]) > 0:
                indeks_detail = event_klik_detail["selection"]["rows"][0]
                tag_terpilih = df_detail_tampil.iloc[indeks_detail]["Clean_Tag"]
                
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader(f"📦 Rincian Produk Terjual untuk Tag: #{tag_terpilih}")
                
                try:
                    all_sales_records = worksheet_raw_sales.get_all_records()
                    df_all_sales = pd.DataFrame(all_sales_records) if all_sales_records else pd.DataFrame()
                except:
                    df_all_sales = pd.DataFrame()

                if not df_all_sales.empty:
                    df_product_selected = df_all_sales[(df_all_sales['Nama Laporan'] == nama_laporan_klik) & (df_all_sales['Clean_Tag'] == tag_terpilih)]
                    
                    if not df_product_selected.empty:
                        kolom_nama_sh = cari_kolom(df_product_selected.columns, ['nama produk', 'product', 'nama'], 'Nama Produk')
                        kolom_kat_sh = cari_kolom(df_product_selected.columns, ['kategori', 'category'], 'Kategori')
                        kolom_item_sh = cari_kolom(df_product_selected.columns, ['item terjual', 'jumlah', 'quantity', 'qty'], 'Item Terjual')
                        kolom_komisi_sh = cari_kolom(df_product_selected.columns, ['komisi', 'commission'], 'Komisi')

                        df_product_selected[kolom_komisi_sh] = pd.to_numeric(df_product_selected[kolom_komisi_sh], errors='coerce').fillna(0.0)
                        df_product_selected[kolom_item_sh] = pd.to_numeric(df_product_selected[kolom_item_sh], errors='coerce').fillna(1).astype(int)

                        df_produk_tampil = df_product_selected.groupby([kolom_nama_sh, kolom_kat_sh]).agg(
                            Item_Terjual=(kolom_item_sh, 'sum'),
                            Komisi_Diterima=(kolom_komisi_sh, 'sum')
                        ).reset_index()
                        
                        df_produk_tampil.columns = ['Nama Produk', 'Kategori', 'Item Terjual', 'Komisi Bersih']
                        st.dataframe(df_produk_tampil.style.format({'Item Terjual': '{:,.0f}', 'Komisi Bersih': 'Rp{:,.0f}'}), use_container_width=True, hide_index=True)
                    else:
                        st.info("Tidak ada rincian item produk khusus untuk tag ini.")
