import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# 1. PENGATURAN HALAMAN UTAMA DASHBOARD
# ==========================================
st.set_page_config(page_title="Affiliate Advanced Analytics", layout="wide")

st.title("📊 Dashboard Evaluasi & Performa Affiliate")
st.write("Kelola pengeluaran iklan Meta dan optimalkan komisi bersih Shopee Anda dalam satu layar.")

# Kamus untuk mengubah nama bulan ke bahasa Indonesia
BULAN_INDO = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

# ==========================================
# 2. INISIALISASI MEMORI (SESSION STATE)
# ==========================================
if 'riwayat_summary' not in st.session_state:
    st.session_state['riwayat_summary'] = pd.DataFrame(columns=[
        "Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi (Nett)", "Profit"
    ])
if 'detail_laporan_data' not in st.session_state:
    st.session_state['detail_laporan_data'] = {}
if 'raw_sales_data' not in st.session_state:
    st.session_state['raw_sales_data'] = {}

# Fungsi pembantu untuk membersihkan nama iklan/tag
def bersihkan_tag(x):
    if pd.isna(x) or str(x).strip() == "" or str(x).lower() == "nan":
        return "Organik"
    s = str(x).strip()
    if s.startswith('#'): s = s[1:]
    if s.endswith('----'): s = s[:-4]
    return s

# Fungsi otomatis mencari nama kolom berdasarkan kata kunci (Pencegah KeyError)
def cari_kolom(list_kolom, kata_kunci_list, default_name):
    for col in list_kolom:
        for kw in kata_kunci_list:
            if kw.lower() in str(col).lower():
                return col
    return default_name

# Fungsi pewarnaan bersyarat untuk baris tabel summary harian
def gaya_tabel_summary(row):
    gaya = [''] * len(row)
    profit_iklan = row['Komisi Iklan'] - row['Spend']
    warna_iklan = 'green' if profit_iklan >= 0 else 'red'
    if 'Komisi Iklan' in row.index:
        gaya[row.index.get_loc('Komisi Iklan')] = f'color: {warna_iklan}; font-weight: bold;'
    
    warna_total = 'green' if row['Profit'] >= 0 else 'red'
    if 'Total Komisi (Nett)' in row.index:
        gaya[row.index.get_loc('Total Komisi (Nett)')] = f'color: {warna_total}; font-weight: bold;'
    if 'Profit' in row.index:
        gaya[row.index.get_loc('Profit')] = f'color: {warna_total}; font-weight: bold;'
    
    return gaya

# Fungsi pewarnaan kolom kebocoran & highlight baris iklan aktif pada tabel detail rinci
def gaya_tabel_detail(row):
    gaya = [''] * len(row)
    
    if row['Tipe'] == "IKLAN (AKTIF)":
        gaya = ['background-color: #f0f4f8; border-left: 4px solid #1f77b4;'] * len(row)
        
    warna_kebocoran = 'green' if row['Klik_Shopee'] > row['Klik_Meta'] else 'red'
    if 'Kebocoran' in row.index:
        bg_style = 'background-color: #f0f4f8;' if row['Tipe'] == "IKLAN (AKTIF)" else ''
        gaya[row.index.get_loc('Kebocoran')] = f'{bg_style} color: {warna_kebocoran}; font-weight: bold;'
        
    return gaya

