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
        
        s = str(val).strip().replace('Rp', '').replace('%', '').replace('x', '').replace(' ', '')
        if not s or s.lower() in ['nan', '-', 'null']:
            return 0.0
        
        # JIKA ada titik dan koma sekaligus (misal: 35.802,40 atau 35,802.40)
        if ',' in s and '.' in s:
            if s.find('.') < s.find(','):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        # JIKA hanya ada koma (misal: 35802,40 atau 35,802)
        elif ',' in s:
            parts = s.split(',')
            if len(parts[-1]) == 3 and len(parts) > 1:
                s = s.replace(',', '')
            else:
                s = s.replace(',', '.')
        # JIKA hanya ada titik (misal: 35.802 atau 35802.40)
        elif '.' in s:
            parts = s.split('.')
            if len(parts[-1]) == 3 and len(parts[0]) <= 3:
                s = s.replace('.', '')
                
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
# 2. SINKRONISASI OTOMATIS & INTERNAL CACHE
# ==========================================
if 'riwayat_summary' not in st.session_state:
    with st.spinner("Sinkronisasi aman data cloud harian..."):
        try:
            # Menggunakan UNFORMATTED_VALUE agar data angka dari Google Sheets ditarik sebagai float murni
            records_summary = worksheet_summary.get_all_records(value_render_option='UNFORMATTED_VALUE')
            df_load_summary = pd.DataFrame(records_summary) if records_summary else pd.DataFrame(columns=["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"])
            
            records_tag = worksheet_tag.get_all_records(value_render_option='UNFORMATTED_VALUE')
            df_load_tag = pd.DataFrame(records_tag) if records_tag else pd.DataFrame()
            
            records_sales = worksheet_raw_sales.get_all_records(value_render_option='UNFORMATTED_VALUE')
            df_load_sales = pd.DataFrame(records_sales) if records_sales else pd.DataFrame()

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
    if 'Kebocoran' in row.index:
        val_kebocoran = row['Kebocoran']
        warna = 'background-color: #d4edda; color: #155724;' if val_kebocoran < 0 else 'background-color: #f8d7da; color: #721c24;'
        gaya[row.index.get_loc('Kebocoran')] = warna
    return gaya

def gaya_tabel_summary(row):
    gaya = [''] * len(row)
    
    # 1. Logika Warna untuk kolom Profit (Menggunakan warna hex agar seragam)
    if 'Profit' in row.index:
        gaya[row.index.get_loc('Profit')] = 'color: #107C41; font-weight: bold;' if row['Profit'] >= 0 else 'color: #A80000; font-weight: bold;'
        
    # 2. Logika Warna Baru untuk kolom Komisi Iklan (Hijau jika > Spend, Sebaliknya Merah)
    if 'Komisi Iklan' in row.index and 'Spend' in row.index:
        warna_komisi = 'color: #107C41; font-weight: bold;' if row['Komisi Iklan'] > row['Spend'] else 'color: #A80000; font-weight: bold;'
        gaya[row.index.get_loc('Komisi Iklan')] = warna_komisi
        
    return gaya

with st.expander("📤 AREA UPLOAD FILE BARU", expanded=True):
    tanggal_laporan = st.date_input("Tanggal Laporan:", value=datetime.now().date())
    nama_bulan = BULAN_INDO[tanggal_laporan.month]
    default_nama = f"Laporan {tanggal_laporan.day:02d} {nama_bulan}"
    
    with st.form("form_upload", clear_on_submit=True):
        col_input1, col_input2 = st.columns([2, 4])
        with col_input1: nama_laporan = st.text_input("Nama / Catatan Laporan:", value=default_nama)
        with col_input2: uploaded_files = st.file_uploader("Pilih berkas CSV:", type=["csv"], accept_multiple_files=True)
        tombol_proses = st.form_submit_button("🚀 Proses & Bedah Laporan", use_container_width=True)

