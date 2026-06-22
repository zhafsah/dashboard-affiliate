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
        if not s or s.lower() in ['nan', '-', 'null']:\
            return 0.0
        
        if ',' in s and '.' in s:
            if s.find('.') < s.find(','):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            parts = s.split(',')
            if len(parts[-1]) == 3 and len(parts) > 1:
                s = s.replace(',', '')
            else:
                s = s.replace(',', '.')
        
        try:
            return float(s)
        except ValueError:
            return 0.0

    return series.apply(konversi_nilai)

# ==========================================
# 1. KONFIGURASI HALAMAN & JUDUL
# ==========================================
st.set_page_config(page_title="Dashboard Bedah Data - LeleKeeper", layout="wide")
st.title("📊 DASHBOARD BEDAH DATA ADS & AFFILIATE")
st.markdown("---")

# ==========================================
# 2. FUNGSI PINTAR PENCARI KOLOM (SMART SEARCH)
# ==========================================
def cari_kolom(daftar_kolom, kata_kunci, nama_standar):
    for kk in kata_kunci:
        for col in daftar_kolom:
            if kk.lower() in col.lower():
                return col
    st.error(f"❌ Kolom untuk '{nama_standar}' tidak ditemukan! Periksa file Anda.")
    st.stop()

def clean_tag(x):
    if pd.isna(x) or str(x).strip() == "" or str(x).lower() == "nan":
        return "Organik"
    s = str(x).strip()
    if s.startswith('#'):
        s = s[1:]
    if s.endswith('----'):
        s = s[:-4]
    return s

# ==========================================
# 3. GLOBAL STYLE UNTUK TABEL & METRIK
# ==========================================
def gaya_tabel_summary(row):
    gaya = [''] * len(row)
    if 'Profit' in row.index:
        gaya[row.index.get_loc('Profit')] = 'color: #107C41; font-weight: bold;' if row['Profit'] >= 0 else 'color: #A80000; font-weight: bold;'
    if 'Komisi Iklan' in row.index and 'Spend' in row.index:
        warna_komisi = 'color: #107C41; font-weight: bold;' if row['Komisi Iklan'] > row['Spend'] else 'color: #A80000; font-weight: bold;'
        gaya[row.index.get_loc('Komisi Iklan')] = warna_komisi
    return gaya

with st.expander("📤 AREA UPLOAD FILE BARU", expanded=True):
    col_u1, col_u2, col_u3 = st.columns(3)
    with col_u1:
        file_meta = file_meta_raw = st.file_uploader("1. Upload Data Iklan Meta Ads (.csv)", type=["csv"], key="meta")
    with col_u2:
        file_click = file_click_raw = st.file_uploader("2. Upload Laporan Klik Web Shopee (.csv)", type=["csv"], key="click")
    with col_u3:
        file_sales = file_sales_raw = st.file_uploader("3. Upload Laporan Komisi Affiliate Shopee (.csv)", type=["csv"], key="sales")