# ==========================================
# 3. AREA UPLOAD FILE DI BAGIAN ATAS
# ==========================================
with st.expander("📤 AREA UPLOAD FILE BARU (Drop 3 File CSV Mentah Anda Sekaligus)", expanded=True):
    with st.form("form_upload", clear_on_submit=True):
        col_input1, col_input2, col_input3 = st.columns([1.5, 1.5, 3])
        
        with col_input2:
            tanggal_laporan = st.date_input("Tanggal Laporan:", value=datetime.now().date())
            tgl_obj = tanggal_laporan
            nama_bulan = BULAN_INDO[tgl_obj.month]
            default_nama = f"Laporan {tgl_obj.day:02d} {nama_bulan}"
            
        with col_input1:
            nama_laporan = st.text_input("Nama / Catatan Laporan:", value=default_nama)
            
        with col_input3:
            uploaded_files = st.file_uploader("Pilih berkas CSV iklan, klik, dan penjualan:", type=["csv"], accept_multiple_files=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        tombol_proses = st.form_submit_button("🚀 Proses & Bedah Laporan", use_container_width=True)

# Proses membaca file ketika tombol form ditekan
if tombol_proses:
    if len(uploaded_files) < 3:
        st.error("Silakan unggah minimal 3 file CSV terlebih dahulu (File Meta Ads, Klik Shopee, dan Penjualan Shopee).")
    elif not nama_laporan:
        st.error("Nama atau Catatan Laporan tidak boleh kosong.")
    else:
        df_meta, df_clicks, df_sales = None, None, None
        for file in uploaded_files:
            try:
                try:
                    df_temp = pd.read_csv(file, encoding='utf-8')
                except:
                    df_temp = pd.read_csv(file, encoding='latin-1')
                
                if 'Jumlah yang dibelanjakan (IDR)' in df_temp.columns or 'Nama iklan' in df_temp.columns:
                    df_meta = df_temp
                elif 'Klik ID' in df_temp.columns and 'Tag_link' in df_temp.columns:
                    df_clicks = df_temp
                elif 'Total Komisi per Pesanan(Rp)' in df_temp.columns or 'Komisi Bersih Affiliate (Rp)' in df_temp.columns or 'Nama Produk' in df_temp.columns:
                    df_sales = df_temp
            except Exception as e:
                st.error(f"Gagal membaca file {file.name}: {str(e)}")

        if df_meta is not None and df_clicks is not None and df_sales is not None:
            df_sales.columns = df_sales.columns.str.strip()
            
            # Deteksi Kolom Penjualan Shopee secara Pintar & Dinamis
            kolom_pesanan = cari_kolom(df_sales.columns, ['id pesanan', 'id pemesanan', 'order id'], df_sales.columns[0])
            kolom_tag_sales = cari_kolom(df_sales.columns, ['tag_link1', 'tag link', 'sub id'], 'Tag_link1')
            kolom_komisi_kotor = cari_kolom(df_sales.columns, ['total komisi per pesanan', 'komisi kotor'], df_sales.columns[-1])
            kolom_komisi_bersih = cari_kolom(df_sales.columns, ['komisi bersih affiliate', 'komisi bersih'], kolom_komisi_kotor)
            
            # Deteksi kolom nama produk, kategori, dan jumlah item (Solusi Utama Error)
            kolom_nama_produk = cari_kolom(df_sales.columns, ['nama produk', 'product name', 'item'], 'Nama Produk')
            kolom_kategori_produk = cari_kolom(df_sales.columns, ['kategori kunci', 'kategori', 'category'], 'Kategori')
            kolom_jumlah_item = cari_kolom(df_sales.columns, ['item terjual', 'jumlah', 'quantity', 'qty'], 'Item Terjual')

            # Proses Normalisasi Tag
            df_meta['Clean_Tag'] = df_meta['Nama iklan'].apply(bersihkan_tag)
            df_clicks['Clean_Tag'] = df_clicks['Tag_link'].apply(bersihkan_tag)
            df_sales['Clean_Tag'] = df_sales[kolom_tag_sales].apply(bersihkan_tag)

            # Kumpulan tag yang aktif di Meta Ads
            ad_tags = set(df_meta[df_meta['Jumlah yang dibelanjakan (IDR)'] > 0]['Clean_Tag'].unique())

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
                Komisi_Kotor=(kolom_komisi_kotor, 'sum'),
                Komisi_Bersih=(kolom_komisi_bersih, 'sum')
            ).reset_index()

            # Penggabungan Data Detail untuk Hasil Bedah Data Rinci
            merged = pd.merge(meta_sum, click_sum, on='Clean_Tag', how='outer')
            merged = pd.merge(merged, sales_sum, on='Clean_Tag', how='outer').fillna(0)

            merged['Tipe'] = merged.apply(lambda r: "IKLAN (AKTIF)" if r['Clean_Tag'] in ad_tags and r['Spend'] > 0 else "ORGANIK", axis=1)
            
            merged['Kebocoran'] = merged.apply(
                lambda r: ((r['Klik_Meta'] - r['Klik_Shopee']) / r['Klik_Meta']) * 100 if r['Klik_Meta'] > 0 else 0.0, 
                axis=1
            )

            merged['Profit_Rugi'] = merged['Komisi_Bersih'] - merged['Spend']
            merged['ROAS'] = merged.apply(lambda r: r['Komisi_Bersih'] / r['Spend'] if r['Spend'] > 0 else 0.0, axis=1)
            
            merged = merged[['Tipe', 'Clean_Tag', 'Spend', 'Klik_Meta', 'Klik_Shopee', 'Pesanan', 'Kebocoran', 'Komisi_Kotor', 'Profit_Rugi', 'ROAS']]
            
            # --- PERHITUNGAN UNTUK RIWAYAT SUMMARY UTAMA ---
            total_spend = merged['Spend'].sum()
            total_komisi_kotor = merged['Komisi_Kotor'].sum()
            
            komisi_iklan_nett = merged[merged['Clean_Tag'].isin(ad_tags)]['Komisi_Kotor'].sum()
            komisi_organik_nett = merged[~merged['Clean_Tag'].isin(ad_tags)]['Komisi_Kotor'].sum()
            
            total_komisi_nett = df_sales[kolom_komisi_bersih].sum() if kolom_komisi_bersih in df_sales.columns else total_komisi_kotor
            total_profit = total_komisi_nett - total_spend

            # Membuat baris rangkuman baru
            new_summary = pd.DataFrame([{
                "Tanggal": tanggal_laporan, 
                "Nama Laporan": nama_laporan,
                "Spend": total_spend, 
                "Komisi Iklan": komisi_iklan_nett,
                "Komisi Organik": komisi_organik_nett,
                "Total Komisi (Nett)": total_komisi_nett,
                "Profit": total_profit
            }])
            
            if nama_laporan not in st.session_state['riwayat_summary']['Nama Laporan'].values:
                st.session_state['riwayat_summary'] = pd.concat([st.session_state['riwayat_summary'], new_summary], ignore_index=True)
                st.session_state['detail_laporan_data'][nama_laporan] = merged
                
                # Pembuatan dataframe penampung rincian produk yang aman dari KeyError
                df_raw_save = pd.DataFrame()
                df_raw_save['Clean_Tag'] = df_sales['Clean_Tag']
                df_raw_save['Nama Produk'] = df_sales[kolom_nama_produk] if kolom_nama_produk in df_sales.columns else "Produk Tidak Diketahui"
                df_raw_save['Kategori'] = df_sales[kolom_kategori_produk] if kolom_kategori_produk in df_sales.columns else "Umum"
                df_raw_save['Item Terjual'] = pd.to_numeric(df_sales[kolom_jumlah_item], errors='coerce').fillna(1)
                df_raw_save['Komisi'] = pd.to_numeric(df_sales[kolom_komisi_kotor], errors='coerce').fillna(0)
                
                st.session_state['raw_sales_data'][nama_laporan] = df_raw_save
                
                st.success(f"✅ Laporan '{nama_laporan}' berhasil diproses dan disimpan! Isian berkas otomatis dikosongkan.")
                st.rerun()
            else:
                st.warning("Nama laporan sudah ada. Harap gunakan nama laporan yang berbeda.")

