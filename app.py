import streamlit as st
import pandas as pd

st.set_page_config(page_title="Assortiment vs MenuList Matcher", layout="wide")

st.title("📦 Assortiment vs MenuList Matcher (avec Images)")
st.markdown("Uploadez vos fichiers pour identifier les produits existants et manquants. Les prix, quantités et **photos** seront intégrés !")

# Barre latérale pour l'upload des fichiers
st.sidebar.header("1. Upload des Fichiers")
assortiment_file = st.sidebar.file_uploader("1️⃣ Fichier Assortiment (CSV ou Excel)", type=['csv', 'xlsx'])
menulist_file = st.sidebar.file_uploader("2️⃣ Fichier MenuList (CSV)", type=['csv'])
pricing_file = st.sidebar.file_uploader("3️⃣ Fichier Prix & Quantités (Ex: invalid_rows.csv)", type=['csv'])

# Variables globales
df_assort = None
store_col = None
store_filter = None

# Fonction pour trouver la colonne image
def find_image_column(df):
    for col in df.columns:
        if 'image' in col.lower() or 'photo' in col.lower() or 'url' in col.lower():
            return col
    return None

# Étape 1 : Lecture de l'assortiment et sélection du Store ID
if assortiment_file:
    try:
        if assortiment_file.name.endswith('.csv'):
            df_assort = pd.read_csv(assortiment_file)
        else:
            df_assort = pd.read_excel(assortiment_file)
            
        store_col = next((col for col in df_assort.columns if 'store' in col.lower() or 'magasin' in col.lower()), None)
        
        st.sidebar.header("2. Choix du Magasin")
        if store_col:
            unique_stores = df_assort[store_col].dropna().astype(str).str.replace(r'\.0$', '', regex=True).unique().tolist()
            unique_stores.sort()
            store_filter = st.sidebar.selectbox("Sélectionnez le Store ID :", unique_stores, index=unique_stores.index('170') if '170' in unique_stores else 0)
        else:
            store_filter = st.sidebar.text_input("Entrez le Store ID manuellement (ex: 170)", value="170")
            
    except Exception as e:
        st.sidebar.error(f"Erreur lors de la lecture de l'assortiment : {e}")

# Étape 2 : Traitement une fois les fichiers uploadés
if df_assort is not None and menulist_file:
    if st.sidebar.button("Lancer la correspondance 🚀"):
        with st.spinner('Traitement des données en cours...'):
            try:
                # Lecture MenuList
                df_menu = pd.read_csv(menulist_file, sep=';', dtype=str)
                
                if 'external_id' in df_assort.columns and 'external_id' in df_menu.columns:
                    # Nettoyage
                    df_assort['external_id'] = df_assort['external_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                    df_menu['external_id'] = df_menu['external_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                    
                    # Filtrage Store
                    if store_col:
                        df_assort_filtered = df_assort[df_assort[store_col].astype(str).str.replace(r'\.0$', '', regex=True) == str(store_filter)]
                    else:
                        df_assort_filtered = df_assort
                    
                    # Jointure
                    menu_subset = df_menu[['external_id', 'food_id']].drop_duplicates(subset=['external_id'])
                    merged = pd.merge(df_assort_filtered, menu_subset, on='external_id', how='left')
                    
                    existing_products = merged[merged['food_id'].notna()].copy()
                    non_existing_products = merged[merged['food_id'].isna()].copy()
                    
                    # --- Étape 3 : Enrichissement Prix & Quantités ---
                    if pricing_file is not None:
                        df_pricing = pd.read_csv(pricing_file)
                        if 'product_id' in df_pricing.columns:
                            df_pricing['product_id'] = df_pricing['product_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                            
                            if 'store_id' in df_pricing.columns and store_filter:
                                df_pricing = df_pricing[df_pricing['store_id'].astype(str).str.replace(r'\.0$', '', regex=True) == str(store_filter)]
                            
                            cols_to_keep = ['product_id']
                            if 'price' in df_pricing.columns: cols_to_keep.append('price')
                            if 'stock' in df_pricing.columns: cols_to_keep.append('stock')
                            
                            pricing_subset = df_pricing[cols_to_keep].drop_duplicates(subset=['product_id'])
                            
                            non_existing_products = pd.merge(non_existing_products, pricing_subset, left_on='external_id', right_on='product_id', how='left')
                            if 'product_id' in non_existing_products.columns:
                                non_existing_products = non_existing_products.drop(columns=['product_id'])
                    
                    # --- Configuration de l'affichage des images ---
                    img_col_existing = find_image_column(existing_products)
                    img_col_non_existing = find_image_column(non_existing_products)
                    
                    config_existing = {img_col_existing: st.column_config.ImageColumn("Aperçu (Image)")} if img_col_existing else {}
                    config_non_existing = {img_col_non_existing: st.column_config.ImageColumn("Aperçu (Image)")} if img_col_non_existing else {}

                    # --- AFFICHAGE ---
                    st.success(f"✅ Traitement terminé pour le Store ID : {store_filter}")
                    
                    tab1, tab2 = st.tabs(["✅ Produits Existants", "❌ Produits Non-Existants (Prix, Stock, Photos)"])
                    
                    with tab1:
                        st.subheader(f"Produits trouvés ({len(existing_products)} articles)")
                        # Affichage avec rendu d'image
                        st.dataframe(existing_products, use_container_width=True, column_config=config_existing)
                        st.download_button(
                            label="📥 Télécharger Produits Existants (CSV)",
                            data=existing_products.to_csv(index=False).encode('utf-8-sig'),
                            file_name=f"Existing_Products_Store_{store_filter}.csv",
                            mime="text/csv"
                        )
                    
                    with tab2:
                        st.subheader(f"Produits manquants ({len(non_existing_products)} articles)")
                        # Affichage avec rendu d'image
                        st.dataframe(non_existing_products, use_container_width=True, column_config=config_non_existing)
                        st.download_button(
                            label=f"📥 Télécharger Produits Non-Existants (CSV)",
                            data=non_existing_products.to_csv(index=False).encode('utf-8-sig'),
                            file_name=f"NonExisting_Products_Store_{store_filter}.csv",
                            mime="text/csv"
                        )
                else:
                    st.error("🚨 Erreur : Les fichiers doivent contenir la colonne `external_id`.")
                    
            except Exception as e:
                st.error(f"Une erreur s'est produite : {e}")
elif not assortiment_file or not menulist_file:
    st.info("👈 Veuillez uploader vos fichiers pour commencer.")
