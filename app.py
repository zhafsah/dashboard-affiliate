import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Pengaturan dasar halaman dashboard
st.set_page_config(page_title="Affiliate Advanced Analytics", layout="wide")

# Custom CSS untuk menyamakan tampilan box dan tabel dengan gambar referensi
st.markdown("""
    import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Pengaturan dasar halaman dashboard
st.set_page_config(page_title="Affiliate Advanced Analytics", layout="wide")

st.title("📊 Dashboard Evaluasi & Performa Affiliate")
st.write("Kelola pengeluaran iklan Meta dan optimalkan komisi bersih Shopee Anda dalam satu layar.")

# ==========================================
# INISIALISASI MEMORI PENYIMPANAN DATA (SESSION STATE)
# ==========================================
if 'riwayat_summary' not in st.session_state:
    st.session_state['riwayat_summary'] = pd.DataFrame(columns=["Tanggal", "Nama Laporan", "Spend", "Komisi", "Profit", "Status"])
if 'detail_laporan_data' not in st.session_state:
    st.session_state['detail_laporan_data'] = {}

# Helper untuk membersihkan tanda pagar (#) dan strip (----) pada nama iklan
def bersihkan_tag(x):
    if pd.isna(x) or str(x).strip() == "" or str(x).lower() == "nan":
        return "Organik"
    s = str(x).strip()
    if s.startswith('#'): s = s[1:]
    if s.endswith('----'): s = s[:-4]
    return s

# ==========================================
# SECTION 1: TOMBOL UPLOAD DI BAGIAN ATAS
# ==========================================
with st.expander("📤 AREA UPLOAD FILE BARU (Drop 3 File CSV Mentah Anda Sekaligus)", expanded=True):
    col_input1, col_input2 = st.columns([1, 2])
    with col_input1:
        nama_laporan = st.text_input("Nama / Catatan Laporan:", placeholder="Contoh: Laporan 04 Jun")
    with col_input2:
        uploaded_files = st.file_uploader("", type=["csv"], accept_multiple_files=True)

# Proses ekstraksi isi file CSV secara otomatis
if len(uploaded_files) >= 3 and nama_laporan:
    df_meta, df_clicks, df_sales = None, None, None
    for file in uploaded_files:
        try:
            df_temp = pd.read_csv(file)
            if 'Jumlah yang dibelanjakan (IDR)' in df_temp.columns or 'Nama iklan' in df_temp.columns:
                df_meta = df_temp
            elif 'Klik ID' in df_temp.columns and 'Tag_link' in df_temp.columns:
                df_clicks = df_temp
            elif 'Total Komisi per Pesanan(Rp)' in df_temp.columns or 'Komisi Bersih Affiliate (Rp)' in df_temp.columns:
                df_sales = df_temp
        except Exception as e:
            st.error(f"Gagal membaca salah satu file: {str(e)}")

    if df_meta is not None and df_clicks is not None and df_sales is not None:
        # Pembersihan Tag menggunakan algoritma Python
        df_meta['Clean_Tag'] = df_meta['Nama iklan'].apply(bersihkan_tag)
        df_sales['Clean_Tag'] = df_sales['Tag_link1'].apply(bersihkan_tag)
        df_clicks['Clean_Tag'] = df_clicks['Tag_link'].apply(bersihkan_tag)

        # 1. Olah Data Meta Ads
        meta_sum = df_meta.groupby('Clean_Tag').agg(
            Spend=('Jumlah yang dibelanjakan (IDR)', 'sum'),
            Klik_Meta=('Klik tautan', 'sum')
        ).reset_index()

        # 2. Olah Data Klik Shopee
        click_sum = df_clicks.groupby('Clean_Tag').agg(Klik_Shopee=('Klik ID', 'count')).reset_index()
        
        # 3. Olah Data Penjualan Shopee
        sales_sum = df_sales.groupby('Clean_Tag').agg(
            Pesanan=('ID Pemesanan', 'nunique'),
            Komisi_Kotor=('Total Komisi per Pesanan(Rp)', 'sum'),
            Komisi_Bersih=('Komisi Bersih Affiliate (Rp)', 'sum')
        ).reset_index()

        # Gabungkan ketiga hasil olahan dokumen menjadi satu tabel utuh
        merged = pd.merge(meta_sum, click_sum, on='Clean_Tag', how='outer')
        merged = pd.merge(merged, sales_sum, on='Clean_Tag', how='outer').fillna(0)

        # Penentuan Tipe Konten: IKLAN AKTIF vs ORGANIK
        ad_tags = set(df_meta['Clean_Tag'].unique())
        merged['Tipe'] = merged.apply(lambda r: "IKLAN (AKTIF)" if r['Clean_Tag'] in ad_tags and r['Spend'] > 0 else "ORGANIK", axis=1)
        
        # Tambahkan kalkulasi Profit dan ROAS per baris tag konten
        merged['Profit_Rugi'] = merged['Komisi_Bersih'] - merged['Spend']
        merged['ROAS'] = merged.apply(lambda r: r['Komisi_Bersih'] / r['Spend'] if r['Spend'] > 0 else 0.0, axis=1)
        
        # Susun kolom laporan akhir
        merged = merged[['Tipe', 'Clean_Tag', 'Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Komisi_Kotor', 'Komisi_Bersih', 'Profit_Rugi', 'ROAS']]
        
        # Hitung angka akumulasi untuk tabel utama depan
        total_spend = merged['Spend'].sum()
        total_komisi = merged['Komisi_Bersih'].sum()
        total_profit = total_komisi - total_spend

        # Simpan ringkasan harian ke daftar tabel depan
        new_summary = pd.DataFrame([{
            "Tanggal": datetime.now().date(), "Nama Laporan": nama_laporan,
            "Spend": total_spend, "Komisi": total_komisi, "Profit": total_profit, "Status": "Sukses"
        }])
        
        if nama_laporan not in st.session_state['riwayat_summary']['Nama Laporan'].values:
            st.session_state['riwayat_summary'] = pd.concat([st.session_state['riwayat_summary'], new_summary], ignore_index=True)
            st.session_state['detail_laporan_data'][nama_laporan] = merged
            st.success(f"✅ Laporan '{nama_laporan}' berhasil dibedah! Data langsung tersinkronisasi di bawah.")
        else:
            st.warning("Nama laporan sudah ada. Silakan gunakan nama laporan yang berbeda.")

st.markdown("---")

# ==========================================
# SECTION 2: FILTER TANGGAL DAN SHORTCUT BUTTON
# ==========================================
st.subheader("🔍 Filter Rentang Waktu Data")
col_btn1, col_btn2, col_btn3, col_date = st.columns([1, 1, 1, 3])

today = datetime.now().date()
start_date, end_date = today, today

with col_btn1:
    if st.button("📅 Kemarin", use_container_width=True):
        start_date = today - timedelta(days=1)
        end_date = today - timedelta(days=1)
with col_btn2:
    if st.button("📅 Bulan Ini", use_container_width=True):
        start_date = today.replace(day=1)
        end_date = today
with col_btn3:
    if st.button("📅 Bulan Lalu", use_container_width=True):
        last_month = today.replace(day=1) - timedelta(days=1)
        start_date = last_month.replace(day=1)
        end_date = last_month

with col_date:
    rentang_tanggal = st.date_input("Atau Pilih Kustom Kalender:", value=(start_date, end_date))

if isinstance(rentang_tanggal, tuple) and len(rentang_tanggal) == 2:
    filter_start, filter_end = rentang_tanggal
else:
    filter_start, filter_end = start_date, end_date

if not st.session_state['riwayat_summary'].empty:
    df_filtered = st.session_state['riwayat_summary'][
        (st.session_state['riwayat_summary']['Tanggal'] >= filter_start) & 
        (st.session_state['riwayat_summary']['Tanggal'] <= filter_end)
    ]
else:
    df_filtered = st.session_state['riwayat_summary']

# ==========================================
# SECTION 3: RINGKASAN KOTAK METRIK (MENGGUNAKAN FITUR NATIVE)
# ==========================================
st.markdown("<br>", unsafe_allow_index=True)
col_m1, col_m2, col_m3 = st.columns(3)

val_spend = df_filtered['Spend'].sum() if not df_filtered.empty else 0
val_komisi = df_filtered['Komisi'].sum() if not df_filtered.empty else 0
val_profit = df_filtered['Profit'].sum() if not df_filtered.empty else 0

with col_m1:
    st.metric(label="💸 Total Pengeluaran Iklan", value=f"Rp {val_spend:,.0f}")
with col_m2:
    st.metric(label="💰 Total Komisi Masuk", value=f"Rp {val_komisi:,.0f}")
with col_m3:
    st.metric(label="📈 Keuntungan Bersih (Profit)", value=f"Rp {val_profit:,.0f}")

st.markdown("<br>", unsafe_allow_index=True)

# ==========================================
# SECTION 4: TABEL RIWAYAT UTAMA & EVENT KLIK DETAIL ROWS
# ==========================================
st.subheader("📋 Riwayat Laporan Harian")
st.write("👉 **Silakan KLIK KOTAK CENTANG/BARIS pada tabel di bawah ini** untuk membedah data operasional secara detail:")

if df_filtered.empty:
    st.info("Belum ada laporan yang diupload dalam rentang tanggal ini. Silakan gunakan form upload di atas.")
else:
    event_pilih = st.dataframe(
        df_filtered, 
        use_container_width=True, 
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    # ==========================================
    # SECTION 5: TAMPILAN DETAIL OPERASIONAL (PASCA KLIK BARIS)
    # ==========================================
    if event_pilih and len(event_pilih["selection"]["rows"]) > 0:
        indeks_terpilih = event_pilih["selection"]["rows"][0]
        nama_laporan_klik = df_filtered.iloc[indeks_terpilih]["Nama Laporan"]
        
        st.markdown("---")
        st.subheader(f"🔍 Hasil Bedah Data Rinci: {nama_laporan_klik}")
        st.write("Berikut adalah rincian performa konversi, rasio kebocoran klik, komisi kotor/bersih, serta ROAS asli per konten:")
        
        if nama_laporan_klik in st.session_state['detail_laporan_data']:
            df_detail_tampil = st.session_state['detail_laporan_data'][nama_laporan_klik]
            
            st.dataframe(
                df_detail_tampil.style.format({
                    'Spend': 'Rp{:,.0f}',
                    'Komisi_Kotor': 'Rp{:,.0f}',
                    'Komisi_Bersih': 'Rp{:,.0f}',
                    'Profit_Rugi': 'Rp{:,.0f}',
                    'ROAS': '{:,.2f}x',
                    'Klik_Meta': '{:,.0f}',
                    'Klik_Shopee': '{:,.0f}',
                    'Pesanan': '{:,.0f}'
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.error("Data detail untuk laporan ini tidak ditemukan di memori browser.")
""", unsafe_allow_index=True)

