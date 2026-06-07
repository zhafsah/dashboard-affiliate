import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import json
import io

# ==========================================
# 0. FUNGSI GLOBAL PEMBERSIH ANGKA SAKTI
# ==========================================
def bersihkan_angka_sakti(series):
    def konversi_nilai(val):
        if pd.isna(val):
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        
        # PERBAIKAN: Menghapus '%' agar data persentase kebocoran tidak gagal dikonversi menjadi float
        s = str(val).strip().replace('Rp', '').replace('%', '').replace(' ', '')
        if not s or s.lower() in ['nan', '-', 'null']:
            return 0.0
        
        if ',' in s and '.' in s:
            if s.find('.') < s.find(','):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            parts = s.split(',')
            if len(parts[-1]) == 2:  
                s = s.replace(',', '.')
            elif len(parts[-1]) == 3 and len(parts) > 1:
                s = s.replace(',', '')
            else:
                s = s.replace(',', '.')
                
        try:
            return float(s)
        except:
            return 0.0
            
    return series.apply(konversi_nilai)


# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI GOOGLE SHEETS
# ==========================================
st.set_page_config(page_title="Affiliate Advanced Analytics", layout="wide")

st.title("📊 Dashboard Evaluasi & Performa Affiliate")
st.write("Kelola pengeluaran iklan Meta dan optimalkan komisi bersih Shopee Anda secara otomatis.")

BULAN_INDO = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

