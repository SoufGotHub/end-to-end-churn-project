# -*- coding: utf-8 -*-
"""
Étape 1 - Génération du dataset de churn à partir du schéma relationnel
=======================================================================
Projet : Prédiction de Churn & Segmentation Client (Portfolio 2025)

Ce script simule des données réalistes pour les tables du schéma SQL
(clients, produits, abonnements, facturation, interactions_support, usage_mensuel)
puis construit la table de base (une ligne par client) pour le modèle,
avec un déséquilibre de classes volontaire : ~85% rétention, ~15% churn.

Impact Business : Un dataset déséquilibré reflète la réalité terrain
(la majorité des clients restent fidèles). Les techniques SMOTE (étape 4)
permettront d'entraîner un modèle qui détecte malgré tout les futurs partants.

Usage : exécuter depuis la racine du projet
    python scripts/01_generate_dataset.py
"""

import os
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Configuration : graine et déséquilibre de classes
# -----------------------------------------------------------------------------
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# Cible : 85% rétention, 15% churn (déséquilibre fort, réaliste en télécom)
TAUX_CHURN_CIBLE = 0.15
NB_CLIENTS = 7000  # Ordre de grandeur du dataset Telco classique

# Répertoire de sortie (aligné avec data/raw)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_FILE = OUTPUT_DIR / "dataset_churn_simule.csv"


def _date_alea(debut: datetime, fin: datetime) -> datetime:
    """Génère une date aléatoire entre debut et fin."""
    delta = (fin - debut).days
    return debut + timedelta(days=random.randint(0, max(0, delta)))


def generer_clients(n: int) -> pd.DataFrame:
    """
    Génère la table clients (démographie + acquisition).
    Impact Business : canal et région servent au ciblage marketing.
    """
    genres = ["Male", "Female"]
    canaux = ["Web", "Télévente", "Magasin", "Partenariat"]
    regions = ["Île-de-France", "Provence", "Nord", "Occitanie", "Bretagne", "Auvergne-Rhône-Alpes"]

    debut_inscription = datetime(2019, 1, 1)
    fin_inscription = datetime(2024, 6, 1)

    clients = []
    for i in range(n):
        client_id = f"{random.randint(1000, 9999)}-{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=5))}"
        date_insc = _date_alea(debut_inscription, fin_inscription)
        clients.append({
            "client_id": client_id,
            "date_inscription": date_insc.strftime("%Y-%m-%d"),
            "genre": random.choice(genres),
            "senior_citizen": 1 if random.random() < 0.16 else 0,  # ~16% seniors
            "partenaire": random.choice(["Yes", "No"]),
            "personnes_a_charge": random.choice(["Yes", "No"]),
            "canal_acquisition": random.choices(canaux, weights=[40, 30, 20, 10])[0],
            "region": random.choice(regions),
        })
    return pd.DataFrame(clients)


def generer_produits() -> pd.DataFrame:
    """Catalogue produits (référentiel)."""
    return pd.DataFrame([
        {"produit_id": "DSL", "nom": "Internet DSL", "categorie": "Internet", "tarif_base": 35.0},
        {"produit_id": "FIBRE", "nom": "Fibre", "categorie": "Internet", "tarif_base": 65.0},
        {"produit_id": "MOBILE", "nom": "Mobile seul", "categorie": "Mobile", "tarif_base": 25.0},
        {"produit_id": "BUNDLE", "nom": "Internet + Mobile", "categorie": "Bundle", "tarif_base": 75.0},
    ])