st.title("📊 Dashboard Evaluasi & Performa Affiliate")
st.write("Kelola pengeluaran iklan Meta dan optimalkan komisi bersih Shopee Anda dalam satu layar.")

# ==========================================
# INISIALISASI MEMORI PENYIMPANAN DATA (SESSION STATE)
# ==========================================
if 'riwayat_summary' not in st.session_state:
    st.session_state['riwayat_summary'] = pd.DataFrame(columns=["Tanggal", "Nama Laporan", "Spend", "Komisi", "Profit", "Status"])
if 'detail_laporan_data' not in st.session_state:
    st.session_state['detail_laporan_data'] = {}

# Helper untuk membersihkan tanda pagar (#) dan strip (----) pada nama iklan
def bersihkan_tag(x):
    if pd.isna(x) or str(x).strip() == "" or str(x).lower() == "nan":
        return "Organik"
    s = str(x).strip()
    if s.startswith('#'): s = s[1:]
    if s.endswith('----'): s = s[:-4]
    return s

# ==========================================
# SECTION 1: TOMBOL UPLOAD DI BAGIAN ATAS
# ==========================================
with st.expander("📤 AREA UPLOAD FILE BARU (Drop 3 File CSV Mentah Anda Sekaligus)", expanded=True):
    col_input1, col_input2 = st.columns([1, 2])
    with col_input1:
        nama_laporan = st.text_input("Nama / Catatan Laporan:", placeholder="Contoh: Laporan 04 Jun")
    with col_input2:
        uploaded_files = st.file_uploader("", type=["csv"], accept_multiple_files=True)

