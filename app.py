# ==========================================
# 5. KOTAK METRIK SUMMARY INDONESIA PALETTE
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
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
    warna_teks_iklan = "green" if val_keuntungan_iklan >= 0 else "red"
    st.markdown("**Keuntungan Iklan**")
    st.markdown(f"<h3 style='color: {warna_teks_iklan}; margin-top: 4px; font-weight: bold;'>Rp {int(round(val_keuntungan_iklan)):,}".replace(',', '.') + "</h3>", unsafe_allow_html=True)
with col_m5: 
    st.metric(label="📈 Keuntungan Bersih (Total)", value=f"Rp {int(round(val_total_keuntungan)):,}".replace(',', '.'))