if file_meta and file_click and file_sales:
    try:
        try:
            df_meta_raw = pd.read_csv(file_meta_raw, encoding='utf-8')
        except UnicodeDecodeError:
            file_meta_raw.seek(0)
            df_meta_raw = pd.read_csv(file_meta_raw, encoding='utf-16')
            
        try:
            df_click_raw = pd.read_csv(file_click_raw, encoding='utf-8')
        except UnicodeDecodeError:
            file_click_raw.seek(0)
            df_click_raw = pd.read_csv(file_click_raw, encoding='utf-16')
            
        try:
            df_sales_raw = pd.read_csv(file_sales_raw, encoding='utf-8')
        except UnicodeDecodeError:
            file_sales_raw.seek(0)
            df_sales_raw = pd.read_csv(file_sales_raw, encoding='utf-16')

        # --- PROSES METADATA FILE ADS ---
        kolom_tgl_m = cari_kolom(df_meta_raw.columns, ['hari', 'tanggal', 'date'], 'Tanggal Meta')
        kolom_nama_m = cari_kolom(df_meta_raw.columns, ['nama iklan', 'ad name'], 'Nama Iklan Meta')
        kolom_spend_m = cari_kolom(df_meta_raw.columns, ['jumlah yang dibelanjakan', 'amount spent', 'spend'], 'Spend Meta')
        kolom_klik_m = cari_kolom(df_meta_raw.columns, ['klik tautan', 'link clicks', 'clicks'], 'Klik Meta')

        df_meta_clean = pd.DataFrame({
            'Tanggal': pd.to_datetime(df_meta_raw[kolom_tgl_m], errors='coerce').dt.date,
            'Tag': df_meta_raw[kolom_nama_m].apply(clean_tag),
            'Spend': bersihkan_angka_sakti(df_meta_raw[kolom_spend_m]),
            'Klik Meta': bersihkan_angka_sakti(df_meta_raw[kolom_klik_m])
        })

        # --- PROSES METADATA FILE KLIK ---
        kolom_tgl_cl = cari_kolom(df_click_raw.columns, ['waktu klik', 'click time', 'tanggal'], 'Tanggal Klik')
        kolom_tag_cl = cari_kolom(df_click_raw.columns, ['tag_link', 'sub_id', 'tag'], 'Tag Klik')
        kolom_id_cl = cari_kolom(df_click_raw.columns, ['klik id', 'click id'], 'Klik ID')

        df_click_clean = pd.DataFrame({
            'Tanggal': pd.to_datetime(df_click_raw[kolom_tgl_cl], errors='coerce').dt.date,
            'Tag': df_click_raw[kolom_tag_cl].apply(clean_tag),
            'Klik Shopee': 1
        })

        # --- PROSES METADATA FILE PENJUALAN ---
        kolom_tgl_sl = cari_kolom(df_sales_raw.columns, ['waktu klik', 'click time', 'tanggal'], 'Tanggal Penjualan')
        kolom_tag_sl = cari_kolom(df_sales_raw.columns, ['tag_link1', 'sub_id1'], 'Tag Penjualan')
        kolom_id_sl = cari_kolom(df_sales_raw.columns, ['id pemesanan', 'order id'], 'ID Pemesanan')
        kolom_komisi_sl = cari_kolom(df_sales_raw.columns, ['komisi bersih affiliate', 'total komisi', 'komisi'], 'Komisi Bersih')

        df_sales_clean = pd.DataFrame({
            'Tanggal': pd.to_datetime(df_sales_raw[kolom_tgl_sl], errors='coerce').dt.date,
            'Tag': df_sales_raw[kolom_tag_sl].apply(clean_tag),
            'Pesanan': df_sales_raw[kolom_id_sl],
            'Komisi': bersihkan_angka_sakti(df_sales_raw[kolom_komisi_sl])
        })

        # Menyimpan berkas mentah penjualan untuk proses bedah produk di bawah
        df_all_sales = df_sales_raw.copy()
        df_all_sales['Clean_Tag'] = df_all_sales[kolom_tag_sl].apply(clean_tag)
        df_all_sales['Nama Laporan'] = pd.to_datetime(df_all_sales[kolom_tgl_sl], errors='coerce').dt.date

        # ==========================================
        # 4. FILTER RENTANG WAKTU DATA
        # ==========================================
        st.subheader("📅 Filter Rentang Waktu Data")
        semua_tanggal = sorted(list(set(df_meta_clean['Tanggal']).union(set(df_click_clean['Tanggal'])).union(set(df_sales_clean['Tanggal']))))
        
        if semua_tanggal:
            min_tgl = semua_tanggal[0]
            max_tgl = semua_tanggal[-1]
            tgl_pilih = st.date_input("Pilih Rentang Analisis:", [min_tgl, max_tgl], min_value=min_tgl, max_value=max_tgl)
            
            if len(tgl_pilih) == 2:
                start_date, end_date = tgl_pilih
            else:
                start_date = end_date = tgl_pilih[0]
                
            df_m_f = df_meta_clean[(df_meta_clean['Tanggal'] >= start_date) & (df_meta_clean['Tanggal'] <= end_date)]
            df_c_f = df_click_clean[(df_click_clean['Tanggal'] >= start_date) & (df_click_clean['Tanggal'] <= end_date)]
            df_s_f = df_sales_clean[(df_sales_clean['Tanggal'] >= start_date) & (df_sales_clean['Tanggal'] <= end_date)]
            
            # --- PROSES AGREGASI UTAMA ---
            meta_agg = df_m_f.groupby('Tag').agg({'Spend': 'sum', 'Klik Meta': 'sum'}).reset_index()
            click_agg = df_c_f.groupby('Tag').agg({'Klik Shopee': 'sum'}).reset_index()
            sales_agg = df_s_f.groupby('Tag').agg({'Pesanan': 'nunique', 'Komisi': 'sum'}).reset_index()

            semua_tag_aktif = sorted(list(set(meta_agg['Tag']).union(set(click_agg['Tag'])).union(set(sales_agg['Tag']))))
            
            rows_summary = []
            ad_tags = set(df_meta_clean['Tag'].unique())
            
            for tag in semua_tag_aktif:
                m_row = meta_agg[meta_agg['Tag'] == tag]
                c_row = click_agg[click_agg['Tag'] == tag]
                s_row = sales_agg[sales_agg['Tag'] == tag]
                
                spend = m_row['Spend'].values[0] if not m_row.empty else 0.0
                klik_meta = m_row['Klik Meta'].values[0] if not m_row.empty else 0.0
                klik_shopee = c_row['Klik Shopee'].values[0] if not c_row.empty else 0.0
                pesanan = s_row['Pesanan'].values[0] if not s_row.empty else 0
                komisi = s_row['Komisi'].values[0] if not s_row.empty else 0.0
                
                if tag == "Organik":
                    tipe_tag = "ORGANIK"
                elif tag in ad_tags and spend > 0:
                    tipe_tag = "IKLAN (AKTIF)"
                else:
                    tipe_tag = "ORGANIK (TAG TANPA SPEND)"
                    
                rows_summary.append({
                    'Tipe': tipe_tag, 'Tag Link': tag, 'Spend': spend, 'Klik Meta': klik_meta,
                    'Klik Shopee': klik_shopee, 'Pesanan': pesanan, 'Komisi': komisi
                })
                
            df_summary = pd.DataFrame(rows_summary)
            
            # Membagi komisi berdasarkan Tipe data iklan atau organik
            df_summary['Komisi Iklan'] = df_summary.apply(lambda r: r['Komisi'] if r['Tipe'] == "IKLAN (AKTIF)" else 0.0, axis=1)
            df_summary['Komisi Organik'] = df_summary.apply(lambda r: r['Komisi'] if r['Tipe'] != "IKLAN (AKTIF)" else 0.0, axis=1)
            df_summary['Profit'] = df_summary['Komisi'] - df_summary['Spend']

            # Reorder Kolom Tabel Utama
            df_summary = df_summary[['Tipe', 'Tag Link', 'Spend', 'Klik Meta', 'Klik Shopee', 'Pesanan', 'Komisi Iklan', 'Komisi Organik', 'Profit']]

            # ==========================================
            # 5. KOTAK METRIK SUMMARY INDONESIA PALETTE
            # ==========================================
            st.markdown("<br>", unsafe_allow_html=True)

            # Memaksa sistem menggunakan font-family asli Streamlit agar bentuk huruf sama persis
            font_sistem = "font-family: 'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;"
            style_label_top = f"{font_sistem} font-size: 14px; color: rgb(49, 51, 63); opacity: 0.8; font-weight: 400; margin-bottom: 2px; line-height: 1.2;"
            style_value_top = f"{font_sistem} font-size: 28px; font-weight: 600; margin-top: 0px; margin-bottom: 0px; line-height: 1.2;"

            col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)

            val_spend = pd.to_numeric(df_summary['Spend'], errors='coerce').sum() if not df_summary.empty else 0
            val_komisi_iklan = pd.to_numeric(df_summary['Komisi Iklan'], errors='coerce').sum() if not df_summary.empty else 0
            val_komisi_organik = pd.to_numeric(df_summary['Komisi Organik'], errors='coerce').sum() if not df_summary.empty else 0
            val_keuntungan_iklan = val_komisi_iklan - val_spend
            val_total_keuntungan = pd.to_numeric(df_summary['Profit'], errors='coerce').sum() if not df_summary.empty else 0

            with col_m1: 
                st.metric(label="💸 Total Pengeluaran Iklan", value=f"Rp {int(round(val_spend)):,}".replace(',', '.'))
            with col_m2: 
                st.metric(label="🎯 Total Komisi Iklan (Meta)", value=f"Rp {int(round(val_komisi_iklan)):,}".replace(',', '.'))
            with col_m3: 
                st.metric(label="📱 Total Komisi Organik", value=f"Rp {int(round(val_komisi_organik)):,}".replace(',', '.'))
            with col_m4: 
                # Menggunakan div custom style agar font 100% sama dengan metrik lainnya dan ditambahkan emotikon 💰
                warna_teks_iklan = "#107C41" if val_keuntungan_iklan >= 0 else "#A80000"
                st.markdown(f"<div style='{style_label_top}'>💰 Keuntungan Iklan</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='{style_value_top} color: {warna_teks_iklan};'>Rp {int(round(val_keuntungan_iklan)):,}".replace(',', '.') + "</div>", unsafe_allow_html=True)
            with col_m5: 
                st.metric(label="📈 Keuntungan Bersih (Total)", value=f"Rp {int(round(val_total_keuntungan)):,}".replace(',', '.'))

            # ==========================================
            # 6. TABEL UTAMA RINGKASAN DATA
            # ==========================================
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📑 Tabel Ringkasan Data Per Tag")
            
            df_tabel_tampil = df_summary.copy()
            st.dataframe(
                df_tabel_tampil.style.apply(gaya_tabel_summary, axis=1).format({
                    'Spend': lambda x: f"Rp {int(x):,}".replace(',', '.'),
                    'Klik Meta': lambda x: f"{int(x):,}".replace(',', '.'),
                    'Klik Shopee': lambda x: f"{int(x):,}".replace(',', '.'),
                    'Pesanan': lambda x: f"{int(x):,}".replace(',', '.'),
                    'Komisi Iklan': lambda x: f"Rp {int(x):,}".replace(',', '.'),
                    'Komisi Organik': lambda x: f"Rp {int(x):,}".replace(',', '.'),
                    'Profit': lambda x: f"Rp {int(x):,}".replace(',', '.')
                }),
                use_container_width=True
            )

            # ==========================================
            # 7. HASIL BEDAH DATA DETIL (DIKEMBALIKAN KE LAYOUT TOTAL LURUS)
            # ==========================================
            st.markdown("---")
            st.subheader("🔍 7. HASIL BEDAH DATA DETIL")

            tab1, tab2 = st.tabs(["🎯 BEDAH DATA IKLAN (BER-TAG)", "📱 BEDAH DATA ORGANIK"])

            # SETUP MODEL STYLE HURUF AGAR SAMA DAN SEJAJAR SEMUA (BAWAAN TOTAL GABUNGAN)
            style_label = "font-family: sans-serif; font-size: 13px; color: #555555; font-weight: bold; margin-bottom: 3px;"
            style_value = "font-family: sans-serif; font-size: 24px; font-weight: bold; margin-top: 0px;"

            with tab1:
                df_iklan_only = df_summary[df_summary['Tipe'] == "IKLAN (AKTIF)"].copy()
                
                if not df_iklan_only.empty:
                    pilihan_tag = df_iklan_only['Tag Link'].unique()
                    tag_terpilih = st.selectbox("🎯 Pilih Tag Iklan yang Mau Dibedah:", pilihan_tag)
                    
                    df_detail_tampil = df_iklan_only[df_iklan_only['Tag Link'] == tag_terpilih].iloc[0]
                    
                    total_spend_gabungan = df_detail_tampil['Spend']
                    total_klik_meta = df_detail_tampil['Klik Meta']
                    total_klik_shopee = df_detail_tampil['Klik Shopee']
                    
                    # Logika perhitungan ROAS Murni Iklan & Kebocoran
                    roas_iklan_gabungan = df_detail_tampil['Komisi Iklan'] / total_spend_gabungan if total_spend_gabungan > 0 else 0.0
                    kebocoran_gabungan = ((total_klik_meta - total_klik_shopee) / total_klik_meta) * 100 if total_klik_meta > 0 else 0.0
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # Menghitung variabel total pesanan gabungan (iklan + organik) sebelum st.columns
                    daftar_laporan_klik = pd.date_range(start=start_date, end=end_date).date
                    df_product_selected = df_all_sales[(df_all_sales['Nama Laporan'].isin(daftar_laporan_klik)) & (df_all_sales['Clean_Tag'] == tag_terpilih)].copy()
                    total_pesanan_gabungan = df_product_selected['ID Pemesanan'].nunique() if not df_product_selected.empty else 0

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
                    
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    st.write(f"📋 **Rincian Produk Terjual pada Tag: {tag_terpilih}**")
                    
                    if not df_product_selected.empty:
                        # Menambahkan 'nama barange' ke dalam daftar kata kunci agar membaca isi Kolom K file komisi affiliate Shopee
                        kolom_nama_sh = cari_kolom(df_product_selected.columns, ['nama produk', 'product', 'nama barange'], 'Nama Produk')
                        kolom_kat_sh = cari_kolom(df_product_selected.columns, ['kategori'], 'Kategori')
                        kolom_item_sh = cari_kolom(df_product_selected.columns, ['item terjual', 'jumlah'], 'Item Terjual')
                        kolom_komisi_sh = cari_kolom(df_product_selected.columns, ['komisi'], 'Komisi')

                        df_produk_tampil = df_product_selected.groupby([kolom_nama_sh, kolom_kat_sh]).agg({
                            kolom_item_sh: 'sum',
                            kolom_komisi_sh: 'sum'
                        }).reset_index()
                        
                        df_produk_tampil.columns = ['Nama Produk', 'Kategori', 'Item Terjual', 'Komisi Bersih']
                        st.dataframe(df_produk_tampil.style.format({
                            'Item Terjual': lambda x: f"{int(x):,}\".replace(',', '.'), ",
                            'Komisi Bersih': lambda x: f"Rp {int(x):,}".replace(',', '.')
                        }), use_container_width=True)
                    else:
                        st.info("Tidak ada rincian data produk terjual untuk tag iklan ini.")
                else:
                    st.info("Belum ada data dengan tipe IKLAN (AKTIF) di dalam rentang tanggal ini.")

            with tab2:
                st.write("📱 **Analisis Komisi Organik (Tanpa Modal Iklan)**")
                df_organik_only = df_summary[df_summary['Tipe'] != "IKLAN (AKTIF)"].copy()
                
                if not df_organik_only.empty:
                    pilihan_tag_org = df_organik_only['Tag Link'].unique()
                    tag_org_terpilih = st.selectbox("📱 Pilih Tag Organik yang Mau Dibedah:", pilihan_tag_org, key="org_select")
                    
                    df_detail_org = df_organik_only[df_organik_only['Tag Link'] == tag_org_terpilih].iloc[0]
                    
                    col_org1, col_org2, col_org3 = st.columns(3)
                    with col_org1:
                        st.markdown(f"<div style='{style_label}'>🛍️ Klik Shopee (Organik)</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='{style_value} color: #31333F;'>{df_detail_org['Klik Shopee']:,.0f}".replace(',', '.') + " Klik</div>", unsafe_allow_html=True)
                    with col_org2:
                        st.markdown(f"<div style='{style_label}'>📦 Total Pesanan</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='{style_value} color: #31333F;'>{df_detail_org['Pesanan']:,.0f}".replace(',', '.') + " Pesanan</div>", unsafe_allow_html=True)
                    with col_org3:
                        st.markdown(f"<div style='{style_label}'>💰 Total Komisi Organik</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='{style_value} color: #107C41;'>Rp {df_detail_org['Komisi Organik']:,.0f}".replace(',', '.') + "</div>", unsafe_allow_html=True)
                        
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    st.write(f"📋 **Rincian Produk Terjual pada Tag Organik: {tag_org_terpilih}**")
                    
                    daftar_laporan_klik = pd.date_range(start=start_date, end=end_date).date
                    df_product_selected = df_all_sales[(df_all_sales['Nama Laporan'].isin(daftar_laporan_klik)) & (df_all_sales['Clean_Tag'] == tag_org_terpilih)].copy()
                    
                    if not df_product_selected.empty:
                        # Menambahkan 'nama barange' ke dalam daftar kata kunci agar membaca isi Kolom K file komisi affiliate Shopee
                        kolom_nama_sh = cari_kolom(df_product_selected.columns, ['nama produk', 'product', 'nama barange'], 'Nama Produk')
                        kolom_kat_sh = cari_kolom(df_product_selected.columns, ['kategori'], 'Kategori')
                        kolom_item_sh = cari_kolom(df_product_selected.columns, ['item terjual', 'jumlah'], 'Item Terjual')
                        kolom_komisi_sh = cari_kolom(df_product_selected.columns, ['komisi'], 'Komisi')

                        df_organik_tampil = df_product_selected.groupby([kolom_nama_sh, kolom_kat_sh]).agg({
                            kolom_item_sh: 'sum',
                            kolom_komisi_sh: 'sum'
                        }).reset_index()
                        
                        df_organik_tampil.columns = ['Nama Produk', 'Kategori', 'Item Terjual', 'Komisi Bersih']
                        st.dataframe(df_organik_tampil.style.format({
                            'Item Terjual': lambda x: f"{int(x):,}\".replace(',', '.'), ",
                            'Komisi Bersih': lambda x: f"Rp {int(x):,}".replace(',', '.')
                        }), use_container_width=True)
                    else:
                        st.info("Tidak ada rincian data produk terjual untuk tag organik ini.")
                else:
                    st.info("Tidak ada data organik dalam rentang tanggal ini.")

        else:
            st.warning("⚠️ Rentang tanggal data kosong atau tidak valid.")
            
    except Exception as e:
        st.error(f"🚨 Terjadi kesalahan sistem saat memproses berkas: {str(e)}")
        st.info("Pastikan format file CSV Anda sesuai dengan kolom data platform iklan dan affiliate Shopee asli.")
else:
    st.info("💡 Sila unggah ketiga dokumen CSV di atas secara lengkap untuk mengaktifkan kalkulasi sistem otomatis.")