st.markdown("---")

# ==========================================
# 4. FILTER KALENDER & SHORTCUTS WAKTU
# ==========================================
st.subheader("🔍 Filter Rentang Waktu Data")
col_btn1, col_btn2, col_btn3, col_date = st.columns([1, 1, 1, 3])

today = datetime.now().date()

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

if isinstance(rentang_tanggal, tuple) and len(rentang_tanggal) == 2:
    filter_start, filter_end = rentang_tanggal
else:
    filter_start, filter_end = st.session_state['start_filter'], st.session_state['end_filter']

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
val_komisi = df_filtered['Total Komisi (Nett)'].sum() if not df_filtered.empty else 0
val_profit = df_filtered['Profit'].sum() if not df_filtered.empty else 0

with col_m1:
    st.metric(label="💸 Total Pengeluaran Iklan", value=f"Rp {val_spend:,.0f}")
with col_m2:
    st.metric(label="💰 Total Komisi Masuk (Nett)", value=f"Rp {val_komisi:,.0f}")
with col_m3:
    st.metric(label="📈 Keuntungan Bersih (Profit)", value=f"Rp {val_profit:,.0f}")

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 6. TABEL RIWAYAT UTAMA & DETEKSI KLIK BARIS
# ==========================================
st.subheader("📋 Riwayat Laporan Harian")
st.write("👉 **Silakan klik baris atau centang kotak** pada laporan di bawah untuk melihat rincian operasional lengkap:")

if df_filtered.empty:
    st.info("Belum ada laporan dalam rentang tanggal ini. Silakan unggah file Anda pada area upload di atas.")