@st.cache_resource
def inisialisasi_gspread():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        raw_json_teks = st.secrets["google_credentials"]["json_teks"]
        kredensial_dict = json.loads(raw_json_teks)
        creds = Credentials.from_service_account_info(kredensial_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Format JSON di Secrets salah: {str(e)}")
        st.stop()

try:
    gc = inisialisasi_gspread()
    spreadsheet_id = st.secrets["spreadsheet"]["id"]
    sheet_utama = gc.open_by_key(spreadsheet_id)
except Exception as e:
    st.error(f"❌ Gagal tersambung ke Google Sheets: {str(e)}")
    st.stop()

def dapatkan_atau_buat_worksheet(nama_sheet, headers):
    try:
        return sheet_utama.worksheet(nama_sheet)
    except:
        ws = sheet_utama.add_worksheet(title=nama_sheet, rows="5000", cols=str(len(headers) + 2))
        ws.append_row(headers)
        return ws

worksheet_summary = dapatkan_atau_buat_worksheet("Riwayat_Summary", ["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"])
worksheet_tag = dapatkan_atau_buat_worksheet("Riwayat_Tag", ["Nama Laporan", "Tipe", "Clean_Tag", "Spend", "Klik_Meta", "Klik_Shopee", "Pesanan", "Kebocoran", "Komisi_Kotor", "Komisi_Bersih", "Profit_Rugi", "ROAS"])
worksheet_raw_sales = dapatkan_atau_buat_worksheet("Raw_Sales", ["Nama Laporan", "Clean_Tag", "Nama Produk", "Kategori", "Item Terjual", "Komisi"])


# ==========================================
# 2. SINKRONISASI OTOMATIS & HEALING DATA
# ==========================================
if 'riwayat_summary' not in st.session_state:
    with st.spinner("Sinkronisasi aman data cloud harian..."):
        try:
            records_summary = worksheet_summary.get_all_records()
            df_load_summary = pd.DataFrame(records_summary) if records_summary else pd.DataFrame(columns=["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"])
            
            records_tag = worksheet_tag.get_all_records()
            df_load_tag = pd.DataFrame(records_tag) if records_tag else pd.DataFrame()
            
            records_sales = worksheet_raw_sales.get_all_records()
            df_load_sales = pd.DataFrame(records_sales) if records_sales else pd.DataFrame()

            # Bersihkan angka dasar
            if not df_load_summary.empty:
                df_load_summary['Tanggal'] = pd.to_datetime(df_load_summary['Tanggal'], errors='coerce').dt.date
                for col in ["Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"]:
                    df_load_summary[col] = bersihkan_angka_sakti(df_load_summary[col])

            if not df_load_tag.empty:
                for col in ['Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Kebocoran', 'Komisi_Kotor', 'Komisi_Bersih', 'Profit_Rugi', 'ROAS']:
                    df_load_tag[col] = bersihkan_angka_sakti(df_load_tag[col])

            if not df_load_sales.empty:
                if 'Komisi' in df_load_sales.columns: df_load_sales['Komisi'] = bersihkan_angka_sakti(df_load_sales['Komisi'])
                if 'Item Terjual' in df_load_sales.columns: df_load_sales['Item Terjual'] = pd.to_numeric(df_load_sales['Item Terjual'], errors='coerce').fillna(1).astype(int)

            # ENGINE SELF-HEALING
            laporan_terinflasi = set()
            if not df_load_tag.empty:
                kondisi_inflasi = (df_load_tag['Tipe'] == "IKLAN (AKTIF)") & (df_load_tag['Spend'] > 0) & (df_load_tag['ROAS'] > 15.0)
                laporan_terinflasi.update(df_load_tag[kondisi_inflasi]['Nama Laporan'].unique())
            if not df_load_summary.empty:
                kondisi_sum_inflasi = (df_load_summary['Spend'] > 0) & ((df_load_summary['Total Komisi (Nett)'] / df_load_summary['Spend']) > 15.0)
                laporan_terinflasi.update(df_load_summary[kondisi_sum_inflasi]['Nama Laporan'].unique())

            for nama_lap in laporan_terinflasi:
                if not df_load_summary.empty:
                    idx = df_load_summary['Nama Laporan'] == nama_lap
                    if df_load_summary.loc[idx, "Total Komisi (Nett)"].max() > 500000:
                        df_load_summary.loc[idx, "Komisi Iklan"] /= 100.0
                        df_load_summary.loc[idx, "Komisi Organik"] /= 100.0
                        df_load_summary.loc[idx, "Total Komisi (Nett)"] /= 100.0
                        df_load_summary.loc[idx, "Profit"] = df_load_summary.loc[idx, "Total Komisi (Nett)"] - df_load_summary.loc[idx, "Spend"]

                if not df_load_tag.empty:
                    idx_tag = df_load_tag['Nama Laporan'] == nama_lap
                    if df_load_tag.loc[idx_tag, "Komisi_Bersih"].max() > 500000:
                        df_load_tag.loc[idx_tag, "Komisi_Kotor"] /= 100.0
                        df_load_tag.loc[idx_tag, "Komisi_Bersih"] /= 100.0
                        df_load_tag.loc[idx_tag, "ROAS"] /= 100.0
                        df_load_tag.loc[idx_tag, "Profit_Rugi"] = df_load_tag.loc[idx_tag, "Komisi_Bersih"] - df_load_tag.loc[idx_tag, "Spend"]

                if not df_load_sales.empty:
                    idx_sales = df_load_sales['Nama Laporan'] == nama_lap
                    if 'Komisi' in df_load_sales.columns and df_load_sales.loc[idx_sales, 'Komisi'].max() > 50000:
                        df_load_sales.loc[idx_sales, 'Komisi'] /= 100.0

            st.session_state['riwayat_summary'] = df_load_summary
            st.session_state['cache_tag'] = df_load_tag
            st.session_state['cache_sales'] = df_load_sales
        except Exception as e:
            st.error(f"Gagal memuat otomatis database internal: {str(e)}")
            st.stop()


# ==========================================
# 3. AREA ENGINE PEMROSES DATA BARU
# ==========================================
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

def baca_csv_sakti(file):
    raw_bytes = file.read()
    file.seek(0)
    try: teks = raw_bytes.decode('utf-8-sig')
    except: teks = raw_bytes.decode('latin-1')
    baris_pertama = teks.split('\n')[0] if '\n' in teks else ""
    sep = ';' if ';' in baris_pertama and baris_pertama.count(';') > baris_pertama.count(',') else ( '\t' if '\t' in baris_pertama else ',' )
    df = pd.read_csv(io.StringIO(teks), sep=sep)
    df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")
    return df

def gaya_tabel_detail(row):
    gaya = [''] * len(row)
    if 'Klik_Meta' in row.index and 'Klik_Shopee' in row.index:
        k_meta = row['Klik_Meta']
        k_shopee = row['Klik_Shopee']
        warna = 'background-color: #d4edda; color: #155724;' if k_shopee >= k_meta else 'background-color: #f8d7da; color: #721c24;'
        gaya[row.index.get_loc('Kebocoran')] = warna
    return gaya

def gaya_tabel_summary(row):
    gaya = [''] * len(row)
    if 'Profit' in row.index:
        gaya[row.index.get_loc('Profit')] = 'color: green; font-weight: bold;' if row['Profit'] >= 0 else 'color: red; font-weight: bold;'
    return gaya

with st.expander("📤 AREA UPLOAD FILE BARU (Drop 3 File CSV Mentah Anda Sekaligus)", expanded=True):
    tanggal_laporan = st.date_input("Tanggal Laporan:", value=datetime.now().date())
    nama_bulan = BULAN_INDO[tanggal_laporan.month]
    default_nama = f"Laporan {tanggal_laporan.day:02d} {nama_bulan}"
    
    with st.form("form_upload", clear_on_submit=True):
        col_input1, col_input2 = st.columns([2, 4])
        with col_input1: nama_laporan = st.text_input("Nama / Catatan Laporan:", value=default_nama)
        with col_input2: uploaded_files = st.file_uploader("Pilih berkas CSV:", type=["csv"], accept_multiple_files=True)
        tombol_proses = st.form_submit_button("🚀 Proses & Bedah Laporan", use_container_width=True)

if tombol_proses:
    if len(uploaded_files) < 3:
        st.error("Silakan unggah minimal 3 file CSV terlebih dahulu.")
    elif nama_laporan in st.session_state['riwayat_summary']['Nama Laporan'].values:
        st.warning("⚠️ Nama laporan sudah ada. Silakan hapus laporan lama terlebih dahulu.")
    else:
        df_meta, df_clicks, df_sales = None, None, None
        for file in uploaded_files:
            df_temp = baca_csv_sakti(file)
            if df_temp is not None:
                if 'Jumlah yang dibelanjakan (IDR)' in df_temp.columns or 'Nama iklan' in df_temp.columns: df_meta = df_temp
                elif 'Klik ID' in df_temp.columns and 'Tag_link' in df_temp.columns: df_clicks = df_temp
                elif any(k in str(df_temp.columns).lower() for k in ['komisi per pesanan', 'komisi bersih', 'nama produk']): df_sales = df_temp

        if df_meta is not None and df_clicks is not None and df_sales is not None:
            kolom_pesanan = cari_kolom(df_sales.columns, ['id pesanan', 'order id', 'no pesanan'], df_sales.columns[0])
            kolom_tag_sales = cari_kolom(df_sales.columns, ['tag_link1', 'tag link', 'sub id', 'tag_link'], 'Tag_link1')
            kolom_komisi_kotor = cari_kolom(df_sales.columns, ['komisi kotor', 'gross commission', 'total komisi per pesanan'], df_sales.columns[-1])
            kolom_komisi_bersih = cari_kolom(df_sales.columns, ['komisi bersih', 'net commission', 'nett commission'], kolom_komisi_kotor)
            kolom_nama_produk = cari_kolom(df_sales.columns, ['nama produk', 'product name', 'info produk'], 'Nama Produk')
            kolom_kategori_produk = cari_kolom(df_sales.columns, ['kategori'], 'Kategori')
            kolom_jumlah_item = cari_kolom(df_sales.columns, ['item terjual', 'jumlah', 'qty'], 'Item Terjual')

            df_meta['Jumlah yang dibelanjakan (IDR)'] = bersihkan_angka_sakti(df_meta['Jumlah yang dibelanjakan (IDR)'])
            df_meta['Klik tautan'] = bersihkan_angka_sakti(df_meta['Klik tautan']).fillna(0).astype(int) if 'Klik tautan' in df_meta.columns else 0
                
            df_sales[kolom_komisi_kotor] = bersihkan_angka_sakti(df_sales[kolom_komisi_kotor])
            df_sales[kolom_komisi_bersih] = bersihkan_angka_sakti(df_sales[kolom_komisi_bersih])
            df_sales[kolom_jumlah_item] = pd.to_numeric(df_sales[kolom_jumlah_item], errors='coerce').fillna(1).astype(int)

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
            
            # PERBAIKAN: Rumus Kebocoran murni & aman dari hasil minus akibat crossover tracking kustom
            merged['Kebocoran'] = merged.apply(lambda r: max(0.0, ((r['Klik_Meta'] - r['Klik_Shopee']) / r['Klik_Meta']) * 100) if r['Klik_Meta'] > 0 else 0.0, axis=1)
            merged['Profit_Rugi'] = merged['Komisi_Bersih'] - merged['Spend']
            merged['ROAS'] = merged.apply(lambda r: r['Komisi_Bersih'] / r['Spend'] if r['Spend'] > 0 else 0.0, axis=1)
            
            total_spend = merged['Spend'].sum()
            komisi_iklan_nett = merged[merged['Tipe'] == "IKLAN (AKTIF)"]["Komisi_Bersih"].sum()
            komisi_organik_nett = merged[merged['Tipe'] == "ORGANIK"]["Komisi_Bersih"].sum()
            total_komisi_nett = df_sales[kolom_komisi_bersih].sum()
            total_profit = total_komisi_nett - total_spend

            try:
                worksheet_summary.append_row([str(tanggal_laporan), nama_laporan, float(total_spend), float(komisi_iklan_nett), float(komisi_organik_nett), float(total_komisi_nett), float(total_profit)], value_input_option='RAW')
                
                rows_tag_to_save = []
                for _, row in merged.iterrows():
                    rows_tag_to_save.append([nama_laporan, str(row['Tipe']), str(row['Clean_Tag']), float(row['Spend']), int(row['Klik_Meta']), int(row['Klik_Shopee']), int(row['Pesanan']), float(row['Kebocoran']), float(row['Komisi_Kotor']), float(row['Komisi_Bersih']), float(row['Profit_Rugi']), float(row['ROAS'])])
                if rows_tag_to_save: worksheet_tag.append_rows(rows_tag_to_save, value_input_option='RAW')
                
                rows_to_save = []
                for _, row in df_sales.iterrows():
                    nama_prod_val = str(row[kolom_nama_produk]).strip() if kolom_nama_produk in df_sales.columns else "Produk Tidak Diketahui"
                    kat_prod_val = str(row[kolom_kategori_produk]).strip() if kolom_kategori_produk in df_sales.columns else "Umum"
                    rows_to_save.append([nama_laporan, str(row['Clean_Tag']), nama_prod_val, kat_prod_val, int(row[kolom_jumlah_item]), float(row[kolom_komisi_bersih])])
                if rows_to_save: worksheet_raw_sales.append_rows(rows_to_save, value_input_option='RAW')
                
                if 'riwayat_summary' in st.session_state: del st.session_state['riwayat_summary']
                st.success(f"✅ Data '{nama_laporan}' Berhasil Tersimpan Otomatis!")
                st.rerun()
            except Exception as sheet_err:
                st.error(f"Gagal menulis ke Cloud: {str(sheet_err)}")

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

df_filtered = st.session_state.get('riwayat_summary', pd.DataFrame())
if not df_filtered.empty:
    df_filtered = df_filtered[(df_filtered['Tanggal'] >= filter_start) & (df_filtered['Tanggal'] <= filter_end)]


# ==========================================
# 5. PERBAIKAN KOTAK METRIK SUMMARY (KPI UTAMA)
# Posisinya tepat berada di atas tulisan "Riwayat Laporan Harian"
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)