# Proses ekstraksi isi file CSV secara otomatis tanpa Google Sheets
if len(uploaded_files) >= 3 and nama_laporan:
    df_meta, df_clicks, df_sales = None, None, None
    for file in uploaded_files:
        # Deteksi otomatis isi file berdasarkan kolom unik di dalamnya
        try:
            df_temp = pd.read_csv(file)
            if 'Jumlah yang dibelanjakan (IDR)' in df_temp.columns or 'Nama iklan' in df_temp.columns:
                df_meta = df_temp
            elif 'Klik ID' in df_temp.columns and 'Tag_link' in df_temp.columns:
                df_clicks = df_temp
            elif 'Total Komisi per Pesanan(Rp)' in df_temp.columns or 'Komisi Bersih Affiliate (Rp)' in df_temp.columns:
                df_sales = df_temp
        except Exception as e:
            st.error(f"Gagal membaca salah satu file: {str(e)}")

    if df_meta is not None and df_clicks is not None and df_sales is not None:
        # Pembersihan Tag di latar belakang menggunakan algoritma Python
        df_meta['Clean_Tag'] = df_meta['Nama iklan'].apply(bersihkan_tag)
        df_sales['Clean_Tag'] = df_sales['Tag_link1'].apply(bersihkan_tag)
        df_clicks['Clean_Tag'] = df_clicks['Tag_link'].apply(bersihkan_tag)

        # 1. Olah Data Meta Ads
        meta_sum = df_meta.groupby('Clean_Tag').agg(
            Spend=('Jumlah yang dibelanjakan (IDR)', 'sum'),
            Klik_Meta=('Klik tautan', 'sum')
        ).reset_index()

        # 2. Olah Data Klik Shopee
        click_sum = df_clicks.groupby('Clean_Tag').agg(Klik_Shopee=('Klik ID', 'count')).reset_index()
        
        # 3. Olah Data Penjualan Shopee
        sales_sum = df_sales.groupby('Clean_Tag').agg(
            Pesanan=('ID Pemesanan', 'nunique'),
            Komisi_Kotor=('Total Komisi per Pesanan(Rp)', 'sum'),
            Komisi_Bersih=('Komisi Bersih Affiliate (Rp)', 'sum')
        ).reset_index()

        # Gabungkan ketiga hasil olahan dokumen menjadi satu tabel utuh
        merged = pd.merge(meta_sum, click_sum, on='Clean_Tag', how='outer')
        merged = pd.merge(merged, sales_sum, on='Clean_Tag', how='outer').fillna(0)

        # Penentuan Tipe Konten: IKLAN AKTIF vs ORGANIK
        ad_tags = set(df_meta['Clean_Tag'].unique())
        merged['Tipe'] = merged.apply(lambda r: "IKLAN (AKTIF)" if r['Clean_Tag'] in ad_tags and r['Spend'] > 0 else "ORGANIK", axis=1)
        
        # Tambahkan kalkulasi Profit dan ROAS per baris tag konten
        merged['Profit_Rugi'] = merged['Komisi_Bersih'] - merged['Spend']
        merged['ROAS'] = merged.apply(lambda r: r['Komisi_Bersih'] / r['Spend'] if r['Spend'] > 0 else 0.0, axis=1)
        
        # Susun kolom laporan akhir sesuai gambar referensi Anda
        merged = merged[['Tipe', 'Clean_Tag', 'Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Komisi_Kotor', 'Komisi_Bersih', 'Profit_Rugi', 'ROAS']]
        
        # Hitung angka akumulasi untuk tabel utama depan
        total_spend = merged['Spend'].sum()
        total_komisi = merged['Komisi_Bersih'].sum()
        total_profit = total_komisi - total_spend

        # Simpan ringkasan harian ke daftar tabel depan
        new_summary = pd.DataFrame([{
            "Tanggal": datetime.now().date(), "Nama Laporan": nama_laporan,
            "Spend": total_spend, "Komisi": total_komisi, "Profit": total_profit, "Status": "Sukses"
        }])
        
        # Cegah duplikasi nama laporan yang sama
        if nama_laporan not in st.session_state['riwayat_summary']['Nama Laporan'].values:
            st.session_state['riwayat_summary'] = pd.concat([st.session_state['riwayat_summary'], new_summary], ignore_index=True)
            # Simpan isi rincian detailnya ke dalam ID nama laporan tersebut
            st.session_state['detail_laporan_data'][nama_laporan] = merged
            st.success(f"✅ Laporan '{nama_laporan}' berhasil dibedah! Data langsung tersinkronisasi di bawah.")
        else:
            st.warning("Nama laporan sudah ada. Silakan gunakan nama laporan yang berbeda.")

