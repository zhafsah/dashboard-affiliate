import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# 1. PENGATURAN HALAMAN UTAMA DASHBOARD
# ==========================================
st.set_page_config(page_title="Affiliate Advanced Analytics", layout="wide")

st.title("📊 Dashboard Evaluasi & Performa Affiliate")
st.write("Kelola pengeluaran iklan Meta dan optimalkan komisi bersih Shopee Anda dalam satu layar.")

# ==========================================
# 2. INISIALISASI MEMORI (SESSION STATE)
# ==========================================
if 'riwayat_summary' not in st.session_state:
    st.session_state['riwayat_summary'] = pd.DataFrame(columns=["Tanggal", "Nama Laporan", "Spend", "Komisi", "Profit", "Status"])
if 'detail_laporan_data' not in st.session_state:
    st.session_state['detail_laporan_data'] = {}

# Fungsi pembantu untuk membersihkan tanda pagar (#) dan strip (----) pada nama iklan/tag
def bersihkan_tag(x):
    if pd.isna(x) or str(x).strip() == "" or str(x).lower() == "nan":
        return "Organik"
    s = str(x).strip()
    if s.startswith('#'): s = s[1:]
    if s.endswith('----'): s = s[:-4]
    return s

# ==========================================
# 3. AREA UPLOAD FILE DI BAGIAN ATAS
# ==========================================
with st.expander("📤 AREA UPLOAD FILE BARU (Drop 3 File CSV Mentah Anda Sekaligus)", expanded=True):
    col_input1, col_input2 = st.columns([1, 2])
    with col_input1:
        nama_laporan = st.text_input("Nama / Catatan Laporan:", placeholder="Contoh: Laporan 04 Jun")
    with col_input2:
        uploaded_files = st.file_uploader("", type=["csv"], accept_multiple_files=True)

# Proses membaca file ketika diupload
if len(uploaded_files) >= 3 and nama_laporan:
    df_meta, df_clicks, df_sales = None, None, None
    for file in uploaded_files:
        try:
            # Menggunakan encoding utf-8 atau latin-1 untuk mencegah error format berkas
            try:
                df_temp = pd.read_csv(file, encoding='utf-8')
            except:
                df_temp = pd.read_csv(file, encoding='latin-1')
            
            # Deteksi otomatis tipe file berdasarkan nama kolom di dalamnya
            if 'Jumlah yang dibelanjakan (IDR)' in df_temp.columns or 'Nama iklan' in df_temp.columns:
                df_meta = df_temp
            elif 'Klik ID' in df_temp.columns and 'Tag_link' in df_temp.columns:
                df_clicks = df_temp
            elif 'Total Komisi per Pesanan(Rp)' in df_temp.columns or 'Komisi Bersih Affiliate (Rp)' in df_temp.columns:
                df_sales = df_temp
        except Exception as e:
            st.error(f"Gagal membaca file {file.name}: {str(e)}")

    if df_meta is not None and df_clicks is not None and df_sales is not None:
        # Sinkronisasi nama kolom untuk mengantisipasi perbedaan huruf besar/kecil
        df_sales.columns = df_sales.columns.str.strip()
        kolom_pesanan = 'ID pesanan' if 'ID pesanan' in df_sales.columns else ('ID Pemesanan' if 'ID Pemesanan' in df_sales.columns else df_sales.columns[0])

        # Pembersihan Nama Konten / Tag Iklan
        df_meta['Clean_Tag'] = df_meta['Nama iklan'].apply(bersihkan_tag)
        df_sales['Clean_Tag'] = df_sales['Tag_link1'].apply(bersihkan_tag)
        df_clicks['Clean_Tag'] = df_clicks['Tag_link'].apply(bersihkan_tag)

        # A. Mengolah Data Pengeluaran Iklan Meta
        meta_sum = df_meta.groupby('Clean_Tag').agg(
            Spend=('Jumlah yang dibelanjakan (IDR)', 'sum'),
            Klik_Meta=('Klik tautan', 'sum')
        ).reset_index()

        # B. Mengolah Data Trafik Masuk Klik Shopee
        click_sum = df_clicks.groupby('Clean_Tag').agg(Klik_Shopee=('Klik ID', 'count')).reset_index()
        
        # C. Mengolah Data Penjualan & Komisi Shopee
        sales_sum = df_sales.groupby('Clean_Tag').agg(
            Pesanan=(kolom_pesanan, 'nunique'),
            Komisi_Kotor=('Total Komisi per Pesanan(Rp)', 'sum'),
            Komisi_Bersih=('Komisi Bersih Affiliate (Rp)', 'sum')
        ).reset_index()

        # Penggabungan 3 Data Mentah Menjadi 1 Tabel Terintegrasi
        merged = pd.merge(meta_sum, click_sum, on='Clean_Tag', how='outer')
        merged = pd.merge(merged, sales_sum, on='Clean_Tag', how='outer').fillna(0)

        # Klasifikasi Otomatis Trafik (IKLAN AKTIF vs ORGANIK)
        ad_tags = set(df_meta['Clean_Tag'].unique())
        merged['Tipe'] = merged.apply(lambda r: "IKLAN (AKTIF)" if r['Clean_Tag'] in ad_tags and r['Spend'] > 0 else "ORGANIK", axis=1)
        
        # Menghitung Profit dan Nilai ROAS
        merged['Profit_Rugi'] = merged['Komisi_Bersih'] - merged['Spend']
        merged['ROAS'] = merged.apply(lambda r: r['Komisi_Bersih'] / r['Spend'] if r['Spend'] > 0 else 0.0, axis=1)
        
        # Menyusun Susunan Kolom Data Operasional Akhir
        merged = merged[['Tipe', 'Clean_Tag', 'Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Komisi_Kotor', 'Komisi_Bersih', 'Profit_Rugi', 'ROAS']]
        
        # Hitung Nilai Akumulasi Total untuk Dashboard Utama depan
        total_spend = merged['Spend'].sum()
        total_komisi = merged['Komisi_Bersih'].sum()
        total_profit = total_komisi - total_spend

        # Membuat baris rangkuman baru
        new_summary = pd.DataFrame([{
            "Tanggal": datetime.now().date(), 
            "Nama Laporan": nama_laporan,
            "Spend": total_spend, 
            "Komisi": total_komisi, 
            "Profit": total_profit, 
            "Status": "Sukses"
        }])
        
        # Menyimpan ke memori internal halaman aplikasi
        if nama_laporan not in st.session_state['riwayat_summary']['Nama Laporan'].values:
            st.session_state['riwayat_summary'] = pd.concat([st.session_state['riwayat_summary'], new_summary], ignore_index=True)
            st.session_state['detail_laporan_data'][nama_laporan] = merged
            st.success(f"✅ Laporan '{nama_laporan}' berhasil dibedah! Silakan periksa tabel di bawah.")
        else:
            st.warning("Nama laporan sudah ada. Harap gunakan nama laporan yang berbeda.")

