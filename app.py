import streamlit as st
import pandas as pd

st.set_page_config(page_title="Assortiment vs MenuList Matcher", layout="wide")

st.title("📦 Assortiment vs MenuList Matcher")
st.markdown("Uploadez vos fichiers pour identifier les produits existants et manquants en fonction du **Store ID** choisi, et enrichir les produits manquants avec leurs prix et quantités.")

# Barre latérale pour l'upload des fichiers
st.sidebar.header("1. Upload des Fichiers")
assortiment_file = st.sidebar.file_uploader("1️⃣ Fichier Assortiment (CSV ou Excel)", type=['csv', 'xlsx'])
menulist_file = st.sidebar.file_uploader("2️⃣ Fichier MenuList (CSV)", type=['csv'])
pricing_file = st.sidebar.file_uploader("3️⃣ Fichier Prix & Quantités (Ex: invalid_rows.csv)", type=['csv'])

# Variables globales pour le traitement
df_assort = None
store_col = None
store_filter = None

# Étape 1 : Lecture de l'assortiment et sélection du Store ID
if assortiment_file:
    try:
        if assortiment_file.name.endswith('.csv'):
            df_assort = pd.read_csv(assortiment_file)
        else:
            df_assort = pd.read_excel(assortiment_file)
            
        # Cherche une colonne qui ressemble à "store" ou "magasin"
        store_col = next((col for col in df_assort.columns if 'store' in col.lower() or 'magasin' in col.lower()), None)
        
        st.sidebar.header("2. Choix du Magasin")
        if store_col:
            # Récupérer les Store IDs uniques et nettoyer
            unique_stores = df_assort[store_col].dropna().astype(str).str.replace(r'\.0$', '', regex=True).unique().tolist()
            unique_stores.sort()
            
            store_filter = st.sidebar.selectbox("Sélectionnez le Store ID :", unique_stores, index=unique_stores.index('170') if '170' in unique_stores else 0)
            st.sidebar.success(f"Colonne de magasin détectée : '{store_col}'")
        else:
            store_filter = st.sidebar.text_input("Entrez le Store ID manuellement (ex: 170)", value="170")
            st.sidebar.warning("Aucune colonne 'store' ou 'magasin' détectée automatiquement.")
            
    except Exception as e:
        st.sidebar.error(f"Erreur lors de la lecture de l'assortiment : {e}")

# Étape 2 : Traitement une fois les fichiers uploadés
if df_assort is not None and menulist_file:
    if st.sidebar.button("Lancer la correspondance 🚀"):
        with st.spinner('Traitement des données en cours...'):
            try:
                # Lecture de la MenuList
                df_menu = pd.read_csv(menulist_file, sep=';', dtype=str)
                
                if 'external_id' in df_assort.columns and 'external_id' in df_menu.columns:
                    # Nettoyage des ID pour la jointure
                    df_assort['external_id'] = df_assort['external_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                    df_menu['external_id'] = df_menu['external_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                    
                    # Filtrer l'assortiment par le Store ID
                    if store_col:
                        df_assort_filtered = df_assort[df_assort[store_col].astype(str).str.replace(r'\.0$', '', regex=True) == str(store_filter)]
                    else:
                        df_assort_filtered = df_assort
                    
                    # Jointure avec MenuList
                    menu_subset = df_menu[['external_id', 'food_id']].drop_duplicates(subset=['external_id'])
                    merged = pd.merge(df_assort_filtered, menu_subset, on='external_id', how='left')
                    
                    # Séparation
                    existing_products = merged[merged['food_id'].notna()].copy()
                    non_existing_products = merged[merged['food_id'].isna()].copy()
                    
                    # --- Étape 3 : Enrichissement avec le 3ème fichier (Prix et Quantités) ---
                    if pricing_file is not None:
                        df_pricing = pd.read_csv(pricing_file)
                        
                        # Nettoyer l'ID produit du fichier de prix pour la correspondance
                        if 'product_id' in df_pricing.columns:
                            df_pricing['product_id'] = df_pricing['product_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                            
                            # Filtrer le fichier de prix pour le Store ID sélectionné (si la colonne existe)
                            if 'store_id' in df_pricing.columns and store_filter:
                                df_pricing = df_pricing[df_pricing['store_id'].astype(str).str.replace(r'\.0$', '', regex=True) == str(store_filter)]
                            
                            # Conserver uniquement les colonnes utiles (on suppose 'price' et 'stock')
                            cols_to_keep = ['product_id']
                            if 'price' in df_pricing.columns: cols_to_keep.append('price')
                            if 'stock' in df_pricing.columns: cols_to_keep.append('stock')
                            
                            pricing_subset = df_pricing[cols_to_keep].drop_duplicates(subset=['product_id'])
                            
                            # Fusionner avec les produits non-existants
                            non_existing_products = pd.merge(
                                non_existing_products, 
                                pricing_subset, 
                                left_on='external_id', 
                                right_on='product_id', 
                                how='left'
                            )
                            # Supprimer la colonne product_id en double après la fusion
                            if 'product_id' in non_existing_products.columns:
                                non_existing_products = non_existing_products.drop(columns=['product_id'])
                                
                            st.success(f"✅ Fichier Prix & Quantités intégré avec succès pour le Store {store_filter} !")
                        else:
                            st.warning("⚠️ La colonne 'product_id' n'a pas été trouvée dans le fichier Prix & Quantités. Enrichissement ignoré.")

                    # --- AFFICHAGE ---
                    st.success(f"✅ Traitement terminé pour le Store ID : {store_filter}")
                    
                    tab1, tab2 = st.tabs(["✅ Produits Existants", "❌ Produits Non-Existants (avec Prix/Stock)"])
                    
                    with tab1:
                        st.subheader(f"Produits trouvés dans la MenuList ({len(existing_products)} articles)")
                        st.dataframe(existing_products, use_container_width=True)
                        st.download_button(
                            label="📥 Télécharger Produits Existants (CSV)",
                            data=existing_products.to_csv(index=False).encode('utf-8-sig'),
                            file_name=f"Existing_Products_Store_{store_filter}.csv",
                            mime="text/csv"
                        )
                    
                    with tab2:
                        st.subheader(f"Produits manquants dans la MenuList ({len(non_existing_products)} articles)")
                        st.dataframe(non_existing_products, use_container_width=True)
                        st.download_button(
                            label=f"📥 Télécharger Produits Non-Existants (CSV)",
                            data=non_existing_products.to_csv(index=False).encode('utf-8-sig'),
                            file_name=f"NonExisting_Products_Store_{store_filter}.csv",
                            mime="text/csv"
                        )
                else:
                    st.error("🚨 Erreur : Les fichiers Assortiment et MenuList doivent contenir la colonne `external_id`.")
                    
            except Exception as e:
                st.error(f"Une erreur s'est produite lors du traitement : {e}")
elif not assortiment_file or not menulist_file:
    st.info("👈 Veuillez uploader vos fichiers dans la barre latérale, puis choisir votre Store ID.")