st.markdown("---")

# ==========================================
# SECTION 2: FILTER TANGGAL DAN SHORTCUT BUTTON
# ==========================================
st.subheader("🔍 Filter Rentang Waktu Data")
col_btn1, col_btn2, col_btn3, col_date = st.columns([1, 1, 1, 3])

today = datetime.now().date()
start_date, end_date = today, today

with col_btn1:
    if st.button("📅 Kemarin", use_container_width=True):
        start_date = today - timedelta(days=1)
        end_date = today - timedelta(days=1)
with col_btn2:
    if st.button("📅 Bulan Ini", use_container_width=True):
        start_date = today.replace(day=1)
        end_date = today
with col_btn3:
    if st.button("📅 Bulan Lalu", use_container_width=True):
        last_month = today.replace(day=1) - timedelta(days=1)
        start_date = last_month.replace(day=1)
        end_date = last_month

with col_date:
    rentang_tanggal = st.date_input("Atau Pilih Kustom Kalender:", value=(start_date, end_date))

# Proses filter tanggal
if isinstance(rentang_tanggal, tuple) and len(rentang_tanggal) == 2:
    filter_start, filter_end = rentang_tanggal
else:
    filter_start, filter_end = start_date, end_date

# Filter data summary utama di dashboard depan
if not st.session_state['riwayat_summary'].empty:
    df_filtered = st.session_state['riwayat_summary'][
        (st.session_state['riwayat_summary']['Tanggal'] >= filter_start) & 
        (st.session_state['riwayat_summary']['Tanggal'] <= filter_end)
    ]