# Membuat susunan 5 Kolom Sejajar sesuai permintaan instruksi baru Anda
col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)

val_spend = pd.to_numeric(df_filtered['Spend'], errors='coerce').sum() if not df_filtered.empty else 0
val_komisi_iklan = pd.to_numeric(df_filtered['Komisi Iklan'], errors='coerce').sum() if not df_filtered.empty else 0
val_komisi_organik = pd.to_numeric(df_filtered['Komisi Organik'], errors='coerce').sum() if not df_filtered.empty else 0

# Matematika keuntungan iklan & total keuntungan gabungan
val_keuntungan_iklan = val_komisi_iklan - val_spend
val_total_keuntungan = pd.to_numeric(df_filtered['Profit'], errors='coerce').sum() if not df_filtered.empty else 0

with col_m1: 
    st.metric(label="💸 Total Pengeluaran Iklan", value=f"Rp {val_spend:,.0f}")

with col_m2: 
    st.metric(label="🎯 Total Komisi Iklan (Meta)", value=f"Rp {val_komisi_iklan:,.0f}")

with col_m3: 
    st.metric(label="📱 Total Komisi Organik (Shopee Video)", value=f"Rp {val_komisi_organik:,.0f}")

with col_m4: 
    # PERBAIKAN: Menentukan warna dinamis menggunakan HTML Markdown (Hijau = Untung, Merah = Rugi)
    warna_teks_iklan = "green" if val_keuntungan_iklan >= 0 else "red"
    st.markdown("**Keuntungan (Profit/Rugi) Iklan**")
    st.markdown(
        f"<h3 style='color: {warna_teks_iklan}; margin-top: 4px; margin-bottom: 0px; font-weight: bold;'>Rp {val_keuntungan_iklan:,.0f}</h3>", 
        unsafe_allow_html=True
    )