def generer_abonnements(clients: pd.DataFrame, produits: pd.DataFrame, taux_churn: float) -> pd.DataFrame:
    """
    Génère les abonnements. Les clients « churn » ont statut='résilié' et date_fin renseignée.
    On biaise légèrement : moins de tenure et plus de contrats mensuels pour les churners.
    Impact Business : tenure et type de contrat sont des prédicteurs majeurs.
    """
    date_ref = datetime(2024, 12, 31)
    abonnements = []
    # On décide à l'avance qui churn (pour pouvoir biaiser facturation/support/usage)
    churners = set(random.sample(clients["client_id"].tolist(), int(len(clients) * taux_churn)))

    for _, row in clients.iterrows():
        client_id = row["client_id"]
        date_insc = datetime.strptime(row["date_inscription"], "%Y-%m-%d")
        is_churner = client_id in churners

        # Tenure : churners ont en moyenne moins d'ancienneté
        if is_churner:
            tenure_mois = max(1, int(np.random.lognormal(2, 1.2)))  # plus de nouveaux
        else:
            tenure_mois = max(1, int(np.random.lognormal(3, 1.0)))
        tenure_mois = min(tenure_mois, (date_ref - date_insc).days // 30)

        date_debut = date_ref - timedelta(days=tenure_mois * 30)
        prod = produits.sample(1).iloc[0]
        tarif = prod["tarif_base"] * (0.9 + random.random() * 0.2)

        # Contrat : mensuel plus fréquent chez les churners
        if is_churner:
            type_contrat = random.choices(["Mensuel", "1_an", "2_ans"], weights=[50, 35, 15])[0]
        else:
            type_contrat = random.choices(["Mensuel", "1_an", "2_ans"], weights=[25, 40, 35])[0]

        if is_churner:
            # Résiliation dans les 3 derniers mois de la période
            date_fin = _date_alea(date_ref - timedelta(days=90), date_ref)
            statut = "résilié"
        else:
            date_fin = None
            statut = "actif"

        abonnements.append({
            "client_id": client_id,
            "produit_id": prod["produit_id"],
            "date_debut": date_debut.strftime("%Y-%m-%d"),
            "date_fin": date_fin.strftime("%Y-%m-%d") if date_fin else None,
            "tarif_mensuel": round(tarif, 2),
            "type_contrat": type_contrat,
            "facturation_sans_papier": random.choice(["Yes", "No"]),
            "mode_paiement": random.choice(["CB", "Virement", "Prélèvement", "Chèque"]),
            "statut": statut,
        })
    return pd.DataFrame(abonnements)


def generer_facturation(clients: pd.DataFrame, abonnements: pd.DataFrame, churn_ids: set) -> pd.DataFrame:
    """
    Historique de facturation. Les churners ont plus de retards de paiement.
    Impact Business : retard = signal de friction et risque de départ.
    """
    factures = []
    date_debut_periode = datetime(2024, 1, 1)
    date_ref = datetime(2024, 12, 31)
    abo = abonnements.set_index("client_id")

    for client_id in clients["client_id"]:
        if client_id not in abo.index:
            continue
        tarif = abo.loc[client_id, "tarif_mensuel"]
        nb_mois = min(12, (date_ref - date_debut_periode).days // 30)
        proba_retard = 0.35 if client_id in churn_ids else 0.12
        for m in range(nb_mois):
            date_facture = date_debut_periode + timedelta(days=m * 30)
            paye_a_temps = 0 if random.random() < proba_retard else 1
            factures.append({
                "client_id": client_id,
                "date_facture": date_facture.strftime("%Y-%m-%d"),
                "montant": round(tarif * (0.95 + random.random() * 0.1), 2),
                "paye_a_temps": paye_a_temps,
            })
    return pd.DataFrame(factures)


def generer_interactions_support(clients: pd.DataFrame, churn_ids: set) -> pd.DataFrame:
    """
    Tickets / appels support. Les churners ont plus d'interactions et plus de thèmes « résiliation ».
    Impact Business : volume et thème résiliation = indicateurs de mécontentement.
    """
    interactions = []
    date_debut = datetime(2024, 1, 1)
    date_fin = datetime(2024, 12, 31)
    for client_id in clients["client_id"]:
        is_churner = client_id in churn_ids
        nb_interactions = np.random.poisson(3 if is_churner else 0.8)
        for _ in range(min(nb_interactions, 15)):
            date_int = _date_alea(date_debut, date_fin)
            if is_churner and random.random() < 0.4:
                theme = "résiliation"
                resolution = 0 if random.random() < 0.5 else 1
            else:
                theme = random.choice(["technique", "facturation", "résiliation"])
                resolution = 1 if random.random() < 0.75 else 0
            interactions.append({
                "client_id": client_id,
                "date_interaction": date_int.strftime("%Y-%m-%d"),
                "type_interaction": random.choice(["appel", "ticket", "chat"]),
                "theme": theme,
                "resolution_satisfaisante": resolution,
            })
    return pd.DataFrame(interactions)


def generer_usage_mensuel(clients: pd.DataFrame, abonnements: pd.DataFrame, churn_ids: set) -> pd.DataFrame:
    """
    Usage mensuel (connexions, volume). Les churners ont une baisse d'usage sur les derniers mois.
    Impact Business : baisse d'engagement = signal précoce de churn.
    """
    usages = []
    for _, row in abonnements.iterrows():
        client_id = row["client_id"]
        is_churner = client_id in churn_ids
        date_debut = datetime.strptime(row["date_debut"], "%Y-%m-%d")
        base_connexions = random.randint(20, 120)
        base_volume = random.uniform(20, 200)
        for m in range(12):
            mois = date_debut + timedelta(days=m * 30)
            if mois > datetime(2024, 12, 31):
                break
            # Churners : baisse progressive sur les 3 derniers mois
            if is_churner and m >= 9:
                dec = 0.5 - (m - 9) * 0.15
            else:
                dec = 1.0
            nb_connexions = max(0, int(base_connexions * (0.8 + random.random() * 0.4) * dec))
            volume_go = max(0, round(base_volume * (0.8 + random.random() * 0.4) * dec, 2))
            usages.append({
                "client_id": client_id,
                "mois": mois.strftime("%Y-%m-%d"),
                "nb_connexions": nb_connexions,
                "volume_data_go": volume_go,
                "duree_appels_min": random.randint(0, 120),
            })
    return pd.DataFrame(usages)


def construire_table_features(
    clients: pd.DataFrame,
    produits: pd.DataFrame,
    abonnements: pd.DataFrame,
    facturation: pd.DataFrame,
    interactions: pd.DataFrame,
    usage: pd.DataFrame,
    churn_ids: set,
) -> pd.DataFrame:
    """
    Reconstruit la table plate « une ligne par client » comme la requête SQL d'extraction.
    Agrégations : facturation, support, usage avec tendance (3 derniers vs 3 mois avant).
    """
    date_ref = datetime(2024, 12, 31)
    debut_periode = datetime(2024, 1, 1)

    # Abonnements : dernier par client
    abo = abonnements.copy()
    abo["date_debut_dt"] = pd.to_datetime(abo["date_debut"])
    abo = abo.sort_values("date_debut_dt").groupby("client_id").last().reset_index()
    abo["tenure_mois"] = abo["date_debut_dt"].apply(
        lambda d: max(0, (date_ref - d.to_pydatetime()).days // 30)
    )
    abo = abo.merge(produits[["produit_id", "categorie"]], on="produit_id", how="left")
    abo = abo.rename(columns={"categorie": "categorie_produit", "tarif_mensuel": "charges_mensuelles"})

    # Facturation
    facturation["date_facture_dt"] = pd.to_datetime(facturation["date_facture"])
    facturation = facturation[
        (facturation["date_facture_dt"] >= debut_periode) & (facturation["date_facture_dt"] <= date_ref)
    ]
    agg_fact = facturation.groupby("client_id").agg(
        nb_factures=("montant", "count"),
        total_charges=("montant", "sum"),
        nb_retards_paiement=("paye_a_temps", lambda x: (x == 0).sum()),
    ).reset_index()
    agg_fact["ratio_retards_paiement"] = agg_fact["nb_retards_paiement"] / agg_fact["nb_factures"].replace(0, 1)

    # Support
    interactions["date_interaction_dt"] = pd.to_datetime(interactions["date_interaction"])
    interactions = interactions[
        (interactions["date_interaction_dt"] >= debut_periode) & (interactions["date_interaction_dt"] <= date_ref)
    ]
    agg_support = interactions.groupby("client_id").agg(
        nb_interactions_support=("theme", "count"),
        nb_contacts_resiliation=("theme", lambda x: (x == "résiliation").sum()),
        taux_resolution_satisfaisante=("resolution_satisfaisante", "mean"),
    ).reset_index()

    # Usage : tendance 3 derniers mois vs 3 mois d'avant
    usage["mois_dt"] = pd.to_datetime(usage["mois"])
    usage = usage[(usage["mois_dt"] >= debut_periode) & (usage["mois_dt"] <= date_ref)]
    usage = usage.sort_values(["client_id", "mois_dt"])
    usage["rn"] = usage.groupby("client_id").cumcount()
    usage["reverse_rn"] = usage.groupby("client_id")["rn"].transform("max") - usage["rn"]
    connexions_3derniers = usage[usage["reverse_rn"] < 3].groupby("client_id")["nb_connexions"].mean().reset_index()
    connexions_3derniers = connexions_3derniers.rename(columns={"nb_connexions": "connexions_moy_3derniers_mois"})
    connexions_3avant = usage[(usage["reverse_rn"] >= 3) & (usage["reverse_rn"] < 6)].groupby("client_id")["nb_connexions"].mean().reset_index()
    connexions_3avant = connexions_3avant.rename(columns={"nb_connexions": "connexions_moy_3mois_avant"})
    total_usage = usage.groupby("client_id").agg(
        total_connexions_12_mois=("nb_connexions", "sum"),
        total_volume_go_12_mois=("volume_data_go", "sum"),
    ).reset_index()
    usage_agg = connexions_3derniers.merge(connexions_3avant, on="client_id", how="outer").fillna(0)
    usage_agg = usage_agg.merge(total_usage, on="client_id", how="outer").fillna(0)
    usage_agg["evolution_connexions_ratio"] = np.where(
        usage_agg["connexions_moy_3mois_avant"] > 0,
        (usage_agg["connexions_moy_3derniers_mois"] - usage_agg["connexions_moy_3mois_avant"])
        / usage_agg["connexions_moy_3mois_avant"],
        0,
    )

    # Assemblage
    df = clients.merge(
        abo[["client_id", "tenure_mois", "type_contrat", "charges_mensuelles", "categorie_produit", "statut"]],
        on="client_id",
        how="inner",
    )
    df = df.merge(agg_fact, on="client_id", how="left")
    df = df.merge(agg_support, on="client_id", how="left")
    df = df.merge(usage_agg, on="client_id", how="left")
    df["churn"] = (df["client_id"].isin(churn_ids)).astype(int)
    # Nettoyage des NaN issus des LEFT JOIN
    for col in ["nb_factures", "total_charges", "nb_retards_paiement", "ratio_retards_paiement",
                "nb_interactions_support", "nb_contacts_resiliation", "taux_resolution_satisfaisante",
                "total_connexions_12_mois", "connexions_moy_3derniers_mois", "connexions_moy_3mois_avant",
                "total_volume_go_12_mois", "evolution_connexions_ratio"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    df["taux_resolution_satisfaisante"] = df["taux_resolution_satisfaisante"].fillna(1.0)
    return df


def main():
    print("Génération des données selon le schéma relationnel (télécom)...")
    clients = generer_clients(NB_CLIENTS)
    produits = generer_produits()
    churn_ids = set(random.sample(clients["client_id"].tolist(), int(NB_CLIENTS * TAUX_CHURN_CIBLE)))
    abonnements = generer_abonnements(clients, produits, TAUX_CHURN_CIBLE)
    facturation = generer_facturation(clients, abonnements, churn_ids)
    interactions = generer_interactions_support(clients, churn_ids)
    usage = generer_usage_mensuel(clients, abonnements, churn_ids)
    print("Construction de la table de features (équivalent requête SQL)...")
    df = construire_table_features(
        clients, produits, abonnements, facturation, interactions, usage, churn_ids
    )
    # Colonnes pour le ML : on garde un export propre (noms compatibles avec la suite du projet)
    colonnes_export = [
        "client_id", "date_inscription", "genre", "senior_citizen", "partenaire", "personnes_a_charge",
        "canal_acquisition", "region", "tenure_mois", "type_contrat", "charges_mensuelles", "categorie_produit",
        "nb_factures", "total_charges", "nb_retards_paiement", "ratio_retards_paiement",
        "nb_interactions_support", "nb_contacts_resiliation", "taux_resolution_support",
        "total_connexions_12_mois", "connexions_moy_3derniers_mois", "connexions_moy_3mois_avant",
        "total_volume_go_12_mois", "evolution_connexions_ratio", "churn",
    ]
    df["taux_resolution_support"] = df["taux_resolution_satisfaisante"]
    df_export = df[[c for c in colonnes_export if c in df.columns]]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df_export.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    taux_churn_observe = df_export["churn"].mean()
    print(f"Dataset exporté : {OUTPUT_FILE}")
    print(f"Nombre de lignes : {len(df_export)}")
    print(f"Taux de churn (cible ~{TAUX_CHURN_CIBLE*100:.0f}%) : {taux_churn_observe*100:.2f}%")


if __name__ == "__main__":
    main()