if tombol_proses:
    # 1. Ubah validasi minimal upload menjadi 2 file
    if len(uploaded_files) < 2:
        st.error("Silakan unggah minimal 2 file CSV (Data Meta & Data Penjualan) terlebih dahulu.")
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

        # 2. Syarat utama: Hanya Data Meta dan Data Sales yang wajib terdeteksi
        if df_meta is not None and df_sales is not None:
            
            # --- PENANGANAN JIKA FILE KLIK (CLICKS) TIDAK DIUNGGAH ---
            if df_clicks is None:
                df_clicks = pd.DataFrame(columns=['Klik ID', 'Tag_link', 'Clean_Tag'])
            # ---------------------------------------------------------

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
            df_sales['Clean_Tag'] = df_sales[kolom_tag_sales].apply(bersihkan_tag)
            
            # 3. Terapkan pembersih tag ke data Klik HANYA jika file aslinya diunggah
            if not df_clicks.empty and 'Tag_link' in df_clicks.columns:
                df_clicks['Clean_Tag'] = df_clicks['Tag_link'].apply(bersihkan_tag)

            ad_tags = set(df_meta[df_meta['Jumlah yang dibelanjakan (IDR)'] > 0]['Clean_Tag'].unique())

            meta_sum = df_meta.groupby('Clean_Tag').agg(Spend=('Jumlah yang dibelanjakan (IDR)', 'sum'), Klik_Meta=('Klik tautan', 'sum')).reset_index()
            
            # 4. Filter agar pengelompokan Klik tidak error saat datanya kosong
            if not df_clicks.empty:
                click_sum = df_clicks.groupby('Clean_Tag').agg(Klik_Shopee=('Klik ID', 'count')).reset_index()
            else:
                click_sum = pd.DataFrame(columns=['Clean_Tag', 'Klik_Shopee'])

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
        else:
            st.error("Gagal mendeteksi kolom Meta atau Kolom Penjualan. Pastikan file yang diunggah benar!")

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
# 5. KOTAK METRIK SUMMARY INDONESIA PALETTE
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)

# Memaksa sistem menggunakan font-family asli Streamlit agar bentuk huruf sama persis
font_sistem = "font-family: 'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;"
style_label_top = f"{font_sistem} font-size: 14px; color: rgb(49, 51, 63); opacity: 0.8; font-weight: 400; margin-bottom: 2px; line-height: 1.2;"
style_value_top = f"{font_sistem} font-size: 28px; font-weight: 600; margin-top: 0px; margin-bottom: 0px; line-height: 1.2;"

col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)

val_spend = pd.to_numeric(df_filtered['Spend'], errors='coerce').sum() if not df_filtered.empty else 0
val_komisi_iklan = pd.to_numeric(df_filtered['Komisi Iklan'], errors='coerce').sum() if not df_filtered.empty else 0
val_komisi_organik = pd.to_numeric(df_filtered['Komisi Organik'], errors='coerce').sum() if not df_filtered.empty else 0
val_keuntungan_iklan = val_komisi_iklan - val_spend
val_total_keuntungan = pd.to_numeric(df_filtered['Profit'], errors='coerce').sum() if not df_filtered.empty else 0

with col_m1: 
    st.metric(label="💸 Total Pengeluaran Iklan", value=f"Rp {int(round(val_spend)):,}".replace(',', '.'))
with col_m2: 
    st.metric(label="🎯 Total Komisi Iklan (Meta)", value=f"Rp {int(round(val_komisi_iklan)):,}".replace(',', '.'))
with col_m3: 
    st.metric(label="📱 Total Komisi Organik", value=f"Rp {int(round(val_komisi_organik)):,}".replace(',', '.'))
with col_m4: 
    # Ditambahkan emotikon 💰 dan disesuaikan warna serta font-family-nya
    warna_teks_iklan = "#107C41" if val_keuntungan_iklan >= 0 else "#A80000"
    st.markdown(f"<div style='{style_label_top}'>💰 Keuntungan Iklan</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='{style_value_top} color: {warna_teks_iklan};'>Rp {int(round(val_keuntungan_iklan)):,}".replace(',', '.') + "</div>", unsafe_allow_html=True)
with col_m5: 
    st.metric(label="📈 Keuntungan Bersih (Total)", value=f"Rp {int(round(val_total_keuntungan)):,}".replace(',', '.'))


# ==========================================
# 6. TABEL UTAMA & ACTION HAPUS DATA (MULTI-SELECT)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("📋 Riwayat Laporan Harian")
if df_filtered.empty:
    st.info("Belum ada data terekam pada periode ini.")