with col_m5: 
    st.metric(label="📈 Total Keuntungan (Iklan + Organik)", value=f"Rp {val_total_keuntungan:,.0f}")


# ==========================================
# 6. TABEL UTAMA & ACTION HAPUS DATA
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("📋 Riwayat Laporan Harian")
if df_filtered.empty:
    st.info("Belum ada data terekam pada periode ini.")
else:
    df_styled_summary = df_filtered.style.format({'Spend': 'Rp{:,.0f}', 'Komisi Iklan': 'Rp{:,.0f}', 'Komisi Organik': 'Rp{:,.0f}', 'Total Komisi (Nett)': 'Rp{:,.0f}', 'Profit': 'Rp{:,.0f}'}).apply(gaya_tabel_summary, axis=1)
    event_pilih = st.dataframe(df_styled_summary, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

    if event_pilih and len(event_pilih["selection"]["rows"]) > 0:
        indeks_terpilih = event_pilih["selection"]["rows"][0]
        laporan_terpilih = df_filtered.iloc[indeks_terpilih]
        nama_laporan_klik = laporan_terpilih["Nama Laporan"]
        
        if st.button(f"🗑️ Hapus Laporan dari Cloud: {nama_laporan_klik}", type="secondary"):
            try:
                def hapus_laporan_aman(worksheet, nama_lap, headers):
                    records = worksheet.get_all_records()
                    if records:
                        df_temp = pd.DataFrame(records)
                        if "Nama Laporan" in df_temp.columns:
                            df_sisa = df_temp[df_temp["Nama Laporan"] != nama_lap]
                            worksheet.clear()
                            worksheet.append_row(headers)
                            if not df_sisa.empty:
                                for col in df_sisa.columns:
                                    if pd.api.types.is_datetime64_any_dtype(df_sisa[col]) or df_sisa[col].dtype == 'object':
                                        df_sisa[col] = df_sisa[col].astype(str)
                                worksheet.append_rows(df_sisa.values.tolist(), value_input_option='RAW')

                with st.spinner("Menghapus data di Cloud..."):
                    hapus_laporan_aman(worksheet_summary, nama_laporan_klik, ["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"])
                    hapus_laporan_aman(worksheet_tag, nama_laporan_klik, ["Nama Laporan", "Tipe", "Clean_Tag", "Spend", "Klik_Meta", "Klik_Shopee", "Pesanan", "Kebocoran", "Komisi_Kotor", "Komisi_Bersih", "Profit_Rugi", "ROAS"])
                    hapus_laporan_aman(worksheet_raw_sales, nama_laporan_klik, ["Nama Laporan", "Clean_Tag", "Nama Produk", "Kategori", "Item Terjual", "Komisi"])
                    
                if 'riwayat_summary' in st.session_state: del st.session_state['riwayat_summary']
                st.toast("Sukses menghapus data lama!")
                st.rerun()
            except Exception as del_e:
                st.error(f"Gagal menghapus: {str(del_e)}")


        # ==========================================
        # 7. PERBAIKAN HASIL BEDAH DATA DETIL (ROAS & KEBOCORAN)
        # ==========================================
        st.markdown("---")
        st.subheader(f"🔍 Hasil Bedah Data Rinci: {nama_laporan_klik}")
        
        df_detail_tampil = st.session_state.get('cache_tag', pd.DataFrame())
        if not df_detail_tampil.empty and 'Nama Laporan' in df_detail_tampil.columns:
            df_detail_tampil = df_detail_tampil[df_detail_tampil['Nama Laporan'] == nama_laporan_klik].copy()
        else:
            df_detail_tampil = pd.DataFrame()

        if not df_detail_tampil.empty:
            df_iklan_aktif = df_detail_tampil[df_detail_tampil['Tipe'] == "IKLAN (AKTIF)"]
            total_spend_iklan = df_iklan_aktif['Spend'].sum()
            total_klik_meta = df_iklan_aktif['Klik_Meta'].sum()
            total_klik_shopee = df_iklan_aktif['Klik_Shopee'].sum()
            
            # PERBAIKAN UTAMA: Matematika ROAS & Kebocoran Makro agar nilainya presisi & rasional
            roas_iklan_gabungan = (df_iklan_aktif['Komisi_Bersih'].sum() / total_spend_iklan) if total_spend_iklan > 0 else 0.0
            kebocoran_gabungan = max(0.0, ((total_klik_meta - total_klik_shopee) / total_klik_meta) * 100) if total_klik_meta > 0 else 0.0
            
            # Menampilkan ringkasan metrik iklan rinci dengan 5 Kolom agar lengkap dengan angka Kebocoran
            col_ad1, col_ad2, col_ad3, col_ad4, col_ad5 = st.columns(5)
            with col_ad1: st.metric(label="💳 Total Spend Iklan", value=f"Rp {total_spend_iklan:,.0f}")
            with col_ad2: st.metric(label="🖱️ Total Klik Meta", value=f"{total_klik_meta:,.0f} Klik")
            with col_ad3: st.metric(label="🛍️ Total Klik Shopee (Iklan)", value=f"{total_klik_shopee:,.0f} Klik")
            with col_ad4: st.metric(label="📊 ROAS (Murni Iklan)", value=f"{roas_iklan_gabungan:,.2f}x")
            with col_ad5: st.metric(label="📉 Kebocoran Klik Iklan", value=f"{kebocoran_gabungan:,.2f}%")
            
            st.write("💡 *Klik salah satu baris di bawah ini untuk melihat detail produk:*")

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
                
                df_all_sales = st.session_state.get('cache_sales', pd.DataFrame())
                if not df_all_sales.empty:
                    df_product_selected = df_all_sales[(df_all_sales['Nama Laporan'] == nama_laporan_klik) & (df_all_sales['Clean_Tag'] == tag_terpilih)].copy()
                    
                    if not df_product_selected.empty:
                        kolom_nama_sh = cari_kolom(df_product_selected.columns, ['nama produk', 'product'], 'Nama Produk')
                        kolom_kat_sh = cari_kolom(df_product_selected.columns, ['kategori'], 'Kategori')
                        kolom_item_sh = cari_kolom(df_product_selected.columns, ['item terjual', 'jumlah'], 'Item Terjual')
                        kolom_komisi_sh = cari_kolom(df_product_selected.columns, ['komisi'], 'Komisi')

                        df_produk_tampil = df_product_selected.groupby([kolom_nama_sh, kolom_kat_sh]).agg(
                            Item_Terjual=(kolom_item_sh, 'sum'),
                            Komisi_Diterima=(kolom_komisi_sh, 'sum')
                        ).reset_index()
                        
                        df_produk_tampil.columns = ['Nama Produk', 'Kategori', 'Item Terjual', 'Komisi Bersih']
                        st.dataframe(df_produk_tampil.style.format({'Item Terjual': '{:,.0f}', 'Komisi Bersih': 'Rp{:,.0f}'}), use_container_width=True, hide_index=True)
