# -*- coding: utf-8 -*-
"""
Étape 2 - Entraînement d'un premier modèle de prédiction de churn
=================================================================
Projet : Prédiction de Churn & Segmentation Client (Portfolio 2025)

Ce script charge le dataset généré à l'étape 1, prépare les données
et entraîne un modèle simple (Régression Logistique) pour prédire le churn.

Usage : exécuter depuis la racine du projet
    python scripts/02_train_model.py
"""

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.preprocessing import OneHotEncoder
from pathlib import Path
import joblib

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "raw" / "dataset_churn_simule.csv"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_FILE = MODEL_DIR / "churn_logistic_regression.joblib"

# Créer le dossier pour les modèles s'il n'existe pas
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# 1. Chargement des données
# -----------------------------------------------------------------------------
print("Chargement du dataset...")
df = pd.read_csv(DATA_FILE)

# -----------------------------------------------------------------------------
# 2. Préparation des données pour le modèle
# -----------------------------------------------------------------------------
print("Préparation des données...")

# Variable cible
target = 'churn'
y = df[target]

# Sélection des features (excluons les identifiants et dates)
features = df.drop(columns=[target, 'client_id', 'date_inscription'])

# Identification des variables catégorielles et numériques
categorical_features = features.select_dtypes(include=['object']).columns
numerical_features = features.select_dtypes(include=['number']).columns

# Encodage des variables catégorielles (One-Hot Encoding)
encoder = OneHotEncoder(handle_unknown='ignore', sparse_output=False)
encoded_cats = encoder.fit_transform(features[categorical_features])
encoded_cats_df = pd.DataFrame(encoded_cats, columns=encoder.get_feature_names_out(categorical_features))

# Concaténation des features numériques et encodées
X = pd.concat([features[numerical_features].reset_index(drop=True), encoded_cats_df], axis=1)

# Division en ensembles d'entraînement et de test
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

print(f"Taille de l'ensemble d'entraînement : {X_train.shape[0]} clients")
print(f"Taille de l'ensemble de test : {X_test.shape[0]} clients")


# -----------------------------------------------------------------------------
# 3. Entraînement du modèle (Régression Logistique)
# -----------------------------------------------------------------------------
print("Entraînement du modèle de régression logistique...")
logreg = LogisticRegression(random_state=42, max_iter=1000, class_weight='balanced')
logreg.fit(X_train, y_train)

# -----------------------------------------------------------------------------
# 4. Évaluation du modèle
# -----------------------------------------------------------------------------
print("Évaluation du modèle...")
y_pred = logreg.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)
print(f"Précision (Accuracy) : {accuracy:.4f}")

print("\nMatrice de confusion :")
print(confusion_matrix(y_test, y_pred))

print("\nRapport de classification :")
print(classification_report(y_test, y_pred))


# -----------------------------------------------------------------------------
# 5. Sauvegarde du modèle entraîné
# -----------------------------------------------------------------------------
print(f"Sauvegarde du modèle dans : {MODEL_FILE}")
joblib.dump(logreg, MODEL_FILE)
print("Modèle sauvegardé avec succès.")