else:
    # Mengubah format visual US menjadi ID (Koma jadi Titik)
    df_styled_summary = df_filtered.style.format({
        'Spend': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
        'Komisi Iklan': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
        'Komisi Organik': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
        'Total Komisi (Nett)': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
        'Profit': lambda x: f"Rp {int(round(x)):,}".replace(',', '.')
    }).apply(gaya_tabel_summary, axis=1)
    
    # UBAH DISINI: selection_mode="multi-row"
    event_pilih = st.dataframe(df_styled_summary, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="multi-row")

    if event_pilih and len(event_pilih["selection"]["rows"]) > 0:
        indeks_terpilih = event_pilih["selection"]["rows"]
        laporan_terpilih = df_filtered.iloc[indeks_terpilih]
        
        # MENGAMBIL LIST NAMA LAPORAN YANG DICENTANG
        daftar_laporan_klik = laporan_terpilih["Nama Laporan"].tolist()
        
        # Tombol hapus disesuaikan untuk menghapus banyak laporan sekaligus
        if st.button(f"🗑️ Hapus {len(daftar_laporan_klik)} Laporan Terpilih dari Cloud", type="secondary"):
            try:
                def hapus_laporan_aman(worksheet, list_nama_lap, headers):
                    records = worksheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
                    if records:
                        df_temp = pd.DataFrame(records)
                        if "Nama Laporan" in df_temp.columns:
                            # Filter: Buang baris yang nama laporannya ada di dalam daftar yang dicentang
                            df_sisa = df_temp[~df_temp["Nama Laporan"].isin(list_nama_lap)]
                            worksheet.clear()
                            worksheet.append_row(headers)
                            if not df_sisa.empty:
                                for col in df_sisa.columns:
                                    if pd.api.types.is_datetime64_any_dtype(df_sisa[col]) or df_sisa[col].dtype == 'object':
                                        df_sisa[col] = df_sisa[col].astype(str)
                                worksheet.append_rows(df_sisa.values.tolist(), value_input_option='RAW')

                with st.spinner("Menghapus data di Cloud..."):
                    hapus_laporan_aman(worksheet_summary, daftar_laporan_klik, ["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"])
                    hapus_laporan_aman(worksheet_tag, daftar_laporan_klik, ["Nama Laporan", "Tipe", "Clean_Tag", "Spend", "Klik_Meta", "Klik_Shopee", "Pesanan", "Kebocoran", "Komisi_Kotor", "Komisi_Bersih", "Profit_Rugi", "ROAS"])
                    hapus_laporan_aman(worksheet_raw_sales, daftar_laporan_klik, ["Nama Laporan", "Clean_Tag", "Nama Produk", "Kategori", "Item Terjual", "Komisi"])
                    
                if 'riwayat_summary' in st.session_state: del st.session_state['riwayat_summary']
                st.toast("Sukses menghapus data yang dipilih!")
                st.rerun()
            except Exception as del_e:
                st.error(f"Gagal menghapus: {str(del_e)}")


        # ==========================================
        # 7. HASIL BEDAH DATA DETIL (DI-SPLIT ATAS & BAWAH)
        # ==========================================
        st.markdown("---")
        judul_tabel = f"🔍 Hasil Bedah Data Rinci: Gabungan {len(daftar_laporan_klik)} Laporan" if len(daftar_laporan_klik) > 1 else f"🔍 Hasil Bedah Data Rinci: {daftar_laporan_klik[0]}"
        st.subheader(judul_tabel)
        
        df_detail_tampil = st.session_state.get('cache_tag', pd.DataFrame())
        if not df_detail_tampil.empty and 'Nama Laporan' in df_detail_tampil.columns:
            # Filter menggunakan .isin() untuk mengambil banyak laporan
            df_detail_tampil = df_detail_tampil[df_detail_tampil['Nama Laporan'].isin(daftar_laporan_klik)].copy()
        else:
            df_detail_tampil = pd.DataFrame()

        if not df_detail_tampil.empty:
            # Karena laporan digabung, kita harus menjumlahkan Tag yang sama dari tanggal yang berbeda
            df_detail_tampil = df_detail_tampil.groupby(['Clean_Tag', 'Tipe']).agg({
                'Spend': 'sum',
                'Klik_Meta': 'sum',
                'Klik_Shopee': 'sum',
                'Pesanan': 'sum',
                'Komisi_Kotor': 'sum',
                'Komisi_Bersih': 'sum',
                'Profit_Rugi': 'sum'
            }).reset_index()

            # Rekalkulasi Dinamis Pengunci Formula Akurasi Tinggi (Dihitung SETELAH digabung)
            df_detail_tampil['ROAS'] = df_detail_tampil.apply(lambda r: r['Komisi_Bersih'] / r['Spend'] if r['Spend'] > 0 else 0.0, axis=1)
            df_detail_tampil['Kebocoran'] = df_detail_tampil.apply(lambda r: ((r['Klik_Meta'] - r['Klik_Shopee']) / r['Klik_Meta']) * 100 if r['Klik_Meta'] > 0 else 0.0, axis=1)

            df_iklan_aktif = df_detail_tampil[df_detail_tampil['Tipe'] == "IKLAN (AKTIF)"].copy()
            df_organik_calc = df_detail_tampil[df_detail_tampil['Tipe'] != "IKLAN (AKTIF)"].copy()
            
            # --- 1. PERHITUNGAN MACRO KPI (FINANSIAL) ---
            total_spend_iklan = df_iklan_aktif['Spend'].sum()
            total_komisi_iklan = df_iklan_aktif['Komisi_Bersih'].sum()
            total_keuntungan_iklan = total_komisi_iklan - total_spend_iklan
            
            total_komisi_organik = df_organik_calc['Komisi_Bersih'].sum()
            total_keuntungan_bersih = (total_komisi_iklan + total_komisi_organik) - total_spend_iklan
            
            # --- TAMPILAN BARIS PERTAMA: 5 METRIK FINANSIAL (UKURAN & WARNA SERAGAM) ---
            style_label = "font-size: 14px; color: rgb(49, 51, 63); opacity: 0.8; font-weight: 400; margin-bottom: 2px;"
            style_value = "font-size: 28px; font-weight: 600; margin-top: 0px; margin-bottom: 0px;"
            
            col_ad1, col_ad2, col_ad3, col_ad4, col_ad5 = st.columns(5)
            with col_ad1:
                st.markdown(f"<div style='{style_label}'>💳 Total Spend Iklan</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{style_value} color: #31333F;'>Rp {int(round(total_spend_iklan)):,}".replace(',', '.') + "</div>", unsafe_allow_html=True)
            with col_ad2:
                # Logika Warna Komisi Iklan: Hijau jika > Spend Iklan, jika tidak Merah
                warna_komisi_iklan = "#107C41" if total_komisi_iklan > total_spend_iklan else "#A80000"
                st.markdown(f"<div style='{style_label}'>🎯 Total Komisi Iklan</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{style_value} color: {warna_komisi_iklan};'>Rp {int(round(total_komisi_iklan)):,}".replace(',', '.') + "</div>", unsafe_allow_html=True)
            with col_ad3:
                warna_iklan = "#107C41" if total_keuntungan_iklan >= 0 else "#A80000"
                st.markdown(f"<div style='{style_label}'>🔥 Keuntungan Iklan</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{style_value} color: {warna_iklan};'>Rp {int(round(total_keuntungan_iklan)):,}".replace(',', '.') + "</div>", unsafe_allow_html=True)
            with col_ad4:
                # Total Komisi Organik dipaksa selalu berwarna Hijau
                st.markdown(f"<div style='{style_label}'>📱 Total Komisi Organik</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{style_value} color: #107C41;'>Rp {int(round(total_komisi_organik)):,}".replace(',', '.') + "</div>", unsafe_allow_html=True)
            with col_ad5:
                warna_bersih = "#107C41" if total_keuntungan_bersih >= 0 else "#A80000"
                st.markdown(f"<div style='{style_label}'>💎 Keuntungan Bersih</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{style_value} color: {warna_bersih};'>Rp {int(round(total_keuntungan_bersih)):,}".replace(',', '.') + "</div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)

            # --- 2. PERHITUNGAN KPI TEKNIS / OPERASIONAL ---
            total_klik_meta = df_iklan_aktif['Klik_Meta'].sum()
            total_klik_shopee = df_iklan_aktif['Klik_Shopee'].sum()
            roas_iklan_gabungan = (total_komisi_iklan / total_spend_iklan) if total_spend_iklan > 0 else 0.0
            kebocoran_gabungan = ((total_klik_meta - total_klik_shopee) / total_klik_meta) * 100 if total_klik_meta > 0 else 0.0
            
            # Tambahkan variabel total pesanan gabungan terlebih dahulu sebelum st.columns
            total_pesanan_gabungan = df_detail_tampil['Pesanan'].sum()

            # --- TAMPILAN BARIS KEDUA: 5 METRIK TEKNIS (DITAMBAH TOTAL PESANAN) ---
            col_op1, col_op2, col_op3, col_op4, col_op5 = st.columns(5)
            with col_op1: 
                st.markdown(f"<div style='{style_label}'>🖱️ Total Klik Meta</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{style_value} color: #31333F;'>{total_klik_meta:,.0f}".replace(',', '.') + " Klik</div>", unsafe_allow_html=True)
            with col_op2: 
                # Logika Warna Klik Shopee: Hijau jika > Klik Meta, jika tidak Merah
                warna_klik_shopee = "#107C41" if total_klik_shopee > total_klik_meta else "#A80000"
                st.markdown(f"<div style='{style_label}'>🛍️ Total Klik Shopee (Iklan)</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{style_value} color: {warna_klik_shopee};'>{total_klik_shopee:,.0f}".replace(',', '.') + " Klik</div>", unsafe_allow_html=True)
            with col_op3: 
                # Metrik Baru: Total Pesanan diletakkan di sebelah kanan Klik Shopee
                st.markdown(f"<div style='{style_label}'>📦 Total Pesanan (All)</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{style_value} color: #107C41;'>{total_pesanan_gabungan:,.0f}".replace(',', '.') + " Pesanan</div>", unsafe_allow_html=True)
            with col_op4: 
                st.markdown(f"<div style='{style_label}'>📊 ROAS (Murni Iklan)</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{style_value} color: #31333F;'>{roas_iklan_gabungan:,.2f}x</div>", unsafe_allow_html=True)
            with col_op5: 
                # Logika Kebocoran: Jika minus -> Hijau. Jika plus -> Merah.
                warna_bocor = "#107C41" if kebocoran_gabungan <= 0 else "#A80000"
                st.markdown(f"<div style='{style_label}'>📉 Total Kebocoran</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{style_value} color: {warna_bocor};'>{kebocoran_gabungan:,.2f}%</div>", unsafe_allow_html=True)
            
            st.markdown("---")
            st.write("💡 *Klik salah satu baris pada tabel di bawah ini untuk melihat detail produk:*")

            tag_terpilih = None

            # 🅰️ TABEL ATAS: KELOMPOK IKLAN AKTIF
            st.markdown("#### 🎯 Kelompok Iklan Aktif")
            if not df_iklan_aktif.empty:
                df_styled_iklan = df_iklan_aktif[['Tipe', 'Clean_Tag', 'Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Kebocoran', 'Komisi_Kotor', 'Profit_Rugi', 'ROAS']].style.format({
                    'Spend': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
                    'Komisi_Kotor': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
                    'Profit_Rugi': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
                    'ROAS': '{:,.2f}x', 
                    'Klik_Meta': lambda x: f"{int(x):,}".replace(',', '.'), 
                    'Klik_Shopee': lambda x: f"{int(x):,}".replace(',', '.'), 
                    'Pesanan': lambda x: f"{int(x):,}".replace(',', '.'), 
                    'Kebocoran': '{:,.2f}%'
                }).apply(gaya_tabel_detail, axis=1)
                
                event_klik_iklan = st.dataframe(df_styled_iklan, use_container_width=True, hide_index=True, on_select="rerun", key="grid_iklan_aktif", selection_mode="single-row")
                if event_klik_iklan and len(event_klik_iklan["selection"]["rows"]) > 0:
                    indeks_iklan = event_klik_iklan["selection"]["rows"][0]
                    tag_terpilih = df_iklan_aktif.iloc[indeks_iklan]["Clean_Tag"]
            else:
                st.info("Tidak ada tracker dengan status Iklan Aktif.")

            # 🅱️ TABEL BAWAH: KELOMPOK ORGANIK / TIDAK AKTIF
            st.markdown("#### 📱 Kelompok Organik / Tidak Aktif")
            df_organik = df_detail_tampil[df_detail_tampil['Tipe'] != "IKLAN (AKTIF)"].copy()
            df_organik = df_organik.sort_values(by=['Pesanan', 'Komisi_Kotor'], ascending=[False, False])

            if not df_organik.empty:
                df_styled_organik = df_organik[['Tipe', 'Clean_Tag', 'Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Kebocoran', 'Komisi_Kotor', 'Profit_Rugi', 'ROAS']].style.format({
                    'Spend': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
                    'Komisi_Kotor': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
                    'Profit_Rugi': lambda x: f"Rp {int(round(x)):,}".replace(',', '.'),
                    'ROAS': '{:,.2f}x', 
                    'Klik_Meta': lambda x: f"{int(x):,}".replace(',', '.'), 
                    'Klik_Shopee': lambda x: f"{int(x):,}".replace(',', '.'), 
                    'Pesanan': lambda x: f"{int(x):,}".replace(',', '.'), 
                    'Kebocoran': '{:,.2f}%'
                }).apply(gaya_tabel_detail, axis=1)
                
                event_klik_organik = st.dataframe(df_styled_organik, use_container_width=True, hide_index=True, on_select="rerun", key="grid_organik_aktif", selection_mode="single-row")
                if event_klik_organik and len(event_klik_organik["selection"]["rows"]) > 0:
                    indeks_organik = event_klik_organik["selection"]["rows"][0]
                    tag_terpilih = df_organik.iloc[indeks_organik]["Clean_Tag"]
            else:
                st.info("Tidak ada tracker dengan status Organik.")

            # --- SUB-DETAIL: RAW DATA DATA PRODUK BERDASARKAN SELECTION ---
            if tag_terpilih:
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader(f"📦 Rincian Produk Terjual pada Tag: {tag_terpilih}")
                
                df_raw_sales = st.session_state.get('cache_sales', pd.DataFrame())
                if not df_raw_sales.empty and 'Nama Laporan' in df_raw_sales.columns and 'Clean_Tag' in df_raw_sales.columns:
                    df_sales_filtered = df_raw_sales[(df_raw_sales['Nama Laporan'].isin(daftar_laporan_klik)) & (df_raw_sales['Clean_Tag'] == tag_terpilih)].copy()
                    
                    if not df_sales_filtered.empty:
                        df_sales_sum = df_sales_filtered.groupby(['Nama Produk', 'Kategori']).agg({
                            'Item Terjual': 'sum',
                            'Komisi': 'sum'
                        }).reset_index().sort_values(by='Item Terjual', ascending=False)
                        
                        df_styled_sales = df_sales_sum.style.format({
                            'Item Terjual': lambda x: f"{int(x):,}".replace(',', '.'),
                            'Komisi': lambda x: f"Rp {int(round(x)):,}".replace(',', '.')
                        })
                        st.dataframe(df_styled_sales, use_container_width=True, hide_index=True)
                    else:
                        st.info("Tidak ada data produk spesifik yang terekam untuk tag ini.")
                else:
                    st.info("Database produk kosong.")


            # ==========================================
            # 8. RINCIAN ITEM PRODUK YANG TERJUAL
            # ==========================================
            if tag_terpilih is not None:
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader(f"📦 Rincian Produk Terjual untuk Tag: #{tag_terpilih}")
                
                df_all_sales = st.session_state.get('cache_sales', pd.DataFrame())
                if not df_all_sales.empty:
                    # UBAH DISINI: Filter juga menggunakan .isin() untuk membaca semua penjualan dari tanggal-tanggal yang dipilih
                    df_product_selected = df_all_sales[(df_all_sales['Nama Laporan'].isin(daftar_laporan_klik)) & (df_all_sales['Clean_Tag'] == tag_terpilih)].copy()
                    
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
                        st.dataframe(df_produk_tampil.style.format({
                            'Item Terjual': lambda x: f"{int(x):,}".replace(',', '.'), 
                            'Komisi Bersih': lambda x: f"Rp {int(round(x)):,}".replace(',', '.')
                        }), use_container_width=True, hide_index=True)