else:
    df_styled_summary = df_filtered.style.format({
        'Spend': 'Rp{:,.0f}',
        'Komisi Iklan': 'Rp{:,.0f}',
        'Komisi Organik': 'Rp{:,.0f}',
        'Total Komisi (Nett)': 'Rp{:,.0f}',
        'Profit': 'Rp{:,.0f}'
    }).apply(gaya_tabel_summary, axis=1)

    event_pilih = st.dataframe(
        df_styled_summary, 
        use_container_width=True, 
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if event_pilih and len(event_pilih["selection"]["rows"]) > 0:
        indeks_terpilih = event_pilih["selection"]["rows"][0]
        laporan_terpilih = df_filtered.iloc[indeks_terpilih]
        nama_laporan_klik = laporan_terpilih["Nama Laporan"]
        
        if st.button(f"🗑️ Hapus Laporan: {nama_laporan_klik}", type="secondary"):
            st.session_state['riwayat_summary'] = st.session_state['riwayat_summary'][
                st.session_state['riwayat_summary']['Nama Laporan'] != nama_laporan_klik
            ].reset_index(drop=True)
            
            if nama_laporan_klik in st.session_state['detail_laporan_data']:
                del st.session_state['detail_laporan_data'][nama_laporan_klik]
            if nama_laporan_klik in st.session_state['raw_sales_data']:
                del st.session_state['raw_sales_data'][nama_laporan_klik]
                
            st.toast(f"Laporan '{nama_laporan_klik}' berhasil dihapus!")
            st.rerun()

        # ==========================================
        # 7. AREA BEDAH DETAIL RINCI OPERASIONAL (PASCA KLIK)
        # ==========================================
        st.markdown("---")
        st.subheader(f"🔍 Hasil Bedah Data Rinci: {nama_laporan_klik}")
        
        if nama_laporan_klik in st.session_state['detail_laporan_data']:
            df_detail_tampil = st.session_state['detail_laporan_data'][nama_laporan_klik]
            
            # Perhitungan Akumulasi Total Berurutan Iklan Aktif
            df_iklan_aktif = df_detail_tampil[df_detail_tampil['Tipe'] == "IKLAN (AKTIF)"]
            total_spend_iklan = df_iklan_aktif['Spend'].sum()
            total_klik_meta_iklan = df_iklan_aktif['Klik_Meta'].sum()
            total_klik_shopee_iklan = df_iklan_aktif['Klik_Shopee'].sum()
            roas_iklan_gabungan = (df_iklan_aktif['Komisi_Kotor'].sum() / total_spend_iklan) if total_spend_iklan > 0 else 0.0
            
            # Tampilan Metrik Berurutan 4 Kolom Utama
            col_ad1, col_ad2, col_ad3, col_ad4 = st.columns(4)
            with col_ad1:
                st.metric(label="💳 Total Spend Iklan (Iklan Aktif)", value=f"Rp {total_spend_iklan:,.0f}")
            with col_ad2:
                st.metric(label="🎯 Total Klik Meta (Iklan Aktif)", value=f"{total_klik_meta_iklan:,.0f} Klik")
            with col_ad3:
                st.metric(label="🛍️ Total Klik Shopee (Iklan Aktif)", value=f"{total_klik_shopee_iklan:,.0f} Klik")
            with col_ad4:
                st.metric(label="📊 ROAS (Iklan Aktif)", value=f"{roas_iklan_gabungan:,.2f}x")
            
            st.write("💡 *Baris bertanda warna **abu-biru muda** merupakan video yang dipasangi **Iklan Aktif**. Silakan klik baris di bawah untuk membedah produk terjual:*")

            # Memformat tabel rincian dengan highlight baris khusus iklan aktif
            df_styled_detail = df_detail_tampil.style.format({
                'Spend': 'Rp{:,.0f}',
                'Komisi_Kotor': 'Rp{:,.0f}',
                'Profit_Rugi': 'Rp{:,.0f}',
                'ROAS': '{:,.2f}x',
                'Klik_Meta': '{:,.0f}',
                'Klik_Shopee': '{:,.0f}',
                'Pesanan': '{:,.0f}',
                'Kebocoran': '{:,.2f}%'
            }).apply(gaya_tabel_detail, axis=1)
            
            event_klik_detail = st.dataframe(
                df_styled_detail,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            # ==========================================
            # 8. RINCIAN PRODUK TERJUAL (PASCA KLIK BARIS DETAIL)
            # ==========================================
            if event_klik_detail and len(event_klik_detail["selection"]["rows"]) > 0:
                indeks_detail = event_klik_detail["selection"]["rows"][0]
                tag_terpilih = df_detail_tampil.iloc[indeks_detail]["Clean_Tag"]
                
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader(f"📦 Rincian Produk Terjual untuk Tag: #{tag_terpilih}")
                
                if nama_laporan_klik in st.session_state['raw_sales_data']:
                    df_raw_sales = st.session_state['raw_sales_data'][nama_laporan_klik]
                    df_produk_terfilter = df_raw_sales[df_raw_sales['Clean_Tag'] == tag_terpilih]
                    
                    if not df_produk_terfilter.empty:
                        df_produk_tampil = df_produk_terfilter.groupby(['Nama Produk', 'Kategori']).agg(
                            Item_Terjual=('Item Terjual', 'sum'),
                            Komisi_Diterima=('Komisi', 'sum')
                        ).reset_index()
                        
                        df_produk_tampil.columns = ['Nama Produk', 'Kategori', 'Item Terjual', 'Komisi']
                        
                        st.dataframe(
                            df_produk_tampil.style.format({
                                'Item Terjual': '{:,.0f}',
                                'Komisi': 'Rp{:,.0f}'
                            }),
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.info("Tidak ada rincian item produk yang tercatat khusus untuk tag ini.")
        else:
            st.error("Gagal menarik data detail dari memori sistem.")