else:
    df_filtered = st.session_state['riwayat_summary']

# ==========================================
# SECTION 3: RINGKASAN KOTAK METRIK (CARD KPI)
# ==========================================
st.markdown("<br>", unsafe_allow_index=True)
col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    st.markdown(f"<div class='metric-box'><h5>💸 Total Pengeluaran Iklan</h5><h2>Rp {df_filtered['Spend'].sum() if not df_filtered.empty else 0:,.0f}</h2></div>", unsafe_allow_index=True)
with col_m2:
    st.markdown(f"<div class='metric-box'><h5>💰 Total Komisi Masuk</h5><h2>Rp {df_filtered['Komisi'].sum() if not df_filtered.empty else 0:,.0f}</h2></div>", unsafe_allow_index=True)
with col_m3:
    profit_total = df_filtered['Profit'].sum() if not df_filtered.empty else 0
    warna_profit = "#28a745" if profit_total >= 0 else "#dc3545"
    st.markdown(f"<div class='metric-box'><h5>📈 Keuntungan Bersih (Profit)</h5><h2 style='color:{warna_profit};'>Rp {profit_total:,.0f}</h2></div>", unsafe_allow_index=True)

st.markdown("<br>", unsafe_allow_index=True)

# ==========================================
# SECTION 4: TABEL RIWAYAT UTAMA & EVENT KLIK DETAIL ROWS
# ==========================================
st.subheader("📋 Riwayat Laporan Harian")
st.write("👉 **Silakan KLIK KOTAK CENTANG/BARIS pada tabel di bawah ini** untuk membedah data operasional secara detail:")

if df_filtered.empty:
    st.info("Belum ada laporan yang diupload dalam rentang tanggal ini. Silakan gunakan form upload di atas.")
else:
    # Tampilkan tabel riwayat utama interaktif dengan fitur pilih baris bawaan Streamlit
    event_pilih = st.dataframe(
        df_filtered, 
        use_container_width=True, 
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    # ==========================================
    # SECTION 5: TAMPILAN DETAIL OPERASIONAL (PASCA KLIK BARIS)
    # ==========================================
    if event_pilih and len(event_pilih["selection"]["rows"]) > 0:
        indeks_terpilih = event_pilih["selection"]["rows"][0]
        nama_laporan_klik = df_filtered.iloc[indeks_terpilih]["Nama Laporan"]
        
        st.markdown("---")
        st.subheader(f"🔍 Hasil Bedah Data Rinci: {nama_laporan_klik}")
        st.write("Berikut adalah rincian performa konversi, rasio kebocoran klik, komisi kotor/bersih, serta ROAS asli per konten:")
        
        # Ambil data detail terurai dari memori penyimpanan berdasarkan nama laporan yang diklik
        if nama_laporan_klik in st.session_state['detail_laporan_data']:
            df_detail_tampil = st.session_state['detail_laporan_data'][nama_laporan_klik]
            
            # Tampilkan tabel detail operasional dengan format mata uang rupiah dan desimal ROAS
            st.dataframe(
                df_detail_tampil.style.format({
                    'Spend': 'Rp{:,.0f}',
                    'Komisi_Kotor': 'Rp{:,.0f}',
                    'Komisi_Bersih': 'Rp{:,.0f}',
                    'Profit_Rugi': 'Rp{:,.0f}',
                    'ROAS': '{:,.2f}x',
                    'Klik_Meta': '{:,.0f}',
                    'Klik_Shopee': '{:,.0f}',
                    'Pesanan': '{:,.0f}'
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.error("Data detail untuk laporan ini tidak ditemukan di memori browser.")