st.markdown("---")

# ==========================================
# 4. FILTER KALENDER & SHORTCUTS WAKTU
# ==========================================
st.subheader("🔍 Filter Rentang Waktu Data")
col_btn1, col_btn2, col_btn3, col_date = st.columns([1, 1, 1, 3])

today = datetime.now().date()

# Mengunci nilai default agar tidak memicu error kosong pertama kali dimuat
if 'start_filter' not in st.session_state:
    st.session_state['start_filter'] = today - timedelta(days=7)
if 'end_filter' not in st.session_state:
    st.session_state['end_filter'] = today

with col_btn1:
    if st.button("📅 Kemarin", use_container_width=True):
        st.session_state['start_filter'] = today - timedelta(days=1)
        st.session_state['end_filter'] = today - timedelta(days=1)
with col_btn2:
    if st.button("📅 Bulan Ini", use_container_width=True):
        st.session_state['start_filter'] = today.replace(day=1)
        st.session_state['end_filter'] = today
with col_btn3:
    if st.button("📅 Bulan Lalu", use_container_width=True):
        last_month_end = today.replace(day=1) - timedelta(days=1)
        st.session_state['start_filter'] = last_month_end.replace(day=1)
        st.session_state['end_filter'] = last_month_end

with col_date:
    rentang_tanggal = st.date_input(
        "Atau Pilih Kustom Kalender:", 
        value=(st.session_state['start_filter'], st.session_state['end_filter'])
    )

# Mengamankan pembacaan data kalender
if isinstance(rentang_tanggal, tuple) and len(rentang_tanggal) == 2:
    filter_start, filter_end = rentang_tanggal
else:
    filter_start, filter_end = st.session_state['start_filter'], st.session_state['end_filter']

# Filter data riwayat summary harian
if not st.session_state['riwayat_summary'].empty:
    df_filtered = st.session_state['riwayat_summary'][
        (st.session_state['riwayat_summary']['Tanggal'] >= filter_start) & 
        (st.session_state['riwayat_summary']['Tanggal'] <= filter_end)
    ]
else:
    df_filtered = st.session_state['riwayat_summary']

# ==========================================
# 5. KOTAK METRIK RINGKASAN DATA (KPI CARDS)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
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

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 6. TABEL RIWAYAT UTAMA & DETEKSI KLIK BARIS
# ==========================================
st.subheader("📋 Riwayat Laporan Harian")
st.write("👉 **Silakan klik baris atau centang kotak** pada laporan di bawah untuk melihat rincian operasional lengkap:")

if df_filtered.empty:
    st.info("Belum ada laporan dalam rentang tanggal ini. Silakan unggah 3 file CSV Anda pada area upload di atas.")
else:
    # Mengaktifkan fitur interaktif row selection pada dataframe
    event_pilih = st.dataframe(
        df_filtered, 
        use_container_width=True, 
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    # ==========================================
    # 7. AREA BEDAH DETAIL RINCI OPERASIONAL (PASCA KLIK)
    # ==========================================
    if event_pilih and len(event_pilih["selection"]["rows"]) > 0:
        indeks_terpilih = event_pilih["selection"]["rows"][0]
        nama_laporan_klik = df_filtered.iloc[indeks_terpilih]["Nama Laporan"]
        
        st.markdown("---")
        st.subheader(f"🔍 Hasil Bedah Data Rinci: {nama_laporan_klik}")
        st.write("Berikut detail perbandingan performa konversi klik, pesanan, omset komisi kotor/bersih, serta ROAS per video:")
        
        if nama_laporan_klik in st.session_state['detail_laporan_data']:
            df_detail_tampil = st.session_state['detail_laporan_data'][nama_laporan_klik]
            
            # Format visual tabel detail operasional
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
            st.error("Gagal menarik data detail dari memori sistem.")
